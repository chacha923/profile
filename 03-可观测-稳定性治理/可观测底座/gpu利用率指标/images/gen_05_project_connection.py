# -*- coding: utf-8 -*-
from svgkit import SVG

# 平台落地闭环：采集 -> 观测 -> 治理 -> 行动；并标注真实经验边界
COLS = [
    ("采集层", "#059669", "#ecfdf5",
     ["DCGM Exporter (GPU 指标)", "kube-state-metrics (GPU request/Pod)", "推理/训练框架埋点 (QPS/step)"]),
    ("观测层", "#0891b2", "#ecfeff",
     ["Prometheus / VictoriaMetrics", "Grafana GPU 看板", "告警/事件平台联动"]),
    ("治理层", "#2563eb", "#eff6ff",
     ["GPU 资源看板 (分配 vs 利用)", "任务 / 模型画像", "低利用率规则 (只筛选 不强制)"]),
    ("行动层", "#7c3aed", "#f5f3ff",
     ["规格推荐 / 分层资源池", "多卡准入校验", "分时弹性 / 共卡 (MIG·MPS)", "成本治理榜单"]),
]
# ownership label per column
OWN = ["平台真实在做", "平台真实在做", "可做 / 部分落地", "演进方向 / 需结合 SLA"]

W = 2500
PAD = 50
GAP = 70
COL_W = (W - 2*PAD - GAP*(len(COLS)-1)) / len(COLS)
HEAD_H = 64
SUB_H = 78
SUB_GAP = 18
TOP = 200

maxsub = max(len(c[3]) for c in COLS)
col_body_h = maxsub*SUB_H + (maxsub-1)*SUB_GAP
H = TOP + HEAD_H + 16 + col_body_h + 150
s = SVG(W, int(H))
s.text(PAD, 56, "GPU 利用率治理的平台落地闭环（采集 → 观测 → 治理 → 行动）", 34, "#0f172a", weight="700")
s.text(PAD, 92, "目标不是把 GPU 打满，而是把『分配 vs 真实利用』讲清，输出规格推荐、准入与分时弹性，按 SLA 做成本治理", 19, "#64748b")

for i,(name, color, bg, subs) in enumerate(COLS):
    x = PAD + i*(COL_W+GAP)
    # ownership chip
    s.rect(x, TOP-58, COL_W, 40, "#f1f5f9", stroke=color, rx=10, sw=1.5)
    s.text(x+COL_W/2, TOP-31, OWN[i], 18, color, anchor="middle", weight="700")
    # header
    s.rect(x, TOP, COL_W, HEAD_H, color, rx=14)
    s.text(x+COL_W/2, TOP+HEAD_H/2+9, name, 27, "#ffffff", anchor="middle", weight="700")
    # subs
    sy = TOP + HEAD_H + 16
    for sub in subs:
        s.rect(x, sy, COL_W, SUB_H, bg, stroke=color, rx=12, sw=2)
        s.wraptext(x+COL_W/2, sy+SUB_H/2+7, sub, COL_W-28, 19, "#1f2937", anchor="middle")
        sy += SUB_H + SUB_GAP
    # arrow to next col
    if i < len(COLS)-1:
        ay = TOP + HEAD_H + 16 + col_body_h/2
        s.arrow(x+COL_W+8, ay, x+COL_W+GAP-8, ay, "#94a3b8", sw=5)

# boundary legend
ly = TOP + HEAD_H + 16 + col_body_h + 44
s.rect(PAD, ly, W-2*PAD, 80, "#fff7ed", stroke="#ea580c", rx=14, sw=2)
s.text(PAD+24, ly+34, "经验边界", 22, "#c2410c", weight="700")
s.wraptext(PAD+(W-2*PAD)/2+60, ly+30, "采集 / 观测 / 看板 / 画像 = 平台可观测与治理范围内的真实工作；推理引擎内部 (KV cache / 动态批 / 量化) 与 NCCL 细节 = 对标理解，不夸大为自研",
           W-2*PAD-220, 19, "#9a3412", anchor="middle")
s.wraptext(PAD+(W-2*PAD)/2+60, ly+30+24, "低利用率规则只用于筛选与给建议，在线推理服务不能脱离业务 SLA 与峰值流量直接强制回收",
           W-2*PAD-220, 19, "#9a3412", anchor="middle")

s.save("05_gpu_util_project_connection.svg")
print("H=%d"%H)
