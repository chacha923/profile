# 面试定位卡
+ **技术点**：从 0 到 1 部署一个支撑 1000 节点的 Kubernetes 集群。
+ **所属领域**：Kubernetes / SRE / 云原生平台 / AI Infra 基础设施。
+ **面试价值**：证明你不是只会使用 Kubernetes，而是理解生产级集群从控制面、节点面、网络、存储、可观测、容量和运维治理如何组合起来。
+ **常见考法**：组件清单、控制面高可用、etcd 规划、CNI 选型、DNS 稳定性、apiserver 压力、节点生命周期、监控日志、升级和故障恢复。
+ **适合挂钩项目**：SAE 多集群发布平台、SAI 训推平台、Bigeyes / OTel 可观测与告警、数据平台 Spark / 调度任务托管。
+ **不适合夸大的地方**：如果没有真实从 0 到 1 落地过 1000 节点集群，不要说“我完整建设过”。更稳妥的说法是：我理解这类集群的建设拆解、关键瓶颈、排障路径，并在多集群发布、训练推理托管、可观测治理中接触过相邻能力。

# 三十秒回答
> 从 0 到 1 部署一个能支撑 1000 节点的 Kubernetes 集群，不能只理解成 kubeadm 拉起控制面再加 worker。生产级建设至少要拆成四层：第一是控制面高可用，包括多副本 kube-apiserver、controller-manager、scheduler 和独立高可用 etcd；第二是节点面，包括 kubelet、containerd、CNI、kube-proxy 或 eBPF datapath；第三是基础能力，包括 CoreDNS、NodeLocal DNSCache、CSI、Ingress/Gateway、RBAC、Admission、证书和审计；第四是运维治理，包括监控、日志、事件、etcd 备份、节点生命周期、升级灰度、容量治理和弹性伸缩。1000 节点真正的难点不是组件能不能安装，而是 apiserver QPS、etcd 写延迟、watch 扩散、DNS 压力、网络规模、镜像分发和可观测数据量。
>

# 为什么需要它
+ **没有系统化规划的问题**：小集群可以靠默认配置和人工运维撑住，但 1000 节点下，控制面、DNS、网络、镜像、监控、日志都会出现规模化放大。
+ **它的解决方式**：用分层架构把控制面、节点面、网络、存储、安全、可观测、运维治理拆开设计，每一层都能独立扩容、监控、压测和回滚。
+ **它引入的新问题**：集群越大，故障域越大；控制面压力越集中；升级周期更长；多租户治理、配额、审计和准入规则更复杂。
+ **必须关注的场景**：大规模发布、节点批量扩容、AI 训练任务集中提交、Pod 突发创建、DNS 高 QPS、镜像拉取风暴、控制器异常重试、监控指标爆量。

# 核心概念
+ **控制面**：kube-apiserver、controller-manager、scheduler、etcd 等管理组件。面试展开点是高可用、限流、watch、etcd 延迟、leader election。
+ **节点面**：kubelet、containerd、CNI、kube-proxy/eBPF 等节点组件。面试展开点是节点注册、Pod 生命周期、镜像拉取、资源预留、驱逐。
+ **external etcd**：独立部署的 etcd 集群。面试展开点是磁盘延迟、备份恢复、leader、DB size、defrag。
+ **kube-apiserver**：Kubernetes API 入口，也是共享状态访问前端。面试展开点是 QPS、APF、audit、webhook、watch cache、inflight。
+ **controller-manager**：多个控制循环的集合。面试展开点是 reconcile、并发、对象规模、异常重试。
+ **scheduler**：为未绑定节点的 Pod 做调度决策。面试展开点是调度插件、亲和性、拓扑、GPU、批任务调度。
+ **CNI**：Pod 网络插件。面试展开点是 Overlay / Underlay、NetworkPolicy、eBPF、VPC CNI。
+ **kube-proxy / eBPF datapath**：Service 转发数据面。面试展开点是 iptables、ipvs、eBPF、conntrack、EndpointSlice。
+ **CoreDNS**：集群 DNS 服务。面试展开点是 QPS、缓存、上游 DNS、ndots、DNS autoscaler。
+ **NodeLocal DNSCache**：节点本地 DNS 缓存。面试展开点是降低 CoreDNS 压力，减少 DNAT 和 conntrack 影响。
+ **CSI**：容器存储接口。面试展开点是 PV/PVC、动态供给、快照、扩容、attach/detach。
+ **Admission**：准入控制链路。面试展开点是安全、配额、镜像治理、webhook 延迟和稳定性。
+ **可观测**：指标、日志、事件、Trace、告警。面试展开点是规模化采集、指标基数、日志爆量、事件聚合。
+ **节点生命周期**：节点初始化、纳管、巡检、下线、重装、升级。面试展开点是 1000 节点不能靠人工维护。

# 原理模型
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1779170644854-3328929c-baff-41fd-9861-a17c486bb756.png" width="900" title="" crop="0,0,1,1" id="uc5c5a5de" class="ne-image">

## 底层 / 硬件 / 基础设施层
这层不是 Kubernetes 自身，但决定集群上限：

