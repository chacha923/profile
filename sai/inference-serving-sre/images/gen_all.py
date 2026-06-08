# -*- coding: utf-8 -*-
FONT='font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif"'
def svg_open(w,h,bg="#f8fafc"):
    return ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" %s>'%(w,h,FONT),
            '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>'%(w,h,bg)]
def box(L,x,y,w,h,fill,stroke,lines,fs=15,tcolor="#1f2937",rx=10,bold_first=True,lh=22,sw=2):
    L.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%d" fill="%s" stroke="%s" stroke-width="%g"/>'%(x,y,w,h,rx,fill,stroke,sw))
    n=len(lines); ty=y+h/2-(n-1)*lh/2+fs/2-2
    for i,ln in enumerate(lines):
        fw="700" if (i==0 and bold_first) else "400"
        L.append('<text x="%g" y="%.1f" text-anchor="middle" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+w/2,ty+i*lh,tcolor,fs+1 if (i==0 and bold_first) else fs,fw,ln))
def arrow(L,x1,y1,x2,y2,color="#64748b",sw=2.2,dash=False):
    d=' stroke-dasharray="6 5"' if dash else ''; mid=color.replace('#','')
    L.append('<defs><marker id="ah%s" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="%s"/></marker></defs>'%(mid,color))
    L.append('<path d="M %g,%g L %g,%g" stroke="%s" stroke-width="%.1f" fill="none"%s marker-end="url(#ah%s)"/>'%(x1,y1,x2,y2,color,sw,d,mid))
def title(L,x,y,t,fs=24):
    L.append('<text x="%d" y="%d" fill="#0f172a" font-size="%d" font-weight="700">%s</text>'%(x,y,fs,t))
def legend(L,x,y,items):
    for i,(c,t) in enumerate(items):
        xx=x+i*250
        L.append('<rect x="%d" y="%d" width="22" height="16" rx="3" fill="%s"/>'%(xx,y-13,c))
        L.append('<text x="%d" y="%d" fill="#334155" font-size="14">%s</text>'%(xx+30,y,t))
def save(L,name):
    L.append('</svg>'); open(name+".svg","w").write("\n".join(L).replace('&','&amp;'))

REAL="#2563eb"; KNOW="#d97706"; BIZ="#dc2626"

def mindmap():
    def N(t,*ch): return {"t":t,"children":list(ch)}
    root=N("推理服务·SRE",
      N("serving 解决什么",N("稳定在线服务"),N("攒批提吞吐"),N("并发调度"),N("压延迟压显存")),
      N("核心概念",N("延迟分解"),N("dynamic batching"),N("continuous batching"),N("KV cache / PagedAttn"),N("TTFT / TPOT")),
      N("四框架对标",N("TF Serving 纯TF稳"),N("TorchServe 纯PyTorch简"),N("Triton 多框架高利用"),N("vLLM LLM高吞吐")),
      N("推理性能排查",N("加载失败 格式/显存"),N("延迟高 先做分解"),N("利用率低还慢 别加卡"),N("吞吐上不去 调batch/实例"),N("OOM KV cache/batch")),
      N("落地设计",N("按约束选型"),N("统一网关+格式规范"),N("按QPS/延迟扩缩"),N("延迟分解+TTFT可观测")),
      N("经验边界",N("平台承接 真实"),N("框架对标 了解"),N("引擎内核 不开发")),
    )
    FS=17;ROW=42;TOP=46;GAP=68;PADW=10
    PAL=["#2563eb","#0891b2","#7c3aed","#dc2626","#059669","#d97706"]
    def tw(s,fs=FS): return sum((fs*1.02 if ord(c)>0x2E80 else fs*0.56) for c in s)
    for i,c in enumerate(root["children"]):
        col=PAL[i%len(PAL)]
        def paint(n,col):
            n["color"]=col
            for k in n["children"]: paint(k,col)
        paint(c,col)
    root["color"]="#475569"; cnt=[0]
    def assign(n,d):
        n["depth"]=d
        if n["children"]:
            for k in n["children"]: assign(k,d+1)
            n["y"]=(n["children"][0]["y"]+n["children"][-1]["y"])/2.0
        else:
            n["y"]=TOP+cnt[0]*ROW; cnt[0]+=1
    assign(root,0); alln=[]
    def cl(n):
        alln.append(n)
        for k in n["children"]: cl(k)
    cl(root)
    maxd=max(n["depth"] for n in alln); maxw={}
    for n in alln: maxw[n["depth"]]=max(maxw.get(n["depth"],0),tw(n["t"])+PADW*2)
    rw=tw(root["t"],20)+44; colx={0:40,1:40+rw+GAP}
    for d in range(2,maxd+1): colx[d]=colx[d-1]+maxw[d-1]+GAP
    for n in alln: n["x"]=colx[n["depth"]]; n["w"]=tw(n["t"])+PADW*2
    VW=max(n["x"]+n["w"] for n in alln)+50; VH=TOP+cnt[0]*ROW+30; rc=root["y"]
    L=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" %s>'%(int(VW),int(VH),FONT),
       '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>'%(int(VW),int(VH))]
    def conn(n):
        px,py=(40+rw,rc) if n["depth"]==0 else (n["x"]+n["w"],n["y"])
        for k in n["children"]:
            cx,cy=k["x"],k["y"]; dx=(cx-px)*0.5
            L.append('<path d="M %.1f,%.1f C %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'%(px,py,px+dx,py,cx-dx,cy,cx,cy,k["color"]))
            conn(k)
    conn(root)
    L.append('<rect x="40" y="%.1f" width="%.1f" height="50" rx="11" fill="#1e293b"/>'%(rc-25,rw))
    L.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#fff" font-size="20" font-weight="700">%s</text>'%(40+rw/2,rc+7,root["t"]))
    for n in alln:
        if n["depth"]==0: continue
        x,y,w,c=n["x"],n["y"],n["w"],n["color"]
        L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'%(x,y,x+w,y,c))
        fw="700" if n["depth"]==1 else "400"; fill=c if n["depth"]==1 else "#1f2937"
        L.append('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+PADW,y-8,fill,FS,fw,n["t"]))
    L.append('</svg>')
    open("00_inference_serving_overview_mindmap.svg","w").write("\n".join(L).replace('&','&amp;'))

def arch():
    W,H=1640,780
    L=svg_open(W,H)
    title(L,40,52,"推理服务接入链路与四框架定位")
    legend(L,40,86,[(REAL,"SRE 真实掌控"),(KNOW,"serving 层·了解+配合"),(BIZ,"模型·业务侧")])
    # pipeline
    stages=[("Client","请求 QPS",REAL),("网关 / LB","路由·限流·鉴权",REAL),
            ("Serving 框架","加载·batching·并发调度·预/后处理",KNOW),("GPU 计算","显存·算力·KV cache",REAL)]
    x=60; y=140; bw=360; bh=120; gap=40
    for i,(n,s,col) in enumerate(stages):
        bg={REAL:"#eff6ff",KNOW:"#fffbeb",BIZ:"#fef2f2"}[col]
        box(L,x,y,bw,bh,bg,col,[n,s],fs=18,tcolor="#334155",lh=28,sw=2.4)
        if i<3: arrow(L,x+bw,y+bh/2,x+bw+gap,y+bh/2,color="#64748b",sw=2.4)
        x+=bw+gap
    # model load into serving
    box(L,60+ (360+40)*2, y+bh+40, 360, 60, "#fef2f2", BIZ, ["模型(业务侧)：SavedModel/TorchScript/ONNX/TensorRT"], fs=14, tcolor=BIZ, sw=2)
    arrow(L,60+(360+40)*2+180, y+bh+40, 60+(360+40)*2+180, y+bh+8, color=BIZ, sw=2, dash=True)
    # framework positioning row
    title(L,40,440,"四框架定位（按场景，不堆功能）",fs=20)
    fr=[("TF Serving","纯 TF·成熟稳定","#0891b2"),
        ("TorchServe","纯 PyTorch·简单快上","#dc2626"),
        ("Triton","多框架·高 GPU 利用·通用首选","#7c3aed"),
        ("vLLM","LLM 专用·高吞吐·PagedAttention","#059669")]
    fx=60; fw=370; fbh=120; fy=470; fgap=30
    for n,s,col in fr:
        box(L,fx,fy,fw,fbh,"#ffffff",col,[n,s],fs=18,tcolor="#334155",lh=30,sw=2.6)
        fx+=fw+fgap
    save(L,"01_inference_serving_architecture")

def trouble():
    W,H=1740,1080
    L=svg_open(W,H)
    title(L,40,52,"推理性能排查决策树（先延迟分解，再判配置 vs 资源）")
    legend(L,40,84,[(REAL,"平台侧·SRE 处理"),(KNOW,"框架配置·SRE 配合调"),(BIZ,"模型·业务侧")])
    box(L,40,110,260,72,"#0f172a","#0f172a",["推理报障","先做延迟分解"],fs=17,tcolor="#fff",lh=24,rx=12)
    rows=[
        ("加载失败 / 起不来",KNOW,"格式/版本/依赖/显存/路径","看启动日志·模型格式·显存余量","格式/依赖=业务 · 显存/镜像=平台"),
        ("延迟高 / 超时",KNOW,"分解:排队/计算/预处理/网络","排队→并发batch·计算→模型·预处理→CPU","batch/并发/预热=配置 · 模型重=业务"),
        ("利用率低还慢",REAL,"batch没打满/并发不足/预处理卡CPU","看batch命中·并发数·CPU·GPU曲线","多为配置/预处理 · 别盲目加卡"),
        ("吞吐上不去",KNOW,"batching没开/实例不够/(LLM)KV受限","看batch配置·实例数·continuous batching","调batching+实例 · LLM看KV预算"),
        ("OOM",BIZ,"模型大/batch大/(LLM)KV cache爆","看显存随并发与序列长度变化","限batch/并发/序列 · LLM用分页省显存"),
    ]
    bx=340; ytop=110; bh=168; vg=14; src=146
    for i,(sym,col,cause,verify,concl) in enumerate(rows):
        y=ytop+i*(bh+vg)
        arrow(L,300,src,bx-12,y+bh/2,color="#94a3b8",sw=2)
        box(L,bx,y,250,bh,col,col,[sym],fs=16,tcolor="#fff",rx=12)
        bg={REAL:"#eff6ff",KNOW:"#fffbeb",BIZ:"#fef2f2"}[col]
        cells=[("可能原因",cause,"#f1f5f9"),("怎么验证",verify,"#eef2ff"),("结论/责任方",concl,bg)]
        sx=bx+266; tot=W-sx-40; cwid=(tot-2*14)/3
        for k,(lab,txt,cbg) in enumerate(cells):
            cxx=sx+k*(cwid+14)
            L.append('<rect x="%.0f" y="%d" width="%.0f" height="%d" rx="9" fill="%s" stroke="%s" stroke-width="1.6"/>'%(cxx,y,cwid,bh,cbg,col))
            L.append('<text x="%.0f" y="%d" fill="%s" font-size="14" font-weight="700">%s</text>'%(cxx+14,y+28,col,lab))
            maxc=15
            segs=[txt[t:t+maxc] for t in range(0,len(txt),maxc)]
            for si,sg in enumerate(segs[:5]):
                L.append('<text x="%.0f" y="%d" fill="#334155" font-size="13.5">%s</text>'%(cxx+14,y+54+si*22,sg))
    save(L,"02_inference_serving_troubleshooting")

def quad():
    W,H=1180,900
    L=svg_open(W,H,bg="#ffffff")
    title(L,40,52,"serving 框架定位象限（横向对标）")
    cx0,cy0,sz=140,120,720
    # axes
    L.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#f8fafc" stroke="#cbd5e1" stroke-width="2"/>'%(cx0,cy0,sz,sz))
    L.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#94a3b8" stroke-width="2"/>'%(cx0+sz/2,cy0,cx0+sz/2,cy0+sz))
    L.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#94a3b8" stroke-width="2"/>'%(cx0,cy0+sz/2,cx0+sz,cy0+sz/2))
    # axis labels
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="#475569" font-size="16" font-weight="700">通用 / 多框架  →</text>'%(cx0+sz*0.75,cy0+sz+34))
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="#475569" font-size="16" font-weight="700">←  单一框架 / 专用</text>'%(cx0+sz*0.25,cy0+sz+34))
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="#475569" font-size="16" font-weight="700" transform="rotate(-90 %d %d)">高吞吐 / 高利用率  →</text>'%(cx0-34,cy0+sz*0.28,cx0-34,cy0+sz*0.28))
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="#475569" font-size="16" font-weight="700" transform="rotate(-90 %d %d)">←  简单 / 基础</text>'%(cx0-34,cy0+sz*0.78,cx0-34,cy0+sz*0.78))
    pts=[("TorchServe","纯PyTorch·简单","#dc2626",0.26,0.74),
         ("TF Serving","纯TF·成熟稳定","#0891b2",0.30,0.40),
         ("Triton","多框架·高利用·通用首选","#7c3aed",0.74,0.30),
         ("vLLM","LLM专用·高吞吐","#059669",0.34,0.18)]
    for n,s,col,fx,fy in pts:
        px=cx0+sz*fx; py=cy0+sz*fy
        L.append('<circle cx="%g" cy="%g" r="13" fill="%s"/>'%(px,py,col))
        box(L,px-130,py-72,260,52,"#ffffff",col,[n,s],fs=15,tcolor="#334155",lh=22,sw=2.2)
        L.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="1.6"/>'%(px,py-20,px,py-13,col))
    save(L,"03_inference_serving_comparison")

mindmap(); arch(); trouble(); quad()
print("ok")
