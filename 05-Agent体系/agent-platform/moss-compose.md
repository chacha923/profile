# 项目定位
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1780296382482-f6658660-dc96-4e22-b964-5e01b40aeed2.png" width="726" title="" crop="0,0,1,1" id="u0c2f619b" class="ne-image">

+ 项目名称：moss-compose
+ 项目来源：基于 Coze Studio 二次开发的企业内部 Agent 应用平台
+ 所属领域：
    - Agent 应用构建
    - Workflow 编排
    - RAG / 知识库
    - MCP / Plugin 工具接入
    - 模型 Provider
    - 企业私有化与平台治理
+ 我的参与阶段：
    - 参与前期私有化开发与企业适配
    - 后续项目已交接，不把长期运营或后续演进说成自己负责
+ 面试定位：
    - 不包装成模型训练专家
    - 更适合定位为懂云原生、SRE、平台工程，同时参与过 Agent 平台私有化建设的工程师
+ 一句话：
    - moss-compose 是基于 Coze Studio 二开的企业内部 Agent 应用平台，我参与的是前期私有化和企业治理适配，重点不是简单部署，而是把 Agent、Workflow、RAG、MCP、模型 Provider、权限和观测接入企业内部体系。
+ 延伸 tech-point：
    - [AI 网关计费与 Token 限流](./ai-gateway-billing-rate-limit.md)
    - [Worker 拆分与 Serverless 化](./moss-worker-serverless.md)
    - [阿里云百炼竞品调研](./bailian-competitor-research.md)

# 一分钟开场
可以直接背：

moss-compose 是公司内部的企业私有化 Agent 应用平台，基于 Coze Studio 二开。我参与的是前期私有化开发，后续已经交接。

这块工作不是简单把 Coze Studio 部署起来，而是围绕企业内部可用性做适配，包括 SSO、团队和空间隔离、OpenAPI JWT 鉴权、模型配置管理、OpenAI / Ark 兼容、response_format 支持、MCP 服务管理、工具选择和搜索权限控制。

我对这类平台的理解是，它的核心不只是封装大模型 API，而是把 Agent、Workflow、RAG、MCP、模型 Provider、权限、安全、审计、Token 成本和调用链观测组合成一个企业内部可持续使用的平台。这个思路和我之前做 SAE、SAI、Bigeyes、OTel 的平台工程经验是一致的，只是平台对象从 K8s 应用、AI 训练任务、告警事件，换成了 Agent、Workflow、模型和工具。

# 项目背景
+ 各团队各自接模型 API：
    - API Key、base_url、模型参数、错误处理、成本统计分散。
    - 平台要提供统一的模型配置和 Provider 抽象。
+ Agent / Workflow 构建缺少统一入口：
    - Prompt、工具、知识库、发布、调试散在各个业务项目里。
    - 平台要提供统一的 Agent 应用构建入口。
+ 内部工具接入不受控：
    - 工具可能访问内部系统，如果只追求“能调通”，会带来越权和高危动作风险。
    - 平台要管理 MCP / Plugin 的注册、权限、参数校验、审计和风险等级。
+ 私有知识接入存在泄露风险：
    - RAG 召回本质上也是数据访问。
    - 如果不做用户、团队、空间权限过滤，就可能跨团队召回内部资料。
+ 开源平台不满足企业身份体系：
    - 原生账号、空间、权限模型和公司内部 SSO / 团队体系不一致。
    - 私有化必须把身份、资源归属、调用方鉴权和执行时权限校验打通。
+ 上线后问题不可解释：
    - 一次 Agent 调用可能经过 Prompt、RAG、模型、工具、Workflow 多个节点。
    - 如果没有 trace、token、latency、error、cost，排障和成本归因都会很困难。

面试表达重点：

私有化难点不是把服务跑起来，而是把一个面向通用场景的 Agent 平台改造成符合企业内部身份、权限、数据、安全和运维要求的平台。

# 项目目标
+ 企业身份接入：
    - 接入公司 SSO。
    - 把用户身份和内部团队体系映射到平台用户、团队、空间。
+ 资源隔离：
    - 用 Team / Space / App / Agent / Workflow / Knowledge / Tool 做资源边界。
    - 避免跨团队查看应用、工具和知识库。
+ 统一模型接入：
    - 通过 Provider 抽象兼容 OpenAI、Ark 或内部模型网关。
    - 屏蔽调用入口差异，但不掩盖模型能力差异。
+ 工具治理：
    - 管理 MCP 服务和工具选择权限。
    - 降低 Agent 调内部系统的越权和误操作风险。
+ RAG 权限治理：
    - 控制不同用户、团队、空间的知识库检索范围。
    - 防止跨权限召回。
+ OpenAPI 可调用：
    - 通过 JWT 或 API Key 类机制支持外部系统调用已发布应用。
    - 调用方身份要能审计和追踪。
+ 可观测与成本：
    - 为模型调用、工具调用、检索、Workflow 节点建立 Trace、Token、Latency、Error、Cost 口径。
+ 控制二开侵入性：
    - 企业适配尽量收敛在认证、权限、Provider、配置、工具管理等扩展层。
    - 降低后续跟进 Coze Studio 上游版本的维护风险。