+ 机型规格：CPU、内存、磁盘、网卡、GPU、ENI 数量。
+ 网络：VPC、子网、路由表、安全组、LB、跨可用区链路。
+ 磁盘：etcd 对低延迟磁盘敏感，节点本地盘影响 image、日志和 emptyDir。
+ 镜像仓库：大规模扩容时，镜像仓库吞吐和缓存会直接影响 Pod 启动。
+ 时间同步：NTP / chrony 异常会影响证书、日志、分布式组件判断。

面试不要只说“准备机器”。更准确的表达是：

> 大规模 K8s 集群建设先要规划底层故障域、网络域、镜像分发和存储性能，否则 Kubernetes 组件部署成功也不代表生产可用。
>

## 操作系统 / 运行时层
每个节点至少要统一：

+ OS 版本和内核参数；
+ containerd 版本；
+ systemd cgroup driver；
+ kubelet 配置；
+ CNI 配置；
+ 日志目录、镜像目录和磁盘水位；
+ sysctl、ulimit、conntrack、ipvs/eBPF 相关参数；
+ GPU 节点还要统一驱动、container toolkit、device plugin。

这一层的核心是“节点标准化”。1000 节点下，节点差异会放大成不可控的排障成本。

## 容器 / Kubernetes 层
Kubernetes 层核心分成：

+ 控制面：apiserver、controller-manager、scheduler、etcd；
+ 节点面：kubelet、containerd、CNI、kube-proxy/eBPF；
+ 基础服务：CoreDNS、NodeLocal DNSCache、CSI、Ingress/Gateway；
+ 安全治理：RBAC、Admission、Pod Security、ResourceQuota、LimitRange；
+ 运维治理：监控、日志、事件、告警、备份、升级、节点生命周期。

1000 节点的关键判断：

> 组件清单只是第一步，真正要回答的是每个组件在规模化下的瓶颈、指标、故障表现和治理手段。
>

## 应用 / 业务层
业务看到的不是 Kubernetes 组件，而是：

+ 发布是否稳定；
+ Pod 是否能快速启动；
+ 服务发现是否稳定；
+ 入口流量是否可控；
+ 训练任务是否能调度到合适资源；
+ 日志、指标、事件是否能定位问题；
+ 集群升级是否影响业务。

所以大规模集群建设最后要回到业务 SLA，而不是停留在“组件安装成功”。

# 关键机制
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1779170661823-dcbe2024-1c06-465b-924f-e33e5039a174.png" width="900" title="" crop="0,0,1,1" id="u6d65969c" class="ne-image">

## 控制面高可用
解决的问题：

单个控制面节点故障会导致 API 不可用，进而影响发布、扩缩容、调度和运维操作。

工作方式：

+ kube-apiserver 多副本部署，前面放 LB / VIP；
+ controller-manager 和 scheduler 多副本部署，通过 leader election 保证同一时间一个主实例工作；
+ etcd 独立部署 3 或 5 节点，保证多数派可用；
+ 控制面节点和 etcd 节点需要资源隔离，不建议和业务 Pod 混跑。

代价：

+ apiserver 多副本会增加对 etcd 的连接和 watch 压力；
+ etcd 多副本对网络 RTT 和磁盘延迟敏感；
+ HA 拓扑增加证书、备份、升级和故障切换复杂度。

面试追问：

> apiserver 扩容是不是就能解决控制面瓶颈？
>

回答要点：

> 不能。apiserver 是无状态入口，扩容能缓解入口并发，但 etcd、webhook、audit、watch fan-out 才可能是后端瓶颈。扩容 apiserver 前要先看请求分布、inflight、APF、webhook latency 和 etcd 延迟。
>

## etcd 独立部署与备份恢复
解决的问题：

etcd 是 Kubernetes 的状态存储，控制面所有对象最终都落到 etcd。如果 etcd 慢或不可用，apiserver 和 controller 都会受影响。

工作方式：

+ 使用 external etcd，独立节点部署；
+ 使用低延迟 SSD / NVMe；
+ 定时 snapshot；
+ 定期做恢复演练；
+ 监控 leader、fsync、DB size、proposal pending、peer RTT。

代价：

+ 独立 etcd 增加机器和运维成本；
+ 跨可用区部署要权衡容灾和 RTT；
+ 备份不是完成脚本就结束，还要验证恢复可用性。

面试追问：

> etcd 为什么不建议跨地域部署？
>

回答要点：

> etcd 依赖多数派和低延迟复制，跨地域 RTT 高会放大写入延迟和选主风险。跨可用区可以做，但也要压测 RTT 和 fsync。跨地域多活通常不靠一个 etcd 集群硬撑，而是多集群和上层流量治理。
>

## API Priority and Fairness 与客户端限流
解决的问题：

平台、控制器、CI/CD、operator、kubectl 都会访问 apiserver。大规模场景下，低优先级请求或异常重试可能拖垮关键请求。

工作方式：

+ 开启并配置 APF；
+ 区分系统组件、平台控制器、普通用户、批量任务；
+ 对自研控制器配置 client-side QPS / burst；
+ 避免频繁 LIST 全量对象；
+ 优先使用 informer cache 和 watch。

代价：

+ APF 配错可能误伤关键链路；
+ 客户端限流过严会导致控制器收敛变慢；
+ informer cache 会引入内存消耗和一致性窗口。

面试追问：

