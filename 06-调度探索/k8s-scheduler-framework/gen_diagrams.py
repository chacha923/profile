#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import html
import subprocess
from pathlib import Path


OUT = Path(__file__).resolve().parent
FONT = "-apple-system, BlinkMacSystemFont, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif"


def esc(s):
    return html.escape(str(s), quote=True)


def save_svg(name, body, width, height):
    path = OUT / f"{name}.svg"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <style>
    text {{ font-family: {FONT}; }}
  </style>
  <defs>
    <marker id="arrow-blue" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto">
      <polygon points="0 0, 12 4.5, 0 9" fill="#2563eb"/>
    </marker>
    <marker id="arrow-red" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto">
      <polygon points="0 0, 12 4.5, 0 9" fill="#dc2626"/>
    </marker>
    <marker id="arrow-green" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto">
      <polygon points="0 0, 12 4.5, 0 9" fill="#16a34a"/>
    </marker>
    <marker id="arrow-purple" markerWidth="12" markerHeight="9" refX="11" refY="4.5" orient="auto">
      <polygon points="0 0, 12 4.5, 0 9" fill="#9333ea"/>
    </marker>
  </defs>
  <rect width="{width}" height="{height}" fill="#ffffff"/>
{body}
</svg>
'''
    path.write_text(svg, encoding="utf-8")
    return path


def export_png(svg_path, width=2600):
    probe = svg_path.with_suffix(".probe.png")
    subprocess.run(["rsvg-convert", str(svg_path), "-o", str(probe)], check=True)
    probe.unlink(missing_ok=True)
    subprocess.run(["rsvg-convert", "-w", str(width), str(svg_path), "-o", str(svg_path.with_suffix(".png"))], check=True)


def text(x, y, s, size=22, color="#111827", weight=400, anchor="start"):
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>'


def wrap_cjk(s, max_units):
    lines = []
    cur = ""
    units = 0
    tokens = []
    buf = ""
    for ch in str(s):
        if ch == " ":
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(" ")
        elif ord(ch) > 0x2E80:
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        else:
            buf += ch
    if buf:
        tokens.append(buf)
    for token in tokens:
        token_units = 0.6 if token == " " else sum(1.0 if ord(c) > 0x2E80 else 0.58 for c in token)
        if token == " " and not cur:
            continue
        if cur and units + token_units > max_units:
            lines.append(cur.rstrip())
            cur = "" if token == " " else token
            units = 0 if token == " " else token_units
        else:
            cur += token
            units += token_units
    if cur:
        lines.append(cur)
    return lines


def box(x, y, w, h, title, subs=(), fill="#ffffff", stroke="#d1d5db", title_color="#111827"):
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
        text(x + 22, y + 34, title, 24, title_color, 700),
    ]
    yy = y + 68
    for s in subs:
        for line in wrap_cjk(s, max(8, int((w - 44) / 22))):
            parts.append(text(x + 22, yy, line, 19, "#374151", 400))
            yy += 28
    return "\n".join(parts)


def arrow(x1, y1, x2, y2, color="#2563eb", label=None, dashed=False, marker="arrow-blue"):
    dash = ' stroke-dasharray="8 7"' if dashed else ""
    parts = [f'<path d="M {x1},{y1} C {(x1+x2)/2},{y1} {(x1+x2)/2},{y2} {x2},{y2}" fill="none" stroke="{color}" stroke-width="3"{dash} marker-end="url(#{marker})"/>']
    if label:
        parts.append(text((x1 + x2) / 2, (y1 + y2) / 2 - 10, label, 18, color, 600, "middle"))
    return "\n".join(parts)


def make_mindmap():
    def N(t, *children):
        return {"t": t, "children": list(children)}

    root = N(
        "K8s Scheduler Framework 二开",
        N("经验边界", N("0 基础上手"), N("理论对标"), N("不包装生产主导")),
        N("调度基础", N("Pod 进入队列"), N("Scheduling Cycle"), N("Binding Cycle")),
        N("扩展点", N("Filter / Score"), N("Reserve / Permit"), N("PreBind / Bind"), N("QueueingHint")),
        N("开发路径", N("选插件点"), N("写 Go 插件"), N("注册二进制"), N("配置 Profile")),
        N("本地验证", N("kind / minikube"), N("schedulerName"), N("Event / logs")),
        N("排障上线", N("RBAC / 配置"), N("版本强绑定"), N("灰度回滚")),
        N("面试表达", N("能说清边界"), N("能讲落地"), N("能排 Pending")),
    )

    fs = 20
    row = 56
    top = 58
    gap = 92
    padw = 12
    palette = ["#7c3aed", "#2563eb", "#0891b2", "#dc2626", "#ea580c", "#059669", "#d97706"]

    def tw(s, size=fs):
        return sum(size * 1.02 if ord(c) > 0x2E80 else size * 0.58 for c in s)

    for i, child in enumerate(root["children"]):
        col = palette[i % len(palette)]

        def paint(n):
            n["color"] = col
            for k in n["children"]:
                paint(k)

        paint(child)
    root["color"] = "#475569"

    count = [0]

    def assign(n, d):
        n["depth"] = d
        if n["children"]:
            for k in n["children"]:
                assign(k, d + 1)
            n["y"] = (n["children"][0]["y"] + n["children"][-1]["y"]) / 2
        else:
            n["y"] = top + count[0] * row
            count[0] += 1

    assign(root, 0)
    nodes = []

    def collect(n):
        nodes.append(n)
        for k in n["children"]:
            collect(k)

    collect(root)
    maxd = max(n["depth"] for n in nodes)
    maxw = {}
    for n in nodes:
        maxw[n["depth"]] = max(maxw.get(n["depth"], 0), tw(n["t"]) + padw * 2)
    root_w = tw(root["t"], 22) + 46
    colx = {0: 46, 1: 46 + root_w + gap}
    for d in range(2, maxd + 1):
        colx[d] = colx[d - 1] + maxw[d - 1] + gap
    for n in nodes:
        n["x"] = colx[n["depth"]]
        n["w"] = tw(n["t"]) + padw * 2

    width = int(max(n["x"] + n["w"] for n in nodes) + 70)
    height = int(top + count[0] * row + 45)
    root_cy = root["y"]
    parts = []

    def conn(n):
        px, py = (46 + root_w, root_cy) if n["depth"] == 0 else (n["x"] + n["w"], n["y"])
        for k in n["children"]:
            cx, cy = k["x"], k["y"]
            dx = (cx - px) * 0.5
            parts.append(f'<path d="M {px:.1f},{py:.1f} C {px+dx:.1f},{py:.1f} {cx-dx:.1f},{cy:.1f} {cx:.1f},{cy:.1f}" fill="none" stroke="{k["color"]}" stroke-width="2.8" stroke-linecap="round"/>')
            conn(k)

    conn(root)
    rh = 58
    parts.append(f'<rect x="46" y="{root_cy-rh/2:.1f}" width="{root_w:.1f}" height="{rh}" rx="12" fill="#1e293b"/>')
    parts.append(text(46 + root_w / 2, root_cy + 8, root["t"], 22, "#ffffff", 700, "middle"))
    for n in nodes:
        if n["depth"] == 0:
            continue
        x, y, w, c = n["x"], n["y"], n["w"], n["color"]
        parts.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+w:.1f}" y2="{y:.1f}" stroke="{c}" stroke-width="2.8" stroke-linecap="round"/>')
        parts.append(text(x + padw, y - 9, n["t"], fs, c if n["depth"] == 1 else "#1f2937", 700 if n["depth"] == 1 else 400))
    return save_svg("00_k8s_scheduler_framework_overview_mindmap", "\n".join(parts), width, height)


def make_architecture():
    parts = [text(80, 58, "Kubernetes Scheduler Framework 二开接入架构", 34, "#111827", 700)]
    parts.append(text(80, 92, "图中区分：真实生产经验 = 平台/ACK/SAI 调度意图；理论对标对象 = 自定义 kube-scheduler 插件二开。", 21, "#6b7280"))
    parts.append(f'<rect x="60" y="130" width="560" height="610" rx="18" fill="#f0fdf4" stroke="#86efac" stroke-width="2" stroke-dasharray="10 7"/>')
    parts.append(text(86, 166, "真实生产经验：平台侧资源治理", 25, "#15803d", 700))
    parts.append(box(105, 205, 445, 130, "平台 / 控制面", ["生成 PodSpec", "nodeSelector / tolerations / resources", "必要时指定 schedulerName"], "#ffffff", "#bbf7d0"))
    parts.append(box(105, 385, 445, 125, "Kubernetes API Server", ["接收 Pod / ConfigMap / RBAC", "记录 Events 与 Binding"], "#ffffff", "#bbf7d0"))
    parts.append(box(105, 565, 445, 120, "业务 Pod / 训练任务", ["真实落地经验：SAI/ACK 调度能力接入", "不是自建 Scheduler 生产经验"], "#ffffff", "#bbf7d0"))

    parts.append(f'<rect x="690" y="130" width="780" height="610" rx="18" fill="#eff6ff" stroke="#93c5fd" stroke-width="2"/>')
    parts.append(text(716, 166, "理论对标对象：Scheduler Framework 二开", 25, "#1d4ed8", 700))
    parts.append(box(730, 205, 285, 150, "自定义 scheduler", ["复用 kube-scheduler main", "app.WithPlugin 注册", "镜像版本绑定 K8s minor"], "#ffffff", "#bfdbfe"))
    parts.append(box(1090, 205, 300, 150, "Plugin Registry", ["Name + Factory", "按 Profile 启用", "args 解析"], "#ffffff", "#bfdbfe"))
    parts.append(box(730, 410, 285, 185, "Extension Points", ["PreFilter / Filter", "PreScore / Score", "Reserve / Permit", "PreBind / Bind"], "#ffffff", "#bfdbfe"))
    parts.append(box(1090, 410, 300, 185, "调度结果", ["Filter 决定能不能放", "Score 决定更适合放哪里", "Bind 写入 nodeName"], "#ffffff", "#bfdbfe"))
    parts.append(box(730, 620, 660, 120, "开发第一目标", ["先写 Score/Filter 插件", "跑通本地 schedulerName + Event + 日志闭环"], "#fefce8", "#fde68a", "#92400e"))

    parts.append(arrow(550, 270, 730, 270, "#2563eb", "PodSpec", False, "arrow-blue"))
    parts.append(arrow(1015, 280, 1090, 280, "#2563eb", "注册", False, "arrow-blue"))
    parts.append(arrow(873, 355, 873, 410, "#2563eb", None, False, "arrow-blue"))
    parts.append(arrow(1015, 500, 1090, 500, "#2563eb", "候选节点", False, "arrow-blue"))
    parts.append(arrow(1240, 410, 1240, 355, "#16a34a", None, False, "arrow-green"))
    parts.append(arrow(730, 500, 550, 448, "#16a34a", "watch/cache", True, "arrow-green"))
    parts.append(arrow(1240, 600, 550, 610, "#9333ea", "bind / event", False, "arrow-purple"))
    return save_svg("01_k8s_scheduler_framework_architecture", "\n".join(parts), 1540, 840)


def make_core_flow():
    parts = [text(70, 56, "Scheduler Framework 核心主流程", 34, "#111827", 700)]
    parts.append(text(70, 90, "主线：一个 Pending Pod 从队列进入 scheduling cycle，再进入 binding cycle；失败会进入 backoff/unschedulable，靠事件和 QueueingHint 重试。", 21, "#6b7280"))
    y = 150
    xs = [70, 310, 550, 790, 1030, 1270]
    titles = [
        ("Pod 创建", ["nodeName 为空", "schedulerName 匹配 profile"]),
        ("调度队列", ["PreEnqueue", "ActiveQ / BackoffQ", "Unschedulable pool"]),
        ("Filter 阶段", ["PreFilter 预计算", "Filter 并发过滤节点", "PostFilter 兜底/抢占"]),
        ("Score 阶段", ["PreScore 准备", "Score 打分", "Normalize + 权重"]),
        ("Reserve / Permit", ["Reserve 假定资源", "Permit 等待或拒绝", "失败要 Unreserve"]),
        ("Binding Cycle", ["PreBind", "Bind 写 API Server", "PostBind 清理"]),
    ]
    for x, (title_, subs) in zip(xs, titles):
        parts.append(box(x, y, 200, 230, title_, subs, "#ffffff", "#d1d5db"))
    for i in range(len(xs) - 1):
        parts.append(arrow(xs[i] + 200, y + 115, xs[i + 1], y + 115, "#2563eb", None, False, "arrow-blue"))

    parts.append(f'<rect x="545" y="460" width="690" height="170" rx="14" fill="#fef2f2" stroke="#fecaca" stroke-width="2"/>')
    parts.append(text(585, 500, "失败 / 不可调度路径", 25, "#b91c1c", 700))
    parts.append(text(575, 538, "Unschedulable：约束不满足，通常等相关事件触发重试", 20, "#374151"))
    parts.append(text(575, 570, "Error：插件内部错误，Pod 进入 backoff 后重试", 20, "#374151"))
    parts.append(text(575, 602, "QueueingHint：判断某个 Node/Pod/资源事件是否真的可能让 Pod 可调度", 20, "#374151"))
    parts.append(arrow(650, y + 230, 650, 460, "#dc2626", None, False, "arrow-red"))
    parts.append(arrow(545, 585, 410, 380, "#dc2626", "重入队列", True, "arrow-red"))

    parts.append(box(70, 690, 1360, 95, "开发入门顺序", ["先 Score（只影响偏好）→ 再 Filter（会导致 Pending）→ 再 Reserve/Permit（涉及状态回滚）→ 最后碰 Bind/抢占/队列排序"], "#f8fafc", "#cbd5e1", "#334155"))
    return save_svg("02_k8s_scheduler_framework_core_flow", "\n".join(parts), 1500, 820)


def make_troubleshooting():
    parts = [text(70, 56, "自定义 Scheduler 插件开发与 Pending 排障路径", 34, "#111827", 700)]
    parts.append(text(70, 90, "适合本地开发第一天使用：先确认插件是否被加载，再确认是否影响了调度决策，最后看版本/RBAC/回滚。", 21, "#6b7280"))
    items = [
        (80, 150, "Pod schedulerName", ["不指定时走 default-scheduler", "多 profile 看 profile.schedulerName"], "#eff6ff", "#93c5fd"),
        (420, 150, "scheduler 是否运行", ["kube-system Pod Running", "leader election / healthz 正常"], "#eff6ff", "#93c5fd"),
        (760, 150, "配置启用插件", ["plugins.score/filter.enabled", "pluginConfig.name 与 Name() 一致"], "#eff6ff", "#93c5fd"),
        (1100, 150, "二进制注册插件", ["app.WithPlugin(Name, New)", "镜像是新构建版本"], "#eff6ff", "#93c5fd"),
        (80, 430, "看 Pod Events", ["FailedScheduling 原因", "插件返回的 status message"], "#fef2f2", "#fecaca"),
        (420, 430, "看 scheduler 日志", ["-v=4 起步", "确认 Score/Filter 被调用"], "#fef2f2", "#fecaca"),
        (760, 430, "看权限与缓存", ["system:kube-scheduler RBAC", "额外 CRD informer", "list/watch 权限"], "#fef2f2", "#fecaca"),
        (1100, 430, "看版本与回滚", ["K8s minor 强绑定", "保留 default-scheduler / 灰度 profile"], "#fef2f2", "#fecaca"),
    ]
    for x, y, title_, subs, fill, stroke in items:
        parts.append(box(x, y, 280, 175, title_, subs, fill, stroke))
    for x1, y1, x2, y2 in [
        (360, 235, 420, 235), (700, 235, 760, 235), (1040, 235, 1100, 235),
        (1240, 325, 1240, 430), (1100, 520, 1040, 520), (760, 520, 700, 520), (420, 520, 360, 520),
    ]:
        parts.append(arrow(x1, y1, x2, y2, "#2563eb", None, False, "arrow-blue"))
    parts.append(f'<rect x="80" y="690" width="1300" height="95" rx="14" fill="#f0fdf4" stroke="#86efac" stroke-width="2"/>')
    parts.append(text(110, 733, "最小可回滚上线策略", 25, "#15803d", 700))
    parts.append(text(110, 766, "先作为第二 scheduler + 只让测试 namespace 的 Pod 指定 schedulerName；确认无误后再考虑替换默认 scheduler。", 21, "#374151"))
    return save_svg("03_k8s_scheduler_framework_troubleshooting", "\n".join(parts), 1460, 830)


def main():
    svgs = [make_mindmap(), make_architecture(), make_core_flow(), make_troubleshooting()]
    for svg in svgs:
        export_png(svg)
        print(svg.name)


if __name__ == "__main__":
    main()
