---
description: |+
    Trigger ONLY on alarm-with-diagnosis-intent phrases:
      "告警 EVT-XXX 为什么触发", "帮我看下这个告警", "告警根因",
      "粘贴告警卡片 + 帮我分析",  "5 分钟 ERROR 超阈值", "Top1 是 Dubbo RpcException",
      "下游服务是整体抖动还是单 Pod 问题", "alert root cause".

name: alarm-diagnosis
version: 3.0.8
---


# alarm-diagnosis Skill

**一条命令，从告警事件 ID 到根因分析 + 修复建议。**

围绕**告警事件**做诊断。和 `apm-diagnosis`（围绕**服务/应用**做诊断）形成互补：

| 维度 | apm-diagnosis | **alarm-diagnosis（本 skill）** |
|------|--------------|-------------------------------|
| 入口 | 服务名 / traceId | **告警事件 ID / 告警卡片** |
| 方向 | Outside-in：服务全景 → 下钻 | **Inside-out：症状 → 反推根因** |
| 时间锚点 | 宽窗口（1h ~ 1d 看趋势） | **告警 triggerTime ± 30min（精窗口）** |
| 核心问题 | "这个服务健康吗" | **"为什么这条规则触发了，何时恢复"** |
| 典型用户 | 开发（review、上线后回看） | **oncall / SRE（被告警叫醒）** |

## Environment

| Env Var | Purpose |
|---|---|
| `PLATFORM_ENV` | `prod`/`production` → prod URL，else test URL（默认）|
| `INTERNAL_TOKEN` | **推荐配置**，bigeyes 的 Cas-User 鉴权头。**未配置时自动降级**：跳过 bigeyes API（Phase 1 + context-analyzer），仅靠飞书卡片正文 + logs/traces 完成诊断；告警画像节会标"⚠️ 历史 / 复发 / 并发数据不可用" |

```bash
export INTERNAL_TOKEN=your_cas_user_name
export PLATFORM_ENV=prod   # 通常告警都在生产
```

> **没有 token 怎么办**？去 [soul-claw 龙虾](https://soul-claw.soulapp-inc.cn) 申请 Cas-User，或直接复制飞书告警卡片正文 @ 龙虾机器人 —— skill 会用 [shared/scripts/feishu_card_parser.py](../shared/scripts/feishu_card_parser.py) 解析卡片，跳过 bigeyes 走降级路径。降级后能产出：告警上下文 / 触发窗口分析 / 链路与下游归因 / 观测限制 / 根因假设 / 行动清单 / 一句话结论。失去的是：告警画像里的"同规则 24h 频次 / 复发判定 / 同时刻并发"三项。

---

## 首次使用配置（推荐）

alarm-diagnosis 一次诊断会调用告警查询 + logs_client + traces_client 多次，默认每次都会弹 Allow。

**推荐：一键脚本**（幂等可重复执行）：

```bash
bash skills/setup-permissions.sh
```

**手动做法**：在项目根目录 `.claude/settings.local.json` 合并以下白名单：

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 skills/alarm-diagnosis/scripts/alarm_client.py *)",
      "Bash(python3 skills/alarm-diagnosis/scripts/logs_client.py *)",
      "Bash(python3 skills/alarm-diagnosis/scripts/traces_client.py *)",
      "Bash(PLATFORM_ENV=prod python3 skills/alarm-diagnosis/scripts/alarm_client.py *)",
      "Bash(PLATFORM_ENV=prod python3 skills/alarm-diagnosis/scripts/logs_client.py *)",
      "Bash(PLATFORM_ENV=prod python3 skills/alarm-diagnosis/scripts/traces_client.py *)"
    ]
  }
}
```

仅放行只读查询命令；`.claude/settings.local.json` 为个人本地配置，不进 git。已有文件请合并 `allow` 数组。

---

## ⚡ 并发执行硬性规则（性能关键）

**本 skill 是耗时敏感的**：告警诊断 Pipeline 有 15+ 个命令（Phase 1 告警详情 + Phase 3 触发窗分析 + Phase 4 规则上下文 + 关联告警），若串行执行每步 ~20s agent thinking loop，总耗时到 6~8 分钟。以下规则压到 2~3 分钟。

### 规则 1：独立命令必须同 message 并发

**每个 Phase 内部的命令彼此独立，必须在单条 assistant message 内通过多个 Bash tool call 并行发送**，禁止一条一条等结果。

| Phase | 必须同批并发的命令集合 |
|-------|---------------------|
| **Phase 1** 告警基本信息 | `alarm-event-detail` **+** `alarm-event-notify-records` **+** `alarm-event-escalation` **+** `alarm-event-logs` |
| **Phase 3** 触发窗分析（Application 类） | `logs aggregate exception.type` **+** `logs aggregate logger.name` **+** `logs search-logs ERROR` **+** `logs trend` **+** `traces list-errors` **+** `traces aggregate p99` **+** `traces long-op`（共 7 条）|
| **Phase 4** 上下文 | `alarm-rule-detail` **+** `alarm-events --rule-id` **+** `alarm-stats-active` |

**Phase 1 拿到 triggerTime + alarm-category + resource 后**，Phase 3 和 Phase 4 之间**无依赖**，可以**合并成一批 10 个 Bash 并发**发送。

### 规则 2：Application 类告警用 Subagent 分工（推荐）

对 `alarm-category=Application` 的告警，主 agent 在完成 Phase 1 + Phase 2 分支判定后，应**并发派发 2 个 subagent**：

| subagent | subagent_type | 职责 | 命令集合 |
|---------|---------------|------|---------|
| **window-analyzer** | `general-purpose` | Phase 3 触发窗错误 + 性能一把梭 | `logs aggregate` × 2 + `search-logs` + `trend` + `traces list-errors` + `traces aggregate p99` + `long-op` |
| **context-analyzer** | `general-purpose` | Phase 4 规则上下文 + 关联告警 | `alarm-rule-detail` + `alarm-events --rule-id` + `alarm-stats-active` |

主 agent：
1. Phase 1：**4 个告警 API 并发**拿详情 + 通知 + 升级 + 操作日志
2. Phase 2：解析 category/resource/triggerTime，决定分支
3. 单条 message 派发 2 个 subagent，附带 `service`、`start`、`end`、`rule_id`、`env` 参数
4. 收到 2 份 JSON 后合并成 Phase 5 报告

**window-analyzer prompt 模板**：
```
你是 window-analyzer，专门分析告警 triggerTime 窗口内的错误 + 性能数据。
服务：{service}
时间窗：{trigger - 30m} ~ {trigger + 30m}
环境：PLATFORM_ENV={env}

任务：单条 message 内并发执行以下 **13 个命令**（Bash tool call × 13，v3.0.3 加 4 个 trace 命令支撑性能 / 上游 / 长尾分析）：

**日志维度（5 条，所有 service 都能跑）**

1. logs_client.py aggregate --group-by exception.type --q "severity_text=ERROR AND service.name={service}"
2. logs_client.py aggregate --group-by logger.name --q "severity_text=ERROR AND service.name={service}"
3. logs_client.py search-logs --q "severity_text=ERROR AND service.name={service}" --limit 10
4. logs_client.py trend --service {service} --output /tmp/alarm-{event_id}-trend.png
5. logs_client.py aggregate --group-by host.id --q "severity_text=ERROR AND service.name={service}" --limit 50 — Pod 分布 log-fallback

**Trace 错误维度（2 条）**

6. traces_client.py list-errors --service {service} --limit 10 --order-by exceptionCount --order descending
7. traces_client.py long-op --service {service} — Top 慢操作 + P99

**Trace 性能维度（v3.0.3 新增 — 让响应正文「⏱️ 性能指标」节有数据）**

8. traces_client.py **overview** --service {service} — 总览（QPS / 错误率 / P99 时序），用于 vs 24h 基线
9. traces_client.py **dubbo-duration** --service {service} — Dubbo P50/P95/P99 时序；纯 HTTP 服务换 `http-duration`
10. traces_client.py **long-trace** --service {service} --limit 1 → 拿到长尾 trace_id 后 traces_client.py get-trace --trace-id <id> — 长尾样本完整调用链（飞书响应正文引用 trace_id 给 oncall 跳转 bigeyes UI）

**Trace 上游 / Pod 维度（v3.0.3 新增 — 让响应正文「📡 影响范围」+「📍 Pod 分布」节有数据）**

11. traces_client.py **dubbo-upstream** --service {service} — 上游应用列表（谁在调我，多少次）⭐ 影响范围核心
12. traces_client.py **dubbo-upstream-interfaces** --service {service} — 上游应用 × 接口细分（细化业务入口）
13. traces_client.py long-ip-distribution --service {service} — Pod 分布主路径

> ⚠️ **traces_client.py 实际可用子命令**：`overview` / `long-op` / `long-trace` / `long-ip-distribution` / `long-sql-table` / `dubbo-duration` / `dubbo-interfaces` / **`dubbo-upstream` / `dubbo-upstream-interfaces` / `dubbo-upstream-methods`** / `dubbo-downstream` / `dubbo-downstream-interfaces` / `dubbo-downstream-methods` / `http-duration` / `http-paths` / `db-duration` / `list-errors` / `count-errors` / `trace-services` / `get-trace`。**没有 `aggregate` 子命令**。

### 下游归因双轨（Trace 优先 → Log 兜底）

**Step A（主路径）**：先看命令 5 (`list-errors`) 返回的 trace 链路里有没有跨服务调用：
- 从 `traces_client.py trace-services --trace-id <top1 error trace>` 提取调用拓扑
- 如果 trace 拓扑明确指出下游 service.name → `downstream_attribution.source = "trace"`，直接用 trace 数据填 Top 下游

**Step B（兜底）**：以下任一条件成立，启用日志正则兜底：
- Step A 没拿到 trace（采样率丢 / 时间窗外 / trace 表无记录）
- 命令 3 (`search-logs`) 样本里 ≥ 30% 缺 `remote.application`（老 Dubbo SDK，trace 也大概率缺埋点）
- 跨服务但 trace 拓扑只有单服务（OTel 未接入下游）

执行：
```bash
# 把命令 3 的 search-logs JSON 输出喂给 shared parser
python3 ../shared/scripts/dubbo_log_parser.py --input /tmp/alarm-{event_id}-error-samples.json --mode all
```

`downstream_attribution.source = "log-fallback"`，并把 parser 返回的 `legacy_sdk_warning`（如果有）原文填入 `observability_limits`。

### 问题实例（中间件归因）

Step B 的 parser 同时返回 `problem_instance` 节（HBase/Redis/DB/MQ 具体实例）。当主异常类是中间件相关（`HBaseException` / `RedisCommandTimeout` / `DataAccessException` / `MQException` 等），**必填**报告的"问题实例"小节；否则可以为空。

### 量化 Pod 分布判定

命令 8/9 拿到 host/IP 分布后，调用 `dubbo_log_parser.pod_judgement(rows)` 得到固化 verdict：
- `single-pod-likely` (top1 ≥ 50%)
- `two-pod-likely` (top2 ≥ 70%)
- `few-pod-skew` (top1 ≥ 20% 或 top3 ≥ 50%)
- `multi-pod-service-wide` (其它)