> 如果自研平台频繁查 Pod 状态，会有什么问题？
>

回答要点：

> 如果每次都 LIST apiserver，会增加 apiserver 和 etcd 压力。更好的方式是 informer/watch 缓存状态，平台查询走本地缓存或状态同步表，只在必要时读 apiserver。
>

## NodeLocal DNSCache
解决的问题：

Pod DNS 查询高频发生，所有请求都打到 CoreDNS Service 会带来 CoreDNS、kube-proxy、conntrack 和跨节点网络压力。

工作方式：

+ 每个节点部署 node-local-dns DaemonSet；
+ Pod DNS 请求先访问本节点 DNS cache；
+ cache hit 本地返回；
+ cache miss 再访问 CoreDNS 或上游 DNS。

代价：

+ 每个节点多一个 DaemonSet；
+ 节点本地 DNS 异常会影响该节点 Pod；
+ 需要配合监控和升级策略。

面试追问：

> 为什么不直接把 CoreDNS 做成 DaemonSet？
>

回答要点：

> NodeLocal DNSCache 的定位是节点本地缓存，CoreDNS 仍然承担集群 DNS 解析逻辑。直接改成 CoreDNS DaemonSet不是标准答案，关键要看服务发现逻辑、缓存、一致性、升级和运维复杂度。
>

## CNI 与 Service 数据面
解决的问题：

Pod 网络、Service 访问、网络策略和跨节点通信都依赖网络组件。1000 节点下，网络规模和规则数量会放大。

工作方式：

+ CNI 负责 Pod IP、路由、网络策略；
+ kube-proxy 用 iptables/ipvs 实现 Service 转发；
+ eBPF datapath 可以替代部分 kube-proxy 路径；
+ EndpointSlice 降低大规模 Endpoints 对象压力。

代价：

+ CNI 选型影响排障方法；
+ eBPF 能力强，但对内核、工具链和团队能力要求更高；
+ NetworkPolicy 规则复杂后也会带来性能和排障成本。

面试追问：

> 1000 节点一定要上 eBPF 吗？
>

回答要点：

> 不一定。eBPF 有优势，但不是银弹。要看 Service 数量、Endpoint 规模、网络策略复杂度、内核版本、团队排障能力和云厂商 CNI 支持。更稳妥的说法是：大规模集群需要评估 eBPF，但不能只因为节点多就盲目切换。
>

## 镜像分发与节点预热
解决的问题：

节点扩容或大规模发布时，很多节点同时拉镜像，可能先打爆 Harbor、对象存储、NAT 或出口带宽。

工作方式：

+ 私有镜像仓库；
+ registry mirror；
+ 节点池预热基础镜像；
+ P2P 镜像分发；
+ 构建缓存和基础镜像治理；
+ 控制 image pull 并发。

代价：

+ 缓存一致性和镜像清理要治理；
+ P2P 分发需要额外组件；
+ 镜像预热会占用节点磁盘。

面试追问：

> 为什么 Pod 启动慢不一定是 scheduler 慢？
>

回答要点：

> Pod Pending 可能是调度失败，但也可能是 image pull、CNI、CSI、admission、quota 等链路慢。要先看 Pod condition 和 events，不能一看到 Pending 就归因 scheduler。
>

# 横向对比
+ **小集群 vs 1000 节点集群**
    - 区别：小集群关注组件可用；大集群关注规模化、故障域和运维治理。
    - 什么时候用：解释为什么不能只按默认配置部署。
    - 面试注意点：强调瓶颈会从“能不能跑”变成“能不能稳定治理”。
+ **stacked etcd vs external etcd**
    - 区别：stacked 把 etcd 和控制面放一起；external etcd 独立部署。
    - 什么时候用：生产大规模集群优先 external etcd。
    - 面试注意点：不要绝对说 stacked 不能用，小集群和测试环境可以用。
+ **iptables vs ipvs vs eBPF**
    - 区别：都能实现 Service 转发，但实现机制和规模化能力不同。
    - 什么时候用：Service/Endpoint 规模大时重点评估。
    - 面试注意点：eBPF 不是必选项，要看团队和环境。
+ **CoreDNS 扩容 vs NodeLocal DNSCache**
    - 区别：CoreDNS 扩容提升服务端能力；NodeLocal 缓存减少请求打到服务端。
    - 什么时候用：DNS QPS 高、conntrack 压力明显时。
    - 面试注意点：两者可以组合，不是二选一。
+ **HPA vs VPA vs Cluster Autoscaler**
    - 区别：HPA 调 Pod 副本，VPA 调 request，CA 调节点容量。
    - 什么时候用：建设弹性容量体系。
    - 面试注意点：不要把 HPA 说成能解决节点资源不足。
+ **单大集群 vs 多集群**
    - 区别：单大集群资源池大但故障域也大；多集群隔离好但治理复杂。
    - 什么时候用：多地域、多业务、多资源类型场景。
    - 面试注意点：1000 节点能做，不代表一定应该做成一个集群。
+ **Ingress vs Gateway API vs Service Mesh**
    - 区别：Ingress 偏入口；Gateway API 更标准化；Service Mesh 管服务间治理。
    - 什么时候用：入口流量、灰度、东西向治理。
    - 面试注意点：不要把 Gateway 和 Service Mesh 混成一类。
