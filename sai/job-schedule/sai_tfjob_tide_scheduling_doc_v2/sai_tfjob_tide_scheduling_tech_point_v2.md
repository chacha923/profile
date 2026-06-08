# 面试定位卡

| 项目 | 内容 |
|---|---|
| 技术点 | TFJob 潮汐调度：任务画像驱动的提交路由、待退资源利用、在线失败退避与离线回退 |
| 所属领域 | AI Infra / MLOps / Kubernetes 调度 / 训练平台资源治理 / 成本治理 |
| 适合挂钩项目 | SAI 训推平台、TFJob / CronJob 托管、ACK 多集群、多节点池、在线集群夜间退场、低优延迟任务治理 |
| 面试价值 | 证明你不是只会创建 TFJob，而是能把训练任务、在线低峰资源、待退按量实例、checkpoint、失败补偿和 ROI 结合起来思考。 |
| 安全定位 | 不是完整联邦调度，不是跨集群热迁移，不是已经做成全局智能调度器；更稳妥的说法是：SAI 从作业托管向训练资源治理演进的一阶段方案。 |
| 最容易被挑战 | 没有控制面改造怎么叫潮汐调度；周期任务怎么迁移；长任务能不能夜间跑在线集群；checkpoint 跨集群恢复是否可靠；ROI 是否真的成立；在线失败后如何退避。 |

# 三十秒回答

> 我们不会把它包装成完整的联邦调度。更现实的做法是：SAI 在任务提交阶段根据任务画像和资源窗口做 cluster routing。单批延迟任务可以在夜间直接提交到在线集群；周期任务不是迁移 CronJob 本身，而是每次周期实例触发时判断本次提交到在线集群还是离线集群。任务画像包括优先级、QoS、P95 耗时、checkpoint、可重试、是否允许延迟、是否允许在线集群运行。在线侧看夜间窗口、在线水位、待退节点状态和最近失败率。对于长时间任务，理论上可以依赖 NAS 共享 checkpoint 跨集群 stop-and-resume，但 ROI 未必好，默认只建议短耗时、低 QoS、可延迟、可重试任务上在线低峰资源。失败后要有退避，在线失败多次或 checkpoint / NAS 异常时回到离线集群排队。

# 为什么要重新收敛口径

之前的表述容易被面试官追问成“你们是不是做了完整跨集群调度”。现在需要把边界讲清楚：

| 问题 | 真实边界 | 推荐表达 |
|---|---|---|
| 没有控制面改造 | 没有全局调度器、没有联邦控制面、没有跨集群统一资源视图 | 这是提交阶段的 cluster routing，不是联邦调度 |
| 没有热迁移 | 运行中的 Pod / TFJob 不能原地搬到另一个集群 | 只能通过 checkpoint 做停止、重建、恢复 |
| 周期任务怎么迁移 | 不迁移 CronJob 本体，而是每个周期实例触发时重新选择目标集群 | 周期实例级别路由 |
| 长任务能不能上在线 | 技术上可能，工程上要谨慎 | 只在 checkpoint 可靠、恢复成本低、窗口足够时考虑 |
| ROI 是否成立 | 不一定成立 | 短任务高 ROI，长任务频繁恢复可能低 ROI |
| 在线失败怎么办 | 必须有退避、熔断、回退离线 | 失败不是简单重试，要按原因分类 |

# 原理模型

![TFJob 潮汐调度原理模型](./images/01_tfjob_tide_principle.png)

TFJob 潮汐调度不要理解成“晚上把任务丢到在线集群”。它至少包含四层：

| 层次 | 作用 | 面试表达 |
|---|---|---|
| 任务画像 | 判断任务是否适合使用低保障资源 | 周期/单批、耗时、P95、优先级、QoS、checkpoint、可重试、SLA |
| 资源池画像 | 判断资源是否适合承接训练任务 | 专用训练池、在线低峰池、待退按量实例池、弹性兜底池 |
| 提交路由 | 本次任务实例提交到哪个集群 | online / offline 二选一或多集群选择 |
| 失败补偿 | 在线失败后是否重试、退避、回退离线 | 避免在线集群反复失败造成抖动 |