**禁止主 agent 在报告里用自然语言重新解释 verdict** —— parser 输出什么就用什么，保持跨次诊断一致性。

返回 JSON:
```json
{
  "top_exceptions": [...],
  "top_loggers": [...],
  "error_samples": [{"ts":...,"body":...,"trace_id":...}],
  "trend_summary": "...",
  "p99_top_operations": [...],
  "long_ops": [...],
  "is_error_burst_at_trigger": bool,

  "performance_metrics": {
    "p50_ms": N | null,
    "p95_ms": N | null,
    "p99_ms": N | null,
    "p99_vs_24h_baseline_ratio": float | null,
    "is_fat_tail": bool,
    "top_slow_op": {"op": "...", "p99_ms": N, "count": N} | null,
    "long_trace_id": "..." | null,
    "long_trace_bigeyes_url": "..." | null,
    "source": "trace" | "card-only" | "none"
  },
  "upstream_apps": {
    "source": "trace" | "log-inferred" | "none",
    "top_upstream": [
      {"app": "...", "count": N, "share_pct": P, "inferred_business": "..."}
    ],
    "business_impact_summary": "<核心链路 / 边缘场景 / 影响 X% 流量>"
  },

  "downstream_attribution": {
    "source": "trace" | "log-fallback" | "none",
    "chain": "outer-app -> middle-app -> source-app",
    "top_downstream_apps": [{"app":"...","count":N,"pct":P}],
    "top_downstream_methods": [{"method":"...","count":N}],
    "legacy_sdk_ratio": 0.0
  },
  "problem_instance": {
    "type": "hbase|redis|db|mq|null",
    "host": "ip:port",
    "table_or_key_or_topic": "...",
    "signal": "callTimeout|CallQueueTooBigException|MOVED|deadlock|...",
    "evidence_log_id": "..."
  },
  "pod_distribution": {
    "verdict": "single-pod-likely|two-pod-likely|few-pod-skew|multi-pod-service-wide|unknown",
    "top1_pct": 0.0,
    "top2_pct": 0.0,
    "top3_pct": 0.0,
    "hot_ips": ["ip:port"],
    "source": "trace" | "log-fallback"
  },
  "observability_limits": [
    "trace sampling rate too low (only N% spans found)",
    "30% logs missing remote.application — old Dubbo SDK",
    "service.name mapping failed; using alarm card text only"
  ]
}
```

只返回 JSON，不要生成报告。`observability_limits` 是数组，没有限制就给 `[]`。
```

**context-analyzer prompt 模板**：
```
你是 context-analyzer，负责拉告警规则上下文 + 告警画像（历史频次 / 复发判定 / 同时刻并发）。
event_id: {event_id}
rule_id: {rule_id}
resource: {resource}
triggerTime: {trigger}
环境：PLATFORM_ENV={env}

任务：单条 message 内并发执行（Bash tool call × 5）：
1. bigeyes_admin_api_client.py alarm-rule-detail {rule_id}
2. bigeyes_admin_api_client.py alarm-events --rule-id {rule_id} --limit 20 — 同规则近 24h（看噪音 + 复发间隔）
3. bigeyes_admin_api_client.py alarm-events --resource {resource} --start "{trigger - 7d}" --end "{trigger}" — 同 resource 近 7d 全规则告警
4. bigeyes_admin_api_client.py alarm-stats-active --start "{trigger - 5m}" --end "{trigger + 5m}" — 同时刻并发
5. bigeyes_admin_api_client.py alarm-event-logs {event_id} — 操作日志，提取上次类似事件的 ack/处置（若 bigeyes 归档）

返回 JSON:
{
  "rule_expr": "...",
  "rule_threshold": "...",
  "rule_last_modified": "...",
  "alarm_profile": {
    "same_rule_24h_fire_count": N,
    "is_noisy_rule": bool,                              # > 50 次/24h 判 true
    "same_resource_7d_alarm_count": N,
    "same_resource_7d_trend": "rising|stable|falling",
    "last_fire_hours_ago": N | null,                   # null = 从未触发
    "is_first_occurrence": bool,
    "last_handle_record": {                             # 取自 alarm-event-logs，无归档时为 null
      "ack_by": "...",
      "action": "restart|rollback|config-change|false-positive|...",
      "outcome": "resolved|recurring|escalated"
    } | null,
    "correlated_firing_alarms": [
      {"event_id":..., "rule":..., "service":..., "category":...}
    ],
    "is_storm": bool                                    # 同时刻并发 >= 10 或含中间件类告警
  }
}

只返回 JSON。
```

> **alarm_profile 字段直接喂给 Phase 5 报告的"告警画像"节** —— 主 agent 不重新解释，原文塞进 4 个子条目（历史频次 / 错误时序 / 复发判定 / 同时刻并发）。错误时序由 window-analyzer 的 `trend_summary` 提供。

### 规则 3：非 Application 类直接短路

`alarm-category != Application` 时**禁止**跑 Phase 3/Phase 4 查询，直接进入信息卡片版报告。主 agent **只**做 Phase 1（4 个命令并发）+ 类别提示即可。这种情况下总耗时应 < 30s。

### 预期收益

| 模式 | 总耗时 | 说明 |
|------|-------|------|
| 完全串行（优化前） | 6~8 min | 15+ 命令 × 每步 ~20s thinking |
| 规则 1 单层并行 | **2.5~4 min** | 每 Phase 内部并发，主 agent 仍做所有 thinking |
| 规则 1+2 多 agent | **1.5~2.5 min** | 2 个 subagent 并发，主 agent 只做 merge |
| 非 Application 类（规则 3 短路） | **< 30s** | 只拿告警元信息 + 类别提示 |

---

## 诊断 Pipeline

### Phase 0: 输入分流（Triage）

主 agent **必须**先判断输入形态，决定走哪条路径。三种入口：

#### 路径 A：纯 EVT-ID（典型 CLI 调用）

用户给了 `EVT-XXXXXXXX` 或纯告警事件链接。**前提**：`INTERNAL_TOKEN` 已配置。

→ 直接进 Phase 1，跑完整 5 Phase pipeline。

#### 路径 B：飞书卡片正文粘贴（龙虾飞书机器人主场景）

用户 @ 龙虾机器人 + 粘贴/转发了飞书告警卡片正文。判定信号（任一命中）：
- 出现"告警规则"/"触发时间"/"阈值"等多个卡片字段标签
- 出现"@xxx"接收人 mention
- 出现飞书内链 `https://bigeyes.soulapp-inc.cn/...` 或 `https://applink.feishu.cn/...`
- 字符数 > 100 且包含中英文混排的结构化字段

**Step 1**：调 feishu_card_parser 抽结构化字段：
```bash
python3 ../shared/scripts/feishu_card_parser.py --format json <<<"<整段卡片正文>"
```

parser 自动处理：
- markdown 加粗 `**应用名称：**` 包裹的标签
- k8s deploy 路径后缀 `prod-xxx-k8s/(error.log)` → strip 为 `prod-xxx-k8s`
- bigeyes ERROR 告警专有字段（错误关键字 / 错误统计 / 错误分类Top3 / 错误内容 / IP分布 / 报警时间段）
- 从"错误分类Top3"第一条里识别 top_exception 类名
- 即使无 EVT-ID + 无规则名，只要 sample/top_errors/ip_dist 三选二命中也给 confidence ≥ 4

**Step 1.5（无 EVT-ID 自动 keyword 搜，v3.0.2 加自动降级重试，v3.0.4 加严"必须"）**：

⛔ **强制**：parser 输出 `event_id == null` 但拿到 `resource` 时，**禁止直接走路径 C**，必须先按以下**降级序列**反查 bigeyes 拿 event_id（每次 0 hit 自动剥一段重试，注意：`alarm-events` 接口**不接 --start/--end，时间窗自动取当前活跃 + 历史**）：

❌ **不允许跳过本步骤**。常见偷懒模式（v3.0.3 实测发现）：主 agent 看到无 EVT-ID 就直接走路径 C，绕过 Step 1.5 → 导致丢失告警画像数据 + 后续大量盲搜浪费时间。

```bash
# 降级序列（v3.0.2 新增 — 长 keyword 0 hit 自动剥前缀/后缀重试）：
#   1. <完整 resource>            → 例: prod-meta-service
#   2. strip env prefix          → 例: meta-service          ← 实测最容易命中
#   3. strip 复合后缀 (-k8s/-dubbo/-provider) → 例: meta
#   4. 取 resource 最核心 token   → 例: meta-service 的核心 "meta-service" 已是第 2 步
# 用 mapper candidates 输出的 list 顺序也可以指导降级
python3 scripts/bigeyes_admin_api_client.py --raw alarm-events --keyword "<resource>" --pageSize 10
# regex 解析 list 里的 id + eventNo + resourceName，匹配卡片 rule_name 的一条
```

- 命中且与卡片 rule_name / resourceName 吻合 → 拿到 event_id，回填后走路径 A
- 全部降级序列 0 命中 → 走路径 C（卡片正文已够分析），event_id 用占位 `cardonly-<YYYYMMDDHHMM>`

> ⚠️ **bigeyes alarm-events 返回 JSON 容错**：客户端必须用 `--raw` 模式，因为 `content` 字段（卡片正文）含未转义引号，`json.loads` 会报 `Unterminated string`。**主 agent 用 regex 抽取 list 里的字段**（id / eventNo / level / status / alertCount / firstAlertTime / lastAlertTime / resourceName），不要试图 json.loads 全部 body。

**Step 2（service.name 锁定 — v3.0.5 重构为"list-apps 事实优先"）**：

⛔ **v3.0.4 实测发现 bug**：旧 Step 2 用 `logs search-logs --q "service.name=X AND severity_text=ERROR"` 探测，告警时段服务无 ERROR 日志时（但 service 实际已接入 OTel）会被误判 miss → 错走路径 D。**真实 case：`prod-push-base-provider-k8s` → 第 2 候选 `push-base-provider` 是真实 OTel 名，但 ERROR-filtered probe 返 0 被放弃**。

**v3.0.5 修复**：先用 `list-apps --name <核心 token>` 拿 OTel 注册的真实应用名（事实判定，不依赖时段数据），命中即锁定；同时并发跑无 severity 过滤的 logs probe 作辅证。

```bash
# 2.1 先生成候选清单
CANDS=$(python3 ../shared/scripts/alarm_resource_mapper.py candidates "<resource>" --format lines)
# 示例（prod-push-base-provider-k8s）:
#   push-base-provider-k8s
#   push-base-provider     ← 真实 OTel 名（v3.0.5 能锁定）
#   push-base
#   soul-push-base-provider-k8s
#   ...

# 2.2 提取"核心 token"（去 prod-/-k8s/-dubbo/-provider 后的最小标识）
CORE=$(python3 ../shared/scripts/alarm_resource_mapper.py candidates "<resource>" --format lines | tail -2 | head -1)
# 上例 CORE = push-base
```

⛔ **强制并发**（v3.0.4 硬规则）：必须**单条 message 内**多 Bash tool call **同时**发以下查询：

