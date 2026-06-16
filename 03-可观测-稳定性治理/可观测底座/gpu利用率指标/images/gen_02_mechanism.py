# -*- coding: utf-8 -*-
from svgkit import SVG

# 机制图：GPU 算力为什么空闲 —— 沿数据/计算流水线标注卡点
# 每个 stage = (阶段名, 卡点表现, 该看的指标)
INFER = [
    ("请求到达 / 排队", "流量不足或副本过多", "QPS / 队列长度 / 副本数"),
    ("CPU 前处理", "tokenizer / 特征组装慢", "CPU_UTIL / 前处理耗时"),
    ("组 batch", "动态批没生效, batch≈1", "batch 分布 / 等待时间"),
    ("H2D 拷贝", "CPU↔GPU 搬运卡住", "MEM_COPY_UTIL"),
    ("GPU forward", "compute / memory bound", "SM / Tensor / DRAM active"),
    ("D2H + 后处理", "返回链路慢", "后处理耗时 / 网络"),
]
TRAIN = [
    ("数据加载", "远端存储 / 小文件 / worker 少", "dataloader 占 step 比"),
    ("CPU 预处理", "解压 / 增强重", "CPU_UTIL"),
    ("H2D 拷贝", "喂不动 GPU", "MEM_COPY_UTIL"),
    ("fwd + bwd", "batch 小 / 算子碎 / FP32", "SM / Tensor active"),
    ("梯度同步", "NCCL / PS / worker skew", "all-reduce 耗时 / 网络"),
    ("周期阻塞", "checkpoint / eval 太频", "ckpt 耗时 / global step"),
]

W = 2600
PAD = 50
FS_LABEL = 23
FS_NOTE = 18
FS_METRIC = 17

def draw_pipeline(s, y, title, color, bg, stages):
    s.text(PAD, y, title, 28, color, weight="700")
    y += 26
    n = len(stages)
    gap = 34
    bw = (W - 2*PAD - gap*(n-1)) / n
    box_h = 78
    note_h = 132
    for i,(name, note, metric) in enumerate(stages):
        x = PAD + i*(bw+gap)
        # stage box
        s.rect(x, y, bw, box_h, color, rx=12)
        s.wraptext(x+bw/2, y+box_h/2+8, name, bw-20, FS_LABEL, "#ffffff", weight="700")
        # arrow to next
        if i < n-1:
            s.arrow(x+bw+4, y+box_h/2, x+bw+gap-4, y+box_h/2, "#94a3b8", sw=4)
        # note card under
        ny = y + box_h + 14
        s.rect(x, ny, bw, note_h, bg, stroke=color, rx=12, sw=2)
        s.text(x+14, ny+30, "卡点", 17, "#dc2626", weight="700")
        ln = s.wraptext(x+bw/2, ny+58, note, bw-24, FS_NOTE, "#b91c1c", anchor="middle")
        s.wraptext(x+bw/2, ny+58+ln*FS_NOTE*1.3+6, "看 "+metric, bw-24, FS_METRIC, "#0f172a", anchor="middle")
    return y + box_h + 14 + note_h

H = PAD + 40 + 300 + 60 + 300 + PAD
s = SVG(W, int(H))
s.text(PAD, PAD+30, "低利用率成因机制：GPU 算力为什么空闲（沿流水线找卡点）", 34, "#0f172a", weight="700")
y = PAD + 80
yb = draw_pipeline(s, y, "推理流水线", "#2563eb", "#eff6ff", INFER)
y2 = yb + 56
yb2 = draw_pipeline(s, y2, "训练流水线", "#059669", "#ecfdf5", TRAIN)
H2 = yb2 + PAD
# resize by re-saving with correct height: rebuild
s.h = int(H2)
s.L[0] = s.L[0].replace('viewBox="0 0 %d %d"'%(W,int(H)), 'viewBox="0 0 %d %d"'%(W,int(H2)))
s.L[1] = '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(W,int(H2))
s.save("02_gpu_util_mechanism.svg")
print("H2=%d"%H2)
