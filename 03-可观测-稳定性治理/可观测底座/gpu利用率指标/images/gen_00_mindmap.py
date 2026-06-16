# -*- coding: utf-8 -*-
def N(t, *ch): return {"t": t, "children": list(ch)}

root = N("GPU 利用率指标体系与低利用率治理",
  N("指标体系分层",
    N("GPU 硬件层", N("util / 显存 / 带宽"), N("SM·Tensor active"), N("功耗 / 时钟 / XID")),
    N("K8s 资源层", N("GPU request / 碎片"), N("Pod / 节点状态")),
    N("框架层", N("推理 QPS·P99·batch"), N("LLM TTFT·TPOT·KV"), N("训练 samples/s·step")),
    N("业务层", N("SLA / 错误率"), N("单位 GPU 成本"))),
  N("推理打不满成因",
    N("流量不足 / 副本过多"),
    N("batch 小 / 动态批失效"),
    N("CPU 前后处理拖慢"),
    N("显存占满算力空"),
    N("memory-bound"),
    N("调度与规格错配")),
  N("训练打不满成因",
    N("数据加载慢"),
    N("batch 太小"),
    N("模型小 / 算子碎"),
    N("分布式通信瓶颈"),
    N("checkpoint·eval 频繁"),
    N("Tensor Core 没吃到"),
    N("资源规格错配")),
  N("排障决策",
    N("先看 util+功耗+显存"),
    N("症状→假设→验证→优化"),
    N("快速判断矩阵"),
    N("瓶颈不一定在 GPU")),
  N("平台落地",
    N("GPU 资源看板"),
    N("任务 / 模型画像"),
    N("低利用率治理规则"),
    N("规格推荐 / 准入校验")),
  N("边界与误区",
    N("打满不是唯一目标"),
    N("显存高≠利用率高"),
    N("引擎内部为对标理解")),
  N("面试话术",
    N("30s / 3min / 5min"),
    N("追问树 / 高频 QA")),
)

FS=19; ROW=46; TOP=50; GAP=72; PADW=10
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
open("00_gpu_util_overview_mindmap.svg","w").write("\n".join(L))
print("VW=%d VH=%d leaves=%d"%(VW,VH,cnt[0]))
