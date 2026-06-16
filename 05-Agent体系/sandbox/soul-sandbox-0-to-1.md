# 从 0 到 1 建设 Soul Sandbox 体系（落地设计 + 面试问答）

这篇是 [[sandbox]] 的实战配套：sandbox.md 讲清楚了「sandbox 是什么、隔离怎么选、冷启动怎么消除」，本文回答一个具体场景题——**「Soul 现在有 moss-compose 和 soulclaw 云上 Hermes 容器，怎么从 0 建一套 Sandbox 体系？」**。它同时是我准备的：① 反问面试官的问题清单；② 如果面试官把这题抛给我，我怎么答。

边界先讲清：Agent Sandbox 强隔离运行时（gVisor / Kata / Firecracker）我没有生产落地，是理论对标；但「从 0 搭一套平台体系」这件事——控制面、生命周期、镜像分发、状态同步、资源治理、可观测、灰度——我在 SAE / SAI / Bigeyes 真做过。所以这篇是「真实平台建设经验 + sandbox 问题域对标」的组合，不是「我搭过 sandbox」。

# 先盘清楚：Soul 现在有什么，差什么才算 Sandbox

## 现状（三块现成资产）

+ moss-compose：基于 Coze 的 Agent / Workflow 编排平台，解决「Agent 怎么编排、调哪些工具、跑什么流程」。
+ soulclaw（龙虾）：Soul 版 OpenClaw，内部 Agent / Coding Agent 平台，是「Agent 大脑 + 入口」。
+ Hermes 云上容器：soulclaw 跑东西的容器执行环境，是目前最接近「执行底座」的一块。

一句话定位：moss-compose / soulclaw 是「大脑和编排」，Hermes 是「现在的手」。但这只手还是普通容器，不是 sandbox。

## Gap：普通容器 ≠ Sandbox

把 sandbox.md 里 sandbox 要解决的问题域，对照 Soul 现状，缺口很清楚：

+ 隔离不够强：Hermes 若是普通容器，共享宿主内核，跑 Agent 生成的不可信代码（任意 Python/shell）逃逸即宿主沦陷。sandbox 要的是 gVisor / Kata / microVM 级别的强隔离。
+ 没有「秒级、高频、用完即弃」的生命周期：普通容器/Pod 调度是分钟级、为长任务设计；Agent 执行是秒级、极高频、突发，需要 Pool 预热 / Snapshot / 轻量调度。
+ 没有会话级状态语义：Agent 多轮交互要保留上一轮文件和进程（Sleep/Resume），又要能一次性销毁防数据残留——普通容器没这套抽象。
+ 多租户治理薄：缺租户级 Quota、Fair Share、Noisy Neighbor 抑制、死循环/OOM 快速回收、按用量计费。
+ 安全边界没体系化：出站网络白名单、禁特权、seccomp/能力裁剪、密钥注入隔离、跨租户复用防护。
+ 可观测/可解释不足：缺 sandbox 生命周期 Event（创建/启动/执行/挂起/销毁/异常）的状态机和失败原因回写。

结论：Soul 不缺「Agent 大脑」和「能跑容器」，缺的是把执行底座升级成「强隔离 + 秒级 + 受控多租户 + 会话语义 + 可观测」的 Sandbox 控制面。这恰好是平台工程问题，不是模型问题。

# 目标：什么样才算「一套 Sandbox 体系」

不堆功能，按能力域定义「做完了」的样子：

+ 一层统一抽象：Agent 只看到 `CreateSandbox / Exec / Snapshot / Sleep / Resume / Destroy` 这组会话+执行语义，看不到底层 microVM/容器/网络/镜像细节。
+ 控制面高可用 + 扛涌浪：分布式管控中心高可用，接口幂等、限流、背压、削峰排队，瞬时高并发创建不雪崩——对应 JD 的「高可用分布式管控中心 + 海量任务瞬间涌浪」。
+ 可插拔的隔离后端：同一套控制面下，能按负载切 容器（受信轻量）/ gVisor（要密度+GPU）/ Kata 或 Firecracker（不可信代码强隔离），而不是绑死一种。
+ 秒级就绪：冷启动分层优化（镜像预热 + Lazy Pull → Pool → Snapshot），把启动从用户路径上摘掉。
+ 受控多租户：Quota / Fair Share / 资源上限 / 快速回收 / 计费。
+ 会话状态语义：有状态会话 Sleep/Resume，无状态执行用完即弃。
+ 安全默认收紧：出站白名单、禁特权、syscall 裁剪、密钥隔离、防跨租户复用。
+ 可观测可解释：全生命周期 Event 状态机 + 失败原因回写。

