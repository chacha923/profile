# SAE 项目总结

说明：本文按 `interview-project-doc` 组织，目标是面试表达材料，不是源码导览。图片和关键代码引用保留，源码级细节放在“深水区”用于追问展开。

面试主线不要从路由表、controller 文件、CRD 字段开始。先讲 SAE 是什么平台、解决什么交付与运行治理问题、为什么要拆成同步控制面和异步状态面，再按追问进入 `sae-console`、`sae-api`、watcher、job 和具体代码锚点。

# 项目定位（90 秒开场）

SAE 是公司内部面向研发和运维团队的应用交付与运行治理平台。它不是一个简单的 Kubernetes 管理后台，也不只是发布页面，而是把应用创建、环境接入、资源配置、镜像构建、流水线执行、灰度发布、回滚、日志排查、事件定位和运行诊断收敛到统一控制面。对研发来说，SAE 把“直接使用 Kubernetes、Tekton、Rollouts、GitLab、Harbor、日志和通知系统”这件事，变成“通过一个平台完成应用交付和运行管理”。

从平台定位看，SAE 向下复用 Kubernetes 作为运行底座，复用 Tekton 做持续构建，复用 Argo Rollouts / 内部 Rollouts 能力做持续发布，复用 `sae-api` 定义 Application、Cluster 等 SAE 领域资源契约；向上通过 `sae-console` 提供控制台 API、OpenAPI、MCP / Agent 入口、鉴权、审计和排障能力。它的核心价值不是替代这些基础设施，而是把分散的云原生能力产品化、流程化、标准化，形成可规模化支撑公司应用交付和线上治理的内部平台。

我的职责边界主要在 SAE 后端控制面、应用生命周期治理、发布与运行态治理、多集群资源编排、异步状态同步和平台排障能力建设。面试里我会强调：我做的是平台控制面和治理体系，不是自研 Kubernetes、Tekton、Rollouts，也不是重写底层调度或网络控制器。

# 我的职责与边界

## 我主要负责的部分

### 控制面建设

围绕 `sae-console` 建设统一 API 控制面，承接控制台、OpenAPI、MCP / Agent 等入口，把应用管理、发布、流水线、工作负载、事件、指标、权限、审计和诊断能力组织成统一后端服务。

面试表达：

我做的不是单个页面接口，而是把研发日常交付动作收敛到一个控制面里，让应用创建、构建、发布、回滚、扩缩容、日志、事件和诊断走统一平台口径。

### 应用生命周期治理

通过 `sae-console` 与 `sae-api` 的配合，将“应用”从数据库记录上升为可声明、可 watch、可调谐的领域资源。`console` 处理用户请求和业务规则，`sae-api` 的 Application controller 负责把 `Application` CRD 调谐成 Deployment、Service、Ingress 等底层资源。

面试表达：

SAE 不是只把应用存在 MySQL 里，而是把应用抽象成平台领域资源，再用 Kubernetes 的 watch、status 和 controller 机制做生命周期治理。

### 持续构建与持续发布治理

将 Tekton Pipeline / PipelineRun、Rollouts 发布策略、发布记录、质量校验、发布窗口、暂停 / 继续 / promote / abort / rollback 等动作纳入平台流程。

面试表达：

SAE 不是自己从零实现构建和发布引擎，而是把 Tekton 和 Rollouts 这些底座能力封装成研发能稳定使用的发布流程和治理入口。

### 异步状态同步与补偿

通过 `cmd/watcher`、`K8sWatcher`、Event watcher、Replicas watcher、PipelineRun watcher、Rollout notification 等能力，将集群事实同步回数据库、事件中心和通知系统。

面试表达：

发布、构建、事件和副本状态不能只靠用户请求实时查询。SAE 把同步 API 和异步状态面拆开，watcher 负责把真实运行态持续同步回来。

### 多集群与资源编排

通过 `Cluster` CRD、`ClusterManager`、typed SAE client、Kubernetes client、dynamic client、Rollouts client 等能力维护多集群访问和资源编排入口。