+ **理论上限 vs 生产上限**
    - 区别：官方支持上限不等于业务生产可承受上限。
    - 什么时候用：容量评估和面试边界。
    - 面试注意点：要结合对象数量、QPS、DNS、监控、运维能力压测。

# 典型业务场景
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1779170694395-8af6b8ac-dd77-44b2-a766-ede5327aa4e5.png" width="900" title="" crop="0,0,1,1" id="u5e87632c" class="ne-image">

+ **大规模发布**
    - 为什么相关：一次发布会创建/更新大量 Deployment、ReplicaSet、Pod、EndpointSlice。
    - 可能现象：发布卡住、Pod Pending、apiserver 延迟升高。
    - 排查方式：看 rollout events、apiserver latency、scheduler pending、EndpointSlice 更新。
    - 优化方向：发布限流、分批灰度、控制器并发治理、平台状态缓存。
+ **AI 训练任务集中提交**
    - 为什么相关：TFJob / Job 会产生多角色 Pod、PVC、GPU 调度和日志事件。
    - 可能现象：GPU 资源不足、Pod 长期 Pending、PVC 绑定慢。
    - 排查方式：describe pod、scheduler events、CSI logs、GPU node metrics。
    - 优化方向：节点池隔离、Quota、队列、Gang Scheduling、资源画像。
+ **推理服务扩缩容**
    - 为什么相关：推理服务对启动耗时和 P99 敏感。
    - 可能现象：镜像拉取慢、探针失败、流量切换抖动。
    - 排查方式：看 image pull、readiness、Ingress/Gateway、HPA events。
    - 优化方向：镜像预热、分批扩容、就绪探针、灰度流量。
+ **DNS 高 QPS**
    - 为什么相关：服务发现每个请求链路都可能触发 DNS。
    - 可能现象：请求偶发超时、CoreDNS CPU 高、conntrack 异常。
    - 排查方式：CoreDNS metrics、NodeLocal DNSCache、conntrack、应用 ndots。
    - 优化方向：NodeLocal DNSCache、CoreDNS 扩容、缓存、应用连接池。
+ **节点批量扩容**
    - 为什么相关：新节点同时注册、拉镜像、启动 DaemonSet。
    - 可能现象：节点 Ready 慢、镜像仓库压力高、DaemonSet 堆积。
    - 排查方式：node condition、kubelet logs、containerd logs、registry metrics。
    - 优化方向：节点预热、镜像缓存、分批扩容、节点初始化标准化。
+ **监控指标爆量**
    - 为什么相关：节点和 Pod 数上来后，指标量非线性增加。
    - 可能现象：Prometheus OOM、remote write 延迟、查询慢。
    - 排查方式：Prometheus targets、series cardinality、scrape duration。
    - 优化方向：分片、remote write、降采样、控制 label cardinality。
+ **多租户混跑**
    - 为什么相关：不同业务、平台、AI 任务共享集群。
    - 可能现象：某类任务影响其他业务，资源争抢。
    - 排查方式：namespace quota、limitrange、node pool waterline。
    - 优化方向：节点池隔离、Quota、PriorityClass、准入控制。
+ **控制器异常重试**
    - 为什么相关：自研 operator 或平台控制器 bug 会高频请求 apiserver。
    - 可能现象：apiserver QPS 异常、etcd 延迟升高。
    - 排查方式：apiserver request by user-agent、audit、controller logs。
    - 优化方向：client QPS 限制、指数退避、informer cache、异常熔断。

# 排障路径
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1779170712829-d24127c2-e1af-44d4-ae15-51f5d9836373.png" width="900" title="" crop="0,0,1,1" id="ue26226be" class="ne-image">

+ **症状**：Pod Pending、发布卡住、DNS 慢、apiserver 慢、节点 NotReady、监控采集延迟、镜像拉取慢。
+ **初始假设**：控制面压力、etcd 延迟、scheduler 慢、DNS 问题、CNI 问题、CSI 问题、镜像仓库问题、节点资源不足。
+ **验证命令**：先看 Pod events / Node condition，再看控制面指标、etcd 指标、CoreDNS 指标、CNI / kubelet / containerd 日志。
+ **关键指标**：apiserver request latency、inflight、APF rejected、etcd fsync、scheduler pending、CoreDNS latency、conntrack、image pull duration。
+ **可能结论**：不是所有问题都归因 scheduler；Pending 只是表象，背后可能是资源、镜像、网络、存储、准入或控制面慢。
+ **优化动作**：分批发布、限流、扩容 CoreDNS、启用 NodeLocal DNSCache、优化镜像缓存、治理 webhook、拆分 Prometheus、节点池隔离。
+ **验证结果**：用压测、灰度发布、指标长尾、错误率和业务延迟验证优化是否有效。

## Pod Pending 排查
```bash
kubectl describe pod <pod-name> -n <namespace>
```

这条命令用于验证什么：

> 查看 Pod 的调度事件、镜像拉取事件、PVC 绑定事件、CNI 创建事件和准入失败信息。
>

重点看什么：

+ `Events`；
+ `FailedScheduling`；
+ `FailedMount`；
+ `ImagePullBackOff`；
+ `CreateContainerConfigError`；
+ `PodScheduled` condition。

