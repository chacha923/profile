# 总结
我们现在这套 `cmdb_new` 更准确地说是一个多资源资产管理后台，而不是完整意义上的配置项关系库。它的优点是资源覆盖面比较广，已经纳入了应用、主机、RDS、Redis、SLB、Mongo、HBase、Kafka、RocketMQ、ClickHouse、SAI、PAI、EAS、大数据集群等资源，也有阿里云、华为云、SAE、SAI、PAI 等同步脚本，所以不是完全靠人工录入。  


但它和理想 CMDB 的差距也比较明显。第一，模型主要是按资源类型拆表，比如 `Application`、`Host`、`Redis`、`Rds`、`KafkaTopic` 各自独立，缺少统一的 `ResourceType`、`ResourceInstance`、`ResourceRelation` 抽象。所以它能查“有哪些资产”，但很难统一回答“这个资源和哪些应用有关”。



第二，关系建模比较弱。比如应用和主机有一定关联，但应用到 Redis、RDS、Kafka Topic、RocketMQ Topic、域名、SLB、上下游服务这些关系没有系统化建模。因此在 Redis 迁移、Topic 下线、域名排障、告警归属、发布影响面分析时，CMDB 还不能直接给出可靠答案。  


第三，Kubernetes 运行态建模偏粗。目前应用表里有 `cluster_name`、`namespace`、`pod_count` 这类字段，但没有把 `Cluster`、`Namespace`、`Workload`、`Service`、`Ingress`、`HPA`、`Image` 这些对象独立建模。对云原生平台来说，这会限制它对实际运行态的表达能力。



第四，同步能力有，但还不够平台化。现在是很多脚本分别同步云资源、SAE、SAI、PAI、中间件资源，但缺少统一的 `DataSource`、`SyncJob`、`SyncRun`、`SyncDiff` 和软删除机制。这样很难追踪某条数据来自哪里、最后一次同步是什么时候、同步失败时会不会误删数据。



如果让我设计演进路线，我不会推翻重写，而是先在现有表之上补三层。第一层是统一资源索引，把现有 `Application`、`Host`、`Redis`、`Rds`、`KafkaTopic` 都映射成统一 `Resource`。第二层是关系模型，用 `ResourceRelation` 表达 `Application -> Redis`、`Application -> RDS`、`Application -> KafkaTopic`、`Domain -> Application`、`Application -> Owner` 这些关系。第三层是应用画像，把负责人、部门、集群、namespace、workload、镜像、域名、中间件依赖、告警、日志、Trace、发布记录聚合到一个应用视图里。



最终目标不是单纯做资产列表，而是让 CMDB 成为发布、告警、排障、迁移和 Agent 答疑的事实底座。比如 Bigeyes 告警可以从 CMDB 查负责人和飞书群；SAE 发布前可以查上下游和中间件依赖；Redis 或 Kafka 迁移前可以查影响应用；故障排查时可以从应用画像直接跳到日志、指标、Trace 和最近发布记录。这才是完整 CMDB 的价值。



## 怎么结合 AI
我不会让 AI 直接维护 CMDB 的事实数据，因为 CMDB 最重要的是准确性。AI 更适合放在 CMDB 上层做提效。



第一，做自然语言查询入口，把“这个域名是谁的”“这个 Redis 影响哪些应用”这类问题转成 CMDB API 查询。



第二，做关系抽取，从配置文件、环境变量、Nacos 配置、代码仓库、日志和 Trace 里抽取应用到 Redis、RDS、Kafka、RocketMQ、域名、下游服务的候选关系，但必须带 source、confidence 和人工确认机制。



第三，做数据治理辅助，把无负责人、负责人离职、资源无归属、生产应用未接告警这类巡检结果转成可执行的治理建议。



第四，做故障和变更辅助。告警时基于应用画像聚合负责人、部署、依赖、最近发布、日志和 Trace，生成排查路径；迁移 Redis 或 Kafka Topic 时，基于 CMDB 关系生成影响面和通知清单。



所以 AI 的定位不是替代 CMDB，而是基于 CMDB 的确定性数据做查询编排、关系发现和场景解释。

## 
# 干什么
**Soul CMDB = 应用 / 资源 / 关系 / 归属 / 运行态索引的统一事实库**

我理解 CMDB 不是简单的资产录入系统，而是应用、资源、组织、依赖、变更之间的统一事实库。



它至少要解决四类问题：



第一，资源看得清：应用、集群、Workload、主机、中间件、域名这些资源能统一查询。



第二，关系串得起来：应用和团队、应用和资源、应用和中间件、应用和上下游服务之间的关系能够建模。



第三，数据保持准：通过 Kubernetes、发布系统、注册中心、云厂商 API、组织架构系统做自动同步和定时校准，减少人工维护。



第四，能被其他平台消费：告警中心用它做负责人路由，发布系统用它做影响面分析，故障平台用它聚合日志、指标、Trace，Agent 问答也可以用它作为上下文来源。



所以 CMDB 的价值不在于多几张资产表，而在于它能不能成为运维、发布、告警、排障、成本治理的基础数据底座。





# 理想的 cmdb 长什么样
应用、资源、组织、依赖、变更、运行态索引之间的统一事实库

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778132155785-f4b9ebb4-406a-443d-a449-06974917a670.png" width="783" title="" crop="0,0,1,1" id="u8a52e5ab" class="ne-image">



# soul cmdb 现状
```latex
cmdb_new/
  account/          用户、部门、权限相关
  category/         核心资产模型、序列化、视图、API
  history/          操作历史
  sync/             一些巡检、同步、检查脚本
  sync-scripts/     云资源 / SAE / SAI / PAI / Kafka / Mongo 等同步脚本
  utils/            阿里云、华为云、LDAP、JumpServer、推送、资源 API 工具
```



## 当前的能力
多资源资产管理后台 + 一批资源同步脚本

<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778132151419-3d1ea208-31c3-4c8a-ac68-79f396c094eb.png" width="819" title="" crop="0,0,1,1" id="ub43798ed" class="ne-image">

## 缺陷
没有统一 CI 抽象

没有通用关系模型

没有应用画像

没有依赖拓扑

K8s 运行态建模偏粗

同步治理不系统

对 Bigeyes / SAE / OTel / Agent 的场景 API 不够





## Roadmap
<img src="https://cdn.nlark.com/yuque/0/2026/png/29786964/1778132175105-403ca084-ff0a-4a28-8da4-147da8491eff.png" width="863" title="" crop="0,0,1,1" id="u6799409a" class="ne-image">



# 