# 0 → 1 分阶段建设路线（重点）

不要一上来追求 Firecracker 全家桶。按「先跑通 → 再隔离 → 再提速 → 再治理 → 再自治」推进，每阶段都能独立交付价值、可灰度可回退。

![Soul Sandbox 0→1 分阶段建设路线](diagrams/06_soul_sandbox_0to1_roadmap.png)

## P0：复用现状先跑通闭环（不引入新隔离，但安全不能裸奔）

+ 做什么：在 Hermes 容器之上，先抽出统一的 Sandbox 控制面 API（Create/Exec/Destroy），让 moss-compose / soulclaw 通过这一层调用，而不是各自直连容器。
+ 价值：先把「编排 → 执行 → 回收」的链路和接口契约定下来，隔离后端先用现有普通容器顶着。
+ **安全红线（关键，别把命门留到 P1）**：P0 隔离弱，所以必须用「准入 + 网络」兜底——① 出站 **默认拒绝**，只放白名单；② P0 **只接受信代码 / 受控工具调用，不可信的任意代码 gating 到 P1 强隔离 ready 之前不放行**；③ 禁特权、基础 seccomp。安全不是一个能「后面再补」的阶段，弱隔离阶段尤其要靠网络和准入把风险压住。
+ **控制面从第一天就按高并发设计**：接口幂等（重复 Create 不产生幽灵 sandbox）、限流、背压，别等 P3 才想吞吐——契约定下来后再改语义代价很大。
+ 复用我的经验：SAE 控制面拆分（入口/元数据/事件同步/巡检补偿）和把底层动作收敛成语义化 API 的做法，直接平移。
+ 出口标准：Agent 能通过统一 API 创建执行环境、跑代码、拿结果、销毁，链路可观测；不可信代码在 P0 被拒绝或强制走受限模式，出站默认拒绝。

## P1：补强隔离（解决「不可信代码」这条命门）

+ 做什么：把隔离后端做成可插拔的 RuntimeClass。先在 K8s 体系下接 gVisor / Kata（复用生态、改动小）；对「跑 Agent 生成的任意代码」这类高危场景，评估 Firecracker microVM 路线。
+ 选型判断（沿用 sandbox.md）：不可信任意代码 + 高频多租户 → 倾向 Firecracker；要 GPU 跑模型 → gVisor；已有重 K8s 体系要标准接入 → Kata；纯受信轻量 → 容器/WASM。
+ 复用我的经验：SAI 的多云 Runtime 抽象、按资源模式（独占/共享/抢占）切后端的思路，可平移到「按负载切隔离后端」。
+ 出口标准：高危执行落在强隔离后端，隔离方案可灰度、可回退到普通容器。

## P2：冷启动提速（让「秒级就绪」成立）

+ 做什么：分层上优化——镜像预热 + Lazy Pull（nydus/stargz）解决拉取，Sandbox Pool 摘掉用户路径冷启动，Snapshot/Restore 跳过引导（microVM 路线）。按场景组合，不全上。
+ 复用我的经验：SAE 的镜像构建分发链路（Tekton/buildx/containerd/Harbor）真做过，加速方案接入设计见 [[image-distribution-fast-start]]。
+ 出口标准：常用运行环境冷启动达到目标 SLO（先定百毫秒还是秒级，见反问清单）。

## P3：多租户治理 + 安全 + 控制面硬化 + 可观测（让它「敢上生产」）