异常说明什么：

+ `FailedScheduling`：优先看资源、taint/toleration、nodeSelector、affinity、quota；
+ `FailedMount`：看 CSI 和 PV/PVC；
+ `ImagePullBackOff`：看镜像仓库、凭证、网络和节点 runtime；
+ 没有事件但长时间 Pending：看 scheduler、apiserver、准入链路。

## apiserver 变慢排查
```bash
kubectl get --raw /metrics | grep apiserver_request_duration_seconds
```

这条命令用于验证什么：

> 查看 apiserver 请求延迟，判断是不是某类 resource / verb 延迟异常。
>

重点看什么：

+ 请求类型：LIST、WATCH、PATCH、CREATE；
+ 资源类型：pods、events、endpointslices、configmaps、secrets；
+ 长尾分位；
+ 是否有 429 或 APF rejected。

异常说明什么：

+ LIST 延迟高：可能有低质量客户端全量扫对象；
+ CREATE/PATCH 延迟高：可能 admission webhook 或 etcd 写入慢；
+ WATCH 异常：可能 watch client 多或对象变化频繁。

## etcd 延迟排查
```bash
etcdctl endpoint status --write-out=table
```

这条命令用于验证什么：

> 查看 etcd 成员状态、leader、DB size、raft index 等基本信息。
>

重点看什么：

+ leader 是否稳定；
+ DB size 是否过大；
+ raft index 是否正常推进；
+ endpoint 是否有异常成员。

异常说明什么：

+ leader 频繁变化：网络、磁盘或节点压力可能异常；
+ DB size 过大：需要检查对象量、事件量、compaction/defrag；
+ endpoint 慢：可能是磁盘 fsync 或网络问题。

## DNS 慢排查
```bash
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
```

这条命令用于验证什么：

> 查看 CoreDNS 副本是否正常分布，是否有重启、节点集中或 NotReady。
>

重点看什么：

+ CoreDNS 副本数；
+ Pod restart；
+ 节点分布；
+ CoreDNS CPU / memory；
+ 是否部署 NodeLocal DNSCache。

异常说明什么：

+ CoreDNS CPU 高：可能 DNS QPS 过高或 upstream 慢；
+ 单节点 DNS 异常：可能 NodeLocal DNSCache 或节点网络问题；
+ 全局 DNS 慢：可能 CoreDNS、upstream、kube-proxy/conntrack 问题。

## 节点 NotReady 排查
```bash
kubectl describe node <node-name>
```

这条命令用于验证什么：

> 查看节点 condition、资源压力、kubelet 上报和 taint 情况。
>

重点看什么：

+ `Ready`；
+ `MemoryPressure`；
+ `DiskPressure`；
+ `PIDPressure`；
+ `NetworkUnavailable`；
+ 最近 events。

异常说明什么：

+ DiskPressure：镜像、日志或 emptyDir 可能占满；
+ MemoryPressure：系统预留不足或 Pod 内存压力；
+ NetworkUnavailable：CNI 或节点网络异常；
+ Ready Unknown：kubelet 到 apiserver 通信异常。

# 风险、边界和误区
+ **1000 节点就是把 worker 扩到 1000 台**
    - 问题：忽略控制面、DNS、网络、镜像、监控和运维治理。
    - 更稳妥的表达：1000 节点要按生产体系建设，worker 数只是结果。
+ **apiserver 慢就扩容 apiserver**
    - 问题：可能真正瓶颈是 etcd、webhook、audit 或客户端异常请求。
    - 更稳妥的表达：先看请求分布和后端延迟，再决定扩容或治理。
+ **etcd 多节点越多越稳定**
    - 问题：etcd 成员越多，复制和选主成本也增加。
    - 更稳妥的表达：通常 3 或 5 节点，重点是低延迟磁盘和网络。
+ **上 eBPF 就能解决网络规模问题**
    - 问题：eBPF 也有内核、排障、升级和团队能力要求。
    - 更稳妥的表达：eBPF 是可选优化，不是大规模集群的唯一答案。
+ **CoreDNS 多加副本就够了**
    - 问题：请求仍然可能穿过 kube-proxy、conntrack 和跨节点链路。
    - 更稳妥的表达：CoreDNS 扩容可以和 NodeLocal DNSCache 组合。
+ **HPA 可以解决资源不足**
    - 问题：HPA 只调副本，节点资源不足还需要 CA 或容量治理。
    - 更稳妥的表达：HPA、VPA、CA 解决不同层级问题。
+ **监控装 Prometheus 就行**
    - 问题：1000 节点下指标基数、采集延迟、存储和查询都会成为问题。
    - 更稳妥的表达：需要分片、remote write、降采样和 label 治理。
+ **单集群越大越好**
    - 问题：故障域、升级成本、租户隔离都会恶化。
    - 更稳妥的表达：1000 节点能做，但要评估是否应该拆多集群。
+ **自研 controller 直接轮询 apiserver**
    - 问题：会放大 apiserver QPS 和 etcd 压力。
    - 更稳妥的表达：用 informer/watch/cache，必要时做平台侧状态同步。
