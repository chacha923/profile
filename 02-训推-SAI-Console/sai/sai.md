# SAI-Console 项目总结

说明：本文按 `interview-project-doc` 组织，目标是面试表达材料，不是源码导览。图片和核心代码段落暂时保留，深水区用于承接追问展开。

面试主线不要从代码路径、接口实现、贝联网络细节开始。先讲项目定位、核心问题、架构分层和治理能力；只有被追问时，再进入深水区。

---

# 项目定位（90 秒开场）

SAI-Console 是面向算法、模型服务和平台运维团队的 AI 工作负载运行托管与治理平台。它不是单纯的控制台后端，而是把训练任务、推理服务、模型制品、GPU 资源池、多云托管服务和运行观测收敛到统一入口，让算法同学不需要分别理解 KServe、PAI、贝联、火山、TFJob、CronJob 和不同集群的运行差异。

这个平台的核心价值不是多做几个页面或接口，而是把异构 AI 工作负载纳入统一生命周期管理：创建、发布、伸缩、重启、迁移、状态同步、日志、事件、资源池和排障入口都由平台统一治理。底层可以是 Kubernetes 原生工作负载，也可以是云厂商托管服务，用户侧看到的是统一服务画像和统一运维动作。

我主要负责 SAI 后端控制面和平台运行治理相关工作，包括训练 / 推理任务生命周期管理、多云推理服务托管、GPU 资源池抽象、TFJob 训练任务接入、watcher 状态同步、模型制品异步处理，以及大模型推理场景下平台侧运行治理适配。我的职责边界主要在平台控制面、资源治理和运行态治理，不涉及自研训练框架、推理引擎或 GPU Scheduler。

---

# 我的职责与边界

## 我主要负责的部分

### 控制面建设

负责 SAI 后端控制面能力建设，收口训练任务、推理服务、模型制品、资源池和第三方托管服务的创建、变更、查询、状态同步和运维入口。

面试表达：

我做的不是单个接口，而是把算法工作负载常见动作收敛到统一控制面，比如创建、发布、变配、伸缩、重启、迁移、日志、事件和状态查询。

### AI 工作负载生命周期治理

统一训练、推理、Cron、Nuclio、模型下载等不同运行形态的生命周期动作，包括创建、伸缩、重启、迁移、状态查询、日志、事件和运行态补偿。

面试表达：

不同工作负载底层形态不同，但平台侧需要统一生命周期语义，否则用户要分别理解多套系统。

### GPU 资源池与资源治理

通过 NodePool / ResourceGroup 抽象 GPU 独占、共享显存、抢占 GPU、CPU 等资源形态，将底层节点标签、污点容忍和 GPU 插件字段收敛成平台资源池选择。

面试表达：

我们不是自研 Scheduler，而是把调度意图产品化。用户选择资源池，平台生成 PodSpec，最终调度仍然交给 Kubernetes scheduler 和底层 GPU 插件。

### 多云推理服务托管

适配 ACK/KServe、PAI EAS、火山、贝联等不同推理托管形态，对上提供统一的服务规格、实例状态、扩缩容、重启、迁移和状态同步能力。

面试表达：

多云托管最难的不是调用 API，而是状态语义、资源规格、日志事件、扩缩容和网络接入口径对齐。

### 状态同步与补偿链路

通过 watcher / Sync 处理训练任务、定时任务、FAISS 任务和第三方推理服务的运行态变化，解决平台元数据和真实运行态不一致的问题。

面试表达：

SAI 里的很多任务是长周期任务，不能只靠 API 同步返回。watcher 和 Sync 负责最终一致性和状态补偿。

### 大模型推理平台侧适配

在 PD 分离等大模型推理场景下，参与平台侧运行治理适配，重点是多组件服务表达、GPU 资源池划分、状态聚合、扩缩容入口和观测口径，不涉及底层推理引擎实现。

面试表达：

PD 分离不是我实现的推理引擎逻辑。我参与的是平台侧运行治理适配，让 Prefill / Decode 这类多组件推理形态可以纳入统一服务托管体系。

## 我不负责的部分

1. 不负责自研训练框架，底层训练能力主要复用 TFJob / Training Operator 等 Runtime。
2. 不负责自研推理引擎，底层推理能力主要来自 KServe、Triton、PAI、贝联等服务。
3. 不负责自研 GPU Scheduler，平台侧主要做资源池抽象、准入校验和 PodSpec 生成，最终调度仍由 Kubernetes scheduler 和 GPU 插件完成。
4. 不负责 PD 分离推理引擎实现，平台侧只做运行治理、资源池、状态和观测入口适配。
5. 不把模型下载能力包装成完整 Model Registry。这里更多是模型制品进入平台、落盘、挂载和复用的基础治理能力。

---

# 项目整体架构

SAI-Console 的架构拆分核心是：短链路动作走控制面，同步返回；长周期状态变化交给 watcher 和 Sync；重任务交给 Job Runtime；底层差异交给适配层；资源、网络、发布、观测都以 Runtime 视角统一治理。

这样拆的原因是 AI 工作负载本身生命周期长、底座异构、状态来源多。如果所有逻辑都放在一个 HTTP 请求里，会导致请求阻塞、状态不可补偿，也会让多云差异扩散到上层。

## 系统架构图

<img src="https://cdn.nlark.com/yuque/__mermaid_v3/719cfbd44e7f366e7fdf5e83a964abab.svg" width="1573" title="" crop="0,0,1,1" id="PoMU0" class="ne-image">

## 这张图该怎么讲

