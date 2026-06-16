# -*- coding: utf-8 -*-
from svgkit import SVG

# 典型场景的指标特征签名：看到这组组合 -> 大概率是某场景
# sig item: (指标, 方向) 方向 up/down/mid
CARDS = [
    ("推理容量过剩", "#7c3aed", "#f5f3ff",
     [("GPU_UTIL","down"),("QPS","down"),("P99","good"),("显存","up"),("功耗","down")],
     "副本过多 / 低峰 → 分时弹性、共卡、按 SLA 反推副本"),
    ("动态批没生效", "#2563eb", "#eff6ff",
     [("QPS","mid"),("GPU_UTIL","mid"),("batch≈1","down"),("P99","good")],
     "请求不集中 / 等待短 → 调 batch wait、相近 shape 路由"),
    ("CPU 前后处理瓶颈", "#0891b2", "#ecfeff",
     [("GPU_UTIL","down"),("CPU","up"),("forward","down"),("端到端","up")],
     "tokenizer / 特征慢 → 异步化、并行、优化特征服务"),
    ("LLM decode memory-bound", "#dc2626", "#fef2f2",
     [("GPU_UTIL","mid"),("DRAM_ACTIVE","up"),("Tensor","down"),("tokens/s","down")],
     "访存受限 → 量化、算子融合、KV cache、换推理引擎"),
    ("训练数据加载瓶颈", "#ea580c", "#fff7ed",
     [("GPU_UTIL","saw"),("CPU","up"),("存储 IO","up"),("step time","up")],
     "远端存储 / 小文件 → 加 worker、缓存、prefetch、合并小文件"),
    ("多卡通信瓶颈", "#059669", "#ecfdf5",
     [("单卡 UTIL","good"),("多卡 UTIL","down"),("网络","up"),("all-reduce","up")],
     "梯度同步贵 → 拓扑亲和、NCCL 调优、控制分布式规模"),
]

ARROW = {"up":("▲","#dc2626"), "down":("▼","#2563eb"), "good":("✓","#059669"),
         "mid":("≈","#d97706"), "saw":("锯齿","#ea580c")}

W = 2400
PAD = 50
COLS = 3
GAP = 36
CARD_W = (W - 2*PAD - GAP*(COLS-1)) / COLS
CARD_H = 360

H = PAD + 70 + 2*CARD_H + GAP + PAD
s = SVG(W, int(H))
s.text(PAD, PAD+34, "典型场景的指标特征签名（看到这组组合 → 优先怀疑）", 34, "#0f172a", weight="700")
s.text(PAD, PAD+66, "▲=偏高  ▼=偏低  ≈=中等  ✓=正常/达标  —— 任何单一指标都不下结论，看组合", 19, "#64748b")

y0 = PAD + 92
for idx,(title, color, bg, sig, action) in enumerate(CARDS):
    r, c = idx//COLS, idx%COLS
    x = PAD + c*(CARD_W+GAP)
    y = y0 + r*(CARD_H+GAP)
    s.rect(x, y, CARD_W, CARD_H, bg, stroke=color, rx=16, sw=2.5)
    s.rect(x, y, CARD_W, 56, color, rx=16, sw=0)
    s.rect(x, y+28, CARD_W, 28, color, rx=0, sw=0)
    s.text(x+CARD_W/2, y+37, title, 24, "#ffffff", anchor="middle", weight="700")
    # signature rows
    sy = y + 92
    for metric, d in sig:
        sym, col = ARROW[d]
        s.text(x+28, sy, metric, 21, "#1f2937")
        s.text(x+CARD_W-28, sy, sym, 22, col, anchor="end", weight="700")
        s.line(x+24, sy+12, x+CARD_W-24, sy+12, "#e2e8f0", sw=1)
        sy += 40
    # action footer
    s.line(x+20, y+CARD_H-94, x+CARD_W-20, y+CARD_H-94, color, sw=1.5, dash="5,5")
    s.text(x+24, y+CARD_H-64, "→ 处理方向", 18, color, weight="700")
    s.wraptext(x+CARD_W/2, y+CARD_H-36, action, CARD_W-44, 18, "#334155", anchor="middle")

s.save("03_gpu_util_scenario.svg")
print("H=%d card=%d"%(H, CARD_W))
