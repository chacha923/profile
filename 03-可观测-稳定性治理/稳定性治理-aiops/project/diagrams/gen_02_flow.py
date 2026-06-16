# -*- coding: utf-8 -*-
# 核心流程：双泳道 — 上=单Agent ReAct主链路，下=多Agent圆桌
W=2600
L=[]
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def vbox(x,y,w,h,title,lines,fill,stroke,th=22,sh=17,tcolor="#0f172a"):
    L.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s" stroke-width="2.2"/>'%(x,y,w,h,fill,stroke))
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="%s" font-size="%d" font-weight="700">%s</text>'%(x+w//2,y+32,tcolor,th,esc(title)))
    yy=y+32+sh+9
    for ln in lines:
        L.append('<text x="%d" y="%d" text-anchor="middle" fill="#475569" font-size="%d">%s</text>'%(x+w//2,yy,sh,esc(ln)))
        yy+=sh+6
def harrow(x1,x2,y,color="#94a3b8",label=None):
    L.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3" marker-end="url(#ar)"/>'%(x1,y,x2,y,color))
    if label:
        L.append('<text x="%d" y="%d" text-anchor="middle" fill="#64748b" font-size="15">%s</text>'%((x1+x2)//2,y-9,esc(label)))

# ===== 泳道 A: 单 Agent ReAct =====
yA=120; hA=148
L.append('<rect x="40" y="%d" width="%d" height="%d" rx="14" fill="#f5f3ff" stroke="#7c3aed" stroke-width="1.6" opacity="0.5"/>'%(yA-30,W-80,hA+70))
L.append('<text x="70" y="%d" fill="#7c3aed" font-size="24" font-weight="800" transform="rotate(-90 70 %d)" text-anchor="middle">单 Agent ReAct（生产主力）</text>'%(yA+hA//2,yA+hA//2))
stepsA=[
 ("告警接入",["HTTP / 轮询 / MQ","三种触发入口"]),
 ("解析告警",["正则提服务树","Pod名 · 告警时间","失败抛错带原文"]),
 ("预取上下文",["get_pod/service","_all_info","end_time = 告警+5min"]),
 ("读知识库案例",["get_alert_analysis","按告警类型筛案例","现象/根因/方案"]),
 ("ReAct 取证循环",["think→只读工具→observe","逐项验证故障现象","时间→现象→证据"]),
 ("12项否决质检",["OBSERVER_PROMPT","任一不过禁 terminate","修正后重出"]),
 ("输出落地",["去md包裹","落 analysis_history","send_clerk 回贴飞书"]),
]
n=len(stepsA); gap=26; bw=(W-110-40-(n-1)*gap)//n; x=120
fillA,strokeA="#ede9fe","#7c3aed"
xs=[]
for t,ls in stepsA:
    vbox(x,yA,bw,hA,t,ls,fillA,strokeA); xs.append((x,x+bw)); x+=bw+gap
for i in range(n-1):
    lbl="未找到根因→兜底" if i==4 else None
    harrow(xs[i][1],xs[i+1][0],yA+hA//2,strokeA)
# 关键反馈：ReAct循环箭头
L.append('<path d="M %d,%d C %d,%d %d,%d %d,%d" fill="none" stroke="#7c3aed" stroke-width="2.4" stroke-dasharray="6,5" marker-end="url(#ar2)"/>'%(xs[4][0]+bw//2,yA+hA,xs[4][0]+bw//2-60,yA+hA+46,xs[4][0]+bw//2+60,yA+hA+46,xs[4][0]+bw//2,yA+hA+4))
L.append('<text x="%d" y="%d" text-anchor="middle" fill="#7c3aed" font-size="15">证据不足 → 继续取证（轮数上限10·超限强制汇总）</text>'%(xs[4][0]+bw//2,yA+hA+62))

# ===== 泳道 B: 多 Agent 圆桌 =====
yB=yA+hA+150; hB=150
L.append('<rect x="40" y="%d" width="%d" height="%d" rx="14" fill="#ecfeff" stroke="#0891b2" stroke-width="1.6" opacity="0.5"/>'%(yB-30,W-80,hB+72))
L.append('<text x="70" y="%d" fill="#0891b2" font-size="24" font-weight="800" transform="rotate(-90 70 %d)" text-anchor="middle">多 Agent 圆桌（探索形态）</text>'%(yB+hB//2,yB+hB//2))
stepsB=[
 ("receiver",["告警接收人","抛出告警","向 analyst 求因"]),
 ("analyst",["分析师","按可能性输出","最多5条根因(JSON)"]),
 ("planner",["规划师","对每条根因","规划验证步骤","指派 executor"]),
 ("k8s_engineer",["k8s工程师","按步骤调只读工具","仅依据工具输出","给阶段性结论"]),
 ("examiner",["检查员","裁决是否根因","汇总最可能1条","根因+解决方案"]),
]
m=len(stepsB); gapB=70; bwB=(W-110-40-(m-1)*gapB)//m; xb=120
fillB,strokeB="#cffafe","#0891b2"
xbs=[]
labelsB=["告警","≤5根因","验证步骤","工具结论","裁决/汇总"]
for t,ls in stepsB:
    vbox(xb,yB,bwB,hB,t,ls,fillB,strokeB,th=23); xbs.append((xb,xb+bwB)); xb+=bwB+gapB
for i in range(m-1):
    harrow(xbs[i][1],xbs[i+1][0],yB+hB//2,strokeB,labelsB[i+1])
L.append('<text x="%d" y="%d" text-anchor="middle" fill="#0891b2" font-size="16">终止条件：k8s_engineer 队列空 且 根因/步骤验证完成，或已产出最终答案 → examiner 读 summary 汇总</text>'%(W//2,yB+hB+52))

H=yB+hB+90
svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif">'%(W,H),
 '<defs><marker id="ar" markerWidth="12" markerHeight="12" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker>',
 '<marker id="ar2" markerWidth="12" markerHeight="12" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#7c3aed"/></marker></defs>',
 '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(W,H),
 '<text x="%d" y="58" text-anchor="middle" fill="#0f172a" font-size="32" font-weight="800">AIOps 根因分析 · 核心流程</text>'%(W//2)]
svg+=L; svg.append('</svg>')
open("02_aiops-rca_core_flow.svg","w").write("\n".join(svg))
print("H=%d bw=%d bwB=%d"%(H,bw,bwB))