+ 做什么：租户 Quota / Fair Share / 单 sandbox 资源与时长上限 / 死循环 OOM 超时快速回收 / 按用量计费；安全默认收紧（出站白名单、禁特权、seccomp、密钥隔离）；全生命周期 Event 状态机 + 失败原因回写。
+ **控制面容量硬化**：管控中心做高可用，瞬时涌浪用排队削峰 + 背压保护后端，避免「Pod/microVM 调度链路被高频创建打爆」；这点和我做控制面 Reconcile 性能优化同类。
+ **状态对账与资源不泄漏（sandbox 特有的硬骨头）**：sandbox 海量、秒级、易失，控制面记录极易和实际 drift——必须有对账回收兜底：定期核对「控制面认为存在 vs 节点实际存在」，清掉幽灵 sandbox，确保 Destroy = 真释放（IP / GPU / 磁盘 / microVM / 网络命名空间都回收，不残留）。这是普通 Pod 巡检补偿的加强版，难度高一个量级。
+ 复用我的经验：Bigeyes 的 Runtime Event 状态机直接对应 sandbox 生命周期治理；SAE 把 Reconcile 状态做成可解释回写，对应「启动失败/配额不足/被回收」翻译成用户可懂信息；SAE 的巡检补偿对应对账回收。
+ 出口标准：单租户跑死循环/吃满资源不拖垮别人，闲置能挂起省成本，异常可观测可解释，无资源泄漏和幽灵 sandbox，控制面在峰值创建下不雪崩。

## P4：会话语义 + 自治演进（往前留口子）

+ 做什么：有状态会话 Sleep/Resume，无状态用完即弃；再往后让 Agent 能自主编排「创建→执行→快照→唤醒→销毁」，但动作受控（呼应 [[cicd-ai-native]] 的受控自治：权限/审计/边界不丢）。
+ **自治的新攻击面**：Agent 能自主创建/销毁 sandbox，意味着 prompt 注入后可能被诱导滥用创建权（刷爆配额、当跳板、绕审计）。所以自治动作必须挂在租户配额、速率限制、审计和权限边界之内，Agent 的「自主」永远在控制面的硬约束之下。
+ 出口标准：多轮 Agent 会话能保留环境又防跨租户残留；自治执行在受控边界内，且对滥用有配额和审计兜底。

# 复用 Soul 现有资产的映射

+ moss-compose / soulclaw：保留作「编排 + 大脑 + 入口」，下沉到统一 Sandbox API，不再各自直连容器。
+ Hermes 容器：作为 P0 的执行底座先顶着，P1 起降级成「隔离后端之一（受信/轻量场景）」，高危场景切强隔离后端。
+ SAE 镜像链路（Tekton/Harbor/containerd）：复用为 sandbox 镜像的构建分发底座，P2 在此接 Lazy Pull/预热。
+ K8s 多集群底座：作 sandbox 调度与资源池底座，强隔离后端以 RuntimeClass 接入。
+ Bigeyes Event 体系：复用为 sandbox 生命周期 Event 状态机。

# 我能直接平移的真实经验（面试锚点）

+ 控制面建设：SAE 把分散的云原生能力收敛成统一语义化 API + 模块拆分（入口/元数据/事件同步/巡检补偿）。
+ 多云/多形态 Runtime 抽象：SAI 屏蔽底层差异、按资源模式切后端、状态同步与补偿。
+ 镜像构建分发：SAE 的 Tekton/buildx/containerd/Harbor 真实链路。
+ 生命周期 Event 状态机 + 可解释回写：Bigeyes + SAE。
+ 受控开放：把能力做成带权限/审计/边界的受控接口（cicd-ai-native 的 MCP Skills）。

一句话：sandbox 控制面要解决的工程问题——抽象、调度、生命周期、镜像、状态、治理、可观测、灰度——我在别的 Runtime 平台上逐一做过，只是对象从「业务 Pod / 训练任务 / 告警事件」换成「sandbox」。隔离运行时本身是我要补的对标知识。

# 选型：adopt OpenKruise Agents vs 从 0 自研

边界先讲清：**Kruise 工作负载（Advanced StatefulSet / Advanced DaemonSet / CloneSet）Soul 生产在用，这是相邻真实经验；但 KruiseAgents（agents.kruise.io 子项目）我没生产跑过，是选型对标。** 版本成熟度、性能数字不做断言。

