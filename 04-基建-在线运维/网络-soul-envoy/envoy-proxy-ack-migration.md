# Envoy Proxy 与 ACK 外部平滑迁移

本文补充 `project-overview.md` 没有展开的 `envoy-proxy` 模块。这里说的 `envoy-proxy` 不是 `api/config/v1alpha1.EnvoyProxy` CRD；当前这个 CRD 的 `Spec` 还是空壳。本文讨论的是 `cmd/proxy` 打包出来的 agent + Envoy 运行形态，用来让 Envoy 数据面在 ACK 集群外运行，同时复用 ACK 内的 Gateway 控制面配置。

# 1. 一句话定位

`envoy-proxy` 是一个 ACK 外部数据面适配层：

- ACK 内继续由 `envoy-gateway` 监听 Gateway / HTTPRoute / Service / EndpointSlice 并生成 xDS。
- ACK 外部署 `cmd/proxy` agent，它通过 Delta ADS 从 ACK 内控制面拉取 xDS。
- agent 在本机启动一个本地 xDS server，Envoy 只连接本机 `127.0.0.1:18002`。
- 上游入口流量可以逐步从 ACK 内 `envoy-default-eg` 切到 ACK 外 `envoy-proxy`，控制面配置不需要同步改两套。

核心价值不是“新写一套网关”，而是把数据面从 ACK 内解耦出来，支撑平滑迁移、灰度验证和快速回滚。

# 2. 为什么和 ACK 外迁有关

原主链路是：

```text
外部流量
  -> ACK 内 envoy-default-eg
  -> ACK 内/集群网络里的后端
```

加入 `envoy-proxy` 后，可以形成双数据面：

```text
同一套 Gateway / HTTPRoute / Service / EndpointSlice
        |
        v
ACK 内 envoy-gateway 控制面
        |
        +-- xDS -> ACK 内 envoy-default-eg
        |
        +-- Delta ADS -> ACK 外 cmd/proxy agent -> 本地 xDS -> ACK 外 Envoy
```

这样迁移时可以先保持控制面和路由规则不变，只增加 ACK 外数据面。入口 LB、DNS、上游网关或调度系统再按权重把流量从 ACK 内数据面逐步切到 ACK 外数据面。

平滑迁移依赖三个条件：

- 配置一致：ACK 内外 Envoy 都来自同一个 xDS 控制面。
- 可观测：外部 proxy 能看到 ACK/NACK、Listener ready、Envoy stats 和访问日志。
- 可回滚：切流策略在入口层完成，回滚时只把权重切回 ACK 内 `envoy-default-eg`。

# 3. 运行拓扑

推荐按下面这张逻辑图理解：

```text
ACK 集群内
┌──────────────────────────────────────────────────────┐
│ Kubernetes API                                        │
│ Gateway / HTTPRoute / Service / EndpointSlice / Secret│
└───────────────────────┬──────────────────────────────┘
                        v
                envoy-gateway 控制面
                        |
               xDS ResourceManager
                        |
          ┌─────────────┴─────────────┐
          v                           v
  envoy-default-eg              Delta ADS stream
  ACK 内主数据面                      |
                                      v
ACK 集群外                     cmd/proxy agent
┌─────────────────────────────────────┴────────────────┐
│ 本地 xDS server :18002                                │
│   -> Envoy bootstrap xds_cluster = 127.0.0.1:18002    │
│   -> Envoy listener 承接入口流量                       │
└──────────────────────────────────────────────────────┘
```

这条链路里，ACK 外 Envoy 不 watch Kubernetes，也不自己翻译 HTTPRoute。它只消费 ACK 内控制面已经生成好的 xDS。

# 4. 模块边界

| 模块 | 职责 |
| --- | --- |
| `cmd/proxy/main.go` | agent 入口，解析 `proxyAddr`、`irKey`、本地 xDS 端口、Envoy admin 地址，并启动 stats / xDS proxy / shutdown manager。 |
| `cmd/proxy/setup/xdsproxy.go` | 创建 `pkg/xds/proxy.XdsProxy` 并启动。 |
| `pkg/xds/proxy` | 核心中继：连接上游 xDS，创建本地 xDS server，把上游 Delta 响应写入本地 server。 |
| `pkg/xds/proxy/upstream` | 上游 Delta ADS client，负责连接、订阅、接收响应和发送 ACK。 |
| `pkg/proxy/envoy/stats` | 从 Envoy admin 拉 `/stats/prometheus`，过滤后在 `15008` 暴露。 |
| `pkg/proxy/envoy/shutdown` | Envoy drain / shutdown 工具链。当前 `cmd/proxy` 的调用顺序需要单独确认。 |
| `cmd/proxy/ci` | agent + Envoy 镜像形态：用 supervisor 同时拉起 agent 和 Envoy。 |
| `cmd/proxy/ci/conf/envoy-agent.yaml` | ACK 外 Envoy bootstrap，xDS 地址指向本机 `127.0.0.1:18002`。 |