# 我的职责
+ 私有化前期开发：
    - 参与 Coze Studio 私有化落地和企业内部适配。
    - 面试展开点：为什么不是简单部署，企业私有化真正难在哪里。
+ 身份与权限：
    - 参与 SSO、团队 / 空间隔离、OpenAPI JWT 鉴权相关改造。
    - 面试展开点：用户、团队、空间、应用、工具、知识库之间的权限边界。
+ 模型接入：
    - 参与模型配置管理、OpenAI / Ark 兼容、response_format 支持。
    - 面试展开点：Provider 抽象、模型能力差异、JSON 输出、streaming、tool calling。
+ MCP / 工具治理：
    - 参与 MCP 服务管理、工具选择和调用权限控制。
    - 面试展开点：MCP 安全、工具分级、高危动作控制、审计。
+ 搜索 / RAG 权限：
    - 参与搜索权限控制相关能力。
    - 面试展开点：RAG 不只是向量检索，权限过滤和数据隔离同样关键。
+ 平台工程视角：
    - 从已有 SRE、可观测、平台控制面经验出发参与设计讨论和落地。
    - 面试展开点：如何把 Agent 平台讲成平台工程，而不是模型算法项目。

边界要说清楚：

+ 可以说“参与前期私有化开发”“参与企业适配”“负责部分能力落地或改造”。
+ 不要说“我主导了 moss-compose 全生命周期”。
+ 不要说“我负责长期运营”。
+ 不要说“我完整设计了 Coze Studio Runtime”。
+ 如果面试官追问后续状态，可以说：
    - 后续项目已经交接，所以我会重点讲前期私有化、企业身份权限、模型和工具接入这些我参与过的部分。

# 总体架构
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1780296398669-ff7b36c4-c399-489c-b7b3-8ffe5a77feb2.png" width="786" title="" crop="0,0,1,1" id="ude78b2ea" class="ne-image">

+ 接入层：
    - 面向业务用户和内部系统。
    - 入口包括 Console、OpenAPI、发布渠道和 API 调用。
+ 企业治理层：
    - SSO / JWT 解决登录身份和调用方鉴权。
    - Team / Space 解决资源归属和隔离边界。
    - 权限策略覆盖应用、工具、知识库和搜索。
    - 审计 / 成本记录 Trace、Token、Cost。
+ 控制面：
    - App / Agent 管理 Prompt 和发布配置。
    - Workflow 管理节点、变量、条件分支。
    - Knowledge 管理文档、索引状态和权限策略。
    - Model Provider 管理 OpenAI / Ark 兼容配置和模型能力标签。
    - MCP / Tool 管理工具 schema、风险等级和授权关系。
+ 执行面与外部能力：
    - Agent Runtime 负责会话上下文、模型决策和工具选择。
    - Workflow Runtime 负责节点执行、变量传递和异常分支。
    - 知识库检索负责 retrieve、rerank 和权限过滤。
    - 模型服务负责 LLM call、response_format、streaming 等能力。
    - 内部工具 / API 通过 MCP Server 或 Plugin 暴露给 Agent / Workflow。
+ 观测闭环：
    - 记录入口请求、Prompt、RAG、LLM、Tool、Workflow 节点、Token、Latency、Error、Audit、Eval。

面试速记：

控制面管资源，执行面跑调用链，治理层管身份、权限、安全、审计、成本和观测。

# 核心能力
+ Agent 应用构建：
    - 通过 Prompt、模型、知识库、工具组合构建对话型应用。
    - Agent 适合不确定路径和模型自主规划。
+ Workflow 编排：
    - 把任务拆成节点、条件、输入输出和异常处理。
    - Workflow 适合生产确定性流程。
+ RAG / 知识库：
    - 让应用基于私有数据回答问题。
    - 重点不是向量库本身，而是权限、召回质量、切片、重排、引用和评测。
+ MCP / Plugin：
    - 把外部工具暴露给 Agent / Workflow。
    - 重点是工具 schema、鉴权、超时、审计和高危动作控制。
+ Model Provider：
    - 统一模型配置和调用入口。
    - 重点是 OpenAI / Ark 兼容、response_format、tool calling、streaming 和错误码适配。
+ 企业权限：
    - SSO、团队空间、应用权限、工具权限、搜索权限。
    - 这是私有化平台最核心的企业级能力。
+ OpenAPI 调用：
    - 已发布应用可被内部系统调用。
    - 需要调用方身份、JWT 鉴权、限流和审计。
+ 可观测：
    - 记录一次调用经过哪些节点、花了多少 token、哪里失败。
    - 这是 Agent 平台生产化的基础能力。
+ 成本治理：
    - 按模型、应用、团队、调用链统计 token 和费用。
+ 发布与版本：
    - 应用变更、Prompt 版本、Workflow 版本、模型配置版本要能灰度和回滚。
    - 否则只是 demo 平台，不是生产平台。

# 核心流程
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1780296414874-d72eaa8e-cda5-4b61-8b18-bd61d78b857a.png" width="960" title="" crop="0,0,1,1" id="uec697544" class="ne-image">