# 无联邦控制面下的提交路由

![无联邦控制面下的 TFJob 提交路由](./images/06_tfjob_cluster_routing_no_federation.png)

没有联邦控制面时，不能说“跨集群调度器统一调度 TFJob”。更准确的路径是：

```text
任务触发
  -> 读取任务画像
  -> 读取在线窗口和集群状态
  -> 判断本次实例是否允许 online
  -> 选择 kubeconfig / cluster / namespace / nodeSelector / toleration
  -> 提交 TFJob
```

## 单批延迟任务

单批延迟任务最适合做第一阶段落地。

| 判断项 | 说明 |
|---|---|
| 是否延迟任务 | 不要求立即完成，可以等待夜间窗口 |
| 是否低 QoS | 失败、延迟、重试对业务影响较低 |
| 是否运行快 | P95 耗时小于剩余窗口减去 buffer |
| 是否可重试 | 节点被释放或在线集群异常时可以重跑 |
| 是否允许在线集群 | 任务画像显式打开 allowOnlineCluster |

提交逻辑可以很简单：

```text
if inNightWindow
  and task.allowOnlineCluster
  and task.qos == low
  and task.retryable
  and task.p95Runtime < remainingWindow - buffer
  and onlineClusterHealthy
then
  submit to online cluster
else
  submit to offline cluster
```

## 周期任务

周期任务不要说“夜间把任务迁移到在线集群”。更准确是：

> 每次周期实例触发时，做一次目标集群选择。

例如每天 01:00 的训练任务：

```text
01:00 触发本轮周期实例
  -> 当前处于夜间窗口
  -> 在线集群水位安全
  -> 任务画像允许 online
  -> 本轮 TFJob 提交到 online cluster

第二天 01:00 再触发
  -> 再重新判断
  -> 不保证每轮都去 online
```

这样不需要改 Kubernetes 调度器，也不需要联邦机制。SAI 或 DAG 触发器只需要在创建 TFJob 前选择目标集群。

## 配置示例

```yaml
taskProfile:
  jobType: periodic
  priority: P2
  qos: low
  expectedRuntimeMinutes: 30
  p95RuntimeMinutes: 45
  maxRuntimeMinutes: 60
  checkpointEnabled: true
  retryable: true
  delayTolerant: true
  allowOnlineCluster: true
  allowRetiringNode: true
  onlineWindow: "00:00-08:00"
  fallbackCluster: offline
  maxOnlineFailures: 3
```

# 待退资源机会型调度机制

![待退资源机会型调度机制](./images/02_tfjob_tide_mechanism.png)

在线集群夜间退场时，按量实例理想情况下应该释放。但现实中可能因为云厂商退机 API 限速、节点排水、伸缩组队列、Pod 驱逐保护等原因，导致一批节点处于“待退未退”状态。

这批节点如果完全空置是浪费；如果继续承载核心在线服务又会干扰退场。因此可以把它们隔离成低保障资源池：

```yaml
apiVersion: v1
kind: Node
metadata:
  labels:
    tide.soulapp/pool: retiring
spec:
  taints:
    - key: tide.soulapp/retiring
      value: "true"
      effect: NoSchedule
```

低优任务显式容忍：

```yaml
spec:
  tolerations:
    - key: tide.soulapp/retiring
      operator: Equal
      value: "true"
      effect: NoSchedule
  nodeSelector:
    tide.soulapp/pool: retiring
```

关键边界：

| 边界 | 说明 |
|---|---|
| taint 不控制退机顺序 | 污点只控制 Kubernetes 调度，不控制阿里云释放顺序 |
| 退机优先级高于任务运行 | 不能为了低优任务延迟节点最终释放 |
| 只承接低保障任务 | QoS 低、短耗时、可延迟、可重试 |
| 需要 maxRuntime | 避免任务拖住资源窗口 |
| 需要失败补偿 | 节点被释放时任务进入重试或回退离线 |

# 长任务是否能夜间转移

你的直觉是对的：如果 NAS 跨集群可通，checkpoint 保存到共享路径，理论上可以在另一个集群恢复继续跑。但这件事必须谨慎表达。