+ **同步控制面**：承接控制台和自动化系统，负责统一 API、鉴权、参数校验、生命周期动作和平台状态写入。
+ **异步状态同步层**：通过 watcher / Sync 监听训练任务、定时任务、FAISS 任务和第三方托管服务状态，处理运行态回写和状态补偿。
+ **长耗时 Job Runtime**：承接 Hugging Face 下载、OSS 下载、制品上传等不可放入同步 API 的任务。
+ **底座适配层**：隔离 ACK/KServe、PAI、火山、贝联等不同托管形态的 API、资源模型、状态语义和运维动作差异。
+ **资源治理层**：通过 NodePool / ResourceGroup 抽象 GPU 独占、共享显存、抢占池和 CPU 池，把调度意图产品化。
+ **发布与网络治理层**：复用 SAE、Gateway、Envoy、Argo Rollouts、Tekton 等底座能力，承接灰度、构建、网络接入和跨平台流程。

## 思维导图

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777433815648-164cbdd4-90b3-4f16-bb13-e7fc7b48251d.png" width="1536" title="" crop="0,0,1,1" id="lb4pr" class="ne-image">

## 架构选型如何服务治理

| 层次 | 主要选型 | 面试表达 |
| --- | --- | --- |
| 控制面 | Go 1.22、Gin、GORM + MySQL、Redis Session | 负责统一入口、权限、参数、编排和平台状态 |
| AI Runtime | Kubernetes client-go、KServe、Training Operator | 承接推理、训练、Cron、FAISS 等异构工作负载 |
| 发布与构建 | Tekton、Argo Rollouts | 把构建、发布、灰度纳入平台治理 |
| 资源治理 | NodePool / ResourceGroup、`nodeSelector`、`tolerations`、`nvidia.com/gpu`、`aliyun.com/gpu-mem` | 把调度意图产品化，不自研 Scheduler |
| 可观测 | OpenTelemetry、Prometheus `/metrics`、日志、事件 | 统一排障入口和运行态观测 |
| 外部平台 | 阿里云 PAI（EAS/DLC）、火山、贝联（LcComputing） | 多云与外部托管平台通过适配层收敛 |

---

# 项目核心问题

## 异构 AI 工作负载如何统一托管

SAI 承接的不是单一工作负载，而是一批运行形态不同的 AI 工作负载：在线推理服务、TFJob 训练任务、CronJob 周期任务、Nuclio Function、FAISS Build、模型下载 Job，以及 PAI、火山、贝联等第三方托管服务。

难点不在于创建某一个对象，而在于这些工作负载底层形态不同、状态语义不同、资源模型不同、运维动作不同。平台如果逐个暴露底层能力，用户需要理解多套系统。

SAI 的治理方式是建立统一服务画像和统一生命周期动作，把创建、变更、伸缩、重启、迁移、状态、日志、事件、资源池和存储挂载收敛到统一控制面。

## 长周期运行态如何保持一致

AI 工作负载通常不是一次 API 调用就结束。训练任务会持续运行，CronJob 会周期触发，模型下载耗时不可控，第三方推理服务状态还可能和平台数据库漂移。

如果所有逻辑都放在同步 API 中，会导致请求阻塞；如果只记录数据库状态，又容易和真实运行态不一致。

SAI 通过同步控制面、watcher / Sync 和 Job Runtime 分层解决这个问题：server 负责用户动作和初始编排，watcher / Sync 负责异步状态同步和补偿，Job Runtime 负责模型下载、制品处理等长耗时任务。

## GPU 异构资源如何治理

训练、推理、FAISS Build、模型下载等任务会共同使用 GPU 和 CPU 资源。GPU 成本高、资源池敏感，如果让用户直接填写节点标签、污点容忍和 GPU 插件字段，很容易误用资源池，也不利于后续成本和稳定性治理。

SAI 通过 NodePool / ResourceGroup 抽象 GPU 独占、共享显存、抢占 GPU、CPU 等资源形态。用户选择的是业务语义上的资源池，平台负责转换为 PodSpec、资源 limits、nodeSelector 和 tolerations，最终调度仍交给 Kubernetes scheduler 和底层 GPU 插件。

## 多云推理和第三方托管如何收敛差异

推理服务不只运行在一个 Kubernetes 集群里，还包括 ACK/KServe、PAI EAS、火山、贝联等不同托管形态。它们的 API、资源规格、状态、日志、扩缩容、迁移和网络接入方式都不一样。

SAI 的处理方式是把上层服务语义稳定住，对用户提供统一的服务规格、实例状态、扩缩容、重启、迁移、日志和事件入口；底层差异放到平台适配层处理。这样新增云厂商或托管平台时，主要扩展底层适配，不打散用户操作流程。

---

# 核心专题

面试时不要 6 个专题都主动展开。通常主动讲前 3 个，后 3 个用于追问补强。

推荐主讲顺序：

1. AI 工作负载 Runtime 统一
2. GPU 资源池与资源治理
3. 生命周期与状态一致性治理

备讲专题：

4. 多云推理服务托管
5. PD 分离平台侧适配
6. 长耗时任务异步化

---

## AI 工作负载 Runtime 统一：异构训练、推理与任务托管

### 背景

SAI 需要同时托管 KServe/Triton、PAI EAS、火山推理、贝联 LcComputing、TFJob/Cron TFJob、Nuclio Function、FAISS Build 和模型下载 Job。

这些工作负载的底层形态差异很大：有的是 Kubernetes CRD，有的是外部托管平台，有的是事件驱动任务，有的是离线 Job，有的是长周期训练任务。

### 问题

如果用户需要分别理解 KServe、PAI、贝联、TFJob、CronJob、Nuclio 和模型下载 Job，就会形成多套操作手册。控制台和自动化系统也会被底层 Runtime 绑定，后续新增托管平台或迁移云厂商都会很困难。

真正难点不是创建某个对象，而是统一这些 Runtime 的状态、资源、日志、事件和运维动作。

### 方案

SAI 通过统一服务画像和统一生命周期动作来收敛不同 Runtime：

