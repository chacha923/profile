下面这套材料的目标不是背 Kubernetes 八股，而是把你包装成“能从平台、控制面、节点面和可观测体系一起定位问题”的运维型候选人。

面试表达时始终围绕三件事：

- 我能解释 Kubernetes 的声明式控制链路。
- 我能按组件边界快速定位故障。
- 我能把故障治理沉淀成监控、告警、SLO、容量和变更体系。

---

# 总体心智模型

Kubernetes 可以理解成一套围绕 API 对象持续对账的分布式控制系统。

![Kubernetes 运维总体心智模型](../k8s-interview-mindset.png)

面试可以这样开场：

> 我理解 Kubernetes 不只是一个能跑容器的平台，而是一套声明式 API 加控制器持续对账的系统。排障时我会先判断问题卡在 API 写入、调度、节点执行、容器运行时、网络、存储还是应用自身，再用事件、日志、指标和变更记录做交叉验证。

---

# 核心链路图

## Pod 创建与排障链路

![Pod 创建与排障链路](../k8s-interview-pod-lifecycle.png)

这张图是最重要的面试主线。只要能沿着它讲清楚，绝大多数 Pod 故障都能归类。

## Service 访问链路

![Service 访问链路](../k8s-interview-service-path.png)

面试里要强调：Service 不是代理进程，它是稳定入口和转发规则；真正的数据面可能是 kube-proxy、iptables、ipvs 或 eBPF。

## 故障定位决策树

![Kubernetes 故障定位决策树](../k8s-interview-troubleshooting-tree.png)

排障时不要一上来重启 Pod。先按状态把问题归层，再决定看哪个组件。

---

# 面试回答框架

## 表达层次

| 层次 | 你要表达什么 | 示例 |
|---|---|---|
| 概念 | 组件边界和责任 | kubelet 负责执行已绑定到本节点的 Pod，不负责调度 |
| 链路 | 一个请求如何流转 | 发布系统提交资源后，先过 apiserver，再由 scheduler 和 kubelet 接力 |
| 排障 | 现象如何归因 | Pending 看调度，ContainerCreating 看 kubelet、CNI、CSI、containerd |
| 治理 | 如何减少重复故障 | 建监控、告警、SLO、容量水位、变更关联和故障复盘 |

## 排障时先问的问题

| 问题 | 目的 |
|---|---|
| 资源对象是否存在 | 区分 API 层失败和后续状态收敛失败 |
| Pod 是否绑定 Node | 区分 scheduler 问题和 kubelet 问题 |
| Event 最后一条关键错误是什么 | 快速定位 Image、CNI、CSI、Probe、Quota 等方向 |
| 影响范围是单 Pod、单节点、单 namespace 还是全局 | 判断故障半径和优先级 |
| 最近是否有发布、配置、证书、网络、节点变更 | 把故障和变更关联起来 |

---

# 控制面

## apiserver

apiserver 是 Kubernetes 的统一入口，负责认证、鉴权、准入、API 校验、资源持久化和 watch 分发。

| 能力 | 面试说法 | 常见故障 |
|---|---|---|
| 认证 Authentication | 判断调用者是谁 | token、证书、ServiceAccount 异常 |
| 鉴权 Authorization | 判断能不能操作资源 | RBAC forbidden |
| 准入 Admission | 修改或拒绝请求 | webhook 超时、策略误拦截 |
| API 校验 | 校验字段和版本 | CRD schema、版本转换失败 |
| 持久化 | 写入 etcd | etcd 慢导致写入慢 |
| Watch | 分发资源变化 | watch 过多导致内存和延迟升高 |

apiserver 慢的常见原因：

| 方向 | 典型现象 | 快速处理 |
|---|---|---|
| 请求压力大 | `kubectl` 卡顿，controller 延迟 | 查 QPS、inflight、慢请求，限制异常客户端 |
| Webhook 慢 | apply 卡住或失败 | 查 webhook service、timeout、failurePolicy |
| etcd 慢 | 创建和更新资源慢 | 查 fsync、leader、db size、网络 RTT |
| 大对象或大 List | apiserver 内存高 | 查大 ConfigMap、Secret、CRD 对象和分页 |
| 客户端限流 | client-side throttling | 调整 client-go QPS/Burst 或减少轮询 |