不要把这里的 `envoy-proxy` 和 `api/config/v1alpha1/EnvoyProxy` 混在一起。后者更像上游 Envoy Gateway 留下的 API scaffolding，目前没有承载 ACK 外迁逻辑。

# 5. xDS 同步链路

`cmd/proxy` 启动后做三件事：

1. 读取启动参数：

```text
-port             本地 xDS server 端口，默认 18002
-proxyAddr        上游 xDS 地址，默认 envoy-gateway.envoy-gateway-system:18001
-irKey            资源隔离键，会写入 node.Cluster
-adminAddress     Envoy admin 地址，默认 127.0.0.1:15000
-xDSProxy         是否启动 xDS proxy，默认 true
-shutDownManager  是否启动 shutdown manager，默认 true
```

2. 创建上游连接和本地 server：

```text
NewXdsProxy(upstreamAddr, irKey, localPort)
  -> node.Id = xds-proxy-<uuid>-<timestamp>
  -> node.Cluster = irKey
  -> xds/server.NewServer(localPort)
  -> upstream.NewClient(upstreamAddr)
```

3. 通过 Delta ADS 拉取资源并落到本地：

```text
上游 DeltaDiscoveryResponse
  -> RemovedResources -> localServer.DeleteResources(irKey, type, names)
  -> Resources        -> localServer.PushDeltaResources(irKey, response)
  -> TypeUrl Listener -> 标记 proxy ready
```

upstream client 会订阅这些资源类型：

```text
Cluster
Endpoint
Listener
Route
ScopedRoute
VirtualHost
Secret
Runtime
ExtensionConfig
RateLimitConfig
```

收到每个上游响应后，agent 会先向上游发送 ACK，再把响应写入本地 xDS server。也就是说，ACK 外数据面是否配置同步成功，可以从上游 xDS 的 ACK/NACK、agent 日志、本地 xDS ready 和 Envoy admin 多处交叉确认。

# 6. Envoy 本地启动方式

`cmd/proxy/ci` 不是只跑 agent，而是把 agent 和 Envoy 放在同一个运行单元里：

```text
supervisord
  -> /usr/local/bin/agent
  -> /usr/local/bin/envoy -c /etc/envoy/envoy-agent.yaml
```

`envoy-agent.yaml` 里 Envoy 的 xDS cluster 指向本机：

```yaml
static_resources:
  clusters:
    - name: xds_cluster
      load_assignment:
        endpoints:
          - lb_endpoints:
              - endpoint:
                  address:
                    socket_address:
                      address: 127.0.0.1
                      port_value: 18002
```

因此 ACK 外 Envoy 的配置链路是：

```text
Envoy
  -> 127.0.0.1:18002
  -> cmd/proxy 本地 xDS server
  -> cmd/proxy upstream client
  -> ACK 内 envoy-gateway xDS
```

Envoy 对入口流量的处理仍然由 LDS/RDS/CDS/EDS 决定。外部只需要把实际流量送到 ACK 外 Envoy 暴露的监听端口。

# 7. 平滑迁移步骤

## 7.1 准备阶段

先确认三件事：

- `proxyAddr` 能从 ACK 外访问到 ACK 内 xDS server。生产默认 Service 是 `envoy-gateway:18000`，而 `cmd/proxy` 代码默认写的是 `18001`，实际部署前必须核对真实暴露端口。
- `irKey` 必须和要复用的 Gateway / Envoy resource isolation key 对上。主 HTTP/HTTPS 链路通常是 gateway 名称，例如 `default-eg`。
- ACK 外 Envoy 能访问 xDS 下发的 upstream 地址。如果 EDS 里仍是 ACK Pod IP，ACK 外网络必须能路由到这些地址；否则需要改为可达的 Service、SLB、ExternalName 或其他出口地址。

## 7.2 影子部署

先部署 ACK 外 `envoy-proxy`，但不接正式流量。

检查点：

- agent 能连接 `proxyAddr`。
- upstream Delta ADS 有 ACK，无持续 NACK。
- 本地 proxy 收到 Listener 后进入 ready。
- Envoy admin `15000` 能看到 listener / cluster。
- agent 暴露的 `15008/stats/prometheus` 有过滤后的 Envoy 指标。

## 7.3 小流量验证

从入口层切少量流量到 ACK 外 Envoy。入口层可以是 DNS、SLB、上游网关或其他流量调度系统，关键是不要在一开始改 Gateway / HTTPRoute 语义。

重点观察：

- 4xx / 5xx 是否和 ACK 内数据面对齐。
- cluster upstream 连接、超时、重试、熔断是否异常。
- Envoy access log 的 host、path、backend cluster 是否符合预期。
- xDS 是否持续 ACK，是否出现 Listener 或 Route NACK。
- 后端网络路径是否绕路，延迟是否明显变化。

## 7.4 扩大权重

小流量稳定后，按固定阶梯扩大 ACK 外权重：

