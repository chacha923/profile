# -*- coding: utf-8 -*-
from svgkit import SVG

# 排障决策树：症状 -> 判别条件 -> 结论/优化
# row = (group, condition, conclusion, color)
ROWS = [
    ("hi", "吞吐 / P99 达标", "健康：转向成本与吞吐治理", "#059669"),
    ("hi", "吞吐低 或 P99 高", "batch 过大 / 通信 / 框架效率低 或 容量不足 → 按 SLA 扩容、拆分流量", "#d97706"),
    ("lo", "功耗低 + 显存高 + 队列空 + P99 好", "容量过剩 → 副本治理、分时弹性、共卡", "#7c3aed"),
    ("lo", "CPU 高 + forward 低", "前处理 / dataloader 瓶颈 → 异步化、加 worker、缓存", "#0891b2"),
    ("lo", "MEM_COPY_UTIL 高", "H2D / D2H 搬运瓶颈 → 减少拷贝、pin memory", "#0891b2"),
    ("lo", "DRAM_ACTIVE 高 + Tensor 低", "memory-bound → 量化、算子融合、KV cache、换引擎", "#dc2626"),
    ("lo", "网络/all-reduce 高，单卡高多卡低", "分布式通信瓶颈 → 拓扑亲和、NCCL 调优、控规模", "#2563eb"),
    ("lo", "GPU_UTIL 锯齿", "数据加载 / checkpoint / eval → 看占比、异步 ckpt", "#ea580c"),
    ("lo", "Tensor active 低", "没吃 Tensor Core → 开 AMP/FP16/BF16、检查 shape", "#4f46e5"),
    ("lo", "以上都正常但 P99 差", "瓶颈不在 GPU → 查队列、IO、网络、依赖服务", "#db2777"),
]

W = 2600
PAD = 40
ROW_H = 96
PITCH = 122
COND_X, COND_W = 1000, 600
CONC_X, CONC_W = 1660, W-PAD-1660
B_X, B_W = 560, 220
ROOT_X, ROOT_W = 60, 380

y0 = 150
H = y0 + len(ROWS)*PITCH + PAD
s = SVG(W, int(H))
s.text(PAD, 56, "GPU 低利用率排障决策树（症状 → 判别 → 结论/优化）", 34, "#0f172a", weight="700")
s.text(PAD, 92, "第一步永远是同时看 GPU_UTIL + 功耗 + 显存 + 吞吐/P99，再分叉；命令只是手段，关键是每步看什么、异常说明什么", 19, "#64748b")

def cy(i): return y0 + i*PITCH + ROW_H/2

# root
hi_rows = [i for i,r in enumerate(ROWS) if r[0]=="hi"]
lo_rows = [i for i,r in enumerate(ROWS) if r[0]=="lo"]
root_cy = (cy(0)+cy(len(ROWS)-1))/2
s.rect(ROOT_X, root_cy-70, ROOT_W, 140, "#1e293b", rx=16)
s.wraptext(ROOT_X+ROOT_W/2, root_cy-8, "入口指标", 360, 26, "#ffffff", weight="700")
s.wraptext(ROOT_X+ROOT_W/2, root_cy+26, "UTIL+功耗+显存+吞吐", 360, 20, "#cbd5e1")

# branch nodes
hi_cy = (cy(hi_rows[0])+cy(hi_rows[-1]))/2
lo_cy = (cy(lo_rows[0])+cy(lo_rows[-1]))/2
def bnode(cyy, label, sub, color):
    s.rect(B_X, cyy-58, B_W, 116, color, rx=14)
    s.text(B_X+B_W/2, cyy-6, label, 26, "#ffffff", anchor="middle", weight="700")
    s.text(B_X+B_W/2, cyy+28, sub, 18, "#f1f5f9", anchor="middle")
bnode(hi_cy, "UTIL 高", "但要核对吞吐", "#16a34a")
bnode(lo_cy, "UTIL 低", "逐条排查信号", "#b45309")

# root -> branches
s.arrow(ROOT_X+ROOT_W, root_cy-30, B_X-6, hi_cy, "#475569", sw=3)
s.arrow(ROOT_X+ROOT_W, root_cy+30, B_X-6, lo_cy, "#475569", sw=3)

# rows
for i,(g, cond, conc, color) in enumerate(ROWS):
    yc = cy(i)
    bx = B_X+B_W
    bcy = hi_cy if g=="hi" else lo_cy
    # branch -> condition
    s.path("M %.1f,%.1f C %.1f,%.1f %.1f,%.1f %.1f,%.1f"%(bx, bcy, bx+90, bcy, COND_X-90, yc, COND_X-6, yc), "#94a3b8", sw=2.6)
    # condition box
    s.rect(COND_X, yc-ROW_H/2, COND_W, ROW_H, "#f8fafc", stroke="#64748b", rx=12, sw=2)
    s.wraptext(COND_X+COND_W/2, yc+7, cond, COND_W-30, 20, "#0f172a", anchor="middle", weight="700")
    # arrow to conclusion
    s.arrow(COND_X+COND_W+4, yc, CONC_X-6, yc, "#94a3b8", sw=3)
    # conclusion box
    s.rect(CONC_X, yc-ROW_H/2, CONC_W, ROW_H, "#ffffff", stroke=color, rx=12, sw=2.8)
    s.wraptext(CONC_X+CONC_W/2, yc+7, conc, CONC_W-34, 20, color, anchor="middle", weight="700")

s.save("04_gpu_util_troubleshooting.svg")
print("H=%d"%H)