面试可说：

> 我会先判断请求是否到达并通过 apiserver。如果资源没有创建出来，优先看 RBAC、Admission Webhook、CRD schema 和 audit；如果资源创建了但状态不收敛，再进入 scheduler、controller、kubelet 和 runtime 链路。

## etcd

etcd 是 Kubernetes 的强一致状态存储。kubelet、scheduler、controller 不直接访问 etcd，它们都通过 apiserver 读写 API 对象。

| 关注点 | 为什么重要 | 异常表现 |
|---|---|---|
| leader 稳定性 | leader 抖动会影响写入 | 请求失败、延迟抖动 |
| raft proposal 延迟 | 反映一致性写入质量 | 控制面整体变慢 |
| fsync latency | etcd 对磁盘很敏感 | 写入慢、apiserver 慢 |
| backend db size | 历史版本和碎片膨胀 | list/watch 慢、磁盘告警 |
| network RTT | raft 成员依赖稳定网络 | 选主、心跳异常 |
| snapshot | 灾备恢复能力 | 备份不可用会放大事故 |

compact 和 defrag 的区别：

| 操作 | 作用 | 面试表述 |
|---|---|---|
| compact | 清理历史 revision | 让 etcd 不再保留过旧版本 |
| defrag | 整理后端文件 | 把逻辑释放的空间真正还给文件系统 |

## scheduler

scheduler 负责给未绑定的 Pod 选择节点，核心阶段是 Filter、Score、Bind。

| 阶段 | 做什么 | 常见问题 |
|---|---|---|
| Filter | 过滤不能运行的节点 | 资源不足、污点不容忍、亲和冲突、PVC 限制 |
| Score | 给候选节点打分 | 负载不均、拓扑策略不合理 |
| Bind | 写入 Pod 的 NodeName | apiserver 写入失败、调度器异常 |

Pending 排查重点：

| 方向 | 快速判断 | 快速处理 |
|---|---|---|
| 资源不足 | event 里有 Insufficient CPU/Memory | 扩容、降低 request、迁移低优先级 Pod |
| 污点不匹配 | event 里有 taint not tolerated | 加 toleration 或换节点池 |
| 标签不匹配 | nodeSelector 或 affinity 无匹配 | 修正标签和亲和规则 |
| PVC 问题 | PVC Pending 或拓扑不匹配 | 查 StorageClass、PV、可用区 |
| 节点不可调度 | node unschedulable | uncordon 或换节点池 |
| 配额限制 | namespace quota 不足 | 调整 quota 或清理资源 |

## controller-manager

Controller 的本质是持续对账：观察实际状态，和期望状态比较，执行动作让系统收敛。

| 控制器 | 负责什么 | 常见故障 |
|---|---|---|
| Deployment Controller | 管 ReplicaSet 和滚动更新 | 发布卡住、RS 不变化 |
| ReplicaSet Controller | 维持 Pod 副本数 | 副本不足或异常扩缩 |
| Node Controller | 维护 Node 状态 | Node NotReady 处理延迟 |
| EndpointSlice Controller | 维护 Service 后端 | Service 没有 Endpoint |
| Job Controller | 管批任务完成状态 | Job 不结束、重复执行 |

面试重点：

> Kubernetes 不是执行一次命令就结束，而是 controller 持续 reconcile。Deployment、Job、EndpointSlice、Node、ServiceAccount 等对象背后都有控制器推动状态收敛。

---

# 节点面与运行时

## kubelet

kubelet 是节点上的核心 Agent，负责执行已经绑定到本节点的 Pod。

| 能力 | 说明 | 故障表现 |
|---|---|---|
| Pod 生命周期 | 创建、更新、删除 Pod | ContainerCreating、Terminating |
| CRI 调用 | 通过 CRI 调 containerd | 创建容器失败 |
| Probe 执行 | startup、readiness、liveness | NotReady、重启 |
| Volume 管理 | 调 CSI 或本地挂载 | mount failed |
| Node 状态上报 | 心跳、condition、容量 | Node NotReady |
| Eviction | 资源压力下驱逐 Pod | Evicted、DiskPressure |
| 日志管理 | stdout/stderr 落盘 | 日志占满磁盘 |