## 为什么值得认真对标

调研下来，KruiseAgents 几乎就是本文设计那套 sandbox 控制面的**开源实现**，而且 Soul 已经在用 Kruise 体系，引入子项目是同生态延伸——同一套 Operator 心智、团队已熟、安装和运维路径顺，不是平地起新栈。这把决策从「从 0 自研」推向「adopt + 适配」。

## 它提供什么（核对过的事实）

+ 核心 CRD：`Sandbox`（Pause/Resume/Checkpoint/Fork/原地升级）、`SandboxSet` / `SandboxWarmPool`（预热池→亚秒级启动）、`SandboxTemplate`、`SandboxClaim`、`Checkpoint`、`SandboxUpdateOps`。
+ 控制面：`sandbox-manager`（无状态，E2B API + MCP API）、`sandbox-gateway`（Envoy Filter 流量代理）、`sandbox-controller`（controller + admission webhook）、`agent-runtime`（sidecar，兼容 E2B envd、动态 CSI 挂载）。
+ 隔离：通过 K8s **RuntimeClass 可插拔**（容器 / gVisor / Kata / microVM），不改应用。
+ API：K8s CRD + E2B 兼容 + MCP；声称兼容 Sig Agent-Sandbox。

## 和我设计的映射

我 P0–P4 设计的统一抽象、可插拔隔离、Pool 预热、休眠唤醒、统一网关、让 moss/soulclaw 走统一 API，几乎一一对应到 `Sandbox` CRD、RuntimeClass、`SandboxWarmPool`、`Checkpoint`/Fork、`sandbox-gateway`、E2B/MCP API。soulclaw 是 OpenClaw 系，**E2B 兼容直接对上**接入契约。

## 它解决了什么、没解决什么（关键判断）

+ 解决：控制面、CRD、生命周期、WarmPool、Checkpoint、网关、E2B/MCP 接入——这些自研要花大力气的平台工程，它现成。
+ **没解决（仍是我的活）**：它是**编排层不是隔离层**。① gVisor/Kata/Firecracker 的节点改造、内核兼容、安全加固要自己搭——**命门「不可信代码强隔离」它只给挂载点，不替你解决**；② GPU × 强隔离依旧难，SAI 的 GPU 场景接进来还是开放难题；③ Checkpoint 的 CRIU/外部状态恢复成熟度要验；④ Envoy gateway 要和 Soul 的 CNI/VPC/出站安全整合，多租户和出站策略仍自定；⑤ 海量短生命周期的对账/泄漏回收/控制面容量要验证它的边界，不够再补；⑥ 新增 CRD + gateway + sidecar 的运维成本，要有人 own。

## buy vs build 结论

在 Soul 已用 Kruise 的约束下，**adopt + 适配明显优于从 0 自研**：不重复造控制面/CRD/WarmPool/Checkpoint，把精力集中到它没覆盖的隔离后端建设、GPU、对账防泄漏、多租户安全。这不是「有开源就无脑用」——而是它恰好命中 Soul 的现有生态，且把我的价值从「造轮子」重定位到「选型 + 接入 + 隔离后端 + 治理补齐」。

## 对路线的影响

+ P0 从「自研控制面」改成「**POC 接入 KruiseAgents**」：普通容器 RuntimeClass 跑通 `Sandbox` + `SandboxWarmPool` + E2B API，soulclaw 接上；安全红线不变。
+ P1 接 gVisor/Kata RuntimeClass 解决不可信代码（隔离后端部署是这阶段的真活）。
+ P2 用 `SandboxWarmPool` + `Checkpoint` 提冷启动，复用 SAE 镜像链路。
+ P3 多租户/安全/对账/控制面容量，验证 KruiseAgents 边界并补齐，接 Bigeyes 观测。

## 不能怎么说

+ 不要说「我们用 KruiseAgents 建好了 sandbox」——是选型对标，没生产落地。
+ 不要把 KruiseAgents 说成「引入就解决了强隔离」——它是编排层，隔离后端和 GPU 仍是硬骨头。
+ 不要给它的版本级/性能级断言——没自测，只讲它解决什么、边界在哪。
+ 可以说的：Kruise 工作负载我们真在用，KruiseAgents 是同生态延伸，我从选型角度判断 adopt 优于自研，并能说清它没覆盖的部分要自己补。