## 技术上可行的路径

```text
离线集群运行中
  -> 到达夜间窗口或触发策略
  -> 等待最近 checkpoint 或主动保存 checkpoint
  -> 停止离线集群 TFJob
  -> 在线集群重建 TFJob
  -> 从 NAS checkpoint 恢复
  -> 夜间窗口结束或在线水位升高
  -> 再保存 checkpoint
  -> 回到离线集群继续
```

这不是热迁移，而是 stop-and-resume。

## 为什么不建议作为主卖点

| 风险 | 说明 |
|---|---|
| 恢复成本 | 加载模型、optimizer state、数据状态可能很慢 |
| checkpoint IO | NAS 可能成为瓶颈，尤其是大模型或大状态训练 |
| 窗口不足 | 夜间 6-8 小时窗口可能覆盖不了长任务 |
| 频繁中断 | 每天停止、恢复、再停止，可能把收益吃掉 |
| 训练一致性 | 数据读取 offset、随机种子、optimizer state 恢复不完整会影响结果 |
| 多机多卡复杂 | Worker 组重建、gang 调度、局部失败都会放大成本 |
| 在线稳定性 | 在线水位上升时必须让路，任务随时可能被中断 |

## 推荐判断

| 任务类型 | 是否建议夜间转移 | 原因 |
|---|---:|---|
| 10-60 分钟低优延迟任务 | 建议 | 容易在窗口内完成，失败成本低 |
| 小时级周期增量任务 | 谨慎建议 | 要看 P95、checkpoint、窗口和重试成本 |
| 追几个月数据的长任务 | 默认不建议 | 频繁 stop-and-resume，ROI 未必成立 |
| 多机多卡强同步训练 | 不建议 | 单节点失败可能导致整批失败 |
| 支持阶段切分的长任务 | 可以改造后尝试 | 拆成分片任务或阶段任务，比整体迁移更稳 |

更稳妥的面试表达：

> 长任务理论上可以依赖共享 NAS checkpoint 跨集群恢复，但我不会默认把它作为潮汐调度的主要对象。因为它不是热迁移，而是停止、重建、恢复，存在恢复耗时、checkpoint IO、窗口不足和失败重试成本。更现实的是先让低 QoS、短耗时、可延迟、可重试任务使用在线低峰资源；长任务如果要做，最好先拆成阶段化或分片化任务。

# ROI 判断

潮汐调度不是“能跑就有收益”。要看收益是否覆盖额外成本和稳定性风险。

```text
预期收益 = 在线低峰可用资源时长 * 单位资源成本
         - checkpoint / 恢复成本
         - 失败重试成本
         - 调度等待成本
         - 对退机时长的影响
         - 运维复杂度成本
```

## 高 ROI 场景

| 场景 | 原因 |
|---|---|
| 退机 API 限速导致待退实例空置 | 资源本来短时间无法释放，二次利用收益高 |
| 低 QoS 延迟任务堆积 | 任务对失败和延迟不敏感 |
| 短耗时任务 | 更容易在夜间窗口内完成 |
| 可重试 / 幂等任务 | 失败补偿成本低 |
| 周期实例每次新提交 | 只要提交前选择目标集群，不需要迁移运行中任务 |

## 低 ROI 场景

| 场景 | 原因 |
|---|---|
| 长时间大训练任务 | 频繁 checkpoint 和恢复成本高 |
| 多机多卡同步训练 | 单点失败放大为整体失败 |
| 强 SLA 产出任务 | 在线失败会影响模型产出或业务链路 |
| 在线集群窗口不稳定 | 失败概率高，重试成本高 |
| NAS IO 压力大 | checkpoint 可能拖慢训练或影响其他任务 |

面试不要乱报节省比例。可以说看三类指标：

| 指标 | 说明 |
|---|---|
| 资源收益 | 待退实例利用时长、在线低峰资源利用率、低优任务等待时间下降 |
| 稳定性成本 | 在线失败率、重试次数、抢占次数、checkpoint 恢复失败次数 |
| 退场影响 | 按量实例退场完成时长是否变长、退机队列是否被任务拖慢 |

