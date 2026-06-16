# -*- coding: utf-8 -*-
# TAOPlayer Think-Act-Observe (ReAct) 循环与状态机
W=2200; H=1120
L=[]
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def node(cx,cy,r,title,color,fill):
    L.append('<circle cx="%d" cy="%d" r="%d" fill="%s" stroke="%s" stroke-width="3.5"/>'%(cx,cy,r,fill,color))
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="%s" font-size="30" font-weight="800">%s</text>'%(cx,cy+10,color,esc(title)))
def card(x,y,w,h,title,lines,fill,stroke,th=22,sh=18):
    L.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s" stroke-width="2"/>'%(x,y,w,h,fill,stroke))
    L.append('<text x="%d" y="%d" fill="#0f172a" font-size="%d" font-weight="700">%s</text>'%(x+18,y+30,th,esc(title)))
    yy=y+30+sh+8
    for ln in lines:
        L.append('<text x="%d" y="%d" fill="#475569" font-size="%d">%s</text>'%(x+18,yy,sh,esc(ln)))
        yy+=sh+7

# 三节点三角循环 think -> action -> observe -> think
TX,TY=520,300   # think
AX,AY=1150,300  # action
OX,OY=835,640   # observe
R=110
# 循环箭头
def carrow(x1,y1,x2,y2,color,label,lx,ly):
    L.append('<path d="M %d,%d L %d,%d" stroke="%s" stroke-width="4" marker-end="url(#ar)"/>'%(x1,y1,x2,y2,color))
    L.append('<text x="%d" y="%d" fill="%s" font-size="20" font-weight="700">%s</text>'%(lx,ly,color,esc(label)))
carrow(TX+R,TY+10,AX-R,AY+10,"#7c3aed","有 tool_calls",760,278)
carrow(AX-30,AY+R,OX+R+30,OY-R+10,"#0891b2","执行完工具",1080,500)
carrow(OX-R-30,OY-R+10,TX+30,TY+R,"#059669","回到思考",470,505)
# think 直接到 observe (只有content)
carrow(TX+60,TY+R,OX-R-10,OY-30,"#7c3aed","只有结论(无工具)",520,560)

node(TX,TY,R,"Think","#7c3aed","#ede9fe")
node(AX,AY,R,"Action","#0891b2","#cffafe")
node(OX,OY,R,"Observe","#059669","#dcfce7")

# 节点说明卡
card(180,90,330,150,"Think 思考",["调 LLM（带 tools）","判断走 action / observe","轮数 >10 → 强制汇总输出"],"#f5f3ff","#7c3aed")
card(1320,90,360,150,"Action 行动",["逐个执行只读工具","结果回灌为观察输出","发现飞书链接→自动查阅"],"#ecfeff","#0891b2")
card(1320,560,360,180,"Observe 观察",["上条是工具结果→继续think","工具失败→有限重试(仅1次)","否则→注入12项质检","FINISHED→返回报告"],"#f0fdf4","#059669")

# 状态机条
sy=860
L.append('<text x="180" y="%d" fill="#0f172a" font-size="25" font-weight="800">AgentState 状态机</text>'%(sy-18))
states=[("IDLE","#94a3b8"),("RUNNING","#2563eb"),("FINISHED","#059669"),("FAILED / ERROR","#dc2626")]
sx=180; sw=360; sh=70
for i,(s,c) in enumerate(states):
    L.append('<rect x="%d" y="%d" width="%d" height="%d" rx="35" fill="#ffffff" stroke="%s" stroke-width="2.6"/>'%(sx,sy,sw,sh,c))
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="%s" font-size="24" font-weight="700">%s</text>'%(sx+sw//2,sy+45,c,s))
    if i<len(states)-1:
        L.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#94a3b8" stroke-width="3" marker-end="url(#ar)"/>'%(sx+sw,sy+sh//2,sx+sw+58,sy+sh//2))
    sx+=sw+60
L.append('<text x="180" y="%d" fill="#475569" font-size="19">terminate 工具 + 12项质检全通过 → FINISHED；唯一合法结束出口。get_summary 兜底取「故障根因/凭据/方案」结论。</text>'%(sy+sh+44))

svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif">'%(W,H),
 '<defs><marker id="ar" markerWidth="13" markerHeight="13" refX="9" refY="5" orient="auto"><path d="M0,0 L11,5 L0,10 z" fill="#64748b"/></marker></defs>',
 '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(W,H),
 '<text x="%d" y="52" text-anchor="middle" fill="#0f172a" font-size="32" font-weight="800">TAOPlayer · Think-Act-Observe（ReAct）引擎</text>'%(W//2)]
svg+=L; svg.append('</svg>')
open("03_aiops-rca_react_engine.svg","w").write("\n".join(svg))
print("ok")
