# -*- coding: utf-8 -*-
def N(t, *ch): return {"t": t, "children": list(ch)}

root = N("Agent应用 vs 微服务",
  N("经验边界",
     N("隔离运行时·理论对标"),
     N("控制面/保障·真经验"),
     N("先声明再展开")),
  N("运行环境差异",
     N("共享内核→强隔离"),
     N("分钟长驻→秒级即弃"),
     N("镜像拉取→瞬时就绪")),
  N("保障体系差异",
     N("探针重启→durable可重放"),
     N("HPA按QPS→涌浪削峰"),
     N("RBAC→出站白名单/防残留"),
     N("P99→Event状态机+token")),
  N("为什么微服务不够",
     N("不可信代码逃逸"),
     N("秒级高频突发"),
     N("会话态/数据残留")),
  N("如果让我落地",
     N("复用控制面跑闭环"),
     N("可插拔隔离后端"),
     N("冷启动分层提速"),
     N("多租户+安全收紧")),
  N("排障主线",
     N("会话→沙箱→隔离层"),
     N("Event时间线+日志"),
     N("回写用户可理解结论")),
  N("项目安全连接",
     N("SAE 微服务底座·实践"),
     N("SAI 多云Runtime·实践"),
     N("Bigeyes 闭环·设计")),
)

FS=22; ROW=50; TOP=54; GAP=64; PADW=12
PALETTE=["#7c3aed","#2563eb","#0891b2","#dc2626","#ea580c","#059669","#db2777"]

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
root_w=tw(root["t"],26)+52
colx={0:44, 1:44+root_w+GAP}
for d in range(2,maxd+1): colx[d]=colx[d-1]+maxw[d-1]+GAP
for n in allnodes:
    n["x"]=colx[n["depth"]]; n["w"]=tw(n["t"])+PADW*2

VW=max(n["x"]+n["w"] for n in allnodes)+54
VH=TOP+cnt[0]*ROW+34
root_cy=root["y"]

L=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif">'%(int(VW),int(VH)),
   '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(int(VW),int(VH))]

def conn(n):
    px,py=(44+root_w,root_cy) if n["depth"]==0 else (n["x"]+n["w"],n["y"])
    for k in n["children"]:
        cx,cy=k["x"],k["y"]; dx=(cx-px)*0.5
        L.append('<path d="M %.1f,%.1f C %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="2.6" stroke-linecap="round"/>'%(px,py,px+dx,py,cx-dx,cy,cx,cy,k["color"]))
        conn(k)
conn(root)

rh=62
L.append('<rect x="44" y="%.1f" width="%.1f" height="%d" rx="12" fill="#1e293b"/>'%(root_cy-rh/2,root_w,rh))
L.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#ffffff" font-size="26" font-weight="700">%s</text>'%(44+root_w/2,root_cy+9,root["t"]))
for n in allnodes:
    if n["depth"]==0: continue
    x,y,w,c=n["x"],n["y"],n["w"],n["color"]
    L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.6" stroke-linecap="round"/>'%(x,y,x+w,y,c))
    fw="700" if n["depth"]==1 else "400"
    fill=c if n["depth"]==1 else "#1f2937"
    L.append('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+PADW,y-9,fill,FS,fw,n["t"]))
L.append('</svg>')
open("00_agent_vs_micro_overview_mindmap.svg","w").write("\n".join(L))
print("ok mindmap")