## Agent 调用链路
+ 用户请求进入 Console 或 OpenAPI。
+ 平台先做鉴权和空间校验：
    - 校验用户身份。
    - 校验调用方身份。
    - 校验应用、空间、工具和知识库权限。
+ 加载 Agent 配置：
    - Prompt。
    - 模型 Provider。
    - 可用工具。
    - 可用知识库。
    - 版本信息。
+ 组装上下文：
    - 系统 Prompt。
    - 历史会话。
    - 用户输入。
    - 权限过滤后的知识和工具。
+ RAG 检索：
    - 文档解析。
    - 切片。
    - embedding。
    - 向量检索 / 关键词检索。
    - rerank。
    - 权限过滤。
+ 模型 Provider 调用：
    - 处理 base_url、API Key、模型名、参数映射。
    - 处理 streaming、tool calling、response_format。
    - 记录 token、latency、错误码。
+ 工具调用：
    - 模型判断是否需要调用 MCP / Plugin。
    - 平台做工具权限、参数 schema、风险等级和审计校验。
    - 工具结果回填上下文，再继续生成。
+ 返回输出：
    - 支持最终结果或流式输出。
    - 记录 trace、token、latency、error、audit。

## Workflow 执行链路
+ Start 后先做参数校验。
+ 条件分支决定后续节点路径。
+ 节点类型可以包括：
    - RAG 节点。
    - API 节点。
    - MCP 节点。
    - LLM 节点。
    - 条件判断节点。
    - 脚本或函数计算节点。
+ 节点之间传递变量和结构化输出。
+ 节点失败后进入异常分支：
    - 超时。
    - 重试。
    - 降级。
    - 人工处理。
    - 兜底回复。
+ 每个节点都要记录：
    - 输入输出摘要。
    - token。
    - latency。
    - error。
    - retry count。

面试表达：

Agent 更偏模型自主决策，Workflow 更偏确定性编排。企业内部生产场景里，我更倾向于让关键路径进入 Workflow，把模型放在理解、生成、总结、分类这些节点里，而不是把高危动作完全交给 Agent 自主决定。

# 关键设计
## 企业身份和空间隔离
解决的问题：

+ 开源平台原生账号体系和公司内部 SSO、团队组织、权限模型不一致。
+ 如果不做适配，会出现用户身份不可控、跨团队看应用、跨空间访问知识库或工具的问题。

方案设计：

+ SSO 负责登录身份。
+ Team / Space 承载组织和资源边界。
+ App / Agent / Workflow / Knowledge / Tool 归属到明确空间。
+ OpenAPI JWT 用于外部系统调用时携带调用方身份和授权范围。
+ 搜索权限和工具选择权限不能只依赖页面隐藏，后端执行链路也要校验。

为什么这样做：

+ Agent 平台的风险不只在管理页面。
+ 一次执行会间接访问模型、知识库和内部工具。
+ 权限必须穿透到 Runtime。

取舍：

+ 权限模型越细，治理越强，但配置复杂度也更高。
+ 前期可以先做团队、空间、应用、工具、知识库几个关键边界，后续再细化到字段级或动作级。

高频追问：

+ 一个用户能不能看到别的团队的 Agent？
+ Agent 能不能调用没有授权的 MCP 工具？
+ RAG 检索如何防止跨团队召回？
+ API 调用时怎么识别调用方身份？

## 模型 Provider 抽象
解决的问题：

+ 不同模型服务的 base_url、API Key、模型名、streaming、tool calling、response_format、错误码、token 统计都不完全一致。
+ 如果上层 Agent / Workflow 直接绑定厂商 API，后续切模型和治理成本很高。

方案设计：

+ 上层只选择模型能力，不直接依赖厂商细节。
+ Provider 层管理：
    - base_url。
    - API Key。
    - 模型名。
    - 参数映射。
    - 超时。
    - 重试。
    - 错误码。
    - token 统计。
+ 对 OpenAI-compatible、Ark 或内部模型网关做兼容。
+ 用能力标签表达差异：
    - 是否支持 streaming。
    - 是否支持 tool calling。
    - 是否支持 JSON / response_format。
    - 是否支持长上下文。
    - 是否支持多模态。

关键边界：

Provider 能统一调用入口，但不能消除模型能力差异。平台要把差异显式建模。

高频追问：

+ response_format 为什么重要？
+ 如果模型 JSON 输出不稳定怎么办？
+ 如何统计一次 Workflow 多个模型节点的成本？
+ 模型失败是否 fallback？

## MCP / Plugin 工具治理
解决的问题：

+ MCP / Plugin 把内部系统能力暴露给 Agent。
+ 能调通不是最终目标，关键是能不能安全、可控、可审计地调用。

工具分级：

+ L1 查询类工具：
    - 可自动调用。
    - 记录参数摘要和结果摘要。
+ L2 低风险写操作：
    - 调用前二次确认。
    - 记录审计。
+ L3 变更类工具：
    - 生成工单或审批后执行。
+ L4 高危工具：
    - 不直接开放给 Agent。