面试表达：

多集群治理的关键不是在每个接口里临时创建 client，而是通过 `Cluster` 资源和 `ClusterManager` 维护稳定的多集群访问层。

## 我不负责的部分

1. 不负责自研 Kubernetes，底层资源编排仍复用 Kubernetes。
2. 不负责自研 Tekton，构建执行仍由 Tekton Pipeline / PipelineRun 承接。
3. 不负责自研 Rollouts 控制器，持续发布底座依赖 Argo Rollouts / 内部 Rollouts 能力。
4. 不把 `sae-api` 说成面向前端的 HTTP API，它本质是 SAE 领域 CRD、typed client、informer、lister 和 controller 契约。
5. 不把 `watcher` 说成用户操作入口。`console` 处理用户要做什么，`watcher` 处理集群实际发生了什么。

# 项目整体架构

SAE 的架构拆分核心是：用户动作走 `console` 同步控制面，应用领域对象由 `sae-api` 定义和调谐，构建交给 Tekton，发布交给 Rollouts，运行态变化交给 watcher，周期性补偿交给 job，底层资源访问通过 `ClusterManager` 和 `pkg/sae` 收敛。这样拆的原因是应用交付链路长、外部系统多、状态变化异步，如果全部塞进一次 HTTP 请求，会导致请求阻塞、状态不可补偿，也会让底层平台差异扩散到上层。

## 总体架构图

<img src="https://cdn.nlark.com/yuque/__mermaid_v3/db821895e0edeeb5ee52ea438b052507.svg" width="1277" title="" crop="0,0,1,1" id="FBq9d" class="ne-image">

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778555224681-02cc3037-69d1-4382-bc0e-aab66ab87916.png" width="1332" title="" crop="0,0,1,1" id="u95d27ae7" class="ne-image">

## 这张图怎么讲

+ **入口层**：控制台用户、OpenAPI、MCP / Agent 调用方都进入 `sae-console`。
+ **同步控制面**：`cmd/console/main.go` 启动主 API 服务，初始化配置、MySQL、Redis、OpenTelemetry、GitLab client、K8sWatcher、ClusterWatcher、PipelineManager，再由 `cmd/console/routes/routemanager.go` 注册 `/api/v1/*`、`/open/api/v1/*`、`/mcp/v1/*` 等路由。
+ **领域资源契约层**：`sae-api` 定义 `Application`、`Cluster`、`Zone`、`Tenant` 等 CRD，并生成 typed client、informer、lister 和 controller。
+ **领域编排层**：`sae-console/pkg/sae` 消费 `sae-api` 和 Kubernetes client，封装应用创建、Rollout、Pipeline、ClusterManager、ResourceVerber、Ingress、Gateway、弹性等能力。
+ **异步状态面**：`cmd/watcher/main.go` 默认启用 Event watcher 与 Replicas watcher，可通过配置启用 PipelineRun watcher 和 Rollout notification。
+ **补偿任务面**：`cmd/job/main.go` 启动 `saejob`，用于周期性、一次性、补偿类任务。
+ **底座层**：Kubernetes 承载真实工作负载，Tekton 承载构建，Rollouts 承载灰度发布，GitLab / Harbor 承载代码与镜像，MySQL / Redis / 通知 / 指标系统承载控制面状态。

## 架构选型如何服务治理

