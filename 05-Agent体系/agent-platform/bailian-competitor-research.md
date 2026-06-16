# 阿里云百炼（Model Studio）竞品调研

> 用途：作为 moss-compose 的对标竞品调研，不是面试自述材料。
> 性质：基于阿里云官方公开文档的桌面调研（desk research），不代表内部实现，也不代表我做过百炼。
> 核对时间：截至 2026-05-27 已用官方文档核对公开能力；阿里云迭代较快，引用前请按文末链接复核。

# 一句话定位

百炼是阿里云的**大模型服务 + AI 应用构建平台**，可以拆成两层理解：

- **低代码 AI 应用平台**：通过控制台配置 Agent、Workflow、知识库、插件 / MCP，不写或少写代码就能构建并发布 AI 应用。
- **模型调用网关**：统一接入模型广场（通义系列及第三方模型），对外提供兼容 OpenAI 的 API、Key 管理、计费和限流。

和 moss-compose 的关系：moss-compose 基于开源 Coze Studio 二开、面向企业内部私有化；百炼是云厂商级商业平台。两者解决的是同一类问题（Agent / Workflow / RAG / MCP / 模型接入 / 应用观测 / 企业治理），但形态、规模和云产品集成深度不同。

# 能力模块（公开文档口径）

- 智能体应用（Single Agent）
  - 支持模型、系统提示词、知识库 RAG、插件、MCP、发布和 API 调用。
- 工作流应用（Workflow）
  - 通过节点组合复杂任务，典型节点：知识库、MCP、API、插件、函数计算、条件判断、大模型等。
- 知识库 / RAG
  - 文档导入、切片、向量化、检索，供应用引用。
- 插件 / MCP
  - MCP 作为大模型与外部工具之间的信息传递通道，支持官方 MCP 服务和自定义 MCP 服务。
- 模型接入（模型广场 / 网关）
  - 统一接入通义系列及第三方模型，提供 OpenAI 兼容调用入口、API Key、计费与限流。
- 应用观测
  - 将智能体 / 工作流调用拆成 Chain、Retriever、Embedding、Reranker、LLM、Tool、API、Script、Function Compute、Guardrail 等节点类型，记录 token、延时等信息。
- 发布与调用
  - 应用可发布并通过 API 被外部系统调用。

# 模型网关视角

把百炼当"AI 模型调用网关"看，关注点：

- 统一接入：屏蔽不同模型厂商的 base_url / 鉴权 / 参数差异，对上层暴露统一（OpenAI 兼容）接口。
- 计费与配额：按 token / 调用量计费，提供配额和限流。
- 能力差异：网关统一入口，但 function calling、response_format、长上下文、多模态、推理模型输出、计费规则各模型并不一致——这点和 moss-compose 的 Provider 抽象是同一个工程难点。
- 治理：Key 管理、调用审计、用量归因。

> 注：百炼计费 / 限流的具体规则、商业化报价随时间变化，本节只给框架，数字以官方为准。

# 与 moss-compose 对标

| 维度 | 百炼 | moss-compose |
| --- | --- | --- |
| 形态 | 云厂商级商业平台 | 基于 Coze Studio 二开的企业内部私有化平台 |
| 模型生态 | 通义系列 + 第三方，模型广场完整 | 内部模型网关 + OpenAI / Ark 兼容 |
| 身份权限 | 云账号 / RAM | 公司 SSO + Team / Space + OpenAPI JWT |
| 工具接入 | 插件 + MCP（官方/自定义） | MCP 服务管理 + 工具选择 / 搜索权限 |
| 观测 | 应用观测（多节点类型 + token / 延时） | Trace / Token / Latency / Error / Cost |
| 云产品集成 | 函数计算、数据连接器、RAM、计费等深度集成 | 接内部基础设施，集成面更窄 |
| 部署 | 公有云托管 | 企业内网私有化 |

共性平台问题（两者都绕不开）：应用构建、模型接入、MCP、RAG、Workflow、观测、权限和成本。

# 调研待补充（TODO）

- [ ] 计费模型与限流的具体规则、配额维度
- [ ] 工作流节点的完整类型清单与编排能力边界（循环 / 并行 / 子流程）
- [ ] 知识库 RAG 的切片 / 重排 / 引用 / 评测能力细节
- [ ] 应用观测能否服务于 Prompt / 模型灰度和评测闭环
- [ ] 多租户 / 权限模型（RAM 与应用级权限的关系）
- [ ] 与 Coze（商业版）、Dify 的横向对比

# 参考链接（阿里云官方）

- [智能体应用](https://help.aliyun.com/zh/model-studio/single-agent-application)
- [工作流应用](https://help.aliyun.com/zh/model-studio/workflow-application/)
- [MCP 介绍](https://help.aliyun.com/zh/model-studio/mcp-introduction)
- [富代码应用 MCP](https://help.aliyun.com/zh/model-studio/rich-code-application-mcp)
- [应用观测](https://help.aliyun.com/zh/model-studio/application-observation)
