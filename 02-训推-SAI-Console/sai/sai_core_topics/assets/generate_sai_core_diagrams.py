#!/usr/bin/env python3
from __future__ import annotations

import html
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
RSVG = "/opt/homebrew/bin/rsvg-convert"

FONT = "'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', 'Microsoft JhengHei', 'SimHei', sans-serif"

COLORS = {
    "bg": "#ffffff",
    "text": "#111827",
    "muted": "#6b7280",
    "line": "#d1d5db",
    "soft": "#f8fafc",
    "blue": "#2563eb",
    "blue_fill": "#eff6ff",
    "blue_stroke": "#bfdbfe",
    "green": "#16a34a",
    "green_fill": "#f0fdf4",
    "green_stroke": "#bbf7d0",
    "purple": "#9333ea",
    "purple_fill": "#faf5ff",
    "purple_stroke": "#e9d5ff",
    "orange": "#ea580c",
    "orange_fill": "#fff7ed",
    "orange_stroke": "#fed7aa",
    "red": "#dc2626",
    "red_fill": "#fef2f2",
    "red_stroke": "#fecaca",
    "teal": "#0f766e",
    "teal_fill": "#f0fdfa",
    "teal_stroke": "#99f6e4",
}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def wrap_text(text: str, max_chars: int) -> list[str]:
    parts = text.split()
    if len(parts) > 1:
        lines: list[str] = []
        cur = ""
        for part in parts:
            next_cur = part if not cur else f"{cur} {part}"
            if len(next_cur) <= max_chars:
                cur = next_cur
            else:
                if cur:
                    lines.append(cur)
                cur = part
        if cur:
            lines.append(cur)
        return lines

    lines = []
    cur = ""
    for ch in text:
        if len(cur) >= max_chars:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


