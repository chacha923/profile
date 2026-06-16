#!/usr/bin/env python3
"""
otel-logs-query client — log search, aggregation & error analysis.

7 commands:
  health         Check connectivity
  list-apps      List registered applications (by owner/name/tenant/language)
  search-logs    Search logs with filters (v3 API)
  aggregate      Aggregate logs by field — group by + count/sum/... (v3 API)
  trend          Error trend chart — time series PNG with auto bucket sizing
  fields         List available log fields
  error-summary  Error analysis (types / timeline / list)

Env:    PLATFORM_ENV unset/"prod"/"production" → prod URL (default).
        PLATFORM_ENV=test|dev|local|staging → test URL.
Time:   --start/--end accept "30m ago", "1h ago", "now", "2026-04-14 22:00", or raw ns.
"""

import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared", "scripts"))
from otel_client_common import (
    OtelClient,
    enforce_time_range,
    format_services_table,
    parse_time_to_ns,
    print_json,
    query_services,
    resolve_base_url,
    resolve_token,
    validate_limit,
    warn_high_cardinality_group_by,
)


# ---------------------------------------------------------------------------
# v3 query_range helpers
# ---------------------------------------------------------------------------

# Static log columns that are top-level in ClickHouse schema
_STATIC_FIELDS = {
    "severity_text": {"dataType": "string", "isColumn": True},
    "severity_number": {"dataType": "uint8", "isColumn": True},
    "body": {"dataType": "string", "isColumn": True},
    "trace_id": {"dataType": "string", "isColumn": True},
    "span_id": {"dataType": "string", "isColumn": True},
}


def _field_to_v3_key(field: str) -> dict:
    """Convert a q-syntax field name to v3 filter key object."""
    # Static fields
    if field in _STATIC_FIELDS:
        info = _STATIC_FIELDS[field]
        dt = info["dataType"]
        return {"key": field, "dataType": dt, "type": "", "isColumn": True, "isJSON": False,
                "id": f"{field}--{dt}----true"}
    # resources_string.X → resource
    if field.startswith("resources_string."):
        key = field[17:]
        return {"key": key, "dataType": "string", "type": "resource", "isColumn": False, "isJSON": False,
                "id": f"{key}--string--resource--true"}
    # attributes_string.X → tag
    if field.startswith("attributes_string."):
        key = field[18:]
        return {"key": key, "dataType": "string", "type": "tag", "isColumn": False, "isJSON": False,
                "id": f"{key}--string--tag--true"}
    # attributes_int.X → tag int64
    if field.startswith("attributes_int."):
        key = field[15:]
        return {"key": key, "dataType": "int64", "type": "tag", "isColumn": False, "isJSON": False,
                "id": f"{key}--int64--tag--true"}
    # Shorthand: treat bare dotted names as resource fields (e.g. service.name)
    return {"key": field, "dataType": "string", "type": "resource", "isColumn": False, "isJSON": False,
            "id": f"{field}--string--resource--true"}


def _parse_single_filter(expr: str) -> dict | None:
    """Parse one filter expression like 'severity_text=ERROR' or 'body contains timeout'."""
    expr = expr.strip()
    if not expr:
        return None
    # != before =
    if "!=" in expr:
        field, value = expr.split("!=", 1)
        return {"key": _field_to_v3_key(field.strip()), "op": "!=", "value": value.strip()}
    # Word operators
    for op in ("ncontains", "contains", "nin", "gte", "gt", "lte", "lt", "nexists", "exists", "in"):
        m = re.match(rf"^(.+?)\s+{op}\s+(.*)$", expr, re.IGNORECASE)
        if m:
            field = m.group(1).strip()
            value = m.group(2).strip() if op not in ("exists", "nexists") else ""
            return {"key": _field_to_v3_key(field), "op": op, "value": value}
    # =
    if "=" in expr:
        field, value = expr.split("=", 1)
        return {"key": _field_to_v3_key(field.strip()), "op": "=", "value": value.strip()}
    return None


def _parse_q_to_v3_filters(q: str | None) -> dict:
    """Parse --q filter string into v3 filters object."""
    if not q or not q.strip():
        return {"items": [], "op": "AND"}
    parts = re.split(r"\s+AND\s+", q, flags=re.IGNORECASE)
    items = [item for p in parts if (item := _parse_single_filter(p))]
    return {"items": items, "op": "AND"}