# 在线失败退避与离线回退

![在线集群失败退避与离线回退机制](./images/07_tfjob_online_backoff_fallback.png)

没有退避机制，在线集群失败后反复投递，会导致调度抖动。建议设计成三层：任务级退避、集群级熔断、离线队列回退。

## 任务级退避

```yaml
onlineSchedulingStatus:
  onlineAttempts: 3
  onlineFailures: 2
  lastFailureReason: NodeReclaimed
  lastFailureTime: "2026-05-20T02:30:00"
  fallbackCluster: offline
  fallbackCooldown: 24h
  checkpointPath: "nas://train-checkpoints/job-a/latest"
```

规则示例：

| 场景 | 处理方式 |
|---|---|
| 在线失败 1 次 | 短退避，例如 10 分钟后重新判断 |
| 在线失败 2 次 | 延长退避，例如 30 分钟，并重新判断窗口、水位、节点状态 |
| 在线失败 3 次 | 当日不再 online，回到离线集群排队 |
| checkpoint 恢复失败 | 直接回离线，避免在线反复失败 |
| NAS 访问异常 | 直接回离线，同时触发集群级熔断判断 |
| 训练代码异常 | 不应该换集群重试，应该按业务失败处理 |

## 失败原因分类

| 失败原因 | 是否应继续尝试在线 | 说明 |
|---|---:|---|
| NodeReclaimed | 可以有限重试 | 节点被释放，属于在线低保障资源风险 |
| ResourceInsufficient | 可以退避后重试 | 要重新检查在线水位和剩余窗口 |
| FailedScheduling | 视原因而定 | 可能是 taint / nodeSelector / quota 配置问题 |
| ImagePullBackOff | 不应盲目重试 | 要修镜像、网络、凭证 |
| NasMountFailed | 不建议在线重试 | 可能是跨集群存储链路问题 |
| CheckpointRestoreFailed | 不建议在线重试 | 可能需要人工或回离线恢复 |
| CodeError | 不应调度重试 | 业务代码失败，不是资源问题 |

## 集群级熔断

```text
过去 30 分钟：
  online TFJob 启动失败率 > 30%
  OR NodeReclaimed 导致失败次数 > 10
  OR NAS / checkpoint 相关失败次数 > 3
  OR 在线水位超过安全阈值
then
  熔断 online 1 小时
  新任务全部回 offline
```

## 回退离线条件

```text
满足任一条件：
  onlineFailures >= maxOnlineFailures
  checkpoint 恢复失败
  NAS 访问异常
  当前时间接近白天窗口
  在线集群水位超过阈值
  任务运行时间超过 maxRuntime
  节点回收率过高
then
  fallback to offline queue
  设置 fallbackCooldown，避免当天反复切回 online
```

# 典型业务场景

![夜间在线集群退场受限场景](./images/03_tfjob_tide_scenario.png)

| 场景 | 推荐处理 | 不建议做法 |
|---|---|---|
| 单批低优延迟任务夜间提交 | 提交前路由到 online 或 retiring pool | 白天也强行占用在线集群 |
| 周期任务夜间实例 | 每次实例触发时判断目标集群 | 迁移 CronJob 本体或宣称热迁移 |
| 待退实例 API 限速堆积 | 打 taint 隔离为低保障资源池 | 让普通服务或高优训练误调度上去 |
| 长任务追几个月数据 | 默认离线跑；如要潮汐，先阶段化 / 分片化 | 每天整批停止再恢复，不算 ROI |
| 在线集群失败率升高 | 任务级退避 + 集群级熔断 + 回离线 | 在线反复重试导致抖动 |
| NAS 跨集群可通 | 作为 checkpoint 恢复基础 | 直接假设所有任务都能无成本恢复 |

# 排障路径

![潮汐调度排障路径](./images/04_tfjob_tide_troubleshooting.png)

