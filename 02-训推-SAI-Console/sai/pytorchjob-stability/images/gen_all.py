from html import escape
from pathlib import Path
import subprocess

OUT = Path(__file__).parent

W = 1600
H = 960
BG = "#ffffff"
TEXT = "#111827"
SUB = "#475569"
MUTED = "#64748b"
BLUE = "#2563eb"
RED = "#dc2626"
GREEN = "#16a34a"
PURPLE = "#9333ea"
ORANGE = "#ea580c"
TEAL = "#0891b2"
BORDER = "#cbd5e1"
SOFT = {
    "blue": "#eff6ff",
    "red": "#fef2f2",
    "green": "#f0fdf4",
    "purple": "#faf5ff",
    "orange": "#fff7ed",
    "teal": "#f0fdfa",
    "gray": "#f8fafc",
}


def wrap(s, n):
    out, cur, width = [], "", 0
    for ch in s:
        w = 2 if ord(ch) > 127 else 1
        if width + w > n and cur:
            out.append(cur)
            cur, width = ch, w
        else:
            cur += ch
            width += w
    if cur:
        out.append(cur)
    return out


def header(lines, title, subtitle=None, w=W, h=H):
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">')
    lines.append("<style>")
    lines.append("text { font-family: 'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif; }")
    lines.append("</style>")
    lines.append("<defs>")
    for name, color in [("blue", BLUE), ("red", RED), ("green", GREEN), ("purple", PURPLE), ("orange", ORANGE), ("teal", TEAL), ("gray", MUTED)]:
        lines.append(f'<marker id="arrow-{name}" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">')
        lines.append(f'<polygon points="0 0, 10 3.5, 0 7" fill="{color}"/>')
        lines.append("</marker>")
    lines.append('<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">')
    lines.append('<feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.14"/>')
    lines.append("</filter>")
    lines.append("</defs>")
    lines.append(f'<rect width="{w}" height="{h}" fill="{BG}"/>')
    lines.append(f'<text x="60" y="62" fill="{TEXT}" font-size="30" font-weight="800">{escape(title)}</text>')
    if subtitle:
        lines.append(f'<text x="60" y="96" fill="{SUB}" font-size="17">{escape(subtitle)}</text>')


def text(lines, x, y, s, fs=16, fill=TEXT, weight=400, anchor="start"):
    lines.append(f'<text x="{x}" y="{y}" fill="{fill}" font-size="{fs}" font-weight="{weight}" text-anchor="{anchor}">{escape(s)}</text>')