Node NotReady 快速处理：

| 检查项 | 快速判断 | 处理方向 |
|---|---|---|
| kubelet 存活 | systemd 状态和日志 | 重启 kubelet、修配置 |
| containerd 状态 | runtime ready 是否正常 | 重启 runtime、查 shim、查镜像目录 |
| 节点资源 | disk、inode、memory、pid | 清理日志镜像、扩容、驱逐低优先级 Pod |
| CNI 状态 | network plugin 是否 ready | 修 CNI Pod、路由、iptables、MTU |
| apiserver 连通 | 节点到 apiserver 是否通 | 查网络、证书、LB |
| 证书 | kubelet client/server cert | 轮转证书或修 bootstrap |

## containerd

containerd 是容器运行时管理层，kubelet 通过 CRI 调用它。

| 概念 | 面试说法 |
|---|---|
| CRI | Kubernetes 与运行时之间的接口 |
| containerd | 管理镜像、容器、sandbox、快照 |
| shim | 托管容器进程生命周期 |
| runc | 真正创建 Linux 容器 |
| cgroups | 做资源限制 |
| namespaces | 做进程、网络、挂载等隔离 |

常见问题：

| 问题 | 表现 | 快速处理 |
|---|---|---|
| 镜像拉取失败 | ImagePullBackOff | 查 registry、secret、DNS、节点出口 |
| sandbox 创建失败 | ContainerCreating | 查 pause 镜像、CNI、runtime 日志 |
| overlayfs 异常 | 容器启动失败 | 查磁盘、inode、snapshotter |
| shim 残留 | 进程泄漏、删除卡住 | 查残留进程，必要时重启 runtime |
| 镜像 GC 失败 | 磁盘高、ImageGCFailed | 清理镜像和日志，调 GC 阈值 |

排障命令只需要记入口，不要在面试里堆命令块。常用入口包括 `kubectl describe pod`、`kubectl logs`、`crictl ps`、`crictl pods`、`crictl inspect`、`journalctl -u kubelet`、`journalctl -u containerd`。

---

# 网络

Kubernetes 网络模型要求 Pod 之间可以直接互通，Service 提供稳定访问入口，Ingress 或 Gateway 承接集群外流量。

| 层级 | 组件 | 常见故障 |
|---|---|---|
| Pod 网络 | CNI、IPAM、路由、隧道 | Pod 跨节点不通、IP 分配失败 |
| Service 数据面 | kube-proxy、iptables、ipvs、eBPF | ClusterIP 不通、规则异常 |
| DNS | CoreDNS、kube-dns Service | 解析慢、解析失败 |
| 访问控制 | NetworkPolicy、安全组 | 部分流量被拦截 |
| 入口流量 | Ingress、Gateway、LB | 外部访问异常 |

Pod 访问 Service 不通的快速路径：

| 检查顺序 | 看什么 | 结论 |
|---|---|---|
| Service | selector 和 port 是否正确 | 配置问题 |
| EndpointSlice | 是否有 Ready 后端 | readiness 或 label 问题 |
| DNS | 服务名能否解析 | CoreDNS 或 search domain 问题 |
| 数据面 | kube-proxy、iptables、ipvs、eBPF | 转发规则问题 |
| CNI | Pod 到 Pod 是否通 | 路由、隧道、MTU、NetworkPolicy |
| 应用 | 容器是否监听端口 | 业务进程或协议问题 |

DNS 异常快速处理：

| 现象 | 可能原因 | 处理方向 |
|---|---|---|
| 服务名解析失败 | CoreDNS Pod 异常 | 查 CoreDNS 日志和 Service |
| 偶发超时 | CoreDNS 负载高或上游慢 | 扩容 CoreDNS、看缓存和上游 |
| 只有某些 Pod 失败 | resolv.conf 或节点网络异常 | 查 Pod DNSPolicy、节点 CNI |
| 外部域名慢 | 上游 DNS 慢 | 优化 forward、缓存、节点 DNS |

