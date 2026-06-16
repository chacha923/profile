# -*- coding: utf-8 -*-
import re
FONT='font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif"'
def _bump(s,k=1.22):
    return re.sub(r'font-size="([\d.]+)"', lambda m:'font-size="%.1f"'%(float(m.group(1))*k), s)
def svg_open(w,h,bg="#f8fafc"):
    return ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" %s>'%(w,h,FONT),
            '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>'%(w,h,bg)]
def box(L,x,y,w,h,fill,stroke,lines,fs=15,tcolor="#1f2937",rx=10,bold_first=True,lh=22,sw=2):
    L.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s" stroke="%s" stroke-width="%g"/>'%(x,y,w,h,rx,fill,stroke,sw))
    n=len(lines); ty=y+h/2-(n-1)*lh/2+fs/2-2
    for i,ln in enumerate(lines):
        fw="700" if (i==0 and bold_first) else "400"
        L.append('<text x="%d" y="%.1f" text-anchor="middle" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+w/2,ty+i*lh,tcolor,fs+1 if (i==0 and bold_first) else fs,fw,ln))
def arrow(L,x1,y1,x2,y2,color="#64748b",sw=2.2,dash=False):
    d=' stroke-dasharray="6 5"' if dash else ''
    mid=color.replace('#','')
    L.append('<defs><marker id="ah%s" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="%s"/></marker></defs>'%(mid,color))
    L.append('<path d="M %d,%d L %d,%d" stroke="%s" stroke-width="%.1f" fill="none"%s marker-end="url(#ah%s)"/>'%(x1,y1,x2,y2,color,sw,d,mid))
def title(L,x,y,t,fs=24):
    L.append('<text x="%d" y="%d" fill="#0f172a" font-size="%d" font-weight="700">%s</text>'%(x,y,fs,t))
def legend(L,x,y,items):
    for i,(c,t) in enumerate(items):
        xx=x+i*270
        L.append('<rect x="%d" y="%d" width="22" height="16" rx="3" fill="%s"/>'%(xx,y-13,c))
        L.append('<text x="%d" y="%d" fill="#334155" font-size="14">%s</text>'%(xx+30,y,t))
def save(L,name):
    L.append('</svg>')
    open(name+".svg","w").write(_bump("\n".join(L)).replace('&','&amp;'))

REAL="#2563eb"   # SRE 真实掌控
KNOW="#d97706"   # 框架了解
BIZ="#dc2626"    # 业务侧

# ---- 00 mindmap ----
def mindmap():
    def N(t,*ch): return {"t":t,"children":list(ch)}
    root=N("框架科普·SRE排查",
      N("框架是什么",N("计算图 动态/静态"),N("autograd 训练核心"),N("分布式扩展"),N("serving 部署")),
      N("PyTorch",N("动态图 eager"),N("训练为主业"),N("推理转 TorchScript/ONNX")),
      N("TensorFlow",N("训练+推理都强"),N("TF1静态/TF2 eager"),N("TF Serving/TFLite")),
      N("训练视角",N("吃显存 反向+优化器"),N("分布式 NCCL/PS"),N("checkpoint 容错"),N("故障:Pending/卡死/OOM/慢")),
      N("推理视角",N("只前向"),N("延迟/吞吐/batch"),N("故障:加载/延迟/利用率低")),
      N("SRE 分层排查",N("基础设施层 平台侧"),N("框架层 配合查"),N("业务代码层 甩回业务")),
      N("经验边界",N("TFJob 熟·实践"),N("PyTorch 了解"),N("NCCL/内核 对标")),
    )
    FS=21;ROW=46;TOP=46;GAP=58;PADW=11
    PAL=["#7c3aed","#2563eb","#0891b2","#dc2626","#ea580c","#059669","#db2777"]
    def tw(s,fs=FS): return sum((fs*1.02 if ord(c)>0x2E80 else fs*0.56) for c in s)
    for i,c in enumerate(root["children"]):
        col=PAL[i%len(PAL)]
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
    alln=[]
    def col_(n):
        alln.append(n)
        for k in n["children"]: col_(k)
    col_(root)
    maxd=max(n["depth"] for n in alln); maxw={}
    for n in alln: maxw[n["depth"]]=max(maxw.get(n["depth"],0),tw(n["t"])+PADW*2)
    root_w=tw(root["t"],24)+48; colx={0:40,1:40+root_w+GAP}
    for d in range(2,maxd+1): colx[d]=colx[d-1]+maxw[d-1]+GAP
    for n in alln: n["x"]=colx[n["depth"]]; n["w"]=tw(n["t"])+PADW*2
    VW=max(n["x"]+n["w"] for n in alln)+50; VH=TOP+cnt[0]*ROW+30; rc=root["y"]
    L=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" %s>'%(int(VW),int(VH),FONT),
       '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(int(VW),int(VH))]
    def conn(n):
        px,py=(40+root_w,rc) if n["depth"]==0 else (n["x"]+n["w"],n["y"])
        for k in n["children"]:
            cx,cy=k["x"],k["y"]; dx=(cx-px)*0.5
            L.append('<path d="M %.1f,%.1f C %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'%(px,py,px+dx,py,cx-dx,cy,cx,cy,k["color"]))
            conn(k)
    conn(root)
    L.append('<rect x="40" y="%.1f" width="%.1f" height="58" rx="11" fill="#1e293b"/>'%(rc-29,root_w))
    L.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#fff" font-size="24" font-weight="700">%s</text>'%(40+root_w/2,rc+8,root["t"]))
    for n in alln:
        if n["depth"]==0: continue
        x,y,w,c=n["x"],n["y"],n["w"],n["color"]
        L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'%(x,y,x+w,y,c))
        fw="700" if n["depth"]==1 else "400"; fill=c if n["depth"]==1 else "#1f2937"
        L.append('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+PADW,y-8,fill,FS,fw,n["t"]))
    L.append('</svg>')
    open("00_framework_sre_overview_mindmap.svg","w").write("\n".join(L).replace('&','&amp;'))

# ---- 01 architecture ----
def arch():
    W,H=1640,860
    L=svg_open(W,H)
    title(L,40,52,"训练栈 vs 推理栈分层（SRE 掌控层 vs 框架了解层）")
    legend(L,40,86,[(REAL,"SRE 真实掌控/能动手"),(KNOW,"框架层·了解+配合查"),(BIZ,"业务代码层·甩回业务")])
    cols=[("训练栈","#1d4ed8"),("推理栈","#047857")]
    layers_t=[("业务训练代码","模型 / 超参 / 数据 / batch",BIZ),
              ("框架层","PyTorch/TF + NCCL + DataLoader + checkpoint",KNOW),
              ("容器 / K8s / 调度","gang · 配额 · 镜像 · PVC",REAL),
              ("基础设施","GPU · 网络(RDMA) · 存储(NAS)",REAL)]
    layers_i=[("业务请求","QPS / batch / 预处理·后处理",BIZ),
              ("serving 框架","TF Serving/TorchServe/Triton + 模型格式",KNOW),
              ("容器 / K8s / HPA","副本 · 配额 · 弹性 · 镜像",REAL),
              ("基础设施","GPU · 网络 · 存储",REAL)]
    cw=720; gap=60; x0=70; ytop=130; lh=130; lg=16
    for ci,(cn,cc) in enumerate(cols):
        x=x0+ci*(cw+gap)
        box(L,x,ytop,cw,46,cc,cc,[cn],fs=20,tcolor="#fff",rx=10)
        ly=ytop+62
        layers=layers_t if ci==0 else layers_i
        for ln,sub,col in layers:
            bg={REAL:"#eff6ff",KNOW:"#fffbeb",BIZ:"#fef2f2"}[col]
            box(L,x,ly,cw,lh,bg,col,[ln,sub],fs=17,tcolor="#334155",lh=28,sw=2.2)
            ly+=lh+lg
    save(L,"01_framework_sre_architecture")

# ---- 02 troubleshooting ----
def trouble():
    W,H=1740,1000
    L=svg_open(W,H)
    title(L,40,52,"业务报障 → SRE 分层定位决策树")
    legend(L,40,84,[(REAL,"平台侧·SRE 处理"),(KNOW,"跨层·SRE 配合判断"),(BIZ,"业务侧·甩回业务")])
    box(L,40,110,260,70,"#0f172a","#0f172a",["业务模糊报障","先分层:哪一层?"],fs=17,tcolor="#fff",lh=24,rx=12)
    rows=[
        ("Pending / 起不来",REAL,"基础设施/调度层","GPU配额不足·gang没满足·taint·镜像失败·PVC挂不上","看 Pod events / PodGroup / quota","平台侧 SRE 直接处理"),
        ("卡死不动",KNOW,"框架通信/发现层","NCCL超时·rendezvous差worker·PS连不上·DataLoader卡数据","看 rank0/Master NCCL/rendezvous 日志","网络/存储=平台 · 通信配置=业务"),
        ("OOM 显存爆",BIZ,"业务代码层(多)","batch太大·模型太大·没开梯度累积/混合精度","分清 CUDA OOM vs K8s OOMKill","CUDA OOM=业务调参 · OOMKill=改limit"),
        ("变慢 / 利用率低",KNOW,"跨层","DataLoader喂不饱·慢节点straggler·带宽不够·没用RDMA","看 GPU利用率 vs 等待 · 各rank进度","先分:等数据 还是 等通信"),
    ]
    bx=340; ytop=110; bh=190; vg=16; src=145
    for i,(sym,col,layer,cause,verify,concl) in enumerate(rows):
        y=ytop+i*(bh+vg)
        arrow(L,300,src,bx-12,y+bh/2,color="#94a3b8",sw=2)
        box(L,bx,y,260,bh,col,col,[sym,layer],fs=16,tcolor="#fff",lh=26,rx=12)
        bg={REAL:"#eff6ff",KNOW:"#fffbeb",BIZ:"#fef2f2"}[col]
        cells=[("可能原因",cause,"#f1f5f9"),("怎么验证",verify,"#eef2ff"),("结论/责任方",concl,bg)]
        sx=bx+276; tot=W-sx-40; cwid=(tot-2*14)/3
        for k,(lab,txt,cbg) in enumerate(cells):
            cxx=sx+k*(cwid+14)
            L.append('<rect x="%.0f" y="%d" width="%.0f" height="%d" rx="9" fill="%s" stroke="%s" stroke-width="1.6"/>'%(cxx,y,cwid,bh,cbg,col))
            L.append('<text x="%.0f" y="%d" fill="%s" font-size="14" font-weight="700">%s</text>'%(cxx+14,y+28,col,lab))
            maxc=14
            segs=[txt[t:t+maxc] for t in range(0,len(txt),maxc)]
            for si,sg in enumerate(segs[:6]):
                L.append('<text x="%.0f" y="%d" fill="#334155" font-size="13.5">%s</text>'%(cxx+14,y+54+si*22,sg))
    save(L,"02_framework_sre_troubleshooting")

# ---- 03 train vs infer ----
def cmp():
    W,H=1480,820
    L=svg_open(W,H)
    title(L,40,52,"训练 vs 推理：故障形态横向对标（SRE 关注点）")
    cols=[("训练","#1d4ed8","#eff6ff"),("推理","#047857","#ecfdf5")]
    rows=[
        ("计算","前向+反向+参数更新","只前向"),
        ("显存","激活+梯度+优化器(几倍)","只装模型+激活(小)"),
        ("时长/形态","长任务·分布式·多卡","常驻服务·并发请求"),
        ("关键资源","GPU·NCCL通信·NAS checkpoint","GPU·batch·CPU预处理"),
        ("典型故障","Pending/卡死/OOM/慢/慢节点","加载失败/延迟高/利用率低"),
        ("SRE 核心指标","各rank进度·GPU利用率·通信","P99延迟·QPS·batch命中"),
    ]
    lx=40; lw=210; cw=580; gap=20; cx0=lx+lw+gap; ytop=86; rh=108; rg=12
    for j,(cn,cc,_) in enumerate(cols):
        x=cx0+j*(cw+gap)
        box(L,x,ytop,cw,46,cc,cc,[cn],fs=20,tcolor="#fff",rx=10)
    ry=ytop+58
    for rl,tv,iv in rows:
        box(L,lx,ry,lw,rh,"#334155","#334155",[rl],fs=17,tcolor="#fff",rx=9)
        for j,(cn,cc,bg) in enumerate(cols):
            x=cx0+j*(cw+gap); v=tv if j==0 else iv
            box(L,x,ry,cw,rh,bg,cc,v.split("·") if v.count("·")>=2 else [v],fs=16,tcolor="#334155",lh=26,sw=2,bold_first=False)
        ry+=rh+rg
    save(L,"03_framework_sre_train_vs_infer")

mindmap(); arch(); trouble(); cmp()
print("ok")
