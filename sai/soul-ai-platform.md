# SAI-Console 项目总结
> 说明：本文按「面试表达」组织；**文首**按平台约定为 **约 90 秒开场白 → 架构图 → STAR**，其后为问题背景、技术栈与模块展开（多云统一与贝联网络打通等亮点在正文）。
>

---

---

## 一、约 90 秒开场白
我负责的是 SAI-Console **后端控制面**（Go + Gin）：`cmd/server` 主进程提供**同步 API**，把训练与推理相关能力统一成一套 HTTP 入口，对上承接控制台和自动化系统，对下对接 Kubernetes、KServe、Tekton、Argo Rollouts，以及多家云厂商推理/训练平台（PAI、火山、贝联）。

仓库里不只有「一个 console」：还有 `cmd/watcher`** 异步进程**（Watch TFJob/Cron/FAISS CronJob 等事件并驱动平台侧状态；另含贝联侧 **定时 Sync**），以及面向重任务的 `batch/v1`** Job** 能力——典型例子是 **一键从 Hugging Face 拉模型**：API 在集群里创建 Job，容器内用 `hfd.sh` + `aria2c` 下载，把权重落到工作空间绑定的 **PVC** 上（`VolumeMount.subPath: huggingface`，PVC `claimName` 与命名空间/存储约定一致，落地目录对业务表现为 **NAS 上的模型盘**）。

我做的核心价值不是“再写一套业务 CRUD”，而是用「**同步控制面 + 异步 watcher + Job 执行面**」把动作抽象成可治理的平台能力：**统一入口完成模型与制品治理、训练任务管理、资源观测、灰度发布、外部平台联动**。

如果面试官继续问 AI Infra 深水区，我会重点讲 SAI 的另一条主线：**GPU 异构资源治理**。SAI 没有自研一个 Kubernetes Scheduler，而是在控制面把业务诉求抽象成 **NodePool / 资源组 / 资源规格**：区分 GPU 独占、共享显存、抢占 GPU、CPU 等资源池，把表单里的节点池选择转成真实 PodSpec 里的 `nodeSelector`、`tolerations` 和资源 `limits`；同时把 KServe 推理、TFJob 训练、Nuclio Function、FAISS Build、模型下载 Job 这些异构工作负载收进同一套资源、存储、日志、事件和状态同步口径里。

---

## 二、系统架构图（重点）
<img src="https://cdn.nlark.com/yuque/__mermaid_v3/719cfbd44e7f366e7fdf5e83a964abab.svg" width="1573" title="null" crop="0,0,1,1" id="jV2oG" class="ne-image">

### 2.1 这张图该怎么讲
+ SAI-Console 自己是**控制面聚合层**，不是单一云厂商 SDK 的薄转发。
+ 业务侧通过统一控制器调用“标准动作层”，再由 Provider 去适配各厂商差异。
+ 这也是“为什么新增厂商可以快”的关键：新增点集中在 Provider，不会把上层业务逻辑撕裂。

### 2.2 仓库内多入口：别只讲 console
+ `cmd/server`**（主 API）**：Gin 路由、`/api/v1/*` 域控制器、鉴权/中间件与 `pkg/provider/*` 多云编排；面试里说的「控制面」多数指它。
+ `cmd/watcher`（后台）**：`pkg/kubernetes/event` 注册 **TFJobWatcher、CronWatcher、FaissCronJobEventWatcher** 等，持续 Watch 集群事件并联动平台状态；另有 **cron**（`@every 10m`）触发贝联侧 **Sync**（`pkg/provider/lccomputing`）。与主进程解耦，避免长周期监听/轮询塞进 HTTP 请求线程。
+ **Job 执行面**：`pkg/kubernetes/job/*` 拼装 `batch/v1` Job（如 Hugging Face 下载、OSS 下载），由 `controller/model/job.go` 等 API 触发；适合大文件、长耗时、需要独占节点/容忍调度的任务。

### 2.3 思维导图
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777433815648-164cbdd4-90b3-4f16-bb13-e7fc7b48251d.png" width="1071" title="" crop="0,0,1,1" id="u9e8c92eb" class="ne-image">