| 层次 | 主要选型 / 代码锚点 | 面试表达 |
| --- | --- | --- |
| 同步控制面 | `cmd/console/main.go`、`cmd/console/routes/routemanager.go` | 面向用户和自动化入口，负责 API、权限、审计、编排和查询 |
| 领域资源模型 | `sae-api/apis/apps/v1/Application`、`sae-api/apis/core/v1/Cluster` | 把 SAE 应用和集群变成 Kubernetes 原生可声明、可 watch、可调谐的资源 |
| 领域编排层 | `sae-console/pkg/sae`、`ClusterManager`、`PipelineManager` | 统一多集群 client、Pipeline、Rollout、Application 和通用资源访问 |
| 持续构建 | Tekton Pipeline / PipelineRun | 构建执行交给 Tekton，平台负责触发、状态、历史、日志和治理 |
| 持续发布 | Rollouts | 发布执行交给 Rollouts，平台负责策略、进度、通知、回滚和治理 |
| 异步状态面 | `cmd/watcher/main.go`、`pkg/sae/watcher/watcher.go` | 监听集群事实并回写状态、事件、通知和清理结果 |
| 补偿任务面 | `cmd/job/main.go` | 承接定时重检、引用修复、历史数据修复等批处理任务 |

# 项目核心问题

## 统一入口问题

SAE 面对的是研发完整交付流程，而不是单一 Kubernetes 对象。应用创建、构建、发布、回滚、扩缩容、日志、事件、诊断、权限、审计、OpenAPI、MCP / Agent 都需要统一入口。

难点在于底层能力分散：Kubernetes、Tekton、Rollouts、GitLab、Harbor、Prometheus、通知系统都有自己的模型和状态。如果直接暴露给研发，会形成多套操作手册。

SAE 的治理方式是用 `sae-console` 作为统一控制面，将底层资源和外部系统封装成面向应用生命周期的操作语义。

## 应用领域模型问题

如果应用只存在 MySQL 里，平台很难利用 Kubernetes 的 watch、status、RBAC、controller 和 reconcile 能力。

难点在于 SAE 的“应用”不是单个 Deployment，它还包含负责人、环境、多集群映射、镜像、资源、仓库、Ingress、环境变量、卷、探针、Service 等平台语义。

SAE 通过 `sae-api` 定义 `Application` CRD，将应用期望状态声明化；`ApplicationReconciler` 根据 `Application.spec` 创建 Deployment、Service、Ingress，并通过 condition 表达状态。

## 多集群治理问题

SAE 需要纳管多个 Kubernetes 集群，应用可能存在主集群和目标集群的映射关系。

难点在于每个请求里临时解析 kubeconfig 和创建 client 会造成性能、稳定性和权限管理问题；多集群发布还涉及镜像、资源、Rollout 配置同步。

SAE 通过 `Cluster` CRD 表达纳管集群，通过 `ClusterManager` watch `clusters.core.sae`，为每个集群维护 kubeClient、dynamicClient、saeClient、apiExtensionsClient 等访问能力；`sae-api/pkg/apps/SyncManager` 负责多集群运行态同步。

## 持续发布治理问题

应用发布不是简单改镜像，它涉及构建、审批、质量校验、发布时间窗口、灰度步骤、暂停、继续、回滚、状态观测和通知。

难点在于发布过程长、状态变化异步、失败原因来自多个系统，不能只靠同步 API 返回。

SAE 把发布执行交给 Tekton 和 Rollouts，控制面负责发布单、策略、流程、权限和查询；watcher 负责 PipelineRun、Rollout、Deployment 等真实状态回写和通知。

## 状态一致性问题

应用、构建、发布、Pod、事件、副本数、Rollout 进度都在持续变化。

难点在于平台数据库、Kubernetes 运行态、Tekton 状态、Rollout 状态和通知记录可能漂移。

SAE 通过 `console + watcher + saejob` 分层治理：`console` 写入期望状态和业务记录，`watcher` 同步运行态和事件，`saejob` 做周期性补偿与修复。

# 核心专题

面试时不需要把所有源码模块逐个讲完。建议主动讲前三个专题，后面的作为追问补强。

推荐主讲顺序：

1. 应用交付控制面统一
2. `sae-api` 领域资源模型与 CRD 契约
3. 同步控制面与异步状态面分层

备讲专题：

4. 持续构建与持续发布治理
5. 多集群资源编排
6. 稳定性与可观测治理

## 应用交付控制面统一

**背景**

研发日常交付涉及应用、构建、镜像、发布、回滚、日志、事件、指标、权限、审计等多个系统。

