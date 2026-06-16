#!/usr/bin/env python3
"""Dubbo error log attribution parser (fallback for trace-first attribution).

Used by alarm-diagnosis / apm-diagnosis as a fallback when otel-traces lack
coverage (sampling missed, service.name not mapped, or legacy Dubbo SDK without
trace export). Regex fields below cover both new and old Dubbo SDK patterns;
old SDK without `remote.application` will still yield service/method/provider
but `app="UNKNOWN"` — callers must report this as a fidelity downgrade.

Stdlib-only, Python 3.9+. Mirrors the parsing logic battle-tested in
error-log-analysis/scripts/diagnose_alert_chain.py with extra schema fields
and explicit data-source labeling so the diagnosis report can declare which
attribution source produced each row.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from typing import Iterable

# Regex set — keep in sync with error-log-analysis/diagnose_alert_chain.py
RE_SERVICE = re.compile(r"service\s+([\w.$]+)\. Tried")
RE_INTERFACE = re.compile(r"interface=([\w.$]+)")
RE_METHOD = re.compile(r"method:\s*([A-Za-z0-9_$]+)")
RE_REMOTE_APP = re.compile(r"remote\.application=([^&\s,]+)")
RE_PROVIDERS = re.compile(r"providers \[([^\]]+)\]")
RE_PROVIDER_URL = re.compile(r"provider: dubbo://([^/?]+)")
RE_TIMEOUT = re.compile(r"timeout:\s*(\d+)\s*ms")
RE_ENTRY_SPRINGMVC = re.compile(r"_sys_entry-endpoint=springmvc#([^&\s]+)")
RE_ENTRY_UPSTREAM = re.compile(r"upstream-endpoint=springmvc#([^&\s]+)")
RE_ENTRY_DUBBO_PROVIDER = re.compile(r"_sys_entry-endpoint=dubbo-provider#([^&\s]+)")

# Middleware instance regex
RE_HBASE_HOST = re.compile(r"(?:hbase|HBase).*?([\w.-]+:\d{4,5})")
RE_HBASE_TABLE = re.compile(r"table[=:\s]+([\w:_.-]+)", re.IGNORECASE)
RE_HBASE_REGION = re.compile(r"(?:RegionServer|region)[=:\s]+([\w.:_-]+)", re.IGNORECASE)
RE_REDIS_NODE = re.compile(r"(?:redis|Redis)[^a-zA-Z0-9]+([\w.-]+:\d{4,5})")
RE_REDIS_CMD = re.compile(r"command[=:\s]+([A-Z]+)")
RE_REDIS_KEY = re.compile(r"key[=:\s]+([\w:.-]+)")
RE_DB_URL = re.compile(r"jdbc:mysql://([\w.-]+:\d{4,5})/(\w+)")
RE_DB_TABLE = re.compile(r"(?:FROM|UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+`?(\w+)`?", re.IGNORECASE)
RE_MQ_TOPIC = re.compile(r"topic[=:\s]+([\w.-]+)")
RE_MQ_GROUP = re.compile(r"(?:group|consumerGroup)[=:\s]+([\w.-]+)")
RE_MQ_BROKER = re.compile(r"broker[=:\s]+([\w.-]+:\d{4,5})")


def parse_downstream(logs: Iterable[dict]) -> dict:
    """Parse Dubbo downstream attribution from a list of error log entries.

    Each log entry should follow the OTel log API shape:
      {"data": {"attributes_string": {"exception.message": ..., "exception.stacktrace": ..., "code.function": ...}}}

    Returns a dict with structured attribution + a `legacy_sdk_ratio` field that
    callers should surface as observability-limits when high.
    """
    methods: Counter[str] = Counter()
    apps: Counter[str] = Counter()
    providers: Counter[str] = Counter()
    by_method_provider: dict[str, Counter[str]] = defaultdict(Counter)
    endpoints: Counter[str] = Counter()
    timeouts: Counter[int] = Counter()

    total = 0
    missing_remote_app = 0

    for entry in logs:
        total += 1
        data = entry.get("data") or {}
        attrs = data.get("attributes_string") or {}
        msg = attrs.get("exception.message") or attrs.get("exception.stacktrace") or ""

        svc_match = RE_SERVICE.search(msg) or RE_INTERFACE.search(msg)
        method_match = RE_METHOD.search(msg)
        app_match = RE_REMOTE_APP.search(msg)
        provider_match = RE_PROVIDERS.search(msg) or RE_PROVIDER_URL.search(msg)
        ep_match = (
            RE_ENTRY_SPRINGMVC.search(msg)
            or RE_ENTRY_UPSTREAM.search(msg)
            or RE_ENTRY_DUBBO_PROVIDER.search(msg)
        )
        timeout_match = RE_TIMEOUT.search(msg)

        service = svc_match.group(1) if svc_match else "UNKNOWN"
        method = method_match.group(1) if method_match else attrs.get("code.function", "UNKNOWN")
        if app_match:
            app = app_match.group(1)
        else:
            app = "UNKNOWN"
            missing_remote_app += 1
        provider = provider_match.group(1) if provider_match else "UNKNOWN"
        endpoint = ep_match.group(1) if ep_match else attrs.get("code.function", "UNKNOWN")

        key = f"{service}#{method}"
        methods[key] += 1
        apps[app] += 1
        providers[provider] += 1
        by_method_provider[key][provider] += 1
        endpoints[endpoint] += 1
        if timeout_match:
            timeouts[int(timeout_match.group(1))] += 1

    legacy_ratio = round(missing_remote_app * 100.0 / total, 1) if total else 0.0

    return {
        "total_samples": total,
        "methods": methods.most_common(20),
        "apps": apps.most_common(10),
        "providers": providers.most_common(20),
        "endpoints": endpoints.most_common(20),
        "timeouts_ms": timeouts.most_common(5),
        "by_method_provider": {k: v.most_common(5) for k, v in by_method_provider.items()},
        "legacy_sdk_ratio": legacy_ratio,
        "legacy_sdk_warning": (
            f"{legacy_ratio}% samples missing remote.application — likely old Dubbo SDK; "
            "downstream app attribution unreliable, prefer trace-based attribution."
            if legacy_ratio >= 30
            else None
        ),
    }


def parse_problem_instance(logs: Iterable[dict]) -> dict:
    """Extract concrete middleware instance (HBase/Redis/DB/MQ) signals.

    Returns a dict keyed by middleware type. Each entry is a list of
    (instance, count) tuples sorted desc. Callers should fill the "问题实例"
    section of the diagnosis report from these.
    """
    hbase_hosts: Counter[str] = Counter()
    hbase_tables: Counter[str] = Counter()
    hbase_regions: Counter[str] = Counter()
    redis_nodes: Counter[str] = Counter()
    redis_cmds: Counter[str] = Counter()
    db_hosts: Counter[str] = Counter()
    db_tables: Counter[str] = Counter()
    mq_topics: Counter[str] = Counter()
    mq_brokers: Counter[str] = Counter()
    mq_groups: Counter[str] = Counter()

    hbase_signals: Counter[str] = Counter()
    redis_signals: Counter[str] = Counter()

    for entry in logs:
        data = entry.get("data") or {}
        attrs = data.get("attributes_string") or {}
        text = " ".join(
            x
            for x in (
                attrs.get("exception.message"),
                attrs.get("exception.stacktrace"),
                data.get("body"),
            )
            if x
        )
        if not text:
            continue

        for m in RE_HBASE_HOST.finditer(text):
            hbase_hosts[m.group(1)] += 1
        for m in RE_HBASE_TABLE.finditer(text):
            hbase_tables[m.group(1)] += 1
        for m in RE_HBASE_REGION.finditer(text):
            hbase_regions[m.group(1)] += 1
        for signal in ("CallQueueTooBigException", "callTimeout", "rpcTimeout", "NotServingRegion"):
            if signal in text:
                hbase_signals[signal] += 1

        for m in RE_REDIS_NODE.finditer(text):
            redis_nodes[m.group(1)] += 1
        for m in RE_REDIS_CMD.finditer(text):
            redis_cmds[m.group(1)] += 1
        for signal in ("MOVED", "ASK", "CLUSTERDOWN", "READONLY", "LOADING"):
            if signal in text:
                redis_signals[signal] += 1

        for m in RE_DB_URL.finditer(text):
            db_hosts[f"{m.group(1)}/{m.group(2)}"] += 1
        for m in RE_DB_TABLE.finditer(text):
            db_tables[m.group(1)] += 1

        for m in RE_MQ_TOPIC.finditer(text):
            mq_topics[m.group(1)] += 1
        for m in RE_MQ_BROKER.finditer(text):
            mq_brokers[m.group(1)] += 1
        for m in RE_MQ_GROUP.finditer(text):
            mq_groups[m.group(1)] += 1

    return {
        "hbase": {
            "hosts": hbase_hosts.most_common(5),
            "tables": hbase_tables.most_common(5),
            "regions": hbase_regions.most_common(5),
            "signals": hbase_signals.most_common(),
        },
        "redis": {
            "nodes": redis_nodes.most_common(5),
            "commands": redis_cmds.most_common(5),
            "signals": redis_signals.most_common(),
        },
        "db": {
            "hosts": db_hosts.most_common(5),
            "tables": db_tables.most_common(5),
        },
        "mq": {
            "topics": mq_topics.most_common(5),
            "brokers": mq_brokers.most_common(5),
            "groups": mq_groups.most_common(5),
        },
    }


def logger_attribution(logger_rows: list[dict], threshold_pct: float = 70.0) -> dict | None:
    """Attribute downstream from Java logger class name dominance.

    Added in v3.0.1 after the chat-biz / photon AbInvoker case demonstrated that
    a heavily concentrated `logger.name` aggregate is often more reliable than
    regex-parsed stack traces for identifying the downstream service —
    especially when:
      - OTel trace is not sampled for the upstream service (trace fallback fails)
      - Old Dubbo SDK does not populate `remote.application`
      - The client-side SDK class name encodes the downstream service identity
        (e.g. `com.soul.photon.govern.AbInvoker` ⇒ photon)

    Input:
        logger_rows: [{"logger.name": "com.foo.bar.X", "count": 6385}, ...]
                     sorted by count desc.
        threshold_pct: minimum concentration to trigger attribution (default 70%).

    Returns:
        None if no logger is dominant (Top1 < threshold).
        Otherwise: {
            "top_logger": "com.foo.bar.X",
            "top_logger_pct": 84.6,
            "inferred_downstream_app": "foo",           # 2nd package segment
            "inferred_downstream_class": "com.foo.bar.X",
            "evidence": "Top1 logger 84.6% concentration"
        }

    Heuristic for inferring downstream app:
        Java package convention `<tld>.<company>.<app>.<...>`:
          com.soul.photon.govern.AbInvoker        → photon
          com.soul.chat.biz.component.X            → chat (with hint of chat-biz)
          com.alibaba.dubbo.rpc.X                  → alibaba (framework — caller should ignore)
        Returns the 2nd package segment by default. If the result is a known
        infra/framework package (org, apache, alibaba, dubbo, spring, jdk), the
        function returns None so the caller can fall back to other signals.
    """
    if not logger_rows:
        return None

    total = sum(int(r.get("count", 0) or 0) for r in logger_rows)
    if total <= 0:
        return None

    top = logger_rows[0]
    top_name = top.get("logger.name") or top.get("name") or ""
    top_count = int(top.get("count", 0) or 0)
    top_pct = round(top_count * 100.0 / total, 1)
    if top_pct < threshold_pct or not top_name:
        return None

    INFRA_TOKENS = {"org", "io", "javax", "java", "jdk", "apache", "spring", "alibaba", "dubbo"}
    parts = top_name.split(".")
    inferred_app: str | None = None
    if len(parts) >= 3 and parts[0].lower() not in INFRA_TOKENS:
        # Standard pattern: tld.company.app.module.Class → take parts[2]
        candidate = parts[2].lower()
        if candidate not in INFRA_TOKENS:
            inferred_app = candidate
    # If pattern doesn't fit (framework class name), explicitly return None for
    # downstream app so caller knows logger-attribution can't conclude here.

    return {
        "top_logger": top_name,
        "top_logger_pct": top_pct,
        "top_logger_count": top_count,
        "inferred_downstream_app": inferred_app,
        "inferred_downstream_class": top_name,
        "evidence": f"Top1 logger '{top_name}' contributes {top_pct}% of error volume ({top_count}/{total})",
        "is_framework_logger": inferred_app is None,
    }


# Distributed lock failure patterns (v3.0.2)
RE_LOCK_FAIL_MSG = re.compile(
    r"Failed to obtain the distributed lock|获取分布式锁失败|加锁失败|"
    r"lock\.tryLock.*returned false|lock acquisition failed",
    re.IGNORECASE,
)
RE_LOCK_KEY = re.compile(r"key\s*=\s*([\w:.\-]+)", re.IGNORECASE)
RE_LOCK_TTL = re.compile(r"second\s*=\s*(\d+)|expire\s*=\s*(\d+)|ttl\s*=\s*(\d+)", re.IGNORECASE)
RE_LOCK_HOLDER = re.compile(r"holder\s*=\s*([\w\-]+)", re.IGNORECASE)


def lock_failure_attribution(logs: Iterable[dict]) -> dict | None:
    """Attribute distributed-lock-failure errors.

    Added in v3.0.2 after the meta-service / USER_DIGITAL_PROPERTY case
    demonstrated that this scenario has a unique attribution shape:
      - root cause is not in upstream/downstream service, but in lock contention
      - key pattern + TTL + holder UUID reveal whether it's same-key reentry
        or distinct-key parallel saturation
      - standard fixes are: (a) idempotency guard, (b) shrink TTL,
        (c) check unlock path

    Returns None if no log sample matches the lock-failure pattern.
    Otherwise returns:
        {
          "matched_samples": N,
          "key_patterns": [{"prefix": "ext:<user>:avatar-...", "count": N, "example": "ext:29990374:..."}, ...],
          "ttl_seconds": [30, 30, ...],   # observed TTL values
          "distinct_holders": M,           # how many distinct lock holder UUIDs (consumer pods)
          "same_key_repeat_max": K,        # max times any single key appears (contention severity)
          "evidence": "<one-line summary>",
          "standard_fixes": [
              "P1: 检查 finally 块是否漏 unlock",
              "P1: producer 端对同 key 加 idempotent 去重",
              "P2: TTL 30s 可能过长，建议改 5s + 业务幂等校验",
              "P2: 拿锁失败应 retry+backoff，避免 30s 死等",
          ]
        }
    """
    samples: list[str] = []
    for entry in logs:
        data = entry.get("data") or {}
        attrs = data.get("attributes_string") or {}
        text = " ".join(
            x
            for x in (
                attrs.get("exception.message"),
                attrs.get("exception.stacktrace"),
                data.get("body"),
            )
            if x
        )
        if text and RE_LOCK_FAIL_MSG.search(text):
            samples.append(text)

    if not samples:
        return None

    key_count: Counter[str] = Counter()
    key_prefix_count: Counter[str] = Counter()
    holders: set[str] = set()
    ttls: Counter[int] = Counter()

    for s in samples:
        for km in RE_LOCK_KEY.finditer(s):
            key = km.group(1)
            key_count[key] += 1
            # Prefix = drop last `-<digit>+-<digit>+` style suffix when present
            # e.g. ext:29990374:avatar-1707030496556-05342 → ext:29990374:avatar
            prefix = re.sub(r"-\d{4,}(?:-\d+)?$", "", key)
            key_prefix_count[prefix] += 1
        for hm in RE_LOCK_HOLDER.finditer(s):
            holders.add(hm.group(1))
        for tm in RE_LOCK_TTL.finditer(s):
            for g in tm.groups():
                if g:
                    ttls[int(g)] += 1

    top_prefixes = [
        {"prefix": p, "count": c, "example": next(iter(k for k in key_count if k.startswith(p)), p)}
        for p, c in key_prefix_count.most_common(5)
    ]
    same_key_max = max(key_count.values()) if key_count else 0

    fixes = [
        "P1: 检查 consumer/业务代码的 finally 块是否漏 unlock（异常路径锁未释放）",
        "P1: 上游 producer 对同 key 做幂等去重，重复消息直接 ACK 不进锁",
    ]
    if any(t >= 20 for t in ttls):
        fixes.append(f"P2: 锁 TTL {sorted(ttls.keys())[-1]}s 偏长，建议改 5s + 业务幂等校验")
    fixes.append("P2: 拿锁失败应 retry+backoff，避免线程长时间死等")

    return {
        "matched_samples": len(samples),
        "key_patterns": top_prefixes,
        "ttl_seconds": dict(ttls),
        "distinct_holders": len(holders),
        "same_key_repeat_max": same_key_max,
        "evidence": (
            f"{len(samples)} lock-failure samples observed; "
            f"top key prefix '{top_prefixes[0]['prefix']}' appeared {top_prefixes[0]['count']}x; "
            f"{len(holders)} distinct lock holders (consumer pods); "
            f"max same-key contention = {same_key_max}"
            if top_prefixes
            else f"{len(samples)} lock-failure samples observed (no parseable key)"
        ),
        "standard_fixes": fixes,
    }


def pod_judgement(rows: list[dict]) -> dict:
    """Quantified Pod-distribution judgement.

    Input rows: [{"name": "<ip-or-host>", "count": N, "pct": float}, ...] sorted desc.
    Returns: {"verdict": str, "top1_pct": float, "top2_pct": float, "top3_pct": float, "evidence": str}.

    Thresholds (battle-tested in error-log-analysis):
      single-pod likely : top1 >= 50
      two-pod likely    : top2 >= 70 (and top1 < 50)
      few-pod skew      : top1 >= 20 or top3 >= 50
      multi-pod / service-wide : otherwise
    """
    if not rows:
        return {
            "verdict": "unknown",
            "top1_pct": 0.0,
            "top2_pct": 0.0,
            "top3_pct": 0.0,
            "evidence": "no host/provider distribution data",
        }
    top1 = rows[0].get("pct", 0.0)
    top2 = sum(r.get("pct", 0.0) for r in rows[:2])
    top3 = sum(r.get("pct", 0.0) for r in rows[:3])
    if top1 >= 50:
        verdict = "single-pod-likely"
    elif top2 >= 70:
        verdict = "two-pod-likely"
    elif top1 >= 20 or top3 >= 50:
        verdict = "few-pod-skew"
    else:
        verdict = "multi-pod-service-wide"
    return {
        "verdict": verdict,
        "top1_pct": round(top1, 2),
        "top2_pct": round(top2, 2),
        "top3_pct": round(top3, 2),
        "evidence": f"top1={top1}% top2={top2}% top3={top3}%",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse Dubbo error logs for downstream / instance / pod attribution.",
    )
    parser.add_argument(
        "--input",
        help="JSON file containing a list of OTel log entries; '-' to read stdin",
        default="-",
    )
    parser.add_argument(
        "--mode",
        choices=("downstream", "instance", "all"),
        default="all",
    )
    args = parser.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input).read()
    try:
        logs = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(logs, list):
        print("expected a JSON array of log entries", file=sys.stderr)
        return 2

    output: dict = {}
    if args.mode in ("downstream", "all"):
        output["downstream"] = parse_downstream(logs)
    if args.mode in ("instance", "all"):
        output["problem_instance"] = parse_problem_instance(logs)

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())