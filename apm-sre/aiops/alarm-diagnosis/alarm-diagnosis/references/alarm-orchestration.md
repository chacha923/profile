# 查询编排参考：告警事件诊断（Alarm Root Cause）

本文档记录 **告警事件驱动诊断**（用户给一个告警 ID 或粘贴告警卡片）时的推荐查询编排套路。

适用场景：
- "告警 #EVT-94895962 帮我排查"
- "JVMFullGC 告警 为什么触发"
- "粘贴一段飞书告警卡片 + 这个告警怎么回事"

---

## 与 apm-diagnosis 的边界

| 维度 | apm-diagnosis | **alarm-diagnosis** |
|------|--------------|----------------------|
| 入口 | 服务名 / traceId | **告警事件 ID / 告警卡片** |
| 方向 | Outside-in：宏观 → 微观 | **Inside-out：症状 → 反推** |
| 时间锚点 | 宽窗口（1h~1d） | **trigger ± 30min（精窗口）** |
| 关注维度 | 错误率、长尾、性能、容量 | **告警规则、阈值、关联事件、通知响应** |
| 典型用户 | 开发 review | **oncall 凌晨被叫醒** |

**互不替代**：apm 答"健不健康"，alarm 答"为什么炸了"。

---

## 5 阶段 Pipeline

```
┌─────────────────────────────────┐
│ 用户输入: 告警 ID / 告警卡片      │
└──────────┬──────────────────────┘
           │ INTERNAL_TOKEN + PLATFORM_ENV
           ▼
┌─────────────────────────────────┐
│ Phase 1: 拉告警基本信息（必跑）   │
│   alarm-event-detail            │
│   alarm-event-notify-records    │
└──────────┬──────────────────────┘
           │ 提取 alarm-category / resource / triggerTime
           ▼
┌─────────────────────────────────┐
│ Phase 2: 按 category 分支       │
│   if Application:                │
│     resource → service.name      │
│     → 进入 Phase 3a (深度诊断)   │
│   else:                          │
│     → 进入 Phase 3b (信息卡片)   │
└──────────┬──────────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
┌──────────┐  ┌──────────────────┐
│ Phase 3a │  │ Phase 3b         │
│ logs/    │  │ 仅展示告警上下文，│
│ traces   │  │ 给出 category    │
│ (并行)   │  │ hint，不查 trace │
└──────┬───┘  └─────────┬────────┘
       │                │
       └─────┬──────────┘
             ▼
┌─────────────────────────────────┐
│ Phase 4: 规则上下文 + 关联告警   │
│   alarm-rule-detail             │
│   alarm-events --rule-id        │
│   alarm-stats-active (附近时段) │
└──────────┬──────────────────────┘
           ▼
┌─────────────────────────────────┐
│ Phase 5: 输出报告（必落盘）      │
│   docs/diagnosis/YYYY-MM-DD-    │
│     alarm-<EVT-ID>-<slug>.md    │
└─────────────────────────────────┘
```

---

## Phase 1: 告警基本信息（串行，必跑）

| # | 命令 | 用途 |
|---|------|------|
| 1.1 | `bigeyes / alarm-event-detail <EVT_ID>` | 拿全字段：category、resource、triggerTime、ruleId、level、status |
| 1.2 | `bigeyes / alarm-event-notify-records <EVT_ID>` | 谁被通知，是否响应 |
| 1.3 | (选) `bigeyes / alarm-event-escalation` | 升级历史 |
| 1.4 | (选) `bigeyes / alarm-event-logs` | 操作日志 |

**1.1 先跑**，从结果里拿 `alarm-category` 决定 Phase 2 走哪条分支。
1.2/1.3/1.4 可以并行。

---

## Phase 2: 类别分支决策

```python
# 用 shared/scripts/alarm_resource_mapper.py 判断
from alarm_resource_mapper import is_diagnosable_category, resource_to_service, category_hint

if is_diagnosable_category(category):  # 当前只有 "Application"
    service = resource_to_service(resource)  # prod-pay-asset → pay-asset
    # 进入 Phase 3a
else:
    # 进入 Phase 3b，输出 category_hint(category) 提示
    pass
```

| 类别 | 路径 | 备注 |
|------|------|------|
| **Application** | 3a 完整诊断 | 唯一 P0 支持的类别 |
| application（小写）| 3b 信息卡片 | 历史遗留 |
| PromQL | 3b 信息卡片 | 后续支持，需解析表达式 |
| NginxDomain | 3b 信息卡片 | 域名维度，超出 otel 范围 |
| KafkaTopic / Redis / Rds | 3b 信息卡片 | 等指标 skill |
| GroupEcs / ecs | 3b 信息卡片 | 等主机 skill |
| ModelApplication | 3b 信息卡片 | 特殊场景 |

---

## Phase 3a: Application 深度诊断（并行）

时间窗：`START = triggerTime - 30min`，`END = triggerTime + 30min`。