+ **我完整建设过 1000 节点集群**
    - 问题：如果没有事实支撑，会被追问细节打穿。
    - 更稳妥的表达：可以说理解方案、参与过相邻能力、能设计和排查关键链路。

# 和项目的安全连接
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1779171070772-31c4bedd-7503-49e9-b2d7-ba82e06cdb37.png" width="1200" title="" crop="0,0,1,1" id="u61ac9a07" class="ne-image">

## 了解型说法
> 我没有把“1000 节点集群建设”包装成一个我完整落地过的项目。更准确地说，我理解这类生产级集群建设要从控制面、节点面、网络、DNS、存储、入口、可观测、节点生命周期和容量治理一起设计。这个知识点和我做过的 SAE 多集群发布、SAI 训练推理托管、Bigeyes / OTel 可观测、数据平台调度都有交集。
>

## 排查型说法
> 如果生产里出现大规模发布卡住、Pod Pending、DNS 慢、节点 NotReady 或训练任务调度异常，我不会直接归因某个组件，而是按“症状 → 假设 → 验证 → 指标 → 结论 → 优化”排查。比如 Pod Pending 先看 events，再区分是 scheduler、quota、taint、image pull、CSI、CNI 还是 admission；apiserver 慢则看 request latency、APF、webhook 和 etcd 延迟。
>

## 实践型说法
> 在 SAE 场景里，我可以把这个知识点连接到多集群发布、Rollouts 灰度、Tekton 构建、状态 watcher 和发布限流；在 SAI 场景里，可以连接到 TFJob、推理服务、GPU 节点池、资源组、镜像、PVC 和事件日志；在 Bigeyes / OTel 场景里，可以连接到指标、日志、事件、告警聚合和 RCA。更稳妥的表达是：这些项目让我接触了大规模 K8s 平台的关键子问题，但不能直接说我完整从 0 到 1 建过 1000 节点集群。
>

## 不能说的话
+ 不能说“我独立落地了 1000 节点 K8s 集群”，除非有事实支撑。
+ 不能说“只要 external etcd 和 3 个 apiserver 就能支撑 1000 节点”。
+ 不能说“上 eBPF 就解决大规模网络问题”。
+ 不能说“Prometheus 单实例就够”。
+ 不能把云厂商 ACK / EKS / GKE 的托管能力说成自己建设了底层控制面。

# 面试追问树
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1779170788358-9107501b-daa8-4227-9d59-3614f1b69ec3.png" width="900" title="" crop="0,0,1,1" id="ube1d4f57" class="ne-image">

```latex
Q1：1000 节点 K8s 集群要部署哪些组件？
  └── Q2：这些组件怎么分层？控制面、节点面、基础能力、运维治理分别是什么？
        └── Q3：控制面为什么会成为瓶颈？apiserver、etcd、watch、webhook 分别怎么看？
              └── Q4：etcd 为什么要独立部署？3 节点和 5 节点怎么取舍？
                    └── Q5：DNS、网络、镜像、监控在大规模下分别有什么风险？
                          └── Q6：Pod Pending、apiserver 慢、DNS 慢分别怎么排查？
                                └── Q7：如果和你的 SAE / SAI / Bigeyes 项目结合，你能说到什么程度？
                                      └── Q8：哪些内容不能夸大成实际项目经验？
```

# 高频 Q&A
## Q：1000 节点集群最核心的组件清单是什么？
回答：

> 核心组件分四类。控制面是 apiserver、controller-manager、scheduler、etcd；节点面是 kubelet、containerd、CNI、kube-proxy 或 eBPF；基础能力是 CoreDNS、NodeLocal DNSCache、CSI、Ingress/Gateway、RBAC、Admission、证书和审计；运维治理是监控、日志、事件、告警、备份、升级、节点生命周期和容量弹性。1000 节点下，清单只是起点，更关键是每个组件的规模化瓶颈。
>

## Q：1000 节点最大的瓶颈通常在哪里？
回答：

> 常见瓶颈在控制面和基础链路：apiserver 请求量、etcd 写延迟、watch 扩散、webhook 延迟、DNS QPS、CNI / Service 数据面、镜像拉取和监控指标量。不是所有问题都靠加节点解决，很多问题是控制面和运维治理能力不足。
>

## Q：apiserver 怎么做高可用？
回答：

> apiserver 本身无状态，可以多副本部署，前面通过 LB 或 VIP 暴露统一入口。controller-manager 和 scheduler 也可以多副本，但通过 leader election 保证一个主实例工作。要注意 apiserver 扩容不是万能的，后端 etcd、webhook 和审计链路可能才是瓶颈。
>

## Q：为什么 etcd 建议独立部署？
回答：

> etcd 是 Kubernetes 的状态存储，对磁盘延迟和网络稳定性敏感。独立部署可以隔离控制面其他组件的资源竞争，也便于单独做备份、恢复、监控、升级和故障替换。1000 节点下，我会优先考虑 external etcd，而不是把 etcd 和 apiserver 简单混在一起。
>

## Q：etcd 3 节点和 5 节点怎么选？
回答：

> 3 节点可以容忍 1 个节点故障，5 节点可以容忍 2 个节点故障，但 5 节点复制成本更高，也更依赖网络质量。不是节点越多越好，通常要根据故障域、RTT、磁盘延迟和运维能力决定。大部分场景先从 3 节点高质量部署起步更稳。
>