补充治理：

+ 工具 schema 要描述清楚，否则模型难以判断何时调用。
+ 参数要做服务端校验，不能只相信模型生成的参数。
+ 工具调用要有超时、熔断、重试和失败可见性。
+ 内部工具要做调用方身份透传和权限校验。

高频追问：

+ MCP 和 Plugin 区别是什么？
+ prompt injection 会不会诱导模型调用危险工具？
+ MCP Server 如何注册、鉴权、审计？
+ 工具能访问内部系统，如何防止越权？

## RAG 权限和评测闭环
解决的问题：

+ RAG 不只是“文档切片 + embedding + 向量库”。
+ 企业内部真正难点是权限、新鲜度、召回质量、引用可信度和评测闭环。

排查顺序：

+ 文档解析是否正确。
+ 切片是否合理。
+ embedding 是否合适。
+ 召回是否命中。
+ 重排是否有效。
+ 权限过滤是否正确。
+ Prompt 是否正确引用。
+ 模型是否幻觉。

定位方法：

+ 正确片段没召回：检索问题。
+ 召回了但排序靠后：ranking 问题。
+ 召回正确但回答错：Prompt 或模型问题。
+ 回答引用了无权限内容：权限治理问题。
+ 上下文太长导致成本高：召回策略和上下文裁剪问题。

评测口径：

+ Recall@K：正确文档是否进入前 K 个召回。
+ MRR / NDCG：正确片段排序是否靠前。
+ Faithfulness：回答是否忠于引用内容。
+ Hallucination Rate：幻觉率。
+ Token Cost：召回上下文是否过多导致成本上升。
+ Latency：检索、重排、生成整体耗时。

## 调用链观测与成本治理
解决的问题：

+ Agent 应用上线后，最大的问题不是“能不能生成答案”。
+ 更关键的是出了问题能不能解释、质量能不能评估、成本能不能归因。

一次调用至少要记录：

+ 入口请求：
    - app。
    - space。
    - user。
    - caller。
    - 版本。
+ Prompt：
    - 模板版本。
    - 上下文长度。
+ RAG：
    - query。
    - 召回数量。
    - 命中文档。
    - rerank 分数。
    - 权限过滤结果。
+ LLM：
    - provider。
    - model。
    - input token。
    - output token。
    - latency。
    - 错误码。
+ Tool：
    - tool name。
    - 参数摘要。
    - 调用方。
    - latency。
    - 错误码。
+ Workflow：
    - 节点输入输出摘要。
    - 异常分支。
    - 重试次数。

高频追问：

+ 一次 Workflow 调用了多个模型，成本怎么算？
+ 如何定位慢在 RAG、模型还是工具？
+ Prompt 改动导致效果下降怎么发现？
+ 如何做灰度、A/B 和评测集？

# 技术难点
+ 开源平台企业化改造：
    - 难点：原生产品模型和企业身份、权限、审计不匹配。
    - 思路：把差异收敛在 SSO、权限、Provider、配置、工具管理扩展层。
    - 面试展开：私有化不是部署，而是治理能力补齐。
+ 权限穿透 Runtime：
    - 难点：页面权限不等于执行权限，Agent 会间接访问知识库和工具。
    - 思路：执行前校验用户、空间、工具、知识库权限。
    - 面试展开：RAG 泄露和 MCP 越权是高频问题。
+ 模型能力不一致：
    - 难点：不同模型对 JSON、tool calling、streaming、长上下文支持不同。
    - 思路：Provider 统一调用，能力标签显式暴露。
    - 面试展开：不能说 Provider 完全屏蔽差异。
+ 工具调用安全：
    - 难点：模型可能被 prompt injection 诱导调用危险工具。
    - 思路：工具分级、参数校验、确认 / 审批、审计。
    - 面试展开：MCP 安全治理。
+ RAG 质量排查：
    - 难点：效果不好可能来自解析、切片、召回、重排、Prompt、模型多个环节。
    - 思路：建立分段指标和 Trace。
    - 面试展开：把 RAG 当搜索系统 + 生成系统。
+ 调用链可观测：
    - 难点：一次调用跨模型、工具、检索、Workflow 多节点。
    - 思路：节点级 Trace、token、latency、error。
    - 面试展开：Agent 平台生产化能力。
+ 二开升级成本：
    - 难点：改太深会难以跟上 Coze Studio 上游。
    - 思路：控制侵入性，维护 patch 基线和企业适配层。
    - 面试展开：私有化长期维护策略。

# 稳定性与治理
+ 鉴权：
    - SSO + JWT + 空间权限 + 执行时权限校验。
    - 防止未授权访问和调用。
+ 工具安全：
    - 工具分级、参数校验、二次确认、审批、审计。
    - 防止高危工具被模型误调用。
+ 超时重试：
    - 模型、API、MCP、Workflow 节点分别设置超时和重试。
    - 避免单节点拖垮整条链路。
+ 异常分支：
    - Workflow 节点失败后进入兜底或人工处理。
    - 让失败可控，而不是只返回大模型错误。
