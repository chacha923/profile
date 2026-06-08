# SAI 后续可扩展技术点索引

本目录存放 SAI 相关的 7 个可扩展技术点。它们不是项目总结文档，而是面向面试表达的技术点材料，统一按 `tech-point` 结构组织：

```text
问题 -> 原理 -> 机制 -> 对比 -> 场景 -> 排障 -> 边界 -> 追问 -> 话术
```

核心目标是：把 SAI 的真实项目经验和后续演进方向连接起来，但不把没有亲自实现的底层能力夸大成项目结果。

# 文件列表

| 顺序 | 技术点 | 文件 | 主讲价值 |
|---|---|---|---|
| 1 | AI 工作负载 Runtime 统一治理 | [01_ai_runtime_unification.md](01_ai_runtime_unification.md) | 先讲清 SAI 的平台定位：统一 Runtime 治理，不是自研执行引擎 |
| 2 | GPU 资源池与调度意图治理 | [02_gpu_resource_governance.md](02_gpu_resource_governance.md) | 体现 AI Infra 深度：GPU 资源池、准入、PodSpec 翻译和调度边界 |
| 3 | 生命周期与状态一致性治理 | [03_lifecycle_state_consistency.md](03_lifecycle_state_consistency.md) | 体现平台工程能力：server / watcher / Sync / Job Runtime 和最终一致性 |
| 4 | 多云推理服务托管与 Provider 抽象 | [04_multi_cloud_serving.md](04_multi_cloud_serving.md) | 回答多云、贝联、Provider、状态同步和网络接入问题 |
| 5 | PD 分离推理形态的平台侧适配 | [05_pd_separation_platform_adaptation.md](05_pd_separation_platform_adaptation.md) | 连接大模型 Serving 演进，但只讲平台侧运行治理适配 |
| 6 | 模型制品任务异步化与 Job Runtime | [06_async_model_artifact_jobs.md](06_async_model_artifact_jobs.md) | 说明控制面和长耗时任务解耦，模型下载不是完整 Model Registry |
| 7 | SAI 适配 LLM 训推场景 | [07_original_model_vs_llm.md](07_original_model_vs_llm.md) | 回答传统训推到 LLM 训推的差异、平台改造点、难点和架构演进 |

# 统一文档结构

每篇专题都包含这些一级章节：

- 面试定位卡
- 三十秒回答
- 为什么需要它
- 核心概念表
- 原理模型
- 关键机制
- 横向对比
- 典型业务场景
- 排障路径
- 风险、边界和误区
- 和项目的安全连接
- 面试追问树
- 高频 Q&A
- 三档背诵版
- 图示清单
- 面试前检查清单

# 面试主讲顺序

建议先讲三篇主线：

1. **Runtime 统一治理**：解释 SAI 为什么不是普通 Kubernetes Portal。
2. **GPU 资源治理**：体现 AI Infra 对高成本资源的治理能力。
3. **生命周期一致性**：体现平台控制面和稳定性能力。

根据面试官追问再展开：

1. **多云推理托管**：回答 ACK、PAI、火山、贝联、Provider 和网络接入。
2. **PD 分离平台侧适配**：回答大模型 Serving 演进，但强调平台边界。
3. **模型制品异步化**：回答控制面和长耗时任务解耦。
4. **LLM 训推场景适配**：回答 SAI 从传统训推到数据、训练、评测、Serving、RAG / Agent 和反馈闭环的升级路径。

# 统一边界

不要说：

- 自研 AI Runtime。
- 自研训练框架。
- 自研推理引擎。
- 自研 GPU Scheduler。
- 自研 GPU 插件、显存隔离、MIG 管理或抢占调度。
- 自研贝联底层网络。
- 实现了 PD 分离、KV Cache、attention、block manager 或 vLLM / SGLang 内核。
- 模型下载能力等于完整 Model Registry。

可以说：

- 平台侧 Runtime 治理。
- 异构 AI 工作负载统一托管。
- GPU 资源池抽象、准入校验和 PodSpec 生成。
- server / watcher / Sync / Job Runtime 分层。
- 多云 Provider 适配和状态补偿。
- 贝联接入编排复用基础设施。
- PD 分离带来的平台侧多组件建模、状态聚合和观测适配。
- 模型制品下载、落盘、挂载和训练 / 推理复用。

# 推荐总口径

> 我在 SAI 里的核心经验，是把异构 AI 工作负载和多云底座差异收敛到统一控制面。Runtime 侧统一服务画像和生命周期，资源侧做 GPU / NodePool 治理，状态侧用 watcher、Sync 和 Job Runtime 处理长周期最终一致，多云侧用 Provider 适配 ACK、PAI、火山、贝联等托管形态。对于 PD 分离和模型制品这些后续扩展点，我会明确区分平台侧运行治理和底层推理 / 模型管理能力，不把没有实现的底层能力夸大成项目结果。