# 反问面试官的问题（这是我准备的核心）

这些问题既能问出关键信息，也在暗示「我知道建 sandbox 该先想清楚哪些约束」。如果面试官反过来问「你觉得这些怎么定」，我也有判断（见括号里我的倾向）。

+ 负载画像：你们 sandbox 主要承接什么——coding agent 跑代码为主，还是通用工具/数据处理执行？（这决定隔离强度和冷启动目标，是一切选型的前提。）
+ 隔离路线：现在走 Firecracker / gVisor / Kata 哪条？GPU 场景占比多大？（GPU 直通会把我从 microVM 拉向 gVisor 路线。）
+ 冷启动 SLO：目标是百毫秒级还是秒级？现在瓶颈卡在镜像拉取还是 runtime 启动？（决定先上 Lazy Pull/预热还是 Pool/Snapshot。）
+ 状态语义：sandbox 是有状态会话复用为主，还是一次性用完即弃？（决定 Snapshot/Pool 的投入方向。）
+ 控制面吞吐：峰值每秒要创建多少 sandbox？现在调度走 K8s Pod 还是自研轻量调度？（高频涌浪下 Pod 调度链路会成瓶颈，这点和我做控制面 Reconcile 性能同类。）
+ 多租户与成本：怎么防 noisy neighbor、计费粒度多细、闲置回收策略？
+ 安全边界：出站网络策略、密钥注入、逃逸防护、跨租户复用防护现在怎么做？
+ 团队当前最大的痛点：是隔离安全、冷启动延迟、还是控制面吞吐/成本？（直接问「最痛的是哪个」，能听出团队真实阶段。）

# 如果面试官把这题抛给我

## 三十秒版

我会先盘资产和 gap：Soul 已经有 moss-compose、soulclaw 做编排和大脑，Hermes 提供容器执行，但那还是普通容器，不是 sandbox——缺强隔离、秒级生命周期、会话语义、多租户治理和可观测。所以我不会从隔离技术入手，而是先抽一层统一的 Sandbox 控制面 API 把现状跑通，再分阶段补隔离、提冷启动、上治理。每阶段可灰度可回退，先复用 K8s 生态（gVisor/Kata），高危不可信代码再上 Firecracker。

## 三分钟版

在三十秒版基础上展开五个阶段：P0 复用 Hermes 容器先把控制面 API 和编排链路跑通；P1 把隔离做成可插拔 RuntimeClass，按负载切容器/gVisor/Kata/Firecracker；P2 冷启动分层优化，镜像预热+Lazy Pull→Pool→Snapshot；P3 上多租户 Quota、安全默认收紧、生命周期 Event 状态机和可解释回写；P4 会话 Sleep/Resume 和受控自治。我会强调两点判断：一是不要一上来全套 Firecracker，先复用生态再谈自建；二是隔离运行时我是对标理解的，但控制面、镜像分发、状态机、治理、灰度这些平台工程问题我在 SAE/SAI/Bigeyes 真做过，能直接平移——我的价值是把 sandbox 当成一种特殊 Runtime 平台来建，而不是声称我是隔离内核专家。我还会主动讲选型判断：我调研过 OpenKruise Agents，它几乎就是这套 sandbox 控制面的开源实现（Sandbox CRD、WarmPool 亚秒级、Checkpoint/Fork、RuntimeClass 可插拔、E2B/MCP API），而 Soul 本来就在用 Kruise 工作负载，所以我不会从 0 自研控制面，而是 adopt + 适配，把精力放在它没解决的隔离后端、GPU、对账防泄漏、多租户安全上——我没生产跑过它，这是选型层面的判断。最后我会主动抛我认为最难的几个点（强隔离×GPU、秒级 vs 安全销毁、海量短生命周期的对账与不泄漏、控制面扛涌浪），把「知道难在哪」也讲出来，而不是只报路线。

# 落地最大的难点与风险（这是体现深度的部分）