+ 幂等：
    - 对写操作工具要求 request_id、业务幂等键或工单流转。
    - 避免模型重复调用造成重复变更。
+ 观测：
    - Trace、Log、Metric、Token、Cost、Audit。
    - 支撑排障、成本治理和安全复盘。
+ 版本治理：
    - Prompt、Workflow、模型配置、工具配置有版本意识。
    - 支撑灰度、回滚和效果对比。
+ 评测：
    - 构建 eval dataset，覆盖关键业务问题和工具调用路径。
    - 防止 Prompt 或模型切换凭感觉上线。

# 数据模型 / 资源模型
+ User：
    - 核心字段：user_id、sso_id、team_ids、roles。
    - 作用：承载用户身份。
    - 设计考虑：和公司 SSO / 组织架构映射。
+ Team：
    - 核心字段：team_id、name、members。
    - 作用：承载团队边界。
    - 设计考虑：资源归属、权限继承。
+ Space：
    - 核心字段：space_id、team_id、admins、members。
    - 作用：承载工作空间。
    - 设计考虑：Agent、Workflow、知识库、工具的主要隔离单元。
+ App：
    - 核心字段：app_id、space_id、type、version、publish_status。
    - 作用：对外应用。
    - 设计考虑：发布、调用、版本管理。
+ Agent：
    - 核心字段：prompt、model、tools、knowledge_refs、memory_config。
    - 作用：智能体配置。
    - 设计考虑：工具和知识库必须经过权限过滤。
+ Workflow：
    - 核心字段：nodes、edges、variables、error_policy、version。
    - 作用：编排流程。
    - 设计考虑：节点输入输出、异常分支、重试。
+ ModelProvider：
    - 核心字段：provider_type、base_url、api_key_ref、model_name、capabilities。
    - 作用：模型接入。
    - 设计考虑：能力标签和密钥管理。
+ MCPServer / Tool：
    - 核心字段：server_url、tool_schema、auth、risk_level、owner。
    - 作用：工具接入。
    - 设计考虑：工具权限、安全分级、审计。
+ KnowledgeBase：
    - 核心字段：kb_id、space_id、doc_scope、index_status、permission_policy。
    - 作用：知识库。
    - 设计考虑：数据权限和索引新鲜度。
+ InvocationTrace：
    - 核心字段：trace_id、app_id、node_spans、token、latency、error、cost。
    - 作用：调用观测。
    - 设计考虑：问题定位、成本归因、质量评估。

# 指标与收益
+ 统一入口：
    - 结果：统一 Agent、Workflow、Knowledge、Tool、Model 配置入口。
    - 价值：不再让每个团队各自封装模型 API、工具权限和知识库接入。
+ 企业身份接入：
    - 结果：SSO、Team / Space、OpenAPI JWT。
    - 价值：让平台资源能接入公司内部身份和调用方体系。
+ 权限治理：
    - 结果：工具选择权限、搜索权限、空间隔离。
    - 价值：降低 MCP 工具越权和 RAG 跨权限召回风险。
+ 模型接入：
    - 结果：OpenAI / Ark 兼容、response_format 支持。
    - 价值：降低上层应用直接绑定模型厂商 API 的成本。
+ 可观测基础：
    - 结果：Trace、Token、Latency、Error、Cost 口径。
    - 价值：为后续排障、成本归因、评测和灰度提供基础。
+ 私有化可维护性：
    - 结果：企业差异尽量放在扩展层。
    - 价值：降低后续跟进 Coze Studio 上游版本的维护风险。

不要编造数字：

前期建设阶段，更多是建立统一入口和治理基础。具体长期使用指标后续已交接，我不夸大。

# 核心能力映射
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1780296435291-d4e5b58f-6539-4fec-b5ba-f38bc5ee1e4d.png" width="798" title="" crop="0,0,1,1" id="ue208bf04" class="ne-image">

+ 智能体应用：
    - moss-compose 对应经验：Agent 应用构建、Prompt、模型、工具、知识库组合。
    - 面试展开：Agent 适合自主规划，但生产场景要关注可控性。
+ 工作流应用：
    - moss-compose 对应经验：Workflow 节点编排、输入输出、异常处理。
    - 面试展开：关键路径更适合确定性 Workflow。
+ 知识库 / RAG：
    - moss-compose 对应经验：搜索权限控制、RAG 链路理解。
    - 面试展开：权限、召回、重排、评测、上下文成本。
+ MCP / 工具接入：
    - moss-compose 对应经验：MCP 服务管理、工具选择权限。
    - 面试展开：工具 schema、鉴权、超时、审计、高危动作治理。
+ 模型服务：
    - moss-compose 对应经验：OpenAI / Ark 兼容、response_format、Provider 管理。
    - 面试展开：统一调用入口，但不掩盖模型能力差异。
+ 应用观测：
    - moss-compose 对应经验：Token、Trace、Latency、Error、Cost 思路。
    - 面试展开：一次调用拆成 Retriever、Embedding、Reranker、LLM、Tool、Workflow 节点。
+ 企业治理：
    - moss-compose 对应经验：SSO、Team / Space、JWT、权限隔离。
    - 面试展开：企业级平台同样绕不开租户、权限、审计和成本。