1. **统一服务画像**  
   用 `cloud_provider`、`serve_runtime`、`model_format`、`node_pool` 等元数据描述服务来源、运行时、模型形态和资源池。

2. **统一运维动作**  
   创建、发布、扩缩容、重启、迁移、变配、状态查询、日志、事件、Pod 查询等动作对上保持统一语义。

3. **统一资源与存储口径**  
   Nuclio、TFJob、FAISS、模型下载等非推理工作负载也复用 NodePool、存储挂载和 watcher 状态同步能力。

4. **底层差异集中适配**  
   ACK/KServe、PAI、贝联等不同底座差异放到底层适配层处理，不让控制台和用户流程被厂商模型打散。

### 收益

底层服务形态可以异构，上层运维体验保持一致。新增托管平台或工作负载类型时，主要扩展底层适配和 Runtime 处理逻辑，不需要重做控制台主流程。

### 面试展开话术

可以这样说：

我们不是单纯做一个 TFJob 页面，而是把训练、推理、serverless、Cron 和模型下载这些不同运行形态统一到一个 AI 工作负载 Runtime 里。底层可能是 KServe、PAI、贝联，也可能是 TFJob 或 Kubernetes Job，但用户看到的是统一的服务画像、资源池、日志事件和运维动作。

### 高频追问

**Q：你们是不是自研了 AI Runtime？**

答：

不是自研训练框架或推理引擎。这里说的 Runtime 是平台侧运行治理抽象。底层仍然复用 KServe、Training Operator、Kubernetes Job、PAI、贝联等能力。SAI 负责统一入口、资源池、状态同步、日志事件和运维动作。

---

## GPU 资源池与资源治理：把调度意图产品化

### 背景

算法平台里既有高优先级在线推理，也有训练、FAISS Build、模型下载等离线或批处理任务。GPU 资源昂贵，不能只靠人工指定机器。

### 问题

如果平台直接暴露节点标签、污点、资源字段，用户需要理解 Kubernetes 调度细节和厂商 GPU 插件差异。共享显存、独占卡、抢占池和 CPU 池也容易被误用。

常见风险包括：

1. 离线任务误用在线推理资源池。
2. 小模型全部占整卡，GPU 利用率低。
3. 抢占资源和稳定资源边界不清。
4. 资源成本、容量和稳定性治理缺少统一口径。

### 方案

SAI 建设 NodePool / ResourceGroup 资源抽象，按 `gpu`、`gpu_shared_memory`、`spot_gpu`、`cpu`、`spot_cpu` 等类型管理节点池。

创建或变更推理服务、TFJob、Nuclio Function、FAISS Build 时，控制面把 NodePool 翻译成 PodSpec 的 `nodeSelector` / `tolerations`，并把资源规格写入容器 limits。

资源口径包括：

1. 独占卡走 `nvidia.com/gpu`。
2. 共享显存走 `aliyun.com/gpu-mem`。
3. 抢占池和 CPU 池有单独校验。
4. 用户选择资源池，不直接操作节点标签和污点。

### 收益

在线推理、训练和批处理可以在统一平台下共存，但资源池边界清晰。小模型可通过共享显存提高利用率，关键在线服务可落到独占池，离线或可重试任务可以使用抢占池，降低“全靠人肉约定”的调度风险。

### 面试展开话术

可以这样说：

GPU 在 AI 平台里不是普通资源字段，而是需要治理的高成本资源。我们做的是调度意图产品化，用户选择独占 GPU 池、共享显存池、抢占 GPU 池或 CPU 池，平台把这个选择翻译成 PodSpec 和资源 limits。最终调度还是 Kubernetes scheduler 和 GPU 插件完成，我们不替代 Scheduler。

### 高频追问

**Q：你们是不是自研 GPU Scheduler？**

答：

不是。SAI 没有替代 Kubernetes scheduler。我们做的是资源池抽象、准入校验和 PodSpec 生成。真正的调度仍然由 Kubernetes scheduler、节点标签、污点容忍和 GPU 插件完成。

**Q：共享显存和独占 GPU 有什么区别？**

答：

独占 GPU 一般通过 `nvidia.com/gpu` 这类资源字段申请整卡。共享显存是通过厂商 GPU 插件暴露的显存资源字段来表达，适合小模型或资源利用率要求更高的场景，但隔离性和性能稳定性通常不如独占卡。

---

## 生命周期与状态一致性治理：server、watcher、Sync 与 Job Runtime 分层

### 背景

训练、Cron、FAISS、模型下载、贝联托管服务都有长周期状态变化，状态不只来自一次 API 返回。

AI 工作负载和普通 Web 服务不同。训练任务会持续运行，CronJob 会周期触发，模型下载耗时不可控，第三方推理服务的状态可能来自外部平台回写或查询。

### 问题

如果 API 同步等待所有动作完成，请求会被长耗时任务拖住；如果只写数据库状态，又容易和真实运行态偏离。

平台状态来源复杂，可能包括：

1. 用户在控制台发起的创建、重启、扩缩容。
2. Kubernetes event。
3. TFJob / CronJob / Job 的运行状态。
4. 第三方托管平台回写或查询结果。
5. 定时同步任务。
6. 数据库里保存的平台元数据。

### 方案

SAI 将生命周期治理拆成三层：

1. **server 同步控制面**  
   负责同步 API、参数校验、权限、初始编排和平台期望状态写入。

2. **watcher / Sync 异步状态层**  
   watcher 消费 TFJob / Cron / FAISS 等事件并回写平台状态；贝联等外部平台通过定时 Sync 补齐元数据。

3. **Job Runtime 长耗时任务层**  
   模型下载、OSS 下载、制品上传等长耗时动作交给 Kubernetes Job Runtime，避免阻塞控制面。

### 收益

平台可以把“用户发起动作”和“运行态持续变化”解耦，既保证 API 可控，也能通过 watcher / Sync 做状态补偿，避免长周期任务污染同步请求链路。

