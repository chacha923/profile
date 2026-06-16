# 面试定位卡

- **技术点**：Envoy Gateway 视角下的 GPU 服务平滑出云。
- **所属领域**：云原生网关、Gateway API、Envoy xDS、跨云流量治理、AI Infra 推理链路迁移。
- **面试价值**：能说明自己不是把 Envoy 当成普通反向代理，而是能从 Kubernetes 资源、控制面、数据面、xDS、灰度和回滚几个层次解释一条真实流量迁移链路。
- **常见考法**：Envoy Gateway 和 Ingress 的区别、HTTPRoute 如何生成 xDS、ExternalName 如何变成 STRICT_DNS cluster、权重灰度为什么不等于真实流量比例、xDS ACK 不代表业务成功。
- **适合挂钩项目**：ACK 内 CPU 服务调用 GPU 推理服务，GPU 服务从 ACK 迁到贝联，需要灰度、回滚和跨云可观测。
- **不适合夸大的地方**：不能说当前仓库已经实现了贝联专用导流能力，也不能说 `cmd/proxy` 是主生产路径；更不能说 Envoy 会自动接管所有 Pod 出站流量。

# 三十秒回答

> 这个问题的核心不是把 Envoy 数据面部署到 ACK 外，而是让 ACK 内 CPU 服务的 GPU 调用显式经过可控的 Gateway / Envoy / LB / Mesh 入口。当前 gateway 仓库的主路径是 ACK 内 `envoy-gateway` 控制面 watch Gateway、HTTPRoute、Service、EndpointSlice，然后生成 xDS，下发给 ACK edge 节点上的 Envoy Deployment。GPU 出云时，真正切换的是 Envoy 的 upstream backend：从 ACK 内 GPU Service 逐步切到贝联 GPU 入口。代价是必须先解决导流入口、跨云网络、DNS/TLS、xDS 生效和业务指标验证，不能只看 YAML 权重。

# 为什么需要它

- **没有它之前的问题**：CPU 服务直接调用 ACK 内 GPU Service，GPU 服务迁到贝联时，如果直接改域名或删除旧服务，容易出现大面积超时、回滚困难、指标不可解释。
- **它的解决方式**：在 CPU 调用 GPU 的路径上放一个可控的流量治理层，通过 HTTPRoute backend 权重、ExternalName Service、LB 或业务域名逐步切换 upstream。
- **它引入的新问题**：流量入口必须真实经过 Envoy；edge 节点到贝联必须网络可达；ExternalName 只解决 DNS 映射，不等于完整服务治理；xDS 正常不代表请求一定成功。
- **必须关注的场景**：跨云推理调用、GPU 服务迁移、ACK 内外混部灰度、跨云链路超时、TLS/SNI 不一致、权重配置和实际流量比例不一致。

# 核心概念表

- **envoy-gateway 控制面**
  - 解释：运行在 ACK 内的控制面，watch Kubernetes 资源并生成 Envoy xDS。
  - 面试展开点：它不是业务流量数据面，而是配置生成和下发中心。

- **Envoy 数据面**
  - 解释：由 controller 根据 PodTemplate 创建成 Kubernetes Deployment，运行在 ACK edge 节点。
  - 面试展开点：当前主路径不是 ACK 外 `cmd/proxy` + 本地 Envoy。

- **Gateway / HTTPRoute**
  - 解释：Gateway API 的入口和路由模型，表达 host、path、backendRef、weight 等规则。
  - 面试展开点：HTTPRoute 不是直接转发流量，而是被控制面翻译成 xDS。

- **Service / EndpointSlice**
  - 解释：ClusterIP Service 通过 EndpointSlice 生成 EDS；ExternalName Service 生成 STRICT_DNS cluster。
  - 面试展开点：不同 Service 类型对应不同 xDS cluster 形态。

- **xDS**
  - 解释：Envoy 的动态配置协议，包括 Listener、Route、Cluster、Endpoint 等资源。
  - 面试展开点：xDS ACK 只能说明 Envoy 接受了配置，不代表 upstream 一定可达。

- **ExternalName**
  - 解释：把 Kubernetes Service 名映射到外部 DNS 名。
  - 面试展开点：适合把贝联域名纳入 HTTPRoute backendRef 模型，但它不负责健康检查、摘除、限流和证书治理。