+ 平台工程：
    - moss-compose 对应经验：SAE / SAI / Bigeyes / OTel 的控制面经验。
    - 面试展开：把复杂底层能力产品化、治理化、可观测化。

# 高频问题
## 介绍一下 moss-compose，你主要做了什么？
建议回答：

moss-compose 是我们基于 Coze Studio 二开的企业内部 Agent 应用平台。我参与的是前期私有化开发，重点不是单纯部署，而是企业适配和治理能力，包括 SSO、团队 / 空间隔离、OpenAPI JWT 鉴权、模型配置管理、OpenAI / Ark 兼容、response_format 支持、MCP 服务管理、工具选择和搜索权限控制。

目标是让内部业务团队可以用统一平台构建 Agent、Workflow、知识库和内部工具调用，而不是每个团队各自接模型、接工具、做权限和观测。

追问准备：

+ 你只是部署，还是改了控制面、权限、模型接入、运行链路？
+ 后续交接后你还负责吗？
+ 你们二开的核心价值是什么？

边界回答：

后续项目已经交接，所以我不会把长期运营经验说成我负责。我能展开的是前期私有化、企业身份权限、模型和工具接入这些我参与过的部分。

## 为什么基于 Coze Studio 二开，而不是自研、Dify、LangChain / LangGraph？
建议回答：

我们要解决的是企业内部 Agent 应用平台问题，不是单个 Agent 应用开发问题。Coze Studio 已经有 Agent、Prompt、Workflow、RAG、Plugin 等应用平台基础形态，二开可以更快补齐企业内部 SSO、团队空间、模型配置、MCP 管理、工具权限、OpenAPI 鉴权等能力。

LangChain / LangGraph 更像开发框架，适合写代码构建 Agent 流程；Coze Studio 更像应用开发平台，适合让业务方或平台用户通过控制面配置 Agent、Workflow、知识库和工具。

不要说：

+ Coze Studio 最好，其他都不行。

更稳的说法：

+ 选型取决于目标。
+ 如果目标是研发自己写 Agent 应用，框架更灵活。
+ 如果目标是企业内部提供统一应用构建、发布、权限和治理入口，平台型产品更合适。

## Agent 和 Workflow 怎么选？
建议回答：

不确定路径、需要模型根据工具自主规划的，用 Agent；路径明确、需要可控、可审计、可回放的，用 Workflow。

企业生产场景里，我更倾向于 Workflow 承载关键路径，Agent 做理解、规划、总结或辅助节点。比如查询、审批、运维动作、数据写入，不适合完全放给 Agent 自主决定。

追问：Workflow 是 DAG 吗？节点失败怎么办？

可以把 Workflow 理解成有向流程图，重点是节点输入输出、条件分支、异常分支、超时重试和变量传递。节点失败不能只返回一个大模型错误，要能定位失败节点、输入输出摘要、错误码和重试策略。

## 你们怎么做权限隔离？
建议回答：

我会拆四层：用户身份、空间资源权限、工具权限、数据权限。

用户通过 SSO 进入平台；Team / Space 决定能管理哪些 Agent、Workflow、知识库和工具；工具权限决定某个 Agent 能不能调用某个 MCP；数据权限决定 RAG 检索范围。最容易被忽略的是知识库检索权限，因为 RAG 召回本质上也是数据访问。

追问：只在前端隐藏工具够不够？

不够。Agent Runtime 执行时也必须校验工具和知识库权限，否则绕过页面或通过 OpenAPI 调用仍然可能越权。

## MCP 工具调用有什么安全风险？
建议回答：

风险主要是越权访问、参数注入、高危操作、SSRF、内部系统误调用、API Key 泄露和审计缺失。

我的倾向是工具分级治理：查询类自动执行，低风险写操作二次确认，变更类生成工单或审批，高危工具不直接开放给 Agent。

追问：prompt injection 怎么防？

不能只靠 Prompt 约束。要在平台侧做工具 allowlist、参数 schema 校验、调用方权限校验、风险分级、敏感字段脱敏和审计。模型只负责建议调用，最终能不能执行由平台策略决定。

## 模型 Provider 怎么设计？
建议回答：

上层 Agent / Workflow 不直接依赖模型厂商 API。Provider 层统一处理 base_url、API Key、模型名、streaming、tool calling、response_format、超时、重试、错误码和 token 统计。

但 Provider 不能假装所有模型能力完全一致。比如 JSON 输出稳定性、function calling、长上下文、多模态、推理模型输出、计费规则都不一样。平台应该把能力差异显式建模。

追问：response_format 为什么重要？

Workflow 和工具调用经常需要结构化输出。如果模型输出不是稳定 JSON，下游节点解析就会失败。response_format 能提高结构化输出稳定性，但仍要做 schema 校验和失败兜底。

## RAG 效果不好怎么排查？
建议回答：

先拆链路：文档解析是否正确、切片是否合理、embedding 是否合适、召回是否命中、重排是否有效、权限过滤是否正确、Prompt 是否正确引用、模型是否幻觉。