交叉面爱问「你觉得最难的是什么」。知道难在哪，比知道分几个阶段更显资深。下面是我判断这套体系真正的硬骨头，以及我的取舍。

+ **强隔离 × GPU —— 最大技术风险**。「跑不可信代码要强隔离」和「跑模型要 GPU」是冲突的：Firecracker 基本不支持 GPU 直通，gVisor 的 GPU（nvproxy）支持也新且受限。所以「又要 microVM 强隔离、又要 GPU」在业界都还是半开放问题。我的判断：先按场景分流——纯 CPU 的不可信代码走 Firecracker/gVisor；要 GPU 的尽量收敛到受信/半受信、用 gVisor + GPU 或受控容器，别一开始就追「不可信 + GPU + 强隔离」全都要。

+ **秒级 × 安全销毁 × 多租户复用 的三角**。Pool/Snapshot 复用热实例提速，和「用完即弃防跨租户残留」直接打架。我的取舍：**Pool 只在同租户/同信任域内复用，跨租户一律 fresh 实例**；持久会话用 Snapshot 且快照加密隔离；临时执行用完即弃、彻底销毁。快和安全冲突时，安全优先，靠预热和分层把延迟补回来。

+ **海量短生命周期下的状态对账与资源不泄漏**。sandbox 秒级、易失、量大，控制面记录和实际状态极易 drift：幽灵 sandbox 烧钱、Destroy 没真释放导致 IP/GPU/磁盘泄漏。这比普通 Pod 巡检难一个量级，必须有对账回收兜底，且回收要「确定性释放所有资源」。这是我认为最容易在生产暴雷、又最依赖平台工程功底的一块——正好是我的强项。

+ **控制面扛瞬时涌浪**。峰值每秒大量创建，K8s Pod 调度链路会成瓶颈，可能要轻量自研调度 + 预创建池。难在既要高吞吐又要状态一致、幂等、可灰度。和我做控制面 Reconcile 性能优化同类，能平移。

+ **可插拔隔离后端是 leaky abstraction**。`Snapshot/Sleep/Resume` 在容器（CRIU）和 microVM（Snapshot）上语义、可靠性、GPU/网络支持都不同。统一 API 下藏着后端差异，硬抽象会漏。我的做法：抽象只保证「会话+执行」最小公共语义，后端能力差异显式暴露成 capability（这个后端支不支持 Snapshot/GPU），不假装所有后端等价。

+ **网络两头堵**。既要冷启动快（网络预创建 / eBPF 数据面），又要出站受控（白名单 / 防 SSRF / 防打内网）。快和安全在网络层也对立，要预创建受控网络池，而不是「先开通再收紧」。

+ **成本：warm pool 常驻 vs 冷启动延迟**。Pool 太大烧钱、太小延迟差，要按负载预测做弹性预热（分时段/分镜像），并把预热常驻成本算进单位成本。低延迟和低成本要显式权衡，不能只报「秒级」。

+ **组织/依赖风险（常被低估）**。P0 要把 moss-compose/soulclaw 从「直连容器」改成「走统一 API」，是改别人的既有链路，跨团队推动比技术更难；且要先验证 Hermes 现状能不能平滑下沉成 sandbox 后端，「先顶着」别变成技术债。

+ **我的默认 SLO 立场（反问留空时给得出判断）**：coding agent 跑代码场景，我会先定 **冷启动 P95 秒级、warm/Pool 命中走百毫秒级**，先达标再往毫秒级抠；不一上来追全场景毫秒，因为成本和复杂度不成正比。

# 风险与不能说

+ 不要说「我在 Soul 已经建好了 sandbox」——目前是设计判断 + 资产盘点，没落地。
+ 不要把 Hermes 说成已经是强隔离 sandbox——它现在更可能是普通容器，gap 要如实讲。
+ 不要吹 Firecracker/gVisor 的版本级、性能级数字——我没自测，只讲选型场景和取舍。
+ 不要把隔离内核细节讲成实操——逃逸防护、seccomp 策略我讲设计意图和边界，不假装调过内核。
+ 自治执行（P4）要讲成演进方向，不是已实现的闭环。
