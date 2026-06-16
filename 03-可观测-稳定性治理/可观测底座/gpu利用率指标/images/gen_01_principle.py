# -*- coding: utf-8 -*-
from svgkit import SVG, tw

# 指标分层模型：底=GPU硬件层 -> K8s资源层 -> 框架层 -> 顶=业务层
LAYERS = [
    ("业务层", "判断 GPU 用得值不值", "#7c3aed", "#f5f3ff",
     ["SLA / P99 目标", "错误率 / 超时率", "单位 GPU 吞吐", "单位 GPU 成本", "高峰 / 低峰容量"]),
    ("框架层", "判断喂没喂满、效率高不高", "#2563eb", "#eff6ff",
     ["推理: QPS / 并发 / 队列", "推理: batch / 动态批命中", "LLM: TTFT / TPOT / tokens/s", "LLM: KV cache 占用",
      "训练: samples/s / step time", "训练: dataloader 耗时", "训练: NCCL / PS 通信", "训练: checkpoint / eval"]),
    ("K8s 资源层", "判断分配、调度、容器是否正常", "#0891b2", "#ecfeff",
     ["nvidia.com/gpu request", "GPU 分配碎片 / Pending", "Pod: Running / Restart / OOM", "节点 Ready / taint / 驱动",
      "TFJob 角色: chief / worker / ps"]),
    ("GPU 硬件层", "判断算力、显存、带宽、健康", "#059669", "#ecfdf5",
     ["DCGM GPU_UTIL", "FB_USED 显存", "MEM_COPY_UTIL", "POWER_USAGE 功耗", "SM_CLOCK 时钟",
      "PROF_SM_ACTIVE", "PIPE_TENSOR_ACTIVE", "PROF_DRAM_ACTIVE", "NVLink / PCIe", "XID / ECC / 温度"]),
]

W = 2200
PAD = 50
TITLE_H = 96
LABEL_W = 360
CHIP_AREA_X = PAD + LABEL_W + 30
CHIP_AREA_W = W - CHIP_AREA_X - PAD
FS = 20
CH = 46
VGAP = 14

def measure(items, maxw, fs=FS, padx=16, gap=14, ch=CH, vgap=VGAP):
    x0 = CHIP_AREA_X; cx = x0; rows = 1
    for s in items:
        cw = tw(s, fs) + padx*2
        if cx + cw > x0 + maxw and cx > x0:
            cx = x0; rows += 1
        cx += cw + gap
    return rows*ch + (rows-1)*vgap

# pre-compute band heights
band_h = []
for _,_,_,_,chips in LAYERS:
    band_h.append(max(110, measure(chips, CHIP_AREA_W) + 36))

H = PAD + TITLE_H + sum(band_h) + 22*(len(LAYERS)-1) + 70 + PAD
s = SVG(W, int(H))
s.text(PAD, PAD+44, "GPU 利用率指标体系：四层模型（自底向上）", 34, "#0f172a", weight="700")
s.text(PAD, PAD+78, "低利用率根因可能落在任意一层；单看 GPU_UTIL 不能下结论，需跨层交叉验证", 20, "#64748b")

y = PAD + TITLE_H
for i,(name, sub, color, bg, chips) in enumerate(LAYERS):
    bh = band_h[i]
    s.rect(PAD, y, W-2*PAD, bh, bg, stroke=color, rx=16, sw=2.5)
    # left label
    s.rect(PAD+18, y+18, LABEL_W-18, bh-36, color, rx=12)
    s.text(PAD+18+(LABEL_W-18)/2, y+bh/2-6, name, 28, "#ffffff", anchor="middle", weight="700")
    s.text(PAD+18+(LABEL_W-18)/2, y+bh/2+26, sub, 17, "#e2e8f0", anchor="middle")
    # chips
    s.chips(CHIP_AREA_X, y+24, CHIP_AREA_W, chips, fs=FS, fill="#ffffff", txt="#1f2937", ch=CH, vgap=VGAP)
    y += bh + 22

# bottom arrow note (cross-layer)
ay = y + 6
s.text(PAD, ay+30, "交叉验证示例：", 22, "#dc2626", weight="700")
s.text(PAD+150, ay+30, "GPU_UTIL 低 + 功耗低 → 没活干；显存高 + 功耗低 → 占着没算；DRAM_ACTIVE 高 + Tensor 低 → memory-bound", 20, "#b91c1c")

s.save("01_gpu_util_principle.svg")
print("H=%d band_h=%s" % (H, band_h))