- **cmd/proxy**
  - 解释：仓库里存在的 xDS proxy / agent 形态。
  - 面试展开点：从当前部署文件和 controller 逻辑看，它不能被当成 GPU 出云的主生产链路。

# 原理模型

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1779176986728-38929a5a-18b4-46cb-8dc5-1e397d2f4b3e.png" width="1300" title="" crop="0,0,1,1" id="ue3553ffb" class="ne-image">

## 基础设施层

- ACK 集群内有 `envoy-gateway` 控制面 Deployment。
- Envoy 数据面也是 ACK 内 Kubernetes Deployment，通过 PodTemplate 创建。
- 数据面 Pod 使用 `dnsPolicy: ClusterFirst`，bootstrap 里连接 `envoy-gateway:18000`。
- `nodeSelector: type=edge` 和 toleration 说明数据面会调度到 ACK edge 节点。

## Kubernetes 层

- Gateway 决定数据面入口和 listener 归属。
- HTTPRoute 表达 host、path、backendRef 和权重。
- ClusterIP Service 通过 EndpointSlice 进入 EDS。
- ExternalName Service 会被翻译成 STRICT_DNS cluster。

## Envoy / xDS 层

- 控制面把 Gateway、HTTPRoute、Service、EndpointSlice 翻译成 LDS、RDS、CDS、EDS 等 xDS 资源。
- Envoy 数据面通过 ADS / Delta ADS 拉取配置。
- Envoy 收到配置后，按 route 和 cluster 把流量转到 ACK 内 GPU 或贝联 GPU。

## 业务层

- CPU 服务不会天然经过 Envoy。
- 这套方案成立的前提是 CPU 到 GPU 的调用路径已经显式经过 Gateway、Envoy、Mesh Egress、内部 LB 或可切换业务域名。
- 如果 CPU 服务仍然直接调用 `gpu-service.namespace.svc.cluster.local`，流量会走 Kubernetes Service / EndpointSlice / kube-proxy / CNI，不会自动进入 edge Envoy。

# 关键机制

## 控制面和数据面分离

- **解决的问题**：避免把路由配置、Envoy 进程和业务流量混在一起理解。
- **工作方式**：`envoy-gateway` 在 ACK 内 watch Kubernetes 资源；GatewayController 根据 PodTemplate 创建 Envoy Deployment；Envoy Pod 连接 `envoy-gateway:18000` 获取 xDS。
- **代价**：排障要同时看 Kubernetes 资源、控制面日志、xDS ACK/NACK 和 Envoy admin，不是只看一个 YAML。
- **面试追问**：你为什么确定它不是 ACK 外数据面？

可以这样回答：

> 因为主部署文件里 Envoy 是 PodTemplate，controller 代码会创建 Kubernetes Deployment；Envoy bootstrap 使用 `envoy-gateway:18000`，Pod 使用 `dnsPolicy: ClusterFirst`。这些证据都指向 ACK 内运行模型。`cmd/proxy/ci` 虽然存在 docker-compose 和本地 xDS 形态，但不能反推为主生产路径。

## HTTPRoute 到 xDS

- **解决的问题**：把面向 Kubernetes 用户的路由声明转换成 Envoy 可执行的动态配置。
- **工作方式**：HTTPRoute 变化后进入 reconciler；控制面解析 parentRef、hostnames、matches、backendRefs；再结合 Service 和 EndpointSlice 构建 Route、Cluster、Endpoint。
- **代价**：HTTPRoute status Accepted、xDS ACK、真实请求成功是三件事，不能混为一谈。
- **面试追问**：为什么 HTTPRoute 权重变了，真实流量比例不一定立刻等于权重？

当前仓库接入示例要注意 `parentRefs.namespace` 和 annotations。示例可以写成：

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: HTTPRoute
metadata:
  name: gpu-inference-route
  namespace: app-ns
  annotations:
    envoy-gateway/timeout: 30s
spec:
  parentRefs:
    - name: default-eg
      namespace: envoy-gateway-system
  hostnames:
    - gpu-inference.soulapp.cn
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /gpu-inference
      backendRefs:
        - name: gpu-ack
          port: 80
          weight: 99
        - name: gpu-belian
          port: 80
          weight: 1