| # | 命令 | 用途 | 并行组 |
|---|------|------|--------|
| 3a.1 | `logs / aggregate --group-by exception.type --q "severity_text=ERROR AND service.name=$SVC"` | 异常类型分布 | A |
| 3a.2 | `logs / search-logs --q "severity_text=ERROR AND service.name=$SVC" --limit 10` | ERROR 样本（拿 traceId）| A |
| 3a.3 | `logs / trend --service $SVC --start $START --end $END` | 错误趋势图（看告警时刻是不是突增）| A |
| 3a.4 | `traces / list-errors --service $SVC` | trace 侧异常聚合 | B |
| 3a.5 | `traces / aggregate --group-by name --function p99 --q "serviceName=$SVC"` | P99 延迟（如告警涉及性能）| B |

A 组（logs）和 B 组（traces）相互独立，可全部并行。

### 按规则名追加查询（heuristic）

| 规则名/告警内容含 | 额外查询 |
|------------------|---------|
| `JVMFullGC` / `OOM` / `内存` | logs 关键字 `OutOfMemory` / `Full GC`；后续指标 skill 看 JVM heap |
| `超时` / `timeout` / `延迟` / `latency` | `traces / aggregate --function p99` 必跑；考虑长尾分析 |
| `error rate` / `错误率` | `logs / aggregate --group-by exception.type` 必跑 + traceId 样本 |
| 日志关键字告警 | `logs / search-logs --q "body contains <关键字>"` 直接查 |

### 抓 traceId 做深度溯源

如果在 ERROR 样本里看到 traceId，**强烈建议**接着调用 apm-diagnosis 的 trace lookup 能力（同 zip 内已 bundle 了 traces_client）：

```bash
python3 scripts/traces_client.py get-trace --trace-id <ID>
python3 scripts/logs_client.py trace-logs --trace-id <ID> --padding 5
```

---

## Phase 3b: 非 Application 信息卡片

不查 logs/traces，只展示：
- 告警基本信息（来自 Phase 1）
- `category_hint(category)` 输出的指引
- 规则详情（Phase 4 仍跑）
- 通知记录（Phase 1.2 已拿）

避免浪费查询资源在不适用的维度上。

---

## Phase 4: 规则上下文 + 关联告警（并行）

| # | 命令 | 用途 |
|---|------|------|
| 4.1 | `bigeyes / alarm-rule-detail <RULE_ID>` | 规则表达式、阈值、最近改动 |
| 4.2 | `bigeyes / alarm-events --rule-id <RULE_ID> --limit 20` | 同规则近期触发频次（判断噪音）|
| 4.3 | `bigeyes / alarm-stats-active --start <trigger-5m> --end <trigger+5m>` | 同时刻活跃告警（连锁反应识别）|

Phase 3 和 Phase 4 互相独立，**可整体并行**。

---

## Phase 5: 报告落盘

### 命名规范

```
docs/diagnosis/YYYY-MM-DD-alarm-<EVT-ID>-<rule-slug>.md
```

例：
- `docs/diagnosis/2026-04-18-alarm-EVT-94895962-jvm-fullgc.md`
- `docs/diagnosis/2026-04-18-alarm-EVT-12345678-error-rate.md`

**slug 规则**：规则名 → 小写 → 非字母数字替换为 `-` → 连续 `-` 合并为一个。
`JVMFullGC` → `jvmfullgc`（如分词更好则 `jvm-fullgc`，由 AI 判断）。

### 报告结构

详见 SKILL.md 的报告模板章节。两套：Application 完整版 / 非 Application 信息卡片版。

---

## 关键编排取舍

1. **类别分支必须在最前**：决定后续是"深度查"还是"轻量展示"，避免对 Redis 告警去查 service log
2. **时间窗用绝对时间**：所有 logs/traces 查询用 `triggerTime ± 30min`，不用 `"1h ago"` 相对时间（避免诊断报告写完后被时间漂移污染）
3. **Phase 3 + 4 并行**：规则查询和数据查询互不依赖，全部并行
4. **strip 前缀必须用工具函数**：`prod-pay-asset` → `pay-asset`，不要让 AI 手撸字符串处理
5. **关联告警不可省**：单条告警可能是表象，同时刻其他告警往往揭示真正的根因（如下游中间件挂了）
6. **报告落盘前确认目录存在**：`mkdir -p docs/diagnosis/` 再写

---

## 常见降级场景

| 现象 | 降级方案 |
|------|---------|
| `INTERNAL_TOKEN` 未设置 | 告知用户配置环境变量后重试，**禁止**继续往下查 |
| `alarm-event-detail` 返回 404 | 事件 ID 错或已过期，让用户提供新 ID |
| Phase 3a 中 trace 节点异常（`signoz_index_v2` 不可用）| 跳过 trace 部分，只用 logs（与 apm-diagnosis 同样的降级套路）|
| 告警 triggerTime 距今超过 7d | 部分接口可能查不到数据，降级为"仅展示告警基本信息"|
| 同时刻活跃告警 > 50 条 | 全集群可能有故障，重点看上游中间件类告警，提示用户切换到中间件视角 |

---

## 案例索引

（待真实案例补充）

- 例：`docs/diagnosis/2026-04-18-alarm-EVT-94895962-jvm-fullgc.md`