| 问题 | 首先怀疑 | 排查点 | 处理 |
|---|---|---|---|
| 任务没有去 online | 画像或窗口不满足 | allowOnlineCluster、QoS、P95、夜间窗口、熔断状态 | 修正画像或接受回 offline |
| 任务调度失败 | taint / toleration / nodeSelector 不匹配 | Pod Event、Node taints、Namespace quota | 修正注入逻辑 |
| 在线任务频繁失败 | 节点过快释放或任务不适合 | NodeReclaimed、P95、checkpoint、在线水位 | 降低准入、缩短 maxRuntime、回 offline |
| checkpoint 恢复失败 | 存储或训练框架状态问题 | NAS mount、checkpoint path、训练日志 | 回 offline，停止 online 重试 |
| 退机被拖慢 | 低优任务阻塞 final drain | 退机队列、Pod deletion、PDB、grace period | 退机优先，强制中断低优任务 |
| ROI 不明显 | 任务太长或恢复成本高 | 运行时长、恢复耗时、失败率、资源利用时长 | 只保留短任务，长任务拆分 |

## 常用验证命令

```bash
kubectl get node -L tide.soulapp/pool
kubectl describe node <node-name>
```

看节点是否被标记为 retiring pool，是否有 `tide.soulapp/retiring=true:NoSchedule`，是否已进入 `SchedulingDisabled` 或 drain 状态。

```bash
kubectl describe pod <pod-name>
```

看 `FailedScheduling`、`taint not tolerated`、`NodeAffinity`、`Evicted`、`Preempted`、`ImagePullBackOff`、`NasMountFailed` 等事件。

```bash
kubectl get tfjob -A
kubectl describe tfjob <tfjob-name> -n <namespace>
```

看 Worker / PS 状态、失败副本、重试次数、失败是否集中在 online / retiring pool。

# 和 SAI 项目的安全连接

![和 SAI 项目的安全连接与演进路线](./images/05_tfjob_tide_project_connection.png)

## 了解型说法

> SAI 已经承接了 TFJob / CronJob 的创建、状态查询、日志事件和运行治理入口，所以后续可以把任务从普通 YAML 抽象成可治理的训练任务。潮汐调度不是从一开始就做复杂调度器，而是先做任务画像、提交路由和失败回退。

## 实践型说法

> 在没有联邦控制面改造的前提下，第一阶段可以做得很轻：单批延迟任务提交时直接选择 online 或 offline；周期任务每次实例触发时重新判断目标集群；在线失败后退避，达到阈值回离线集群排队。这个方案和现有 SAI 控制面更容易连接。

## 演进型说法

> 后续如果要做深，可以补齐资源池画像、任务画像自动更新、低峰预测、在线水位感知、退机队列感知、checkpoint 感知、失败原因分类、成本归因和调度审计。再往后才是更复杂的多集群统一调度或联邦能力。

## 不能说的话

```text
不能说：我们已经做了完整联邦调度。
不能说：运行中的 TFJob 可以热迁移到在线集群。
不能说：NAS 跨集群可通就意味着所有任务都能低成本迁移。
不能说：长任务夜间转移一定省钱。
不能说：打污点能控制阿里云退机顺序。
不能说：在线失败后无限重试就行。
```

# 面试追问树

```text
Q1：你们没有控制面改造，怎么做 TFJob 潮汐？
  └── A：不是联邦调度，而是提交前 cluster routing。
      └── Q2：周期任务怎么夜间迁移？
          └── A：不迁移 CronJob，每次周期实例触发时选择目标集群。
              └── Q3：运行中的 TFJob 能迁移吗？
                  └── A：不能热迁移，只能 checkpoint stop-and-resume。
                      └── Q4：长任务追几个月数据能不能用 online？
                          └── A：理论上能，默认不建议，除非 checkpoint 可靠且 ROI 成立。
                              └── Q5：ROI 怎么算？
                                  └── A：资源节省要扣掉恢复、失败、checkpoint、退场影响和运维成本。
                                      └── Q6：在线失败怎么办？
                                          └── A：任务级退避、集群级熔断、回离线队列。
                                              └── Q7：怎么保证不影响在线服务？
                                                  └── A：水位保护、taint 隔离、低 QoS 准入、退机优先。
```

# 高频 Q&A

## Q：没有联邦机制，怎么叫潮汐调度？

回答：