---

# 存储

Kubernetes 存储链路是 Pod、PVC、PV、StorageClass、CSI Controller、CSI Node、kubelet mount 的组合。

| 对象 | 作用 | 常见问题 |
|---|---|---|
| PVC | 用户声明存储需求 | Pending、容量或访问模式不匹配 |
| PV | 实际卷资源 | reclaimPolicy、绑定异常 |
| StorageClass | 动态供给策略 | provisioner 错误、拓扑限制 |
| CSI Controller | 创建、attach、detach | 云盘创建失败、挂载冲突 |
| CSI Node | 节点侧 mount | NodePublishVolume 失败 |
| kubelet | 把卷挂到容器 | ContainerCreating 卡住 |

存储排障要点：

| 现象 | 优先看什么 | 快速处理 |
|---|---|---|
| PVC Pending | StorageClass、PV、事件 | 修 SC、扩容存储池、检查拓扑 |
| Pod 卡 ContainerCreating | kubelet event、CSI Node 日志 | 修挂载、权限、云盘状态 |
| 多节点挂载冲突 | RWO/RWX 和调度位置 | 调整访问模式或副本调度 |
| 挂载慢 | CSI、云盘、NAS 延迟 | 查云厂商控制面和节点 IO |
| 文件权限错误 | fsGroup、securityContext | 修权限策略或镜像用户 |
| inode 满 | 空间还够但无法写文件 | 清理小文件、调整日志策略 |

面试重点：

> PVC Bound 只能说明卷已经绑定，不代表 kubelet 已经挂载成功。Pod 卡 ContainerCreating 时必须继续看 kubelet event、CSI node plugin、云盘 attach/mount 状态和节点磁盘情况。

---

# 资源与稳定性

## CPU 与 Memory

| 资源 | 关键概念 | 面试说法 |
|---|---|---|
| CPU request | 调度参考和资源保障 | request 太大导致 Pending，太小导致争抢 |
| CPU limit | CFS quota 限制 | limit 太低可能 CPU throttling，延迟升高 |
| Memory request | 调度参考 | request 影响节点装箱 |
| Memory limit | cgroup OOM 边界 | 超过 limit 会 OOMKilled |
| Eviction | 节点整体压力处理 | Evicted 是 kubelet 因节点压力驱逐，不等同于容器 OOM |

## Disk 与 PID

| 资源 | 常见原因 | 典型表现 |
|---|---|---|
| Disk | 镜像、容器日志、emptyDir、overlayfs | DiskPressure、ImageGCFailed、Pod Evicted |
| inode | 大量小文件、日志碎片 | 有空间但无法创建文件 |
| PID | 进程泄漏、fork 过多 | PIDPressure、容器创建失败 |

快速治理：

| 方向 | 做法 |
|---|---|
| 镜像治理 | 设置 image GC 阈值，清理废弃镜像 |
| 日志治理 | 限制容器日志大小，接入日志采集和轮转 |
| emptyDir 治理 | 设置 sizeLimit，监控临时目录占用 |
| 节点水位 | 对磁盘、inode、PID、内存设置预警 |
| 优先级 | 用 PriorityClass 和 PDB 降低故障扩散 |

---

# 运维常见故障速查

这一章是面试里最有用的部分。回答时先说“现象、判断边界、快速处理、长期治理”。

