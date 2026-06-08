#!/usr/bin/env python3
"""Reusable Bigeyes Admin API client.

Auth header rule:
- Use Cas-User header only from INTERNAL_TOKEN env var.
- If INTERNAL_TOKEN is missing/empty/blank, exit and do not send requests.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from urllib import error, parse, request
from urllib.request import Request


ENV_URL_MAP = {
    "local": "http://localhost:8080",
    "prod": "http://prod-bigeyes-admin.soulapp-inc.cn",
    "production": "http://prod-bigeyes-admin.soulapp-inc.cn",
}
DEFAULT_URL = "http://prod-bigeyes-admin.soulapp-inc.cn"


def select_base_url() -> str:
    env = (os.getenv("PLATFORM_ENV") or "").strip().lower()
    return ENV_URL_MAP.get(env, DEFAULT_URL)


def get_internal_token() -> str:
    token = os.getenv("INTERNAL_TOKEN")
    if token is None or not token.strip():
        raise SystemExit(
            "INTERNAL_TOKEN is required. Set a non-empty value before running this command; "
            "no request will be sent when invalid."
        )
    return token.strip()


def summarize_body(raw: bytes, max_len: int = 1200) -> str:
    if not raw:
        return ""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + " ...[truncated]"


def fetch_json(
    method: str,
    path: str,
    token: str,
    query: dict | None = None,
    payload: dict | None = None,
    timeout: int = 15,
) -> tuple[int, str, str]:
    """Execute HTTP request and return (status, url, raw_text).

    Raises HTTPError on non-2xx; callers can catch.
    """
    base_url = select_base_url()
    if not path.startswith("/"):
        path = "/" + path
    url = f"{base_url.rstrip('/')}{path}"

    if query:
        encoded = parse.urlencode(query, doseq=True)
        url = f"{url}?{encoded}" if encoded else url

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("Cas-User", token)
    req.add_header("User-Agent", "bigeyes-admin-api-client/1.0")
    if payload is not None:
        req.add_header("Content-Type", "application/json")

    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        status = response.getcode()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        return status, url, text


def request_json(
    method: str,
    path: str,
    token: str,
    query: dict | None = None,
    payload: dict | None = None,
    timeout: int = 15,
    raw: bool = False,
) -> int:
    base_url = select_base_url()
    if not path.startswith("/"):
        path = "/" + path
    url = f"{base_url.rstrip('/')}{path}"

    if query:
        encoded = parse.urlencode(query, doseq=True)
        url = f"{url}?{encoded}" if encoded else url

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("Cas-User", token)
    req.add_header("User-Agent", "bigeyes-admin-api-client/1.0")
    if payload is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw_bytes = response.read()
            status = response.getcode()
            if raw:
                try:
                    text = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw_bytes.decode("utf-8", errors="replace")
                print(text)
                return 0
            body = summarize_body(raw_bytes)
            print(
                json.dumps(
                    {"ok": True, "status": status, "url": url, "body": body},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
    except error.HTTPError as exc:
        err_raw = exc.read()
        if raw:
            try:
                text = err_raw.decode("utf-8")
            except UnicodeDecodeError:
                text = err_raw.decode("utf-8", errors="replace")
            print(text)
            return 1
        err_body = summarize_body(err_raw)
        print(
            json.dumps(
                {
                    "ok": False,
                    "http_status": exc.code,
                    "url": url,
                    "body": err_body,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "url": url,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def do_health(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", "/health_check", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_user_current(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", "/api/user/current", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_user_departments(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", "/api/user/departments", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_events(args: argparse.Namespace, token: str) -> int:
    query: dict = {"pageNum": args.pageNum, "pageSize": args.pageSize}
    for key in ("receiver", "source", "statuses", "levels", "keyword", "department"):
        val = getattr(args, key, None)
        if val:
            query[key] = val
    return request_json("GET", "/api/alarm/events", token, query=query, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_dept_stats(args: argparse.Namespace, token: str) -> int:
    """One-shot department aggregate: auto-paginate /api/alarm/events and summarize."""
    statuses = [s.strip() for s in (args.statuses or "firing,acked").split(",") if s.strip()]
    top_n = max(1, args.top)
    page_size = max(1, min(args.pageSize, 100))

    all_events: list[dict] = []
    total = None
    page_num = 1
    max_pages = max(1, args.max_pages)

    while page_num <= max_pages:
        query = {
            "pageNum": page_num,
            "pageSize": page_size,
            "department": args.department,
            "statuses": statuses,
        }
        try:
            status, url, text = fetch_json(
                "GET", "/api/alarm/events", token, query=query, timeout=args.timeout
            )
        except error.HTTPError as exc:
            print(json.dumps({"ok": False, "http_status": exc.code, "page": page_num}, ensure_ascii=False))
            return 1
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc), "page": page_num}, ensure_ascii=False))
            return 1

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            print(json.dumps({"ok": False, "error": f"json parse: {exc}", "page": page_num}, ensure_ascii=False))
            return 1

        data = payload.get("data") or {}
        page_total = data.get("total")
        if page_total is not None:
            total = page_total
        items = data.get("list") or data.get("records") or []
        if not items:
            break
        all_events.extend(items)
        if total is not None and len(all_events) >= total:
            break
        page_num += 1

    def top_counter(values) -> list[dict]:
        c = Counter(v for v in values if v)
        return [{"key": k, "count": v} for k, v in c.most_common(top_n)]

    summary = {
        "ok": True,
        "department": args.department,
        "statuses": statuses,
        "total_reported": total,
        "collected": len(all_events),
        "by_status": top_counter(e.get("status") for e in all_events),
        "by_level": top_counter(e.get("level") for e in all_events),
        "by_source": top_counter(e.get("source") for e in all_events),
        "by_receiver": top_counter(e.get("receiver") for e in all_events),
        "by_ruleName": top_counter(e.get("ruleName") for e in all_events),
        "by_resourceName": top_counter(e.get("resourceName") for e in all_events),
        "by_alarmType": top_counter(e.get("alarmType") for e in all_events),
        "top_alertCount": sorted(
            (
                {
                    "id": e.get("id"),
                    "ruleName": e.get("ruleName"),
                    "resourceName": e.get("resourceName"),
                    "alertCount": e.get("alertCount") or 0,
                    "level": e.get("level"),
                    "status": e.get("status"),
                }
                for e in all_events
            ),
            key=lambda x: x["alertCount"],
            reverse=True,
        )[:top_n],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _fetch_resource_category_map(token: str, query: dict, timeout: int) -> dict[str, str]:
    """Call /api/alarm/events/stats/category and build a {resourceName: category} lookup.

    The backend groups events by category server-side (Application / GroupEcs / Rds / Redis ...).
    We reuse that mapping to avoid heuristic drift when filtering events client-side.
    Returns {} on any failure — callers should treat missing keys as 'unknown category'.
    """
    try:
        _status, _url, text = fetch_json(
            "GET", "/api/alarm/events/stats/category", token, query=query or None, timeout=timeout
        )
    except Exception:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    data = payload.get("data") or {}
    by_rc = data.get("byResourceCategory") or {}
    mapping: dict[str, str] = {}
    for category, rows in by_rc.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            name = row.get("resourceName")
            if name and name not in mapping:
                mapping[name] = category
    return mapping


def do_alarm_user_stats(args: argparse.Namespace, token: str) -> int:
    """One-shot receiver aggregate: auto-paginate /api/alarm/events by --receiver and summarize."""
    statuses = [s.strip() for s in (args.statuses or "firing,acked").split(",") if s.strip()]
    categories_filter: set[str] | None = None
    if args.category:
        categories_filter = {c.strip() for c in args.category.split(",") if c.strip()}
    top_n = max(1, args.top)
    page_size = max(1, min(args.pageSize, 100))

    resource_category: dict[str, str] = {}
    if categories_filter is not None:
        resource_category = _fetch_resource_category_map(
            token, {"receiver": args.receiver}, timeout=args.timeout
        )

    def event_category(event: dict) -> str | None:
        name = event.get("resourceName")
        if name and name in resource_category:
            return resource_category[name]
        return None

    all_events: list[dict] = []
    total = None
    page_num = 1
    max_pages = max(1, args.max_pages)

    while page_num <= max_pages:
        query = {
            "pageNum": page_num,
            "pageSize": page_size,
            "receiver": args.receiver,
            "statuses": statuses,
        }
        try:
            _status, _url, text = fetch_json(
                "GET", "/api/alarm/events", token, query=query, timeout=args.timeout
            )
        except error.HTTPError as exc:
            print(json.dumps({"ok": False, "http_status": exc.code, "page": page_num}, ensure_ascii=False))
            return 1
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc), "page": page_num}, ensure_ascii=False))
            return 1

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            print(json.dumps({"ok": False, "error": f"json parse: {exc}", "page": page_num}, ensure_ascii=False))
            return 1

        data = payload.get("data") or {}
        page_total = data.get("total")
        if page_total is not None:
            total = page_total
        items = data.get("list") or data.get("records") or []
        if not items:
            break
        all_events.extend(items)
        if total is not None and len(all_events) >= total:
            break
        page_num += 1

    raw_collected = len(all_events)
    if categories_filter is not None:
        all_events = [e for e in all_events if event_category(e) in categories_filter]

    def top_counter(values) -> list[dict]:
        c = Counter(v for v in values if v)
        return [{"key": k, "count": v} for k, v in c.most_common(top_n)]

    summary = {
        "ok": True,
        "receiver": args.receiver,
        "statuses": statuses,
        "category_filter": sorted(categories_filter) if categories_filter else None,
        "total_reported": total,
        "collected_raw": raw_collected,
        "collected_after_filter": len(all_events),
        "by_status": top_counter(e.get("status") for e in all_events),
        "by_level": top_counter(e.get("level") for e in all_events),
        "by_source": top_counter(e.get("source") for e in all_events),
        "by_category": top_counter(event_category(e) for e in all_events) if resource_category else [],
        "by_ruleName": top_counter(e.get("ruleName") for e in all_events),
        "by_resourceName": top_counter(e.get("resourceName") for e in all_events),
        "by_alarmType": top_counter(e.get("alarmType") for e in all_events),
        "top_alertCount": sorted(
            (
                {
                    "id": e.get("id"),
                    "ruleName": e.get("ruleName"),
                    "resourceName": e.get("resourceName"),
                    "category": event_category(e) if resource_category else None,
                    "alertCount": e.get("alertCount") or 0,
                    "level": e.get("level"),
                    "status": e.get("status"),
                }
                for e in all_events
            ),
            key=lambda x: x["alertCount"],
            reverse=True,
        )[:top_n],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def do_alarm_event_detail(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", f"/api/alarm/events/{args.id}", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_event_logs(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", f"/api/alarm/events/{args.id}/logs", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_event_notify_records(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", f"/api/alarm/events/{args.id}/notify-records", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_event_escalation(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", f"/api/alarm/events/{args.id}/escalation", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_event_ack(args: argparse.Namespace, token: str) -> int:
    return request_json("POST", f"/api/alarm/events/{args.id}/ack", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_event_resolve(args: argparse.Namespace, token: str) -> int:
    return request_json("POST", f"/api/alarm/events/{args.id}/resolve", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_event_batch_ack(args: argparse.Namespace, token: str) -> int:
    ids = [int(x.strip()) for x in args.ids.split(",")]
    return request_json("POST", "/api/alarm/events/batch-ack", token, payload=ids, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_event_batch_resolve(args: argparse.Namespace, token: str) -> int:
    ids = [int(x.strip()) for x in args.ids.split(",")]
    return request_json("POST", "/api/alarm/events/batch-resolve", token, payload=ids, timeout=args.timeout, raw=getattr(args, "raw", False))


STATS_FILTER_KEYS = ("department", "receiver", "source", "startTime", "endTime")


def do_alarm_stats_summary(args: argparse.Namespace, token: str) -> int:
    query: dict = {}
    for key in STATS_FILTER_KEYS:
        val = getattr(args, key, None)
        if val:
            query[key] = val
    return request_json("GET", "/api/alarm/events/stats/summary", token, query=query or None, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_stats_trend(args: argparse.Namespace, token: str) -> int:
    query: dict = {}
    for key in STATS_FILTER_KEYS:
        val = getattr(args, key, None)
        if val:
            query[key] = val
    return request_json("GET", "/api/alarm/events/stats/trend", token, query=query or None, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_stats_category(args: argparse.Namespace, token: str) -> int:
    query: dict = {}
    for key in STATS_FILTER_KEYS:
        val = getattr(args, key, None)
        if val:
            query[key] = val

    only_raw = getattr(args, "only_category", None)
    wanted: set[str] | None = None
    if only_raw:
        wanted = {c.strip() for c in only_raw.split(",") if c.strip()}

    if not wanted:
        return request_json(
            "GET",
            "/api/alarm/events/stats/category",
            token,
            query=query or None,
            timeout=args.timeout,
            raw=getattr(args, "raw", False),
        )

    try:
        _status, url, text = fetch_json(
            "GET",
            "/api/alarm/events/stats/category",
            token,
            query=query or None,
            timeout=args.timeout,
        )
    except error.HTTPError as exc:
        err_body = summarize_body(exc.read())
        print(json.dumps({"ok": False, "http_status": exc.code, "body": err_body}, ensure_ascii=False, indent=2))
        return 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"json parse: {exc}", "url": url}, ensure_ascii=False, indent=2))
        return 1

    data = payload.get("data") or {}
    by_rc = data.get("byResourceCategory") or {}
    data["byResourceCategory"] = {k: v for k, v in by_rc.items() if k in wanted}
    data["_onlyCategory"] = sorted(wanted)
    payload["data"] = data
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def do_alarm_stats_response(args: argparse.Namespace, token: str) -> int:
    query: dict = {}
    for key in STATS_FILTER_KEYS:
        val = getattr(args, key, None)
        if val:
            query[key] = val
    return request_json("GET", "/api/alarm/events/stats/response", token, query=query or None, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_stats_active(args: argparse.Namespace, token: str) -> int:
    query: dict = {}
    for key in ("department", "receiver", "source"):
        val = getattr(args, key, None)
        if val:
            query[key] = val
    return request_json("GET", "/api/alarm/events/stats/active", token, query=query or None, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_rules(args: argparse.Namespace, token: str) -> int:
    query: dict = {"pageNum": args.pageNum, "pageSize": args.pageSize}
    for key in ("source", "category", "resource", "keyword", "receiver", "department"):
        val = getattr(args, key, None)
        if val:
            query[key] = val
    return request_json("GET", "/api/alarm/rules", token, query=query, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_rule_detail(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", f"/api/alarm/rules/{args.id}", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_rules_stats_source(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", "/api/alarm/rules/stats/source", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_rules_stats_category(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", "/api/alarm/rules/stats/category", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_alarm_category(args: argparse.Namespace, token: str) -> int:
    query: dict = {"pageNum": args.pageNum, "pageSize": args.pageSize}
    for key in ("name", "owner", "department", "scopeOwner", "prodOnly"):
        val = getattr(args, key, None)
        if val is not None:
            query[key] = val
    return request_json("GET", f"/api/alarm/category/{args.type}", token, query=query, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_event_center_events(args: argparse.Namespace, token: str) -> int:
    query: dict = {"pageNum": args.pageNum, "pageSize": args.pageSize}
    for key in ("user", "department", "source", "type", "status", "keyword", "startTime", "endTime"):
        val = getattr(args, key, None)
        if val:
            query[key] = val
    return request_json("GET", "/api/event-center/events", token, query=query, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_event_center_types(args: argparse.Namespace, token: str) -> int:
    return request_json("GET", "/api/event-center/event-types", token, timeout=args.timeout, raw=getattr(args, "raw", False))


def do_lark_bot_chats(args: argparse.Namespace, token: str) -> int:
    query: dict = {}
    if args.keyword:
        query["keyword"] = args.keyword
    return request_json("GET", "/api/lark/bot/chats", token, query=query or None, timeout=args.timeout, raw=getattr(args, "raw", False))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _add_stats_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--department", default=None, help="Filter by department")
    parser.add_argument("--receiver", default=None, help="Filter by receiver (e.g. jijie)")
    parser.add_argument("--source", default=None, help="Filter by source")
    parser.add_argument("--startTime", default=None, help="Start time (yyyy-MM-dd HH:mm:ss)")
    parser.add_argument("--endTime", default=None, help="End time (yyyy-MM-dd HH:mm:ss)")


def _add_pagination(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pageNum", type=int, default=1, help="Page number (default 1)")
    parser.add_argument("--pageSize", type=int, default=20, help="Page size (default 20)")


def _add_id_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("id", type=int, help="Alarm event ID")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Soul Bigeyes Admin API client. Uses INTERNAL_TOKEN -> Cas-User header."
    )
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print full response body without truncation or JSON wrapping (useful for aggregation)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- System ---
    sub.add_parser("health", help="GET /health_check").set_defaults(func=do_health)

    # --- User ---
    sub.add_parser("user-current", help="GET /api/user/current").set_defaults(func=do_user_current)
    sub.add_parser("user-departments", help="GET /api/user/departments").set_defaults(func=do_user_departments)

    # --- Alarm Events: List & Detail ---
    p = sub.add_parser("alarm-events", help="GET /api/alarm/events")
    _add_pagination(p)
    p.add_argument("--department", default=None, help="Filter by department (supported natively by backend)")
    p.add_argument("--receiver", default=None, help="Filter by receiver")
    p.add_argument("--source", default=None, help="Filter by source")
    p.add_argument("--statuses", default=None, help="e.g. firing,acked")
    p.add_argument("--levels", default=None, help="e.g. P1,P2")
    p.add_argument("--keyword", default=None, help="Keyword filter")
    p.set_defaults(func=do_alarm_events)

    # --- Alarm Events: Department one-shot aggregate ---
    p = sub.add_parser(
        "alarm-dept-stats",
        help="One-shot: auto-paginate /api/alarm/events by --department and aggregate",
    )
    p.add_argument("--department", required=True, help="Department name, e.g. 平台保障组")
    p.add_argument("--statuses", default="firing,acked", help="Comma list, default firing,acked")
    p.add_argument("--top", type=int, default=10, help="Top-N per dimension (default 10)")
    p.add_argument("--pageSize", type=int, default=100, help="Page size (<=100, default 100)")
    p.add_argument("--max-pages", dest="max_pages", type=int, default=50, help="Safety cap on pages (default 50)")
    p.set_defaults(func=do_alarm_dept_stats)

    p = sub.add_parser("alarm-event-detail", help="GET /api/alarm/events/{id}")
    _add_id_arg(p)
    p.set_defaults(func=do_alarm_event_detail)

    p = sub.add_parser("alarm-event-logs", help="GET /api/alarm/events/{id}/logs")
    _add_id_arg(p)
    p.set_defaults(func=do_alarm_event_logs)

    p = sub.add_parser("alarm-event-notify-records", help="GET /api/alarm/events/{id}/notify-records")
    _add_id_arg(p)
    p.set_defaults(func=do_alarm_event_notify_records)

    p = sub.add_parser("alarm-event-escalation", help="GET /api/alarm/events/{id}/escalation")
    _add_id_arg(p)
    p.set_defaults(func=do_alarm_event_escalation)

    # --- Alarm Events: Actions ---
    p = sub.add_parser("alarm-event-ack", help="POST /api/alarm/events/{id}/ack")
    _add_id_arg(p)
    p.set_defaults(func=do_alarm_event_ack)

    p = sub.add_parser("alarm-event-resolve", help="POST /api/alarm/events/{id}/resolve")
    _add_id_arg(p)
    p.set_defaults(func=do_alarm_event_resolve)

    p = sub.add_parser("alarm-event-batch-ack", help="POST /api/alarm/events/batch-ack")
    p.add_argument("--ids", required=True, help="Comma-separated event IDs")
    p.set_defaults(func=do_alarm_event_batch_ack)

    p = sub.add_parser("alarm-event-batch-resolve", help="POST /api/alarm/events/batch-resolve")
    p.add_argument("--ids", required=True, help="Comma-separated event IDs")
    p.set_defaults(func=do_alarm_event_batch_resolve)

    # --- Alarm Stats ---
    for name, func in [
        ("alarm-stats-summary", do_alarm_stats_summary),
        ("alarm-stats-trend", do_alarm_stats_trend),
        ("alarm-stats-response", do_alarm_stats_response),
    ]:
        p = sub.add_parser(name, help=f"GET /api/alarm/events/stats/{name.split('-')[-1]}")
        _add_stats_filters(p)
        p.set_defaults(func=func)

    p = sub.add_parser("alarm-stats-category", help="GET /api/alarm/events/stats/category")
    _add_stats_filters(p)
    p.add_argument(
        "--only-category",
        dest="only_category",
        default=None,
        help="Filter byResourceCategory to specific categories, comma separated "
             "(e.g. Application or Application,Rds,Redis)",
    )
    p.set_defaults(func=do_alarm_stats_category)

    p = sub.add_parser("alarm-stats-active", help="GET /api/alarm/events/stats/active")
    p.add_argument("--department", default=None, help="Filter by department")
    p.add_argument("--receiver", default=None, help="Filter by receiver")
    p.add_argument("--source", default=None, help="Filter by source")
    p.set_defaults(func=do_alarm_stats_active)

    # --- Alarm Events: Receiver one-shot aggregate ---
    p = sub.add_parser(
        "alarm-user-stats",
        help="One-shot: auto-paginate /api/alarm/events by --receiver and aggregate; "
             "optional --category to filter by alarm category (Application/Rds/Redis/...)",
    )
    p.add_argument("--receiver", required=True, help="Receiver username, e.g. jijie")
    p.add_argument("--statuses", default="firing,acked", help="Comma list, default firing,acked")
    p.add_argument(
        "--category",
        default=None,
        help="Filter by alarm category (client-side), comma separated, "
             "e.g. Application or Application,Rds,Redis",
    )
    p.add_argument("--top", type=int, default=10, help="Top-N per dimension (default 10)")
    p.add_argument("--pageSize", type=int, default=100, help="Page size (<=100, default 100)")
    p.add_argument("--max-pages", dest="max_pages", type=int, default=50, help="Safety cap on pages (default 50)")
    p.set_defaults(func=do_alarm_user_stats)

    # --- Alarm Rules ---
    p = sub.add_parser("alarm-rules", help="GET /api/alarm/rules")
    _add_pagination(p)
    p.add_argument("--source", default=None, help="Filter by source")
    p.add_argument("--category", default=None, help="Filter by category")
    p.add_argument("--resource", default=None, help="Filter by resource")
    p.add_argument("--keyword", default=None, help="Keyword filter")
    p.add_argument("--receiver", default=None, help="Filter by receiver")
    p.add_argument("--department", default=None, help="Filter by department")
    p.set_defaults(func=do_alarm_rules)

    p = sub.add_parser("alarm-rule-detail", help="GET /api/alarm/rules/{id}")
    _add_id_arg(p)
    p.set_defaults(func=do_alarm_rule_detail)

    sub.add_parser("alarm-rules-stats-source", help="GET /api/alarm/rules/stats/source").set_defaults(func=do_alarm_rules_stats_source)
    sub.add_parser("alarm-rules-stats-category", help="GET /api/alarm/rules/stats/category").set_defaults(func=do_alarm_rules_stats_category)

    # --- Alarm Category ---
    p = sub.add_parser("alarm-category", help="GET /api/alarm/category/{type}")
    p.add_argument("type", help="Category type")
    _add_pagination(p)
    p.add_argument("--name", default=None, help="Filter by name")
    p.add_argument("--owner", default=None, help="Filter by owner")
    p.add_argument("--department", default=None, help="Filter by department")
    p.add_argument("--scopeOwner", default=None, help="Filter by scope owner")
    p.add_argument("--prodOnly", default=None, help="Production only (true/false)")
    p.set_defaults(func=do_alarm_category)

    # --- Event Center ---
    p = sub.add_parser("event-center-events", help="GET /api/event-center/events")
    _add_pagination(p)
    p.add_argument("--user", default=None, help="Filter by user")
    p.add_argument("--department", default=None, help="Filter by department")
    p.add_argument("--source", default=None, help="Filter by source")
    p.add_argument("--type", default=None, help="Filter by event type")
    p.add_argument("--status", default=None, help="Filter by status")
    p.add_argument("--keyword", default=None, help="Keyword filter")
    p.add_argument("--startTime", default=None, help="Start time")
    p.add_argument("--endTime", default=None, help="End time")
    p.set_defaults(func=do_event_center_events)

    sub.add_parser("event-center-types", help="GET /api/event-center/event-types").set_defaults(func=do_event_center_types)

    # --- Lark Bot ---
    p = sub.add_parser("lark-bot-chats", help="GET /api/lark/bot/chats")
    p.add_argument("--keyword", default=None, help="Search keyword")
    p.set_defaults(func=do_lark_bot_chats)

    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    token = get_internal_token()
    return args.func(args, token)


if __name__ == "__main__":
    sys.exit(main())