## 三、STAR 回答模板（可直接背）
### STAR A：多云统一控制面
**S（情境）**：推理和训练能力分散在 PAI、火山、贝联，多平台接口差异导致上层接入成本高。  
**T（任务）**：把多平台能力收敛到 SAI-Console，做到统一入口和快速扩展。  
**A（行动）**：沉淀通用 K8s 标准动作，按 Provider 隔离平台差异，对外统一响应语义。  
**R（结果）**：上层只对接一套 API；新增平台时改动集中在 Provider，交付速度更快、维护成本更低。

### STAR B：贝联网络一键打通
**S（情境）**：贝联推理接入经常卡在网络连通，人工步骤多、联调慢。  
**T（任务）**：把连通链路平台化，做到可复用、低心智负担。  
**A（行动）**：接入 Envoy 控制面能力，创建/更新 Cluster 与转发配置，实现流量到贝联域名的平滑转发。  
**R（结果）**：从“人工网络准备”变成“一键接入”，业务联调效率明显提升。

### STAR C：Hugging Face 一键拉模到 NAS（Job）
**S（情境）**：模型权重在 Hub 上，研发需要反复拷到集群侧共享盘，链路慢且难审计。  
**T（任务）**：在平台内提供「一键拉取」，落盘到工作区 **NAS/PVC** 供推理与训练复用。  
**A（行动）**：由控制面 API 创建 `batch/v1`** Job**：专用镜像跑 `hfd.sh` + `aria2c`，挂载 PVC `subPath=huggingface`；可选 HF Token；失败支持删旧 Job 重试；任务状态写入 `model_job` 等表。  
**R（结果）**：下载与 API 解耦，大文件不阻塞 Gin；存储路径统一，后续服务挂载一致。

### STAR D：GPU 调度、混部与隔离治理
**S（情境）**：算法平台里既有高优先级在线推理，也有训练、FAISS Build、模型下载等离线/批处理任务；GPU 资源昂贵，如果只靠人工指定机器，容易出现利用率低、抢占资源误用、在线服务被离线任务干扰等问题。  
**T（任务）**：在不自研 Scheduler 的前提下，把资源池、隔离策略和资源规格做成平台能力，让用户按业务语义选择资源，而不是直接操作节点标签和污点。  
**A（行动）**：建设 **NodePool 资源抽象**，按 `gpu`、`gpu_shared_memory`、`spot_gpu`、`cpu`、`spot_cpu` 等类型管理节点池；创建/变更推理服务时把节点池翻译成 `nodeSelector`、`tolerations` 和 GPU `limits`，独占卡走 `nvidia.com/gpu`，共享显存走 `aliyun.com/gpu-mem`，抢占池和 CPU 池有单独校验；训练任务按 Worker / PS / Chief / Evaluator 分角色绑定节点池。  
**R（结果）**：在线推理、训练和批处理可以在统一平台下共存，但资源池边界清晰；小模型可通过共享显存提高利用率，关键在线服务可落到独占池，离线/可重试任务可以使用抢占池，避免“全靠人肉约定”的调度风险。

### STAR E：异构服务统一托管
**S（情境）**：SAI 里既有 KServe/Triton 推理，也有 PAI EAS、贝联托管服务、Nuclio Function、TFJob/Cron TFJob 和 FAISS Build，不同平台的服务模型、日志、事件、Pod、资源组接口差异很大。  
**T（任务）**：让用户在控制台里看到的是统一的服务生命周期和排障入口，而不是每种底座一套操作手册。  
**A（行动）**：用 `cloud_provider`、`serve_runtime`、`model_format`、`node_pool` 等元数据建立统一服务画像；控制器层按 Provider 分发到 ACK/KServe、PAI、贝联等实现，日志、事件、Pod、资源组、重启、变配等动作保持统一 API 语义；Nuclio、TFJob、FAISS 这些非推理工作负载也复用 NodePool、存储挂载和 watcher 状态同步能力。  
**R（结果）**：底层服务形态可以异构，上层运维体验保持一致；新增托管平台或工作负载类型时，主要扩 Provider/适配层，不把控制台和用户操作流程打散。

