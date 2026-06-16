#!/usr/bin/env python3
"""
alarm_resource_mapper — convert bigeyes alarm "resource name" to otel service.name,
and decide whether the alarm category is auto-diagnosable.

Usage as a module:
    from alarm_resource_mapper import resource_to_service, is_diagnosable_category

    svc = resource_to_service("prod-pay-asset")     # → "pay-asset"
    ok  = is_diagnosable_category("Application")    # → True

Usage as a CLI (for AI agents to call inline):
    python3 alarm_resource_mapper.py to-service prod-pay-asset
    python3 alarm_resource_mapper.py check-category Application
"""

from __future__ import annotations

import argparse
import sys

# Environment prefixes to strip when mapping bigeyes resource → otel service.name.
# Order matters only insofar as longer prefixes should not eclipse shorter ones;
# the entries below are mutually unambiguous.
ENV_PREFIXES = ("prod-", "pre-", "test-", "gray-")

# Categories that alarm-diagnosis can drive end-to-end (logs + traces correlation).
# v3.0.6: 大小写均接受 — bigeyes 历史 / 新规则都可能用 "Application" 或 "application"。
# 实测 EVT-20260408-76768978（user-provider）alarmCategory="application" 小写
# 完全可诊断，旧 v3.0.5 因严格大小写匹配错踢到信息卡片分支 → 修复为 case-insensitive。
_DIAGNOSABLE_LOWER = frozenset({"application"})
DIAGNOSABLE_CATEGORIES = frozenset({"Application", "application"})  # 保留显式集合，便于审计


def resource_to_service(resource: str) -> str:
    """Strip k8s namespace prefix and environment prefix from a bigeyes resource.

    Examples:
        prod-pay-asset                  -> pay-asset
        pre-nacos-server                -> nacos-server
        gray-soul-order                 -> soul-order
        test-foo                        -> foo
        service-c-pay/prod-pay-asset    -> pay-asset
        pay-asset                       -> pay-asset            (no change)
        prod--weird                     -> -weird               (only first prefix stripped)
    """
    if not resource:
        return resource
    s = resource.strip()
    # k8s-style namespace prefix
    if "/" in s:
        s = s.split("/")[-1]
    # environment prefix (single strip)
    for p in ENV_PREFIXES:
        if s.startswith(p):
            return s[len(p):]
    return s


# Cluster / environment suffixes — 这些是部署形态标识，**不属于** OTel service.name。
# v3.0.7 简化策略（用户反馈 push-base-provider / user-provider / chat-biz-dubbo 案例后）：
#
# **核心规则只有两条**（确定性）：
#   1. 去环境前缀（prod- / pre- / test- / gray-）
#   2. 去固定集群后缀（-k8s / -bj / -sh / -dt / -aliyun / -ack）
#
# **不 strip 业务名中的任何部分**（包括 -dubbo / -provider / -consumer / -server 等）：
# 业务名的所有部分都是 service.name 的合法组成部分。
#   - prod-user-provider          → service.name = user-provider（不是 user）
#   - prod-push-base-provider     → service.name = push-base-provider（不是 push-base）
#   - prod-pay-channel-provider   → service.name = pay-channel-provider（不是 pay-channel）
#   - prod-chat-biz-dubbo-k8s     → service.name = chat-biz-dubbo（不是 chat-biz）
#
# **特例**：少数服务在 OTel 注册时去掉了部分业务后缀（如 chat-biz-dubbo 在 OTel 里实际叫 chat-biz）。
# 这类不规则命名由 SKILL.md Phase 0 Step 2 的 `list-apps --name <候选>` fuzzy 兜底秒命中，
# **不由 mapper 暴力穷举生成**（避免误命中无关服务，比如 `user` 撞到其他叫 user 的服务）。
#
# 设计取舍：少候选 + 高准确率 + list-apps 兜底 > 多候选 + 误命中其他服务。
CLUSTER_SUFFIXES = ("-k8s", "-bj", "-sh", "-dt", "-aliyun", "-ack")