```bash
# ✅ 优先权威（list-apps，事实判定，不依赖时段）
# Bash#1: traces_client.py list-apps --name "$CORE"
#         → 返回应用名列+实例名列；任一应用名出现在 $CANDS 即锁定

# ✅ 并发辅证（logs probe，看时段数据；v3.0.5 去掉 severity 过滤）
# Bash#2: logs_client.py search-logs --limit 1 --start "<trigger - 1m>" --end "<trigger + 1m>" --q "service.name=<候选1>"
# Bash#3: logs_client.py search-logs --limit 1 ... --q "service.name=<候选2>"
# Bash#4: logs_client.py search-logs --limit 1 ... --q "service.name=<候选3>"
# ...（N 个候选都发 N 条 probe；禁串行 for 循环；禁 severity_text=ERROR 过滤）
```

> ⚠️ **v3.0.5 关键变更**：probe **不带 `severity_text=ERROR`**，因为 service 是否接入 OTel 是事实判断，不依赖该时段是否有错误日志。任意 INFO/DEBUG 日志命中即证明 OTel 接入 OK。

**锁定优先级**（按可信度排序）：
1. **list-apps 命中**且应用名 ∈ candidates → **直接锁定该应用名**为 service.name（最权威）
2. list-apps 0 命中 + 任一 probe 返非空 → 锁定 probe 命中的候选
3. **全部 0 命中** → 走路径 D（OTel 未接入）

⛔ **禁止偷懒**（v3.0.5 实测发现）：
- ❌ 不要跑 1-3 候选 probe 看到 miss 就放弃，必须**并发跑完所有候选 + list-apps fuzzy**
- ❌ 不要用 `service.name=X AND severity_text=ERROR` 作 probe 条件
- ❌ 不要在 list-apps 命中的情况下还相信 probe miss 结果（list-apps 权威性高于 probe）

**Step 4**：把 parser 的 `service`、`trigger_time`、`level`、`top_exception`、`trace_id`、`ip_distribution`、`top_errors` 作为 Phase 3 (window-analyzer) subagent 的固定参数。

#### 路径 C：INTERNAL_TOKEN 缺失的降级路径

**触发条件**：环境变量 `INTERNAL_TOKEN` 未设置 / 已过期，或路径 B 显式落入此分支。

**降级行为**：
- ❌ 跳过 Phase 1 bigeyes API（alarm-event-detail / notify-records / escalation / logs）
- ❌ 跳过 context-analyzer subagent（无法查 alarm-rule-detail / alarm-events / alarm-stats-active）
- ✅ 仍跑 window-analyzer subagent（logs_client + traces_client 不需要 token）
- ✅ 主 agent 用 feishu_card_parser 的输出作为 Phase 1 替代

**降级模板：告警画像节填充**
```markdown
### 告警画像（横向 + 纵向 + 复发判定）

> ⚠️ 未配置 INTERNAL_TOKEN，bigeyes 告警上下文不可达，本节大部分维度退化。
> 完整画像请配置 INTERNAL_TOKEN（去 soul-claw 龙虾申请 Cas-User）后重跑。

**4.1 历史频次**: ⚠️ 不可用（需 bigeyes alarm-events --rule-id）
**4.2 错误时序**: <仍由 window-analyzer 的 trend_summary 提供，可填>
**4.3 复发判定**: ⚠️ 不可用（需 bigeyes alarm-event-logs）
**4.4 同时刻并发**: ⚠️ 不可用（需 bigeyes alarm-stats-active）
```

**降级模板：观测限制节追加**
```
- ⚠️ INTERNAL_TOKEN 缺失，告警事件历史 / 复发 / 同时刻并发数据降级；其它数据维度（错误 + 链路 + Pod 分布）完整
```

**何时建议用户配置 token**：
- 告警画像 ≥ 50% 缺失，且诊断结论的可靠性受影响时
- 用户问"这是不是噪音规则" / "之前是不是触发过"
- 提示文案：「检测到 INTERNAL_TOKEN 未配置，告警画像维度退化。如需完整诊断，请去 soul-claw 龙虾申请 Cas-User 后 `export INTERNAL_TOKEN=<你的 Cas-User>` 再重跑。」

#### 路径 D：OTel 未接入 / service.name 全部 miss

**触发条件**：Phase 0 Step 2 探测 mapper candidates 全部返空 **AND** Step 2.5 `list-apps --name <core_key>` 也返 0 个有效应用。

**降级行为**（v3.0.4 严格短路）：
- ⛔ **触发后立即跳到 Phase 4 + Phase 5**，**禁止任何额外 OTel 查询**（v3.0.3 实测主 agent 仍会试探搜索浪费 ~75s）
- ⛔ **禁止用业务关键词做 logs search**（如"装扮祈愿池"/"hasLiked"等）— OTel 没接入，logs 表里**根本没这个 service 的数据**，搜也是 0
- ⛔ **禁止用 Dubbo SO-TraceId 调 `traces get-trace`** — Dubbo traceId 不是 OTel 32-hex 格式，必然 miss（详见工具速查）；如要跨链路查日志用 `logs search-logs --q 'logback.mdc.SO-TraceId=<id>'`
- ⛔ **禁止"再多试几个候选"** — mapper candidates 全 miss + list-apps fuzzy 0 个 = 终局判定，再加候选只是浪费时间
- ❌ 跳过 window-analyzer subagent（OTel 没数据派下去也是 0 返回）
- ✅ context-analyzer 仍可跑（如 token 在），bigeyes 数据完整可用
- ✅ 主分析基于飞书卡片正文（`top_exception` / `top_errors` / `error_count_text` / `ip_distribution` / `scenarios` / `primary_scenario`）+ bigeyes notify-records 历史时序
- ✅ 如果 parser `scenarios.is_lock_failure_scenario=true`，调 `dubbo_log_parser.lock_failure_attribution()` 用卡片样本生成标准修复建议
- ✅ **可选**：如果错误样本指出明确的下游服务名（如 `MachineAuditProvider`），可以**只对该明确下游**跑一次 logs aggregate / list-errors 看下游是否有数据；但**禁止对告警应用本身再试探任何 OTel 查询**

**报告里的强制声明**：

```markdown
### 观测限制
- ⚠️ **OTel 未采集到该 service 的数据**。已探测候选: <候选清单>，全部返回 0 条样本。
  建议 owner 检查 OTel agent 是否注入、`service.name` 是否在 list-apps 中。
- 本次结论基于飞书告警卡片正文（错误统计 / Top 错误分类 / IP 分布）+ bigeyes 上下文，
  trace 维度 / Pod 分布固化判定不可用。
```

**Pod 分布退化为卡片字段**：

```markdown
### Pod 分布
- **Verdict**: 来自卡片 IP 分布字段（非 trace span 数据）
- 卡片列出 Top N IP + 占比；占比通常 < 10%（卡片只报告 Top 3）→ 通常判 multi-pod-service-wide
- 数据源: feishu-card `ip_distribution`（非量化 verdict）
```

### Phase 1: 拉告警基本信息（Gather）

> 路径 C 跳过本 Phase，直接用 feishu_card_parser 输出。

```bash
# 必跑 1：告警详情（含 alarm-category、resource、triggerTime、rule_id）
python3 scripts/bigeyes_admin_api_client.py alarm-event-detail <EVENT_ID>

# 必跑 2：告警通知记录（谁被通知了、有没有人响应）
python3 scripts/bigeyes_admin_api_client.py alarm-event-notify-records <EVENT_ID>

# 选跑：升级历史 / 操作日志
python3 scripts/bigeyes_admin_api_client.py alarm-event-escalation <EVENT_ID>
python3 scripts/bigeyes_admin_api_client.py alarm-event-logs <EVENT_ID>
```

**从详情中提取的关键字段**：

| 字段 | 用途 |
|------|------|
| `alarm-category` | 决定 Phase 2 的诊断路径 |
| `resource` | 资源名（如 `prod-pay-asset`），用于映射 service.name |
| `triggerTime` | 时间锚点，定义诊断窗口 |
| `rule_id` | 拉规则详情看阈值/PromQL |
| `level` (P0/P1/P2) | 决定输出报告紧迫度 |

### Phase 2: 按 alarm-category 分支决定诊断路径

```python
from alarm_resource_mapper import resource_to_service, is_diagnosable_category, category_hint

if is_diagnosable_category(category):     # v3.0.6: 大小写均接受 "Application" / "application"
    service = resource_to_service(resource)
    # → 走完整诊断链路（Phase 3 + 4）
else:
    print(category_hint(category))
    # → 输出"信息卡片报告"（仅 Phase 5），不强行查 logs/traces
```

#### 路径 A：Application 类（完整诊断）

> ⚡ **执行方式看本 SKILL.md 上方「并发执行硬性规则」**：下面的 5 个查询彼此独立，**必须在同一条 message 内多 Bash 并发**；中重任务建议改用 `window-analyzer` + `context-analyzer` 两个 subagent 并行派发（规则 2）。

```bash
# 资源名 strip 前缀得到 otel service.name
SERVICE=$(python3 ../shared/scripts/alarm_resource_mapper.py to-service "prod-pay-asset")
# SERVICE=pay-asset

# 时间窗：triggerTime ± 30min
START="<triggerTime - 30m>"
END="<triggerTime + 30m>"

# 拉异常聚合（按 exception.type）
python3 scripts/logs_client.py aggregate --start "$START" --end "$END" \
  --group-by "exception.type" \
  --q "severity_text=ERROR AND service.name=$SERVICE" --limit 10

# 拉 ERROR 日志样本（找 traceId）
python3 scripts/logs_client.py search-logs --start "$START" --end "$END" \
  --q "severity_text=ERROR AND service.name=$SERVICE" --limit 10

# 错误趋势（看告警时刻是不是错误突增）
python3 scripts/logs_client.py trend --start "$START" --end "$END" \
  --service "$SERVICE"

# Trace 侧异常聚合
python3 scripts/traces_client.py list-errors --start "$START" --end "$END" \
  --service "$SERVICE" --limit 10 --order-by exceptionCount --order descending

# 如告警跟性能/超时相关，补查 P99（用 long-op + dubbo-duration，非 aggregate）
python3 scripts/traces_client.py long-op --service "$SERVICE" --start "$START" --end "$END"
python3 scripts/traces_client.py dubbo-duration --service "$SERVICE" --start "$START" --end "$END"
# 纯 HTTP 服务用：
# python3 scripts/traces_client.py http-duration --service "$SERVICE" ...
```

> ⚠️ **bigeyes alarm-event-detail JSON 解析容错**：bigeyes 返回的 JSON 中 `content` 字段可能含未转义字符（告警卡片正文里的引号 / 换行），导致 `json.loads` 报 `Unterminated string`。主 agent 检测到 stderr 含 `JSONDecodeError` 时，**必须**自动重试 `--raw` 模式，再用正则提取关键字段（`event_id` / `triggerTime` / `ruleId` / `category` / `resource`）。**不要**在第一次 JSON 失败就放弃 Phase 1。

**规则匹配建议**（根据规则名/告警内容判断该多查什么）：