**问题**

如果每个能力都直接暴露底层入口，研发需要理解 Kubernetes、Tekton、Rollouts、GitLab、Harbor、Prometheus 等系统的原生模型，接入和排障成本很高。

**方案**

`sae-console` 作为统一控制面，通过 `routes.NewRouteManager(...).Run()` 注册应用、发布、Pipeline、Rollout、Cluster、Workload、Events、Metrics、Quality、Diagnosis、OpenAPI、MCP 等路由，将底层动作收敛为应用交付语义。

**收益**

研发不需要直接面对各底座系统的原生复杂度，平台也能统一权限、审计、质量校验、发布窗口和排障入口。

**面试展开话术**

SAE 的核心不是给 Kubernetes 套一层页面，而是把研发交付动作产品化。用户想做的是“发布一个应用、看发布进度、失败了怎么排查”，而不是直接操作 Deployment、PipelineRun、Rollout 和 Event。

## 领域资源模型与 CRD 契约

**背景**

SAE 需要表达应用、集群、可用区、租户等平台对象，并让这些对象被控制面、watcher、controller 和多集群编排代码复用。

**问题**

如果只靠数据库表保存平台状态，缺少 Kubernetes 原生的声明式、watch、status、RBAC 和 reconcile 能力；如果每个服务都手写 dynamic client，又会导致资源路径和字段口径分散。

**方案**

`sae-api` 独立定义 `Application`、`Cluster`、`Zone`、`Tenant` 等 CRD，提供 `config/crd/bases/*`、`client/clientset`、`client/informers`、`client/listers` 和 controller-runtime reconciler。`ApplicationSpec` 中沉淀副本、环境、负责人、多集群映射、WorkloadRef、镜像、资源、仓库、Ingress、环境变量、卷、探针、Service 等字段。

**收益**

SAE 的业务对象可以被 Kubernetes 存储、watch 和调谐；`sae-console`、watcher 和后台任务可以用 typed client 访问 SAE 原生资源，减少手写资源路径和字段拼接。

**面试展开话术**

`sae-api` 名字里有 API，但它不是前端直接调用的 HTTP 服务。它更像 SAE 的领域资源协议层：规定 Application 和 Cluster 长什么样、如何被 watch、如何被 controller 调谐。

## 同步控制面与异步状态面分层

**背景**

应用交付链路里有很多长生命周期动作：构建、发布、灰度推进、事件沉淀、副本同步、PipelineRun 清理、长时间 Rollout 提醒。

**问题**

这些动作不适合放在一次 HTTP 请求里同步完成，否则会拖慢控制面，也会让后台抖动影响用户请求。

**方案**

`console` 只处理用户动作、参数校验、业务编排和期望状态写入；`watcher` 通过 Event watcher、Replicas watcher、PipelineRun watcher、Rollout notification 持续同步运行态；`saejob` 承接定时补偿和批处理。

**收益**

请求延迟和后台状态同步被隔离。控制面可以快速响应用户，watcher 和 job 负责最终一致性、事件留痕、通知和资源清理。

**面试展开话术**

我会用“用户要做什么”和“集群实际发生了什么”来解释边界：`console` 管前者，`watcher` 管后者。

## 持续构建与持续发布治理

**背景**

一次发布可能从 GitLab 分支、tag、commit 开始，经过 Tekton 构建镜像，再通过 Rollouts 做灰度和回滚。

**问题**

构建和发布状态来自不同系统，失败原因也可能来自代码、镜像、Pipeline、Rollout、Pod 或网络。

**方案**

`controller/pipeline` 与 `pkg/sae/pipeline` 封装 Tekton Pipeline / PipelineRun；`controller/rollouts` 与 `pkg/sae/rollouts` 封装 Rollout 查询、暂停、继续、promote、abort、rollback、set image、canary rate 等动作；watcher 同步 PipelineRun 和 Rollout 状态。

**收益**

