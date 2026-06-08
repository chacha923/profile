> **项目定位**：基于 [tektoncd/pipeline](https://github.com/tektoncd/pipeline) **v0.32.4** fork 的内部分支，**只用到 Tekton，没有 ArgoCD**。控制器跑在 K8s 上，对外提供 `Task / Pipeline / TaskRun / PipelineRun` 等 CRD，承载内部所有语言（Go / JDK / Node / Python / 算法）的 **构建 + 推镜像 + 制品上传** 流水线。
>
> **本文用途**：面试口述稿，覆盖三块——**Tekton 整体架构** / **一次 PipelineRun 的运行原理** / **我们在上游基础上改了什么**，并附常见追问。
>



# 开场白
我们维护的是一个基于 **Tekton Pipelines v0.32.4** fork 的内部 CI 引擎。控制器是标准的 K8s Operator —— Informer + Workqueue + Reconcile —— 把 PipelineRun 拆成 TaskRun，再把每个 TaskRun 拆成一个 Pod，每个 step 是 container；通过 **统一 **`/tekton/bin/entrypoint`** + 共享 emptyDir 的文件信号灯** 实现 step 串行和 results 回传。



我们在上游基础上做的二开很克制：**镜像内网化、关掉运行期 manifest 反查、关掉 ko 相关的 changeset、加了个 **`fcp`** 制品收集小工具**；曾经做过镜像 registry rewrite，后来下沉到 containerd `hosts.toml`。大头其实是 `deploy/`** 下按语言沉淀的几十个 Pipeline / Task 模板** 和 buildkit / Harbor / scancode 等周边集成。



Tekton 落地最大的坑不是能不能跑起来，而是规模化之后的治理问题。



第一是控制面压力。PipelineRun、TaskRun 都是 CRD，高频流水线会产生大量对象，必须做历史清理、namespace 隔离和状态归档，否则 etcd 和 apiserver 压力会变大。

第二是 workspace 和 PVC 生命周期。Task 之间共享数据看似简单，但如果 PVC 复用、清理和并发隔离没做好，很容易出现构建上下文污染、存储膨胀和任务互相影响。

第三是权限和 Secret 管理。构建、推镜像、部署生产环境不应该共用一个高权限 ServiceAccount，要做最小权限拆分，避免 CI 任务拿到过大的生产权限。

第四是镜像构建本身。Tekton 只是编排，不解决 Docker 构建、缓存、镜像仓库认证、多架构构建这些问题。生产里通常要结合 Kaniko、BuildKit 或远程构建服务。

第五是平台化能力。Tekton 原生只给 PipelineRun / TaskRun 状态，业务平台还需要自己的状态机、日志聚合、失败归因、审计、审批和并发控制。所以我更倾向于把 Tekton 当执行引擎，而不是完整发布平台。

# 整体架构
## 部署形态
Tekton 在集群里就是一组 Deployment + 一堆 CRD：

+ `tekton-pipelines-controller`：核心控制器，承载所有 Reconcile 逻辑，watch CRD 与 Pod。
+ `tekton-pipelines-webhook`：Admission Webhook，做 CRD 的默认值填充与校验、版本转换（v1alpha1 ↔ v1beta1）。
+ **CRD**：`Task`、`ClusterTask`、`Pipeline`、`TaskRun`、`PipelineRun`、`Run`、`PipelineResource` 等。
+ **辅助镜像**：`entrypoint`、`nop`、`git-init`、`kubeconfig-writer`、`pullrequest-init`、`imagedigest-exporter`——由控制器在创建 Pod 时按需注入。

## 抽象层次
| 层 | 对象 | 类比 |
| --- | --- | --- |
| **模板层** | `Task`、`Pipeline` | 类、函数定义 |
| **执行层** | `TaskRun`、`PipelineRun` | 一次调用、运行实例 |
| **承载层** | Pod（每个 TaskRun 对应一个 Pod，每个 Step 是一个 container） | 真正干活的进程 |


面试一句话：**Tekton 把 CI 流水线当成「K8s 一等资源」**，模板和触发分离，可 RBAC、可 audit、可 watch。

## Pipeline 内的依赖与编排
+ **DAG**：Task 之间用 `runAfter` 或 `params/results` 引用形成有向无环图，Reconcile 时按拓扑顺序逐批触发。
+ **Finally**：无论成功失败都会跑的收尾任务（通知、清理、上报指标）。
+ **When / Conditions**：条件跳过。
+ **Workspaces**：在 Pipeline 内多个 Task 之间共享的目录（同一个 PVC / emptyDir）。

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777007213304-4c12f575-6c23-45a4-be63-cc40e23fde2d.png" width="1600" title="" crop="0,0,1,1" id="pjOb2" class="ne-image">

# 运行原理 — 一条 PipelineRun 的全生命周期
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778563419027-9fe1903d-291c-40ca-a6d9-abecbb3f53cb.png" width="1920" title="" crop="0,0,1,1" id="oB5EH" class="ne-image">

## 用户/平台创建 PipelineRun
通过 `kubectl apply` 或上层平台调 K8s API 写入 PipelineRun，里面引用 `pipelineRef`，传 `params`、绑 `workspaces`。经 **Webhook**：默认值填充（如默认 ServiceAccount、默认 timeout）+ 校验（参数是否齐、workspace 是否绑全）。

## Controller 看到事件
控制器内部典型 **Operator 套路**：

+ **Informer** 通过 List + Watch 把 PipelineRun 对象同步到本地缓存；
+ 事件回调把 `<namespace>/<name>` 丢进 **Workqueue**；
+ 多个 worker 协程从 queue 里取 key，调用 **Reconcile** 函数。

Reconcile 是 **幂等** 的：每次都重新算一遍「期望状态 vs 实际状态」，差什么补什么。

## PipelineRun → 多个 TaskRun
Reconcile 解析 DAG，按依赖顺序为每个就绪的 Task 创建 **TaskRun** 子对象（`OwnerReference` 指向 PipelineRun）。TaskRun 创建后会触发 TaskRun controller 的 Reconcile，进入下一层。

## TaskRun → Pod（核心改写发生在这里）
TaskRun controller 干的事：

1. **解析 Task**（Task / ClusterTask / 远端 bundle）。
2. **构造 Pod**：每个 `step` 变成 Pod 里的一个 container；`sidecars` 直接是 sidecar container。
3. **重写 entrypoint**：把每个 step 的 `command` 改成统一二进制 `/tekton/bin/entrypoint`，原来的命令变成 `entrypoint` 的参数。
4. **挂工作目录**：`/workspace`、`/tekton/results`、`/tekton/run/<idx>` 等约定路径，用 emptyDir 或 PVC 实现。
5. **挂凭据**：从 ServiceAccount 关联的 Secret（git/docker 类型）拷贝到 `/tekton/creds`，业务进程读 `$(credentials.path)` 即可。
6. **注入 init container**：把 `entrypoint` 二进制 `cp` 到 `/tekton/bin/`，把 `nop` / `working-dir` 等准备好。

## Step 串行 + 入口进程协作（必背）
+ K8s 本身**不能保证 container 串行**——所有 container 是并行启动的。
+ Tekton 用 `/tekton/bin/entrypoint` 包装每个 step，做了一套「文件信号灯」：
    - 第 N 个 step 启动后**先阻塞等** `/tekton/run/<N-1>/out`；
    - 等到了再 `exec` 真正的命令；
    - 命令退出后写 `out`（成功）/ `err`（失败），同时把退出码、终止信息写到 `/tekton/termination`；
    - 下一个 step 的 entrypoint 据此放行或终止。
+ 这样在不依赖 K8s 调度顺序的前提下，实现了 **step 串行、可超时、可断点、可上报 results**。

**面试金句**：Tekton 的 step 串行不是靠 K8s 排序，而是靠 **统一入口 + 共享 emptyDir + 文件信号** 实现的。这也解释了为什么每个 step 的 command 都被改写成 `/tekton/bin/entrypoint`。

## 状态回写
+ 控制器持续 watch Pod 状态，把容器退出码、Step 状态、Results、原因等聚合写回 **TaskRun.status**；
+ TaskRun 完成 → PipelineRun 重新 Reconcile → 触发下一批 Task → ……直到 DAG 跑完；
+ 终态打 `Succeeded=True/False` 到 `status.conditions`，外部系统 watch 一下就知道结果。

## 资源回收
Finalizer 处理收尾；Pod 默认保留（便于看日志），由 GC 或上层平台按策略清理；大规模场景下要关注 PVC、emptyDir、Pod 数量对集群的压力。

---

# Tekton v0.32.4 上做了哪些二次开发
二开范围分三块：**Go 控制器代码改动（少而关键）** / **流水线 YAML 模板（大头）** / **构建与运维工具链**。

## 控制器源码改动（核心，一共 4~5 处）
### 默认镜像全部内网化（`cmd/controller/main.go`）
+ 上游：`entrypoint-image`、`nop-image`、`git-image`、`kubeconfig-writer-image`、`shell-image`、`pr-image`、`imagedigest-exporter-image` 默认空，**必须** 启动时通过 flag 传入，否则 `Images.Validate()` 直接 `log.Fatal`。
+ 我们的改动：把这 7 个默认值都写成 `harbor.soulapp-inc.cn/sae/pipeline-*:v0.32.4`，并 **注释掉 **`Images.Validate()`。
+ **为什么**：内部环境镜像固定，不想每次部署都堆一长串 flag；同时方便没填某些次要镜像时也能起来。
+ **可能被追问**：「为什么不放 ConfigMap？」答：可以，但当前以默认值 + 内部镜像规范约束足够；ConfigMap 改动需要 reload，收益不明显。

### 跳过 `resolveEntrypoints`（`pkg/pod/pod.go`）
+ 上游逻辑：如果 step 没写 `command`，控制器会**真的去镜像仓库拉 manifest**，反查容器 ENTRYPOINT 来填上。
+ 我们的改动：**注释掉 **`resolveEntrypoints`** 调用**，强制要求所有 step 显式写 `command`。
+ **为什么**：
    1. 内网 Harbor 走 robot 账号，控制器去 manifest 时鉴权链路复杂、容易报权限错误；
    2. 走外网拉 manifest 慢且不稳定；
    3. 显式 `command` 在 YAML 里更可读、可审计。
+ **代价**：所有内部模板必须写明 `command`（不是技术债，是规范）。

### 关掉 `changeset.Get()` 注入版本注解（`pkg/pod/pod.go`、`pkg/reconciler/taskrun/taskrun.go`）
+ 上游：用 `knative.dev/pkg/changeset` 读 `kodata/HEAD` 拿 git commit，写到 Pod / TaskRun 的 `pipeline.tekton.dev/release` 注解里。
+ 我们的改动：**注释掉这两处**。
+ **为什么**：上游用 [ko](https://github.com/google/ko) 打镜像，自动塞 `kodata/`；我们改用普通 `Dockerfile`（debian-slim）`ADD` 二进制（见 `deploy/Dockerfile` + `deploy/build.sh`），镜像里没有 `kodata/HEAD`，调用会 fatal。最简单的处理就是注释掉。
+ **可能被追问**：「为什么不改用 ko？」答：内网构建、推镜像、基础镜像规范都已经走 Harbor 流水线，引入 ko 收益小、改动面大。

### 新增 `cmd/fcp/main.go`（自定义辅助二进制）
+ 上游 cmd 列表里没有 `fcp`，是我们加的。
+ **功能**：按 glob 文件名（如 `soul-*.war`）在某目录递归找文件，复制到目标目录；目标已存在则跳过。
+ **用法**：在制品流水线（如 JAR/WAR 上传 OSS 之前）作为一个 step，把 `output/` 下的产物按通配收齐，避免每条流水线都手写一段 `find ... -exec cp ...`。
+ **为什么独立做二进制**：在 alpine/scratch 等极简基础镜像里也能跑（静态编译、无依赖）；比一段 shell 更可控、错误码语义清晰（找不到返回 404 等）。

### 历史上做过 Image Registry Rewrite（已下线）
+ 一段时期内引入过 `pkg/registry/repace.go` + `pkg/apis/pipeline/options.go` 的 `--registry-*` 启动参数，用于把 step 镜像里的 `docker.io / k8s.gcr.io / gcr.io` **自动改写** 到内部 Harbor 缓存仓。
+ 后来在 `clear image registry` 提交里**整体撤掉**了，原因是改用 **containerd **`hosts.toml`** 的 mirror 配置**（见 `deploy/containerd/certs.d/...`）：在节点级配置 mirror 更通用，所有 Pod 都能受益，不用控制器侵入。
+ **面试金句**：能展示一次「在控制器里 hack」→「下沉到容器运行时配置」的演进过程，体现对 **关注点分层** 的理解。

## 流水线 YAML 模板（业务侧主战场）
这块占比最大，按语言/场景分目录沉淀模板：

+ `deploy/pipeline/go/`：Go 1.17 ~ 1.25 多版本、`go1-22-nerdctl.yaml` 等；统一 `git-init` → `go build` → `buildctl build + push=true`。
+ `deploy/pipeline/jdk/`：Maven 3.6（JDK 8 / 17）+ scancode（代码扫描，含禁止 `-Ptest` 进 prod 的安全策略）+ testcase（对接内部 Jarvis/SAE 用例平台）。
+ `deploy/pipeline/node14|node16/`：Node 流水线 + npm 内网源。
+ `deploy/pipeline/python/` 与 `deploy/pipeline/algo/`：算法侧——含 NAS 下载、推理服务部署（在线发布、灰度发布）等。
+ `deploy/pipeline/artifact/`：JAR/WAR 制品 → OSS / 内部 artifact API 回调。

以及配套的 **可复用 Task**（`deploy/task/`）：制品 push、`testcase-java`（结果回调发布门户）等。

## 构建与运维工具链
+ **构建方式**：`deploy/Dockerfile` + `deploy/build.sh`，`go build` 出 `pipeline-controller` 然后塞进 `harbor.soulapp-inc.cn/arch/debian:buster-slim`，镜像 tag 形如 `v0.32.4-251023`。
+ **buildkit / nerdctl**：自带 `deploy/buildkit.yaml`、`deploy/buildkit-prune.yaml`（CronJob 定期清缓存）；Tekton step 统一使用 `harbor.soulapp-inc.cn/sae/nerdctl:v2.1.6` 作为工具镜像，但实际执行的是 `buildctl build`，真正完成构建和推镜像的是节点上的 `buildkitd + containerd`，避免依赖 dind / 节点 docker。
+ **containerd 配置**：`deploy/containerd/certs.d/harbor-test.soulapp-inc.cn/hosts.toml(.example)`——节点级配置 Harbor mirror 与认证，配合上面 (5) 把镜像改写下沉到运行时。
+ **私有 registry**：`deploy/registry/` 提供 docker-compose + redis 缓存的 pull-through cache，离线/受限网络环境下作为 Harbor 上游缓存。
+ **Dashboard / Ingress / Secret**：`deploy/release/` 一站式安装包，包括 Harbor robot 账号 `dockerconfigjson` 的生成脚本。

---

# 面试官高频追问 & 怎么答
## Tekton 怎么保证多个 step 按顺序执行？K8s 不是并行起容器吗？
见「Step 4」。**统一 entrypoint + 文件信号灯 + emptyDir 共享卷**。可以加一句：「这套设计的好处是 step 还能拿到上一个 step 的 results 文件，做 DAG 内的小数据传递。」

## Tekton Controller 是怎么实现的？
标准 K8s Operator —— **client-go Informer / Lister + Workqueue + Reconcile loop**。内部用 knative 的 controller 框架包了一层（项目里能看到 `knative.dev/pkg/controller`、`changeset` 等依赖）。Reconcile 幂等，关键状态全在 CRD 的 `status` 里，重启控制器不丢。

## PipelineRun 失败了怎么排查？
**Run.status.conditions → 看哪个 Task 挂了 → 对应 TaskRun → 对应 Pod → 看哪个 Step container 退出码非 0 → 看 **`/tekton/termination`** 终止信息或 step container 日志**。注意 step 是**串行**的，所以前面卡住会让后面 step 一直在 entrypoint 等文件，看起来像「Pod 是 Running 但其实没动」。

## 你们这个 fork 改了上游哪些东西？为什么不直接用上游？
见第三章。重点四条：

1. **默认镜像内网化** + 关掉 Images 校验，部署体验更好；
2. **关掉镜像 manifest 反查 entrypoint**，避开内网 Harbor 鉴权 + 加速调谐；
3. **关掉 changeset 版本注解**，因为我们用 Dockerfile 而非 ko 打包；
4. **加了一个 **`fcp`** 辅助二进制** 给制品流水线用。

战术总结：**控制器侧改动尽量少**，业务能力主要靠 **大量 deploy/ 下的 Pipeline / Task 模板** 沉淀，这样上游升级时合并冲突小。

## Tekton vs Jenkins / GitLab CI ？
+ **K8s 原生**：调度、隔离、弹性、RBAC 直接用 K8s 的；Jenkins 还得自己维护 master/agent。
+ **声明式 + 可复用 Task**：Pipeline / Task 是 CRD，可被 watch、可 RBAC、可 GitOps。
+ **代价**：YAML 写法相对啰嗦，没有 Jenkins Groovy 那种「想干嘛干嘛」的灵活，但换来的是可治理。

## Workspace 用 PVC 还是 emptyDir？
+ 单 Pipeline 跨 Task 共享：必须 PVC（不同 TaskRun = 不同 Pod，emptyDir 出不了 Pod）。
+ 单 Task 内 step 共享：emptyDir 即可。
+ 大文件 / 缓存场景：PVC + ReadWriteMany 或者直接挂 NAS（我们算法 pipeline 就是这么干的）。

## 大规模 Run 并发对集群的压力？
+ 主要压力点：**API Server / etcd**（CRD 事件量大）、**控制器单点**（默认单副本，HA 需要 lease 选主）、**节点 Pod 数量上限**。
+ 缓解：限制并发、Pod GC、Workspace 用瞬时存储、考虑分 namespace 多控制器实例。

## 为什么不用 ArgoCD？
**这个仓库本身就只是 CI 引擎，ArgoCD 是另一码事**。Tekton 解决「在集群里把流水线跑起来」，ArgoCD 解决「集群里的应用配置和 Git 是否一致」。要做完整 GitOps，可以叠加一个 ArgoCD，但不是这个项目的范围。

## Pipeline Pipelinerun Task Taskrun 如何清理
> Tekton 的历史资源主要包括 PipelineRun、TaskRun、TaskRun 对应 Pod，以及 workspace 产生的 PVC。清理不能只删 PipelineRun，因为 TaskRun 才承载很多 step 执行明细和日志索引；PVC 也可能因为 workspace 声明方式不同而不会自动回收。
>
> 如果集群是 Operator 管理，我会优先启用 TektonConfig 里的 Pruner 或新版 Tekton Pruner，按 namespace 配置 TTL 和 history limit，比如成功保留少一点、失败保留久一点。对于没有内置 Pruner 的版本，可以用 CronJob 定期扫描 completionTime，删除过期 PipelineRun / TaskRun，并额外兜底清理 orphan PVC 和异常残留 Pod。
>
> 真正生产里还要先解决日志和结果归档问题，比如接 Loki、ClickHouse、S3 或 Tekton Results。否则资源一清，Dashboard 上的历史日志也会丢，后续排障会断。我的原则是：K8s 里的 Tekton CR 只保留短期排障现场，长期审计和日志必须落外部存储。
>

Tekton 官方的 Pruner 组件用于自动清理已完成的 `PipelineRun` 和 `TaskRun`，支持基于 TTL、成功/失败历史数量等策略。   
如果通过 Tekton Operator 安装，官方推荐通过 `TektonConfig` 管理 Pruner；但要注意 **job-based pruner 和 event-based pruner 不能同时启用**。

Tekton 运行一次流水线，通常会产生：

```yaml
PipelineRun
  └── TaskRun
        └── Pod
              ├── step containers
              ├── init containers
              └── sidecar containers
```

合理的清理策略

```yaml
成功的 PipelineRun / TaskRun：
  保留 3~7 天，或者每个 Pipeline 保留最近 10~20 条

失败的 PipelineRun / TaskRun：
  保留 7~30 天，或者每个 Pipeline 保留最近 50 条

运行中的：
  绝对不删

卡死中的：
  单独处理，比如超过 24h 仍 Running 的标记/终止/告警
```



## buildkit 缓存体系
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778564523668-572eaf70-d88b-432a-ac74-efe730ae2ca5.png" width="1044" title="" crop="0,0,1,1" id="u0158c758" class="ne-image">



BuildKit 的缓存主要会进入 containerd 的内容存储和 snapshotter 体系里，概念上类似：

```yaml
buildkitd
  ├── content store        # blob、layer、cache 数据
  ├── snapshotter          # overlayfs/native/stargz 等快照
  ├── metadata db          # cache key、依赖关系、LLB graph 结果
  └── gc policy            # 按容量/时间清理缓存
```

### 完整方案
BuildKit 可以缓存构建图和中间层，但真正面对“构建环境很大”的问题，不能只靠缓存；应该把稳定的大环境前置成基础镜像，把易变业务层后置，再用 registry cache 和 cache mount 加速增量构建。

```yaml
1. 基础环境镜像
   - CUDA / Python / Java / Go / Node
   - 系统依赖
   - 大型 ML 框架
   - 公司通用 SDK
   - 低频更新

2. 业务构建镜像
   - requirements.txt / pom.xml / package-lock.json 单独 COPY
   - 使用 RUN --mount=type=cache 缓存包管理器目录
   - 业务代码最后 COPY

3. CI 外部缓存
   - registry cache
   - main cache + branch cache
   - mode=max
   - 定期 GC

4. 镜像仓库治理
   - 基础镜像版本化
   - cache ref 单独命名
   - 过期 cache 清理
   - 避免所有项目共用一个巨大 cache tag
```

### 清理机制
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778564957737-f902f823-acca-4906-82f4-f7ce104e9ff3.png" width="1032" title="" crop="0,0,1,1" id="u2fc62f2e" class="ne-image">

# BuildKit / buildctl 构建链路补充
这部分不是泛泛而谈的 Docker 知识，而是**你们这个仓库里真实落地的那套链路**。面试和排障时，最容易讲错的一点是：`docker-build`** 这个 step 虽然跑在 Tekton Pod 里，但它并不是在容器里“自己完成构建”**。

## `buildkitd`、`buildctl`、`nerdctl` 三者到底是什么关系
+ `buildkitd`：BuildKit 的守护进程，真正负责执行 Dockerfile、管理缓存、拉基础镜像、推目标镜像。
+ `buildctl`：BuildKit 的客户端；当前流水线模板里，`docker-build` step 直接执行的就是它。
+ `nerdctl`：面向 containerd 的 Docker 风格 CLI；`nerdctl build` 底层也会走 BuildKit，但这套仓库里的主路径不是它。
+ 这个仓库里之所以经常看到 `harbor.soulapp-inc.cn/sae/nerdctl:v2.1.6`，更多是因为**这张工具镜像同时带了 **`nerdctl`**、**`buildctl`**、**`buildkitd`** 二进制**，不是说流水线真的在执行 `nerdctl build`。
+ `images/nerdctl/Dockerfile` 也能看出来：它基于官方 `ghcr.io/containerd/nerdctl:v2.1.6`，只额外安装了 `curl`、`git` 并覆盖了 `buildkitd.toml`。

## 为什么 K8s 全量切到 containerd 后，这套流水线仍然成立
因为这里的构建链路从一开始就**不依赖 Docker Engine**：

+ 不是 `docker build`；
+ 不是 dind（Docker in Docker）；
+ 而是 `buildctl` → `buildkitd` → 宿主机 `containerd` → Harbor。

所以从架构上说，**“K8s 升级后全量使用 containerd” 与这套流水线是完全一致的**。出了问题，优先怀疑的是 **buildkitd / containerd / Harbor 鉴权 / 入口协议**，而不是“没有 Docker 了”。

在我们的 Tekton 流水线里，`docker-build` 容器本身并不直接完成构建；它只是携带 `buildctl` 客户端和源码上下文，真正执行 Dockerfile、落缓存、访问 Harbor 的是同节点上的 `buildkitd + 宿主机 containerd`。这也是为什么 K8s 升级到纯 Containerd 后，这套流水线依然成立。

## 构建环境与宿主机关系图
下面这张图是最值得背下来的：

```latex
+--------------------------------------------------------------------------------+
| pipeline 节点 / 宿主机                                                          |
|                                                                                |
|  +--------------------------- Tekton TaskRun Pod ---------------------------+  |
|  | docker-build step                                                      |  |
|  | image: harbor.soulapp-inc.cn/sae/nerdctl:v2.1.6                        |  |
|  | command: buildctl build ...                                            |  |
|  |                                                                        |  |
|  | 挂载的 hostPath:                                                       |  |
|  |   /run/buildkit                                                        |  |
|  |   /var/lib/container/buildkit                                          |  |
|  |   /run/containerd/containerd.sock                                      |  |
|  |   /var/lib/containerd                                                  |  |
|  +----------------------------------+-------------------------------------+  |
|                                     |                                        |
|                                     | 通过共享的 /run/buildkit socket        |
|                                     v                                        |
|  +---------------------------- buildkitd DaemonSet Pod --------------------+  |
|  | command: buildkitd                                                    |  |
|  | config: /etc/buildkit/buildkitd.toml                                  |  |
|  | worker.containerd.address   = /run/containerd/containerd.sock         |  |
|  | worker.containerd.namespace = buildkit                                |  |
|  +----------------------------------+-------------------------------------+  |
|                                     |                                        |
|                                     | 访问宿主机 containerd.sock             |
|                                     v                                        |
|                          宿主机 containerd                                   |
|                          读取 /etc/containerd/certs.d/<registry>/...         |
+------------------------------------+-------------------------------------------+
                                     |
                                     | HTTPS pull / push
                                     v
                           harbor.soulapp-inc.cn / harbor-test.soulapp-inc.cn
```

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778565338305-f7facf53-dc4d-4a0b-af83-eac3b23ffbdc.png" width="1143" title="" crop="0,0,1,1" id="uee9beefc" class="ne-image">

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777007239113-a085afec-877d-45be-a34a-87effd3e5bc6.png" width="2100" title="" crop="0,0,1,1" id="L6jQ3" class="ne-image">

这张图想表达的关键点只有一句话：**Task Pod 只是带着源码和 **`buildctl`** 客户端；真正完成 Dockerfile 构建、缓存复用、Harbor 拉推的是同节点上的 **`buildkitd + 宿主机 containerd`**。**

<font style="color:rgb(56, 58, 66);">TaskRun Pod 里只有源码和 buildctl 客户端，真正执行 Dockerfile 构建、缓存复用、镜像拉推的是同节点上的 buildkitd Pod 和宿主机 containerd。</font>

### <font style="color:rgb(56, 58, 66);">三层关系</font>
1. <font style="color:rgb(56, 58, 66);">Tekton TaskRun Pod</font>
2. <font style="color:rgb(56, 58, 66);">buildkitd DaemonSet Pod</font>
3. <font style="color:rgb(56, 58, 66);">宿主机</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">containerd</font>

### <font style="color:rgb(56, 58, 66);">TaskRun Pod 干什么</font>
<font style="color:rgb(56, 58, 66);">docker-build step 跑在 TaskRun Pod 里，镜像一般是 harbor.soulapp-inc.cn/sae/nerdctl:v2.1.6 这类工具镜像。</font>

<font style="color:rgb(56, 58, 66);">它的职责不是“自己完成构建”，而是：</font>

+ <font style="color:rgb(56, 58, 66);">挂载源码工作区，拿到</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">Dockerfile</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">和构建上下文</font>
+ <font style="color:rgb(56, 58, 66);">执行</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildctl build ...</font>
+ <font style="color:rgb(56, 58, 66);">通过共享的</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildkit</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">socket 把构建请求发给</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildkitd</font>

<font style="color:rgb(56, 58, 66);">它更像“构建发起方”。</font>

### <font style="color:rgb(56, 58, 66);">buildkitd Pod 干什么</font>
<font style="color:rgb(56, 58, 66);">buildkitd 以 DaemonSet 跑在每个 pipeline 节点上，基本是“一节点一个 Pod”。</font>

<font style="color:rgb(56, 58, 66);">它负责：</font>

+ **<font style="color:rgb(56, 58, 66);">接收 buildctl 发来的构建请求</font>**
+ <font style="color:rgb(56, 58, 66);">解析 Dockerfile</font>
+ <font style="color:rgb(56, 58, 66);">管理 BuildKit 缓存</font>
+ <font style="color:rgb(56, 58, 66);">调用宿主机</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">containerd</font>
+ <font style="color:rgb(56, 58, 66);">触发基础镜像拉取和目标镜像推送</font>

<font style="color:rgb(56, 58, 66);">它才是“真正执行构建”的地方。</font>

### <font style="color:rgb(56, 58, 66);">宿主机 containerd 干什么</font>
<font style="color:rgb(56, 58, 66);">宿主机 containerd 是最终的运行时后端，buildkitd 通过它完成：</font>

+ <font style="color:rgb(56, 58, 66);">拉基础镜像</font>
+ <font style="color:rgb(56, 58, 66);">管理 snapshot / layer</font>
+ <font style="color:rgb(56, 58, 66);">复用缓存</font>
+ <font style="color:rgb(56, 58, 66);">向 Harbor push 镜像</font>

<font style="color:rgb(56, 58, 66);">在 ACK 升级到纯</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">containerd</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">之后，这条链路仍然成立，因为它本来就不依赖 Docker Engine。</font>

**<font style="color:rgb(56, 58, 66);">两类 Pod 和宿主机是怎么连起来的</font>**<font style="color:rgb(56, 58, 66);">它们不是通过 K8s Service 通信，而是通过同节点上的</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">hostPath</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">挂载共享宿主机目录。</font>

<font style="color:rgb(56, 58, 66);">最关键的共享目录有这几个：</font>

+ **<font style="color:rgb(56, 58, 66);">/run/buildkit</font>**<font style="color:rgb(56, 58, 66);">用途： </font><font style="color:rgb(56, 58, 66);">TaskRun Pod 通过这里的 socket 连到 buildkitd </font><font style="color:rgb(56, 58, 66);">说明： </font><font style="color:rgb(56, 58, 66);">这是 buildctl -> buildkitd 的入口</font>
+ **<font style="color:rgb(56, 58, 66);">/var/lib/container/buildkit</font>**<font style="color:rgb(56, 58, 66);">用途： </font><font style="color:rgb(56, 58, 66);">BuildKit 本地缓存目录 </font><font style="color:rgb(56, 58, 66);">说明： </font><font style="color:rgb(56, 58, 66);">缓存落在宿主机，多个构建可以复用，不在单个 TaskRun 容器生命周期里丢失</font>
+ **<font style="color:rgb(56, 58, 66);">/run/containerd/containerd.sock</font>**<font style="color:rgb(56, 58, 66);">用途： </font><font style="color:rgb(56, 58, 66);">buildkitd 通过这个 socket 调宿主机 containerd </font><font style="color:rgb(56, 58, 66);">说明： </font><font style="color:rgb(56, 58, 66);">这是 buildkitd -> containerd 的入口</font>
+ **<font style="color:rgb(56, 58, 66);">/var/lib/containerd</font>**<font style="color:rgb(56, 58, 66);">用途： </font><font style="color:rgb(56, 58, 66);">containerd 的运行时数据目录 </font><font style="color:rgb(56, 58, 66);">说明： </font><font style="color:rgb(56, 58, 66);">让构建链路直接复用宿主机 runtime 侧的镜像/层能力</font>

**<font style="color:rgb(56, 58, 66);">还有一个不是 Pod 共享、但对链路很关键的目录</font>**

+ **<font style="color:rgb(56, 58, 66);">/etc/containerd/certs.d/</font>****<font style="color:rgb(56, 58, 66);">/hosts.toml</font>**<font style="color:rgb(56, 58, 66);">用途： </font><font style="color:rgb(56, 58, 66);">registry 的 mirror、auth、协议配置 </font><font style="color:rgb(56, 58, 66);">说明： </font><font style="color:rgb(56, 58, 66);">真正和 Harbor 交互时，更多是宿主机 containerd / buildkitd 在读这套配置，不是 TaskRun Pod 里自己 docker login</font>

**<font style="color:rgb(56, 58, 66);">交互顺序</font>**

1. <font style="color:rgb(56, 58, 66);">平台创建</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">TaskRun Pod</font>
2. <font style="color:rgb(56, 58, 66);">docker-build step</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">拿到源码和</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">Dockerfile</font>
3. <font style="color:rgb(56, 58, 66);">step 里执行</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildctl build</font>
4. <font style="color:rgb(56, 58, 66);">buildctl</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">通过</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">/run/buildkit</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">连到同节点</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildkitd</font>
5. <font style="color:rgb(56, 58, 66);">buildkitd</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">根据</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildkitd.toml</font><font style="color:rgb(56, 58, 66);">，通过</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">/run/containerd/containerd.sock</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">调宿主机</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">containerd</font>
6. <font style="color:rgb(56, 58, 66);">containerd</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">拉基础镜像、使用缓存、产出镜像层</font>
7. <font style="color:rgb(56, 58, 66);">再根据 registry 配置把结果 push 到 Harbor</font>

**<font style="color:rgb(56, 58, 66);">哪些东西是共享的，哪些不是</font>**<font style="color:rgb(56, 58, 66);">共享的是：</font>

+ <font style="color:rgb(56, 58, 66);">buildkit socket</font>
+ <font style="color:rgb(56, 58, 66);">containerd socket</font>
+ <font style="color:rgb(56, 58, 66);">BuildKit cache 目录</font>
+ <font style="color:rgb(56, 58, 66);">containerd runtime 数据目录</font>

<font style="color:rgb(56, 58, 66);">不共享的是：</font>

+ <font style="color:rgb(56, 58, 66);">TaskRun Pod 的源码 workspace 本身 </font><font style="color:rgb(56, 58, 66);">说明： </font><font style="color:rgb(56, 58, 66);">源码上下文通常是</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildctl</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">从 TaskRun Pod 本地送给</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildkitd</font><font style="color:rgb(56, 58, 66);">，不是让</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildkitd</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">去读同一个 workspace 目录</font>

**<font style="color:rgb(56, 58, 66);">最容易讲错的一点</font>**<font style="color:rgb(56, 58, 66);">不是：</font>

+ <font style="color:rgb(56, 58, 66);">TaskRun Pod</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">里执行</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">docker build</font>
+ <font style="color:rgb(56, 58, 66);">Pod 自己完成镜像构建</font>

<font style="color:rgb(56, 58, 66);">而是：</font>

+ <font style="color:rgb(56, 58, 66);">Pod 里执行的是</font><font style="color:rgb(56, 58, 66);"> </font><font style="color:rgb(56, 58, 66);">buildctl</font>
+ <font style="color:rgb(56, 58, 66);">真正构建发生在 buildkitd + 宿主机 containerd</font>

## 这套关系在仓库里分别落在哪些文件
1. `deploy/buildkit.yaml`
    - 以 **DaemonSet** 部署 `buildkitd`；
    - **一个节点一个 Pod**；
    - 只调度到 `app_type=pipeline` 的节点；
    - 容器直接 `command: [buildkitd]`；
    - 挂载 `/run/containerd/containerd.sock`、`/var/lib/containerd`、`/var/lib/container/buildkit`、`/run/buildkit`。
2. `images/nerdctl/buildkitd.toml`
    - `root = "/var/lib/container/buildkit"`；
    - `[worker.containerd] address = "/run/containerd/containerd.sock"`；
    - `namespace = "buildkit"`；
    - 打开了 containerd worker，并设置了较激进的缓存容量与 GC 策略。
3. `deploy/pipeline/*`** 里的 `docker-build` step**
    - 实际命令是：

```bash
buildctl build \
  --frontend=dockerfile.v0 --progress=plain \
  --opt filename=Dockerfile --local context=. --local dockerfile=/workspace/.pipeline \
  --output type=image,name=$(params.docker-image),push=true \
  --export-cache type=inline
```

```plain
- 也会挂同一套 hostPath：`containerd.sock`、`/var/lib/containerd`、`/var/lib/container/buildkit`、`/run/buildkit`。
```

4. `deploy/buildkit-prune.yaml`
    - 用单独的 CronJob 做 `buildctl prune` / `buildctl prune-histories`；
    - 本质也是去清理节点共享的 buildkit cache。
5. `deploy/containerd/certs.d/.../hosts.toml(.example)`
    - 这里是**节点级 registry 鉴权 / mirror / 协议配置**；
    - 语雀文档里应该只写“机制与路径”，不要贴任何明文账号、密码或 Basic Token。

## 踩坑 Harbor 鉴权与网络问题，应该从哪一层排查
### 先认清：不是 Tekton Pod 在自己 `docker login`
这个仓库里的 `docker-build` step 通常**没有显式执行 **`docker login`，Harbor 认证更多依赖：

+ 节点 `containerd` 的 `certs.d/<registry>/hosts.toml`；
+ 或节点级 registry 配置与 Harbor robot 账号；
+ 因为真正对 Harbor 发起 OCI registry 交互的是 **buildkitd / containerd**。

所以“Pod 里看不到凭据”不等于“没有凭据”。

### `pull` 成功、`push` 失败，不一定是网络
这是你下午排查里最典型的情况：

+ **拉基础镜像成功**，说明到 Harbor 的基础网络、DNS、TLS 往往已经是通的；
+ **推目标镜像报 `unauthorized` / **`authentication required`，更常见的是：
    1. 目标项目没有 push 权限；
    2. 节点上只配了旧域名 auth，没有配新域名；
    3. `pull` 所在项目和 `push` 所在项目不是同一套 Harbor scope。

### 如果 `WWW-Authenticate` 里给的是 `http://...`，重点不在 Tekton
下午那条排查里最关键的结论是：

+ 访问 `https://harbor.../v2/...`；
+ 返回 `401` 没问题，Registry 本来就会先 challenge；
+ 但如果 `WWW-Authenticate: Bearer realm="http://harbor.../service/token"` 里是 `http://`，那就说明 **Harbor 自己宣告的 token 地址协议错了**。

这类问题常见根因：

+ Harbor `external_url` 配成了 `http://`；
+ 前置 Ingress / Tengine / Nginx 没把 `X-Forwarded-Proto: https` 传进去；
+ 最终表现就是：**你以为是在 HTTPS 上鉴权，实际 Harbor 让客户端去 HTTP token endpoint 拿 token，导致 push 阶段掉鉴权**。

这时候该改的是 **Harbor / Ingress 配置**，不是 Tekton Controller，也不是 `buildctl` 参数。

### 如果怀疑是 buildkit 侧问题，优先看这两个点
+ `buildctl debug workers`：能不能看到 worker；
+ **Task Pod 是否跑在有 buildkitd 的 pipeline 节点上**。

仓库里还专门留了一个调试模板：`deploy/pipeline/jdk/task-maven3-6-scancode-debug.yaml`，里面会：

+ `curl` 探测 `https://.../v2/` 与 `http://.../v2/`；
+ 执行 `buildctl debug workers`；
+ 临时加 `registry.insecure=true` 做协议层定位。

这个模板适合**短期排障**，不适合当正式配置常驻。

## 两个最容易混淆的点
### `nerdctl build` 和 `buildctl build` 不是一回事
+ `nerdctl build`：更像 Docker 用户熟悉的体验；
+ `buildctl build`：直接打到 buildkitd，链路更短；
+ 当前仓库的生产模板主路径是 `buildctl build`；`nerdctl build` 更多是文档对照项或手工排障时备用。

### `FROM` 拉谁，和最终 `push` 到谁，是两码事
+ `Dockerfile` 里的 `FROM harbor.soulapp-inc.cn/...` 决定**基础镜像从哪拉**；
+ `--output type=image,name=$(params.docker-image),push=true` 决定**结果镜像往哪推**。

所以即使你把目标镜像改成 `harbor-test.soulapp-inc.cn/...`，也不代表基础镜像会自动从 test 拉；除非你连 `Dockerfile` 里的 `FROM` 也一起改了。