---

---

## 四、项目要解决的问题
1. **统一入口问题**：前端和上层系统不需要分别适配各云厂商接口，统一调用 SAI-Console。
2. **端到端治理问题**：从训练到推理，再到观测和运维动作，走一条闭环链路。
3. **多平台演进问题**：新增云厂商时，不推翻业务层，只补 Provider 适配与少量路由编排。
4. **GPU 资源治理问题**：GPU 独占、共享显存、抢占资源和 CPU 资源池要有统一表达，避免用户直接面对节点标签、污点和厂商资源字段。
5. **混部与隔离问题**：在线推理、训练、构建、下载等工作负载可以共用平台底座，但需要通过资源池、调度约束、资源 limits 和 watcher 状态治理控制影响面。

---

## 五、技术栈（面试可背）
| 类别 | 选型 |
| --- | --- |
| 语言与框架 | Go 1.22、Gin |
| 数据层 | GORM + MySQL、Redis Session |
| 云原生 | Kubernetes client-go、KServe、Training Operator、Tekton、Argo Rollouts |
| 资源治理 | NodePool / ResourceGroup、`nodeSelector`、`tolerations`、`nvidia.com/gpu`、`aliyun.com/gpu-mem` |
| 可观测 | OpenTelemetry、Prometheus `/metrics` |
| 外部平台 | 阿里云 PAI（EAS/DLC）、火山、贝联（LcComputing） |


---

## 六、项目亮点（重点）
### 亮点 1：多云训练/推理统一控制面
+ 已支持（或已接入路径明确）**贝联推理、PAI 推理/训练（EAS/DLC）、火山推理**。
+ 上层业务不直接感知厂商差异，统一走 SAI-Console API。
+ 我把常见操作沉淀为 **K8s 标准动作**（资源读写、状态查询、生命周期动作），所以新增厂商时主要做 Provider 适配，落地速度快。

### 亮点 2：GPU 异构资源调度、混部与隔离治理
+ **资源抽象**：SAI 把底层资源收敛成 NodePool / 资源组，而不是让用户直接填写节点标签和污点。NodePool 记录 `node_pool_name`、`cluster`、`node_selector`、`tolerations`、`pool_type`，其中 `pool_type` 区分 GPU 独占、GPU 共享显存、抢占 GPU、CPU、抢占 CPU。
+ **调度落地**：平台在创建/变更 KServe 推理服务、TFJob 训练任务、Nuclio Function、FAISS Build 时，把 NodePool 转成工作负载 PodSpec 的 `nodeSelector` 和 `tolerations`；资源规格再转成容器 `limits`，由 Kubernetes 调度器和设备插件完成最终放置。
+ **GPU 类型差异**：独占卡使用 `nvidia.com/gpu`，共享显存使用 `aliyun.com/gpu-mem`，共享算力可扩展到 `aliyun.com/gpu-core.percentage`；平台在变更节点池时会校验资源池类型和资源字段是否匹配，避免共享池还带独占卡字段、CPU 池误带 GPU 字段。
+ **混部策略**：不是无约束混跑，而是按业务优先级做可控混部。高优先级在线推理放独占 GPU 或稳定资源组；小模型、低峰服务可用共享显存提升利用率；训练、FAISS Build、模型下载这类可重试任务可以进入抢占或离线资源池。
+ **隔离边界**：隔离主要落在四层：节点池层用 `nodeSelector`/taint/toleration 隔开资源；资源层用 GPU card / GPU memory / CPU memory limits 控制占用；存储层用 namespace 级 PVC、模型 `subPath` 和工作区约束隔开模型文件；控制面层用权限、状态同步、日志事件入口保证排障和回滚。