构建、发布、灰度、回滚、通知和排障被纳入统一流程，研发不需要分别去 Tekton、Rollouts 和 Kubernetes 中拼状态。

## 多集群资源编排

**背景**

SAE 需要管理多个 Kubernetes 集群，并支持应用在不同集群之间的绑定、同步、迁移和发布。

**问题**

多集群场景下，client 初始化、资源版本、Rollout 配置、镜像、资源规格和目标集群运行态都可能不一致。

**方案**

`ClusterManager` watch `Cluster` CRD，解析 `cluster.spec.kubeConfig`，为每个集群维护 kubeClient、dynamicClient、saeClient、apiExtensionsClient；`sae-api/pkg/apps/SyncManager` 通过 ReplicaSet / Rollout / Deployment 等 watcher，在合适时机同步主集群和目标集群的镜像、资源和 Rollout 配置。

**收益**

多集群访问能力被集中维护，应用同步逻辑有统一入口，避免每个 controller 重复处理集群连接和资源映射。

## 稳定性与可观测治理

**背景**

SAE 不只负责发布，还要帮助研发发现问题、定位问题和治理风险。

**问题**

线上故障往往跨越应用、Pod、事件、日志、指标、发布记录和通知链路。如果平台只提供发布入口，排障仍然会回到人工拼系统。

**方案**

SAE 集成事件中心、通知器、Prometheus / 指标、日志、WebShell、Profile、诊断、审计、质量校验等能力。文档中提到的一键火焰图、应用健康分、POD AI 诊断，都应归到稳定性与运行治理能力，而不是发布功能列表。

**收益**

SAE 从“发布平台”升级为“交付与运行治理平台”，既能发版，也能观测、诊断、通知和沉淀治理规则。

# 深水区

这里的内容用于追问展开，不放在开场主线里。面试先讲平台价值、架构分层和治理问题；只有被追问实现细节时，再进入代码路径和组件边界。

## `sae-console` 仓库入口程序

当前 `sae-console` 仓库可见 7 个 `main.go` 入口：

| 入口 | 路径 | 定位 |
| --- | --- | --- |
| `console` | `cmd/console/main.go` | 主 API 控制面，承接页面、OpenAPI、MCP / Agent |
| `watcher` | `cmd/watcher/main.go` | 异步状态面，监听事件、副本、PipelineRun、Rollout 通知 |
| `saejob` | `cmd/job/main.go` | 批处理和补偿任务入口 |
| `pod` | `cmd/pod/main.go` | Pod 专项服务入口 |
| `nas` | `cmd/nas/main.go` | NAS / 存储专项服务入口 |
| `saectl` | `cmd/saectl/main.go` | 运维 CLI，用于集群注册 / 纳管等 |
| `clone-batch` | `cmd/clone-batch/main.go` | 批量克隆 / 迁移辅助工具 |

主链路不要讲成 7 个入口都同等重要。面试主线是 `console + sae-api + watcher + saejob + K8s/Tekton/Rollouts`。

## `console` 启动与路由

`cmd/console/main.go` 启动时会初始化配置、Aquarius、OpenTelemetry、MySQL、Redis、NodePool、Java Collector、白名单、OBS Agent、GitLab client、K8sWatcher、ClusterWatcher、PipelineManager、Redis cache 和 OpsFilter，最后调用 `routes.NewRouteManager(...).Run()`。

`cmd/console/routes/routemanager.go` 注册的重点不是“有多少接口”，而是它把应用、发布、Rollout、Pipeline、Cluster、Workload、Events、Metrics、Migration、Quality、Diagnosis、OpenAPI、MCP 等域组织进统一控制面。

## `sae-api` CRD 与 controller

`sae-api` 当前核心交付物：