| 故障 | 常见现象 | 快速定位 | 快速解决 | 长期治理 |
|---|---|---|---|---|
| Pod Pending | 一直未调度 | 看 event 是否 FailedScheduling | 扩容、改 request、修 taint/affinity/PVC | 容量水位、资源画像、调度约束规范 |
| ImagePullBackOff | 镜像拉取失败 | 看 image、secret、registry、节点出口 | 修 secret、镜像地址、网络、重试 | 镜像预热、仓库可用性监控 |
| ContainerCreating | 卡创建容器 | 看 kubelet、CNI、CSI、containerd | 修网络插件、挂载、runtime、镜像 | 节点健康检查、CNI/CSI 告警 |
| CrashLoopBackOff | 容器反复重启 | 看应用日志、退出码、Probe、配置 | 回滚配置、修 Probe、扩资源 | 发布健康检查、灰度、配置校验 |
| Running NotReady | Pod 运行但不接流量 | 看 readiness、端口、依赖 | 修应用健康接口或依赖 | readiness 标准化、依赖探活 |
| Service 无后端 | EndpointSlice 为空 | 看 selector、label、readiness | 修 label 或 readiness | 发布前校验和服务拓扑监控 |
| Service 不通 | ClusterIP 访问失败 | 看 DNS、Endpoint、kube-proxy、CNI | 修 CoreDNS、规则、网络策略 | 服务链路探测、DNS SLO |
| CoreDNS 异常 | 解析慢或失败 | 看 CoreDNS QPS、错误、上游延迟 | 扩容、修 upstream、清异常配置 | DNS 缓存、容量和错误率告警 |
| Node NotReady | 节点不可用 | 看 kubelet、runtime、资源、网络 | 重启组件、隔离节点、迁移 Pod | 节点自愈、巡检、证书和资源预警 |
| DiskPressure | 节点磁盘压力 | 看镜像、日志、emptyDir、inode | 清理日志镜像、驱逐低优先级 Pod | 日志轮转、磁盘水位、emptyDir 限额 |
| OOMKilled | 容器被杀 | 看 memory limit、峰值、退出码 | 调高 limit、修内存泄漏、降流 | 内存画像、压测、合理 request/limit |
| CPU throttling | 延迟高但 CPU 不高 | 看 throttling 指标和 limit | 调高 limit 或去掉不合理 limit | request/limit 基线、性能压测 |
| PVC Pending | 存储未绑定 | 看 SC、PV、拓扑、quota | 修 SC、扩容、调度到正确可用区 | 存储容量监控、SC 标准化 |
| Volume mount failed | 挂载失败 | 看 kubelet event 和 CSI 日志 | 修权限、云盘状态、CSI Node | CSI 可用性和挂载耗时监控 |
| 发布卡住 | Deployment/Rollout 不前进 | 看 RS、Pod、readiness、quota | 回滚、暂停、修健康检查 | 灰度策略、自动回滚、发布 SLO |
| apiserver 慢 | kubectl 和控制器慢 | 看 request latency、webhook、etcd | 隔离慢 webhook、降流、修 etcd | API SLO、webhook 容量和超时治理 |
| etcd 延迟 | 控制面整体慢 | 看 fsync、leader、db size | 修磁盘、compact、defrag、扩容 | 定期备份、容量和延迟告警 |

故障回答模板：

> 这个问题我会先判断影响面，再看资源对象和事件，把问题归到 API、调度、节点、网络、存储或应用层。快速止血可以扩容、回滚、隔离节点或修配置；长期要沉淀监控告警、容量水位、发布前校验和故障复盘。

---

# 可观测建设

可观测不是“装 Prometheus 就完了”，而是围绕指标、日志、事件、链路、变更和 SLO 建一套能定位问题、度量稳定性、驱动治理的体系。

![Kubernetes 可观测建设闭环](../k8s-interview-observability.png)

## 建设目标

| 目标 | 说明 |
|---|---|
| 快速发现 | 故障发生时先由监控发现，而不是用户反馈 |
| 快速定位 | 能从服务、工作负载、Pod、节点、组件逐层下钻 |
| 影响面判断 | 能区分单 Pod、单节点、单 namespace、单集群、全局问题 |
| 变更关联 | 能把发布、配置、扩缩容和故障时间线关联 |
| 治理闭环 | 故障后沉淀告警、容量、自动化和流程改进 |

## 指标体系