def _build_v3_log_query(start_ms: int, end_ms: int, filters: dict,
                         limit: int, order: str) -> dict:
    """Build the v3 query_range request body for log search."""
    return {
        "start": start_ms,
        "end": end_ms,
        "step": 60,
        "variables": {},
        "compositeQuery": {
            "queryType": "builder",
            "panelType": "list",
            "builderQueries": {
                "A": {
                    "dataSource": "logs",
                    "queryName": "A",
                    "aggregateOperator": "noop",
                    "aggregateAttribute": {
                        "id": "------false", "dataType": "", "key": "",
                        "isColumn": False, "type": "", "isJSON": False,
                    },
                    "timeAggregation": "rate",
                    "spaceAggregation": "sum",
                    "functions": [],
                    "filters": filters,
                    "expression": "A",
                    "disabled": False,
                    "having": [],
                    "stepInterval": 60,
                    "limit": None,
                    "orderBy": [{"columnName": "timestamp", "order": order}],
                    "groupBy": [],
                    "legend": "",
                    "reduceTo": "avg",
                    "offset": 0,
                    "pageSize": limit,
                }
            },
        },
    }


def _build_v3_aggregate_query(start_ms: int, end_ms: int, filters: dict,
                               group_by_field: str, agg_op: str = "count",
                               step: int = 60, order: str = "desc") -> dict:
    """Build v3 query_range request for aggregation (panelType=table)."""
    group_by_key = _field_to_v3_key(group_by_field)
    return {
        "start": start_ms,
        "end": end_ms,
        "step": step,
        "variables": {},
        "compositeQuery": {
            "queryType": "builder",
            "panelType": "table",
            "builderQueries": {
                "A": {
                    "dataSource": "logs",
                    "queryName": "A",
                    "aggregateOperator": agg_op,
                    "aggregateAttribute": {
                        "id": "------false", "dataType": "", "key": "",
                        "isColumn": False, "type": "", "isJSON": False,
                    },
                    "timeAggregation": "rate",
                    "spaceAggregation": "sum",
                    "functions": [],
                    "filters": filters,
                    "expression": "A",
                    "disabled": False,
                    "having": [],
                    "stepInterval": step,
                    "limit": None,
                    "orderBy": [{"columnName": "#SIGNOZ_VALUE", "order": order}],
                    "groupBy": [group_by_key],
                    "legend": "",
                    "reduceTo": "avg",
                    "offset": 0,
                    "pageSize": 100,
                }
            },
        },
    }


def _extract_v3_logs(response: dict) -> list:
    """Extract log entries from v3 query_range response into flat list."""
    try:
        results = response.get("data", {}).get("result", [])
        logs = []
        for qr in results:
            for entry in qr.get("list") or []:
                log = {"timestamp": entry.get("timestamp", "")}
                log.update(entry.get("data", {}))
                _enrich_code_location(log)
                logs.append(log)
        return logs
    except (KeyError, TypeError):
        return []


# ---------------------------------------------------------------------------
# Code location extraction
# ---------------------------------------------------------------------------

# Regex: "at com.soul.xxx.Class.method(File.java:123)"
_STACK_FRAME_RE = re.compile(
    r"at\s+([\w.$]+)\.([\w$]+)\((\w+\.java):(\d+)\)"
)

# Framework packages to skip when extracting business frames from stacktrace
_FRAMEWORK_PREFIXES = (
    "org.springframework.", "org.apache.", "javax.", "java.",
    "sun.", "com.sun.", "jdk.", "io.netty.", "reactor.",
    "com.alibaba.dubbo.", "org.apache.dubbo.",
    "com.mysql.", "com.zaxxer.hikari.",
)


def _parse_stacktrace(stacktrace: str) -> list[dict]:
    """Parse a Java stacktrace and extract business-relevant frames.

    Returns a list of dicts with keys: class, method, file, line.
    Filters out framework/library frames, keeps only business code.
    """
    if not stacktrace:
        return []
    frames = []
    for m in _STACK_FRAME_RE.finditer(stacktrace):
        full_class = m.group(1)
        # Skip framework frames
        if any(full_class.startswith(p) for p in _FRAMEWORK_PREFIXES):
            continue
        # Skip CGLIB/proxy generated frames
        if "$$" in full_class or "<generated>" in m.group(0):
            continue
        frames.append({
            "class": full_class,
            "method": m.group(2),
            "file": m.group(3),
            "line": int(m.group(4)),
        })
    return frames