def box(lines, x, y, w, h, title, items=None, fill="#ffffff", stroke=BORDER, title_color=TEXT, item_color=SUB, accent=None, fs=18, item_fs=14):
    lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.6" filter="url(#shadow)"/>')
    if accent:
        lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="8" rx="4" fill="{accent}"/>')
    text(lines, x + w / 2, y + 36, title, fs=fs, fill=title_color, weight=800, anchor="middle")
    yy = y + 68
    if items:
        for item in items:
            for i, ln in enumerate(wrap(item, max(18, int((w - 36) / 8)))):
                text(lines, x + 22, yy, ("• " if i == 0 else "  ") + ln, fs=item_fs, fill=item_color)
                yy += item_fs + 7
            yy += 4


def pill(lines, x, y, w, h, label, color):
    lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{color}" stroke="{color}" stroke-width="1"/>')
    text(lines, x + w / 2, y + h / 2 + 6, label, fs=15, fill="#ffffff", weight=700, anchor="middle")


def arrow(lines, x1, y1, x2, y2, color=BLUE, marker="blue", label=None, dashed=False):
    dash = ' stroke-dasharray="7,5"' if dashed else ""
    lines.append(f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="{color}" stroke-width="2.2"{dash} marker-end="url(#arrow-{marker})"/>')
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 8
        lw = max(70, len(label) * 15)
        lines.append(f'<rect x="{mx - lw/2}" y="{my - 18}" width="{lw}" height="24" rx="6" fill="#ffffff" opacity="0.96"/>')
        text(lines, mx, my, label, fs=13, fill=MUTED, weight=700, anchor="middle")


def orth(lines, pts, color=BLUE, marker="blue", label=None, dashed=False):
    dash = ' stroke-dasharray="7,5"' if dashed else ""
    d = "M " + " L ".join(f"{x} {y}" for x, y in pts)
    lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2"{dash} marker-end="url(#arrow-{marker})"/>')
    if label:
        x, y = pts[len(pts) // 2]
        lw = max(80, len(label) * 14)
        lines.append(f'<rect x="{x - lw/2}" y="{y - 22}" width="{lw}" height="24" rx="6" fill="#ffffff" opacity="0.96"/>')
        text(lines, x, y - 4, label, fs=13, fill=MUTED, weight=700, anchor="middle")


def write_svg(name, lines):
    lines.append("</svg>")
    p = OUT / name
    p.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(["rsvg-convert", str(p), "-o", "/tmp/pytorchjob-test.png"], check=True)
    subprocess.run(["rsvg-convert", "-w", "1920", str(p), "-o", str(p.with_suffix(".png"))], check=True)


def overview():
    lines = []
    header(lines, "PyTorchJob 稳定性治理总览", "从 CRD 字段、GPU 调度、分布式启动到 SRE 排障闭环")
    box(lines, 620, 375, 360, 150, "PyTorchJob\n稳定性治理".replace("\n", " "), ["不是只会创建 CRD", "重点是 GPU / gang / rank / NCCL / checkpoint"], fill="#111827", stroke="#111827", title_color="#ffffff", item_color="#cbd5e1", fs=24)
    branches = [
        (90, 160, "API 资源模型", ["apiVersion/kind/namespaced", "runPolicy", "replicaSpecs", "elasticPolicy"], BLUE, "blue"),
        (90, 620, "GPU 调度治理", ["NodePool", "GPU limits", "queue/gang", "拓扑/RDMA"], GREEN, "green"),
        (620, 130, "分布式启动", ["Master/rank0", "Worker ranks", "rendezvous", "world_size"], PURPLE, "purple"),
        (1090, 160, "运行观测", ["condition", "replicaStatuses", "Pod/Event/Logs", "GPU/NCCL"], ORANGE, "orange"),
        (1090, 620, "排障闭环", ["Pending", "rendezvous hang", "NCCL timeout", "OOM/慢训练"], RED, "red"),
        (620, 680, "SAI 项目边界", ["控制面/资源池/状态同步", "不自研 Scheduler", "不夸大 NCCL 内核"], TEAL, "teal"),
    ]
    for x, y, title_, items, color, marker in branches:
        box(lines, x, y, 330, 190, title_, items, fill=SOFT[marker], stroke=color, accent=color)
        arrow(lines, x + 330 if x < 620 else x, y + 95, 620 if x < 620 else 980, 450, color=color, marker=marker)
    text(lines, 800, 910, "面试主线：先讲资源/状态/调度治理，再进入 PyTorch 分布式细节；始终声明 SAI 的真实边界。", fs=17, fill=SUB, weight=700, anchor="middle")
    write_svg("00_pytorchjob_stability_overview_mindmap.svg", lines)


def principle():
    lines = []
    header(lines, "PyTorchJob 运行原理与 SRE 观测边界", "从 SAI 控制面到底层 GPU/NCCL 的责任分层")
    box(lines, 60, 150, 310, 130, "SAI 控制面", ["表单/模板", "NodePool/配额", "提交与状态同步"], fill=SOFT["blue"], stroke=BLUE, accent=BLUE)
    box(lines, 460, 150, 310, 130, "PyTorchJob CRD", ["runPolicy", "Master/Worker", "elasticPolicy"], fill=SOFT["purple"], stroke=PURPLE, accent=PURPLE)
    box(lines, 860, 150, 310, 130, "Training Operator", ["reconcile", "创建 Pods/Services", "更新 conditions"], fill=SOFT["orange"], stroke=ORANGE, accent=ORANGE)
    box(lines, 1250, 150, 290, 130, "K8s 调度器/队列", ["Kueue/Volcano", "quota/gang", "suspend/admit"], fill=SOFT["green"], stroke=GREEN, accent=GREEN)
    arrow(lines, 370, 215, 460, 215, BLUE, "blue", "create")
    arrow(lines, 770, 215, 860, 215, PURPLE, "purple", "watch")
    arrow(lines, 1170, 215, 1250, 215, GREEN, "green", "admit")

    box(lines, 160, 405, 360, 170, "Master / rank0 Pod", ["torchrun 启动", "MASTER_ADDR/PORT", "完成/失败信号常从 rank0 收敛"], fill="#ffffff", stroke=BLUE, accent=BLUE)
    box(lines, 620, 405, 360, 170, "Worker Pods", ["同构 ranks", "requests/limits nvidia.com/gpu", "nodeSelector/tolerations/affinity"], fill="#ffffff", stroke=GREEN, accent=GREEN)
    box(lines, 1080, 405, 360, 170, "Service / Rendezvous", ["rank 发现", "端口可达", "elastic 时 min/max 重集合"], fill="#ffffff", stroke=PURPLE, accent=PURPLE)
    arrow(lines, 1250, 280, 800, 405, GREEN, "green", "schedule")
    arrow(lines, 520, 490, 620, 490, BLUE, "blue", "all ranks")
    arrow(lines, 980, 490, 1080, 490, PURPLE, "purple", "rendezvous")

    box(lines, 160, 710, 360, 130, "GPU 节点与设备插件", ["NVIDIA/厂商 GPU 插件", "显存/卡数/故障 XID", "驱动/CUDA/NCCL 版本"], fill=SOFT["gray"], stroke=BORDER, accent=RED)
    box(lines, 620, 710, 360, 130, "通信与拓扑", ["NVLink/PCIe/IB/RDMA", "NCCL all-reduce", "同 rack/同 RDMA 域"], fill=SOFT["gray"], stroke=BORDER, accent=TEAL)
    box(lines, 1080, 710, 360, 130, "存储与 Checkpoint", ["NAS/OSS/PVC", "checkpoint 保存/恢复", "日志与 TensorBoard"], fill=SOFT["gray"], stroke=BORDER, accent=ORANGE)
    orth(lines, [(340, 575), (340, 710)], RED, "red", "device")
    orth(lines, [(800, 575), (800, 710)], TEAL, "teal", "NCCL")
    orth(lines, [(1260, 575), (1260, 710)], ORANGE, "orange", "state")
    text(lines, 800, 910, "SRE 观测要把 CRD 状态、Pod/Event、GPU 指标、rank 日志、checkpoint 统一到一个 Job 视角。", fs=17, fill=SUB, weight=700, anchor="middle")
    write_svg("01_pytorchjob_principle.png".replace(".png", ".svg"), lines)


def mechanism():
    lines = []
    header(lines, "PyTorchJob GPU 调度关键机制", "把平台资源意图落到 queue/gang/PodSpec/topology")
    box(lines, 70, 145, 300, 160, "1. 准入与画像", ["任务规模：nodes × gpu/node", "卡型/显存/优先级", "checkpoint/可重试"], fill=SOFT["blue"], stroke=BLUE, accent=BLUE)
    box(lines, 445, 145, 300, 160, "2. 队列与配额", ["Kueue queue label", "runPolicy.suspend", "ClusterQueue/ResourceFlavor"], fill=SOFT["green"], stroke=GREEN, accent=GREEN)
    box(lines, 820, 145, 300, 160, "3. Gang / PodGroup", ["all-or-nothing", "避免部分 rank 占卡", "Volcano/coscheduling"], fill=SOFT["purple"], stroke=PURPLE, accent=PURPLE)
    box(lines, 1195, 145, 300, 160, "4. PodSpec 落地", ["GPU limits", "nodeSelector/tolerations", "affinity/topology"], fill=SOFT["orange"], stroke=ORANGE, accent=ORANGE)
    arrow(lines, 370, 225, 445, 225, BLUE, "blue")
    arrow(lines, 745, 225, 820, 225, GREEN, "green")
    arrow(lines, 1120, 225, 1195, 225, PURPLE, "purple")

    box(lines, 170, 425, 330, 170, "资源池分层", ["稳定 GPU 池：关键训练/在线", "共享显存池：小模型/低风险", "抢占池：低 QoS 可恢复任务"], fill="#ffffff", stroke=BORDER, accent=TEAL)
    box(lines, 635, 425, 330, 170, "拓扑约束", ["单机多卡优先 NVLink/NVSwitch", "多机优先同 rack/RDMA 域", "避免跨慢链路拼凑 ranks"], fill="#ffffff", stroke=BORDER, accent=RED)
    box(lines, 1100, 425, 330, 170, "运行时兜底", ["NCCL 超时", "rank 心跳", "checkpoint 恢复/退避"], fill="#ffffff", stroke=BORDER, accent=ORANGE)
    orth(lines, [(1345, 305), (1345, 365), (335, 365), (335, 425)], ORANGE, "orange", "placement")
    arrow(lines, 500, 510, 635, 510, TEAL, "teal", "topology")
    arrow(lines, 965, 510, 1100, 510, RED, "red", "runtime")

    box(lines, 260, 725, 1080, 110, "稳定性判断", ["不是“调度成功”就结束：必须确认所有 rank ready、rendezvous 完成、GPU/NCCL 正常、checkpoint 可落盘、训练 step 有推进。"], fill="#111827", stroke="#111827", title_color="#ffffff", item_color="#cbd5e1", fs=22)
    write_svg("02_pytorchjob_gpu_scheduling_mechanism.svg", lines)


def scenario():
    lines = []
    header(lines, "SAI 承接 PyTorchJob 的场景映射", "从 TFJob 真实经验迁移到 PyTorch 分布式训练治理")
    box(lines, 80, 160, 380, 240, "TFJob 主力经验", ["训练任务托管", "NodePool/资源规格", "TensorBoard/日志/NAS", "watcher 状态同步", "Pending/OOM/PVC 排查"], fill=SOFT["blue"], stroke=BLUE, accent=BLUE)
    box(lines, 610, 160, 380, 240, "PyTorchJob 补齐对象", ["Master/Worker rank", "rendezvous/torchrun", "NCCL/RDMA", "elasticPolicy", "checkpoint shards"], fill=SOFT["purple"], stroke=PURPLE, accent=PURPLE)
    box(lines, 1140, 160, 380, 240, "LLM/多模态训练", ["DDP/FSDP/DeepSpeed", "LoRA/SFT", "大模型 checkpoint", "评测与发布门禁"], fill=SOFT["green"], stroke=GREEN, accent=GREEN)
    arrow(lines, 460, 280, 610, 280, BLUE, "blue", "迁移")
    arrow(lines, 990, 280, 1140, 280, GREEN, "green", "演进")

    box(lines, 160, 555, 330, 190, "能安全说", ["我做过 SAI/TFJob 平台治理", "能把资源/状态/观测迁移到 PyTorchJob", "能按症状排查 rank/NCCL/GPU"], fill="#ffffff", stroke=GREEN, accent=GREEN)
    box(lines, 635, 555, 330, 190, "谨慎表达", ["PyTorchJob 是相邻承接/演进方向", "NCCL/FSDP/DeepSpeed 是理解和排查", "PAI 可以作为执行面"], fill="#ffffff", stroke=ORANGE, accent=ORANGE)
    box(lines, 1110, 555, 330, 190, "不能夸大", ["不说自研 GPU Scheduler", "不说深度调 NCCL 内核", "不说负责过生产 LLM SRE"], fill="#ffffff", stroke=RED, accent=RED)
    text(lines, 800, 875, "面试落点：平台 SRE 负责把 PyTorch 分布式训练变成可提交、可排队、可观测、可恢复、可复盘的工作负载。", fs=18, fill=SUB, weight=800, anchor="middle")
    write_svg("03_pytorchjob_sai_scenario.svg", lines)


def troubleshooting():
    lines = []
    header(lines, "PyTorchJob SRE 排障决策树", "症状 -> 假设 -> 验证 -> 指标 -> 结论 -> 优化")
    symptoms = [
        ("Pending / 起不来", "queue/gang/quota/nodePool/PVC/image", BLUE, "blue", 150),
        ("Running 但卡住", "rendezvous/rank 不齐/master 不可达", PURPLE, "purple", 330),
        ("NCCL timeout / 慢", "拓扑/RDMA/版本/掉队 rank", RED, "red", 510),
        ("OOM / 反复重启", "CUDA OOM/K8s OOMKill/checkpoint 恢复失败", ORANGE, "orange", 690),
    ]
    box(lines, 65, 395, 260, 120, "入口症状", ["先不要直接归因", "先定位卡在哪一层"], fill="#111827", stroke="#111827", title_color="#ffffff", item_color="#cbd5e1", fs=20)
    for title_, sub, color, marker, y in symptoms:
        box(lines, 455, y, 345, 115, title_, [sub], fill=SOFT[marker], stroke=color, accent=color, fs=18)
        orth(lines, [(325, 455), (390, 455), (390, y + 58), (455, y + 58)], color, marker)
        box(lines, 965, y, 455, 115, "验证抓手", [
            "kubectl get/describe pytorchjob,pod,event",
            "rank0/worker logs + GPU/NCCL metrics",
        ], fill="#ffffff", stroke=BORDER, accent=color, fs=18)
        arrow(lines, 800, y + 58, 965, y + 58, color, marker, "verify")
    box(lines, 540, 835, 520, 80, "收口动作", ["补准入校验、放宽/收紧拓扑、退避熔断、checkpoint 恢复、节点隔离、版本基线回归"], fill="#111827", stroke="#111827", title_color="#ffffff", item_color="#cbd5e1", fs=21)
    orth(lines, [(1190, 805), (1190, 875), (1060, 875)], GREEN, "green", "fix")
    write_svg("04_pytorchjob_troubleshooting.svg", lines)


def main():
    for fn in [overview, principle, mechanism, scenario, troubleshooting]:
        fn()
    print("generated PyTorchJob diagrams")


if __name__ == "__main__":
    main()