def resource_to_service_candidates(resource: str) -> list[str]:
    """Generate ordered candidate OTel service.name values to probe (v3.0.7 简化版).

    策略 — 只做 2 个**确定性**转换：
      1. 去环境前缀（prod-/pre-/test-/gray-）
      2. 去集群/环境后缀（-k8s/-bj/-sh/-dt/-aliyun/-ack）

    **不 strip 业务名任何部分**（包括 -dubbo / -provider / -consumer / -server）：
    业务名所有部分都是 service.name 的合法组成部分。例如：
      - prod-user-provider          → user-provider  （不是 user）
      - prod-push-base-provider     → push-base-provider  （不是 push-base）
      - prod-chat-biz-dubbo-k8s     → chat-biz-dubbo  （不是 chat-biz）

    **不加 soul- 前缀变体**：多数情况无意义，造成 probe 浪费 + 误命中无关服务。

    **特例**：少数服务 OTel 注册时去掉了部分业务后缀（如 chat-biz-dubbo 实际注册为
    `chat-biz`）— 这类不规则命名由 SKILL.md Phase 0 Step 2 的 `list-apps --name`
    fuzzy 兜底秒命中，**不由 mapper 暴力穷举生成**。

    输出最多 3 个候选（按 likelihood 降序）:
      [去环境前缀+去集群后缀, 去环境前缀, 原始]

    Examples:
      prod-user-provider-k8s       → [user-provider, user-provider-k8s, prod-user-provider-k8s]
      prod-user-provider           → [user-provider, prod-user-provider]
      prod-push-base-provider-k8s  → [push-base-provider, push-base-provider-k8s, prod-push-base-provider-k8s]
      prod-meta-service            → [meta-service, prod-meta-service]
      chat-biz                     → [chat-biz]
      prod-chat-biz-dubbo-k8s      → [chat-biz-dubbo, chat-biz-dubbo-k8s, **chat-biz**,
                                     chat-biz-dubbo-k8s（无 dubbo 同形），prod-chat-biz-dubbo-k8s]
        （v3.0.8 加 -dubbo 特殊处理: 含 "dubbo" 段时额外生成"去 dubbo"候选）

    History:
      v3.0.0/3.0.1: progressive_tail_strip 暴力 strip 含业务语义后缀 → 候选 7+ 个，
                    误命中风险（如 user-provider → user 撞到无关服务）。
      v3.0.7: 简化为环境前缀 + 集群后缀两个确定性转换，依赖 list-apps fuzzy 兜底特殊命名。
      v3.0.8: 加 -dubbo 特殊处理（实证案例 prod-chat-biz-dubbo-k8s 在 OTel 注册为 chat-biz），
              **仅对 dubbo 段额外加候选**，其它业务后缀 -provider/-consumer/-server 不动。
    """
    if not resource:
        return []

    seen: set[str] = set()
    out: list[str] = []

    def add(c: str) -> None:
        c = c.strip() if c else ""
        if c and c not in seen:
            seen.add(c)
            out.append(c)

    primary = resource_to_service(resource)  # 已去环境前缀 + k8s namespace

    # Layer 1: primary 去集群后缀（最可能的 OTel service.name）
    stripped = primary
    for suf in CLUSTER_SUFFIXES:
        if stripped.endswith(suf):
            stripped = stripped[: -len(suf)]
            break
    add(stripped)

    # Layer 2: primary 不去集群后缀（也可能 OTel 名带 -k8s）
    add(primary)

    # Layer 3 (v3.0.8 新增): -dubbo 特殊处理 — 部分服务 OTel 注册时去掉了 -dubbo 段
    # （实证案例: prod-chat-biz-dubbo-k8s 在 OTel 里注册为 chat-biz）
    # 仅当 stripped 含 "dubbo" 段时额外生成"去 dubbo"候选，**不影响其它业务后缀**
    # （-provider / -consumer / -server 仍保留为合法业务名组成部分）
    for source in (stripped, primary):
        parts = source.split("-")
        if "dubbo" in parts:
            no_dubbo = "-".join(p for p in parts if p != "dubbo")
            if no_dubbo:
                add(no_dubbo)

    # Layer 4: 原始 resource（最后保底）
    add(resource.strip())

    return out


def is_diagnosable_category(category: str) -> bool:
    """Return True if alarm-diagnosis can run its full root-cause pipeline.

    Currently only "Application" is auto-diagnosable. Other categories
    (NginxDomain, KafkaTopic, Redis, Rds, GroupEcs, ecs, ModelApplication,
    PromQL, application[lowercase]) fall back to "info-only" mode.
    """
    # v3.0.6: case-insensitive 比较，"Application" 和 "application" 都接受
    return (category or "").strip().lower() in _DIAGNOSABLE_LOWER


def category_hint(category: str) -> str:
    """Human-readable hint explaining why a non-diagnosable category was skipped."""
    if is_diagnosable_category(category):
        return ""
    hints = {
        # v3.0.6: 小写 application 现在视为可诊断，删除踢出 hint（保留 key 占位防回归）
        # "application": （已并入可诊断，无 hint）,
        "PromQL":      "PromQL 自定义告警，需解析表达式才能定位目标维度，本 skill 暂不支持。",
        "NginxDomain": "Nginx 域名告警，资源是域名而非应用，请用网关/接入层维度排查。",
        "KafkaTopic":  "Kafka topic 告警，请使用 Kafka 监控面板或后续的指标 skill 排查。",
        "Redis":       "Redis 实例告警，请使用 Redis 监控面板或后续的指标 skill 排查。",
        "Rds":         "RDS 数据库告警，请使用 DB 慢日志/监控面板或后续的指标 skill 排查。",
        "GroupEcs":    "ECS 机器组告警（CPU/内存/磁盘等），请使用主机指标面板或后续的指标 skill 排查。",
        "ecs":         "ECS 单机告警，请使用主机指标面板或后续的指标 skill 排查。",
        "ModelApplication": "AI 模型应用告警，需要专门的模型监控视角，本 skill 暂不支持。",
    }
    return hints.get(
        category,
        f"未知告警类别 '{category}'，本 skill 暂不支持自动诊断；已为你拉取告警基本信息。",
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="bigeyes resource → otel service mapper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_to = sub.add_parser("to-service", help="strip prefix from a resource name")
    p_to.add_argument("resource")

    p_cand = sub.add_parser(
        "candidates",
        help="emit ordered candidate OTel service.name values (JSON list) for probing",
    )
    p_cand.add_argument("resource")
    p_cand.add_argument(
        "--format",
        choices=("json", "lines"),
        default="json",
        help="json (default, machine-readable) or lines (one candidate per line)",
    )

    p_chk = sub.add_parser("check-category", help="report whether a category is auto-diagnosable")
    p_chk.add_argument("category")

    args = parser.parse_args()

    if args.cmd == "to-service":
        print(resource_to_service(args.resource))
        return 0

    if args.cmd == "candidates":
        import json as _json
        cands = resource_to_service_candidates(args.resource)
        if args.format == "json":
            _json.dump(cands, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            for c in cands:
                sys.stdout.write(c + "\n")
        return 0

    if args.cmd == "check-category":
        ok = is_diagnosable_category(args.category)
        if ok:
            print(f"diagnosable: {args.category}")
            return 0
        print(f"not-diagnosable: {args.category}")
        hint = category_hint(args.category)
        if hint:
            print(f"hint: {hint}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(_cli())