### 面试展开话术

可以这样说：

SAI 里很多任务不是创建后立即结束，比如 TFJob、CronJob、模型下载、第三方推理服务。我们把同步控制面、异步 watcher / Sync 和 Job Runtime 拆开。server 处理用户动作，watcher 和 Sync 处理真实运行态变化，Job Runtime 承接长耗时任务。这个设计解决的是最终一致性和状态补偿问题。

### 高频追问

**Q：watcher 挂了怎么办？**

答：

watcher 不能只依赖一次事件。一般要有事件驱动和定时 Sync / 巡检补偿两类机制。事件驱动用于及时感知状态变化，定时补偿用于修复事件丢失、watcher 重启或第三方状态漂移带来的不一致。

**Q：数据库状态和真实状态冲突怎么办？**

答：

要区分平台期望状态和真实运行状态。用户操作会更新平台期望状态，watcher / Sync 会同步真实状态。如果冲突，需要看状态来源、操作时间和状态优先级，避免过期状态覆盖新操作。

---

## 多云推理服务托管：统一 ACK、PAI、火山、贝联等运行形态

### 背景

推理和训练能力分散在 PAI、火山、贝联和 ACK 内部 Runtime 中，贝联推理还涉及跨平台网络接入。

推理服务不只跑在一个 Kubernetes 集群里，还涉及 ACK/KServe、PAI EAS、火山、贝联这类不同托管平台。

### 问题

多云托管最难的不是 API 调用，而是语义对齐：

1. 资源规格口径不同。
2. 实例状态不同。
3. 错误信息不同。
4. 日志和事件来源不同。
5. 扩缩容和重启动作不同。
6. 网络接入和访问方式不同。

新增平台时，如果把厂商接口写进业务逻辑，会导致上层被厂商模型绑住；贝联接入如果靠人工配置网络，联调成本高，也难以复用。

### 方案

平台侧沉淀统一的服务模型和运维动作，对外保持统一响应语义。底层按 ACK/KServe、PAI、火山、贝联等运行形态做适配。

贝联网络接入通过 Envoy / Gateway / Service 等控制面能力，把流量到贝联域名的链路封装成平台动作。

### 收益

上层只对接一套平台语义。新增云厂商或托管平台时改动集中在底层适配，网络接入从“人工准备”变成可复用的平台能力。

### 面试展开话术

可以这样说：

多云推理托管不是把几个云厂商 API 调一遍。真正麻烦的是资源规格、状态、日志、扩缩容、迁移和网络接入口径都不一样。我们把用户侧主流程稳定住，底层平台差异集中适配，这样新增托管平台时不需要重做用户操作链路。

### 高频追问

**Q：新增一个厂商为什么能快？**

答：

前提是上层语义已经稳定。新增厂商主要适配服务创建、规格映射、状态查询、实例列表、扩缩容、重启、日志事件和资源组。只要这些能力能对齐，上层控制台和用户流程不需要大改。

**Q：多云抽象会不会过度抽象？**

答：

会有这个风险。所以平台不能强行把所有厂商差异抹平。通用动作统一，厂商特有能力可以通过扩展字段或特定操作保留。核心是统一主流程，而不是把所有能力抽象成完全一样。

---

## 大模型推理场景：PD 分离下的平台侧适配

### 背景

传统推理服务在平台里通常可以按单服务形态托管，平台主要关注服务规格、实例状态、扩缩容、重启、迁移和日志事件。

但在大模型推理场景下，PD 分离会把推理链路拆成 Prefill 和 Decode 等不同组件。对平台来说，这意味着一个模型服务不再只是一个普通 Deployment 或一个单一托管服务，而是多个组件共同组成的推理 Runtime。

### 问题

PD 分离主要影响的是平台侧运行治理方式：

1. **工作负载形态变化**  
   一个模型服务会拆成 Prefill / Decode 等多个组件，平台需要表达它们之间的关联关系，而不是把它们当成完全独立的服务。

2. **资源诉求不同**  
   Prefill 更偏计算密集，Decode 更关注低时延、显存和 KV Cache 相关压力。平台需要支持不同组件绑定不同 GPU 资源池。

3. **状态需要聚合**  
   用户关心的是一个模型服务是否可用，但平台底层需要同步多个组件的运行状态，并聚合成统一服务状态。

4. **扩缩容和观测口径变化**  
   普通推理服务主要看 QPS、RT、实例状态；大模型推理还需要逐渐关注 TTFT、TPS、token latency、queue latency、Prefill latency、Decode latency 等指标。

### 方案

SAI 在 PD 分离场景下主要做平台侧运行治理适配，而不是推理引擎实现：

1. **多组件服务表达**  
   在平台侧将 Prefill、Decode 等组件关联到同一个模型服务下，形成统一服务视图。

2. **GPU 资源池划分**  
   支持不同组件选择不同 NodePool / ResourceGroup，例如计算型 GPU 池、高显存 GPU 池、独占池或共享池。

3. **状态聚合与运行治理**  
   将多个组件的实例状态、运行状态和异常信息聚合到统一推理服务视图中，避免用户在多个底层服务之间切换排障。

4. **扩缩容与观测入口适配**  
   将 Prefill / Decode 等组件的扩缩容和观测入口纳入平台统一托管体系，为后续 AI Serving 指标治理提供基础。

### 收益

PD 分离本身由推理引擎和服务团队实现，SAI 的价值在于把这种复杂推理形态继续纳入统一平台治理，而不是让它变成一套脱离平台的人工运维流程。

平台侧通过多组件表达、GPU 资源池划分、状态聚合和观测入口适配，让大模型推理服务仍然可以复用原有的服务托管、资源治理和运行态排障能力。

### 面试展开话术

必须先划边界：

