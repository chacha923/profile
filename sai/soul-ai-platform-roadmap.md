# SAI-Console 训推平台深挖与后续改造

> 口径说明：本文用于补充 `soul-ai-platform.md` 和简历中的 SAI 经历，重点回答“如果继续改造，我会做什么”和“现在平台还有哪些缺陷”。推理服务演进按 **ACK 集群自托管 -> PAI EAS + 贝联托管** 表达，不展开早期 ACK 阶段的具体底层实现。

## 一句话结论

SAI-Console 现在已经具备“训推统一入口”的雏形：推理服务、TFJob / Cron TFJob、NuclioFunction、FAISS Build、模型下载、GPU NodePool、日志事件和第三方 Provider 都已经接进来了。

但它目前更像一个“多能力聚合控制台”，还不是一个强闭环的训推平台。继续深挖时，我不会优先继续堆新接口，而会把它往 **可声明、可对账、可回滚、可观测、可治理资源成本** 的方向改造。

## 当前主要缺陷

### 1. 控制面和真实资源的一致性不够强

现在很多链路是“先操作 Kubernetes / 第三方平台，再写数据库或审计记录”，中间没有统一事务、幂等键、补偿和对账。

+ 推理服务 ACK 自托管创建时，先创建底层工作负载，再调用 `api.InferenceService().Add` 落库；但落库错误被空 `if cErr != nil {}` 吞掉，容易出现“真实服务已创建、平台表没记录”的孤儿资源。
+ 推理服务删除接口在权限校验失败后没有 `return`，仍会继续执行 `api.InferenceService().Delete(meta)`；且当前删除主要是删平台记录，不是统一的服务生命周期删除。
+ TFJob / Cron TFJob 创建链路也是先创建集群对象，再写 `training_job` 表，再创建 TensorBoard。任一步失败都可能留下不一致状态。
+ 第三方 Provider 的创建、变配、扩缩容多是同步调用，缺少平台级 `Operation` / `Reconcile` 机制，失败重试和最终一致更多依赖人工或定时 Sync。

**本质缺陷**：控制面没有把“用户意图”和“实际资源状态”拆开，也没有统一的操作状态机。

### 2. Provider 抽象太粗，路由分发还偏过程式

现在 `pkg/provider.Interface` 是一个大接口，里面混了创建、启动停止、Pod、日志、事件、PVC、镜像、资源组、规格、存储、加速镜像等能力。不是每个厂商都天然支持全部能力，导致实现层要么空实现，要么靠上层路由提前判断。

路由侧也存在类似问题：同一个 Gin 路由链上串多个处理函数，例如 PAI、贝联、ACK 各自判断是否处理，再 `ctx.Next()` 或 `AbortWithStatus()`。这种写法短期能快速接入，但长期会带来几个问题：

+ 能力边界不清晰：新增 Provider 时需要理解多个 Controller 的链式执行顺序。
+ 错误语义难统一：某个 Provider 判断失败、透传失败、真实调用失败，对上层不容易形成一致错误模型。
+ 能力发现困难：前端和上层系统不知道某个 Provider 是否支持某个动作，只能试错。
+ 测试困难：Provider 行为散在 Controller、utils 和 provider client 中，缺少统一契约测试。

### 3. GPU 资源治理还停留在“调度意图翻译”，没有形成资源运营闭环

当前 NodePool 已经能表达 GPU 独占、共享显存、抢占 GPU、CPU 等资源池，并把节点池翻译成 `nodeSelector`、`tolerations` 和资源 `limits`。这是一层很有价值的抽象，但它还没有继续往资源运营平台演进。

主要缺口：

+ 缺少按 Space / 用户 / 项目维度的 GPU 配额、预留、超卖和用量账本。
+ 缺少在线推理、训练任务、FAISS Build、模型下载 Job 之间的资源优先级和抢占策略表达。
+ 贝联资源组被转换为 NodePool 时还有固定 cluster / pool_type 这类适配痕迹，资源语义没有完全归一。
+ 已有 `gpu-core.percentage` 常量，但平台资源匹配和容量展示主要围绕 GPU card / GPU memory，尚未完整表达共享算力比例。
+ 缺少成本视角：例如按资源池、模型、服务、训练任务统计 GPU 使用时长、显存占用和浪费率。

**下一层价值** 应该是把 NodePool 从“调度参数”升级为 “ResourcePool + Quota + Cost + Priority”。

### 4. 训练任务生命周期还不够产品化

TFJob / Cron TFJob 已经支持创建、更新、重启、迁移、资源变配、TensorBoard、OBSFS 挂载等能力，但整体仍偏模板拼装和对象操作。

主要缺口：