如果正确片段没召回，是检索问题；召回了但排序靠后，是 ranking 问题；召回正确但回答错，是 Prompt 或模型问题；回答引用了无权限内容，是权限治理问题。

## Agent 平台怎么做观测？
建议回答：

一次请求要能看到完整 trace：入口、Prompt、RAG、模型、工具、Workflow 节点、输出。指标包括 latency、token、错误率、模型分布、工具调用次数、检索命中文档、成本。

对平台来说，观测不是附属功能，而是 Agent 应用生产化的基础能力。没有 trace 和 eval dataset，Prompt 改动、模型切换、工具扩展都只能凭感觉上线。

## 私有化二开怎么避免后续升级困难？
建议回答：

尽量减少侵入式修改，把企业差异放在扩展层，比如认证适配、Provider 适配、权限中间层、配置中心、外部服务适配。

对上游代码保持版本基线和 patch 管理，不随意改核心 Runtime。否则短期上线快，长期很难跟上上游。

## 如果让你设计一个企业级 Agent 平台，你会优先做什么？
建议回答：

我会优先做四个底座：模型接入网关、Agent / Workflow 编排、RAG / 知识库、可观测与评测。

但企业级平台必须同时做租户、权限、审计、成本、限流和工具安全。否则只是 demo 平台，不是生产平台。

## vibe coding 全面铺开会遇到什么问题？
建议回答：

我把问题分四层看，不只是“代码写得好不好”。

+ 代码质量与可维护性：模型容易生成能跑但风格不一致、抽象混乱、重复实现的代码。短期效率高，长期变成谁都不敢动的“黑盒代码”，认知债（cognitive debt）转移给后来维护的人。
+ 安全与合规：幻觉 API、过期写法、不安全默认值（弱加密、SQL 拼接、密钥硬编码），以及把内部代码、密钥贴进外部模型带来的数据外泄和供应链风险。
+ 正确性与可验证性：模型给的是“看起来对”的代码，缺测试、缺边界场景。如果开发者自己也不理解，就失去了 review 能力，bug 会被原样合入。
+ 组织与能力结构：新人过度依赖会跳过基础训练，团队整体对系统的“心智模型”退化，出问题时没人能脱离工具排障。

更稳的说法（收尾到我的平台视角）：

+ vibe coding 不是该不该用，而是要不要工程化。它和 Agent 平台是同一个命题：模型只负责“建议”，能不能落地由工程约束决定。
+ 我的对策思路和做 moss-compose 一致：把不可控的部分用平台兜住——强制 code review、CI 里加静态扫描 / SAST / 依赖审计、单测和契约测试做兜底、敏感代码和密钥走内网模型网关而不是公网、用 trace 和评测集衡量产出质量。
+ 一句话：vibe coding 提升的是“写”的速度，但工程的瓶颈一直是“改”和“验证”，所以治理、可观测、评测这些非模型能力反而更重要。

追问：那你们会全面推 vibe coding 吗？

分场景。原型、脚本、一次性工具、测试代码可以放开；核心链路、安全敏感、强一致性逻辑要保留人主导、AI 辅助，并且产出必须过 review 和测试闸门。和 Agent vs Workflow 的取舍是同一套逻辑：探索性放开，确定性收敛。

# 主动引导亮点
## 平台工程，而不是模型算法包装
我不是从模型算法角度切入，而是从平台工程角度切入。我的优势是做过多个内部平台控制面，知道如何把复杂底层能力抽象成业务可用、可治理、可观测的平台。moss-compose 是我把这种经验迁移到 Agent / Workflow / RAG / MCP 场景的一次实践。

## 企业级 Agent 平台的非模型问题
Agent 平台真正生产化，很多问题不在模型本身，而在权限、工具安全、调用链观测、成本治理、发布回滚、评测集和多租户隔离。

## SRE / 可观测性视角
我会特别关注 Agent 应用上线后的可观测性，比如 token 消耗、模型延迟、工具调用失败、RAG 召回质量和 Prompt 变更影响。因为没有这些能力，平台很难支撑企业级应用持续迭代。

## 和已有项目串联
+ SAE：
    - 控制对象：K8s 应用、发布、运行治理。
    - 连接点：控制面、权限、发布、观测、异常恢复。
+ SAI：
    - 控制对象：训练 / 推理任务、资源调度。
    - 连接点：异构资源、任务状态、平台治理。
+ Bigeyes：
    - 控制对象：告警事件、聚合、分派。
    - 连接点：事件治理、可观测、问题定位。
+ OTel / Signoz：
    - 控制对象：Trace、Metric、Log。
    - 连接点：Agent 调用链观测、token / latency / error 分析。
+ moss-compose：
    - 控制对象：Agent、Workflow、Model、Tool、Knowledge。
    - 连接点：AI 应用平台化、企业治理、生产化。

# 不要踩的坑
+ 不要说“我部署了 Coze Studio”。
    - 更好的说法：基于 Coze Studio 做企业内部 Agent 平台私有化和治理增强。
+ 不要说“我主导了整个项目”。
    - 更好的说法：我参与前期私有化开发，后续已交接；我重点讲参与过的企业适配部分。
