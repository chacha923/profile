# SAI TFJob 潮汐调度技术点文档 V2

包含：

- sai_tfjob_tide_scheduling_tech_point_v2.md
- images/ 下 7 张 PNG 图

本版更新重点：

1. 收敛为“提交前 cluster routing”，避免夸大成联邦调度。
2. 增加周期任务夜间实例级路由说明。
3. 增加长任务 checkpoint stop-and-resume 的 ROI 判断。
4. 增加在线失败退避、集群熔断、离线队列回退机制。
5. 增加可能被面试官挑战的问题与回答口径。