| 类型 | 代码 / 资源 | 作用 |
| --- | --- | --- |
| Application CRD | `apis/apps/v1/application_types.go`、`config/crd/bases/apps.sae_applications.yaml` | 表达 SAE 应用期望状态 |
| Cluster CRD | `apis/core/v1/cluster_types.go`、`config/crd/bases/core.sae_clusters.yaml` | 表达纳管集群和 kubeconfig |
| Zone CRD | `apis/core/v1/zone_types.go` | 承载可用区类平台元信息 |
| Tenant CRD | `apis/core.sae/v1/tenant_types.go` | 承载租户类平台元信息 |
| generated client | `client/clientset`、`client/informers`、`client/listers` | typed client、informer、lister |
| controller-runtime | `main.go`、`controllers/apps`、`controllers/core` | 启动 manager 和 reconciler |

`ApplicationReconciler` 会监听 `Application`，在 Progressing 且存在 `WorkloadRef` 时创建 Deployment，并根据声明创建 Service、Ingress，补默认 liveness / readiness probe，最终通过 condition 表达状态。

`ApplicationReconciler.SetupWithManager()` 会启动 `SyncManager.Run(context.Background())` 和 OpenKruise manager，再注册 `For(&appsv1.Application{})`。

## watcher 能力边界

`pkg/sae/watcher/watcher.go` 里的 `K8sWatcher` 是异步能力装配器：

| 方法 | 实际能力 | 作用 |
| --- | --- | --- |
| `EnableClusterWatcher()` | `pkg/sae/core/cluster` | 初始化多集群 client 缓存 |
| `EnableAppWatcher()` | `pkg/sae/apps` | watch `Application` 并同步应用信息 |
| `EnableEventWatcher()` | `pkg/sae/core/event` | watch Kubernetes Event，落库、订阅、通知 |
| `EnableReplicasWatcher()` | `pkg/sae/rollouts` | watch Rollout / Deployment 副本状态 |
| `EnablePipelineRunWatcher()` | `pkg/sae/pipeline` | watch Tekton PipelineRun，更新构建历史并清理资源 |
| `EnableRolloutNotify()` | `pkg/sae/rollouts/notify` | 扫描长时间 Progress 的 Rollout 并发送提醒 |

注意：`cmd/watcher/main.go` 默认启用 Event watcher 和 Replicas watcher；Rollout notification 由 `EnableRolloutNotification()` 控制；PipelineRun watcher 由 `--enablePipelineRun` 或 `enablePipelineRun=true` 控制。`ClusterWatcher` 主要在 `console`、`pod`、`saejob` 等启动时用于初始化多集群 client。

## `sae-api` SyncManager

`sae-api/pkg/apps/SyncManager` 创建 ClusterWatcher、ApplicationWatcher、DeploymentWatcher、ReplicaSetWatcher、RolloutWatcher 等能力。当前 `Run()` 重点启动 `syncSae`。

`syncSae` 通过 ReplicaSet 变化触发同步：当旧 ReplicaSet 副本归零且属于 Rollout 控制时，找到对应 Application；如果 `Application.spec.clusters` 存在多集群配置，就同步主集群与目标集群的镜像、资源和 Rollout 配置。同步时会处理 paused、grayReplicas 等状态，避免目标集群卡在灰度态。

## 典型链路

### 应用创建链路

1. 用户或 Agent 调用应用创建接口。
2. `controller/application` 校验应用名、团队、负责人、仓库、集群、环境等参数。
3. `pkg/sae/apps.CreateApp()` 创建 `Application` CRD，并写入应用 MySQL 元数据。
4. `sae-api` Application controller 监听到 CRD 后创建 Deployment / Service / Ingress。
5. watcher 后续监听副本和事件，把运行态回写到 DB 与事件中心。

### 发布链路

1. 用户提交发布申请或快速发布。
2. `controller/application/deploy.go` 记录发布单，执行白名单、时间窗口、质量校验等规则。
3. 需要构建时通过 `controller/pipeline` 触发 Tekton PipelineRun。
4. 需要发布时更新 Deployment 或 Rollout 镜像 / 灰度策略。
5. watcher 监听 PipelineRun、Rollout、Deployment 状态，回写发布状态、发送通知、清理历史资源。

### 排障查询链路