| 规则关键词 | 重点查什么 |
|------------|-----------|
| `JVMFullGC` / `OOM` / `GC` | service 错误日志 + 内存相关 metric（后续指标 skill）|
| `超时` / `timeout` / `latency` | P99/P95 延迟 + 长尾分析 + 下游 trace |
| `error rate` / `错误率` | exception.type 分布 + traceId 样本 |
| `日志` 类（Log-based 但 category 仍是 Application） | 直接拉规则关键字日志 |

#### 路径 B：非 Application 类（信息卡片，不深度查）

直接调用：
```bash
python3 ../shared/scripts/alarm_resource_mapper.py check-category <CATEGORY>
```

把 `category_hint` 的提示放进报告，**不**强行拉 logs/traces。常见非 Application 类别：

| 类别 | 资源举例 | 处理 |
|------|---------|------|
| `application`（小写）| 历史遗留 | 不诊断，提示用户切到 `Application` |
| `PromQL` | 自定义表达式 | 仅展示告警基本信息 |
| `NginxDomain` | 域名 | 仅展示，引导查网关日志 |
| `KafkaTopic` / `Redis` / `Rds` | 中间件实例 | 仅展示，待后续指标 skill |
| `GroupEcs` / `ecs` | 主机/机器组 | 仅展示，待后续主机 skill |
| `ModelApplication` | AI 模型 | 仅展示 |

### Phase 3: 拉规则上下文（Rule Context）

```bash
# 规则详情（看阈值、表达式、最近改动）
python3 scripts/bigeyes_admin_api_client.py alarm-rule-detail <RULE_ID>

# 同规则最近的告警（看是不是噪音规则、频次、是否新规则）
python3 scripts/bigeyes_admin_api_client.py alarm-events --rule-id <RULE_ID> --limit 20
```

### Phase 4: 关联告警（Correlated Events）

同一时刻有没有其他告警在 firing？常见场景：上游中间件挂了 → 多个 Application 告警同时炸。

```bash
# 拉 triggerTime ± 5min 内所有活跃告警
python3 scripts/bigeyes_admin_api_client.py alarm-stats-active \
  --start "<trigger - 5m>" --end "<trigger + 5m>"
```

### Phase 5: 输出报告（Report）

**输出顺序优化（2026-04-25 用户反馈）— 强制流程**：

```
Phase 2 subagent 返回 JSON（rules-fetcher + telemetry-puller 等）
        ↓
Phase 5 主 agent：
  ① 先在响应窗口完整流式输出 markdown 分析（用户立刻可读）
       ├─ ## 核心结论 (标题 + 加粗 emoji 报告路径占位 + TL;DR 表)
       ├─ ## Phase 2 数据快照 (告警上下文 + 错误/性能 + 同时刻关联告警)
       ├─ ## 因果链分析 / 根因假设
       └─ ## 行动清单
  ② 输出完整分析后，最后调用 Write 落盘 docs/diagnosis/*.md + *-orchestration.md
  ③ 响应末尾追加一行 ✅ 落盘确认
```

**核心原则**:
- 响应窗口里的分析就是**完整可读的诊断**——用户不打开文档也能 100% 理解结论
- 文档是"持久化副本 + 编排数据"，给后续复盘 / 二次分发 / skill 迭代用
- 非主链路的辅助查询（如 trend 图导出、关联告警批量拉取）可用 `run_in_background: true` subagent 异步跑
- 主链路（rules-fetcher / telemetry-puller）必须同步并发等齐，**不要 background**

**必须落盘 + 必须 PUT 到内网 WebDAV**。命名规范（v3.0.2 起，对齐 alarm-diagnosis 目录）：

**本地缓存路径**（调试 / 复跑用，会自动创建目录）：
```
~/alarm-diagnosis-reports/<YYYY-MM-DD>/<EVT-ID>-<rule-slug>.md
~/alarm-diagnosis-reports/<YYYY-MM-DD>/<EVT-ID>-<rule-slug>-orchestration.md
```

**WebDAV 远端路径**（**强制 PUT**，分发给团队 / oncall）：
```
https://dl.soulapp-inc.cn/dav/alarm-diagnosis/<YYYY-MM-DD>/<EVT-ID>-<rule-slug>.md
https://dl.soulapp-inc.cn/dav/alarm-diagnosis/<YYYY-MM-DD>/<EVT-ID>-<rule-slug>-orchestration.md
```

例：
- 本地: `~/alarm-diagnosis-reports/2026-05-19/EVT-20260408-97574511-meta-service-log.md`
- 远端: `https://dl.soulapp-inc.cn/dav/alarm-diagnosis/2026-05-19/EVT-20260408-97574511-meta-service-log.md`

**slug 规则**：取规则名转小写，非字母数字替换为 `-`，去掉 `prod-` / `日志告警` 等冗余词
（如 `prod-chat-biz-dubbo-k8s 日志告警` → `chat-biz-dubbo-log`；`JVMFullGC` → `jvm-fullgc`；`prod-meta-service 日志告警` → `meta-service-log`）。

**EVT-ID 来源**：优先用 bigeyes 返回的 `eventNo`（形如 `EVT-20260408-97574511`），无 token / 反查不到时退化为 `cardonly-<YYYYMMDDHHMM>` 占位符。

**Phase 5 落盘 + 上传流程（每次诊断必跑，伪代码）**：

```bash
DATE=$(date +%Y-%m-%d)
EVT="<EVT-ID 或 cardonly-... 占位>"
SLUG="<rule-slug>"
LOCAL_DIR="$HOME/alarm-diagnosis-reports/$DATE"
WEBDAV_BASE="https://dl.soulapp-inc.cn/dav/alarm-diagnosis/$DATE"

mkdir -p "$LOCAL_DIR"

# 1. Write 诊断报告 + 编排报告 到本地
Write "$LOCAL_DIR/$EVT-$SLUG.md"               <诊断报告 markdown>
Write "$LOCAL_DIR/$EVT-$SLUG-orchestration.md" <编排报告 markdown>

# 2. PUT 到 WebDAV（必须并发；目录会自动创建；匿名 PUT 无需鉴权）
curl -sS -X PUT --upload-file "$LOCAL_DIR/$EVT-$SLUG.md" \
  "$WEBDAV_BASE/$EVT-$SLUG.md" -w "HTTP %{http_code}\n"
curl -sS -X PUT --upload-file "$LOCAL_DIR/$EVT-$SLUG-orchestration.md" \
  "$WEBDAV_BASE/$EVT-$SLUG-orchestration.md" -w "HTTP %{http_code}\n"

# 3. 响应正文中的报告路径**必须**指向 WebDAV URL（不是本地路径），方便 oncall 点开浏览器看
```

**预期 HTTP 返回**：首次上传 `201 Created`，覆盖更新 `204 No Content`。其他码报错。

**禁止**：
- ❌ 跳过 WebDAV 上传（响应正文里的 `📄 ...` 路径必须 markdown 链接到 `https://dl.soulapp-inc.cn/dav/alarm-diagnosis/...`）
- ❌ 本地路径写到 `docs/diagnosis/` 这种项目相对目录（飞书龙虾场景无项目根，会失败）
- ❌ 在响应里把 WebDAV URL 写成纯文本（必须 markdown link 让 oncall 一键点开）

#### 报告模板（Application 类完整版）

```markdown
# 告警根因报告: <规则名> on <资源>

> 生成时间: 2026-04-18 HH:MM CST
> 诊断入口: alarm-diagnosis skill
> 告警事件: EVT-XXXXXXXX
> 告警时间: 2026-04-18 HH:MM CST

## 1. 告警基本信息
- **事件编号**: EVT-XXXXXXXX
- **规则名**: JVMFullGC
- **告警类别**: Application
- **资源**: prod-pay-asset
- **映射 service.name**: pay-asset
- **级别**: P2
- **状态**: 处理中 / 未处理 / 已解决
- **告警次数**: N
- **责任人 / 接收人**: <负责人> / <接收人>

## 2. 规则上下文
- **PromQL/表达式**: ...
- **阈值**: ...
- **规则创建/修改时间**: ...
- **同规则近 24h 触发次数**: N（判断是否噪音）

## 3. 触发窗口分析（trigger ± 30min）
- 错误总量: N
- 错误类型分布:
  | 异常类型 | 数量 |
  |---------|------|
  | ... | ... |
- P99 延迟变化: ...
- Top 慢操作: ...
- 错误样本（含 trace_id）: 5 条

## 4. 告警画像（历史 + 趋势 + 复发判定）

**4.1 历史频次**
- 同规则近 24h 触发: N 次 → {首次发生 / 偶发 / 高频复发 / 噪音规则}（>50 次/24h 判为噪音）
- 同 resource 近 7d 告警条数: N（趋势: 上升 / 平稳 / 下降）

**4.2 错误时序**
- trend.png 形态: {平稳 / 阶梯上涨 / 突增 at HH:MM / 缓降中}
- 当次告警处于: 上升期 / 峰顶 / 回落期

**4.3 复发判定**
- 同规则上次触发: N 小时前 / 从未触发过
- 上次处理记录（取自 `alarm-event-logs`）: <ack 人> / <处理动作> / <是否标 false-positive>

**4.4 同时刻并发**
- triggerTime ± 5min 内 firing 告警条数: N
- 关联告警列表:
  - EVT-XXX (规则: ...) — 可能相关
  - ...
- ⚠️ 并发 ≥ 10 或同时刻有中间件类告警 firing → 雪崩信号，根因可能在共享下游

## 5. 链路与下游归因

**5.1 调用链层级（outer → middle → source）** · 数据源: trace / log-fallback / none

| 层级 | 应用 | 角色 | 关键证据 |
|---|---|---|---|
| 外层 | {service} | 报警主体 | exception=..., count=N |
| 中间层 | {middle-app} | 传播路径 | trace span / remote.application |
| 最终源 | {source-app} | 根因层 | timeout=Nms / 错误码 |

> log-fallback 且 legacy_sdk_ratio ≥ 30 时加："⚠️ 老 Dubbo SDK 缺 remote.application，N% 样本无法归因下游"

**5.2 问题实例（仅中间件类异常时填）**

| 类型 | 实例 host:port | 表/Key/Topic | 信号 | 证据 log_id |
|---|---|---|---|---|
| HBase / Redis / DB / MQ | ... | ... | callTimeout / MOVED / deadlock | ... |

> 非中间件类异常写"—（本次主异常非中间件类）"，不要省略本节

**5.3 Pod 分布** · Verdict: `<parser 固化标签>`
- Top1 / Top2 / Top3 占比: N% / N% / N%
- 热点 IP（仅 single/two-pod 时填）: `ip:port`
- 数据源: trace `long-ip-distribution` / log-fallback `host.id`

## 6. 观测限制
- 列出 `observability_limits` 数组里的每一条
- 无降级时写: ✅ trace + log + bigeyes 数据完整，无观测降级

## 7. 根因假设
**假设 X**: <根据数据推断的原因>
- 证据 1: ...
- 证据 2: ...
- 证据 3: ...

## 8. 修复建议
1. **短期**：...
2. **中期**：...
3. **长期**：...

## 9. 通知 & 响应
- 通知到: <谁> via <飞书/电话>
- 响应时间: ...
- 升级路径: ...

## 10. 附录: 复现命令
```bash
export PLATFORM_ENV=prod INTERNAL_TOKEN=...
python3 scripts/bigeyes_admin_api_client.py alarm-event-detail <EVT-ID>
python3 scripts/bigeyes_admin_api_client.py alarm-events --rule-id <RULE_ID> --limit 20
python3 scripts/bigeyes_admin_api_client.py alarm-stats-active --start "..." --end "..."
python3 scripts/logs_client.py search-logs --start "..." --end "..." --q "..."
python3 scripts/logs_client.py trend --service <SVC> --start "..." --end "..."
# 日志归因兜底（trace 缺数据时启用）
python3 ../shared/scripts/dubbo_log_parser.py --input <samples.json> --mode all
```

## 11. 一句话结论（IM 转发友好）
**不是 `{应用名}` `{单 Pod / 自身代码}` 问题，而是 `{下游应用 / 中间件实例 / 线程池}` 异常导致。**
**错误集中在 `{接口/方法/操作}`，表现为 `{超时 / 拒绝 / 队列满 / 错误码}`，问题节点指向 `{IP / Pod / 实例}`。**
**应用侧 `{Pod 分布均匀 / 集中在少数 Pod}`，因此判断为 `{依赖侧问题 / 少数 Pod 饱和 / 应用线程池满}`。**
```