> 我不会把它叫完整联邦调度。更准确是潮汐调度的一阶段：在任务提交阶段，根据任务画像、时间窗口和在线集群水位做目标集群路由。它解决的是“本次任务实例投到哪里”，不是“全局统一调度所有集群资源”。

## Q：周期任务怎么在夜间移到在线集群？

回答：

> 周期任务不需要迁移 CronJob 本身。每次周期实例触发时，SAI 或 DAG 触发器根据当前是否夜间、在线水位是否安全、任务是否允许 online、P95 是否小于剩余窗口来决定本轮实例提交到 online 还是 offline。

## Q：运行中的 TFJob 能不能从离线集群迁移到在线集群？

回答：

> 不能热迁移。真实做法只能是 checkpoint-based stop-and-resume：先停止或等待 checkpoint，再在另一个集群重建 TFJob，从共享 NAS 的 checkpoint 恢复。

## Q：跑几个月数据的长任务能不能夜间转移？

回答：

> 理论上可以，但默认不建议。长任务每天反复停止、恢复、再停止，checkpoint IO 和恢复耗时可能吃掉收益，而且在线窗口不稳定。更合理的是把长任务拆成阶段任务或分片任务，让可重试的小单元进入 online。

## Q：NAS 跨集群通了，为什么还不推荐长任务？

回答：

> NAS 通只是解决 checkpoint 可见性，不等于恢复成本为零。还要看 checkpoint 大小、恢复耗时、训练状态是否完整、数据读取 offset 是否正确、在线窗口是否够、失败概率是否可接受。

## Q：在线集群失败几次回离线？

回答：

> 可以按任务画像配置，比如失败 1 次短退避，失败 2 次延长退避并重新判断水位，失败 3 次当日回离线排队。checkpoint 恢复失败、NAS 异常、代码异常这类不应该在线反复重试，应该直接回离线或失败终止。

## Q：怎么避免在线集群反复失败造成抖动？

回答：

> 做任务级退避和集群级熔断。任务级记录 onlineAttempts、onlineFailures、lastFailureReason；集群级看最近 30 分钟启动失败率、节点回收失败、NAS 异常、在线水位。超过阈值就暂停 online 投递。

## Q：ROI 怎么判断？

回答：

> 不能只看用了多少空闲机器。要看在线低峰利用时长减去 checkpoint、恢复、失败重试、退场延迟和运维复杂度成本。短任务、低 QoS、可重试任务 ROI 高；长任务、多机多卡、强 SLA 任务 ROI 通常低。

## Q：这个方案和 SAI 当前能力怎么连接？

回答：

> SAI 已经有 TFJob / CronJob 托管、状态、日志、事件和运行治理入口。第一阶段可以在创建任务前做目标集群选择，注入 nodeSelector、toleration、priority、deadline；运行后记录失败原因和重试状态。后续再演进任务画像、资源池画像、低峰预测和成本归因。

# 三档背诵版

## 三十秒版

> 这个能力我不会说成完整联邦调度。没有控制面改造时，最现实的是做提交前 cluster routing：单批延迟任务夜间直接投 online，周期任务每次实例触发时判断本轮投 online 还是 offline。判断依据是任务画像和资源窗口，包括 QoS、优先级、P95 耗时、checkpoint、retryable、在线水位、待退节点状态。长任务理论上能通过 NAS checkpoint 跨集群恢复，但不是热迁移，ROI 不一定好，所以默认只建议短耗时、低 QoS、可延迟、可重试任务。在线失败后要退避，失败多次回离线排队。

## 三分钟版

> 我会把 TFJob 潮汐调度收敛成三个阶段。第一阶段是提交路由，不做联邦。SAI 或 DAG 触发器在创建 TFJob 前，根据任务画像和当前在线集群状态选择目标集群。单批延迟任务可以夜间投 online；周期任务不是迁移 CronJob，而是每个周期实例触发时重新判断。
>
> 第二阶段是低保障资源利用。夜间在线集群退场时，按量实例可能因为云 API 限速处于待退未退状态。运维可以给这批节点打 retiring taint，平台只给低优、短耗时、可延迟、可重试任务注入 toleration。这批资源不承诺稳定，退机优先级高于任务运行。
>
> 第三阶段是失败退避。在线失败不能无限重试，要按失败原因分类。节点回收或资源不足可以有限退避；checkpoint、NAS、镜像、代码错误不能盲目重试。失败达到阈值就回离线队列，并设置冷却时间，避免反复切换造成调度抖动。

