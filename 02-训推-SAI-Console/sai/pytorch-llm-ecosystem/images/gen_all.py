# -*- coding: utf-8 -*-
from pathlib import Path
import html
import os


BASE = Path(__file__).resolve().parent
os.chdir(BASE)

FONT = "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', Helvetica, Arial, sans-serif"
PALETTE = ["#7c3aed", "#2563eb", "#0891b2", "#dc2626", "#ea580c", "#059669", "#d97706", "#4f46e5", "#db2777"]
REAL = "#2563eb"
ADJ = "#059669"
THEORY = "#d97706"
RISK = "#dc2626"
TEXT = "#0f172a"
SUB = "#334155"


def esc(s):
    return html.escape(str(s), quote=True)


def tw(s, fs=21):
    return sum((fs * 1.02 if ord(c) > 0x2E80 else fs * 0.56) for c in s)


def wrap(s, max_width, fs=20):
    lines, cur = [], ""
    for ch in s:
        cand = cur + ch
        if cur and tw(cand, fs) > max_width:
            lines.append(cur)
            cur = ch
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def write(name, lines):
    lines.append("</svg>")
    Path(name).write_text("\n".join(lines), encoding="utf-8")


def svg_open(w, h, bg="#f8fafc"):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">',
        f"<style>text {{ font-family: {FONT}; }}</style>",
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{bg}"/>',
        """<defs>
  <marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#2563eb"/></marker>
  <marker id="arrow-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#059669"/></marker>
  <marker id="arrow-orange" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#d97706"/></marker>
  <marker id="arrow-red" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#dc2626"/></marker>
</defs>""",
    ]


def text(L, x, y, s, fs=20, fill=TEXT, weight=400, anchor="start"):
    L.append(f'<text x="{x}" y="{y}" fill="{fill}" font-size="{fs}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')


def box(L, x, y, w, h, title, body=None, fill="#ffffff", stroke="#cbd5e1", accent=None):
    L.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    if accent:
        L.append(f'<rect x="{x}" y="{y}" width="9" height="{h}" rx="4" fill="{accent}"/>')
    text(L, x + w / 2, y + 36, title, fs=23, fill=TEXT, weight=800, anchor="middle")
    if body:
        rows = []
        for item in body:
            rows.extend(wrap(item, w - 44, 19))
        yy = y + 72
        for row in rows[:6]:
            text(L, x + 24, yy, row, fs=19, fill=SUB)
            yy += 27


def arrow(L, x1, y1, x2, y2, color=REAL, marker="arrow-blue", dash=False):
    dash_attr = ' stroke-dasharray="7 5"' if dash else ""
    L.append(f'<path d="M {x1},{y1} L {x2},{y2}" fill="none" stroke="{color}" stroke-width="3"{dash_attr} marker-end="url(#{marker})"/>')


def label(L, x, y, s, color=SUB, w=None):
    w = w or max(110, int(tw(s, 17) + 24))
    L.append(f'<rect x="{x - w / 2}" y="{y - 19}" width="{w}" height="27" rx="6" fill="#ffffff" opacity="0.96"/>')
    text(L, x, y, s, fs=17, fill=color, weight=700, anchor="middle")


def legend(L, x, y):
    items = [(REAL, "真实生产经验"), (ADJ, "相邻经验/可迁移"), (THEORY, "理论对标"), (RISK, "不能夸大")]
    for i, (c, s) in enumerate(items):
        xx = x + i * 260
        L.append(f'<rect x="{xx}" y="{y - 18}" width="28" height="20" rx="4" fill="{c}"/>')
        text(L, xx + 40, y, s, fs=18, fill=SUB, weight=700)