class SVG:
    def __init__(self, title: str, subtitle: str = "", w: int = 960, h: int = 600):
        self.w = w
        self.h = h
        self.parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
            "<style>",
            f"text {{ font-family: {FONT}; }}",
            ".title { font-size: 25px; font-weight: 700; fill: #111827; }",
            ".subtitle { font-size: 13px; fill: #6b7280; }",
            ".label { font-size: 14px; font-weight: 650; fill: #111827; }",
            ".small { font-size: 12px; fill: #6b7280; }",
            ".tiny { font-size: 11px; fill: #6b7280; }",
            ".lane { font-size: 11px; font-weight: 700; letter-spacing: 0.04em; }",
            "</style>",
            "<defs>",
            '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
            '<feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#0f172a" flood-opacity="0.10"/></filter>',
            self.marker("blue", COLORS["blue"]),
            self.marker("green", COLORS["green"]),
            self.marker("purple", COLORS["purple"]),
            self.marker("orange", COLORS["orange"]),
            self.marker("red", COLORS["red"]),
            self.marker("teal", COLORS["teal"]),
            self.marker("gray", COLORS["muted"]),
            "</defs>",
            f'<rect width="{w}" height="{h}" fill="{COLORS["bg"]}"/>',
            f'<text x="{w/2}" y="34" text-anchor="middle" class="title">{esc(title)}</text>',
        ]
        if subtitle:
            self.parts.append(f'<text x="{w/2}" y="57" text-anchor="middle" class="subtitle">{esc(subtitle)}</text>')

    @staticmethod
    def marker(name: str, color: str) -> str:
        return (
            f'<marker id="arrow-{name}" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">'
            f'<polygon points="0 0,10 3.5,0 7" fill="{color}"/></marker>'
        )

    def lane(self, x: int, y: int, w: int, h: int, title: str, color: str = "blue") -> None:
        stroke = COLORS[f"{color}_stroke"] if f"{color}_stroke" in COLORS else COLORS["line"]
        fill = COLORS[f"{color}_fill"] if f"{color}_fill" in COLORS else COLORS["soft"]
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" fill-opacity="0.45" '
            f'stroke="{stroke}" stroke-width="1.3" stroke-dasharray="7 5"/>'
        )
        self.parts.append(f'<text x="{x+14}" y="{y+22}" class="lane" fill="{COLORS[color]}">{esc(title)}</text>')

    def node(self, x: int, y: int, w: int, h: int, title: str, sub: str = "", color: str = "blue", icon: str = "") -> None:
        fill = COLORS.get(f"{color}_fill", "#ffffff")
        stroke = COLORS.get(f"{color}_stroke", COLORS["line"])
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.5" filter="url(#shadow)"/>'
        )
        text_x = x + w / 2
        if icon:
            self.parts.append(f'<circle cx="{x+24}" cy="{y+24}" r="14" fill="#ffffff" stroke="{stroke}" stroke-width="1"/>')
            self.parts.append(f'<text x="{x+24}" y="{y+29}" text-anchor="middle" font-size="13" font-weight="700" fill="{COLORS[color]}">{esc(icon)}</text>')
        lines = wrap_text(title, max(14, int(w / 12)))
        start_y = y + (h / 2) - (len(lines) - 1) * 8
        if sub:
            start_y -= 8
        for i, line in enumerate(lines):
            self.parts.append(f'<text x="{text_x}" y="{start_y+i*17:.1f}" text-anchor="middle" class="label">{esc(line)}</text>')
        if sub:
            sub_lines = wrap_text(sub, max(18, int(w / 10)))
            for i, line in enumerate(sub_lines[:2]):
                self.parts.append(f'<text x="{text_x}" y="{start_y+len(lines)*17+4+i*14:.1f}" text-anchor="middle" class="small">{esc(line)}</text>')

    def pill(self, x: int, y: int, w: int, h: int, title: str, color: str = "blue") -> None:
        fill = COLORS.get(f"{color}_fill", "#ffffff")
        stroke = COLORS.get(f"{color}_stroke", COLORS["line"])
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        self.parts.append(f'<text x="{x+w/2}" y="{y+h/2+5}" text-anchor="middle" class="small" font-weight="650" fill="{COLORS[color]}">{esc(title)}</text>')

    def storage(self, cx: int, top: int, w: int, h: int, title: str, sub: str = "", color: str = "green") -> None:
        fill = COLORS.get(f"{color}_fill", "#ffffff")
        stroke = COLORS.get(f"{color}_stroke", COLORS["line"])
        self.parts.append(f'<ellipse cx="{cx}" cy="{top}" rx="{w/2}" ry="13" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        self.parts.append(f'<rect x="{cx-w/2}" y="{top}" width="{w}" height="{h}" fill="{fill}" stroke="none"/>')
        self.parts.append(f'<line x1="{cx-w/2}" y1="{top}" x2="{cx-w/2}" y2="{top+h}" stroke="{stroke}" stroke-width="1.5"/>')
        self.parts.append(f'<line x1="{cx+w/2}" y1="{top}" x2="{cx+w/2}" y2="{top+h}" stroke="{stroke}" stroke-width="1.5"/>')
        self.parts.append(f'<ellipse cx="{cx}" cy="{top+h}" rx="{w/2}" ry="13" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        self.parts.append(f'<text x="{cx}" y="{top+h/2+2}" text-anchor="middle" class="label">{esc(title)}</text>')
        if sub:
            self.parts.append(f'<text x="{cx}" y="{top+h/2+20}" text-anchor="middle" class="small">{esc(sub)}</text>')

    def arrow(self, x1: int, y1: int, x2: int, y2: int, label: str = "", color: str = "blue", dashed: bool = False) -> None:
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{COLORS[color]}" stroke-width="2.2" '
            f'marker-end="url(#arrow-{color})"{dash}/>'
        )
        if label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2 - 7
            self.parts.append(f'<rect x="{mx-42}" y="{my-14}" width="84" height="20" rx="10" fill="#ffffff" opacity="0.92"/>')
            self.parts.append(f'<text x="{mx}" y="{my+1}" text-anchor="middle" class="tiny">{esc(label)}</text>')

    def path(self, d: str, label: str = "", label_x: int = 0, label_y: int = 0, color: str = "blue", dashed: bool = False) -> None:
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(f'<path d="{d}" fill="none" stroke="{COLORS[color]}" stroke-width="2.2" marker-end="url(#arrow-{color})"{dash}/>')
        if label:
            self.parts.append(f'<rect x="{label_x-46}" y="{label_y-15}" width="92" height="20" rx="10" fill="#ffffff" opacity="0.92"/>')
            self.parts.append(f'<text x="{label_x}" y="{label_y}" text-anchor="middle" class="tiny">{esc(label)}</text>')

    def legend(self, items: list[tuple[str, str]]) -> None:
        x, y = 26, self.h - 40
        for i, (label, color) in enumerate(items):
            yy = y + i * 18
            self.parts.append(f'<line x1="{x}" y1="{yy}" x2="{x+30}" y2="{yy}" stroke="{COLORS[color]}" stroke-width="2" marker-end="url(#arrow-{color})"/>')
            self.parts.append(f'<text x="{x+38}" y="{yy+4}" class="tiny">{esc(label)}</text>')

    def save(self, name: str) -> None:
        self.parts.append("</svg>")
        svg_path = OUT / f"{name}.svg"
        png_path = OUT / f"{name}.png"
        check_path = OUT / f".{name}.check.png"
        svg_path.write_text("\n".join(self.parts), encoding="utf-8")
        subprocess.run([RSVG, str(svg_path), "-o", str(check_path)], check=True)
        check_path.unlink(missing_ok=True)
        subprocess.run([RSVG, "-w", "1920", str(svg_path), "-o", str(png_path)], check=True)


def runtime_unification() -> None:
    s = SVG("AI 工作负载 Runtime 统一", "底层异构，平台侧统一服务画像、资源、状态和运维动作", h=650)
    s.lane(30, 80, 900, 74, "USER / AUTOMATION", "blue")
    s.node(70, 104, 150, 40, "算法同学", "训练 / 推理 / 下载", "blue")
    s.node(300, 104, 150, 40, "SAI Console", "统一入口", "blue")
    s.node(530, 104, 150, 40, "OpenAPI", "自动化系统", "blue")
    s.arrow(220, 124, 300, 124, "提交", "blue")
    s.arrow(450, 124, 530, 124, "调用", "blue")

    s.lane(30, 185, 900, 125, "SAI CONTROL PLANE", "purple")
    s.node(70, 220, 150, 58, "server", "鉴权 / 校验 / 编排", "purple")
    s.node(285, 220, 150, 58, "服务画像", "provider / runtime / model", "purple")
    s.node(500, 220, 150, 58, "生命周期动作", "扩缩容 / 重启 / 迁移", "purple")
    s.node(715, 220, 150, 58, "Provider 适配", "ACK / PAI / 贝联", "purple")
    s.arrow(220, 249, 285, 249, "", "purple")
    s.arrow(435, 249, 500, 249, "", "purple")
    s.arrow(650, 249, 715, 249, "", "purple")

    s.lane(30, 340, 900, 120, "SHARED GOVERNANCE", "green")
    s.node(70, 374, 150, 56, "NodePool", "GPU / CPU / spot", "green")
    s.node(285, 374, 150, 56, "存储挂载", "NAS / OSS / Git / PVC", "green")
    s.node(500, 374, 150, 56, "watcher / Sync", "状态回写 / 补偿", "green")
    s.node(715, 374, 150, 56, "日志事件", "实例 / Pod / Event", "green")
    s.path("M790 278 V337 Q790 352 775 352 H575 V374", "运行态", 690, 354, "green", True)
    s.path("M145 374 V320 Q145 305 160 305 H790 V278", "资源与存储", 452, 323, "green", True)

    s.lane(30, 490, 900, 100, "EXECUTION RUNTIMES", "orange")
    xs = [65, 190, 315, 440, 565, 690, 815]
    labels = [("KServe", "推理"), ("TFJob", "训练"), ("CronJob", "周期"), ("Nuclio", "函数"), ("Job", "模型下载"), ("PAI / 火山", "托管"), ("贝联", "外部推理")]
    for x, (t, sub) in zip(xs, labels):
        s.node(x, 522, 90, 44, t, sub, "orange")
    s.path("M790 278 V505", "执行", 820, 390, "orange")
    s.legend([("同步控制", "blue"), ("平台编排", "purple"), ("状态与治理", "green"), ("底层执行", "orange")])
    s.save("01_runtime_unification")


def gpu_governance() -> None:
    s = SVG("GPU 资源池与资源治理", "SAI 做调度意图产品化，最终调度仍由 Kubernetes 和 GPU 插件完成", h=650)
    s.lane(30, 80, 900, 82, "WORKLOAD INTENT", "blue")
    s.node(65, 108, 120, 42, "在线推理", "低抖动", "blue")
    s.node(210, 108, 120, 42, "训练任务", "算力密集", "blue")
    s.node(355, 108, 120, 42, "FAISS / 下载", "可重试", "blue")
    s.node(500, 108, 120, 42, "CPU 任务", "非 GPU", "blue")
    s.node(680, 102, 170, 54, "SAI 资源准入", "类型 / 规格 / 权限校验", "purple")
    s.arrow(620, 129, 680, 129, "提交", "blue")

    s.lane(30, 200, 900, 115, "NODEPOOL / RESOURCEGROUP", "green")
    pools = [("独占 GPU 池", "nvidia.com/gpu"), ("共享显存池", "aliyun.com/gpu-mem"), ("抢占 GPU 池", "spot / taint"), ("CPU 池", "cpu / memory")]
    for i, (t, sub) in enumerate(pools):
        s.node(75 + i * 215, 236, 165, 50, t, sub, "green")
    s.path("M765 156 V190 Q765 205 750 205 H155 V236", "资源池选择", 480, 207, "green")

    s.lane(30, 350, 900, 88, "PODSPEC TRANSLATION", "purple")
    s.node(95, 377, 155, 42, "nodeSelector", "节点标签", "purple")
    s.node(310, 377, 155, 42, "tolerations", "污点容忍", "purple")
    s.node(525, 377, 155, 42, "limits", "GPU / 显存 / CPU", "purple")
    s.node(740, 377, 120, 42, "PodSpec", "生成", "purple")
    s.arrow(240, 261, 250, 377, "", "purple")
    s.arrow(455, 261, 465, 377, "", "purple")
    s.arrow(670, 261, 680, 377, "", "purple")
    s.arrow(680, 398, 740, 398, "", "purple")

    s.lane(30, 475, 900, 98, "KUBERNETES EXECUTION", "orange")
    s.node(90, 510, 150, 42, "scheduler", "真实调度", "orange")
    s.node(310, 510, 150, 42, "GPU plugin", "设备分配", "orange")
    s.node(530, 510, 150, 42, "GPU / CPU nodes", "运行工作负载", "orange")
    s.node(750, 510, 130, 42, "观测与成本", "水位 / 用量", "teal")
    s.arrow(740, 419, 240, 510, "调度", "orange")
    s.arrow(240, 531, 310, 531, "", "orange")
    s.arrow(460, 531, 530, 531, "", "orange")
    s.arrow(680, 531, 750, 531, "回收口径", "teal")
    s.legend([("用户意图", "blue"), ("资源池治理", "green"), ("PodSpec 翻译", "purple"), ("底层调度", "orange")])
    s.save("02_gpu_resource_governance")


def lifecycle_consistency() -> None:
    s = SVG("生命周期与状态一致性治理", "server 处理期望状态，watcher / Sync 回写真状态，Job 承接长任务", h=650)
    y = 110
    steps = [
        ("用户动作", "创建 / 扩缩容 / 停止", "blue"),
        ("server", "鉴权 / 校验 / 编排", "purple"),
        ("期望状态", "DB / metadata", "green"),
        ("Runtime 执行", "K8s / 第三方平台", "orange"),
        ("真实状态", "Pod / Job / 服务实例", "green"),
    ]
    xs = [55, 225, 395, 565, 735]
    for x, (t, sub, c) in zip(xs, steps):
        s.node(x, y, 145, 58, t, sub, c)
    for x1, x2 in zip([200, 370, 540, 710], [225, 395, 565, 735]):
        s.arrow(x1, y + 29, x2, y + 29, "", "blue")

    s.lane(55, 230, 370, 140, "EVENT DRIVEN", "purple")
    s.node(85, 273, 140, 54, "watcher", "TFJob / Job / Pod 事件", "purple")
    s.node(255, 273, 140, 54, "快速回写", "及时状态更新", "purple")
    s.arrow(225, 300, 255, 300, "", "purple")

    s.lane(535, 230, 370, 140, "PERIODIC COMPENSATION", "teal")
    s.node(565, 273, 140, 54, "Sync", "定时查询", "teal")
    s.node(735, 273, 140, 54, "状态补偿", "修复漂移 / 丢事件", "teal")
    s.arrow(705, 300, 735, 300, "", "teal")

    s.path("M805 168 V220 Q805 236 790 236 H155 V273", "事件", 470, 236, "purple", True)
    s.path("M805 168 V220 Q805 236 790 236 H635 V273", "巡检", 720, 236, "teal", True)

    s.lane(55, 420, 850, 108, "LONG RUNNING TASKS", "orange")
    s.node(95, 455, 165, 48, "Kubernetes Job", "模型下载 / 制品处理", "orange")
    s.node(330, 455, 165, 48, "Pod 日志", "失败定位", "orange")
    s.node(565, 455, 165, 48, "最终收敛", "平台状态可见", "green")
    s.arrow(260, 479, 330, 479, "", "orange")
    s.arrow(495, 479, 565, 479, "", "green")
    s.path("M635 327 V405 Q635 420 620 420 H180 V455", "长任务异步", 405, 420, "orange")

    s.pill(96, 570, 180, 34, "API 返回不等于任务完成", "red")
    s.pill(320, 570, 170, 34, "watcher 保证及时性", "purple")
    s.pill(535, 570, 170, 34, "Sync 保证补偿", "teal")
    s.pill(750, 570, 145, 34, "最终一致性", "green")
    s.legend([("期望状态", "blue"), ("事件回写", "purple"), ("定时补偿", "teal"), ("长任务执行", "orange")])
    s.save("03_lifecycle_state_consistency")


def multi_cloud_serving() -> None:
    s = SVG("多云推理服务托管", "统一推理服务画像，底层 ACK / PAI / 火山 / 贝联 差异集中适配", h=650)
    s.node(70, 95, 155, 54, "统一推理入口", "列表 / 详情 / 操作", "blue")
    s.node(300, 95, 155, 54, "服务画像", "provider / runtime / model", "purple")
    s.node(530, 95, 155, 54, "Provider 适配", "规格 / 状态 / 实例", "purple")
    s.node(760, 95, 120, 54, "Sync", "状态补偿", "teal")
    s.arrow(225, 122, 300, 122, "创建 / 变更", "blue")
    s.arrow(455, 122, 530, 122, "", "purple")
    s.arrow(685, 122, 760, 122, "查询", "teal")

    s.lane(40, 205, 880, 138, "SERVING PROVIDERS", "orange")
    providers = [("ACK / KServe", "CRD / Pod"), ("PAI EAS", "外部托管"), ("火山推理", "云厂商 API"), ("贝联", "LcComputing")]
    for i, (t, sub) in enumerate(providers):
        s.node(80 + i * 215, 250, 165, 58, t, sub, "orange")
    s.path("M590 149 V190 Q590 205 575 205 H160 V250", "适配调用", 370, 207, "orange")
    s.path("M820 149 V190 Q820 205 805 205 H805 V250", "状态拉取", 820, 207, "teal", True)

    s.lane(40, 390, 880, 92, "NETWORK ACCESS", "green")
    nets = [("Envoy", "流量入口"), ("Gateway / HTTPRoute", "路由治理"), ("Service / ExternalName", "外部服务映射"), ("Ingress / VirtualService", "接入编排")]
    for i, (t, sub) in enumerate(nets):
        s.node(80 + i * 215, 418, 165, 42, t, sub, "green")
    s.path("M805 308 V380 Q805 395 790 395 H160 V418", "贝联接入", 450, 397, "green")

    s.lane(40, 520, 880, 70, "UNIFIED OPERATIONS", "blue")
    ops = ["扩缩容", "重启", "迁移", "实例", "日志", "事件", "状态"]
    for i, op in enumerate(ops):
        s.pill(82 + i * 120, 545, 84, 30, op, "blue")
    s.path("M760 149 V512", "运行态回写", 812, 340, "teal", True)
    s.legend([("用户操作", "blue"), ("Provider 调用", "orange"), ("网络接入", "green"), ("状态补偿", "teal")])
    s.save("04_multi_cloud_serving")


def pd_separation() -> None:
    s = SVG("PD 分离下的平台侧适配", "SAI 不实现推理引擎，负责多组件服务表达、资源池、状态聚合和观测入口", h=650)
    s.node(70, 95, 165, 58, "模型服务", "用户视角仍是一个服务", "blue")
    s.node(320, 95, 165, 58, "SAI 服务模型", "组件关系 / 元数据", "purple")
    s.node(570, 95, 165, 58, "服务级状态", "健康度 / 可用性", "green")
    s.arrow(235, 124, 320, 124, "托管", "blue")
    s.arrow(485, 124, 570, 124, "聚合", "green")

    s.lane(55, 215, 850, 130, "INFERENCE COMPONENTS", "purple")
    s.node(105, 258, 180, 58, "Prefill 组件", "吞吐 / 算力 / batch", "purple")
    s.node(390, 258, 180, 58, "Decode 组件", "低时延 / 显存 / KV 压力", "purple")
    s.node(675, 258, 180, 58, "Gateway / Router", "路由 / 接入 / 观测", "purple")
    s.path("M402 153 V202 Q402 217 387 217 H195 V258", "拆分表达", 300, 219, "purple")
    s.arrow(285, 287, 390, 287, "请求流", "blue")
    s.arrow(570, 287, 675, 287, "响应流", "blue")

    s.lane(55, 390, 850, 88, "COMPONENT LEVEL RESOURCE GOVERNANCE", "green")
    s.node(105, 418, 180, 42, "计算型 GPU 池", "Prefill", "green")
    s.node(390, 418, 180, 42, "高显存 / 稳定池", "Decode", "green")
    s.node(675, 418, 180, 42, "服务接入资源", "Gateway", "green")
    s.arrow(195, 316, 195, 418, "", "green")
    s.arrow(480, 316, 480, 418, "", "green")
    s.arrow(765, 316, 765, 418, "", "green")

    s.lane(55, 520, 850, 70, "AI SERVING OBSERVABILITY", "teal")
    for i, t in enumerate(["QPS", "RT", "错误率", "TTFT", "TPS", "token latency", "queue latency"]):
        s.pill(78 + i * 118, 545, 98, 30, t, "teal")
    s.path("M652 153 V505", "状态与指标", 700, 335, "teal", True)
    s.legend([("平台托管", "blue"), ("组件表达", "purple"), ("资源池治理", "green"), ("观测聚合", "teal")])
    s.save("05_pd_separation_platform_adaptation")


def async_model_jobs() -> None:
    s = SVG("长耗时任务异步化：模型下载与制品处理", "控制面只负责编排，Kubernetes Job 承接下载、落盘、日志和重试", h=650)
    s.lane(45, 85, 870, 78, "REQUEST", "blue")
    s.node(85, 110, 150, 42, "下载请求", "HF / OSS / HTTP", "blue")
    s.node(305, 110, 150, 42, "server", "校验 / 任务记录", "purple")
    s.node(525, 110, 150, 42, "model_job", "状态 / 重试 / 错误", "green")
    s.arrow(235, 131, 305, 131, "提交", "blue")
    s.arrow(455, 131, 525, 131, "落库", "green")

    s.lane(45, 215, 870, 115, "KUBERNETES JOB RUNTIME", "orange")
    s.node(90, 252, 160, 52, "batch/v1 Job", "独立执行", "orange")
    s.node(325, 252, 160, 52, "下载容器", "hfd / aria2 / curl", "orange")
    s.node(560, 252, 160, 52, "Pod 日志", "进度 / 失败原因", "orange")
    s.node(765, 252, 110, 52, "退出码", "成功 / 失败", "orange")
    s.path("M600 152 V200 Q600 215 585 215 H170 V252", "创建 Job", 380, 217, "orange")
    s.arrow(250, 278, 325, 278, "", "orange")
    s.arrow(485, 278, 560, 278, "", "orange")
    s.arrow(720, 278, 765, 278, "", "orange")

    s.lane(45, 390, 870, 88, "SHARED STORAGE", "green")
    s.storage(185, 426, 145, 42, "PVC / NAS", "统一模型盘", "green")
    s.node(395, 416, 160, 48, "固定目录", "workspace / subPath", "green")
    s.node(635, 416, 160, 48, "训练 / 推理复用", "TFJob / Serving", "green")
    s.path("M405 304 V375 Q405 390 390 390 H185 V426", "模型落盘", 290, 392, "green")
    s.arrow(257, 445, 315, 445, "", "green")
    s.arrow(555, 440, 635, 440, "挂载", "green")

    s.lane(45, 520, 870, 70, "OBSERVE / RETRY", "teal")
    s.node(110, 543, 150, 34, "状态查询", "Job / Pod / DB", "teal")
    s.node(330, 543, 150, 34, "日志排障", "Pod log", "teal")
    s.node(550, 543, 150, 34, "失败重试", "删旧 Job / 重建", "teal")
    s.node(770, 543, 110, 34, "不阻塞 API", "短链路", "teal")
    s.path("M820 304 V507 Q820 522 805 522 H185 V543", "状态回写", 500, 524, "teal", True)
    s.legend([("请求编排", "blue"), ("Job 执行", "orange"), ("模型落盘", "green"), ("观测重试", "teal")])
    s.save("06_async_model_artifact_jobs")


def main() -> None:
    runtime_unification()
    gpu_governance()
    lifecycle_consistency()
    multi_cloud_serving()
    pd_separation()
    async_model_jobs()


if __name__ == "__main__":
    main()
