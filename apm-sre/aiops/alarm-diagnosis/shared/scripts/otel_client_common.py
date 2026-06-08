#!/usr/bin/env python3
"""
Shared HTTP client utilities for otel-query-service skills.

Auth:
  INTERNAL_TOKEN  → sent as Cas-User request header.
  AUTH_STRICT=true → abort if token is missing.

Environment:
  PLATFORM_ENV unset / "prod" / "production"   → production URL (default)
  PLATFORM_ENV=test | dev | local | staging   → test URL
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

PROD_BASE = "http://prod-otel-query-service.soulapp-inc.cn"
TEST_BASE = "http://test-otel-query-service.soulapp-inc.cn"


def resolve_base_url() -> str:
    """Resolve OTel query service base URL from PLATFORM_ENV.

    Default = production. Only explicit non-prod env values fall back to TEST_BASE.
    Rationale: in-house ops/oncall scenarios overwhelmingly target prod;
    making it the default removes a friction step for the common case.
    """
    env = os.environ.get("PLATFORM_ENV", "").strip().lower()
    if env in ("test", "dev", "local", "staging"):
        return TEST_BASE
    return PROD_BASE


def resolve_token() -> str | None:
    """Resolve auth token once at startup. Call this in __main__, not per-request."""
    token = os.environ.get("INTERNAL_TOKEN", "").strip()
    if token:
        return token

    auth_strict = os.environ.get("AUTH_STRICT", "").strip().lower()
    if auth_strict == "true":
        print(
            "ERROR: INTERNAL_TOKEN is not set (or empty) and AUTH_STRICT=true. "
            "Set INTERNAL_TOKEN before running.",
            file=sys.stderr,
        )
        sys.exit(1)

    return None


def build_headers(token: str | None) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Cas-User"] = token
    return headers


def validate_path_segment(value: str, name: str) -> str:
    """Validate a value used in URL path segments to prevent path traversal."""
    if not re.match(r"^[A-Za-z0-9_\-]+$", value):
        print(f"ERROR: Invalid {name}: {value!r} (only alphanumeric, dash, underscore allowed)", file=sys.stderr)
        sys.exit(1)
    return value


def warn_if_not_nanoseconds(ts: int, label: str) -> None:
    """Warn if a timestamp looks like seconds or milliseconds instead of nanoseconds."""
    if ts < 1_000_000_000_000_000:
        print(
            f"WARNING: --{label}={ts} looks like seconds or milliseconds, not nanoseconds. "
            f"Nanosecond timestamps are typically 19 digits (e.g. 1700000000000000000).",
            file=sys.stderr,
        )


# Asia/Shanghai = UTC+8
_CST = timezone(timedelta(hours=8))

_RELATIVE_PATTERN = re.compile(
    r"^(\d+)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hr|hour|hours|d|day|days)\s+ago$",
    re.IGNORECASE,
)

_UNIT_MAP = {
    "s": "seconds", "sec": "seconds", "second": "seconds", "seconds": "seconds",
    "m": "minutes", "min": "minutes", "minute": "minutes", "minutes": "minutes",
    "h": "hours", "hr": "hours", "hour": "hours", "hours": "hours",
    "d": "days", "day": "days", "days": "days",
}


def parse_time_to_ns(value: str) -> int:
    """Parse a human-friendly time string into nanosecond Unix timestamp.

    Supported formats:
      - Relative: "30m ago", "1h ago", "2d ago"
      - Shortcuts: "now"
      - ISO 8601: "2026-04-14T22:00:00Z", "2026-04-14T22:00:00+08:00"
      - Date-time: "2026-04-14 22:00:00", "2026-04-14 22:00" (assumed CST)
      - Date only: "2026-04-14" (start of day, CST)
      - Raw nanoseconds: "1700000000000000000" (passed through)
      - Raw milliseconds: "1700000000000" (auto-detected and converted)
    """
    v = value.strip()

    # "now"
    if v.lower() == "now":
        return int(time.time_ns())

    # Relative: "30m ago", "1h ago"
    m = _RELATIVE_PATTERN.match(v)
    if m:
        amount = int(m.group(1))
        unit = _UNIT_MAP[m.group(2).lower()]
        dt = datetime.now(_CST) - timedelta(**{unit: amount})
        return int(dt.timestamp() * 1_000_000_000)

    # Pure digits → raw timestamp
    if v.isdigit():
        n = int(v)
        if n > 1_000_000_000_000_000_000:  # nanoseconds (19+ digits)
            return n
        if n > 1_000_000_000_000:  # milliseconds (13+ digits)
            return n * 1_000_000
        if n > 1_000_000_000:  # seconds (10+ digits)
            return n * 1_000_000_000
        # Ambiguous small number — treat as seconds
        return n * 1_000_000_000

    # ISO 8601 with timezone
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M%z"):
        try:
            dt = datetime.strptime(v.replace("Z", "+0000"), fmt.replace("Z", "%z"))
            return int(dt.timestamp() * 1_000_000_000)
        except ValueError:
            continue

    # Local date-time formats (assumed CST/UTC+8)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(v, fmt).replace(tzinfo=_CST)
            return int(dt.timestamp() * 1_000_000_000)
        except ValueError:
            continue

    print(
        f"ERROR: Cannot parse time '{v}'. "
        f"Use: '30m ago', '1h ago', 'now', '2026-04-14 22:00', or raw nanoseconds.",
        file=sys.stderr,
    )
    sys.exit(1)


def query_services(
    client: "OtelClient",
    start_ns: int,
    end_ns: int,
    owner: str = "",
    service_name: str = "",
    tenant: str = "",
    language: list | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Query the /api/v1/services endpoint for registered applications."""
    body = {
        "start": str(start_ns),
        "end": str(end_ns),
        "tags": [],
        "pageSize": page_size,
        "page": page,
        "serviceNameLike": service_name,
        "ownerLike": owner,
        "tenantLike": tenant,
        "languageLike": language or [],
    }
    return client.post("/api/v1/services", body)