#### 报告模板（非 Application 类信息卡片版）

```markdown
# 告警信息卡片: <规则名> on <资源>

> 生成时间: 2026-04-18 HH:MM CST
> 诊断入口: alarm-diagnosis skill
> 告警事件: EVT-XXXXXXXX

## 1. 告警基本信息
（同上）

## 2. 为什么没有自动根因分析
**告警类别**: Redis（举例）
**原因**: <category_hint() 的输出>

## 3. 规则上下文
- **表达式**: ...
- **阈值**: ...

## 4. 通知 & 响应
（同上）

## 5. 建议下一步
- 请使用 <对应工具/面板/未来的指标 skill> 进行下一步排查
```

### 严重性自动定级矩阵（强制 — 2026-04-26）

主 agent 在 Phase 5 输出"核心结论"前，**必须按下表给整个告警诊断打 P0 / P1 / P2 / P3 标签**，并在 TL;DR 表头标注。

| 维度 | P0 | P1 | P2 | P3 |
|---|---|---|---|---|
| 告警同规则 24h 触发次数 | ≥ 100 | 30~100 | 10~30 | < 10 |
| 触发窗口 ±30min 关联 ERROR 量 | ≥ 1000 | 100~1000 | 10~100 | < 10 |
| 同时刻并发告警条数 | ≥ 10（雪崩信号） | 5~10 | 2~5 | < 2 |
| 是否影响支付 / 资金 / 登录链路 | 命中即 P0 | — | — | — |
| 告警规则原始级别 | P0 → 直接采用 | P1 → 采用 | — | — |

**取所有命中维度的最高等级**作为最终等级。

**等级与响应动作映射**：

| 等级 | emoji | 建议响应 |
|---|---|---|
| 🔴 P0 | 🔴 | 立即拉群 / oncall 必须响应 / 加显式提醒 |
| 🔴 P1 | 🔴 | 当天处理 / 关键 trace_id 入 TL;DR |
| 🟠 P2 | 🟠 | 本周处理 |
| 🟡 P3 | 🟡 | 信息确认 / 噪音排查 |

**Why**：固化等级 = 一致性 = 避免漏报 P0。此规则与 apm-diagnosis 共用，保证两类诊断输出语言一致。

### 响应正文结构（强制 — v3.0.3 重构为 "结论先行 + 13 节固化"）

> **设计哲学**: 飞书群 @ 龙虾场景下，oncall 看到的响应正文必须**结论先行 + 简洁分段 + emoji 锚点 + 表格/代码块/树状可视化**。详细 11 段诊断挪到 .md 报告（WebDAV）。借鉴 error-log-analysis 飞书机器人响应风格 + 加入 alarm-diagnosis 特色能力（告警趋势 / Pod 量化判定 / 上游影响范围 / P95 P99 性能指标）。

**13 节固化顺序（不允许重排 / 合并 / 删节）**：

```markdown
🔍 **<规则名>** · 🔴 P1 · <告警时间 YYYY-MM-DD HH:MM:SS>

## 🎯 一句话结论

**<不是 X 单 Pod / 自身代码问题，而是 Y 异常导致，根因在 Z>**（一句话 ≤ 100 字，加粗）

📄 [完整报告](https://dl.soulapp-inc.cn/dav/alarm-diagnosis/<DATE>/<EVT-ID>-<slug>.md) ｜ 📋 [编排详情](https://dl.soulapp-inc.cn/dav/alarm-diagnosis/<DATE>/<EVT-ID>-<slug>-orchestration.md)

---

## 📋 基本信息

- **应用**: `<resource>` (error.log)
- **OTel service.name**: `<service>`
- **租户 / Owner**: `<bizTenant>` / `<owner>`（<department>）
- **告警时间**: <triggerTime>
- **报警窗口**: <start> ~ <end>（<minutes> 分钟）
- **总报错量**: <count> 次（阈值 <threshold>）
- **错误关键字**: `<error_keyword>`
- **事件号**: <EVT-ID> · **<firing/acked/resolved>** · alertCount=<N>

## 📈 告警趋势

- **首发**: <date>（<days> 天前）· 累计 <N> 次 · <噪音判定: 首发/低频偶发/高频复发/噪音规则>
- **本次时序**: <突增 at HH:MM / 阶梯 / 缓降>，告警处于 **<上升期 / 峰顶 / 回落期>**
- **复发判定**: 距今 <hrs> 上次触发 · **<N ack / N mute / N resolve>**（取自 alarm-event-logs）
- **同时刻并发**: ±5min <N> 条相关告警 · <雪崩信号判定>

> 数据来源: bigeyes alarm-event-detail + alarm-event-logs + alarm-events --keyword + alarm-stats-active（skill 特色，error-log-analysis 拿不到）

## 📊 错误分类 Top3

| 排名 | 错误类型 | 次数 | 占比 |
|---|---|---|---|
| 1 | `<exception 或 logger 模式>` | N | X% |
| 2 | `...` | N | X% |
| 3 | `...` | N | X% |

> 数据源: 卡片 Top3（5min 窗）+ logs aggregate exception.type（30min 窗）补充验证

## 📍 Pod 分布

**Verdict**: `<verdict>`（parser 固化标签，禁止重新解释）

- Top1: `<ip>` (X%)
- Top2: `<ip>` (X%)
- Top3: `<ip>` (X%)
- 总 host: <N> 个 pod 报错
- 数据源: trace `long-ip-distribution` / log-fallback `host.id` / card `ip_distribution`

> ⚠️ 场景修正（按 `primary_scenario`）:
> - `mq_consumer` / `lock_failure` → few-pod-skew = MQ rebalance 倾斜，非 Pod 故障，**摘除 Pod 无效**
> - `dubbo_rpc` + multi-pod → 共享下游问题（不是该 Pod 自身）
> - `db` / `redis` + few-pod-skew → 连接池配置


## ⏱️ 性能指标（P95 / P99）

- **P50 / P95 / P99**（30min 窗，trace `dubbo-duration` / `overview`）: <Nms / Nms / Nms>
- **vs 24h 基线**: P99 <↑X倍 / 持平 / ↓Y倍> → **<胖尾 / 正常 / 偏快>**（P99/P95 > 5× 判胖尾）
- **Top 慢操作**: `<method>` P99=<Nms> · count=<N>（来自 `long-op`）
- **长尾样本 trace_id**: `<traceId>` [→ bigeyes trace 查看](<bigeyes-trace-url>)

> ⚠️ trace 维度全空时（list-errors=null / long-op=[] / dubbo-duration=[]）: "<service> 未接入 OTel trace 采样，性能维度不可用，建议 P2 行动里加'<service> 接入 OTel trace 采样'"

## 📡 影响范围（上游应用）

**Top 上游调用方**（30min 内，trace `dubbo-upstream` / `dubbo-upstream-interfaces`）:

| 上游应用 | 调用次数 | 业务入口推断 |
|---|---|---|
| `<upstream-1>` | N | <业务场景> |
| `<upstream-2>` | N | <业务场景> |
| ... | ... | ... |

**业务影响**: <核心链路 / 边缘场景 / 影响 X% 在线流量 / 跨集群>

> ⚠️ trace 维度空时降级：基于卡片 logger / 业务接口名推断业务场景（无量化上游应用列表），并标"trace 未接入，无法量化"


## 🔎 根因推断

**核心问题**: <一句话>

**关键样例**:

```
<3-5 行核心 stacktrace 或日志样本>
```

**调用链路推断**:

```
[上游] <upstream-1> / <upstream-2>（来自 dubbo-upstream / 业务推断）
  → <告警应用>  [N pod 均匀 / 少数 Pod 偏热]
    → [Dubbo/HTTP/DB/Redis/MQ] <下游接口>
      → <下游应用> (集群: <cluster> · owner: <owner>)
        → [...] <下下游 / 真因点> ❌ <错误描述>
```

## 🧐 分析结论

1. **主因 (X%)**: <现象 + 量化证据>
2. **次因 (Y%)**: <现象 + 量化证据>
3. **业务影响**: <核心链路 / 影响哪些上游业务 / 扩散风险>

## 🛠️ 建议排查方向

1. **🔴 P1** <立即动作> — `<owner>`
2. **🔴 P1** <立即动作> — `<owner>`
3. **🟠 P2** <本周动作> — `<owner>`
4. **🟠 P2** <本周动作> — `<owner>`
5. **🟡 P3** <治理 / skill 反馈>

## ⚠️ 紧急程度

**🔴 P0/P1 / 🟠 P2 / 🟡 P3** — <一段话理由：错误量 + 业务影响 + 扩散风险 + 是否影响支付/登录/资金>

---

> 🤖 自动诊断 by **alarm-diagnosis v3.0.3** · 数据源: bigeyes + OTel logs + OTel traces · 完整 11 段分析见顶部 📄 报告链接
```

**硬性规则**（2026-04-25 重写）：

1. 第一级标题必须是 `## 核心结论`（不允许改名 / 合并 / 省略）
2. 紧贴标题的**第一行**是诊断报告路径，必须满足：
   - 用 `**...**` 加粗
   - 前缀带 📄 emoji 作为视觉锚点
   - 用 markdown 链接格式 `[path](path)` 让 CLI 可点击