## 五分钟版

> 如果面试官问 TFJob 怎么做潮汐调度，我会先澄清边界：我们没有做联邦控制面，也没有把运行中的 TFJob 热迁移到另一个集群。因此第一阶段不是全局调度器，而是基于任务画像的提交路由。
>
> 对单批延迟任务，夜间可以直接把目标集群指向在线集群。对周期任务，每次周期实例触发时判断一次：是否在夜间窗口，在线水位是否安全，任务是否允许 online，P95 耗时是否小于剩余窗口，最近 online 是否熔断。如果满足条件，本轮实例提交 online，否则回 offline。
>
> 对于在线集群夜间退场受限的场景，按量实例可能因为阿里云退机 API 限速短时间堆积。我们可以把这批节点通过 taint / toleration 隔离成 retiring pool，只允许低 QoS、短耗时、可延迟、可重试任务调度上去。这里要强调，taint 只控制 Kubernetes 调度，不控制云厂商退机顺序，退机优先级始终高于任务运行。
>
> 长任务要谨慎。虽然 NAS 跨集群可通，checkpoint 可以保存到共享路径，在另一个集群恢复，但这不是热迁移，而是 stop-and-resume。长任务如果每天反复中断、恢复，checkpoint IO、恢复耗时、失败概率和在线窗口不足可能让 ROI 很差。更合理的是先支持短任务，长任务要做也应拆成阶段化或分片化任务。
>
> 最后必须有退避机制。任务级记录 onlineAttempts、onlineFailures、lastFailureReason，失败 1 次短退避，失败 2 次延长退避，失败 3 次回 offline。集群级看最近失败率、节点回收失败、NAS 异常、在线水位，超过阈值熔断 online。这样才能避免潮汐调度变成反复失败的抖动系统。

# 图示清单

| 图片 | 对应章节 | 目的 |
|---|---|---|
| `01_tfjob_tide_principle.png` | 原理模型 | 解释任务画像、资源池画像、SAI 策略层和 K8s 调度隔离 |
| `02_tfjob_tide_mechanism.png` | 待退资源机会型调度机制 | 解释准入、注入、中断和补偿流程 |
| `03_tfjob_tide_scenario.png` | 典型业务场景 | 解释夜间在线集群退场、退机 API 限速和低优任务填充 |
| `04_tfjob_tide_troubleshooting.png` | 排障路径 | 解释任务堆积、退机阻塞、调度失败、在线水位风险 |
| `05_tfjob_tide_project_connection.png` | 和 SAI 项目的安全连接 | 说明它是 SAI 后续演进，而不是夸大成完整调度器 |
| `06_tfjob_cluster_routing_no_federation.png` | 无联邦提交路由 | 解释没有控制面改造时如何做实例级 cluster routing |
| `07_tfjob_online_backoff_fallback.png` | 在线失败退避与离线回退 | 解释失败分类、任务级退避、集群级熔断、离线回退 |

# 面试前检查清单

- [ ] 我不会把这个能力说成完整联邦调度。
- [ ] 我能解释提交路由和 Kubernetes 调度器的区别。
- [ ] 我能解释周期任务是实例级路由，不是迁移 CronJob。
- [ ] 我能解释运行中的 TFJob 不能热迁移，只能 checkpoint stop-and-resume。
- [ ] 我能解释 NAS 跨集群通只是必要条件，不代表长任务迁移 ROI 成立。
- [ ] 我能解释为什么短任务、低 QoS、可延迟、可重试任务更适合在线低峰资源。
- [ ] 我能解释待退实例是机会资源，不是稳定资源。
- [ ] 我能解释 taint 只控制调度，不控制阿里云退机顺序。
- [ ] 我能解释在线失败退避、集群熔断、离线回退。
- [ ] 我能解释 ROI 要同时看资源收益、失败成本、checkpoint 成本和退机影响。
