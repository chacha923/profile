#!/usr/bin/env python3
from html import escape
from pathlib import Path


OUT = Path(__file__).with_name("06_training_to_serving_stack.svg")
W, H = 2400, 1450


def e(text):
    return escape(str(text), quote=True)


lines = []


def add(s):
    lines.append(s)


def text(x, y, content, size=14, fill="#111827", weight=400, anchor="start"):
    add(
        f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{e(content)}</text>'
    )


def multiline(x, y, rows, size=14, fill="#374151", leading=21, weight=400):
    for i, row in enumerate(rows):
        text(x, y + i * leading, row, size=size, fill=fill, weight=weight)


def node(x, y, w, h, title, rows, fill="#ffffff", stroke="#d1d5db", accent="#2563eb"):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    add(f'<rect x="{x}" y="{y}" width="8" height="{h}" rx="4" fill="{accent}"/>')
    text(x + w / 2, y + 40, title, size=22, fill="#111827", weight=700, anchor="middle")
    multiline(x + 22, y + 76, rows, size=15, fill="#374151", leading=22)


def label(x, y, content, color="#6b7280", bg="#ffffff", width=None):
    width = width or max(74, len(content) * 9 + 16)
    add(f'<rect x="{x - width / 2}" y="{y - 15}" width="{width}" height="22" rx="5" fill="{bg}" opacity="0.96"/>')
    text(x, y, content, size=13, fill=color, weight=600, anchor="middle")


def path(d, color="#2563eb", width=2.4, marker="arrow-blue", dash=None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash_attr} marker-end="url(#{marker})"/>')


