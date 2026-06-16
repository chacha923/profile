from html import escape
from pathlib import Path
import subprocess

OUT = Path(__file__).parent
FS = 19
ROOT_FS = 20
ROW = 48
TOP = 50
GAP = 75
PADW = 10
PALETTE = ["#7c3aed", "#2563eb", "#0891b2", "#dc2626", "#ea580c", "#059669", "#d97706", "#4f46e5", "#db2777"]


def N(t, *children):
    return {"t": t, "children": list(children)}


def text_width(s, fs=FS):
    return sum((fs * 1.02 if ord(c) > 0x2E80 else fs * 0.56) for c in s)


def paint(node, color):
    node["color"] = color
    for child in node["children"]:
        paint(child, color)


def assign_y(node, depth, counter):
    node["depth"] = depth
    if node["children"]:
        for child in node["children"]:
            assign_y(child, depth + 1, counter)
        node["y"] = (node["children"][0]["y"] + node["children"][-1]["y"]) / 2.0
    else:
        node["y"] = TOP + counter[0] * ROW
        counter[0] += 1


def collect(node, out):
    out.append(node)
    for child in node["children"]:
        collect(child, out)


def render(root, filename):
    for i, child in enumerate(root["children"]):
        paint(child, PALETTE[i % len(PALETTE)])
    root["color"] = "#475569"

    counter = [0]
    assign_y(root, 0, counter)
    nodes = []
    collect(root, nodes)
    max_depth = max(n["depth"] for n in nodes)
    maxw = {}
    for n in nodes:
        maxw[n["depth"]] = max(maxw.get(n["depth"], 0), text_width(n["t"]) + PADW * 2)

    root_w = text_width(root["t"], ROOT_FS) + 44
    colx = {0: 40, 1: 40 + root_w + GAP}
    for d in range(2, max_depth + 1):
        colx[d] = colx[d - 1] + maxw[d - 1] + GAP
    for n in nodes:
        n["x"] = colx[n["depth"]]
        n["w"] = text_width(n["t"]) + PADW * 2

    vw = int(max(n["x"] + n["w"] for n in nodes) + 60)
    vh = int(TOP + counter[0] * ROW + 40)
    root_cy = root["y"]

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{vw}" height="{vh}">')
    lines.append("<style>")
    lines.append("text { font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', Helvetica, Arial, sans-serif; }")
    lines.append("</style>")
    lines.append(f'<rect x="0" y="0" width="{vw}" height="{vh}" fill="#ffffff"/>')

    def conn(node):
        if node["depth"] == 0:
            px, py = 40 + root_w, root_cy
        else:
            px, py = node["x"] + node["w"], node["y"]
        for child in node["children"]:
            cx, cy = child["x"], child["y"]
            dx = (cx - px) * 0.52
            lines.append(
                '<path d="M %.1f,%.1f C %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'
                % (px, py, px + dx, py, cx - dx, cy, cx, cy, child["color"])
            )
            conn(child)

    conn(root)

    rh = 50
    lines.append(f'<rect x="40" y="{root_cy - rh / 2:.1f}" width="{root_w:.1f}" height="{rh}" rx="11" fill="#1e293b"/>')
    lines.append(f'<text x="{40 + root_w / 2:.1f}" y="{root_cy + 7:.1f}" text-anchor="middle" fill="#ffffff" font-size="{ROOT_FS}" font-weight="700">{escape(root["t"])}</text>')
    for n in nodes:
        if n["depth"] == 0:
            continue
        x, y, w, color = n["x"], n["y"], n["w"], n["color"]
        lines.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + w:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="2.4" stroke-linecap="round"/>')
        weight = "700" if n["depth"] == 1 else "400"
        fill = color if n["depth"] == 1 else "#1f2937"
        lines.append(f'<text x="{x + PADW:.1f}" y="{y - 8:.1f}" fill="{fill}" font-size="{FS}" font-weight="{weight}">{escape(n["t"])}</text>')
    lines.append("</svg>")

    svg = OUT / filename
    png = svg.with_suffix(".png")
    svg.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(["rsvg-convert", str(svg), "-o", "/tmp/pytorchjob-xmind-check.png"], check=True)
    subprocess.run(["rsvg-convert", "-w", "2600", str(svg), "-o", str(png)], check=True)


def main():
    render(
        N(
            "PyTorchJob稳定性",
            N("定位边界", N("SAI/TFJob真实经验"), N("PyTorchJob相邻承接"), N("不夸大NCCL内核")),
            N("资源模型", N("api-resources"), N("runPolicy"), N("replicaSpecs"), N("elasticPolicy")),
            N("GPU调度", N("NodePool"), N("Queue/Gang"), N("PodSpec落地"), N("拓扑/RDMA")),
            N("启动运行", N("Master/rank0"), N("Worker ranks"), N("rendezvous"), N("NCCL all-reduce")),
            N("观测闭环", N("conditions"), N("replicaStatuses"), N("Pod/Event/Logs"), N("GPU/Checkpoint")),
            N("排障路径", N("Pending"), N("rendezvous卡住"), N("NCCL timeout"), N("OOM/慢训练")),
            N("话术检查", N("三档背诵"), N("高频QA"), N("不能说的话")),
        ),
        "00_pytorchjob_stability_overview_mindmap.svg",
    )
    render(
        N(
            "PyTorchJob字段",
            N("资源身份", N("kubeflow.org/v1"), N("namespaced CRD"), N("plural=pytorchjobs")),
            N("runPolicy", N("suspend"), N("backoffLimit"), N("cleanPodPolicy"), N("ttlSeconds")),
            N("replicaSpecs", N("Master/Worker"), N("replicas"), N("restartPolicy"), N("PodTemplate")),
            N("GPU落点", N("resources.limits"), N("nodeSelector"), N("tolerations"), N("volumes")),
            N("elasticPolicy", N("min/max replicas"), N("rdzvBackend"), N("maxRestarts"), N("nprocPerNode")),
            N("status", N("conditions"), N("replicaStatuses"), N("start/completion"), N("lastReconcile")),
            N("平台接入", N("Runtime registry"), N("watcher映射"), N("日志/事件/指标")),
        ),
        "00_pytorchjob_api_resources_overview_mindmap.svg",
    )
    render(
        N(
            "GPU调度Runbook",
            N("调度主线", N("准入画像"), N("队列配额"), N("Gang"), N("PodSpec")),
            N("资源池", N("稳定GPU池"), N("共享显存池"), N("抢占GPU池"), N("CPU池")),
            N("队列/Gang", N("Kueue label"), N("suspend/admit"), N("Volcano/PodGroup"), N("all-or-nothing")),
            N("拓扑", N("NVLink/NVSwitch"), N("RDMA域"), N("同机型版本"), N("避免慢链路")),
            N("观测", N("Job condition"), N("Pod events"), N("GPU/DCGM"), N("NCCL/step")),
            N("排障", N("Pending"), N("部分rank"), N("rendezvous"), N("NCCL/OOM")),
            N("安全表达", N("不自研Scheduler"), N("控制面治理"), N("执行交给底座")),
        ),
        "00_pytorchjob_gpu_scheduling_overview_mindmap.svg",
    )
    print("generated xmind overview maps")


if __name__ == "__main__":
    main()
