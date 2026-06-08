#!/usr/bin/env python3
"""
otel-traces-query client — trace lookup, error analysis, and v1 app metric queries.

All commands except `get-trace` / `trace-services` / `list-errors` / `count-errors`
hit the **v1 app endpoints** that the frontend actually uses. These endpoints
internally select the correct sharded ClickHouse table by hashing
serviceName (signoz_index_v2 → 16 shards prod / dubbo_metric → 24 / http_metric → 6 / db_metric → 6),
which is why they return data in production while the v3 query_range path
(which targets the empty unsharded "umbrella" table) does not.

Commands (grouped):
  health                   Connectivity check (calls /api/v1/services/list)
  list-apps                List registered services
  get-trace                Get full trace by traceId
  trace-services           Extract unique services involved in a trace
  list-errors              List exception groups
  count-errors             Count total errors

  overview                 App overview (qps / rt / error rate)
  overview-log-error       Log error type breakdown
  overview-trace-error     Trace error type breakdown
  log-error-count          Total log error count
  trace-error-count        Total trace error count

  http-{request,duration,error,paths,status,status-top,
        error-path,error-trace,trace,remote-ip,link-host}
  dubbo-{request,duration,error,interfaces,error-interfaces,error-trace,
         trace,remote-ip,downstream,downstream-interfaces,downstream-methods,
         upstream,upstream-interfaces,upstream-methods}
  db-{request,duration,error,mappers,tables,methods,
      error-mapper,error-trace,trace,link-rds}

  long-type / dubbo-long-type
  long-request / long-op / long-trace / long-ip-distribution
  long-sql-request / long-sql-table / long-sql-trace

Env:    PLATFORM_ENV unset/"prod"/"production" -> prod URL (default).
        PLATFORM_ENV=test|dev|local|staging -> test URL.
        INTERNAL_TOKEN sent as Cas-User header.
Time:   --start/--end accept "30m ago", "1h ago", "now", "2026-04-14 22:00", or raw ns.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Callable

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
)


# ---------------------------------------------------------------------------
# Body builders
# ---------------------------------------------------------------------------

# Flag-name → JSON body field mapping for GetInfosParams (v1 app endpoints).
# Frontend always sends string values; we keep parity.
_INFO_FIELDS = {
    "service":             "service",
    "ip":                  "ip",
    "path":                "path",
    "http_code":           "httpCode",
    "downstream_service":  "downstreamService",
    "upstream_service":    "upstreamService",
    "rpc_service":         "rpcService",
    "rpc_method":          "rpcMethod",
    "call_type":           "callType",
    "mapper":              "mapper",
    "table":               "table",
    "method":              "method",
    "cluster":             "cluster",
}

# GetProblemInfosParams (problem/long* endpoints)
_PROBLEM_FIELDS = {
    "service":   "service",
    "long_type": "longType",
    "op_name":   "opName",
    "table":     "table",
    "ip":        "ip",
    "cluster":   "cluster",
}


def _build_app_body(args: argparse.Namespace, field_map: dict[str, str]) -> dict:
    """Build a JSON body for v1 app endpoints from argparse Namespace."""
    start_ns = parse_time_to_ns(args.start)
    end_ns = parse_time_to_ns(args.end)
    body: dict = {"start": str(start_ns), "end": str(end_ns)}
    for attr, json_key in field_map.items():
        val = getattr(args, attr, None)
        if val is None or val == "":
            continue
        body[json_key] = val
    # is_today is a bool — only include if explicitly set
    if hasattr(args, "is_today") and args.is_today:
        body["isToday"] = True
    return body


# ---------------------------------------------------------------------------
# Generic command runners
# ---------------------------------------------------------------------------

def _run_app_info(client: OtelClient, args: argparse.Namespace, path: str) -> None:
    """Generic runner for v1 app endpoints with GetInfosParams body."""
    enforce_time_range(
        parse_time_to_ns(args.start),
        parse_time_to_ns(args.end),
        "search", path.rsplit("/", 1)[-1],
    )
    body = _build_app_body(args, _INFO_FIELDS)
    print_json(client.post(path, body))


def _run_app_problem(client: OtelClient, args: argparse.Namespace, path: str) -> None:
    """Generic runner for v1 problem/* endpoints with GetProblemInfosParams body."""
    enforce_time_range(
        parse_time_to_ns(args.start),
        parse_time_to_ns(args.end),
        "search", path.rsplit("/", 1)[-1],
    )
    body = _build_app_body(args, _PROBLEM_FIELDS)
    print_json(client.post(path, body))


# ---------------------------------------------------------------------------
# Standalone commands (non-app)
# ---------------------------------------------------------------------------

def cmd_health(client: OtelClient, args: argparse.Namespace) -> None:
    """Check connectivity by calling /api/v1/services/list (cheap, schema-free)."""
    result = client.get("/api/v1/services/list", {})
    count = 0
    if isinstance(result, dict):
        count = len(result.get("services") or result.get("data") or [])
    elif isinstance(result, list):
        count = len(result)
    print(f"[OK] {client.base_url} reachable. services listed: {count}")


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


def cmd_get_trace(client: OtelClient, args: argparse.Namespace) -> None:
    """Get full trace by traceId."""
    params = {
        "spanId": args.span_id,
        "levelUp": args.level_up,
        "levelDown": args.level_down,
    }
    print_json(client.get(f"/api/v1/traces/{args.trace_id}", params))


def cmd_trace_services(client: OtelClient, args: argparse.Namespace) -> None:
    """Extract unique services involved in a trace.

    Output: {traceId, totalSpans, rootService, rootOperation, services:[...]}
    """
    result = client.get(f"/api/v1/traces/{args.trace_id}", {})
    events: list = []
    if isinstance(result, list):
        for chunk in result:
            if isinstance(chunk, dict):
                events.extend(chunk.get("events") or [])
    elif isinstance(result, dict):
        events = result.get("events") or []
    if not events:
        print_json({"traceId": args.trace_id, "totalSpans": 0, "services": []})
        return

    svc_map: dict = {}
    root_candidates: list = []
    for row in events:
        if not isinstance(row, list) or len(row) < 12:
            continue
        svc = row[3] or "unknown"
        name = row[4] if len(row) > 4 else ""
        references = row[9] if len(row) > 9 else None
        has_error = bool(row[11]) if len(row) > 11 else False

        info = svc_map.setdefault(svc, {
            "name": svc, "spanCount": 0, "errorSpanCount": 0,
            "entrySpanName": "", "operations": set(),
        })
        info["spanCount"] += 1
        if has_error:
            info["errorSpanCount"] += 1
        if name:
            info["operations"].add(name)
        if not references or references in ("[]", "", None):
            root_candidates.append((svc, name))
            if not info["entrySpanName"]:
                info["entrySpanName"] = name

    services = []
    for svc, info in svc_map.items():
        ops = sorted(info.pop("operations"))
        info["topOperations"] = ops[:5]
        info["hasError"] = info["errorSpanCount"] > 0
        services.append(info)
    services.sort(key=lambda s: -s["spanCount"])

    print_json({
        "traceId": args.trace_id,
        "totalSpans": len(events),
        "rootService": root_candidates[0][0] if root_candidates else None,
        "rootOperation": root_candidates[0][1] if root_candidates else None,
        "services": services,
    })


def cmd_list_errors(client: OtelClient, args: argparse.Namespace) -> None:
    """List exception/error groups via v1 API."""
    start_ns = parse_time_to_ns(args.start)
    end_ns = parse_time_to_ns(args.end)
    enforce_time_range(start_ns, end_ns, "aggregate", "list-errors")
    body = {
        "start": str(start_ns),
        "end": str(end_ns),
        "limit": args.limit,
        "order": args.order,
        "orderParam": args.order_by,
    }
    if args.service:
        body["serviceName"] = args.service
    print_json(client.post("/api/v1/listErrors", body))


def cmd_count_errors(client: OtelClient, args: argparse.Namespace) -> None:
    """Count total errors in a time range."""
    start_ns = parse_time_to_ns(args.start)
    end_ns = parse_time_to_ns(args.end)
    enforce_time_range(start_ns, end_ns, "aggregate", "count-errors")
    body = {"start": str(start_ns), "end": str(end_ns)}
    if args.service:
        body["serviceName"] = args.service
    print_json(client.post("/api/v1/countErrors", body))


# ---------------------------------------------------------------------------
# v1 app endpoint command map
# ---------------------------------------------------------------------------
#
# Each entry: cli_name -> (path, runner). Runner is _run_app_info or
# _run_app_problem depending on body schema.

_APP_ENDPOINTS: dict[str, tuple[str, Callable]] = {
    # overview
    "overview":            ("/api/v1/app/overview",                  _run_app_info),
    "overview-log-error":  ("/api/v1/app/overview/logError",         _run_app_info),
    "overview-trace-error":("/api/v1/app/overview/traceError",       _run_app_info),
    "log-error-count":     ("/api/v1/app/logErrorCount",             _run_app_info),
    # NOTE: handler registers double slash; preserve it.
    "trace-error-count":   ("/api/v1/app//traceErrorCount",          _run_app_info),

    # http
    "http-request":        ("/api/v1/app/http/request",              _run_app_info),
    "http-duration":       ("/api/v1/app/http/duration",             _run_app_info),
    "http-error":          ("/api/v1/app/http/error",                _run_app_info),
    "http-paths":          ("/api/v1/app/http/paths",                _run_app_info),
    "http-status":         ("/api/v1/app/http/status",               _run_app_info),
    "http-status-top":     ("/api/v1/app/http/statusTop",            _run_app_info),
    "http-error-path":     ("/api/v1/app/http/error/path",           _run_app_info),
    "http-error-trace":    ("/api/v1/app/http/error/trace",          _run_app_info),
    "http-trace":          ("/api/v1/app/http/trace",                _run_app_info),
    "http-remote-ip":      ("/api/v1/app/http/remoteIp",             _run_app_info),
    "http-link-host":      ("/api/v1/app/http/linkHost",             _run_app_info),

    # dubbo
    "dubbo-request":             ("/api/v1/app/dubbo/request",              _run_app_info),
    "dubbo-duration":            ("/api/v1/app/dubbo/duration",             _run_app_info),
    "dubbo-error":               ("/api/v1/app/dubbo/error",                _run_app_info),
    "dubbo-interfaces":          ("/api/v1/app/dubbo/interfaces",           _run_app_info),
    "dubbo-error-interfaces":    ("/api/v1/app/dubbo/error/interfaces",     _run_app_info),
    "dubbo-error-trace":         ("/api/v1/app/dubbo/error/trace",          _run_app_info),
    "dubbo-trace":               ("/api/v1/app/dubbo/trace",                _run_app_info),
    "dubbo-remote-ip":           ("/api/v1/app/dubbo/remoteIp",             _run_app_info),
    "dubbo-downstream":          ("/api/v1/app/dubbo/downstream",           _run_app_info),
    "dubbo-downstream-interfaces":("/api/v1/app/dubbo/downstream/interfaces",_run_app_info),
    "dubbo-downstream-methods":  ("/api/v1/app/dubbo/downstream/methods",   _run_app_info),
    "dubbo-upstream":            ("/api/v1/app/dubbo/upstream",             _run_app_info),
    "dubbo-upstream-interfaces": ("/api/v1/app/dubbo/upstream/interfaces",  _run_app_info),
    "dubbo-upstream-methods":    ("/api/v1/app/dubbo/upstream/methods",     _run_app_info),

    # db
    "db-request":         ("/api/v1/app/db/request",        _run_app_info),
    "db-duration":        ("/api/v1/app/db/duration",       _run_app_info),
    "db-error":           ("/api/v1/app/db/error",          _run_app_info),
    "db-mappers":         ("/api/v1/app/db/mappers",        _run_app_info),
    "db-tables":          ("/api/v1/app/db/tables",         _run_app_info),
    "db-methods":         ("/api/v1/app/db/methods",        _run_app_info),
    "db-error-mapper":    ("/api/v1/app/db/error/mapper",   _run_app_info),
    "db-error-trace":     ("/api/v1/app/db/error/trace",    _run_app_info),
    "db-trace":           ("/api/v1/app/db/trace",          _run_app_info),
    "db-link-rds":        ("/api/v1/app/db/linkRds",        _run_app_info),

    # problem (long-tail / slow request)  — uses GetProblemInfosParams
    "long-type":            ("/api/v1/app/problem/longType",            _run_app_problem),
    "dubbo-long-type":      ("/api/v1/app/problem/dubbo/longType",      _run_app_problem),
    "long-request":         ("/api/v1/app/problem/longRequest",         _run_app_problem),
    "long-op":              ("/api/v1/app/problem/longOp",              _run_app_problem),
    "long-trace":           ("/api/v1/app/problem/longTrace",           _run_app_problem),
    "long-ip-distribution": ("/api/v1/app/problem/longIpDistribution",  _run_app_problem),

    # longSql (uses GetInfosParams, not problem)
    "long-sql-request": ("/api/v1/app/longSql/request", _run_app_info),
    "long-sql-table":   ("/api/v1/app/longSql/table",   _run_app_info),
    "long-sql-trace":   ("/api/v1/app/longSql/trace",   _run_app_info),
}


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _add_time_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--start", required=True,
                   help='Start time ("30m ago", "1h ago", "now", "2026-04-14 22:00", or raw ns)')
    p.add_argument("--end", required=True,
                   help='End time ("now", "2026-04-14 23:00", or raw ns)')


def _add_info_args(p: argparse.ArgumentParser) -> None:
    """Common flags for v1 app endpoints (GetInfosParams)."""
    _add_time_args(p)
    p.add_argument("--service", required=True,
                   help="Service name (REQUIRED — drives sharded-table hash)")
    p.add_argument("--cluster", help="Cluster filter (e.g. prod-edas-k8s-dt)")
    p.add_argument("--ip", help="Pod / instance IP filter")
    # http-only
    p.add_argument("--path", help="HTTP path filter (http-* commands)")
    p.add_argument("--http-code", help="HTTP status code filter")
    # dubbo-only
    p.add_argument("--rpc-service", help="Dubbo interface/service")
    p.add_argument("--rpc-method", help="Dubbo method")
    p.add_argument("--call-type", choices=["provider", "consumer"],
                   help="Dubbo call type (provider/consumer)")
    p.add_argument("--downstream-service", help="Downstream service filter (dubbo)")
    p.add_argument("--upstream-service", help="Upstream service filter (dubbo)")
    # db-only
    p.add_argument("--mapper", help="MyBatis mapper class (db-* commands)")
    p.add_argument("--table", help="DB table name")
    p.add_argument("--method", help="Mapper method name")


def _add_problem_args(p: argparse.ArgumentParser) -> None:
    """Common flags for problem/* endpoints (GetProblemInfosParams)."""
    _add_time_args(p)
    p.add_argument("--service", required=True, help="Service name (REQUIRED)")
    p.add_argument("--cluster", help="Cluster filter")
    p.add_argument("--ip", help="Pod / instance IP filter")
    p.add_argument("--long-type", help="Long-tail bucket (e.g. http/dubbo/db)")
    p.add_argument("--op-name", help="Operation/interface name")
    p.add_argument("--table", help="DB table (for SQL long-tail)")
    p.add_argument("--is-today", action="store_true",
                   help="Restrict to today's data only")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="traces_client.py",
        description=(
            "otel-traces-query client (frontend-aligned v1 app endpoints).\n\n"
            "Env vars:\n"
            "  PLATFORM_ENV      unset/'prod'/'production' -> production URL (default); 'test'/'dev'/'local'/'staging' -> test URL\n"
            "  INTERNAL_TOKEN    token sent as Cas-User header (optional)\n\n"
            "Time format: '30m ago', '1h ago', '2d ago', 'now', '2026-04-14 22:00', or raw nanoseconds."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # --- standalone ----------------------------------------------------------
    sub.add_parser("health", help="Check service connectivity")

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

    p = sub.add_parser("get-trace", help="Get full trace by traceId")
    p.add_argument("--trace-id", required=True, help="Trace ID to look up")
    p.add_argument("--span-id", help="Focus on specific span")
    p.add_argument("--level-up", type=int, help="Parent levels to include")
    p.add_argument("--level-down", type=int, help="Child levels to include")

    p = sub.add_parser("trace-services",
                       help="List unique services in a trace (for cross-service diagnosis)")
    p.add_argument("--trace-id", required=True, help="Trace ID to inspect")

    p = sub.add_parser("list-errors", help="List exception/error groups (v1 API)")
    _add_time_args(p)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--order", default="descending", choices=["ascending", "descending"])
    p.add_argument("--order-by", default="lastSeen",
                   choices=["exceptionType", "exceptionCount", "firstSeen", "lastSeen", "serviceName"])
    p.add_argument("--service", help="Filter by service name")

    p = sub.add_parser("count-errors", help="Count total errors (v1 API)")
    _add_time_args(p)
    p.add_argument("--service", help="Filter by service name")

    # --- v1 app endpoints ----------------------------------------------------
    for cli_name, (_path, runner) in _APP_ENDPOINTS.items():
        helptext = f"POST {_path}"
        p = sub.add_parser(cli_name, help=helptext)
        if runner is _run_app_problem:
            _add_problem_args(p)
        else:
            _add_info_args(p)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_STANDALONE_HANDLERS: dict[str, Callable] = {
    "health":         cmd_health,
    "list-apps":      cmd_list_apps,
    "get-trace":      cmd_get_trace,
    "trace-services": cmd_trace_services,
    "list-errors":    cmd_list_errors,
    "count-errors":   cmd_count_errors,
}


if __name__ == "__main__":
    parser = make_parser()
    args = parser.parse_args()

    token = resolve_token()
    base_url = resolve_base_url()
    client = OtelClient(base_url, token)

    if args.command in _STANDALONE_HANDLERS:
        _STANDALONE_HANDLERS[args.command](client, args)
    elif args.command in _APP_ENDPOINTS:
        path, runner = _APP_ENDPOINTS[args.command]
        runner(client, args, path)
    else:
        parser.error(f"Unknown command: {args.command}")