+ 训练模板里还有硬编码镜像、默认环境变量和 Git 同步凭据，应该迁移到模板版本、Secret、凭据引用和运行时配置。
+ TFJob 更新后通过重启资源让配置生效，缺少更细的安全策略，例如运行中任务是否允许变配、哪些字段需要重新创建、哪些字段可热更新。
+ Cron TFJob 和普通 TFJob 共享 Provider，但状态、active job、template workload、suspend、历史 Job 之间的关系还没有抽象成清晰领域模型。
+ watcher 主要监听当前集群和固定命名空间，FAISS watcher 还有硬编码 namespace / cluster，跨集群扩展和租户隔离不够自然。
+ 完成通知、状态同步、任务缺失恢复已经有点状能力，但还没有统一成训练任务状态机。

### 5. 日志、事件、指标虽然接入了，但统一观测体验还不完整

平台已经把 ACK 自托管、PAI、贝联等服务的 Pod、日志、事件、指标尽量收口到了相似入口，但实现上仍然不够统一。

+ 有些 Provider 的容器列表还是占位数据，不能真正反映远端实例结构。
+ 贝联日志查询目前更像固定参数拉取，没有和 ACK / PAI 日志模型统一分页、时间范围、keyword、previous 等语义。
+ 第三方服务被转换成 Kubernetes Deployment / Pod / Event 视图，这对统一前端很有帮助，但也会损失部分厂商原生状态，需要补标准状态模型。
+ 指标查询规则仍偏散落，缺少按服务维度统一的 golden signals：QPS、成功率、P99、GPU 利用率、显存、实例健康、扩缩容事件。
+ 排障链路还没有产品化成“一键诊断”：服务状态、实例状态、最近变更、日志错误、事件、资源池容量、网络连通应该被串起来。

### 6. 权限、审计和安全边界还需要收紧

目前平台已经有 owner、infra 成员、action_record 和部分中间件能力，但高风险动作的权限与审计还不够强。

+ 推理服务删除权限校验失败仍继续删除，这是必须优先修的缺陷。
+ 多处模型、空间、成员管理存在 `todo check owner` 类注释，说明权限模型没有完全收口。
+ action_record 多是 best effort 写入，没有参与操作状态机；如果审计失败，操作本身通常已经执行。
+ 原始请求体、配置表单、第三方 spec、Git 凭据等敏感信息需要统一脱敏和 Secret 化，不能散在日志、annotation 或模板环境变量里。

### 7. 工程质量问题会放大平台复杂度

当前代码里存在一些典型的“快速接入期”痕迹：`context.TODO()` 广泛使用、`recover()` 吞异常、`fmt.Printf` 打请求体、`db.Debug()` 残留、部分 `panic("not implemented")`、硬编码集群 / namespace / 默认用户等。

这些单点问题不一定立刻造成事故，但在训推平台这种多 Provider、多集群、多资源生命周期的系统里，会放大排障成本。

## 如果继续改造，我会按这个顺序做

### 第一阶段：先补安全网，解决会直接出事故的问题

目标是把当前“能用但不够稳”的控制面先收住。

+ 修复推理服务删除权限校验失败仍继续删除的问题。
+ 修复推理服务创建落库错误被吞的问题，至少做到失败返回、补偿删除或进入待对账状态。
+ 训练任务创建链路加补偿：底层对象创建成功但 DB / TensorBoard 失败时，要能自动回滚或落入 `PendingReconcile`。
+ 移除训练模板中的明文 Git 凭据，改成 Secret 引用或凭据 Provider。
+ 清理高风险日志：请求体、第三方配置、敏感参数统一脱敏。
+ 把关键动作都接入统一审计，并把审计与操作状态绑定。

这一阶段的产出不一定显眼，但它是后面继续做平台化的前提。

### 第二阶段：建立 Operation + Reconcile 模型

我会把“用户点一次按钮”抽象成一条平台操作记录，而不是让 HTTP 请求直接负责所有事情。

建议模型：

+ `Operation`：记录操作类型、目标资源、期望状态、操作者、幂等键、当前阶段、失败原因、重试次数。
+ `DesiredSpec`：记录用户希望服务或训练任务变成什么样。
+ `ObservedStatus`：由 watcher / syncer 从 ACK、PAI、贝联等实际平台同步回来。
+ `Reconciler`：比较 desired 和 observed，推进创建、更新、扩缩容、重启、迁移、删除等动作。

这样可以解决三个核心问题：

+ HTTP 请求变短，只负责提交意图。
+ 第三方接口超时或失败时，可以可靠重试。
+ 控制面和真实资源不一致时，可以自动对账，而不是靠人工查表和补数据。

### 第三阶段：重构 Provider 能力模型

把现在的大 Provider 接口拆成能力接口，并引入 Provider Registry。

可以拆成：