#### 面试里可以这样讲
「我们没有说自己实现一个 GPU Scheduler，而是把调度意图产品化。用户在 SAI 里选的是资源池，比如独占 GPU、共享显存、抢占 GPU；控制面负责把这个选择翻译成 PodSpec 的 `nodeSelector`、`tolerations` 和 GPU limit。这样既复用 K8s 原生调度，又把平台应该管的准入、校验、隔离和运维口径收住。」

#### 被追问混部时的回答
「SAI 做的是可控混部：在线推理和离线训练不会靠口头约定混在同一批节点上，而是通过 NodePool 把稳定池、共享池、抢占池拆开。共享显存解决小模型 GPU 利用率问题，抢占池承接可重试任务，关键在线服务仍然走独占池或稳定资源组。隔离不是一个点，而是节点池、资源 limit、存储路径和 watcher 状态治理一起做。」

### 亮点 3：服务异构统一托管：KServe / PAI / 贝联 / Nuclio / TFJob
+ **推理异构**：ACK 内的 KServe/Triton、PAI EAS、火山推理、贝联 LcComputing 在底层 API 和服务模型上不一样，但 SAI 用 `cloud_provider`、`serve_runtime`、`model_format`、`node_pool` 等字段统一服务画像。
+ **工作负载异构**：除了在线推理，平台还收口 TFJob / Cron TFJob、Nuclio Function、FAISS Build、模型下载 Job。它们运行形态不同，但都复用集群、命名空间、镜像、资源、NodePool、存储挂载、日志和事件这些共同治理面。
+ **运维动作统一**：Pod 列表、容器日志、事件、重启、扩缩容、资源组查询、节点池变更等操作由控制器分发到不同 Provider；对用户暴露的是同一套 API 和页面语义。
+ **存储与模型统一**：模型权重、Hugging Face 下载、NAS/PVC、OSS/HTTP 下载和训练/推理挂载路径统一约束，避免不同工作负载各自定义一套模型目录。
+ **状态同步统一**：server 做同步 API，watcher 消费 TFJob/Cron/FAISS 等事件并回写平台状态，贝联等第三方服务也通过 Sync 机制补齐平台侧元数据。

#### 面试里可以这样讲
「SAI 的难点不是只创建一个服务，而是把不同服务形态统一托管。KServe 是 Kubernetes CRD，PAI 和贝联是外部托管平台，Nuclio、TFJob、FAISS 又是不同类型工作负载。我的做法是把服务画像和运维动作统一，上层只看到列表、详情、日志、事件、扩缩容、重启、迁移和资源变配；底层差异由 Provider 和对应 runtime 模板消化。」

### 亮点 4：贝联推理“一键平滑打通网络”
+ 在访问贝联推理时，可通过 **Envoy 控制面能力**平滑打通网络。
+ 实现思路是：创建/更新 Envoy 控制面相关 `Cluster` 等对象，把内部流量转发到贝联目标域名。
+ 这个能力本质上依赖 SAE 开放能力，对使用方是“低心智负担”的一键式接入。
+ 可参考历史实现线索：`/opt/coding/python/search_service`。

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777015706798-f8f9fc03-7e2d-4da4-b6b2-f221c71d8c80.png" width="1100" title="" crop="0,0,1,1" id="uda89e459" class="ne-image">

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777012185186-746964e7-77a3-4e0c-93ef-d9ebb253dbec.png" width="627" title="" crop="0,0,1,1" id="u02d6dc3e" class="ne-image">

#### <font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">开场（20 秒）</font>
<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">「我们业务在</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">ACK</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，推理在</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">贝联</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，两边用域名和服务名打通。入口侧可能是</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Ingress（背后 Envoy）</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">或</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Gateway API + Istio</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">；出贝联侧已知主要是</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Triton、gRPC</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">（例如端口名</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`<font style="background-color:rgb(252, 252, 252);">grpc</font>`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">、</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">31581</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">），是否还有少量</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">HTTP 自定义服务</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">我这边按「待确认」处理，不武断。」</font>



#### <font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">两条拓扑（30 秒）</font>
<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">「从调用方视角可以分两条：</font>