def _enrich_code_location(log: dict) -> None:
    """Add _code_location summary to a log entry.

    Extracts from two sources:
    1. Log attributes: code.namespace, code.function, code.filepath, code.lineno
    2. Stacktrace: parsed business frames (filtered from framework noise)
    """
    attrs_str = log.get("attributes_string", {})
    attrs_int = log.get("attributes_int64", {})

    code_loc = {}

    # Source 1: log attributes (where the log statement was emitted)
    namespace = attrs_str.get("code.namespace", "")
    filepath = attrs_str.get("code.filepath", "")
    function = attrs_str.get("code.function", "")
    lineno = attrs_int.get("code.lineno", 0)
    if namespace and filepath:
        code_loc["log_source"] = {
            "class": namespace,
            "method": function,
            "file": filepath,
            "line": lineno,
        }

    # Source 2: stacktrace (the actual error origin)
    stacktrace = attrs_str.get("exception.stacktrace", "")
    if stacktrace:
        biz_frames = _parse_stacktrace(stacktrace)
        if biz_frames:
            code_loc["error_origin"] = biz_frames[0]  # top business frame = root cause
            if len(biz_frames) > 1:
                code_loc["call_chain"] = biz_frames[1:]  # remaining = call chain

    if code_loc:
        log["_code_location"] = code_loc


def _extract_v3_aggregate(response: dict) -> list:
    """Extract aggregation results from v3 query_range response into flat rows."""
    try:
        results = response.get("data", {}).get("result", [])
        rows = []
        for qr in results:
            for series in qr.get("series") or []:
                labels = series.get("labels", {})
                for val in series.get("values") or []:
                    row = dict(labels)
                    row["count"] = val.get("value", 0)
                    rows.append(row)
        return rows
    except (KeyError, TypeError):
        return []


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_health(client: OtelClient, args: argparse.Namespace) -> None:
    """Check service connectivity."""
    result = client.get("/api/v1/logs/fields")
    print(f"[OK] {client.base_url} is reachable")
    print_json(result)


def cmd_list_apps(client: OtelClient, args: argparse.Namespace) -> None:
    """List registered applications."""
    start_ns = parse_time_to_ns(args.start) if args.start else parse_time_to_ns("15m ago")
    end_ns = parse_time_to_ns(args.end) if args.end else parse_time_to_ns("now")
    result = query_services(
        client, start_ns, end_ns,
        owner=args.owner or "",
        service_name=args.name or "",
        tenant=args.tenant or "",
        language=[args.language] if args.language else [],
        page=args.page,
        page_size=args.page_size,
    )
    if args.json:
        print_json(result)
    else:
        print(format_services_table(result))


def _filter_fields(filters: dict) -> set[str]:
    """Return the set of field keys present in the parsed v3 filter set."""
    fields = set()
    for item in (filters or {}).get("items", []) or []:
        key = (item.get("key") or {}).get("key") or ""
        if key:
            fields.add(key)
    return fields


