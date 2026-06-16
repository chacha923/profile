# PyTorchJob 稳定性治理文档包

这组文档用于补齐 SAI 从 TFJob 经验迁移到 PyTorchJob / 生成式模型训练生态时的面试表达。重点不是背 PyTorchJob YAML，而是能从平台 SRE 视角讲清楚：

- PyTorchJob 在 Kubernetes 里到底是什么 API Resource。
- `runPolicy`、`pytorchReplicaSpecs`、`elasticPolicy` 这些字段分别影响什么。
- GPU 调度如何从 SAI 的 NodePool / 资源池翻译到 PodSpec、队列、gang 和拓扑约束。
- 作业 Pending、rendezvous 卡住、NCCL timeout、OOM、训练慢时怎么排查。
- 哪些能和 SAI/TFJob 真实经验安全连接，哪些只能说相邻经验或理论对标。

## 阅读顺序

1. [pytorchjob-stability-governance.md](./pytorchjob-stability-governance.md)  
   主文档。按面试技术点写，覆盖定位、原理、关键机制、排障、边界和 Q&A。

2. [pytorchjob-api-resources.md](./pytorchjob-api-resources.md)  
   API Resource 和 CRD 字段阅读地图。适合你刚开始看 `kubectl api-resources` / `kubectl explain pytorchjob` 时用。

3. [pytorchjob-gpu-scheduling.md](./pytorchjob-gpu-scheduling.md)  
   GPU 调度与稳定性 runbook。重点讲 queue/gang/NodePool/PodSpec/topology/NCCL 的平台侧治理。

## 和现有文档的关系

- TFJob 可观测深度参考：[TFJob 可观测体系演进](../job-observability/tfjob_observability_tech_point/tfjob_observability_tech_point.md)
- 框架横向对比参考：[TFJob / PyTorchJob / Ray 工作负载治理对比](../framework-governance/training_framework_governance_tech_point.md)
- SAI 项目主线参考：[SAI-Console 项目总结](../sai.md)
- PyTorch / LLM 生态入口参考：[PyTorch 体系与 LLM 托管生态演进](../pytorch-llm-ecosystem/pytorch-llm-ecosystem.md)
- NCCL 排障参考：[NCCL 集合通信](../nccl/nccl.md)

## 面试主线

一句话：

PyTorchJob 的稳定性治理不是“会创建一个 CRD”，而是把多机多卡 PyTorch 训练变成可准入、可成组调度、可观测、可恢复、可复盘的平台工作负载。

最稳妥的项目连接：

我真实做过的是 SAI/TFJob 的平台控制面、资源池、状态同步和排障。PyTorchJob 是同一类 Training Operator 工作负载的演进承接：字段模型、GPU 调度、rank/rendezvous/NCCL 语义需要补齐。我能讲清平台如果承接 PyTorchJob，要怎么设计资源准入、PodSpec、状态观测和故障排查，但不把它包装成我深度调优过 PyTorch/NCCL 内核。