```

这里的关键点：

- `parentRefs.namespace` 要指向 `envoy-gateway-system`。
- `backendRefs` 要指向当前 namespace 下存在的 Service，或显式写清 namespace。
- 当前代码对 HTTPRoute annotations 有实现依赖，不能把完全无 annotations 的 YAML 当成可直接生效样例。
- `hostnames` 建议明确写出，避免 route domain 不清晰。

## ExternalName 到 STRICT_DNS

- **解决的问题**：让 HTTPRoute backendRef 仍然引用 Kubernetes Service，同时把实际 upstream 指向贝联域名。
- **工作方式**：创建 `type: ExternalName` 的 Service；控制面识别 Service 类型后生成 STRICT_DNS cluster；Envoy 运行时解析外部域名。
- **代价**：ExternalName 只解决名字映射，不解决健康检查、跨云链路抖动、TLS/SNI、贝联侧限流和多实例摘除。
- **面试追问**：ExternalName 和普通 ClusterIP Service 在 xDS 上有什么区别？

示例：

```yaml
apiVersion: v1
kind: Service
metadata:
  name: gpu-belian
  namespace: app-ns
spec:
  type: ExternalName
  externalName: gpu-inference.belian.internal
  ports:
    - name: http
      port: 80
      targetPort: 80