def line_arrow(x1, y1, x2, y2, color="#2563eb", width=2.4, marker="arrow-blue", dash=None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{dash_attr} marker-end="url(#{marker})"/>')


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
add("""<style>
text {
  font-family: 'Helvetica Neue', Helvetica, Arial, 'PingFang SC',
               'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif;
}
</style>""")
add("""<defs>
  <marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
    <polygon points="0 0, 10 3.5, 0 7" fill="#2563eb"/>
  </marker>
  <marker id="arrow-orange" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
    <polygon points="0 0, 10 3.5, 0 7" fill="#ea580c"/>
  </marker>
  <marker id="arrow-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
    <polygon points="0 0, 10 3.5, 0 7" fill="#059669"/>
  </marker>
  <marker id="arrow-purple" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
    <polygon points="0 0, 10 3.5, 0 7" fill="#7c3aed"/>
  </marker>
  <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">
    <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#0f172a" flood-opacity="0.10"/>
  </filter>
</defs>""")
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
add('<rect x="40" y="28" width="2320" height="1370" rx="28" fill="#f8fafc" stroke="#e5e7eb" stroke-width="1.5"/>')

text(1200, 74, "生成式大模型：从训练到上线推理的核心技术栈全景图", size=34, fill="#0f172a", weight=800, anchor="middle")
text(1200, 111, "主线：PyTorch 负责建模与训练，DeepSpeed / FSDP / Megatron 解决分布式训练，vLLM / TensorRT-LLM / TGI 解决在线推理，KServe / Triton / 网关负责服务化。", size=18, fill="#475569", weight=500, anchor="middle")
text(1200, 139, "职责边界：训练框架管“模型怎么学”，推理引擎管“请求怎么跑得快”，服务治理管“怎么稳定上线、灰度和回滚”。", size=16, fill="#64748b", weight=500, anchor="middle")

# Lane backgrounds
add('<rect x="70" y="165" width="2260" height="250" rx="18" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1.2"/>')
text(94, 194, "训练与模型产物链路", size=16, fill="#1d4ed8", weight=800)
add('<rect x="70" y="535" width="2260" height="285" rx="18" fill="#f0fdfa" stroke="#99f6e4" stroke-width="1.2"/>')
text(94, 564, "上线推理与业务调用链路", size=16, fill="#0f766e", weight=800)
add('<rect x="70" y="905" width="2260" height="255" rx="18" fill="#fff7ed" stroke="#fed7aa" stroke-width="1.2"/>')
text(94, 934, "治理闭环与运行保障", size=16, fill="#c2410c", weight=800)

top_x = [95, 465, 835, 1205, 1575, 1945]
top_y, top_w, top_h = 205, 310, 180
top_nodes = [
    ("1. 数据准备", ["语料/图片/音频/视频", "清洗、去重、脱敏", "质量打分、过滤", "tokenizer 训练/选择", "数据湖/对象存储"], "#dbeafe", "#2563eb"),
    ("2. 模型开发", ["PyTorch: Tensor/autograd", "nn.Module 与 Transformers", "模型结构 / tokenizer 配置", "实验追踪: MLflow/W&B/自研", "上下文长度与参数规模"], "#e0f2fe", "#0284c7"),
    ("3. 预训练/微调", ["预训练: next-token prediction", "SFT: 指令微调", "对齐: RLHF/DPO/GRPO", "PEFT: LoRA / QLoRA", "数据配比与训练 recipe"], "#ede9fe", "#7c3aed"),
    ("4. 分布式训练优化", ["DeepSpeed ZeRO", "PyTorch FSDP / DDP", "Megatron-LM: TP/PP/DP", "混合精度: FP16 / BF16", "Checkpoint / Resume"], "#fef3c7", "#d97706"),
    ("5. 评测与安全", ["离线评测: MMLU/CMMLU/业务集", "人评/红队/越狱测试", "幻觉、毒性、隐私泄露", "A/B 测试候选模型", "安全阈值与拒答策略"], "#fee2e2", "#dc2626"),
    ("6. 模型产物管理", ["权重: checkpoint / safetensors", "tokenizer / config / prompt 模板", "版本: Model Registry", "量化: INT8/INT4/AWQ/GPTQ", "发布审批 / 灰度策略"], "#dcfce7", "#16a34a"),
]

for x, (title_, rows, fill, accent) in zip(top_x, top_nodes):
    node(x, top_y, top_w, top_h, title_, rows, fill=fill, stroke=accent, accent=accent)

for i in range(5):
    line_arrow(top_x[i] + top_w + 12, top_y + top_h / 2, top_x[i + 1] - 12, top_y + top_h / 2)

mid_x = [100, 565, 1030, 1495, 1960]
mid_y, mid_w, mid_h = 600, 365, 185
mid_nodes = [
    ("7. 推理引擎 / Runtime", ["vLLM: PagedAttention、KV Cache", "TensorRT-LLM: NVIDIA 高性能推理优化", "TGI / SGLang / llama.cpp: 场景选择", "连续批处理、并发、显存水位", "核心指标: TTFT、TPOT、吞吐"], "#ccfbf1", "#0d9488"),
    ("8. 模型服务化", ["OpenAI-compatible API / gRPC / HTTP", "Triton Inference Server: 通用推理服务", "KServe / Seldon / BentoML / 自研平台", "多副本、滚动发布、自动扩缩容", "镜像、资源规格、启动探针"], "#dbeafe", "#2563eb"),
    ("9. 流量治理", ["API Gateway / Envoy / Ingress", "鉴权、限流、熔断、超时、重试", "模型路由: 按租户/场景/版本", "灰度、A/B、fallback、降级", "请求审计与配额管理"], "#fef3c7", "#d97706"),
    ("10. 应用编排", ["Prompt 模板与变量注入", "RAG: Embedding + Vector DB", "Agent / Workflow / Tool Calling", "会话记忆、上下文压缩", "结果解析与业务校验"], "#ede9fe", "#7c3aed"),
    ("11. 业务入口", ["Chatbot / Copilot", "AIOps Agent / 代码助手", "搜索问答 / 客服 / 内容生成", "业务系统 SDK / Web / App", "用户体验与成本感知"], "#fce7f3", "#db2777"),
]

for x, (title_, rows, fill, accent) in zip(mid_x, mid_nodes):
    node(x, mid_y, mid_w, mid_h, title_, rows, fill=fill, stroke=accent, accent=accent)

for i in range(4):
    line_arrow(mid_x[i] + mid_w + 16, mid_y + mid_h / 2, mid_x[i + 1] - 16, mid_y + mid_h / 2)

bottom_x = [100, 665, 1230, 1695]
bottom_y, bottom_w, bottom_h = 970, 455, 165
bottom_nodes = [
    ("12. 观测与稳定性", ["Metrics: GPU 利用率、显存、QPS、错误率、P95/P99", "Tracing: OpenTelemetry、端到端链路", "Logs: 请求、采样、异常、审计", "SLO: 可用性、时延、成本/千 token"], "#f8fafc", "#64748b"),
    ("13. 容量与成本", ["容量规划: GPU 卡数、副本数、batch size", "弹性: HPA/KEDA/Karpenter/自研调度", "显存优化: KV Cache、量化、prefix cache", "成本治理: 空闲 GPU、冷热模型、混部"], "#f0fdf4", "#16a34a"),
    ("14. 安全与合规", ["输入输出审核: 敏感词、PII、内容安全", "租户隔离: Namespace/Quota/NetworkPolicy", "模型权限: Registry ACL、密钥管理", "审计: 请求留痕、数据使用边界"], "#fef2f2", "#dc2626"),
    ("15. 反馈闭环", ["线上样本采集: 低置信/差评/异常案例", "标注与数据回流: 构造 SFT/RL 数据", "持续评测: 回归集、业务指标、红队集", "重新训练/微调 -> 新版本发布"], "#faf5ff", "#7c3aed"),
]

for x, (title_, rows, fill, accent) in zip(bottom_x, bottom_nodes):
    node(x, bottom_y, bottom_w, bottom_h, title_, rows, fill=fill, stroke=accent, accent=accent)

# Publish and vertical governance arrows
path(f"M {top_x[-1] + top_w / 2},{top_y + top_h} L {top_x[-1] + top_w / 2},500 L {mid_x[0] + mid_w / 2},500 L {mid_x[0] + mid_w / 2},{mid_y - 16}", color="#ea580c", marker="arrow-orange", width=2.2)
label(1880, 492, "发布模型版本", color="#ea580c", width=112)

vertical_pairs = [
    (mid_x[0] + mid_w / 2, mid_y + mid_h, bottom_x[0] + bottom_w / 2, bottom_y - 14, "运行指标"),
    (mid_x[1] + mid_w / 2, mid_y + mid_h, bottom_x[1] + bottom_w / 2, bottom_y - 14, "容量规格"),
    (mid_x[2] + mid_w / 2, mid_y + mid_h, bottom_x[2] + bottom_w / 2, bottom_y - 14, "策略审计"),
    (mid_x[4] + mid_w / 2, mid_y + mid_h, bottom_x[3] + bottom_w / 2, bottom_y - 14, "线上反馈"),
]
for x1, y1, x2, y2, lab in vertical_pairs:
    path(f"M {x1},{y1 + 8} L {x1},{870} L {x2},{870} L {x2},{y2}", color="#7c3aed", marker="arrow-purple", width=1.9)
    label((x1 + x2) / 2, 861, lab, color="#7c3aed", width=86)

# Feedback loop back to data preparation, routed through the clear channel
# between the governance row and the infrastructure foundation.
feedback_y = 1186
path(
    f"M {bottom_x[3] + bottom_w / 2},{bottom_y + bottom_h} "
    f"L {bottom_x[3] + bottom_w / 2},{feedback_y} L 58,{feedback_y} "
    f"L 58,{top_y + 92} L {top_x[0] - 18},{top_y + 92}",
    color="#7c3aed",
    marker="arrow-purple",
    width=2.0,
)
label(210, feedback_y - 8, "数据回流/再训练", color="#7c3aed", width=126)

# Infrastructure foundation
infra_y = 1225
add(f'<rect x="70" y="{infra_y}" width="2260" height="155" rx="16" fill="#ffffff" stroke="#0f172a" stroke-width="2"/>')
text(1200, infra_y + 42, "底座基础设施层 Infrastructure", size=24, fill="#111827", weight=800, anchor="middle")
multiline(105, infra_y + 82, [
    "GPU/加速卡：NVIDIA A100/H100/L40S/4090，或 AMD/国产卡 ｜ CPU/内存/本地 NVMe/云盘/NAS/对象存储",
    "驱动与算子：CUDA / ROCm / cuDNN / NCCL / TensorRT / CUTLASS / FlashAttention",
    "集群与调度：Kubernetes / Slurm / Ray / Volcano / Kueue ｜ CNI/CSI/镜像仓库/Secret/Quota/节点池/污点容忍",
], size=17, fill="#374151", leading=29)

for x in [bottom_x[0] + bottom_w / 2, bottom_x[1] + bottom_w / 2, bottom_x[2] + bottom_w / 2, bottom_x[3] + bottom_w / 2]:
    line_arrow(x, infra_y, x, bottom_y + bottom_h + 14, color="#059669", width=1.9, marker="arrow-green", dash="5,4")

# Legend
legend_x, legend_y = 1740, 1240
add(f'<rect x="{legend_x}" y="{legend_y}" width="545" height="112" rx="12" fill="#f8fafc" stroke="#e5e7eb" stroke-width="1"/>')
text(legend_x + 20, legend_y + 28, "箭头语义", size=15, fill="#111827", weight=800)
line_arrow(legend_x + 22, legend_y + 52, legend_x + 78, legend_y + 52, color="#2563eb", width=2.2, marker="arrow-blue")
text(legend_x + 90, legend_y + 57, "主链路", size=13, fill="#475569", weight=600)
line_arrow(legend_x + 190, legend_y + 52, legend_x + 246, legend_y + 52, color="#ea580c", width=2.2, marker="arrow-orange")
text(legend_x + 258, legend_y + 57, "发布触发", size=13, fill="#475569", weight=600)
line_arrow(legend_x + 362, legend_y + 52, legend_x + 418, legend_y + 52, color="#7c3aed", width=2.0, marker="arrow-purple")
text(legend_x + 430, legend_y + 57, "治理反馈", size=13, fill="#475569", weight=600)
line_arrow(legend_x + 22, legend_y + 84, legend_x + 78, legend_y + 84, color="#059669", width=1.8, marker="arrow-green", dash="5,4")
text(legend_x + 90, legend_y + 89, "基础设施支撑", size=13, fill="#475569", weight=600)

add("</svg>")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)