3. 报告路径上面不允许插任何过渡句
4. 路径**指向的文件可以是即将生成的**——主 agent 先输出整个分析正文，最后再 Write 落盘也允许（推荐）
5. **响应正文 13 节固化结构**（v3.0.3 重构 — 严格不许重排 / 合并 / 删节）：
   ```
   1. 标题行 (规则名 · 级别 · 告警时间)
   2. ## 🎯 一句话结论 + 📄 报告链接（紧贴顶部，结论先行）
   3. ## 📋 基本信息（含 service.name / 事件号 / firing 状态）
   4. ## 📈 告警趋势（首发 / 时序 / 复发判定 / 同时刻并发 — 4 行 bullet）
   5. ## 📊 错误分类 Top3（表格 4 列: 排名/类型/次数/占比）
   6. ## 📍 Pod 分布（verdict + 场景修正） — 紧贴错误分类，看错在哪些 pod
   7. ## ⏱️ 性能指标（P95/P99）— trace 维度（空时降级标 ⚠️）
   8. ## 📡 影响范围（上游应用）— trace dubbo-upstream（空时降级）
   9. ## 🔎 根因推断（核心问题 + 关键样例代码块 + 调用链 ASCII 树）
   10. ## 🧐 分析结论（主因 X% / 次因 Y% / 业务影响）
   11. ## 🛠️ 建议排查方向（带 🔴🟠🟡 优先级 emoji）
   12. ## ⚠️ 紧急程度（独立一节）
   13. 🤖 自动诊断水印（末尾一行 blockquote）
   ```
   - 5.1 **一句话结论**紧贴顶部第 2 节，**📄 完整报告 + 📋 编排详情链接放紧贴一句话结论之下**（不要末尾再重复链接）
   - 5.2 **告警趋势**节用 4 行 bullet 写完（首发 / 时序 / 复发 / 并发），不要再展开 H4 子节
   - 5.3 **错误分类 Top3** 表格列严格 4 列: 排名 / 错误类型 / 次数 / 占比；30min 聚合数据放表格下方一行 blockquote
   - 5.4 **性能指标**节 trace 维度全空时**仍保留标题**，内容标 ⚠️ "未接入 OTel trace 采样，性能维度不可用"
   - 5.5 **影响范围**节 trace 空时**仍保留标题**，降级用 logger / 业务接口名推断"业务影响"，并标注"trace 未接入，无法量化"
   - 5.6 **Pod 分布**节 verdict 必须直接引用 parser 输出的固化标签（single-pod-likely / two-pod-likely / few-pod-skew / multi-pod-service-wide / unknown），**禁止主 agent 自然语言重新解释**；按 `primary_scenario` 加场景修正脚注
   - 5.7 **根因推断**的调用链路推断**必须用 ASCII 树**（4 空格缩进 + `→` 箭头 + `❌` 标真因层），不要用表格
   - 5.8 **建议排查方向**每条带 🔴 P1 / 🟠 P2 / 🟡 P3 emoji + 负责方（用反引号标 owner 名）
   - 5.9 **紧急程度**独立成节，一段话理由（错误量 + 业务影响 + 扩散风险 + 是否影响支付/登录/资金）
   - 5.10 **水印**用 `> 🤖 自动诊断 by **alarm-diagnosis v<VERSION>** · 数据源: bigeyes + OTel logs + OTel traces · 完整 11 段分析见顶部 📄 报告链接`
6. Write 落盘 + curl PUT WebDAV 放在**所有分析输出之后**调用（用户阅读时上传已完成）
7. **报告链接只放顶部一处**（紧贴一句话结论），底部不再重复（v3.0.2 改为顶部一处，结论先行）
8. 绝不允许把报告路径放在响应末尾或仅以纯文本形式出现
9. **响应正文禁止包含以下"元数据"段落**（仅 .md / orchestration.md 写）：
   - ❌ 横向对比表（与历史告警 / 同规则其他事件对比）→ 仅写在诊断报告 .md
   - ❌ SKILL 反向优化建议 / 流程改进提案 → 仅写在 orchestration .md
   - ❌ 诊断元数据附录（subagent 耗时表、token 数）→ 仅写在 orchestration .md
   - ❌ "否定假设" / "观测限制" 详细列举 → 仅写在 .md（响应里如有重要降级在"性能指标 / 影响范围 / Pod 分布"节用 ⚠️ 一行带过）
   理由：oncall 被叫醒后只关心当次告警的根因 + 行动，元数据段无增量价值，复盘时翻 orchestration / .md 即可

**Why**：
- oncall / owner 被告警叫醒后，需要在响应窗口里就看到完整分析，不应该被强迫翻 docs/
- 文档是持久化副本 + 编排数据，给后续复盘用，不是给本次紧急响应读的
- 旧流程"先 Write 再输出短摘要"——用户在落盘的几十秒里没东西可看，体感慢
- 新流程"先输出完整分析、最后 Write 落盘"——感知耗时大幅降低

此偏好为用户 2026-04-20 + 2026-04-25 两次反馈合并，apm-diagnosis / alarm-diagnosis 共用。

---

### Phase 5.1: 输出编排流程报告（必做）

除诊断报告外，**必须额外产出一份编排流程报告**，记录本次 pipeline 的 Phase 执行清单、参数、中间产物、失败点。这是 skill 可复现性与迭代的一手数据。

**命名规范**：与诊断报告同目录同日期，后缀 `-orchestration.md`：

```
docs/diagnosis/YYYY-MM-DD-alarm-<EVT-ID>-<rule-slug>-orchestration.md
```

例：`docs/diagnosis/2026-04-18-alarm-EVT-94895962-jvm-fullgc-orchestration.md`

**编排报告模板**：

```markdown
# 告警诊断编排流程: <规则名> on <资源>

> 对应诊断报告: [YYYY-MM-DD-alarm-<EVT-ID>-<rule-slug>.md](YYYY-MM-DD-alarm-<EVT-ID>-<rule-slug>.md)
> 告警事件: EVT-XXXXXXXX
> 诊断时间窗: trigger ± 30min (YYYY-MM-DD HH:MM ~ HH:MM CST)
> 目的: 记录 pipeline 执行轨迹，为 skill 迭代提供一手数据

## Phase 概览

\`\`\`
Phase 1: 拉告警基本信息
  ├─ alarm-event-detail
  ├─ alarm-event-notify-records
  └─ alarm-event-logs
       ↓
Phase 2: 按 alarm-category 分支
  ├─ [Application] → Phase 3 + 4 完整诊断
  └─ [非 Application] → 直接到 Phase 5 信息卡片
       ↓
Phase 3: 触发窗口并行分析（仅 Application）
  ├─ logs aggregate (exception.type / logger.name)
  ├─ logs search-logs (ERROR 样本)
  ├─ logs trend
  ├─ traces list-errors
  └─ traces aggregate (p99 / long-op)
       ↓
Phase 4: 规则上下文 + 关联告警
  ├─ alarm-rule-detail
  ├─ alarm-events --rule-id（同规则近 24h）
  └─ alarm-stats-active（同时刻 firing 告警）
       ↓
Phase 5: 输出诊断报告 + 编排报告
\`\`\`

## 每步详细记录

| # | Phase | 子命令 | 参数要点 | 返回 | 结论 |
|---|---|---|---|---|---|
| 1 | P1 | `bigeyes_admin_api_client.py alarm-event-detail` | `EVT-XXXXXXXX` | category=Application, resource=prod-pay-asset, level=P2 | 进入 Application 分支 |
| 2 | P1 | `alarm-event-notify-records` | 同上 | 通知 <谁> via 飞书，响应 N 分钟 | 写入报告 §7 |
| 3 | P2 | `alarm_resource_mapper.py to-service` | prod-pay-asset | service.name=pay-asset | 给 logs/traces 查询用 |
| 4 | P3 | `logs aggregate` | ±30min, `service.name=X AND severity_text=ERROR`, group-by exception.type | ... | Top 异常类 |
| 5 | P3 | `logs search-logs` | 同窗口 ERROR 样本，limit=10 | ... | 取代表性 trace_id |
| 6 | P3 | `traces list-errors` | 同窗口 | N 组 exception | trace 侧错误分布 |
| ... | ... | ... | ... | ... | ... |

## 命令清单（可复现）

\`\`\`bash
export PLATFORM_ENV=prod INTERNAL_TOKEN=<your_cas_user>
export EVT=EVT-XXXXXXXX
export SVC=pay-asset
export START="2026-04-18 13:00:00"
export END="2026-04-18 14:00:00"

# Phase 1
python3 scripts/bigeyes_admin_api_client.py alarm-event-detail $EVT
python3 scripts/bigeyes_admin_api_client.py alarm-event-notify-records $EVT
python3 scripts/bigeyes_admin_api_client.py alarm-event-logs $EVT

# Phase 2
python3 scripts/alarm_resource_mapper.py to-service prod-pay-asset
python3 scripts/alarm_resource_mapper.py check-category Application

# Phase 3 (并行)
python3 scripts/logs_client.py aggregate --start "$START" --end "$END" \\
  --q "service.name=$SVC AND severity_text=ERROR" --group-by "exception.type"
python3 scripts/logs_client.py search-logs --start "$START" --end "$END" \\
  --q "service.name=$SVC AND severity_text=ERROR" --limit 10
python3 scripts/traces_client.py list-errors --service $SVC --start "$START" --end "$END"
python3 scripts/traces_client.py long-op --service $SVC --start "$START" --end "$END"

# Phase 4
python3 scripts/bigeyes_admin_api_client.py alarm-rule-detail <RULE_ID>
python3 scripts/bigeyes_admin_api_client.py alarm-events --rule-id <RULE_ID>
python3 scripts/bigeyes_admin_api_client.py alarm-stats-active --start "$START" --end "$END"
\`\`\`

## 编排评估

### 顺畅的地方
- <记录并行执行是否无阻塞、数据是否在 ± 30min 窗口内都命中等>

### 失败/降级点
| 失败项 | 影响 | 处置 |
|---|---|---|
| <例：dubbo-interfaces 500> | 无法按接口切 P99 | 改用 long-op count 替代 |

### 耗时分布（粗估）
- Phase 1: ~Xs
- Phase 3: ~Xs（并行）
- Phase 4: ~Xs
- **总查询耗时 ~Xs**

### Skill 迭代建议
- <例：Phase 3 对 Application 类告警，建议默认并行跑长尾分析（对齐 apm-diagnosis Phase 2.5）>
- <例：资源名 → service.name 映射失败时应提示用户而不是静默返空>
```

**触发规则**：
- **每次 alarm-diagnosis 调用都必须产出编排报告**（与诊断报告一对一）
- 非 Application 类（信息卡片版）也要产出**极简编排报告**（仅 Phase 1 + Phase 2 分支决策）
- 编排报告与诊断报告放同目录，用户可对照查阅

---

## 工具速查

| 步骤 | 用哪个工具 | 命令 |
|------|-----------|------|
| **飞书卡片正文 → 结构化字段** | shared/feishu_card_parser.py | `feishu_card_parser.py --format json` |
| **日志归因兜底（trace 缺数据时）** | shared/dubbo_log_parser.py | `dubbo_log_parser.py --mode all` |
| 告警详情 | bigeyes_admin_api_client.py | `alarm-event-detail <EVT_ID>` |
| 告警通知记录 | bigeyes_admin_api_client.py | `alarm-event-notify-records <EVT_ID>` |
| 告警操作日志（取上次处理记录） | bigeyes_admin_api_client.py | `alarm-event-logs <EVT_ID>` |
| 升级路径 | bigeyes_admin_api_client.py | `alarm-event-escalation <EVT_ID>` |
| 规则详情 | bigeyes_admin_api_client.py | `alarm-rule-detail <RULE_ID>` |
| 同规则告警史（24h 频次 / 复发） | bigeyes_admin_api_client.py | `alarm-events --rule-id <ID>` |
| 同 resource 7d 告警史 | bigeyes_admin_api_client.py | `alarm-events --resource <name> --start ... --end ...` |
| 同时刻活跃告警（雪崩信号） | bigeyes_admin_api_client.py | `alarm-stats-active --start ... --end ...` |
| 资源 → service（单值） | alarm_resource_mapper.py | `to-service prod-pay-asset` → `pay-asset` |
| **资源 → service 多候选探测**（推荐） | alarm_resource_mapper.py | `candidates prod-chat-biz-dubbo-k8s --format lines` → 2~3 个高精度候选（v3.0.7 简化） |
| 类别能否诊断 | alarm_resource_mapper.py | `check-category Application` |

