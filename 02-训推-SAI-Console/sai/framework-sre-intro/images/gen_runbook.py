# -*- coding: utf-8 -*-
import re
FONT='font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif"'
def _bump(s,k=1.18):
    return re.sub(r'font-size="([\d.]+)"', lambda m:'font-size="%.1f"'%(float(m.group(1))*k), s)
REAL="#2563eb"; KNOW="#d97706"; BIZ="#dc2626"
def box(L,x,y,w,h,fill,stroke,lines,fs=14,tcolor="#1f2937",rx=9,bold_first=True,lh=20,sw=2,anchor="middle",lx=None):
    L.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%d" fill="%s" stroke="%s" stroke-width="%g"/>'%(x,y,w,h,rx,fill,stroke,sw))
    n=len(lines); ty=y+h/2-(n-1)*lh/2+fs/2-2
    for i,ln in enumerate(lines):
        fw="700" if (i==0 and bold_first) else "400"
        tx=x+w/2 if anchor=="middle" else (x+(lx or 12))
        L.append('<text x="%g" y="%.1f" text-anchor="%s" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(tx,ty+i*lh,anchor,tcolor,fs+1 if (i==0 and bold_first) else fs,fw,ln))
W,H=1760,1020
L=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" %s>'%(W,H,FONT),
   '<rect width="%d" height="%d" fill="#ffffff"/>'%(W,H)]
L.append('<text x="40" y="50" fill="#0f172a" font-size="26" font-weight="700">训练 / 推理框架排查 一页速查卡（SRE）</text>')
# legend
for i,(c,t) in enumerate([(REAL,"平台侧·SRE 直接处理"),(KNOW,"框架层·SRE 配合判断"),(BIZ,"业务侧·甩回业务")]):
    xx=40+i*300
    L.append('<rect x="%d" y="68" width="22" height="16" rx="3" fill="%s"/>'%(xx,c))
    L.append('<text x="%d" y="82" fill="#334155" font-size="15">%s</text>'%(xx+30,t))
# two columns
def colhdr(x,t,col):
    box(L,x,108,820,44,col,col,[t],fs=19,tcolor="#fff",rx=10)
colhdr(40,"训练类报障","#1d4ed8")
colhdr(900,"推理类报障","#047857")
def card(x,y,w,sym,col,lines):
    bg={REAL:"#eff6ff",KNOW:"#fffbeb",BIZ:"#fef2f2"}[col]
    h=24+len(lines)*22+18
    L.append('<rect x="%g" y="%g" width="%g" height="%g" rx="10" fill="%s" stroke="%s" stroke-width="2.2"/>'%(x,y,w,h,bg,col))
    L.append('<rect x="%g" y="%g" width="8" height="%g" rx="4" fill="%s"/>'%(x,y,h,col))
    L.append('<text x="%g" y="%g" fill="%s" font-size="17" font-weight="700">%s</text>'%(x+22,y+26,col,sym))
    for i,ln in enumerate(lines):
        L.append('<text x="%g" y="%g" fill="#334155" font-size="14">%s</text>'%(x+22,y+50+i*22,ln))
    return y+h+16
# training cards
y=168; x=40; w=820
y=card(x,y,w,"Pending / 起不来",REAL,["看：Pod events / PodGroup / quota / 镜像 / PVC","根因：配额不足·gang没满足·taint·镜像·PVC","→ 平台侧 90% 直接处理"])
y=card(x,y,w,"卡死不动",KNOW,["看：rank0 NCCL超时 / rendezvous / PS / DataLoader","判：等对端=gang/发现层；网络=平台；通信配置=业务","→ 网络存储平台修，配置/数据甩业务"])
y=card(x,y,w,"OOM",BIZ,["先分：CUDA OOM(显存,调batch/精度)","       vs K8s OOMKill(内存,调limit) — 别混","看：显存曲线 / 容器内存 limit"])
y=card(x,y,w,"变慢 / GPU 利用率低",KNOW,["先判：等数据 / 等通信 / 慢节点 straggler","看：利用率vs等待·各rank进度·带宽·RDMA·DataLoader"])
# inference cards
y=168; x=900
y=card(x,y,w,"加载失败 / 起不来",KNOW,["看：启动日志·模型格式/版本·依赖·显存·路径","判：格式/依赖=业务；显存/镜像/存储=平台"])
y=card(x,y,w,"延迟高 / 超时",KNOW,["先做延迟分解：排队 / 计算 / 预处理 / 网络","排队长→并发batch；计算长→模型；预处理长→CPU"])
y=card(x,y,w,"利用率低但还慢",REAL,["多为：batch没打满 / 并发不足 / 预处理卡CPU","→ 别盲目加卡，先查 batch 和并发"])
y=card(x,y,w,"吞吐上不去 / 推理OOM",BIZ,["吞吐：batching没开/实例少/(LLM)KV受限","OOM：模型大·batch大·(LLM)KV cache爆 → 限/分页"])
# golden rules bar
gy=H-150
L.append('<rect x="40" y="%d" width="%d" height="118" rx="12" fill="#0f172a"/>'%(gy,W-80))
L.append('<text x="64" y="%d" fill="#fff" font-size="18" font-weight="700">黄金判断点</text>'%(gy+32))
rules=["训练显存≈推理几倍 → 训练 OOM 更常见","CUDA OOM(显存) ≠ K8s OOMKill(内存)","GPU 利用率低 ≠ GPU 不够 → 先查 batch/并发/预处理",
       "训练卡死先看发现/通信层(NCCL/rendezvous)，不是算力","推理慢先做延迟分解，不是先看模型","业务不懂框架 → 给报障模板+指定日志/指标+最小验证"]
for i,r in enumerate(rules):
    cx=64+(i%3)*560; cy=gy+62+(i//3)*30
    L.append('<text x="%d" y="%d" fill="#e2e8f0" font-size="15">• %s</text>'%(cx,cy,r))
L.append('</svg>')
open("04_framework_sre_runbook_card.svg","w").write(_bump("\n".join(L)).replace('&','&amp;'))
print("ok")