PD 分离的推理引擎实现不是我负责的，我参与的是平台侧运行治理适配。也就是当推理服务从单一服务形态变成 Prefill / Decode 多组件形态后，平台如何继续托管它、展示它、绑定资源池、做状态聚合、扩缩容和观测。

### 高频追问

**Q：PD 分离是什么？**

答：

大模型推理里可以把请求处理拆成 Prefill 和 Decode 两个阶段。Prefill 阶段主要处理输入 prompt，计算量大，更关注吞吐和算力。Decode 阶段逐 token 生成输出，更关注低时延、显存和 KV Cache 相关开销。PD 分离就是把这两个阶段拆到不同组件或资源池里治理，以便分别优化资源和性能。

**Q：你具体参与了什么？**

答：

我不是做推理引擎实现，主要参与平台侧适配。比如多组件服务怎么在平台里表达，Prefill / Decode 怎么绑定不同 GPU 资源池，状态怎么聚合展示，扩缩容和观测入口怎么继续纳入统一推理服务托管体系。

**Q：KV Cache 怎么管理？**

答：

KV Cache 的底层管理不是平台控制面负责的，主要在推理引擎或 Serving Runtime 里。平台侧更多关注它带来的治理影响，比如 Decode 组件资源池、显存压力、观测指标和扩缩容策略。

---

## 长耗时任务异步化：模型下载与制品处理

### 背景

模型权重通常来自 Hugging Face、OSS、HTTP 源或内部制品系统，文件体积大、下载时间不稳定。算法同学如果手动拷贝模型到集群共享盘，链路慢、容易出错，也不利于审计和复用。

### 问题

模型下载和制品处理不适合放在同步 API 中执行：

1. 文件体积大，请求容易长时间阻塞。
2. 下载失败后需要重试和排障。
3. 不同任务如果各自维护模型路径，会导致挂载目录和复用口径混乱。
4. 下载过程需要独立的资源、日志和状态查询入口。

### 方案

控制面只负责创建下载任务、记录任务状态和提供查询入口，真正的下载动作交给 Kubernetes Job Runtime。

平台创建 `batch/v1` Job，由专用镜像执行 Hugging Face / OSS / HTTP 下载逻辑，挂载工作空间 PVC，将模型权重落到固定目录。失败后可以删除旧 Job 并重新触发，排障时通过 Pod 日志、Job 状态和平台记录定位问题。

### 收益

模型下载不阻塞控制面，训练和推理任务可以复用统一模型挂载路径。这个能力不是完整 Model Registry，而是模型制品进入平台、落盘、挂载和复用的基础治理能力。

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777015506819-1429cdf4-d03b-40bf-8a4f-84fee3158062.png" width="1920" title="" crop="0,0,1,1" id="h4SCQ" class="ne-image">

### 高频追问

**Q：这算模型管理吗？**

答：

严格说这不是完整 Model Registry。这里更多是模型制品下载和挂载治理，解决的是模型权重进入平台、落盘和被训练 / 推理任务复用的问题。完整模型管理还应该包括版本、指标、评估、lineage、发布回滚等能力。

---

# 深水区

这里的内容用于追问展开，不放在开场主线里。面试时先讲平台抽象和治理价值，只有被追问到底层细节时再进入这些材料。

---

## 仓库内多入口：别只讲 console

+ `cmd/server` **（主 API）**：Gin 路由、`/api/v1/*` 域控制器、鉴权/中间件与 `pkg/provider/*` 多云编排；面试里说的「控制面」多数指它。
+ `cmd/watcher` **（后台）**：`pkg/kubernetes/event` 注册 **TFJobWatcher、CronWatcher、FaissCronJobEventWatcher** 等，持续 Watch 集群事件并联动平台状态；另有 **cron**（`@every 10m`）触发贝联侧 **Sync**（`pkg/provider/lccomputing`）。与主进程解耦，避免长周期监听/轮询塞进 HTTP 请求线程。
+ **Job 执行面**：`pkg/kubernetes/job/*` 拼装 `batch/v1` Job（如 Hugging Face 下载、OSS 下载），由 `controller/model/job.go` 等 API 触发；适合大文件、长耗时、需要独占节点/容忍调度的任务。

---

## 贝联推理“一键平滑打通网络”