> **service.name 探测的标准流程**：先 `mapper candidates <resource>` 拿 2~3 个高精度候选（v3.0.7 简化策略，不再暴力 strip 业务名后缀），**单 message 多 Bash 并发** 跑 `logs_client.py search-logs --q "service.name=$SVC" --limit 1`（v3.0.4 强制并发，禁串行 for 循环），任一命中 → 锁定。全部 miss → 走 Phase 0 路径 D（OTel 未接入降级）。**禁止**只用 `to-service` 拿单值就直接 fire 7 个并发查询（90% 概率全空）。

> ⚠️ **Dubbo traceId 不要用 `traces get-trace`**（v3.0.4 新增）：飞书卡片里的 SO-TraceId 是 Dubbo 编码格式（如 `f17791804963150481L2pod2VhcW5...` base64 / `TE:b1779039036806ac10e86345391:TE` / `41779117281679ac1008ca37641` 非 32hex），OTel trace 表存的是标准 32-hex traceId，**调 `get-trace` 必然 miss**。
>
> ✅ 正确查询路径（Dubbo traceId 跨链路查日志）：
> ```bash
> python3 ~/.claude/skills/otel-logs-query/scripts/logs_client.py search-logs \\
>   --start "<trigger - 5m>" --end "<trigger + 5m>" \\
>   --q "logback.mdc.SO-TraceId=<dubbo-trace-id>" --limit 50
> ```
> 因为业务用 logback MDC 透传 Dubbo traceId 到日志，logs 表里能命中跨服务样本。
>
> parser 输出的 `trace_id_format` 字段会标 `"otel"` / `"dubbo"` / `"unknown"`，主 agent 拿 dubbo / unknown 时**禁止调 `get-trace`**。
| 错误聚合（按异常） | logs_client.py | `aggregate --group-by exception.type` |
| 错误样本 | logs_client.py | `search-logs --q "severity_text=ERROR"` |
| 错误趋势图 | logs_client.py | `trend --service <SVC>` |
| 链路异常 | traces_client.py | `list-errors --service <SVC>` |
| 慢操作 | traces_client.py | `aggregate --function p99 --group-by name` |

---

## 脚本路径

本 skill 有两种分发形态：

### A. 独立安装（推荐）— `alarm-diagnosis-skill.zip`

```
alarm-diagnosis/scripts/bigeyes_admin_api_client.py   # 告警
alarm-diagnosis/scripts/logs_client.py                # 日志
alarm-diagnosis/scripts/traces_client.py              # 链路
shared/scripts/otel_client_common.py                  # otel 公共工具
shared/scripts/alarm_resource_mapper.py               # 资源映射
```

执行：
```bash
cd ~/.claude/skills/alarm-diagnosis
python3 scripts/bigeyes_admin_api_client.py alarm-event-detail <EVT_ID>
python3 ../shared/scripts/alarm_resource_mapper.py to-service prod-pay-asset
```

### B. 同仓协作（monorepo）

```
skills/soul-bigeyes/scripts/bigeyes_admin_api_client.py
skills/otel-logs-query/scripts/logs_client.py
skills/otel-traces-query/scripts/traces_client.py
skills/shared/scripts/alarm_resource_mapper.py
skills/shared/scripts/otel_client_common.py
```

---

## 防护规则

- 时间窗：告警诊断默认 trigger ± 30min；最大不超过 ± 2h
- `INTERNAL_TOKEN` 推荐配置；未设置时走 Phase 0 路径 C 降级（跳过 bigeyes API，告警画像节大部分维度退化为"⚠️ 不可用"，但其它维度照常输出）
- 非 Application 类**禁止**强行拉 logs/traces（浪费且无效）
- 报告必须落盘到 `docs/diagnosis/`，文件名严格按命名规范
- 查询前必须告知用户当前环境（test/prod），避免误读告警

---

## 注意事项

1. **告警时间是锚点**：所有 logs/traces 查询都围绕 `triggerTime ± 30min` 进行，不要用 "1h ago" 这种相对时间
2. **资源名先 strip 再用**：`prod-pay-asset` ≠ otel `service.name`，必须经 `alarm_resource_mapper`
3. **关联告警很重要**：单条告警可能是连锁反应，看同时刻其他告警能避免误判根因
4. **规则上下文不能省**：阈值、PromQL、最近改动是判断"是真问题还是噪音规则"的关键
5. **不强行下钻**：非 Application 类直接给信息卡片，把球踢给后续的指标 skill / 主机 skill

---

## 参考文档

- [references/alarm-orchestration.md](references/alarm-orchestration.md) — 告警诊断的查询编排套路：5 阶段 pipeline + 类别分支 + 与 apm-diagnosis 的边界划分
- [LOBSTER_ROLLOUT.md](LOBSTER_ROLLOUT.md) — 龙虾市场推广 + 安装 + 飞书机器人对接 + FAQ

---

## Version History

> 版本规则：重大结构 / 行为变更 → 升大版本（v1 → v2）；增量字段 / bug 修复 / 文案优化 → 升小版本（v1.0 → v1.1）。

### v3.0.8（当前版本 — -dubbo 段特殊处理，覆盖 chat-biz 类特例）

修复来源：2026-05-20 用户实测 5 个 case，发现 v3.0.7 mapper 简化后 4/5 命中，但 `prod-chat-biz-dubbo-k8s` 这种 OTel 注册时去掉 `-dubbo` 段的特例无法锁定（list-apps `--name "chat-biz-dubbo"` 也 0 命中，因为 OTel 真名 `chat-biz` 不包含子串 "chat-biz-dubbo"）。

**v3.0.8 设计原则**：**仅对 `-dubbo` 段做特殊处理**，其它业务后缀（`-provider` / `-consumer` / `-server`）保持不动。基于实证 — Soul 内部命名规则中只有 `-dubbo` 段在 OTel 注册时常被去掉作为服务统一名。

- **🟢 mapper 加 -dubbo 段额外候选生成**: 若主候选含 `dubbo` 段，额外生成"去 dubbo"候选
  - `prod-chat-biz-dubbo-k8s` → 候选 `[chat-biz-dubbo, chat-biz-dubbo-k8s, chat-biz, chat-biz-k8s, prod-...]`（含 v3.0.8 新增的 chat-biz）
  - `prod-user-provider-k8s` → 候选不变（不含 dubbo 段）
- **🟢 5/5 实测全部锁定真实 OTel 名**：
  | resource | 锁定 service.name |
  |---|---|
  | `prod-soul-commercial-activity` | `soul-commercial-activity` |
  | `commercial-business-provider` | `commercial-business-provider` |
  | `prod-commercial-medal-provider-k8s` | `commercial-medal-provider` |
  | **`prod-chat-biz-dubbo-k8s`** | **`chat-biz`**（v3.0.8 新覆盖） |
  | `prod-user-provider-k8s` | `user-provider` |

### v3.0.7（mapper 候选回归保守，避免误命中无关服务）

修复来源：2026-05-20 用户反馈 v3.0.5 / v3.0.6 mapper 暴力穷举候选（progressive tail-token strip）导致：
- `user-provider` 被 strip 到 `user` → 可能误命中无关 user 服务
- 加 `soul-` 前缀变体（如 `soul-user-provider`）→ 多数情况无意义浪费 probe
- 候选 7+ 个 → 主 agent 探测时间长 + 误判风险

**v3.0.7 简化策略**：mapper 只做 2 个确定性转换 — 去环境前缀（prod-/pre-/test-/gray-）+ 去固定集群后缀（-k8s/-bj/-sh/-dt/-aliyun/-ack）。**不 strip 业务名任何部分**（包括 -dubbo / -provider / -consumer / -server），业务名所有部分都是 service.name 合法组成。

- **🟠 移除 progressive_tail_strip + soul- 前缀变体生成**: 候选数从 7+ 降到 2~3，每个都是高精度候选
- **🟠 业务后缀保留**: `prod-user-provider` → `user-provider`（不再生成 `user`）；`prod-chat-biz-dubbo-k8s` → `chat-biz-dubbo`（不再生成 `chat-biz`）
- **🟢 chat-biz 等特例靠 list-apps fuzzy 兜底**: OTel 实际注册名跟 deployment 名不一致的特殊情况由 SKILL.md Step 2 的 `list-apps --name <候选>` fuzzy 命中相邻名（子串匹配秒命中），不依赖 mapper 暴力穷举

候选示例：
| resource | 旧 v3.0.6 候选 | 新 v3.0.7 候选 |
|---|---|---|
| `prod-user-provider-k8s` | 7 个（含 `user` / `soul-user` 等垃圾） | **3 个**（`user-provider` / `user-provider-k8s` / 原始）|
| `prod-push-base-provider-k8s` | 7 个 | **3 个**（`push-base-provider` 第一） |
| `prod-chat-biz-dubbo-k8s` | 7 个（含 `chat-biz`） | **3 个**（`chat-biz-dubbo` 第一，chat-biz 特例靠 list-apps 兜底） |

### v3.0.6（application 小写 case-insensitive 修复）

修复来源：2026-05-20 用户实测 `prod-user-provider-k8s` 告警（EVT-20260408-76768978），发现 `alarmCategory="application"` 小写被 `is_diagnosable_category()` 严格匹配踢到信息卡片分支，**根本没机会走到 Phase 0 Step 2 探测 service.name** → 实际 `user-provider` 早在 OTel 注册，v3.0.5 也无法发挥（因为没进 Phase 3）。

- **🔴 `alarm_resource_mapper.is_diagnosable_category()` 改为 case-insensitive**: `(category or "").strip().lower() in {"application"}`，`Application` / `application` / `APPLICATION` 均通过
- **🔴 `category_hint()` 删除 "application 小写" 的踢出 hint**: 既然现在可诊断，不该再提示"切换到大写"
- **🟠 SKILL.md Phase 2 路径 A 加 v3.0.6 修复说明**: 提醒主 agent 大小写不再敏感

### v3.0.5（list-apps 事实优先 service.name 锁定）

修复来源：2026-05-20 用户实测 `prod-push-base-provider-k8s` 告警，发现真实 OTel 名 `push-base-provider` 就在第 2 候选里，但 v3.0.4 probe 用 `severity_text=ERROR` 严格过滤 + 主 agent 跑 3 个就放弃 + Step 2.5 fuzzy 兜底未触发 → 错走路径 D。