+ `ServiceLifecycleProvider`：Create / Update / Delete / Start / Stop / Restart。
+ `ScaleProvider`：Scale / GetReplicas。
+ `WorkloadViewProvider`：ListPod / GetPod / ListContainer。
+ `LogProvider`：QueryLog / DownloadLog。
+ `EventProvider`：ListEvent。
+ `MetricProvider`：QuerySeries / QueryRange。
+ `ResourceProvider`：ListResourceGroup / ListSpec / QueryQuota。
+ `StorageProvider`：ListStorage / AddStorage / SyncStorage。

Controller 不再用链式路由猜 Provider，而是通过 cluster / cloud_provider / serve_runtime 查 Provider，再判断它是否具备某个 capability。这样新增贝联之外的新平台时，只需要声明它支持哪些能力。

### 第四阶段：把 GPU NodePool 升级成资源治理系统

NodePool 现在是平台能力里最值得继续深挖的部分。下一步我会做成三层：

1. **资源池模型**：统一 ACK NodePool、PAI 资源组、贝联资源组，抽象成 ResourcePool，包含卡型、显存、独占 / 共享 / 抢占、地域、可用状态。
2. **配额模型**：按 Space / 用户 / 项目定义 GPU card、GPU memory、CPU、实例数、并发训练数等 quota，创建前做 admission check。
3. **运营模型**：沉淀成本、利用率、浪费率和热点资源池，给平台治理和容量规划使用。

这一层做好以后，简历和面试里可以更有深度地讲“我不是只做了一个服务管理页面，而是把 GPU 资源调度意图、准入校验、成本治理和容量运营做成了平台能力”。

### 第五阶段：训练任务平台化再往前走一步

训练平台下一步不应只围绕 TFJob 模板增删字段，而应该抽象训练任务生命周期。

我会重点做：

+ 训练任务状态机：Created、Queued、Preparing、Running、Succeeded、Failed、Stopped、ReconcileFailed。
+ 训练模板版本化：镜像、代码同步、挂载、启动命令、环境变量、Sidecar、TensorBoard 都由模板版本管理。
+ 可恢复能力：失败重试、断点恢复、克隆复跑、历史配置对比。
+ 数据和模型产物闭环：训练输入数据、代码版本、镜像版本、输出模型路径、后续推理服务引用关系可追踪。
+ Cron TFJob 产品化：周期、suspend、active job、历史 job、失败策略、并发策略形成统一视图。

### 第六阶段：把观测和排障做成“诊断面板”

平台真正有价值的地方不是展示十个入口，而是能回答“为什么这个服务现在不可用”。

我会做一个统一诊断链路：

+ 服务基础状态：desired / observed / provider status。
+ 实例健康：replica、ready、restart、pod phase、第三方实例状态。
+ 最近操作：发布、变配、扩缩容、重启、迁移、删除。
+ 日志摘要：最近错误、启动失败、健康检查失败。
+ 事件：Kubernetes Event / PAI Event / 贝联 Event 统一归类。
+ 资源池：GPU 是否不足、节点池是否不可调度、资源组是否满。
+ 网络：入口、域名、Service、贝联目标地址连通性。

这会把 SAI 从“控制台”升级为“训推运维入口”。

## 建议提炼成简历 / 面试表达

可以这样说：

> SAI 的后续演进重点不是继续堆 API，而是把训推平台从“多能力控制台”升级为“声明式控制面”。我会把用户操作抽象成 Operation，把服务和训练任务拆成 DesiredSpec / ObservedStatus，通过 Reconcile 保证 ACK、PAI、贝联等多底座最终一致；同时把 GPU NodePool 升级成 ResourcePool / Quota / Cost 模型，形成资源准入、成本治理和容量运营闭环。

更短版本：

> 现在 SAI 最大的问题是能力已经接进来了，但一致性、Provider 能力边界、GPU 资源运营和训练生命周期闭环还不够强。继续做的话，我会优先补 Operation + Reconcile、Provider capability、ResourcePool / Quota、训练状态机和统一诊断面板。

## 代码锚点

+ 推理路由链：`cmd/server/routes/inference.go`
+ 推理服务创建 / 删除 / 变配：`controller/inference/service.go`
+ 推理服务元数据：`api/inference/service.go`
+ Provider 大接口：`pkg/provider/interface.go`
+ 贝联适配与资源组转换：`pkg/provider/lccomputing/*`
+ TFJob 创建 / 更新 / 迁移：`controller/training/tfjob.go`
+ TFJob 模板：`pkg/runtime/tensorflow/template.go`
+ 训练 Provider：`pkg/runtime/tensorflow/provider.go`
+ watcher 入口：`cmd/watcher/main.go`
+ TFJob / Cron / FAISS watcher：`pkg/kubernetes/event/*`
+ NodePool / GPU 资源匹配：`api/core/cluster_nodepool.go`、`pkg/resource/constant.go`