1. **<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">走公网 / 入口域名</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">：客户端打到</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">*.soulapp-inc.cn</font>**`**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">这类 Host</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Ingress</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">把流量转到集群里的</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Service</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">；迁贝联时会挂</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">beilian-gw</font>**`**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">之类</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">的后端，</font>`**<font style="background-color:rgb(252, 252, 252);">externalName</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">指到</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">jinhua-cloud</font>**`**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">的 RPC 域名</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，流量就出 ACK 进贝联。</font>
2. **<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">走集群内</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">：Pod 用</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">集群 DNS</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">访问</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">beilian Service</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，同样</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">ExternalName</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">出网；或者走</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Gateway + HTTPRoute + Istio VirtualService</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，用</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">staticAddress</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">把上游指到贝联 FQDN。」</font>



#### <font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">mesh / gateway 类型（15 秒）</font>
<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">「我们平台里</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">流量转移</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">有</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">mesh / gateway</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">两种类型，对应</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">改哪类 K8s 对象</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">不是</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">gRPC 和 HTTP 二选一；</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">gRPC / HTTP</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">是端口/协议命名（例如端口名填</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`<font style="background-color:rgb(252, 252, 252);">grpc</font>`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">）。」</font>



#### <font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">如何调权重（核心，40 秒）</font>
<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">「</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">gateway 模式</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">：权重调在</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Ingress + Service</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">这条链上——本质是</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Ingress 多个 backend 之间按比例切</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，例如从原来的</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">…tritoninferenceserver</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">迁到</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">…beilian-gw:31581</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">；我们界面是</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">0～10000 千分比</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">0 全老、10000 全新</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">。</font>

**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">mesh 模式</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">：权重调在</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">HTTPRoute</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">和</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">VirtualService</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">上——</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">HTTPRoute</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">用</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">backendRefs</font>**`**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">的</font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**`**<font style="background-color:rgb(252, 252, 252);">weight</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">在多个</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Service</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">之间分；</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Istio</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">用</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">VirtualService 里</font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**`**<font style="background-color:rgb(252, 252, 252);">route.destination</font>**`**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">的</font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**`**<font style="background-color:rgb(252, 252, 252);">weight</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，子集标签一般在</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">DestinationRule</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">里。两层理论上能叠，线上一般会</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">固定只在一层做主灰度</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，避免 Ingress 和 Mesh 各调一半、不好排障。</font>

**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">纯 ExternalName 直连</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">：</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Service 自己没有百分比字段</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，要灰度就得</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">上层 mesh（回到 VS）</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">、</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">双 Service + 入口切流</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，或</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Rollouts</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">之类，不能指望只改一个 ExternalName 就分权。」</font>



#### <font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">和 Istio / Envoy 的关系（15 秒）</font>
<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">「</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">VirtualService 是 Istio CRD</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，不是 Envoy 原生对象；</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Envoy 跑的是翻译后的路由</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">。</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">HTTPRoute</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">是</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Kubernetes Gateway API</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">；在 Istio 集成场景下可以由</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">Istio 转成 Envoy 配置</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">。面试里我会说成：</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">配置在 CRD，执行在 Envoy</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">。」</font>



#### <font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">排查 / 工程化（20 秒，可选）</font>
<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">「排查时我用过一个</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">search_service</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">小脚本：</font>`**<font style="background-color:rgb(252, 252, 252);">kubectl</font>**`**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>****<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">拉 Ingress / HTTPRoute / VirtualService / Service</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，从域名反查</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">beilian、31581、</font>**`**<font style="background-color:rgb(252, 252, 252);">externalName</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">或</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>`**<font style="background-color:rgb(252, 252, 252);">staticAddress</font>**`<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，把</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">ACK 侧哪个对象</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">和</font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">贝联哪个 FQDN</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"> </font><font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">对上，避免靠口口相传。」</font>



#### <font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">收尾一句</font>
<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">「总结：</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">gateway 调 Ingress 后端权重；mesh 调 HTTPRoute / VirtualService 的 weight；协议以贝联 Triton gRPC 为主</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">，和 mesh/gateway </font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">类型正交</font>**<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);">。」</font>