| 层级 | 核心指标 | 用途 |
|---|---|---|
| 业务服务 | QPS、错误率、延迟、可用性 | 判断用户影响 |
| Ingress / Gateway | 请求量、状态码、上游延迟 | 判断入口和路由问题 |
| Workload | 副本数、Ready 数、重启数、发布状态 | 判断发布和副本健康 |
| Pod / Container | CPU、内存、重启、OOM、throttling | 判断资源和应用问题 |
| Node | CPU、内存、磁盘、inode、PID、Network | 判断节点压力 |
| kubelet | PLEG、runtime ready、pod start latency | 判断节点执行链路 |
| containerd | 镜像拉取、容器创建、GC、runtime 错误 | 判断运行时问题 |
| CNI / DNS | IP 分配、丢包、CoreDNS QPS/错误/延迟 | 判断网络问题 |
| CSI / Storage | mount latency、attach error、容量 | 判断存储问题 |
| apiserver | request latency、inflight、错误码、watch | 判断 API 层压力 |
| etcd | fsync、proposal、leader、db size | 判断一致性存储状态 |

面试里可以说“四个黄金信号”：延迟、流量、错误、饱和度。Kubernetes 运维里还要加上事件、状态收敛和变更。

## 日志体系

| 日志 | 价值 |
|---|---|
| 应用日志 | 判断业务错误和依赖异常 |
| kubelet 日志 | 判断 Pod 创建、Probe、Volume、CNI、Eviction |
| containerd 日志 | 判断镜像、sandbox、runtime、shim |
| CNI 日志 | 判断 IP 分配、路由、网络策略 |
| CSI 日志 | 判断 attach、mount、权限和云盘状态 |
| apiserver audit | 判断谁在什么时候做了什么变更 |
| controller 日志 | 判断 reconcile 是否卡住 |

日志治理重点不是收集越多越好，而是字段标准化、保留周期、检索效率、采样和脱敏。

## 事件体系

Kubernetes Event 是排障入口，尤其适合 Pod Pending、ImagePullBackOff、ContainerCreating、FailedMount、Unhealthy、Killing、Evicted 这类问题。

| 事件类型 | 代表问题 |
|---|---|
| FailedScheduling | 调度失败 |
| FailedMount | 存储挂载失败 |
| FailedCreatePodSandBox | CNI 或 sandbox 失败 |
| BackOff | 镜像或容器重启退避 |
| Unhealthy | Probe 失败 |
| Evicted | 节点资源压力 |
| NodeNotReady | 节点心跳异常 |

建议把 Warning Event 接入告警和故障时间线，但要做聚合和抑制，避免事件风暴。

## 告警设计

| 原则 | 说明 |
|---|---|
| 症状优先 | 优先告警用户可感知问题，例如错误率、延迟、不可用 |
| 原因辅助 | 组件指标用于定位，不要所有底层抖动都直接叫醒人 |
| 分级告警 | P0 看全局不可用，P1 看核心业务，P2 看容量和风险 |
| 去重抑制 | Node NotReady 时抑制该节点上大量 Pod 告警 |
| 带上下文 | 告警要带 namespace、workload、node、最近变更、排障入口 |
| 可执行 | 每条告警都应该能对应处理动作或 Runbook |

## SLO 与容量治理

| 方向 | 建设内容 |
|---|---|
| 服务 SLO | 可用性、延迟、错误率，按核心链路分级 |
| 集群 SLO | apiserver 延迟、Pod 启动耗时、调度耗时、DNS 成功率 |
| 节点水位 | CPU、内存、磁盘、inode、PID、Pod 数 |
| 容量预测 | 按 namespace、workload、节点池做趋势和突增分析 |
| 发布质量 | 发布成功率、回滚率、平均恢复时间 |
| Runbook | 常见告警要有处理步骤、止血动作和升级路径 |

可观测面试表述：

> 我会把可观测分成指标、日志、事件、链路和变更五类数据。指标用于发现和度量，日志用于解释细节，事件用于定位 K8s 状态变化，链路用于判断请求经过哪里，变更用于解释为什么突然异常。告警上我倾向症状优先、原因辅助，并且要关联 Runbook 和最近变更。

---

# 面试追问清单

## apiserver 和 etcd

- `kubectl apply` 一个资源后，Kubernetes 内部发生什么？
- apiserver 慢可能由哪些原因导致？
- Webhook 故障会怎样影响资源创建？
- etcd 存什么，业务数据会不会进 etcd？
- compact 和 defrag 有什么区别？
- 为什么 controller 不直接查 etcd？