def mindmap():
    def N(t, *ch):
        return {"t": t, "children": list(ch)}

    root = N(
        "PyTorch体系·LLM托管",
        N("经验边界", N("SAI/TFJob是真实经验"), N("PyTorch/LLM是相邻对标"), N("不冒充LLM SRE")),
        N("为什么学", N("面试官期待LLM生态"), N("承接PAI也要懂语义"), N("从控制台到模型平台")),
        N("PyTorch核心", N("Tensor/nn.Module"), N("autograd训练"), N("torch.compile")),
        N("训练生态", N("DDP/FSDP"), N("DeepSpeed ZeRO"), N("Transformers/LoRA")),
        N("Serving生态", N("vLLM/TTFT/TPOT"), N("Triton/TRT-LLM"), N("OpenAI兼容API")),
        N("平台演进", N("TrainingProvider"), N("ModelVersion/EvalJob"), N("LLMRuntimeProvider")),
        N("SRE排障", N("Pending/OOM/卡死"), N("NCCL/显存/KV Cache"), N("观测到token级")),
        N("面试话术", N("讲迁移能力"), N("讲落地设计"), N("讲边界和不能说")),
    )
    FS, ROW, TOP, GAP, PADW = 21, 48, 50, 68, 12

    for i, child in enumerate(root["children"]):
        col = PALETTE[i % len(PALETTE)]

        def paint(n):
            n["color"] = col
            for k in n["children"]:
                paint(k)

        paint(child)
    root["color"] = "#475569"

    cnt = [0]

    def assign(n, d):
        n["depth"] = d
        if n["children"]:
            for k in n["children"]:
                assign(k, d + 1)
            n["y"] = (n["children"][0]["y"] + n["children"][-1]["y"]) / 2
        else:
            n["y"] = TOP + cnt[0] * ROW
            cnt[0] += 1

    assign(root, 0)
    all_nodes = []

    def collect(n):
        all_nodes.append(n)
        for k in n["children"]:
            collect(k)

    collect(root)
    max_depth = max(n["depth"] for n in all_nodes)
    maxw = {}
    for n in all_nodes:
        maxw[n["depth"]] = max(maxw.get(n["depth"], 0), tw(n["t"], FS) + PADW * 2)
    root_w = tw(root["t"], 24) + 52
    colx = {0: 40, 1: 40 + root_w + GAP}
    for d in range(2, max_depth + 1):
        colx[d] = colx[d - 1] + maxw[d - 1] + GAP
    for n in all_nodes:
        n["x"] = colx[n["depth"]]
        n["w"] = tw(n["t"], FS) + PADW * 2
    vw = int(max(n["x"] + n["w"] for n in all_nodes) + 60)
    vh = int(TOP + cnt[0] * ROW + 35)
    rc = root["y"]
    L = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}">', f"<style>text {{ font-family: {FONT}; }}</style>", f'<rect width="{vw}" height="{vh}" fill="#ffffff"/>']

    def conn(n):
        px, py = (40 + root_w, rc) if n["depth"] == 0 else (n["x"] + n["w"], n["y"])
        for k in n["children"]:
            cx, cy = k["x"], k["y"]
            dx = (cx - px) * 0.52
            L.append(f'<path d="M {px:.1f},{py:.1f} C {px+dx:.1f},{py:.1f} {cx-dx:.1f},{cy:.1f} {cx:.1f},{cy:.1f}" fill="none" stroke="{k["color"]}" stroke-width="2.8" stroke-linecap="round"/>')
            conn(k)

    conn(root)
    L.append(f'<rect x="40" y="{rc - 30:.1f}" width="{root_w:.1f}" height="60" rx="12" fill="#1e293b"/>')
    text(L, 40 + root_w / 2, rc + 8, root["t"], fs=24, fill="#ffffff", weight=800, anchor="middle")
    for n in all_nodes:
        if n["depth"] == 0:
            continue
        x, y, w, c = n["x"], n["y"], n["w"], n["color"]
        L.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+w:.1f}" y2="{y:.1f}" stroke="{c}" stroke-width="2.8" stroke-linecap="round"/>')
        fill = c if n["depth"] == 1 else "#1f2937"
        weight = 800 if n["depth"] == 1 else 400
        text(L, x + PADW, y - 9, n["t"], fs=FS, fill=fill, weight=weight)
    write("00_pytorch_llm_ecosystem_overview_mindmap.svg", L)