def cmd_search_logs(client: OtelClient, args: argparse.Namespace) -> None:
    """Search logs via v3 query_range API."""
    start_ns = parse_time_to_ns(args.start)
    end_ns = parse_time_to_ns(args.end)
    enforce_time_range(start_ns, end_ns, "search", "search-logs")
    start_ms = start_ns // 1_000_000
    end_ms = end_ns // 1_000_000
    filters = _parse_q_to_v3_filters(args.q)

    # Route-guard: logs are routed to per-service tables (see app_ck mapping).
    # A trace_id-only filter hits the wrong table and returns 0 rows silently.
    fields = _filter_fields(filters)
    if "trace_id" in fields and "service.name" not in fields:
        print(
            "WARNING: [search-logs] filter has 'trace_id' but no 'service.name'. "
            "Backend routes logs by service → per-service table (app_ck mapping); "
            "results will likely be empty. "
            "Use `trace-logs --trace-id <id>` for a full cross-service pull, "
            "or add `service.name=<svc>` to the -q expression.",
            file=sys.stderr,
        )

    if getattr(args, "exhaust", False):
        # Exhaust mode: paginate until all logs are fetched (max 20 pages)
        all_logs: list = []
        page_size = min(args.limit, 200)
        max_pages = 20
        current_end_ms = end_ms

        for page in range(1, max_pages + 1):
            body = _build_v3_log_query(start_ms, current_end_ms, filters, page_size, "desc")
            result = client.post("/api/v3/query_range", body)
            batch = _extract_v3_logs(result)
            if not batch:
                break
            all_logs.extend(batch)
            print(f"[exhaust] Page {page}: fetched {len(batch)} logs (total: {len(all_logs)})",
                  file=sys.stderr)
            if len(batch) < page_size:
                break
            # Move cursor: use the oldest log's timestamp as new end
            oldest_ts = batch[-1].get("timestamp", "")
            if oldest_ts:
                # Subtract 1ms to avoid duplicates
                current_end_ms = int(oldest_ts) // 1_000_000 - 1
            else:
                break

        # Sort by timestamp ascending for readability
        all_logs.sort(key=lambda x: x.get("timestamp", ""))
        print_json({"results": all_logs, "total": len(all_logs),
                     "pages_fetched": min(page, max_pages)})
    else:
        args.limit = validate_limit(args.limit, "search", "search-logs")
        body = _build_v3_log_query(start_ms, end_ms, filters, args.limit, args.order)
        result = client.post("/api/v3/query_range", body)
        logs = _extract_v3_logs(result)
        print_json({"results": logs, "total": len(logs)})