<font style="color:rgba(20, 20, 20, 0.92);background-color:rgb(252, 252, 252);"></font>

### 亮点 5：统一错误语义与治理动作
+ 路由层可对不同 Provider 走链式处理，但对外保持统一响应语义。
+ 结合权限中间件与门禁策略（如新建推理服务入口治理），做到“能力收敛 + 风险可控”。

### 亮点 6：Hugging Face 一键拉模型 → NAS（K8s Job）
+ **场景**：平台侧希望「点一下」把 Hugging Face Hub 上的模型拉到训练/推理工作区可读的共享盘上，避免研发本机翻墙/重复拷贝。
+ **做法**：控制台调 `POST /api/v1/model/job/huggingface-download/create`（见 `controller/model/job.go`），服务端组装 `HuggingfaceJobCreate`（cluster/namespace/model、可选 HF 用户名与 Token），调用 `pkg/kubernetes/job/huggingface_download.go` 创建 **Job**：镜像 `algorithm-harbor.soulapp-inc.cn/sae/huggingface:cli`，入口 `/hfd.sh` 读取 `model` 环境变量；下载参数侧用 `aria2c`** 多连接**（`-x 4`）加速；挂载命名空间下 **PVC** 到 `/models`，`subPath` 为 `huggingface`，权重落在共享存储的固定子树，供后续 Triton/训练任务挂载同一 PVC 使用。
+ **面试要点**：这是 **API 异步化 + Job 计算存储分离**：控制面只负责创建 Job、落库 `model_job` 状态；真正下载在 Pod 内完成，失败可 `retry=true` 先删旧 Job 再重建。

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777015506819-1429cdf4-d03b-40bf-8a4f-84fee3158062.png" width="960" title="" crop="0,0,1,1" id="u33eb8642" class="ne-image">

---

## 七、核心业务范围（按模块）
1. 推理服务治理：列表、详情、扩缩容、迁移、配置更新。
2. 训练任务治理：Training/TFJob/Cron 生命周期与联动。
3. GPU 资源治理：NodePool、资源组、独占 GPU、共享显存、抢占 GPU、CPU 池、资源使用观测。
4. K8s 运维能力：Pod、Deployment、Service、Ingress、日志、事件、资源查询。
5. 发布与构建观测：Argo Rollouts、Tekton PipelineRun/Task。
6. 平台与资产能力：Harbor、GitLab、模型元数据与搜索聚合。
7. **模型与制品下载**：Hugging Face 一键拉取（`huggingface-download` Job → PVC `subPath: huggingface`）、OSS/HTTP 下载 Job、制品异步上传 NAS 等（与 `modelArtifact`、SAE NAS 能力协同）。

---

## 八、边界与约束（避免面试误导）
+ 这是后端控制面，不是前端工程。
+ FAISS 在这里主要体现为任务运维能力，不要表述成通用 RAG 平台。
+ 某些创建入口受产品策略限制（如外置到贝联控制台），要按真实产品边界描述。
+ **watcher 与 server 的边界**：server 只做同步 API 与编排；跨集群 Watch、训练/Cron 事件消费、贝联定时同步在 **watcher**；不要把 watcher 里的逻辑说成「都在 Gin 里同步跑完」。
+ **GPU 调度边界**：SAI 做的是资源池抽象、准入校验、PodSpec 生成和治理入口，不要说成自研 Kubernetes Scheduler 或自研 GPU device plugin。
+ **混部边界**：可讲“通过 NodePool 做可控混部和隔离”，不要讲成所有在线/离线任务无差别混跑。

---