## Q：CoreDNS 为什么容易成为瓶颈？
回答：

> 因为服务发现是高频路径，应用短连接、ndots、重试和服务调用都会放大 DNS QPS。如果所有 Pod 都访问 CoreDNS Service，会给 CoreDNS、kube-proxy、conntrack 和网络带来压力。大规模集群通常要配合 CoreDNS 扩容和 NodeLocal DNSCache。
>

## Q：CNI 选型应该怎么回答？
回答：

> 我不会只说装 Calico 或 Cilium，而是看网络模型、云厂商 VPC 集成、NetworkPolicy、Service 规模、endpoint 数量、eBPF 能力、可观测和团队排障能力。1000 节点下，CNI 的可运维性和故障定位能力跟性能一样重要。
>

## Q：为什么镜像分发也是集群建设问题？
回答：

> 因为大规模发布或节点扩容时，很多节点会同时拉镜像。如果镜像仓库、对象存储、NAT 或出口带宽扛不住，Pod 启动会变慢，甚至出现 ImagePullBackOff。生产集群要做私有仓库、镜像缓存、节点预热、基础镜像治理，必要时做 P2P 分发。
>

## Q：Prometheus 在 1000 节点下怎么设计？
回答：

> 不建议一个 Prometheus 全量采所有指标。要考虑分片、remote write、降采样、保留策略和 label cardinality 治理。节点数上来后，Pod、container、endpoint、label 维度会让时序数量快速膨胀，监控系统本身也会成为生产系统。
>

## Q：单集群 1000 节点好，还是拆多个集群好？
回答：

> 1000 节点单集群技术上可以做，但不一定是最优。单集群资源池大、调度统一，但故障域、升级成本和租户隔离压力也更大。是否拆多集群要看地域、业务线、资源类型、在线/离线隔离、GPU/CPU 节点池和运维组织结构。
>

## Q：如果 Pod Pending，你怎么排查？
回答：

> 先看 `kubectl describe pod` 的 events，不直接假设是 scheduler。要区分 FailedScheduling、ImagePullBackOff、FailedMount、CNI 创建失败、quota、taint、node affinity、admission webhook 等情况。Pending 是结果，不是原因。
>

## Q：这个课题怎么和你的项目结合？
回答：

> 我会保守连接。SAE 让我接触多集群发布、Rollouts、Tekton、状态 watcher 和发布治理；SAI 让我接触训练/推理工作负载、GPU 节点池、PVC、日志事件和第三方托管平台；Bigeyes / OTel 让我接触指标、日志、事件和告警治理。这些都是 1000 节点集群建设里的关键子问题，但我不会把它夸大成完整建设过一个 1000 节点集群。
>

# 三档背诵版
## 三十秒版
> 1000 节点 Kubernetes 集群建设不是单纯扩 worker，而是生产级集群体系设计。核心分四层：控制面高可用，包括 apiserver、controller-manager、scheduler、external etcd；节点面，包括 kubelet、containerd、CNI、kube-proxy/eBPF；基础能力，包括 CoreDNS、NodeLocal DNSCache、CSI、Ingress/Gateway、RBAC 和 Admission；运维治理，包括监控、日志、事件、备份、升级、节点生命周期和容量弹性。真正难点是 apiserver QPS、etcd 延迟、watch 扩散、DNS、网络、镜像分发和监控数据量。
>

## 三分钟版
> 如果让我设计一个至少支撑 1000 节点的 Kubernetes 集群，我会先分层。
>
> 第一层是控制面。apiserver 多副本，前面通过 LB 或 VIP 暴露；controller-manager 和 scheduler 多副本，通过 leader election 保证高可用；etcd 用 external etcd，独立 3 或 5 节点，使用低延迟磁盘，并做 snapshot、恢复演练和核心指标监控。
>
> 第二层是节点面。每个节点要标准化 kubelet、containerd、CNI、kube-proxy 或 eBPF datapath。kubelet 要配置系统资源预留、驱逐策略、maxPods、镜像 GC、日志限制；containerd 要接内网镜像仓库和缓存；CNI 要验证 Pod 网络、Service、EndpointSlice、NetworkPolicy 和 conntrack。
>
> 第三层是基础能力。包括 CoreDNS、NodeLocal DNSCache、CSI、Ingress/Gateway、RBAC、Admission、证书和审计。DNS 和镜像分发是容易被忽略的规模化瓶颈，不能只看调度和控制面。
>
> 第四层是运维治理。要有 Prometheus 分片或 remote write、日志和事件治理、告警平台、etcd 备份、节点生命周期、升级灰度、Quota、LimitRange、HPA/VPA/Cluster Autoscaler 和容量压测。
>
> 排障时我会按症状建立假设。比如 Pod Pending 先看 events，区分调度、镜像、PVC、CNI、Admission；apiserver 慢看请求延迟、APF、webhook 和 etcd；DNS 慢看 CoreDNS、NodeLocal DNSCache 和 conntrack。核心不是背组件，而是知道瓶颈在哪里、指标怎么看、怎么治理。
>

