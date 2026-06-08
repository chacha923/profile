# -*- coding: utf-8 -*-
def N(t, *ch): return {"t": t, "children": list(ch)}

root = N("训练框架治理对比",
  N("角色模型",
     N("TFJob 异构 Chief/PS/Worker"),
     N("PyTorch 同构 Master/Worker"),
     N("Ray Head/Worker · Head特殊")),
  N("调度治理",
     N("gang all-or-nothing"),
     N("单层 vs 双层调度"),
     N("Ray 配额/利用率失真")),
  N("故障治理",
     N("角色级 / 任务级 / app级"),
     N("PyTorch 一挂全重启"),
     N("Ray Head 硬单点")),
  N("资源弹性",
     N("静态 / elastic / autoscaler"),
     N("TFJob 适配潮汐待退"),
     N("弹性越强核算越难")),
  N("可观测·生命周期",
     N("完成信号源各异"),
     N("统一状态机适配"),
     N("Pod Running≠任务活")),
  N("统一排障主线",
     N("调度层 gang/quota"),
     N("发现层 rendezvous/GCS"),
     N("计算层 NCCL/算力")),
  N("项目安全连接",
     N("TFJob 实践·潮汐"),
     N("PyTorch 平台承接·了解"),
     N("Ray 少量·对标")),
)

FS=17; ROW=46; TOP=50; GAP=75; PADW=10
PALETTE=["#7c3aed","#2563eb","#0891b2","#dc2626","#ea580c","#059669","#4f46e5","#db2777"]

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

rh=50
L.append('<rect x="40" y="%.1f" width="%.1f" height="%d" rx="11" fill="#1e293b"/>'%(root_cy-rh/2,root_w,rh))
L.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#ffffff" font-size="20" font-weight="700">%s</text>'%(40+root_w/2,root_cy+7,root["t"]))
for n in allnodes:
    if n["depth"]==0: continue
    x,y,w,c=n["x"],n["y"],n["w"],n["color"]
    L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'%(x,y,x+w,y,c))
    fw="700" if n["depth"]==1 else "400"
    fill=c if n["depth"]==1 else "#1f2937"
    L.append('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+PADW,y-8,fill,FS,fw,n["t"]))
L.append('</svg>')
open("00_framework_governance_overview_mindmap.svg","w").write("\n".join(L))
print("ok")