## 九、可被追问的问题（建议准备）
1. 新增一个云厂商时，哪些代码层会改，哪些层不会改？
2. 标准 K8s 动作抽象如何避免“最小公约数”过度收敛？
3. Envoy 控制面网络打通的幂等与回滚策略如何做？
4. 链式 Provider 路由如何保证错误语义统一？
5. 多平台并存时，如何做可观测与故障定位？
6. **HF 拉模 Job 如何排障？**（PVC 挂载、`subPath`、镜像日志、`retry` 删建 Job、`model_job` 表状态）
7. **GPU 调度具体怎么做？**（NodePool → `nodeSelector` / `tolerations` / `limits`，最终仍由 K8s scheduler 调度）
8. **共享显存和独占 GPU 如何区分？**（`nvidia.com/gpu` vs `aliyun.com/gpu-mem`，资源池类型和资源字段要匹配）
9. **混部如何避免影响在线？**（稳定池/共享池/抢占池分层，关键在线不用抢占池，离线任务可重试）
10. **服务异构如何统一？**（服务画像统一、Provider 适配、日志/事件/Pod/资源组操作统一）

---

## 十、代码锚点（复习用）
+ 主入口：`cmd/server/main.go`
+ 路由注册：`cmd/server/routes/*`
+ 鉴权与中间件：`pkg/gin/route/routemanager.go`、`middleware/*`
+ Provider 聚合：`api/api.go`、`pkg/provider/*`
+ 推理路由：`cmd/server/routes/inference.go`
+ 训练路由：`cmd/server/routes/training.go`
+ **NodePool 资源池**：`api/core/cluster_nodepool.go`、`controller/core/nodepool.go`
+ **推理服务节点池变更**：`controller/inference/service.go`、`pkg/kubernetes/serve/update.go`
+ **训练任务资源模板**：`api/training/training.go`、`pkg/runtime/tensorflow/template.go`、`pkg/runtime/tensorflow/cron.go`
+ **异构工作负载**：`api/serverless/nuclio.go`、`controller/function/nuclio.go`、`api/faiss/faiss.go`、`pkg/runtime/faiss/template.go`
+ **异步与 Job**：`cmd/watcher/main.go`、`pkg/kubernetes/event/*`
+ **HF 拉模 Job**：`pkg/kubernetes/job/huggingface_download.go`、`controller/model/job.go`、`cmd/server/routes/model.go`

---

## 十一、追问应答（高频）
1. **为什么新增厂商可以快？**  
因为上层协议和控制器不动，主要改 Provider 适配层。
2. **多云抽象最难点是什么？**  
不是 CRUD，而是状态与错误语义对齐；平台差异必须被隔离在 Provider 内。
3. **Envoy 打通如何保证稳定？**  
按幂等、可观测、可回滚设计，避免单次配置变更影响整体链路。
4. **watcher 解决什么问题？**  
消费 K8s 中训练/Cron/FAISS 等事件并驱动平台状态；定时同步贝联元数据；与 `cmd/server` 进程分离。
5. **为什么 HF 拉模用 Job 而不是 API 里同步下？**  
体积与时延不可控，Job + PVC 才能隔离资源并复用共享存储。
6. **SAI 的 GPU 调度是不是自研调度器？**  
不是。SAI 做的是控制面资源抽象：把 NodePool、资源组、GPU card / GPU memory 等业务选择翻译成 `nodeSelector`、`tolerations` 和容器 `limits`，最终调度仍交给 Kubernetes 和底层 GPU 插件。
7. **混部怎么讲才不虚？**  
讲“可控混部”：独占池保在线稳定性，共享显存池提升小模型利用率，抢占池承接可重试训练/构建/下载任务；隔离靠节点池、污点容忍、资源 limits、存储路径和权限边界共同完成。
8. **异构服务统一难在哪里？**  
难点是服务模型、状态、日志、事件和资源规格不一致。SAI 用统一服务画像 + Provider 适配，把 ACK/KServe、PAI、贝联、Nuclio、TFJob、FAISS 的操作口径收敛到同一套控制面。

---

## 十二、一句话总结（收尾）
我在这个项目里的核心贡献是把异构平台复杂性收敛到控制面：**多云侧做统一抽象，资源侧做 NodePool/GPU 治理，网络侧做一键打通**；同时用 **watcher 承接异步事件、用 Job 承接重下载**，最终让业务通过统一入口稳定获得跨平台能力。

---

_更新时间：2026-04-29_
