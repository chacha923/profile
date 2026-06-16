# -*- coding: utf-8 -*-
def N(t, *ch): return {"t": t, "children": list(ch)}

root = N("AIOps 多Agent根因分析 · 拉普拉斯",
  N("项目定位",
    N("告警链路下游的诊断Agent"),
    N("LLM按ReAct调只读工具取证"),
    N("对照知识库案例定根因")),
  N("两种Agent形态",
    N("单Agent ReAct · 生产主力"),
    N("多Agent圆桌 · 五角色协作"),
    N("receiver→analyst→planner"),
    N("→k8s_engineer→examiner")),
  N("ReAct引擎 TAOPlayer",
    N("think-act-observe 循环"),
    N("轮数上限10 · 超限强制汇总"),
    N("状态机 · terminate唯一出口"),
    N("工具失败有限重试")),
  N("防幻觉四层",
    N("只读工具取证"),
    N("知识库故障案例逐项验证"),
    N("OBSERVER 12项否决质检"),
    N("temperature=0 确定性")),
  N("只读取证工具集",
    N("k8s · 事件 · 日志"),
    N("Prometheus 六维指标"),
    N("变更 · 节点池 · 飞书知识库"),
    N("Function Calling · 结构化回灌")),
  N("核心流程",
    N("告警解析 · 提服务树/Pod名"),
    N("预取上下文 · 读故障案例"),
    N("ReAct取证 · 现象逐项验证"),
    N("质检→回写飞书→落库")),
  N("LLM接入演进",
    N("多模型直连 gpt4o/doubao/ds"),
    N("统一走内部 AI Gateway"),
    N("响应转OpenAI兼容结构")),
  N("我的参与与改造",
    N("参与核心链路建设与改造"),
    N("改造点 · 重试仅1次容错弱"),
    N("多Agent线程+队列轮询脆"),
    N("知识库走飞书实时读耦合重")),
  N("面试边界",
    N("不主导整套平台"),
    N("工具只读 · 不自动处置"),
    N("不报准确率/MTTR指标")),
)

FS=20; ROW=52; TOP=55; GAP=80; PADW=12
PALETTE=["#7c3aed","#2563eb","#0891b2","#dc2626","#ea580c","#059669","#d97706","#4f46e5","#db2777"]

def tw(s, fs=FS):
    return sum((fs*1.02 if ord(c)>0x2E80 else fs*0.56) for c in s)

for i,c in enumerate(root["children"]):
    col=PALETTE[i%len(PALETTE)]
    def paint(n,col):
        n["color"]=col
        for k in n["children"]: paint(k,col)
    paint(c,col)
root["color"]="#475569"

cnt=[0]
def assign(n,d):
    n["depth"]=d
    if n["children"]:
        for k in n["children"]: assign(k,d+1)
        n["y"]=(n["children"][0]["y"]+n["children"][-1]["y"])/2.0
    else:
        n["y"]=TOP+cnt[0]*ROW; cnt[0]+=1
assign(root,0)

allnodes=[]
def collect(n):
    allnodes.append(n)
    for k in n["children"]: collect(k)
collect(root)

maxd=max(n["depth"] for n in allnodes)
maxw={}
for n in allnodes:
    maxw[n["depth"]]=max(maxw.get(n["depth"],0), tw(n["t"])+PADW*2)
root_w=tw(root["t"],20)+44
colx={0:40, 1:40+root_w+GAP}
for d in range(2,maxd+1): colx[d]=colx[d-1]+maxw[d-1]+GAP
for n in allnodes:
    n["x"]=colx[n["depth"]]; n["w"]=tw(n["t"])+PADW*2

VW=max(n["x"]+n["w"] for n in allnodes)+50
VH=TOP+cnt[0]*ROW+30
root_cy=root["y"]

L=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif">'%(int(VW),int(VH)),
   '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(int(VW),int(VH))]

def conn(n):
    px,py=(40+root_w,root_cy) if n["depth"]==0 else (n["x"]+n["w"],n["y"])
    for k in n["children"]:
        cx,cy=k["x"],k["y"]; dx=(cx-px)*0.5
        L.append('<path d="M %.1f,%.1f C %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'%(px,py,px+dx,py,cx-dx,cy,cx,cy,k["color"]))
        conn(k)
conn(root)

rh=54
L.append('<rect x="40" y="%.1f" width="%.1f" height="%d" rx="12" fill="#1e293b"/>'%(root_cy-rh/2,root_w,rh))
L.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#ffffff" font-size="21" font-weight="700">%s</text>'%(40+root_w/2,root_cy+7,root["t"]))
for n in allnodes:
    if n["depth"]==0: continue
    x,y,w,c=n["x"],n["y"],n["w"],n["color"]
    L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'%(x,y,x+w,y,c))
    fw="700" if n["depth"]==1 else "400"
    fill=c if n["depth"]==1 else "#1f2937"
    L.append('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+PADW,y-8,fill,FS,fw,n["t"]))
L.append('</svg>')
open("00_aiops-rca_overview_mindmap.svg","w").write("\n".join(L))
print("VW=%d VH=%d leaves=%d"%(VW,VH,cnt[0]))
