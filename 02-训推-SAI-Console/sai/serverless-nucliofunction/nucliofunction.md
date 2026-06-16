# 控制面架构<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777270379690-0f0f3083-adb5-4b6e-98f9-2f95fbc2eb90.png" width="2200" title="" crop="0,0,1,1" id="u3c26aeb6" class="ne-image">




# 一个 NuclioFunction 的变更过程
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1777270584049-fbdb9942-301c-4599-84df-134c0d18b32e.png" width="938" title="" crop="0,0,1,1" id="ua79ef2df" class="ne-image">  




# Trigger
`trigger` 控制的是：**外部事件怎么进入 Function，以及进入后以什么并发/协议/消费方式调用 handler。**

它不是控制镜像构建，也不是控制副本数。它更像 Function 的 **入口定义**。

```latex
NuclioFunction
  spec.triggers
      |
      v
定义事件入口：
  - HTTP 请求怎么进来
  - Kafka 消息怎么消费
  - Cron 定时怎么触发
  - NATS / MQTT / RabbitMQ 等事件源怎么接入
      |
      v
Nuclio processor 接收事件
      |
      v
调用你的 handler
```





# 什么场景该用 NuclioFunction

NuclioFunction 的定位是 **算法侧的轻量推理 / 特征加工 serverless 函数**：算法同学只写一个 `handler`，平台负责镜像构建、HTTP / Kafka 接入、副本弹性和扩缩容。它适合的典型场景：

- **事件驱动的流式特征加工**：上游一个 Kafka topic 不停产数据，函数逐条消费、抽特征、产出给下游（推荐 / 召回 / 标签）。
- **轻量在线推理**：模型不大、不吃 GPU，CPU 就能跑，按请求量自动扩缩。
- **一套代码、流式 + 点查双入口**：同一个 `Predictor`，既挂 Kafka 做批量，又开 HTTP 做单条调试 / 在线调用。

它不适合的：重型 GPU 大模型常驻推理（那是 KServe / 推理服务的活）、长周期训练（TFJob）、需要复杂状态编排的任务。

# 一个真实例子：群聊切片特征

以 `group-chat-feature-v2`（描述「群聊切片特征v2」，namespace `soul-image-algorithm`）为例，能完整看清一个 NuclioFunction 在生产里长什么样。

**它在做什么**：消费群聊语音切片的「内容打标结果」，做特征加工，产出给推荐系统用。一句话链路——

```latex
标签平台打标结果 (Kafka)
  topic: tag-platform-tag-result-no-audit-prod
  broker: voice-algorithm-kafka*   ← 数据来自语音算法侧
      |
      v
NuclioFunction: group-chat-feature-v2
  handler → Predictor().predict(body)
  依赖 jieba 做中文分词 / 文本特征
      |
      v
群聊特征 → 推荐系统
  otel app_name: prod_nuclio_recommend-group-chat-feature  ← recommend
```

对照前面的科普章节，这个函数把每个概念都落了地：

- **Trigger（双入口）**：
  - `kafka`：消费 `tag-platform-tag-result-no-audit-prod`，消费组 `chat_group_speech_prod_v2@zhr`，`maxWorkers: 16` —— 主力，流式批量算特征。
  - `default-http`：ClusterIP，`maxWorkers: 1` —— 在线 / 调试单条预测。
  - 一套 `Predictor` 代码，两个入口，正是「流式 + 点查」的典型用法。
- **镜像构建（build.commands）**：基础镜像是 `torchserve:...mmbt...`（mmbt = MultiModal BiTransformer 多模态图文模型，说明底座是多模态模型），构建时 `pip install group_chat_feature_v2==0.2.6` + `infra-pyserver-tools[otel]` + `jieba`。算法只交付一个版本化的业务包，平台负责拼镜像。
- **资源与调度**：2C4G，`nodeSelector: cv-cpu` + 对应 toleration，调度到 **CPU 节点池**（GPU 全 0）—— 印证「轻量、CPU 可跑、不吃 GPU」。
- **弹性**：`minReplicas 6 / maxReplicas 12 / targetCPU 40%`，按 CPU 自动扩缩，应对流量波动。
- **可观测**：`handler` 里用 OTel 给每次调用开 span，记 HTTP method / status / 异常，接入统一 trace。

# 踩坑

**HPA 创建失败导致整个 Function 起不来。** 上面这个例子的 CR 其实是 `status.state: error` 的：

```text
Failed to create/update HPA
Error - the server could not find the requested resource
```

配了 `targetCPU + min/max` 就必然要建 HPA，HPA 建不出来，整个 function 就 error。`the server could not find the requested resource` 这类报错的根因，通常是 **集群的 autoscaling API 版本和 Nuclio controller 期望的对不上**（高版本 ACK / K8s 已经把 `autoscaling/v2beta*` 下线，只剩 `autoscaling/v2`，而 controller 还在请求旧版本），或 metrics 相关 API 没就绪。

高版本 ACK 不兼容 HPA api 升级。