细节见 [https://www.yuque.com/bingqilinningmengcha/yys5b5/lcc1koerzfps2gmk](https://www.yuque.com/bingqilinningmengcha/yys5b5/lcc1koerzfps2gmk)

+ 在访问贝联推理时，可通过 **Envoy 控制面能力**平滑打通网络。
+ 实现思路是：创建/更新 Envoy 控制面相关 `Cluster` 等对象，把内部流量转发到贝联目标域名。
+ 这个能力本质上依赖 SAE 开放能力，对使用方是“低心智负担”的一键式接入。
+ 可参考历史实现线索：`/opt/coding/python/search_service`。

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777015706798-f8f9fc03-7e2d-4da4-b6b2-f221c71d8c80.png" width="2200" title="" crop="0,0,1,1" id="fBJSI" class="ne-image">

### 排查流程

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778574924717-1130513c-43d1-bf94-28016023770e.png" title="" crop="0,0,1,1" id="TtK9A" class="ne-image">

### 配流量转发

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777012185186-746964e7-77a3-4e0c-93ef-d9ebb253dbec.png" width="2094" title="" crop="0,0,1,1" id="ZWeSk" class="ne-image"><img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778575281939-ca89e080-a8ac-4d2f-95db-52e0587a252f.png" width="1974" title="" crop="0,0,1,1" id="hIVrz" class="ne-image">

从调用方视角可以分两条：

1. **走公网 / 入口域名**：客户端打到 `*.soulapp-inc.cn` 这类 Host，Ingress 把流量转到集群里的 Service；迁贝联时会挂 `beilian-gw` 之类的后端，`externalName` 指到 `jinhua-cloud` 的 RPC 域名，流量就出 ACK 进贝联。
2. **走集群内**：Pod 用集群 DNS 访问 beilian Service，同样通过 ExternalName 出网；或者走 Gateway + HTTPRoute + Istio VirtualService，用 `staticAddress` 把上游指到贝联 FQDN。

### mesh / gateway 类型

平台里的流量转移有 mesh / gateway 两种类型，对应改哪类 K8s 对象，不是 gRPC 和 HTTP 二选一；gRPC / HTTP 是端口和协议命名。贝联侧已知主要是 Triton、gRPC（例如端口名 `grpc`、31581），少量 HTTP 自定义服务按待确认处理。

### 如何调权重

+ **gateway 模式**：权重调在 Ingress + Service 这条链上，本质是 Ingress 多个 backend 之间按比例切。
+ **mesh 模式**：权重调在 HTTPRoute 和 VirtualService 上。HTTPRoute 用 `backendRefs.weight` 在多个 Service 之间分；Istio 用 VirtualService 里的 `route.destination.weight`，子集标签一般在 DestinationRule 里。
+ **纯 ExternalName 直连**：Service 自己没有百分比字段，要灰度就得依赖上层 mesh、双 Service + 入口切流，或 Rollouts 之类能力，不能指望只改一个 ExternalName 就分权。

### 和 Istio / Envoy 的关系

VirtualService 是 Istio CRD，不是 Envoy 原生对象；Envoy 跑的是翻译后的路由。HTTPRoute 是 Kubernetes Gateway API；在 Istio 集成场景下可以由 Istio 转成 Envoy 配置。面试里可以说成：配置在 CRD，执行在 Envoy。

### 排查 / 工程化

排查时可用 `search_service` 这类脚本拉 Ingress / HTTPRoute / VirtualService / Service，从域名反查 `beilian`、31581、`externalName` 或 `staticAddress`，把 ACK 侧对象和贝联 FQDN 对上，避免靠口口相传。

---

## Provider 与资源抽象代码段（暂保留）

```go
type Interface interface {
    CreateInferenceService(clusterId string, name string, body json.RawMessage) error
    StopInferenceService(clusterId string, name string) error
    StartInferenceService(clusterId string, name string) error
    GetInferenceService(name string) (*appsv1.Deployment, error)
    GetPod(serviceName, name string) (corev1.Pod, error)
    DeletePod(serviceName, name string) error
    ListInferenceService(filter string, pageSize int, pageNumber int) (any, error)
    ListPod(name string, pageSize int, pageNumber int) (*client.ObjectList[corev1.Pod], error)
    ListEvent(name string, instanceName string, pageSize int, pageNumber int) (*client.ObjectList[corev1.Event], int64, error)
    ListPVC(clusterId string, namespace string) ([]corev1.PersistentVolumeClaim, error)
    ListImage(clusterId string, namespace string) ([]string, error)

    ServiceLog(serviceName string, instanceName string, startTime string, endTime string, pageNum int64, pageSize int64, keyword string, previous bool) (*logs.LogDetails, int64, error)
    Scale(targetReplicas int, serviceName string) error
    ListResourceGroup(cluster string, pageSize int, pageNumber int) page.PageResult[*core.NodePool]
    ListPreDefinedSpec(clusterId string) page.PageResult[any]
    UpdateSpec(clusterId string, serviceName string, request json.RawMessage) error

    // 下面接口直接调用，透传
    ListApprove(params ...any) (any, error)
    AddStorage(body json.RawMessage) (any, error)
    ListStorage() (any, error)
    SyncStorage(req any) (any, error)
    ListSpeedImage() (any, error)
    SyncSpeedImage(req any) (any, error)
    AddSpeedImage(req any) (any, error)
    DeleteSpeedImage(req any) (any, error)
}

type Resource struct {
    core.NodePool
}

type NodePool struct {
    ID           int             `json:"id"`
    NodePoolName string          `json:"node_pool_name"`
    Cluster      string          `json:"cluster"`
    Alias        string          `json:"alias"`
    NodeSelector json.RawMessage `json:"node_selector"` //common.KVList
    Tolerations  json.RawMessage `json:"tolerations"`   //[]corev1.Toleration
    PoolType     PoolType        `json:"pool_type"`
    CreateAt     *time.Time      `json:"create_at"`
    UpdateAt     *time.Time      `json:"update_at"`

    // 以下字段不存储到数据库, 动态计算
    CPUUsed     float64 `json:"cpu_used" gorm:"-"`
    CPUCount    float64 `json:"cpu_count" gorm:"-"`
    MemoryUsed  float64 `json:"memory_used" gorm:"-"`
    MemoryCount float64 `json:"memory_count" gorm:"-"`
    // 独占卡
    GPUUsed     float64 `json:"gpu_used" gorm:"-"`
    GPUCount    float64 `json:"gpu_count" gorm:"-"`
    GPUMemUsed  float64 `json:"gpu_mem_used" gorm:"-"`
    GPUMemCount float64 `json:"gpu_mem_count" gorm:"-"`
    // 共享卡
    SharedGPUUsed     float64 `json:"shared_gpu_used" gorm:"-"`
    SharedGPUCount    float64 `json:"shared_gpu_count" gorm:"-"`
    SharedGPUMemUsed  float64 `json:"shared_gpu_mem_used" gorm:"-"`
    SharedGPUMemCount float64 `json:"shared_gpu_mem_count" gorm:"-"`

    // 卡数量，压缩到一个字符串描述
    GPUCard string `json:"gpu_card" gorm:"-"`

    Status string `json:"status" gorm:"-"`
}

```

---

## 核心业务范围（复习用）

1. 推理服务治理：列表、详情、扩缩容、迁移、配置更新。
2. 训练任务治理：Training/TFJob/Cron 生命周期与联动。
3. K8s 运维能力：Pod、Deployment、Service、Ingress、日志、事件、资源查询。
4. 发布与构建观测：Argo Rollouts、Tekton PipelineRun/Task。
5. 平台与资产能力：Harbor、GitLab、模型元数据与搜索聚合。
6. 模型与制品下载：Hugging Face 一键拉取、OSS/HTTP 下载 Job、制品异步上传 NAS 等。

---

## 代码锚点（复习用）

+ 主入口：`cmd/server/main.go`
+ 路由注册：`cmd/server/routes/*`
+ 鉴权与中间件：`pkg/gin/route/routemanager.go`、`middleware/*`
+ Provider 聚合：`api/api.go`、`pkg/provider/*`
+ 推理路由：`cmd/server/routes/inference.go`
+ 训练路由：`cmd/server/routes/training.go`
+ 异步与 Job：`cmd/watcher/main.go`、`pkg/kubernetes/event/*`
+ HF 拉模 Job：`pkg/kubernetes/job/huggingface_download.go`、`controller/model/job.go`、`cmd/server/routes/model.go`

---

# 高频追问

## 高频面试问题与推荐回答

### 为什么新增厂商可以快？

因为上层协议和控制器不动，主要扩底层适配层，把厂商 API、状态语义和资源差异隔离在平台底层。

更完整的回答：

前提是平台已经把上层语义稳定住了。新增厂商主要适配几类能力：服务创建、规格映射、状态查询、实例列表、扩缩容、重启、日志事件和资源组。只要这些能力能对齐，上层控制台和用户流程不需要大改。

### 多云抽象最难点是什么？

不是 CRUD，而是生命周期状态、错误语义、资源模型和观测口径对齐。平台要让用户看到统一动作，同时不把底层差异泄漏到业务流程里。

### watcher 解决什么问题？

watcher 消费训练、Cron、FAISS 等事件并驱动平台状态，贝联等外部平台通过 Sync 补齐元数据。它解决的是长周期状态同步和补偿问题，不是简单后台任务。

### 为什么 HF 拉模用 Job 而不是 API 里同步下？

模型体积和下载时延不可控，同步下载会拖垮控制面。Job + PVC 可以隔离计算资源、复用共享存储，也方便通过 Pod 日志和 Job 状态排障。

### GPU 治理是不是自研 Scheduler？

不是。SAI 做的是调度意图产品化和准入治理：用户选择资源池，控制面生成 PodSpec 和资源 limits，最终调度仍复用 Kubernetes scheduler 和 GPU 插件。

### 贝联网络打通是不是你们实现了底层网络？

不是。平台侧主要做控制面编排和接入治理，复用 Envoy / Gateway / Service / ExternalName 等已有能力，把人工配置收敛成可复用的平台动作。

### SAI 和 SAE 是什么关系？

SAE 是通用云原生交付和运行治理底座，偏应用发布、多集群、Rollout、构建和运维入口。SAI 复用 SAE 的多集群、发布和运行治理能力，但面向 AI 场景做了训练任务、推理服务、GPU 资源池、模型制品和第三方推理托管的适配。

### SAI 和 Kubeflow / KServe 是什么关系？

SAI 不是替代 Kubeflow 或 KServe，而是把底层 Runtime 平台化。底层可以复用 Training Operator、KServe、Kubernetes Job、PAI 或贝联托管服务；SAI 负责统一入口、权限、资源池、状态同步、日志事件和运维动作。

### 你在 PD 分离里具体做了什么？

我没有做推理引擎层的 PD 分离实现，主要参与平台侧运行治理适配。比如多组件服务如何在平台侧表达，Prefill / Decode 如何绑定不同 GPU 资源池，状态如何聚合展示，扩缩容和观测入口如何继续纳入统一推理服务托管体系。

### PD 分离为什么会影响平台？

传统推理服务更多是单服务形态，平台管理一个服务即可。PD 分离后，一个模型服务会拆成 Prefill / Decode 等多个组件，生命周期、资源诉求、状态聚合和观测口径都会变化，所以平台侧需要做多组件托管和运行治理适配。

### KV Cache 是你们平台管理的吗？

KV Cache 的底层管理主要在推理引擎或 Serving Runtime 中，不是 SAI 控制面直接管理。SAI 更关注它对平台治理带来的影响，例如 Decode 组件的显存压力、资源池选择、观测指标和扩缩容策略。

### 如果继续演进 SAI，你会优先做什么？

我会优先补三块：第一是 AI Serving 指标体系，比如 TTFT、TPS、token latency、queue latency；第二是 GPU 资源利用率治理，比如资源池水位、配额和成本统计；第三是推理服务多组件 Runtime，把普通推理和 PD 分离这类复杂推理形态统一纳入平台生命周期管理。

### 这是不是一个完整的 MLOps 平台？

不是完整 MLOps。SAI 更偏 AI 工作负载托管、推理服务治理、训练任务运行治理和 GPU 资源治理。完整 MLOps 还会包括实验管理、模型评估、特征平台、模型版本 lineage、自动化发布回滚等能力。

### 这个项目和传统 Kubernetes Portal 有什么区别？

传统 Kubernetes Portal 更偏对象 CRUD 和运维入口。SAI 的差异在于面向 AI 工作负载做了运行时统一：训练、推理、Cron、serverless、模型下载、多云托管和 GPU 资源池都被纳入统一生命周期和资源治理。

---

## 风险问题

+ 如果被问“是否自研推理引擎”，回答平台侧统一托管和治理 KServe/PAI/贝联，不表述成自研推理引擎。
+ 如果被问“是否自研训练框架”，回答平台侧接入 Training Operator / TFJob 等 Runtime，不表述成自研训练框架。
+ 如果被问“是否自研 GPU Scheduler”，回答资源池抽象、准入校验和 PodSpec 生成，不表述成替代 Kubernetes scheduler。
+ 如果被问“贝联链路是否完全由 SAI 实现”，回答 SAI 做接入编排与治理，底层能力依赖 SAE / Envoy / Gateway 等基础设施。
+ 如果被问“PD 分离是不是你实现的”，回答不是推理引擎实现，自己参与的是平台侧运行治理适配，包括多组件服务表达、GPU 资源池划分、状态聚合、扩缩容入口和观测口径。
+ 如果被问“KV Cache 怎么管理”，回答底层 KV Cache 管理在推理引擎 / Serving Runtime 中，平台侧主要关注资源池、显存压力、指标观测和扩缩容治理。
+ 如果被问“AI Serving 指标是否已经完整落地”，不要说完整落地，可以说平台已经具备推理服务托管和运行观测基础，后续重点会向 TTFT、TPS、token latency、queue latency 等指标演进。
+ 如果被问“模型资产治理是不是 Model Registry”，不要说是完整 Model Registry。这里主要是模型制品下载、落盘、挂载和复用治理。

---

## 哪些不要展开

+ 不要一上来讲 `cmd/server`、`cmd/watcher`、`pkg/provider` 等路径，除非面试官追问代码实现。
+ 不要把 FAISS 说成通用 RAG 平台，这里主要体现为任务运维和状态治理能力。
+ 不要把所有 watcher 逻辑说成 Gin 同步流程；server 与 watcher 是明确分层的。
+ 不要把技术栈表当成主线，主线应该是 Runtime 统一、生命周期治理、资源治理和多云治理。
+ 不要主动讲贝联端口、内部域名、内部脚本路径、具体网络对象名，除非是内部复盘或对方明确追问。
+ 不要把 PD 分离讲成自己做了 vLLM / SGLang / KV Cache / block manager。
+ 不要把下载模型讲成完整模型管理平台。

---

# 简历口径

## 推荐简历片段

```markdown
Soul AI Platform｜AI 训练与推理运行平台
2024.04 - 至今

面向 AI / 算法场景的统一作业与服务托管平台，复用 SAE 多集群、发布和运行治理底座，统一承接推理服务、TFJob 训练任务、NuclioFunction、CronJob、模型资产和数据源管理，支撑 600+ 推理服务、300+ serverless 服务、500+ TFJob 训练任务、100+ CronJob 任务的稳定托管。

● 负责 sai-console 核心控制面建设，统一收口算法工作负载的创建、发布、变配、伸缩、重启、迁移、状态查询、日志、事件和运行治理能力，形成训练 / 推理任务统一生命周期管理体系。

● 统一不同云厂商和托管形态下推理服务的规格、状态、扩缩容、重启、迁移和状态同步链路，屏蔽底层平台差异，降低多云推理服务接入与运维复杂度。

● 建设 GPU 异构资源池与资源组抽象，统一支持 GPU 独占、共享显存、抢占 GPU、CPU 等资源模式，为 GPU 资源治理、弹性托管和成本优化提供基础。

● 承接 TFJob 训练作业托管场景，提供任务创建、状态查询、日志、事件和运行治理能力，支持多角色副本、资源规格、节点池、镜像、存储挂载、TensorBoard、任务克隆、重启、迁移和资源变配；打通 Soda Pepsi 调度平台 DAG 编排链路，支持按天周期触发训练任务并回传任务状态。

● 建设训练任务、定时任务和第三方推理服务状态同步与补偿链路，处理任务缺失恢复、状态漂移和平台元数据一致性问题；补齐模型资产、NAS / OSS / Git 数据源和模型挂载链路，降低算法任务接入与迁移成本。

● 参与大模型推理场景下的平台运行治理建设，围绕 PD 分离架构下的多组件部署、GPU 资源池划分、弹性伸缩和推理观测等方向进行适配，支持平台向 AI Serving Runtime 场景演进。
```

## 简历风险控制

上面最后一条如果写进简历，面试必须准备：

1. PD 分离是什么。
2. 为什么 PD 分离会影响平台。
3. 你参与的是平台侧，不是推理引擎。
4. Prefill / Decode 的资源诉求有什么差异。
5. KV Cache 不由平台控制面直接管理。
6. 平台侧能做的是资源池、状态聚合、扩缩容入口和观测口径。

如果准备不充分，最后一条可以删掉，避免被问到底层推理引擎细节。

---

# 面试使用方式

这份文档不是从头背到尾的稿子，而是面试时的“分层素材”。

## 主动讲的内容

面试开场优先讲：

1. 项目定位：AI 工作负载运行托管与治理平台。
2. 你负责的边界：控制面、资源治理、生命周期治理、多云托管适配。
3. 三个主专题：
   - AI 工作负载 Runtime 统一
   - GPU 资源池与资源治理
   - 生命周期与状态一致性治理

## 被追问再展开的内容

以下内容不要主动讲太深：

1. 贝联网络打通、Gateway、Envoy、ExternalName、VirtualService。
2. Provider 接口和具体代码路径。
3. Hugging Face 下载 Job 细节。
4. PD 分离底层推理引擎、KV Cache、Prefill / Decode 内核实现。

## 必须守住的边界

1. 不说自己实现了推理引擎。
2. 不说自己实现了训练框架。
3. 不说自己实现了 GPU Scheduler。
4. PD 分离只讲平台侧运行治理适配，不讲底层推理引擎实现。

---

# 一句话收尾

我在这个项目里的核心贡献，是把异构 AI 工作负载和多云平台差异收敛到统一控制面：多云侧做托管形态适配，资源侧做 GPU 与 NodePool 治理，生命周期侧用 watcher 和 Job Runtime 解耦长周期状态，最终让业务通过统一入口获得稳定、可观测、可治理的 AI Runtime 能力。

