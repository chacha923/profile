# -*- coding: utf-8 -*-
# 防幻觉四层漏斗：从"模型自由发挥"逐层收窄到"证据驱动结论"
W=2200; H=1080
L=[]
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
layers=[
 ("第一层 · 只读工具取证","#2563eb","#eff6ff",
   ["所有工具只读：k8s/Prometheus/日志/事件/变更/节点池","模型只能拿真实数据，不能动线上；空结果也是合法返回"]),
 ("第二层 · 知识库案例逐项验证","#0891b2","#ecfeff",
   ["对照飞书「故障案例分析」自上而下逐项验证故障现象","每项要「时间→现象→证据」；全通过才认根因，否则未找到根因"]),
 ("第三层 · 12项否决式质检","#7c3aed","#f5f3ff",
   ["terminate 前过 OBSERVER_PROMPT 12项检查","不确定表述/条件结论/数据溯源/工具名/虚构路径…任一不过禁结束"]),
 ("第四层 · 确定性与脱敏","#059669","#f0fdf4",
   ["temperature=0 降输出抖动，诊断可复现","报告剔除工具名与 kubectl 命令，面向研发只给可执行动作"]),
]
topW=1760; botW=900; cx=W//2
ly=150; lh=150; gap=24
n=len(layers)
for i,(t,c,fill,lines) in enumerate(layers):
    w=int(topW-(topW-botW)*i/(n-1))
    wn=int(topW-(topW-botW)*(i+1)/(n-1))
    x=cx-w//2; xn=cx-wn//2
    y=ly+i*(lh+gap)
    # 梯形
    pts="%d,%d %d,%d %d,%d %d,%d"%(x,y, x+w,y, xn+wn,y+lh, xn,y+lh)
    L.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="3"/>'%(pts,fill,c))
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="%s" font-size="26" font-weight="800">%s</text>'%(cx,y+44,c,esc(t)))
    yy=y+44+24
    for ln in lines:
        L.append('<text x="%d" y="%d" text-anchor="middle" fill="#334155" font-size="19">%s</text>'%(cx,yy,esc(ln)))
        yy+=27
    # 收窄箭头
    if i<n-1:
        ay=y+lh; L.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#94a3b8" stroke-width="3.5" marker-end="url(#ar)"/>'%(cx,ay,cx,ay+gap-2))

# 左右标注
L.append('<text x="120" y="190" fill="#dc2626" font-size="23" font-weight="800">幻觉空间大</text>')
L.append('<text x="120" y="218" fill="#94a3b8" font-size="18">模型自由发挥</text>')
yb=ly+n*(lh+gap)+30
L.append('<rect x="%d" y="%d" width="%d" height="86" rx="14" fill="#dcfce7" stroke="#059669" stroke-width="3"/>'%(cx-botW//2-40,yb,botW+80))
L.append('<text x="%d" y="%d" text-anchor="middle" fill="#059669" font-size="26" font-weight="800">证据驱动 · 受控 · 可质检的根因报告</text>'%(cx,yb+40))
L.append('<text x="%d" y="%d" text-anchor="middle" fill="#475569" font-size="19">匹配不上 → 「未找到根因」，宁可不答也不猜（错误根因比没有更危险）</text>'%(cx,yb+70))

svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif">'%(W,H),
 '<defs><marker id="ar" markerWidth="13" markerHeight="13" refX="9" refY="5" orient="auto"><path d="M0,0 L11,5 L0,10 z" fill="#64748b"/></marker></defs>',
 '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(W,H),
 '<text x="%d" y="58" text-anchor="middle" fill="#0f172a" font-size="32" font-weight="800">防幻觉四层 · 把 LLM 约束成证据驱动的排障系统</text>'%(W//2)]
svg+=L; svg.append('</svg>')
open("04_aiops-rca_anti_hallucination.svg","w").write("\n".join(svg))
print("ok")
