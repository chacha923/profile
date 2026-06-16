# alarm-diagnosis — 龙虾 (Lobster) 部署与推广指南

> 把 `alarm-diagnosis-skill.zip` 推到公司内部的龙虾 (Lobster) skill 市场，
> 替换/补位现有的 `error-log-analysis` skill，做飞书告警群 @机器人的诊断主力。

## 1. 推广卖点（"为什么换我们的"）

`error-log-analysis` 是上一代基于"纯日志正则归因"的告警诊断 skill。我们的 `alarm-diagnosis` 是同一生态位的下一代实现：

| 维度 | `error-log-analysis` | **`alarm-diagnosis`（推荐）** |
|------|---------------------|------------------------------|
| 数据源 | 仅 OTel logs | **OTel traces (主) + logs (兜底) + bigeyes (上下文)** |
| 老 Dubbo SDK 支持 | ❌ 无 `remote.application` 时归因失败 | ✅ trace span 走 `peer.service` 字段，新老 SDK 全覆盖 |
| 跨服务下钻 | 部分（靠堆栈正则） | ✅ trace topo (`trace-services`) 直接给跨服务调用链 |
| 性能维度 | ❌ 完全没有 | ✅ P50/P95/P99 + 长尾 op + IP 分布 + Pod 量化判定 |
| 告警事件画像 | ❌ 没有 | ✅ 同规则 24h 频次 / 7d 模式 / 复发判定 / 同时刻并发（雪崩信号） |
| 中间件实例归因 | HBase/Redis/DB/MQ schema | ✅ 同 schema + DB-SQL 维度 + 慢 SQL 样本 |
| Pod 分布判定 | 量化阈值 (Top1≥50%) | ✅ 同阈值 + 固化 verdict (`single-pod-likely` 等)，跨次诊断一致 |
| 报告结构 | 9 节平铺 | ✅ 5 节整合 (告警上下文 / 触发窗口 / 告警画像 / 链路与下游归因 / 观测限制) |
| IM 友好结论 | 三句话句式 | ✅ 同三句句式 + 链路归因层级图 + 量化阈值表 |
| Subagent 并发 | ❌ 单脚本串行 | ✅ window-analyzer + context-analyzer 双 agent 并行，2~3min 出齐报告 |
| 飞书卡片直入 | 靠 LLM 自解析 | ✅ `feishu_card_parser.py` 规则化抽取 17 个字段，confidence 评分 |
| INTERNAL_TOKEN 缺失 | 不依赖（仅查 OTel） | ✅ 自动降级走"卡片正文 + logs/traces"路径，依然产出可用报告 |
| 官方同源 | 第三方 hack | ✅ 与 `otel-logs-query` / `otel-traces-query` 一套数据栈，soul-otel-query-service 团队维护 |

**一句话**：trace 优先 / 日志兜底 / 卡片再兜底 的三层降级架构 + 告警事件画像 + 性能维度全覆盖。

## 2. 安装到龙虾

### 2.1 zip 产物

每次发版前在 `soul-otel-query-service` 仓库根目录执行：

```bash
bash skills/build-skills.sh
```

产物：

```
skills/dist/alarm-diagnosis-skill.zip    ~59K
```

zip 内容（自包含，无外部依赖）：

```
skills/alarm-diagnosis/SKILL.md
skills/alarm-diagnosis/LOBSTER_ROLLOUT.md      (本文档)
skills/alarm-diagnosis/references/
skills/alarm-diagnosis/scripts/
  ├── bigeyes_admin_api_client.py             (告警 API 客户端)
  ├── logs_client.py                          (OTel 日志查询)
  └── traces_client.py                        (OTel 链路查询)
skills/shared/scripts/
  ├── otel_client_common.py                   (公共 HTTP 工具)
  ├── alarm_resource_mapper.py                (resource → service.name)
  ├── dubbo_log_parser.py                     (老 SDK / trace 缺数据时的兜底归因)
  └── feishu_card_parser.py                   (飞书卡片正文 → 结构化字段)
```

### 2.2 上传龙虾市场

按龙虾 skill 上架流程提交 `alarm-diagnosis-skill.zip`。推荐填写：

- **名称**：`alarm-diagnosis`
- **分类**：告警诊断 / SRE / Oncall
- **描述**：从告警事件 / 飞书卡片到根因，trace 优先 + 日志兜底，5 节结构化报告，2~3 分钟出齐
- **入口词**：见 SKILL.md frontmatter 的 `Trigger ONLY on` 列表

### 2.3 环境变量（用户机器需配置）

| 变量 | 是否必填 | 缺失时的行为 |
|---|---|---|
| `PLATFORM_ENV` | 否（默认 test）| 默认 test；告警场景请显式 `export PLATFORM_ENV=prod` |
| `INTERNAL_TOKEN` | **推荐** | **缺失时自动降级**（详见 SKILL.md Phase 0 路径 C）|