- **🔴 Step 2 重构为 "list-apps 事实优先"**: 用 `list-apps --name <核心 token>` 拿 OTel 注册的真实应用名（**事实判定，不依赖时段数据**），命中即锁定；不再依赖 logs probe 作为唯一判定
- **🔴 probe 去掉 `severity_text=ERROR` 过滤**: 服务是否接入 OTel 是事实判断，不依赖该时段是否有错误日志；任意 INFO/DEBUG 日志命中即证明 OTel 接入 OK
- **🔴 强化"必须并发 probe 全部候选"硬规则**: 实测 v3.0.4 主 agent 跑 3 个候选就放弃，未并发完所有候选 → SKILL.md 加 ⛔ 禁止偷懒条款
- **🟠 锁定优先级明确**: list-apps 命中 > probe 命中 > 全部 0（走路径 D）；list-apps 权威性高于 probe（命中名 ∈ candidates 即直接锁定）
- **🟠 旧 Step 2.5 fuzzy 兜底融入 Step 2**: 不再分两步（先 probe 再兜底），而是一开始就同时跑 list-apps + probe 并发，避免"先全 miss 才想起来 fuzzy"的延迟

### v3.0.4（龙虾真实执行 timing 反馈优化）

修复来源：2026-05-19 龙虾真实执行 alarm-diagnosis 时 timing 数据揭示 4 个执行偏差（总浪费 ~120s/次）。

- **🔴 Phase 0 Step 2 强制并发 probe**: 明确"单 message 多 Bash 并发"硬规则，禁串行 for 循环。实测节省 ~23s/次
- **🔴 路径 D 严格短路**: 触发后**禁止任何额外 OTel 查询**（包括业务关键词 logs search / 试探搜索 / 再加候选）。实测节省 ~75s/次
- **🔴 Step 1.5 加严"必须"**: 无 EVT-ID 时必须先 keyword 反查 bigeyes，禁止直接走路径 C 偷懒
- **🟠 Dubbo SO-TraceId 识别**: feishu_card_parser 新增 `is_dubbo_trace_id()` + `classify_trace_id()` 函数，输出 `trace_id_format` (`otel` / `dubbo` / `unknown`) + `so_trace_ids` 字段。识别格式：base64 编码（`f17791...base64==`）、`TE:hex:TE` 包裹、非 32-hex 长 hex
- **🟠 Dubbo traceId 正确查询路径**: SKILL.md 工具速查明确 — Dubbo traceId **禁调 `traces get-trace`**（必然 miss），应该用 `logs search-logs --q "logback.mdc.SO-TraceId=<id>"`（业务通过 logback MDC 透传 Dubbo traceId）

### v3.0.3（响应正文重构 + skill 全维度数据发挥）

修复来源：2026-05-19 用户拿 `prod-user-provider-k8s` 实测 + 反馈"响应应该简洁但结论先行 + 借鉴 error-log-analysis 风格 + 我们 skill 的告警中心 / OTel trace 优势没发挥出来"。

**核心变更：响应正文从 5 段重学术结构 → 13 节固化"结论先行"飞书友好结构**

- **响应正文 13 节固化**: 标题 → 🎯 一句话结论 → 📋 基本信息 → 📈 告警趋势 → 📊 错误分类 Top3 → 📍 Pod 分布 → ⏱️ 性能指标 → 📡 影响范围 → 🔎 根因推断 → 🧐 分析结论 → 🛠️ 建议排查方向 → ⚠️ 紧急程度 → 🤖 水印（Pod 分布紧贴错误分类）
- **一句话结论紧贴顶部**（之前在末尾），📄 完整报告 + 📋 编排详情链接紧跟一句话结论之下，**底部不再重复链接**
- **⏱️ 性能指标节（v3.0.3 新增）**: 利用 OTel trace 的 P50/P95/P99 + vs 24h 基线 + Top 慢操作 + 长尾 trace_id（之前完全没用上 trace 性能维度）
- **📡 影响范围节（v3.0.3 新增）**: 利用 trace `dubbo-upstream` / `dubbo-upstream-interfaces` 量化 Top 上游应用 + 业务入口推断（解决 "user-provider 报错谁受影响？" 的核心问题）
- **window-analyzer 命令 9 → 13**: 加 `overview` / `long-trace` / `dubbo-upstream` / `dubbo-upstream-interfaces` 4 个 trace 命令
- **subagent JSON spec 加字段**: `performance_metrics`（含 p50/p95/p99、vs baseline、top_slow_op、long_trace_id）+ `upstream_apps`（含 source、top_upstream、business_impact_summary）
- **调用链路推断改用 ASCII 树**（之前是表格 5 列）：4 空格缩进 + `→` 箭头 + `❌` 标真因层；树顶层加上游应用（来自 dubbo-upstream）
- **错误分类 Top3 用表格**（4 列固定: 排名/类型/次数/占比），下方一行 blockquote 给 30min 聚合补充
- **告警趋势节用 4 行 bullet**（首发 / 时序 / 复发 / 并发）— 之前是 H4 子节展开太啰嗦
- **建议排查方向**带 🔴 P1 / 🟠 P2 / 🟡 P3 emoji + 反引号标 owner 名
- **末尾水印**: `🤖 自动诊断 by alarm-diagnosis v<version>` + 数据源说明，让飞书群知道这是机器人输出
- **响应正文禁止段落扩充**: 否定假设 / 详细观测限制 / Phase 2 数据快照（之前 5 段重型结构）→ 全挪到 .md 报告，响应只保留量化数据 + 结论 + 行动

### v3.0.2（meta-service 告警实测后优化）

修复来源：2026-05-19 用户拿 `prod-meta-service` 分布式锁告警实测，暴露 5 个新优化点。

- **报告产物自动 PUT WebDAV**: Phase 5 落盘流程加入 `curl -X PUT https://dl.soulapp-inc.cn/dav/alarm-diagnosis/<DATE>/<EVT-ID>-<slug>.md`，本地缓存路径同步改成 `~/alarm-diagnosis-reports/<DATE>/`；响应正文 `📄` emoji 报告链接**指向 WebDAV URL**（不再是本地路径），oncall 一键点开浏览器看
- **`alarm-events --keyword` 自动降级**: Step 1.5 实现长 keyword 0 hit 时自动按 mapper candidates 顺序逐个重试，避免本次 `prod-meta-service` 命不中 + 用户手动改 `meta-service` 才中的尴尬
- **`feishu_card_parser` @-mention 严过滤**: `RE_AT_MENTIONS` 加 `(?<![\w])` 边界 + `_is_real_mention()` 函数排除 hex hash（修复 v3.0.1 把 `LockOption@aab320a` 当 receiver 抽出来的 bug）
- **`feishu_card_parser` 场景识别字段**: 新增 `scenarios` + `primary_scenario` 输出（`lock_failure` / `mq_consumer` / `dubbo_rpc` / `db` / `redis`），让主 agent 按场景定制 Pod 解读和修复建议
- **`dubbo_log_parser.lock_failure_attribution()`**: 自动识别 `Failed to obtain the distributed lock` 模式，提取 key 前缀 + TTL + holder UUID 数量，输出标准修复建议（finally unlock / 幂等去重 / TTL 缩短）
- **路径 D 跳冗余查询**: list-apps fuzzy 也 0 个时**直接跳过 Phase 3 所有 OTel 命令**，不再发 5+ 个空查询，节省 ~10s
- **RocketMQ 场景 Pod 分布解读修正**: `primary_scenario in {mq_consumer, lock_failure}` 时，主 agent 必须注释 "few-pod-skew 是 MQ rebalance 分配不均所致，非 Pod 故障，摘除热点 Pod 无效"
- **bigeyes JSON 容错明示**: SKILL.md Step 1.5 / Phase 1 都明确写出"必须 --raw + regex 抽字段"，不再让主 agent 试 json.loads 全部 body

### v3.0.1（2026-05-18 chat-biz 告警实测后的修复）

修复来源：2026-05-18 用户拿 `prod-chat-biz-dubbo-k8s` 日志告警实测，暴露 3 个真实问题。

- **mapper progressive tail-strip 算法**: `alarm_resource_mapper candidates` 引入"逐段从右 strip 识别 token"算法（k8s / bj / sh / dubbo / provider / consumer / server / api / gateway 等），覆盖复合后缀场景。`prod-chat-biz-dubbo-k8s` 现在第 3 候选就是 `chat-biz`（真实 OTel service.name），不再漏出。
- **Phase 0 Step 2.5 fuzzy 兜底**: candidates 全 miss 时不再立即走路径 D，先用 `traces_client.py list-apps --name <core_key>` 做一次模糊救场；只有 fuzzy 也 0 个应用才进路径 D
- **logger_attribution 新增**: `dubbo_log_parser` 增加按 Java logger.name 集中度反推下游应用的能力（如 `com.soul.photon.govern.AbInvoker` 84% 集中 → 下游 `photon`），自动识别框架 logger（org.apache / spring / dubbo / alibaba）避免误判
- **bigeyes alarm-events 参数纠正**: 用 `--pageSize`（非 `--page-size`），keyword 反查 event_id 正确触发
- **诊断报告 LOBSTER 实测验证**: 30 min 跑通真实案例（chat-biz → photon listConfigByGovern timeout），证明 5 节报告 + Phase 0 路径 B + 量化 pod verdict 在生产场景可用

### v3.0.0

- **5 节 Phase 2 数据快照结构**：告警上下文 / 触发窗口分析 / **告警画像**（含历史频次 / 错误时序 / 复发判定 / 同时刻并发）/ **链路与下游归因**（含调用链层级 / 问题实例 / Pod 分布）/ 观测限制
- **Trace 优先 / 日志兜底**的双轨下游归因，老 Dubbo SDK 自动检测（`legacy_sdk_ratio`）+ 准确度警示
- **量化 Pod 分布固化标签**：`single-pod-likely` / `two-pod-likely` / `few-pod-skew` / `multi-pod-service-wide`，禁止主 agent 自然语言重新解释
- **Phase 0 输入分流**：4 条路径（A: EVT-ID / B: 飞书卡片 / C: INTERNAL_TOKEN 缺失降级 / D: OTel 未接入降级）
- **飞书卡片正文解析**：`feishu_card_parser.py` 抽 17 个字段，支持 markdown 加粗标签、k8s deploy 路径后缀、bigeyes ERROR 卡片专有字段（错误关键字 / 错误统计 / 错误分类Top3 / 错误内容 / IP分布 / 报警时间段）
- **service.name 多候选探测**：`alarm_resource_mapper candidates` 输出 5 个候选，逐个 probe OTel，全 miss 走路径 D
- **bigeyes JSON 容错**：alarm-event-detail 解析失败时自动 fallback `--raw` 模式
- **IM 友好一句话结论**：三句二元式（"不是 X 是 Y 集中在 Z"）独立成节出现在响应末尾
- **subagent 并发**：window-analyzer + context-analyzer 双 agent，预期 2~3 分钟出齐报告
- **共享 Dubbo 堆栈正则归因**：`dubbo_log_parser.py`（service / method / remote.application / providers / endpoint）+ HBase/Redis/DB/MQ 中间件实例归因
- **打包形态**：bigeyes + logs + traces + shared 单 zip 自包含，无第三方 Python 依赖