## 五分钟版
> 1000 节点集群的面试回答要避免两个误区：第一，不要讲成 kubeadm 安装步骤；第二，不要把它夸大成自己完整落地过。更合理的回答是生产级 K8s 集群建设方法论。
>
> 我会先定义目标：不是让 1000 个 Node Ready，而是在大规模发布、节点扩容、AI 训练任务提交、服务发现高 QPS、镜像拉取、监控采集、控制器异常重试时仍然稳定。
>
> 控制面方面，apiserver 多副本解决入口高可用，controller-manager 和 scheduler 通过 leader election 保证 HA，etcd 独立部署并关注磁盘 fsync、leader、DB size、proposal pending。apiserver 扩容不是万能的，因为后端 etcd、webhook、audit、watch fan-out 都可能成为瓶颈。
>
> 节点面方面，kubelet 要做好 resource reservation、eviction、maxPods、日志和镜像 GC。containerd 要统一版本、cgroup driver、私有仓库和镜像缓存。CNI 要根据云环境、VPC、NetworkPolicy、Service 规模和可观测能力选型，不能盲目说某个插件一定最好。
>
> 基础能力方面，CoreDNS 要配合 NodeLocal DNSCache，CSI 要考虑 attach/detach、PVC、快照和拓扑，Ingress/Gateway 要承接入口流量和灰度，Admission 要做安全和资源治理，但 webhook 本身也要有超时、熔断和高可用。
>
> 运维方面，1000 节点必须有 Prometheus 分片或 remote write、日志采样、事件聚合、告警治理、etcd 备份恢复、节点生命周期、灰度升级、Quota、HPA/VPA/CA、节点池水位和容量压测。
>
> 和我自己的项目连接时，我会说 SAE 的多集群发布、Rollouts、Tekton、watcher 状态同步，SAI 的 TFJob、推理服务、GPU 节点池、PVC 和日志事件，以及 Bigeyes / OTel 的告警和可观测治理，都和这个课题有交集。但我不会说自己完整建设过一个 1000 节点集群，而是说我理解关键子问题，并且能把已有平台经验迁移到这类集群建设和排障中。
>

# 图示清单
+ **P0 **`01_k8s_1000_nodes_principle.png`：对应“原理模型”，用于解释 1000 节点集群的分层架构和关键组件关系。
+ **P0 **`02_k8s_1000_nodes_mechanism.png`：对应“关键机制”，用于解释 apiserver、webhook、etcd、watch fan-out 的压力链路。
+ **P1 **`03_k8s_1000_nodes_scenario.png`：对应“典型业务场景”，用于把集群建设映射到发布、AI、入口、可观测、存储、弹性、安全。
+ **P0 **`04_k8s_1000_nodes_troubleshooting.png`：对应“排障路径”，用于把故障定位抽象成症状、假设、验证、指标、结论、优化、复测。
+ **P1 **`05_k8s_1000_nodes_project_connection.png`：对应“和项目的安全连接”，用于说明如何挂到 SAE / SAI / Bigeyes / 数据平台，同时避免夸大。
+ **P2 **`06_k8s_1000_nodes_followup_tree.png`：对应“面试追问树”，用于模拟面试官从组件清单追问到机制、场景、排障和边界。

# 面试前检查清单
- [ ] 我能用三十秒讲清楚 1000 节点 K8s 集群建设不是简单扩 worker。
- [ ] 我能说清楚控制面、节点面、基础能力、运维治理四层。
- [ ] 我能解释 apiserver、etcd、watch、webhook 为什么会成为瓶颈。
- [ ] 我能说出 external etcd 的价值和代价。
- [ ] 我能解释 NodeLocal DNSCache 为什么重要。
- [ ] 我能区分 HPA、VPA、Cluster Autoscaler。
- [ ] 我能说明 CNI 选型不是简单背 Calico / Cilium。
- [ ] 我能按“症状 → 假设 → 验证 → 指标 → 结论 → 优化 → 复测”讲排障。
- [ ] 我知道 Pending 不等于 scheduler 问题。
- [ ] 我知道哪些内容不能夸大成项目经验。
- [ ] 我能把这个技术点安全连接到 SAE、SAI、Bigeyes、数据平台。
- [ ] 我能说明单大集群和多集群的取舍。
- [ ] 我能解释为什么监控、日志、事件在 1000 节点下本身也要治理。

# 官方参考
+ Kubernetes large cluster considerations: [https://kubernetes.io/docs/setup/best-practices/cluster-large/](https://kubernetes.io/docs/setup/best-practices/cluster-large/)
+ Kubernetes components: [https://kubernetes.io/docs/concepts/overview/components/](https://kubernetes.io/docs/concepts/overview/components/)
+ kube-apiserver reference: [https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/)
+ kube-controller-manager reference: [https://kubernetes.io/docs/reference/command-line-tools-reference/kube-controller-manager/](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-controller-manager/)
+ NodeLocal DNSCache: [https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/)
+ DNS horizontal autoscaling: [https://kubernetes.io/docs/tasks/administer-cluster/dns-horizontal-autoscaling/](https://kubernetes.io/docs/tasks/administer-cluster/dns-horizontal-autoscaling/)
+ etcd hardware recommendations: [https://etcd.io/docs/v3.3/op-guide/hardware/](https://etcd.io/docs/v3.3/op-guide/hardware/)