+ 不要说“Provider 能完全屏蔽模型差异”。
    - 更好的说法：Provider 统一调用入口，但能力差异要显式建模。
+ 不要说“RAG 就是向量库”。
    - 更好的说法：RAG 是解析、切片、召回、重排、权限、Prompt、生成、评测、观测的完整链路。
+ 不要说“Agent 能自动解决很多问题”。
    - 更好的说法：Agent 适合探索性任务，Workflow 适合生产确定性流程。
+ 不要说“工具接通就行”。
    - 更好的说法：MCP / Plugin 必须做权限、参数校验、审计、超时和高危动作控制。
+ 不要说“我做模型训练”。
    - 更好的说法：我不是模型算法专家，我的强项是 AI 应用平台工程和企业级治理。

# 临场准备顺序
+ 先背一分钟开场：
    - moss-compose 是什么。
    - 我参与了什么。
+ 再背私有化价值：
    - 不是部署。
    - 是 SSO、Team / Space、JWT、模型配置、MCP、工具权限、搜索权限。
+ 再背总体架构：
    - 控制面。
    - 执行面。
    - Provider。
    - 工具层。
    - 治理观测层。
+ 再背 Agent vs Workflow：
    - 自主决策 vs 确定性编排。
+ 再背 MCP 安全：
    - 工具分级。
    - 权限。
    - 参数校验。
    - 审计。
    - 审批。
+ 再背 RAG 排查：
    - 解析。
    - 切片。
    - 召回。
    - 重排。
    - 权限。
    - Prompt。
    - 生成。
    - 评测。
+ 再背 Model Provider：
    - 统一接口。
    - 不掩盖模型差异。
+ 再背可观测：
    - trace。
    - token。
    - latency。
    - error。
    - cost。
    - eval dataset。
+ 最后串联平台经验：
    - SAE / SAI / Bigeyes / OTel 到 Agent 平台。

# 三档背诵版
## 三十秒版
moss-compose 是基于 Coze Studio 二开的企业内部 Agent 应用平台。我参与的是前期私有化开发，主要围绕 SSO、团队空间隔离、OpenAPI JWT、模型配置、OpenAI / Ark 兼容、response_format、MCP 管理、工具权限和搜索权限这些企业级适配。核心是把 Agent、Workflow、RAG、MCP、模型接入、应用观测和企业治理这些能力组合成企业内部可持续使用的平台。

## 一分钟版
moss-compose 是我们基于 Coze Studio 做的企业内部 Agent 应用平台。我参与前期私有化开发，后续已经交接。我的工作重点不是模型算法，也不是简单部署，而是企业适配和平台治理，包括 SSO、Team / Space 隔离、OpenAPI JWT 鉴权、模型配置管理、OpenAI / Ark 兼容、response_format 支持、MCP 服务管理、工具选择和搜索权限控制。

我理解这类平台的核心，是把 Agent、Workflow、RAG、MCP、模型 Provider、权限、安全、成本和观测组合起来，变成企业内部可持续使用的平台。

## 三分钟版
这个项目可以从三个层次讲。第一是控制面，管理 Agent、Workflow、Prompt、Knowledge、Model Provider、MCP 和应用发布；第二是执行面，处理一次对话或 Workflow 的模型调用、RAG 检索、工具调用和上下文传递；第三是企业治理层，做 SSO、Team / Space、JWT、工具权限、搜索权限、审计、Trace、Token 和成本。

我参与的前期私有化开发主要集中在企业级适配。比如模型 Provider 不能让上层直接绑定某个模型厂商，要兼容 OpenAI / Ark 和 response_format，但也不能假装模型能力完全一致；MCP 工具不能只考虑能不能调通，还要做权限、参数校验、风险分级和审计；RAG 不能只讲向量库，还要做权限过滤、召回质量、重排、引用和评测。

这段经历最能体现的，是我不是从模型训练切入，而是从平台工程切入：如何把复杂 AI 能力产品化、治理化、可观测化，并让企业内部能稳定、安全、可控地使用。

# 面试反问
+ 贵团队在 Agent 应用生产化上，更关注应用构建效率，还是上线后的评测、观测、权限、成本和安全治理？
    - 目的：引导到企业级落地。
+ 业务落地时，更多使用确定性的 Workflow 编排，还是让 Agent 自主规划？两类场景边界怎么划分？
    - 目的：引导到 Agent vs Workflow。
+ MCP 工具接入越来越多以后，在工具权限、调用审计和高危动作控制上怎么做平台治理？
    - 目的：引导到 MCP 安全。
+ 应用观测现在更偏调用链排障，还是也会服务于 Prompt / 模型灰度和评测闭环？
    - 目的：引导到 OTel / SRE 优势。

# 面试主线
整场面试围绕这一条线讲：

我不是模型算法方向，而是平台工程方向。我的优势是做过内部平台控制面、权限治理、运行观测和稳定性建设，知道如何把复杂底层能力变成业务可用、可治理、可观测的平台。moss-compose 是我把这套经验迁移到 Agent / Workflow / RAG / MCP 场景的一次实践。