```

需要补一句边界：

> 如果生产切换依赖修改 Service 的 `externalName` 触发 xDS 更新，需要实际验证 ServiceWatcher 和完整重建行为；infra_docs 里也把 Service 变更边界标为需要 Owner 确认。

## 权重灰度和回滚

- **解决的问题**：避免一次性把 GPU 推理流量全部切到贝联。
- **工作方式**：HTTPRoute backendRef 同时保留 ACK GPU 和贝联 GPU，按 99/1、95/5、90/10、50/50、100/0 逐步调整。
- **代价**：权重是配置意图，不是业务结果。真实比例还受连接复用、重试、超时、LB、DNS、客户端缓存影响。
- **面试追问**：为什么回滚时不建议先删 backend？

回滚更稳妥的表达是：

> 先把贝联 backend 权重切到 0，把 ACK backend 切回 100，再保留现场排查。当前代码会过滤 `weight: 0` 的 backendRef，所以要确认最终 xDS 中该 cluster 是否消失，避免把“配置被过滤”误判成“Envoy 仍保留 0 权重 cluster”。

## cmd/proxy 的边界

- **解决的问题**：避免把仓库里的测试/实验形态误解为主生产链路。
- **工作方式**：`cmd/proxy` 存在 agent + 本地 xDS server + Envoy 的形态，默认参数里有本地端口和上游 xDS 地址。
- **代价**：仅凭这个目录，不能证明生产里有 ACK 外 agent，也不能证明 ACK 内外双数据面共享同一控制面。
- **面试追问**：什么证据才能证明 ACK 外数据面是生产路径？

需要的证据包括：

- ACK 外机器上实际运行了 agent。
- agent 镜像进入生产发布系统。
- xDS 端口对 ACK 外暴露。
- 入口 LB 把业务流量切到 ACK 外 Envoy。
- 生产日志中能看到外部节点连接控制面。

# 横向对比

- **ACK 内 edge Envoy vs ACK 外 cmd/proxy**
  - 区别：前者有部署文件、PodTemplate、controller 创建 Deployment 和集群内 DNS 证据；后者目前只能说明仓库存在 agent/CI 形态。
  - 什么时候用：当前 GPU 出云文档应以 ACK 内 edge Envoy 为主线。
  - 面试注意点：不要把代码目录存在等价成生产链路存在。

- **ClusterIP Service vs ExternalName Service**
  - 区别：ClusterIP 依赖 EndpointSlice 生成 EDS；ExternalName 生成 STRICT_DNS cluster。
  - 什么时候用：ACK 内 GPU Pod 用 ClusterIP；贝联域名接入可以用 ExternalName。
  - 面试注意点：ExternalName 不提供实例健康检查和摘除能力。

- **HTTPRoute 权重 vs DNS/LB/Mesh 权重**
  - 区别：HTTPRoute 权重是 gateway 仓库内可翻译的路由配置；DNS/LB/Mesh 权重属于仓库外部导流能力。
  - 什么时候用：如果流量已经进入 Envoy，优先用 HTTPRoute；如果流量入口不在 Envoy，需要先改业务域名、LB 或 Mesh Egress。
  - 面试注意点：不要把仓库外能力写成 gateway 仓库自身能力。

- **xDS ACK vs 业务成功**
  - 区别：ACK 说明 Envoy 接受配置；业务成功还要求 route 命中、cluster 可达、DNS/TLS 正确、贝联服务正常。
  - 什么时候用：排障时先分层定位，不要看到 ACK 就结束。
  - 面试注意点：xDS 是控制面结果，不是端到端 SLO。

# 典型业务场景

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1779177015963-c18bf599-eb30-4bf0-82db-36c67980cf5a.png" width="1200" title="" crop="0,0,1,1" id="ueac46013" class="ne-image">

- **GPU 推理服务从 ACK 迁到贝联**
  - 为什么相关：GPU 服务迁移需要灰度和回滚，不能直接切全量。
  - 可能现象：部分请求超时、P99 变差、贝联侧 QPS 不符合权重、ACK GPU QPS 没下降。
  - 排查方式：先确认 CPU 流量是否进入 Envoy，再看 HTTPRoute、xDS、cluster、DNS 和贝联入口日志。
  - 优化方向：明确导流入口，保留旧 backend，用权重逐步切换。

- **CPU 服务仍然直连 Kubernetes Service**
  - 为什么相关：这是方案不成立的最常见原因。
  - 可能现象：HTTPRoute 权重调整了，但贝联侧没有流量。
  - 排查方式：看 CPU 服务 access log、Envoy access log、ACK GPU QPS 和贝联入口 QPS。
  - 优化方向：把 CPU 调用改到 Gateway 域名、Mesh Egress、内部 LB 或可切换业务域名。

- **ExternalName 指向贝联域名**
  - 为什么相关：这是把贝联域名纳入 HTTPRoute backendRef 的可行方式。
  - 可能现象：Envoy cluster 存在，但 DNS 解析失败、TLS SNI 不匹配或跨云访问超时。
  - 排查方式：在 Envoy Pod 内验证 DNS、端口、TLS、路由和安全组。
  - 优化方向：为贝联入口提供稳定 LB、健康检查、限流和可观测。

- **灰度比例和真实流量不一致**
  - 为什么相关：权重只是路由配置，真实分布还受连接、重试和客户端行为影响。
  - 可能现象：配置 1%，贝联侧实际 QPS 偏高或偏低。
  - 排查方式：同时对比 Envoy access log、贝联入口日志、ACK GPU QPS 和 CPU 客户端指标。
  - 优化方向：分阶段放量，按错误率、延迟和业务结果指标决策。

# 排障路径

排障顺序不要从 xDS 开始，而要从“流量有没有进入 Envoy”开始。

- **症状**：HTTPRoute 权重已调整，但贝联侧没有流量。
- **初始假设**：CPU 服务仍然直连 ACK 内 GPU Service，流量没有经过 Envoy。
- **验证命令**：

```bash
kubectl get httproute -A -o yaml
kubectl get gateway -n envoy-gateway-system
kubectl get svc -n app-ns gpu-ack gpu-belian
kubectl get endpointslice -n app-ns -l kubernetes.io/service-name=gpu-ack
```

这组命令用于验证什么：

- HTTPRoute 是否被 Gateway 接受。
- backendRef 引用的 Service 是否存在。
- ACK 内旧 backend 是否仍有 EndpointSlice。
- 贝联 ExternalName 是否被建模成 Kubernetes Service。

重点看什么：

- `parentRefs.namespace` 是否是 `envoy-gateway-system`。
- HTTPRoute status 是否 Accepted。
- Service namespace 是否和 backendRef 对得上。
- EndpointSlice 是否为空。

异常说明什么：

- HTTPRoute 未 Accepted：先修 Gateway / ParentRef / host / backendRef。
- Service 不存在：控制面无法生成有效 backend。
- EndpointSlice 为空：Cluster 可能存在，但 upstream 无实例。

- **症状**：Envoy 收到了配置，但请求超时。
- **初始假设**：xDS 已生效，但 upstream 网络、DNS、TLS 或贝联服务异常。
- **验证命令**：

```bash
kubectl exec -n <envoy-ns> <envoy-pod> -- curl -v http://gpu-inference.belian.internal
kubectl exec -n <envoy-ns> <envoy-pod> -- nslookup gpu-inference.belian.internal
```

这组命令用于验证什么：

- Envoy Pod 内是否能解析贝联域名。
- ACK edge 节点到贝联入口是否可达。
- 协议、端口、Host 和 TLS 是否符合预期。

重点看什么：

- DNS 是否解析成功。
- TCP 是否连通。
- TLS/SNI 是否匹配。
- 贝联返回码和耗时是否正常。

异常说明什么：

- DNS 失败：ExternalName 或集群 DNS 解析链路有问题。
- 连接失败：路由、安全组、ACL、NAT 或专线有问题。
- TLS 失败：HostRewrite、SNI 或证书配置有问题。

- **症状**：贝联有流量，但错误率高。
- **初始假设**：跨云链路或贝联服务容量不满足灰度比例。
- **关键指标**：
  - Envoy `upstream_rq_total`
  - Envoy `upstream_rq_5xx`
  - Envoy `upstream_rq_timeout`
  - Envoy `upstream_cx_connect_fail`
  - xDS ACK / NACK
  - CPU 服务端错误率和 P95/P99
  - 贝联入口 QPS、GPU 推理耗时、队列等待时间、限流日志
- **优化动作**：降低权重，修复网络/TLS/容量问题，再小比例复测。
- **复测方式**：同时观察 Envoy、ACK GPU、贝联 GPU 和 CPU 客户端四侧指标，确认比例、错误率和延迟都符合预期。

# 风险、边界和误区

- **说法 / 做法**：`envoy-proxy` 部署到 ACK 外，所以能接管出云流量。
  - 问题：当前主部署证据指向 ACK 内 edge Envoy，不是 ACK 外主数据面。
  - 更稳妥的表达：出云的是 upstream backend，不是 Envoy 数据面本身。

- **说法 / 做法**：只要配置 HTTPRoute 权重，CPU 到 GPU 的流量就会灰度。
  - 问题：前提是 CPU 调用路径已经进入 Envoy。
  - 更稳妥的表达：先确认导流入口，再谈 HTTPRoute backend 权重。

- **说法 / 做法**：ExternalName 就等于完整跨云服务治理。
  - 问题：它只做 DNS 映射，不做健康检查、实例摘除、限流和证书治理。
  - 更稳妥的表达：ExternalName 可以作为接入贝联域名的 Kubernetes 表达方式，但生产治理还要依赖 LB、健康检查、限流和可观测。

- **说法 / 做法**：xDS ACK 说明迁移成功。
  - 问题：ACK 只说明 Envoy 接受配置。
  - 更稳妥的表达：还要验证 route 命中、cluster 可达、DNS/TLS、贝联入口和业务指标。

- **说法 / 做法**：DNS/LB/Mesh 权重都是 gateway 仓库能力。
  - 问题：这些属于仓库外导流层，不是当前 gateway 代码直接提供的能力。
  - 更稳妥的表达：gateway 仓库内可控的是 HTTPRoute、Service、EndpointSlice 到 xDS；DNS/LB/Mesh 是外部配合方案。

# 和项目的安全连接

## 了解型说法

我理解这个问题的关键是把 GPU 服务出云拆成两件事：第一是流量入口，CPU 服务的 GPU 调用必须先进入可控的 Gateway / Envoy / Mesh / LB 层；第二是 backend 切换，在这一层把 upstream 从 ACK 内 GPU Service 灰度切到贝联 GPU 入口。

## 排查型说法

如果迁移后贝联侧没有流量，我不会先看 xDS，而是先确认 CPU 服务流量有没有进入 Envoy。因为如果 CPU 仍然直连 Kubernetes Service，HTTPRoute 权重怎么改都不会影响真实流量。

## 实践型说法

在这个 gateway 仓库里，可以安全挂钩的实践点是 Gateway / HTTPRoute / Service / EndpointSlice 到 xDS 的转换链路，以及 ExternalName Service 生成 STRICT_DNS cluster 的能力。贝联侧 LB、DNS、Mesh Egress 和业务域名切换需要作为外部导流设计单独说明。

## 不能说的话

- 不能说我已经用 `cmd/proxy` 做了 ACK 外生产数据面，除非有实际部署证据。
- 不能说 Envoy 自动接管了 CPU Pod 所有出站流量。
- 不能说 ExternalName 自带健康检查和跨云容灾。
- 不能说 xDS ACK 就代表 GPU 出云成功。
- 不能说 gateway 仓库已经内置贝联专用适配。

# 面试追问树

```text
Q1：Envoy Gateway 在这个场景里解决什么问题？
  └── Q2：为什么不是直接改 CPU 服务调用域名？
        └── Q3：HTTPRoute 是怎么变成 Envoy xDS 的？
              └── Q4：ClusterIP 和 ExternalName 在 xDS 里有什么区别？
                    └── Q5：为什么权重配置不等于真实流量比例？
                          └── Q6：如果贝联侧没有流量，你怎么排查？
                                └── Q7：这个能力和你实际项目怎么安全连接？
                                      └── Q8：哪些说法不能夸大？