1. 页面或 Agent 查询 Pod、日志、事件、指标、诊断。
2. `controller/workload` 通过 `ClusterManager` 找到目标集群 client。
3. 查询 K8s Pod / Event / Deployment / ReplicaSet / PVC / ConfigMap 等资源。
4. 日志、WebShell、Profile、Prometheus 指标、启动诊断分别走对应 controller 和外部系统。

## 代码锚点

+ 主 API 入口：`sae-console/cmd/console/main.go`
+ 路由汇聚：`sae-console/cmd/console/routes/routemanager.go`
+ 应用控制器：`sae-console/controller/application`
+ 发布控制器：`sae-console/controller/application/deploy.go`
+ Rollout 控制器：`sae-console/controller/rollouts`
+ Pipeline 控制器：`sae-console/controller/pipeline`、`sae-console/pkg/sae/pipeline`
+ Workload / 排障：`sae-console/controller/workload`
+ watcher 入口：`sae-console/cmd/watcher/main.go`
+ watcher 装配器：`sae-console/pkg/sae/watcher/watcher.go`
+ 多集群管理：`sae-console/pkg/sae/core/cluster/manager.go`
+ 应用 CRD：`sae-api/apis/apps/v1/application_types.go`
+ 集群 CRD：`sae-api/apis/core/v1/cluster_types.go`
+ Application reconciler：`sae-api/controllers/apps/application_controller.go`
+ SyncManager：`sae-api/pkg/apps/syncManager.go`、`sae-api/pkg/apps/syncSae.go`

# 高频追问

## 高频面试问题与推荐回答

### SAE 是什么，不是什么？

SAE 是公司内部应用交付与运行治理控制面，不是简单 Kubernetes Portal。它复用 Kubernetes、Tekton、Rollouts 等底座能力，对上收敛应用交付、发布、回滚、排障、观测和自动化入口。

### `sae-console` 和 `sae-api` 的关系是什么？

`sae-console` 是用户请求入口和业务编排层；`sae-api` 是 SAE 领域资源模型和 Kubernetes API 扩展层。`console` 决定用户要做什么，`sae-api` 规定 Application / Cluster 等资源长什么样、如何被 watch 和调谐。

### 为什么要有 `sae-api`，只用 MySQL 不行吗？

MySQL 适合业务查询和记录，但不适合声明式资源调谐。`sae-api` 把 SAE 应用和集群变成 CRD，获得 Kubernetes 的 watch、status、RBAC、controller 和 typed client 能力。

### 为什么要拆 `console` 和 `watcher`？

`console` 处理用户动作和同步编排，`watcher` 处理集群事实和异步状态同步。发布、构建、事件、副本变化都有长生命周期，不能全部塞进 HTTP 请求。

### SAE 是不是自研发布系统？

不是从零自研发布控制器。SAE 复用 Tekton 做构建、复用 Rollouts 做灰度发布，平台负责流程编排、权限、发布记录、策略、状态观测、通知和排障。

### 多集群怎么治理？

通过 `Cluster` CRD 表达纳管集群，通过 `ClusterManager` watch 集群资源并维护多集群 client 池，通过 `SyncManager` 和应用多集群配置同步镜像、资源和 Rollout 配置。

### `watcher` 挂了怎么办？

watcher 是异步状态面，应该结合事件监听和周期性补偿。事件监听用于及时同步，job / 定时任务用于修复事件丢失、进程重启或状态漂移。

### SAE 和普通 Kubernetes Portal 的区别？

普通 Portal 更偏资源 CRUD。SAE 的重点是以应用交付为中心，将构建、发布、灰度、回滚、事件、日志、指标、通知和治理规则串成完整生命周期。

## 风险问题

+ 不要说 SAE 自研了 Kubernetes。
+ 不要说 SAE 自研了 Tekton 或 Rollouts。
+ 不要把 `sae-api` 说成前端 HTTP API。
+ 不要把 watcher 说成用户操作入口。
+ 不要把所有能力都说成自己负责，重点讲控制面、编排、状态同步、运行治理。
+ 不要主动展开过多路由和 controller 文件路径，除非面试官追问实现细节。