## scheduler

- Pod 一直 Pending 怎么排查？
- request 和 limit 对调度分别有什么影响？
- taint/toleration 和 nodeSelector 区别是什么？
- affinity、anti-affinity、topologySpreadConstraints 怎么用？
- PVC 为什么会影响调度？

## kubelet 和 containerd

- kubelet 和 containerd 分别负责什么？
- Pod 卡 ContainerCreating 怎么排查？
- ImagePullBackOff 怎么排查？
- `crictl` 和 `docker` 命令有什么区别？
- kubelet 怎么判断 Pod Ready？
- OOMKilled 和 Evicted 区别是什么？

## 网络

- Service 是怎么转发到 Pod 的？
- kube-proxy iptables 和 ipvs 有什么区别？
- eBPF 数据面解决了什么问题？
- Pod 跨节点通信怎么实现？
- CoreDNS 异常怎么排查？
- NetworkPolicy 是谁实现的？
- Ingress、Gateway、Service 的关系是什么？

## 存储

- PVC Pending 怎么排查？
- PVC Bound 了，Pod 为什么还可能挂载失败？
- RWO 和 RWX 有什么区别？
- CSI Controller 和 CSI Node 分别做什么？
- Pod 卡 Terminating 会不会和存储有关？

## 可观测

- Kubernetes 集群监控应该分哪些层？
- Prometheus、kube-state-metrics、cAdvisor 分别提供什么？
- 你会给 Pod 启动失败设计哪些告警？
- 告警风暴怎么治理？
- 如何把发布变更和故障关联起来？
- SLO 在平台运维里怎么落地？

---

# 学习路径

## Pod 生命周期

优先掌握 Pod 创建、Pending、ImagePullBackOff、ContainerCreating、CrashLoopBackOff、Running NotReady、Evicted、Terminating。

目标：能根据 Pod 状态直接判断下一步该看哪个组件。

## 节点执行链路

重点掌握 kubelet、containerd、CRI、CNI、CSI、cgroup、probe、eviction。

目标：能解释 Pod 被调度到节点后，kubelet 到底做了什么。

## 控制面链路

重点掌握 apiserver、etcd、scheduler、controller-manager、informer、watch、admission webhook、CRD。

目标：能解释 Kubernetes 为什么是声明式控制系统。

## 生产稳定性

重点掌握 apiserver 延迟、etcd 延迟、controller 延迟、Node NotReady、CoreDNS 异常、CNI 故障、CSI 故障、containerd 异常、磁盘、inode、PID、CPU throttling。

目标：能把问题归类成 API 层、控制器、调度、节点、网络、存储、应用或平台变更问题。

## 可观测和治理

重点掌握指标、日志、事件、链路、变更、告警、SLO、容量和 Runbook。

目标：不只会处理一次故障，还能说明怎么把故障变成可监控、可预防、可复盘的稳定性能力。

---

# 最小面试闭环

你至少要能流畅讲清楚这些链路：

| 链路 | 必须说清楚 |
|---|---|
| Pod 创建链路 | apiserver、etcd、scheduler、kubelet、containerd、CNI、CSI、Probe |
| Service 访问链路 | DNS、ClusterIP、kube-proxy/eBPF、EndpointSlice、目标 Pod |
| 存储挂载链路 | PVC、PV、StorageClass、CSI Controller、CSI Node、kubelet mount |
| 节点异常链路 | kubelet、containerd、CNI、资源压力、apiserver 连通性 |
| 发布异常链路 | 平台发布、workload controller、调度、节点执行、健康检查、Endpoint |
| 可观测闭环 | 指标发现、日志解释、事件定位、链路确认、变更归因、Runbook 处理 |

最后把自己定位成：

> 我不是只会写 YAML 或看 Pod 状态，而是能按 Kubernetes 的控制面、节点面、运行时、网络、存储、资源和可观测链路定位问题。从平台发布失败、Pod Pending、ContainerCreating、CrashLoop、Service 不通、Node NotReady，到 etcd 和 apiserver 延迟，我都能先分层，再定位具体组件，并把处理经验沉淀成监控、告警和 Runbook。