```text
1% -> 5% -> 10% -> 25% -> 50% -> 100%
```

每一档至少确认：

- 配置版本没有漂移。
- 新旧数据面的请求量符合切流比例。
- 错误率、延迟、连接数、重试率没有突增。
- ACK 外 Envoy 实例扩容后仍能各自拉到同一套 xDS。

## 7.5 回滚

回滚应该优先在入口层完成：

```text
ACK 外 envoy-proxy 权重降到 0
ACK 内 envoy-default-eg 权重恢复到 100%
```

因为 Gateway / HTTPRoute 没有被拆成两套配置，回滚不需要回滚控制面对象。保留 ACK 外 proxy 一段时间用于排查，确认没有连接和请求后再下线。

# 8. 关键风险

## 8.1 后端地址可达性

这是 ACK 外迁最容易漏掉的问题。xDS 的配置一致不等于网络可达。ACK 外 Envoy 如果拿到的是 ACK Pod IP 或集群内 DNS，必须确认 ACK 外机器、容器或 VPC 能访问这些地址。

如果网络不可达，常见处理方向是：

- 让 Endpoint / Service 暴露为 ACK 外可达地址。
- 通过 SLB、NLB、专线、VPC 路由或 PrivateLink 打通。
- 为迁移目标单独准备可达的 backend，并通过路由或权重逐步切换。

## 8.2 `cmd/proxy` 的 shutdown manager 启动顺序

当前 `cmd/proxy/main.go` 在启动 xDS proxy 后立即 `wg.Wait()`，而 `SetupXdsProxy()` 内部又对同一个 `WaitGroup` `Add(1)`，这会导致后面的 `SetupShutDownManager()` 启动路径被阻塞。作为 ACK 外生产入口前，这里需要修正或用实际镜像验证 shutdown 行为。

另外，`SetupShutDownManager()` 里读取的是 `/etc/envoy/envoy.yaml`，而 `cmd/proxy/ci` 的 Envoy 配置文件是 `/etc/envoy/envoy-agent.yaml`。如果依赖 agent 内置 shutdown manager，也要确认配置路径一致。

## 8.3 `destinationPorts` 当前未接入

`cmd/proxy` 有 `destinationPorts` 参数，translator 里也有 passthrough 相关代码，但当前 `SetupXdsProxy()` 没有把这个参数继续传到资源生成逻辑。不要把它当作已经生效的透明转发能力。

## 8.4 上游 xDS 端口要实测

部署模板里 `envoy-gateway` Service 暴露的是 `18000`，但 `cmd/proxy` 默认 `proxyAddr` 是 `envoy-gateway.envoy-gateway-system:18001`。这可能来自某个环境的单独暴露方式，也可能是默认值落后。写迁移方案时必须以实际线上 Service、Ingress、端口映射为准。

# 9. 排查顺序

ACK 外 envoy-proxy 出问题时，按这个顺序查：

1. `proxyAddr` 连通性：ACK 外机器能否连到 ACK 内 xDS。
2. agent 日志：是否反复 `Reconnecting`，是否收到 `PUSH` / `DEL` / `READY`。
3. 上游 xDS admin / metrics：是否看到外部 node 连接，是否持续 ACK。
4. 本地 xDS server：资源是否按 `irKey` 落地。
5. Envoy admin `15000`：listener、route、cluster、endpoint 是否存在。
6. stats `15008`：请求量、错误率、upstream 连接和重试是否异常。
7. 后端网络：ACK 外 Envoy 到 upstream 地址是否真实可达。
8. 入口切流层：DNS / LB / 上游网关权重是否符合预期。

# 10. 面试表达

可以这样讲：

> 这个项目除了 ACK 内的 `envoy-gateway -> envoy-default-eg` 主链路，还有一个外置 `envoy-proxy` 形态。它不是重新实现控制面，而是在 ACK 外跑一个 agent，agent 从 ACK 内 xDS server 拉 Delta ADS，再把资源写入本机 xDS server，旁边的 Envoy 只连本机 `127.0.0.1:18002`。这样 ACK 内外两组数据面可以共享同一套 Gateway / HTTPRoute 配置。迁移时先部署 ACK 外 proxy 做影子验证，再通过入口 LB 或 DNS 分批切流；如果异常，直接把权重切回 ACK 内数据面，控制面对象不用回滚。关键风险是 upstream 地址对 ACK 外是否可达，以及 agent 的 shutdown 和端口配置要实测。

# 11. 推荐补充到总览图的关系

如果后续要改 `project-overview.md` 的总览图，建议在主 HTTP/HTTPS 链路旁边增加一条虚线：

```text
envoy-gateway 控制面
  -> xDS -> envoy-default-eg
  -> Delta ADS -> ACK 外 cmd/proxy agent -> 本地 Envoy
```

这条线的语义是“同一控制面，多组数据面”。它比单纯写 `cmd/proxy` 更能解释为什么这个模块和 ACK 外平滑迁移相关。