def architecture():
    W, H = 2200, 1260
    L = svg_open(W, H)
    text(L, 70, 66, "PyTorch 体系到 LLM 托管生态：平台侧理解分层", fs=34, fill=TEXT, weight=800)
    text(L, 70, 104, "重点不是假装写过框架，而是把训练框架、分布式优化、模型产物、推理 runtime 和 SAI/PAI 托管语义接起来。", fs=21, fill="#475569", weight=600)
    legend(L, 70, 150)

    bands = [
        (225, "业务/模型层", "#fff1f2", RISK, [
            ("训练脚本", ["模型结构、loss、数据读取", "业务侧负责"]),
            ("Transformers生态", ["HF Trainer、PEFT/LoRA", "模型开发者主阵地"]),
            ("评测与Prompt", ["业务评测集、安全集", "上线门禁输入"]),
        ]),
        (455, "PyTorch框架层", "#fffbeb", THEORY, [
            ("Tensor / Module", ["Tensor计算、nn.Module", "参数与算子表达"]),
            ("autograd", ["前向构图、反向求导", "训练显存来源"]),
            ("torch.compile", ["Dynamo捕获图、Inductor优化", "性能优化对标"]),
        ]),
        (685, "分布式训练层", "#eef2ff", THEORY, [
            ("DDP", ["数据并行、AllReduce", "扩吞吐不省显存"]),
            ("FSDP / ZeRO", ["参数/梯度/优化器分片", "拿通信换显存"]),
            ("torchrun / rendezvous", ["多进程启动与发现", "卡死排查入口"]),
        ]),
        (915, "托管与Serving层", "#ecfdf5", ADJ, [
            ("TrainingProvider", ["PyTorchJob / PAI-DLC", "训练语义适配"]),
            ("ModelVersion / EvalJob", ["模型版本、评测报告", "发布可追溯"]),
            ("LLMRuntimeProvider", ["vLLM / Triton / PAI EAS", "TTFT/TPOT/KV Cache"]),
        ]),
    ]
    for y, title_, fill, color, nodes in bands:
        L.append(f'<rect x="55" y="{y-45}" width="2090" height="195" rx="18" fill="{fill}" stroke="{color}" stroke-width="1.7"/>')
        text(L, 78, y - 10, title_, fs=24, fill=color, weight=800)
        x = 360
        for t, body in nodes:
            box(L, x, y - 25, 500, 130, t, body, fill="#ffffff", stroke=color, accent=color)
            x += 560

    # Infrastructure
    L.append('<rect x="55" y="1120" width="2090" height="90" rx="16" fill="#ffffff" stroke="#0f172a" stroke-width="2"/>')
    text(L, 1100, 1157, "真实经验底座：SAI 控制面 / TFJob / Provider / GPU资源池 / PAI托管 / 日志事件指标", fs=24, fill=TEXT, weight=800, anchor="middle")
    text(L, 1100, 1193, "能迁移的能力：提交入口、资源准入、生命周期、状态同步、观测排障、灰度回滚、成本治理", fs=21, fill=SUB, weight=600, anchor="middle")
    write("01_pytorch_llm_stack_architecture.svg", L)


def flow():
    W, H = 2300, 1120
    L = svg_open(W, H)
    text(L, 70, 66, "从 PyTorch 训练到 LLM 托管上线：SRE 该看哪些状态", fs=34, fill=TEXT, weight=800)
    legend(L, 70, 112)
    y1, y2 = 180, 520
    w, h, gap = 300, 160, 42
    top = [
        ("DatasetVersion", ["SFT/偏好/评测集", "数据血缘与质量"]),
        ("PyTorch训练代码", ["Tensor/Module/autograd", "业务侧主导"]),
        ("分布式启动", ["torchrun/DDP/FSDP", "rendezvous/NCCL"]),
        ("Checkpoint", ["分片权重/优化器状态", "断点续训"]),
        ("ModelVersion", ["权重/tokenizer/config", "LoRA/量化/模板"]),
        ("EvalJob", ["业务集/安全集/回归集", "上线门禁"]),
    ]
    x = 70
    prev = None
    for i, (t, b) in enumerate(top):
        color = THEORY if 1 <= i <= 3 else ADJ
        fill = "#fffbeb" if color == THEORY else "#ecfdf5"
        box(L, x, y1, w, h, t, b, fill=fill, stroke=color, accent=color)
        if prev:
            arrow(L, prev + w + 8, y1 + h / 2, x - 8, y1 + h / 2, color=REAL, marker="arrow-blue")
        prev = x
        x += w + gap
    bottom = [
        ("ServingService", ["PAI EAS / vLLM / Triton", "模型加载与warmup"]),
        ("Gateway/API", ["OpenAI兼容/鉴权/限流", "灰度/fallback"]),
        ("RAG/Agent应用", ["知识库/工具/会话", "效果问题归因"]),
        ("Token观测", ["TTFT/TPOT/tokens/s", "KV Cache/显存"]),
        ("Feedback闭环", ["差评/异常/人工标注", "回流评测集"]),
    ]
    x = 250
    prev = None
    for i, (t, b) in enumerate(bottom):
        color = ADJ if i < 4 else REAL
        fill = "#ecfdf5" if color == ADJ else "#eff6ff"
        box(L, x, y2, 330, h, t, b, fill=fill, stroke=color, accent=color)
        if prev:
            arrow(L, prev + 330 + 10, y2 + h / 2, x - 10, y2 + h / 2, color=REAL, marker="arrow-blue")
        prev = x
        x += 380
    # Downstream publish
    arrow(L, 70 + 5 * (w + gap) + w / 2, y1 + h + 10, 250 + 165, y2 - 16, color=ADJ, marker="arrow-green")
    label(L, 1160, 453, "通过门禁后发布", color=ADJ, w=150)
    # Feedback loop
    L.append(f'<path d="M {250+4*380+165},{y2+h} L {250+4*380+165},910 L 70,910 L 70,{y1+h/2}" fill="none" stroke="{REAL}" stroke-width="3" stroke-dasharray="8 6" marker-end="url(#arrow-blue)"/>')
    label(L, 320, 900, "线上反馈回流", color=REAL, w=140)
    # SRE lane
    L.append('<rect x="70" y="760" width="2160" height="115" rx="16" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>')
    text(L, 110, 801, "SRE/平台侧抓手", fs=24, fill=TEXT, weight=800)
    text(L, 110, 839, "资源准入、Pod/Job事件、rank日志、checkpoint完整性、模型加载ready、warmup、TTFT/TPOT、显存/KV Cache、灰度回滚", fs=21, fill=SUB, weight=600)
    write("02_pytorch_training_to_serving_flow.svg", L)