`INTERNAL_TOKEN` 获取入口：去 [soul-claw 龙虾](https://soul-claw.soulapp-inc.cn) 申请 Cas-User。

## 3. 飞书机器人对接流程

假设龙虾飞书机器人已经能接收 @ 消息并把消息正文交给 Claude 处理：

```
飞书告警群
  └─ bigeyes 推告警卡片
      └─ 用户：@龙虾机器人 帮我看下这个告警
          └─ 龙虾把"卡片正文 + 用户消息"组合传给 Claude
              └─ Claude 命中 alarm-diagnosis 的 trigger 短语
                  └─ Phase 0 输入分流
                      ├─ 有 EVT-ID + 有 INTERNAL_TOKEN → 路径 A 完整 pipeline
                      ├─ 有卡片正文 + 有 INTERNAL_TOKEN → 路径 B 卡片解析 + 走 A
                      └─ 没 token 或 confidence < 4 → 路径 C 降级（仅 logs + traces）
```

机器人侧建议：

- 把"@机器人"的消息正文**原文**传给 Claude，不要做 strip
- 在系统消息里告诉 Claude 当前环境（prod / test）
- 把用户的飞书 user_id 或 Cas-User 作为可选透传，方便 skill 自动 export `INTERNAL_TOKEN`

## 4. 用户侧调用示例

### 4.1 飞书 @ 触发（无需用户做任何配置）

```
@龙虾  ──────────────────────────────────────────────
【生产告警】5 分钟 ERROR 超阈值
告警规则名称: pay-channel-error-rate
应用: prod-pay-channel-provider
触发时间: 2026-05-15 14:30:00
阈值: ERROR > 500/5min
当前值: 1234
Top1 异常: org.apache.dubbo.rpc.RpcException
事件: EVT-12345
帮我看下这个告警
─────────────────────────────────────────────────────
```

预期 Claude 行为：
1. 识别 trigger 短语命中 alarm-diagnosis
2. Phase 0 调 `feishu_card_parser.py --format json` 抽字段
3. 拿到 `event_id=EVT-12345` / `service=pay-channel-provider` / `trigger_time=...` 等
4. 如 INTERNAL_TOKEN 已配置 → 走路径 A，subagent 并发拉数据
5. 2~3 分钟出齐 5 节报告 + 一句话结论

### 4.2 CLI 调用（开发自查）

```bash
export INTERNAL_TOKEN=<your_cas_user>
export PLATFORM_ENV=prod
# 在 Claude Code / Claude Desktop 里：
"告警 EVT-94895962 帮我排查"
```

## 5. FAQ

### Q: 和 apm-diagnosis 怎么选？

- **告警事件触发** / 飞书群 @ / 给了 EVT-ID 或卡片 → `alarm-diagnosis`
- **服务级体检** / 给了 service.name / 想看 P99 长尾 → `apm-diagnosis`

两者数据栈相同，输出风格相似（5 节 vs 4 节），可同时安装。

### Q: 没有 INTERNAL_TOKEN 还能用吗？

能用，走 Phase 0 路径 C 降级。会失去的能力：
- 告警画像里的"同规则 24h 频次"
- 告警画像里的"复发判定 / 上次处理记录"
- 告警画像里的"同时刻并发告警"

保留的能力：
- 触发窗口分析 (logs + traces)
- 链路与下游归因 (trace-first / log-fallback)
- Pod 分布量化判定
- 观测限制声明
- 根因假设 / 行动清单 / 一句话结论

### Q: 老 Dubbo SDK 不上报 `remote.application`，归因怎么办？

主路径走 trace span 的 `peer.service` / `service.name` 字段，这跟 SDK 版本无关。
日志兜底路径 `dubbo_log_parser.py` 会输出 `legacy_sdk_ratio` 字段，命中 ≥ 30% 时报告自动加准确度警示脚注："⚠️ 老 Dubbo SDK 缺 remote.application，N% 样本无法归因下游"。

### Q: 飞书卡片格式变了，parser 失效怎么办？

`feishu_card_parser.py` 输出 `confidence` 评分（0~7）。

- `confidence >= 4`：直接进 pipeline
- `confidence < 4`：标 `needs_fallback_extraction=true`，主 agent 用 LLM 在卡片正文里二次抽取
- 即使 parser 完全失效，LLM fallback 抽取仍能跑

发现新卡片格式后，提 PR 加正则同义词到 `_RULE_LABELS` / `_RESOURCE_LABELS` 等。

### Q: 怎么验证 zip 装上去能跑？

最小冒烟测试：

```bash
# 1. parser 单元
echo "告警规则: test\n应用: prod-foo\n触发时间: 2026-05-15 14:30:00\n级别: P1" \
  | python3 skills/shared/scripts/feishu_card_parser.py --format json

# 2. resource 映射
python3 skills/shared/scripts/alarm_resource_mapper.py to-service prod-pay-asset

# 3. log 归因兜底
echo '[{"data":{"attributes_string":{"exception.stacktrace":"timeout providers [10.1.2.3:20880]"}}}]' \
  | python3 skills/shared/scripts/dubbo_log_parser.py --mode all
```

三条都能跑 + 输出 JSON 即表示 zip 内核完整。Phase 1 / window-analyzer / context-analyzer 的真实数据查询需要 OTel + bigeyes 网络可达。

## 6. 升级清单（对接龙虾团队 checklist）

- [ ] zip 上传龙虾市场，version = git rev-parse --short HEAD
- [ ] 飞书机器人侧确认能透传消息原文（不 strip 卡片字段）
- [ ] 龙虾沙箱 Python 3.9+ （stdlib 已足够，无第三方依赖）
- [ ] 文档：告知用户去 soul-claw 申请 INTERNAL_TOKEN（推荐但非必需）
- [ ] 灰度策略：先在 1~2 个告警群试跑，对比 error-log-analysis 输出
- [ ] 退场策略：达成预期后下架 error-log-analysis，或保留为低优先级 fallback

## 7. 后续 roadmap

- **告警事件归档**：把诊断报告反写回 bigeyes，下次同规则触发时复用"上次根因"
- **慢 SQL 自动追 trace**：sql-analyzer 命中 top1 慢表后自动 long-sql-trace
- **指标 skill 互补**：非 Application 类告警（Redis/Rds/KafkaTopic）路由到对应指标 skill
- **告警话术 → service.name 自学习**：从历史诊断里建 `resource → service.name` 映射表，降低 fuzzy 匹配成本