```

# 高频 Q&A

## Envoy 数据面到底在 ACK 内还是 ACK 外？

结合当前仓库证据，主路径应理解为 ACK 内。Envoy 数据面来自 PodTemplate，由 controller 创建成 Kubernetes Deployment，bootstrap 连接的是 `envoy-gateway:18000`，并且 Pod 使用 `dnsPolicy: ClusterFirst`。这些都说明它依赖 ACK 内 Kubernetes 环境。

## `cmd/proxy` 目录是不是完全没用？

不是。它说明仓库里有 agent + 本地 xDS proxy 的形态，但从当前主部署文件看，它不能被当成 GPU 出云的生产主链路。面试里可以说它是非主路径或实验/CI 形态，除非有额外生产部署证据。

## GPU 服务出云到底切的是什么？

切的是 upstream backend。Envoy 数据面仍然在 ACK edge 节点上，流量进入 Envoy 后，再从 ACK 内 GPU Service 逐步切到贝联 GPU 入口。

## 为什么 CPU 服务不会天然经过 Envoy？

因为如果 CPU 服务直接调用 Kubernetes Service DNS，它会走 Service、EndpointSlice、kube-proxy 或 CNI，不会自动绕到 edge Envoy。必须让 CPU 的 GPU 调用入口显式经过 Gateway、Envoy、Mesh Egress、LB 或可切换业务域名。

## ExternalName 为什么适合这个场景？

因为 HTTPRoute backendRef 仍然需要引用 Kubernetes Service。ExternalName 可以把 `gpu-belian` 这个 Service 名映射到贝联域名，控制面再生成 STRICT_DNS cluster，让 Envoy 运行时解析外部 DNS。

## ExternalName 的缺点是什么？

它只解决名字映射，不解决健康检查、实例摘除、TLS、限流、多实例权重和跨云链路抖动。所以生产上最好让贝联入口本身有 LB、健康检查和可观测。

## xDS ACK 以后还要看什么？

还要看 Envoy listener、route、cluster、endpoint 或 DNS 是否符合预期；看 upstream 是否能连通；看 CPU 客户端、Envoy access log、ACK GPU 和贝联 GPU 四侧指标是否一致。

## 回滚为什么不建议先删对象？

先删对象会破坏现场，也可能让排障证据丢失。更稳妥的是先把贝联 backend 权重切到 0，把 ACK backend 切回 100，确认流量恢复后再分析贝联链路问题。

## DNS/LB/Mesh 权重和 HTTPRoute 权重是什么关系？

它们都是导流手段，但不在同一层。HTTPRoute 是 gateway 仓库内可翻译成 xDS 的能力；DNS/LB/Mesh 是外部导流层。如果 CPU 流量根本没进 Envoy，就需要先靠这些外部层把入口切到 Envoy。

## 面试里怎么避免说过头？

可以说自己理解并能分析这类迁移链路，也能指出 gateway 仓库已有的可用切点，比如 HTTPRoute 权重、ExternalName 到 STRICT_DNS、EndpointSlice 到 EDS。但不能说仓库已经实现了完整贝联迁移平台，除非有实际改造和上线证据。

# 三档背诵版

## 三十秒版

这个场景不是把 Envoy 部署到 ACK 外，而是 ACK 内 edge Envoy 承接 GPU 调用后，把 upstream 从 ACK 内 GPU Service 灰度切到贝联 GPU 入口。当前 gateway 仓库主链路是 Gateway / HTTPRoute / Service / EndpointSlice 到 xDS，再由 ACK 内 Envoy 数据面执行。关键前提是 CPU 服务流量必须先进入 Envoy，否则 HTTPRoute 权重不会影响真实请求。

## 三分钟版

我会把它拆成控制面、数据面和业务流量三层。控制面是 ACK 内的 `envoy-gateway`，负责 watch Gateway、HTTPRoute、Service、EndpointSlice，并生成 xDS。数据面是 controller 根据 PodTemplate 创建出来的 Envoy Deployment，运行在 ACK edge 节点，bootstrap 连接 `envoy-gateway:18000`。业务上，GPU 服务从 ACK 迁到贝联时，真正做的是 upstream backend 切换，而不是把 Envoy 本身迁出去。

落地时先确认 CPU 服务的 GPU 调用入口是否经过 Gateway / Envoy / Mesh / LB。然后保留 ACK 内 GPU Service 作为旧 backend，用贝联域名或 LB 建一个 ExternalName Service 作为新 backend，通过 HTTPRoute backendRef 权重从 1% 开始灰度。每一档都要同时看 CPU 客户端、Envoy access log、ACK GPU、贝联 GPU 和 xDS ACK/NACK。异常时先把贝联权重切到 0，不要直接删资源。

## 五分钟版

这类问题最容易误判的地方是把仓库里的 `cmd/proxy` 当成主生产路径。实际上从当前部署文件看，主路径是 ACK 内 GatewayController 创建 Envoy Deployment，Envoy 使用集群 DNS 连接 `envoy-gateway:18000` 拉 xDS。`cmd/proxy` 只能说明有 agent/CI 或实验形态，不能说明生产里存在 ACK 外数据面。

从机制上看，HTTPRoute 只是声明式路由，控制面会结合 Service 和 EndpointSlice 生成 Envoy 的 Route、Cluster 和 Endpoint。ClusterIP Service 走 EndpointSlice/EDS；ExternalName Service 走 STRICT_DNS。GPU 出云可以利用这个能力，把贝联域名包装成 Kubernetes Service，再通过 HTTPRoute 权重切换。但这只是网关内的配置能力，贝联侧网络、TLS/SNI、LB 健康检查、限流和可观测都要单独验证。

排障上我会先看业务流量有没有进 Envoy，再看 HTTPRoute status、Service/EndpointSlice、xDS ACK/NACK、Envoy admin、DNS/TLS 和贝联入口日志。面试里我会明确边界：我能基于这个仓库说明可用切点和风险，但不会把它夸大成已经完成的贝联专用迁移系统。

# 图示清单

| 图片 | 对应章节 | 目的 | 优先级 |
|---|---|---|---|
| 语雀 CDN 拓扑图 | 原理模型 | 说明 ACK 内控制面、ACK edge Envoy 数据面、贝联 upstream 的位置关系 | P0 |
| 语雀 CDN 迁移流程图 | 典型业务场景 / 关键机制 | 说明从 ACK GPU 到贝联 GPU 的灰度、验证和回滚流程 | P0 |

说明：当前文档只保留语雀 CDN 图片链接，已去掉从语雀复制时带出的本地 `images/...` 图片引用。本轮没有新增 Mermaid 图。

# 面试前检查清单

- [ ] 我能用三十秒讲清楚：出云的是 upstream backend，不是 Envoy 数据面本身。
- [ ] 我能解释当前仓库为什么更像 ACK 内 edge Envoy 主路径。
- [ ] 我能说出 Gateway、HTTPRoute、Service、EndpointSlice 到 xDS 的关系。
- [ ] 我能解释 ClusterIP Service 和 ExternalName Service 在 xDS 里的区别。
- [ ] 我能说清楚 CPU 服务必须先进入 Envoy 这个硬前提。
- [ ] 我能按“入口 -> HTTPRoute -> Service/EndpointSlice -> xDS -> Envoy -> 贝联 upstream”排障。
- [ ] 我能说明 xDS ACK 不等于业务成功。
- [ ] 我知道 DNS/LB/Mesh 属于外部导流层，不能说成 gateway 仓库内置能力。
- [ ] 我不会把 `cmd/proxy` 夸大成生产主链路。