def mapping():
    W, H = 2200, 1160
    L = svg_open(W, H)
    text(L, 70, 66, "从 TFJob/PAI 真实经验迁移到 LLM 生态：能说什么、不能说什么", fs=34, fill=TEXT, weight=800)
    legend(L, 70, 112)
    cols = [
        (70, "真实做过/可证明", REAL, "#eff6ff", [
            ("SAI控制面", "统一入口、Provider、生命周期、状态同步"),
            ("TFJob主力承接", "训练任务、TensorBoard、日志、事件、潮汐/待退"),
            ("推理服务托管", "PAI/贝联/ACK Provider、扩缩容、服务状态"),
            ("GPU平台排障", "Pending、OOMKill、镜像、PVC、节点池、配额"),
        ]),
        (770, "可迁移到LLM的能力", ADJ, "#ecfdf5", [
            ("TrainingProvider", "底层可适配 PyTorchJob / PAI-DLC / DeepSpeed模板"),
            ("ModelVersion", "权重、tokenizer、config、LoRA、评测报告绑定"),
            ("LLMRuntimeProvider", "vLLM/Triton/PAI EAS 的创建、ready、扩缩容"),
            ("Token级观测", "TTFT、TPOT、tokens/s、KV Cache、成本/千token"),
        ]),
        (1470, "只能理论对标", THEORY, "#fffbeb", [
            ("PyTorch内核", "autograd、Dynamo/Inductor、算子优化"),
            ("分布式算法", "FSDP/ZeRO/PP/TP 的实现细节"),
            ("推理引擎内核", "PagedAttention、continuous batching、TRT engine"),
            ("大模型效果", "评测集、偏好对齐、LLM-as-Judge 偏差"),
        ]),
    ]
    for x, title_, color, fill, items in cols:
        L.append(f'<rect x="{x}" y="160" width="650" height="700" rx="18" fill="{fill}" stroke="{color}" stroke-width="2"/>')
        text(L, x + 325, 210, title_, fs=25, fill=color, weight=800, anchor="middle")
        y = 255
        for t, b in items:
            box(L, x + 35, y, 580, 125, t, [b], fill="#ffffff", stroke=color, accent=color)
            y += 145
    arrow(L, 720, 510, 760, 510, color=ADJ, marker="arrow-green")
    arrow(L, 1420, 510, 1460, 510, color=THEORY, marker="arrow-orange")
    L.append('<rect x="70" y="920" width="2050" height="160" rx="18" fill="#fef2f2" stroke="#dc2626" stroke-width="2.2"/>')
    text(L, 110, 965, "面试红线", fs=26, fill=RISK, weight=900)
    text(L, 110, 1005, "不能说：我负责过 LLM 服务 SRE / 自研 PyTorch 训练框架 / 自研 vLLM 或 TensorRT-LLM / 做过大模型效果闭环收益。", fs=22, fill=SUB, weight=700)
    text(L, 110, 1045, "可以说：我做的是 SAI/PAI/TFJob 的平台治理经验，正在按 PyTorch 和 LLM 生态做对标，能讲清如果演进该补哪些对象、状态和排障抓手。", fs=22, fill=SUB, weight=700)
    write("03_experience_boundary_mapping.svg", L)


mindmap()
architecture()
flow()
mapping()
print("generated")