## 哪些不要展开

+ 不要一上来讲 `/api/v1/*` 路由清单。
+ 不要把 7 个可执行入口平铺成主线。
+ 不要把 `cmd/pod`、`cmd/nas`、`clone-batch` 讲成核心链路。
+ 不要把 CRD 字段逐个背诵，重点讲为什么需要领域资源模型。
+ 不要把稳定性能力讲成零散工具，要归到运行治理和排障闭环。

# 简历口径

## 推荐简历片段

Soul Application Engine｜应用交付与运行治理平台

面向公司内部研发和运维场景的应用交付控制面，统一承接应用创建、构建流水线、灰度发布、回滚、运行观测、事件通知和排障诊断能力，底层复用 Kubernetes、Tekton、Rollouts、GitLab / Harbor 等基础设施。

+ 参与 SAE 后端控制面建设，围绕 `sae-console` 统一收口应用管理、发布、Pipeline、Rollout、Workload、事件、指标、诊断、OpenAPI 和 MCP / Agent 等平台入口。
+ 基于 `sae-api` 的 Application / Cluster 等 CRD 契约，参与应用生命周期治理和多集群资源编排，将应用期望状态、集群访问和底层 Kubernetes 资源调谐纳入统一平台模型。
+ 参与持续构建与持续发布治理，封装 Tekton PipelineRun 和 Rollouts 灰度发布能力，支撑发布申请、质量校验、发布窗口、暂停 / 继续、回滚、状态观测和通知等流程。
+ 建设异步状态同步与补偿链路，通过 watcher 同步 Event、Replicas、PipelineRun、Rollout 等运行态，提升发布进度、构建状态、事件留痕和副本状态的一致性。
+ 补齐运行治理和排障能力，包括日志、事件、指标、WebShell、Profile、POD 诊断、通知和审计等能力，降低研发直接面对底层云原生组件的复杂度。

## 简历风险控制

如果写“控制面建设”，面试要能讲清 `console`、`watcher`、`sae-api` 的边界。

如果写“持续发布治理”，不要说自研 Rollouts，要说平台封装和治理 Rollouts 能力。

如果写“多集群治理”，要准备 `Cluster` CRD、`ClusterManager` 和多集群 client 池的关系。

如果写“异步状态同步”，要准备 watcher 默认启用哪些能力，以及哪些能力由环境变量或参数控制。

# 面试使用方式

## 主动讲的内容

面试开场优先讲：

1. SAE 是应用交付与运行治理控制面。
2. 它解决统一入口、应用生命周期、持续发布、多集群和状态一致性问题。
3. 核心架构是 `console + sae-api + watcher + saejob + K8s/Tekton/Rollouts`。
4. 你的职责边界在平台控制面、领域编排和运行治理，不是底层引擎自研。

## 被追问再展开的内容

以下内容不要主动讲太深：

1. `cmd/console/routes` 的具体路由清单。
2. `ApplicationSpec` 的全部字段。
3. PipelineRun watcher 和 Rollout notification 的具体状态推进细节。
4. `cmd/pod`、`cmd/nas`、`clone-batch` 这类专项入口。

## 必须守住的边界

1. SAE 不是自研 Kubernetes。
2. SAE 不是自研 Tekton。
3. SAE 不是自研 Rollouts。
4. `sae-api` 不是前端 HTTP API。
5. `watcher` 不是用户操作入口。

# 一句话收尾

我在 SAE 项目里会强调的核心价值，是把公司内部应用交付和运行治理从分散的云原生组件中收敛出来：`console` 负责统一入口和业务编排，`sae-api` 负责领域资源契约和调谐，`watcher` 和 `saejob` 负责异步状态同步与补偿，底层复用 Kubernetes、Tekton 和 Rollouts，最终让研发通过一个平台完成应用创建、构建、发布、回滚、观测和排障。
