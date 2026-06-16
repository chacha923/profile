# -*- coding: utf-8 -*-
# 分层架构图：左侧层名标签，每层横排组件盒子，层间向下流转
W=2360
PALETTE = {
 "ingress":("#eff6ff","#2563eb"),
 "core":("#f5f3ff","#7c3aed"),
 "llm":("#ecfeff","#0891b2"),
 "tool":("#f0fdf4","#059669"),
 "know":("#fff7ed","#ea580c"),
 "out":("#fef2f2","#dc2626"),
}
L=[]
def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def box(x,y,w,h,title,sub,fill,stroke,th=24,sh=19):
    L.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s" stroke-width="2.2"/>'%(x,y,w,h,fill,stroke))
    if sub:
        L.append('<text x="%d" y="%d" text-anchor="middle" fill="#0f172a" font-size="%d" font-weight="700">%s</text>'%(x+w//2,y+34,th,esc(title)))
        yy=y+34+sh+8
        for line in sub:
            L.append('<text x="%d" y="%d" text-anchor="middle" fill="#334155" font-size="%d">%s</text>'%(x+w//2,yy,sh,esc(line)))
            yy+=sh+6
    else:
        L.append('<text x="%d" y="%d" text-anchor="middle" fill="#0f172a" font-size="%d" font-weight="700">%s</text>'%(x+w//2,y+h//2+9,th,esc(title)))

def layerbg(y,h,name,key):
    bg,st=PALETTE[key]
    L.append('<rect x="40" y="%d" width="%d" height="%d" rx="14" fill="%s" stroke="%s" stroke-width="1.6" opacity="0.55"/>'%(y,W-80,h,bg,st))
    L.append('<text x="74" y="%d" fill="%s" font-size="25" font-weight="800" transform="rotate(-90 74 %d)" text-anchor="middle">%s</text>'%(y+h//2,st,y+h//2,name))

def arrow(x,y1,y2,color="#94a3b8"):
    L.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3" marker-end="url(#ar)"/>'%(x,y1,x,y2,color))

rows=[]
y=70
# Layer 1 接入触发
h1=120; layerbg(y,h1,"接入触发",  "ingress")
cx=130; cw=(W-80-110-3*30)//3
box(cx,y+22,cw,h1-44,"HTTP 同步触发",["EventAnalysisView.post","拒绝 nuclio / qa- 服务"],*PALETTE["ingress"])
box(cx+cw+30,y+22,cw,h1-44,"轮询拉取",["entrys.start","alarm-gateway 近1分钟告警"],*PALETTE["ingress"])
box(cx+2*(cw+30),y+22,cw,h1-44,"消息触发",["brain · RocketMQ","PushConsumer(AI_ALERT_GROUP)"],*PALETTE["ingress"])
y1b=y+h1
y+=h1+46

# Layer 2 推理内核
h2=150; layerbg(y,h2,"推理内核","core")
box(cx,y+22,cw,h2-44,"单 Agent ReAct（主力）",["TAOPlayer · 拉普拉斯","解析→预取→读案例→ReAct","→ 12项质检 → 报告"],*PALETTE["core"])
box(cx+cw+30,y+22,cw,h2-44,"多 Agent 圆桌",["AsyncRoundTable · 5角色","receiver→analyst→planner","→k8s_engineer→examiner"],*PALETTE["core"])
box(cx+2*(cw+30),y+22,cw,h2-44,"assistant 协作（早期）",["brain.inquiry","philosopher/k8s/prom","/rocketmq 多专业助手"],*PALETTE["core"])
y2t=y; y2b=y+h2
y+=h2+46

# Layer 3 LLM
h3=110; layerbg(y,h3,"LLM 接入","llm")
lw=(W-80-110-30)//2
box(cx,y+22,lw,h3-44,"内部 AI Gateway（主）",["doubao-seed-2.0 · temperature=0","响应转 OpenAI 兼容结构"],*PALETTE["llm"])
box(cx+lw+30,y+22,lw,h3-44,"OpenAI SDK 多模型（备用）",["gpt-4o / doubao / deepseek-r1","create_completion_openai"],*PALETTE["llm"])
y3t=y; y3b=y+h3
y+=h3+46

# Layer 4 工具
h4=170; layerbg(y,h4,"只读取证工具","tool")
tools=[("k8s","describe_pod·事件·日志·HPA·ingress·service"),
       ("prometheus","Pod/Node/NodePool/JVM/Service/通用 六维指标"),
       ("info","get_pod_all_info · get_service_all_info"),
       ("log","get_pod_history_log（ClickHouse）"),
       ("changes","get_service_change_history 变更记录"),
       ("nodepool","get_nodepool_status 节点池状态"),
       ("feishu","read_feishu_document 读知识库"),
       ("memory / sniffer / terminate","记忆 · 抓包 · 受控结束"),
       ]
tcols=4; trows=2
tw=(W-80-110-(tcols+1)*22)//tcols
ty=y+20; thh=(h4-30-22)//2
for i,(tn,td) in enumerate(tools):
    r=i//tcols; c=i%tcols
    bx=cx+ -0 + c*(tw+22)
    by=ty+r*(thh+10)
    box(bx,by,tw,thh,tn,[td],*PALETTE["tool"],th=21,sh=17)
y4t=y; y4b=y+h4
y+=h4+46

# Layer 5 知识约束
h5=92; layerbg(y,h5,"知识约束","know")
kw=(W-80-110-30)//2
box(cx,y+20,kw,h5-40,"飞书「故障案例分析」表",["故障类型/现象/直接根因/解决方案/特别说明"],*PALETTE["know"],th=22,sh=18)
box(cx+kw+30,y+20,kw,h5-40,"节点池资源配置要求文档",["CPU/存核比红线 · 解决方案引用"],*PALETTE["know"],th=22,sh=18)
y5t=y
y+=h5+46

# Layer 6 输出留痕
h6=100; layerbg(y,h6,"输出留痕","out")
ow=(W-80-110-2*30)//3
box(cx,y+20,ow,h6-40,"结构化报告",["故障根因/分析凭据","/解决方案/参考链接"],*PALETTE["out"],th=22,sh=18)
box(cx+ow+30,y+20,ow,h6-40,"回贴飞书",["send_clerk","原告警消息下挂分析"],*PALETTE["out"],th=22,sh=18)
box(cx+2*(ow+30),y+20,ow,h6-40,"落库",["MySQL analysis_history","kind/target/result"],*PALETTE["out"],th=22,sh=18)
y6t=y
H=y+h6+40

# arrows between layers (中线)
xm=W//2
arrow(xm,y1b,y2t,"#7c3aed")
# core -> llm & tool (双向语义: 调用)
L.append('<text x="%d" y="%d" fill="#64748b" font-size="17">▼ 触发分析</text>'%(xm+14,(y1b+y2t)//2+6))
arrow(xm,y2b,y3t,"#0891b2")
L.append('<text x="%d" y="%d" fill="#64748b" font-size="17">▼ Function Calling 推理</text>'%(xm+14,(y2b+y3t)//2+6))
arrow(xm,y3b,y4t,"#059669")
L.append('<text x="%d" y="%d" fill="#64748b" font-size="17">▼ 选择并执行只读工具取证</text>'%(xm+14,(y3b+y4t)//2+6))
arrow(xm,y4b,y5t,"#ea580c")
L.append('<text x="%d" y="%d" fill="#64748b" font-size="17">▼ 对照案例逐项验证现象</text>'%(xm+14,(y4b+y5t)//2+6))
arrow(xm,y5t+h5,y6t,"#dc2626")
L.append('<text x="%d" y="%d" fill="#64748b" font-size="17">▼ 质检通过后输出</text>'%(xm+14,(y5t+h5+y6t)//2+6))

svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif">'%(W,H),
 '<defs><marker id="ar" markerWidth="12" markerHeight="12" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker></defs>',
 '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(W,H),
 '<text x="%d" y="42" text-anchor="middle" fill="#0f172a" font-size="32" font-weight="800">AIOps 根因分析 Agent · 总体架构</text>'%(W//2)]
svg+=L; svg.append('</svg>')
open("01_aiops-rca_architecture.svg","w").write("\n".join(svg))
print("H=%d"%H)