def cmd_aggregate(client: OtelClient, args: argparse.Namespace) -> None:
    """Aggregate logs by a field via v3 query_range (panelType=table)."""
    start_ns = parse_time_to_ns(args.start)
    end_ns = parse_time_to_ns(args.end)
    enforce_time_range(start_ns, end_ns, "aggregate", "aggregate")
    warn_high_cardinality_group_by(args.group_by, "aggregate")
    start_ms = start_ns // 1_000_000
    end_ms = end_ns // 1_000_000
    filters = _parse_q_to_v3_filters(args.q)

    # Calculate step = entire time range (single bucket)
    step = max((end_ms - start_ms) // 1000, 60)

    body = _build_v3_aggregate_query(
        start_ms, end_ms, filters,
        group_by_field=args.group_by,
        agg_op=args.function,
        step=step,
        order=args.order,
    )
    result = client.post("/api/v3/query_range", body)
    rows = _extract_v3_aggregate(result)

    # Sort by count descending
    rows.sort(key=lambda r: float(r.get("count", 0)), reverse=(args.order == "desc"))
    if args.limit:
        rows = rows[:args.limit]

    print_json({"results": rows, "total": len(rows)})


def cmd_trend(client: OtelClient, args: argparse.Namespace) -> None:
    """Error trend chart — group by exception.type over time buckets, output a PNG."""
    start_ns = parse_time_to_ns(args.start)
    end_ns = parse_time_to_ns(args.end)
    enforce_time_range(start_ns, end_ns, "trend", "trend")
    start_ms = start_ns // 1_000_000
    end_ms = end_ns // 1_000_000

    # Auto-calculate bucket size: aim for 10~15 data points
    range_sec = (end_ms - start_ms) // 1000
    step = max(range_sec // 12, 60)

    filters = _parse_q_to_v3_filters(args.q)
    # Always include severity_text=ERROR unless user explicitly filters
    if "severity_text" not in (args.q or ""):
        filters["items"].append({
            "key": _field_to_v3_key("severity_text"),
            "op": "=",
            "value": "ERROR",
        })
    # Add service filter if provided
    if args.service:
        filters["items"].append({
            "key": _field_to_v3_key("service.name"),
            "op": "=",
            "value": args.service,
        })

    group_by_key = _field_to_v3_key(args.group_by)
    body = {
        "start": start_ms, "end": end_ms, "step": step, "variables": {},
        "compositeQuery": {
            "queryType": "builder", "panelType": "graph",
            "builderQueries": {
                "A": {
                    "dataSource": "logs", "queryName": "A",
                    "aggregateOperator": "count",
                    "aggregateAttribute": {
                        "id": "------false", "dataType": "", "key": "",
                        "isColumn": False, "type": "", "isJSON": False,
                    },
                    "timeAggregation": "rate", "spaceAggregation": "sum",
                    "functions": [], "filters": filters,
                    "expression": "A", "disabled": False, "having": [],
                    "stepInterval": step, "limit": None,
                    "orderBy": [{"columnName": "timestamp", "order": "asc"}],
                    "groupBy": [group_by_key],
                    "legend": "", "reduceTo": "avg", "offset": 0, "pageSize": 100,
                }
            },
        },
    }

    result = client.post("/api/v3/query_range", body)

    # Extract time series data
    all_series = {}
    for qr in result.get("data", {}).get("result", []):
        for series in qr.get("series") or []:
            label = list(series.get("labels", {}).values())
            name = label[0] if label else "unknown"
            # Shorten Java class names: java.lang.NullPointerException → NullPointerException
            short = name.rsplit(".", 1)[-1] if "." in name else name
            times, values = [], []
            for val in series.get("values") or []:
                times.append(val["timestamp"])
                values.append(float(val.get("value", 0)))
            all_series[short] = (name, times, values)

    if not all_series:
        print("No error data found for the given filters.", file=sys.stderr)
        sys.exit(0)

    # Render chart
    output_path = _render_trend_chart(all_series, args.service or "", step, args.output)
    print(f"Chart saved: {output_path}")


def _render_trend_chart(all_series: dict, service: str, step: int,
                         output: str) -> str:
    """Render a trend chart PNG from time series data."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.ticker as ticker
    from datetime import datetime, timezone, timedelta

    # macOS Chinese font support
    from matplotlib import font_manager
    for fp in ["/System/Library/Fonts/PingFang.ttc",
               "/System/Library/Fonts/STHeiti Medium.ttc"]:
        try:
            font_manager.fontManager.addfont(fp)
            break
        except Exception:
            pass
    plt.rcParams["font.sans-serif"] = [
        "PingFang HK", "PingFang SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    CST = timezone(timedelta(hours=8))
    colors = ["#e74c3c", "#f39c12", "#3498db", "#2ecc71", "#9b59b6",
              "#1abc9c", "#e67e22", "#34495e", "#95a5a6", "#d35400"]

    # Sort series by total count descending
    sorted_names = sorted(all_series.keys(),
                          key=lambda k: sum(all_series[k][2]), reverse=True)

    # If top series is 10x+ bigger than #2, split into two subplots
    totals = [sum(all_series[n][2]) for n in sorted_names]
    split = len(sorted_names) > 1 and totals[0] > totals[1] * 8

    if split:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                                        gridspec_kw={"height_ratios": [2, 1]})
        axes_map = {sorted_names[0]: ax1}
        for n in sorted_names[1:]:
            axes_map[n] = ax2
    else:
        fig, ax = plt.subplots(1, 1, figsize=(14, 5))
        axes_map = {n: ax for n in sorted_names}

    step_label = (f"{step}s" if step < 60
                  else f"{step // 60}min" if step < 3600
                  else f"{step // 3600}h")
    title = f"{service + ' ' if service else ''}Error Trend (per {step_label})"
    fig.suptitle(title, fontsize=14, fontweight="bold")

    for idx, name in enumerate(sorted_names):
        _full, timestamps, values = all_series[name]
        color = colors[idx % len(colors)]
        ax_target = axes_map[name]
        dt_times = [datetime.fromtimestamp(t / 1000, tz=CST) for t in timestamps]

        ax_target.fill_between(dt_times, values, alpha=0.2, color=color)
        ax_target.plot(dt_times, values, "o-", color=color, linewidth=2,
                       markersize=5, label=name)
        # Data labels
        for t, v in zip(dt_times, values):
            ax_target.annotate(f"{int(v):,}", (t, v), textcoords="offset points",
                               xytext=(0, 8), ha="center", fontsize=7, color=color)

    used_axes = list(dict.fromkeys(axes_map.values()))
    for ax_item in used_axes:
        ax_item.legend(loc="upper right", fontsize=10)
        ax_item.grid(True, alpha=0.3)
        ax_item.set_ylabel("Count / bucket", fontsize=10)
        ax_item.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax_item.yaxis.set_major_formatter(
            ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
        ax_item.spines["top"].set_visible(False)
        ax_item.spines["right"].set_visible(False)
    used_axes[-1].set_xlabel("Time (CST)", fontsize=10)

    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output


def cmd_fields(client: OtelClient, args: argparse.Namespace) -> None:
    """List available log fields for building filter expressions."""
    result = client.get("/api/v1/logs/fields")
    print_json(result)


def cmd_error_summary(client: OtelClient, args: argparse.Namespace) -> None:
    """Error analysis — 3 modes in one command.

    --mode types    → exception type distribution (POST /api/v1/app/overview/logError)
    --mode timeline → error count over time       (POST /api/v1/app/logErrorCount)
    --mode list     → paginated exception list     (POST /api/v1/listErrors)
    """
    start_ns = parse_time_to_ns(args.start)
    end_ns = parse_time_to_ns(args.end)

    enforce_time_range(start_ns, end_ns, "aggregate", "error-summary")

    # Backend expects start/end as nanoseconds (parser.go: time.Unix(0, timeUnix)).
    start_s = str(start_ns)
    end_s = str(end_ns)

    if args.mode == "types":
        body = {
            "service": args.service or "",
            "start": start_s,
            "end": end_s,
            "ip": args.ip or "",
            "cluster": args.cluster or "",
        }
        result = client.post("/api/v1/app/overview/logError", body)

    elif args.mode == "timeline":
        body = {
            "service": args.service or "",
            "start": start_s,
            "end": end_s,
            "ip": args.ip or "",
            "cluster": args.cluster or "",
        }
        result = client.post("/api/v1/app/logErrorCount", body)

    elif args.mode == "list":
        body = {
            "start": start_s,
            "end": end_s,
            "limit": args.limit,
            "order": args.order,
            "orderParam": args.order_by,
        }
        if args.service:
            body["serviceName"] = args.service
        if args.exception_type:
            body["exceptionType"] = args.exception_type
        result = client.post("/api/v1/listErrors", body)

    else:
        print(f"ERROR: Unknown mode '{args.mode}'", file=sys.stderr)
        sys.exit(1)

    print_json(result)


# ---------------------------------------------------------------------------
# trace-logs — cross-service log pull for a single traceId
# ---------------------------------------------------------------------------

# Column index of the trace-spans API response (list-of-list events).
# See traces_client.cmd_trace_services for the full schema.
_TRACE_COL_TIME = 0
_TRACE_COL_SERVICE = 3

# Cap to protect the backend. If a trace spans more services than this,
# only the first N (by span count) are queried.
_TRACE_LOGS_MAX_SERVICES = 10


def _trace_services_and_window(client: OtelClient, trace_id: str) -> tuple[list[str], int, int]:
    """Call trace API and return (services, earliest_ns, latest_ns).

    Response shape: `[{columns: [...], events: [[row], ...]}, ...]`.
    Each row has columns defined in traces_client._TRACE_COL_*.
    """
    result = client.get(f"/api/v1/traces/{trace_id}", {})
    chunks = result if isinstance(result, list) else [result]

    svc_span_count: dict[str, int] = {}
    min_ts: int | None = None
    max_ts: int | None = None
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        events = chunk.get("events") or []
        for row in events:
            if not isinstance(row, list) or len(row) <= max(_TRACE_COL_TIME, _TRACE_COL_SERVICE):
                continue
            svc = row[_TRACE_COL_SERVICE] or "unknown"
            svc_span_count[svc] = svc_span_count.get(svc, 0) + 1
            # __time is ns per earlier probing of this endpoint
            ts = row[_TRACE_COL_TIME]
            try:
                ts = int(ts)
            except (TypeError, ValueError):
                continue
            min_ts = ts if min_ts is None else min(min_ts, ts)
            max_ts = ts if max_ts is None else max(max_ts, ts)

    if not svc_span_count:
        return [], 0, 0

    # Order services by span count desc, take top N.
    services = sorted(svc_span_count, key=lambda s: svc_span_count[s], reverse=True)
    if len(services) > _TRACE_LOGS_MAX_SERVICES:
        print(
            f"WARNING: [trace-logs] trace spans {len(services)} services; "
            f"limiting to top {_TRACE_LOGS_MAX_SERVICES} by span count.",
            file=sys.stderr,
        )
        services = services[:_TRACE_LOGS_MAX_SERVICES]

    return services, int(min_ts or 0), int(max_ts or 0)


def _fetch_service_logs(client: OtelClient, service: str, trace_id: str,
                         start_ms: int, end_ms: int, limit: int) -> list:
    """Pull logs for one (service, trace_id) via v3 query_range."""
    q = f"service.name={service} AND trace_id={trace_id}"
    filters = _parse_q_to_v3_filters(q)
    body = _build_v3_log_query(start_ms, end_ms, filters, limit, "asc")
    try:
        result = client.post("/api/v3/query_range", body)
    except Exception as exc:  # single-service failure must not kill the whole pull
        print(f"WARNING: [trace-logs] service={service} query failed: {exc}", file=sys.stderr)
        return []
    return _extract_v3_logs(result)


def cmd_trace_logs(client: OtelClient, args: argparse.Namespace) -> None:
    """Pull all logs for a traceId across every service it touched.

    Flow:
      1. GET /api/v1/traces/<tid>  → distinct ServiceName + min/max __time.
      2. Expand window by --padding minutes on each side.
      3. For every service, run v3 query_range with `service.name=X AND trace_id=Y`
         (parallel, max 5 workers).
      4. Merge, sort ascending by timestamp, output as JSON.
    """
    services, min_ns, max_ns = _trace_services_and_window(client, args.trace_id)
    if not services:
        print_json({"traceId": args.trace_id, "services": [], "results": [], "total": 0,
                     "note": "trace has no spans or was not found"})
        return

    padding_ns = max(0, args.padding) * 60 * 1_000_000_000
    start_ns = max(0, min_ns - padding_ns)
    end_ns = max_ns + padding_ns
    enforce_time_range(start_ns, end_ns, "search", "trace-logs")
    start_ms = start_ns // 1_000_000
    end_ms = end_ns // 1_000_000

    per_service_limit = validate_limit(args.limit, "search", "trace-logs")

    print(
        f"[trace-logs] trace={args.trace_id} services={services} "
        f"window={(end_ns - start_ns) / 1e9:.1f}s padding={args.padding}m",
        file=sys.stderr,
    )

    all_logs: list = []
    with ThreadPoolExecutor(max_workers=min(5, len(services))) as pool:
        futures = {
            pool.submit(_fetch_service_logs, client, svc, args.trace_id,
                        start_ms, end_ms, per_service_limit): svc
            for svc in services
        }
        for fut in as_completed(futures):
            svc = futures[fut]
            logs = fut.result()
            print(f"[trace-logs] service={svc} fetched={len(logs)}", file=sys.stderr)
            for log in logs:
                log["_service"] = svc  # tag for downstream grouping
            all_logs.extend(logs)

    all_logs.sort(key=lambda log: log.get("timestamp", ""))

    print_json({
        "traceId": args.trace_id,
        "services": services,
        "windowStartNs": start_ns,
        "windowEndNs": end_ns,
        "results": all_logs,
        "total": len(all_logs),
    })


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logs_client.py",
        description=(
            "otel-logs-query: search, analyze, and investigate logs.\n\n"
            "Time format:\n"
            '  "30m ago", "1h ago", "2d ago", "now"\n'
            '  "2026-04-14 22:00", "2026-04-14"\n'
            "  1700000000000000000 (raw nanoseconds)\n\n"
            "Auth env vars:\n"
            "  INTERNAL_TOKEN   token sent as Cas-User header\n"
            "  AUTH_STRICT       set to 'true' to fail if token is missing\n\n"
            "Environment:\n"
            "  PLATFORM_ENV     unset/'prod'/'production' → prod URL (default); 'test'/'dev'/'local'/'staging' → test URL"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # --- health ---
    sub.add_parser("health", help="Check service connectivity")

    # --- list-apps ---
    p = sub.add_parser("list-apps", help="List registered applications")
    p.add_argument("--owner", help="Filter by owner (fuzzy match)")
    p.add_argument("--name", help="Filter by service name (fuzzy match)")
    p.add_argument("--tenant", help="Filter by tenant (fuzzy match)")
    p.add_argument("--language", help="Filter by language (java/python/go/...)")
    p.add_argument("--start", help="Start time (default: 15m ago)")
    p.add_argument("--end", help="End time (default: now)")
    p.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    p.add_argument("--page-size", type=int, default=50, help="Page size (default: 50)")
    p.add_argument("--json", action="store_true", help="Output raw JSON")

    # --- search-logs ---
    p = sub.add_parser("search-logs", help="Search logs with filters")
    _add_time_args(p)
    p.add_argument("--q", help="Filter expression (e.g. 'severity_text=ERROR')")
    p.add_argument("--limit", type=int, default=100, help="Max results (default: 100, max: 1000)")
    p.add_argument("--order", default="desc", choices=["asc", "desc"])
    p.add_argument("--exhaust", action="store_true",
                   help="Paginate until all logs are fetched (max 20 pages). Use for traceId diagnosis.")

    # --- aggregate ---
    p = sub.add_parser("aggregate", help="Aggregate logs by field (group by + count)")
    _add_time_args(p)
    p.add_argument("--group-by", required=True,
                   help="Field to group by (e.g. exception.type, service.name, severity_text)")
    p.add_argument("--function", default="count",
                   choices=["count", "count_distinct", "sum", "avg", "min", "max",
                            "p50", "p90", "p95", "p99"],
                   help="Aggregation function (default: count)")
    p.add_argument("--q", help="Filter expression")
    p.add_argument("--limit", type=int, default=20, help="Max groups to return (default: 20)")
    p.add_argument("--order", default="desc", choices=["asc", "desc"])

    # --- trend ---
    p = sub.add_parser("trend", help="Error trend chart (PNG output)")
    _add_time_args(p)
    p.add_argument("--service", help="Service name (used in chart title and filter)")
    p.add_argument("--group-by", default="exception.type",
                   help="Field to group by (default: exception.type)")
    p.add_argument("--q", help="Additional filter expression")
    p.add_argument("--output", default="/tmp/error-trend.png",
                   help="Output PNG path (default: /tmp/error-trend.png)")

    # --- trace-logs ---
    p = sub.add_parser("trace-logs",
                        help="Pull full logs for a traceId across all services it touched")
    p.add_argument("--trace-id", required=True, help="32-hex trace id")
    p.add_argument("--padding", type=int, default=30,
                   help="Minutes to extend the trace time window on each side (default: 30)")
    p.add_argument("--limit", type=int, default=500,
                   help="Per-service max logs (default: 500, max: 1000)")

    # --- fields ---
    sub.add_parser("fields", help="List available log fields")

    # --- error-summary ---
    p = sub.add_parser("error-summary", help="Error analysis (types / timeline / list)")
    _add_time_args(p)
    p.add_argument(
        "--mode", required=True,
        choices=["types", "timeline", "list"],
        help="types: exception distribution | timeline: error trend | list: error details",
    )
    p.add_argument("--service", help="Application/service name")
    p.add_argument("--ip", help="Filter by instance IP")
    p.add_argument("--cluster", help="Filter by cluster name")
    # list-mode specific
    p.add_argument("--limit", type=int, default=10, help="Max results for list mode (default: 10)")
    p.add_argument("--order", default="descending", choices=["ascending", "descending"])
    p.add_argument("--order-by", default="lastSeen",
                   choices=["exceptionType", "exceptionCount", "firstSeen", "lastSeen", "serviceName"])
    p.add_argument("--exception-type", help="Filter by exception type (list mode)")

    return parser


def _add_time_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--start", required=True,
        help='Start time: "30m ago", "1h ago", "2026-04-14 22:00", or raw nanoseconds',
    )
    p.add_argument(
        "--end", required=True,
        help='End time: "now", "2026-04-14 23:00", or raw nanoseconds',
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMAND_MAP = {
    "health": cmd_health,
    "list-apps": cmd_list_apps,
    "search-logs": cmd_search_logs,
    "aggregate": cmd_aggregate,
    "trend": cmd_trend,
    "fields": cmd_fields,
    "error-summary": cmd_error_summary,
    "trace-logs": cmd_trace_logs,
}

if __name__ == "__main__":
    parser = make_parser()
    args = parser.parse_args()

    token = resolve_token()
    base_url = resolve_base_url()
    client = OtelClient(base_url, token)

    handler = COMMAND_MAP[args.command]
    handler(client, args)