def format_services_table(result: dict) -> str:
    """Format services API result as a readable table."""
    apps = result.get("list", [])
    total = result.get("total", 0)
    if not apps:
        return "No applications found."

    lines = [f"共 {total} 个应用（当前页 {len(apps)} 条）:\n"]
    header = f"{'#':<4} {'应用名称':<35} {'实例名称':<40} {'语言':<8} {'SDK版本':<12} {'租户':<15} {'集群':<25} {'负责人':<12}"
    lines.append(header)
    lines.append("-" * len(header))
    for i, app in enumerate(apps, 1):
        lines.append(
            f"{i:<4} {app.get('serviceName',''):<35} "
            f"{app.get('serviceInstanceName',''):<40} "
            f"{app.get('sdkLanguage',''):<8} "
            f"{app.get('sdkVersion',''):<12} "
            f"{app.get('tenant',''):<15} "
            f"{app.get('cluster',''):<25} "
            f"{app.get('owner',''):<12}"
        )
    return "\n".join(lines)


def parse_tags_json(raw: str) -> list:
    """Parse a --tags JSON string with clear error on malformed input."""
    try:
        tags = json.loads(raw)
        if not isinstance(tags, list):
            print("ERROR: --tags must be a JSON array", file=sys.stderr)
            sys.exit(1)
        return tags
    except json.JSONDecodeError as exc:
        print(f"ERROR: --tags is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

class OtelClient:
    """Thin HTTP client wrapping urllib for otel-query-service."""

    def __init__(self, base_url: str, token: str | None):
        self.base_url = base_url
        self.headers = build_headers(token)

    def get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            filtered = {k: v for k, v in params.items() if v is not None}
            if filtered:
                url = f"{url}?{urllib.parse.urlencode(filtered)}"
        req = urllib.request.Request(url, headers=self.headers, method="GET")
        return self._send(req, url)

    def post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
        return self._send(req, url)

    def get_stream(self, path: str, params: dict | None = None):
        """Open a streaming GET connection. Caller must iterate lines and close."""
        url = f"{self.base_url}{path}"
        if params:
            filtered = {k: v for k, v in params.items() if v is not None}
            if filtered:
                url = f"{url}?{urllib.parse.urlencode(filtered)}"
        req = urllib.request.Request(url, headers=self.headers, method="GET")
        try:
            return urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"[HTTP {e.code}] {url}\n{body}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"[Network Error] {url}\n{e.reason}", file=sys.stderr)
            sys.exit(1)

    def _send(self, req: urllib.request.Request, url: str) -> dict:
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                if not raw.strip():
                    return {}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    print(f"WARNING: Response is not valid JSON from {url}", file=sys.stderr)
                    print(raw[:500], file=sys.stderr)
                    sys.exit(1)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"[HTTP {e.code}] {url}\n{body}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"[Network Error] {url}\n{e.reason}", file=sys.stderr)
            sys.exit(1)


def print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Query safety guards
# ---------------------------------------------------------------------------

# Max time range per command category (in seconds)
MAX_RANGE = {
    "search":    3 * 3600,       # 3h  — search-logs, search-spans, app trace endpoints
    "aggregate": 24 * 3600,      # 24h — aggregate, error-summary, list-errors, count-errors
    "trend":     7 * 24 * 3600,  # 7d  — trend charts
}

# Max result limits per command category
MAX_LIMIT = {
    "search": 1000,
    "aggregate": 200,
}

# High-cardinality fields that are dangerous to GROUP BY
_HIGH_CARDINALITY_FIELDS = {
    "traceID", "trace_id", "spanID", "span_id", "body",
    "traceId", "spanId",
}


def enforce_time_range(start_ns: int, end_ns: int, category: str, cmd: str) -> None:
    """Abort if the query time range exceeds the safe maximum for the command category.

    Categories: 'search', 'aggregate', 'trend'.
    """
    if end_ns <= start_ns:
        print(
            f"ERROR: [{cmd}] --end must be after --start.",
            file=sys.stderr,
        )
        sys.exit(1)

    max_sec = MAX_RANGE.get(category)
    if not max_sec:
        return
    range_sec = (end_ns - start_ns) / 1_000_000_000
    if range_sec > max_sec:
        max_h = max_sec / 3600
        actual_h = range_sec / 3600
        print(
            f"ERROR: [{cmd}] Time range {actual_h:.1f}h exceeds maximum {max_h:.0f}h. "
            f"Use a shorter range or add more specific filters.\n"
            f"Tip: Large applications can generate 1M+ logs/min — wide time ranges may overload the backend.",
            file=sys.stderr,
        )
        sys.exit(1)


def validate_limit(limit: int, category: str, cmd: str) -> int:
    """Clamp the result limit to a safe maximum. Returns the validated limit."""
    max_limit = MAX_LIMIT.get(category)
    if max_limit and limit > max_limit:
        print(
            f"WARNING: [{cmd}] --limit={limit} exceeds maximum {max_limit}, clamping to {max_limit}.",
            file=sys.stderr,
        )
        return max_limit
    return limit


def warn_high_cardinality_group_by(field: str, cmd: str) -> None:
    """Warn if the GROUP BY field has high cardinality, which is expensive in ClickHouse."""
    bare = field.split(".")[-1]
    if bare in _HIGH_CARDINALITY_FIELDS or field in _HIGH_CARDINALITY_FIELDS:
        print(
            f"WARNING: [{cmd}] GROUP BY '{field}' is a high-cardinality field. "
            f"This may cause excessive memory usage in ClickHouse. "
            f"Consider grouping by a lower-cardinality field instead.",
            file=sys.stderr,
        )