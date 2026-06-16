# -*- coding: utf-8 -*-
import re
FONT='font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif"'
def _bump(s,k=1.22):
    return re.sub(r'font-size="([\d.]+)"', lambda m:'font-size="%.1f"'%(float(m.group(1))*k), s)

def svg_open(w,h):
    return ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" %s>'%(w,h,FONT),
            '<rect x="0" y="0" width="%d" height="%d" fill="#f8fafc"/>'%(w,h)]

def box(L,x,y,w,h,fill,stroke,lines,fs=15,tcolor="#1f2937",rx=10,bold_first=True,lh=22,sw=2):
    L.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s" stroke="%s" stroke-width="%d"/>'%(x,y,w,h,rx,fill,stroke,sw))
    n=len(lines); ty=y+h/2-(n-1)*lh/2+fs/2-2
    for i,ln in enumerate(lines):
        fw="700" if (i==0 and bold_first) else "400"
        col=tcolor if not (i==0 and bold_first) else tcolor
        L.append('<text x="%d" y="%.1f" text-anchor="middle" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+w/2,ty+i*lh,col,fs if not(i==0 and bold_first) else fs+1,fw,ln))

def arrow(L,x1,y1,x2,y2,color="#64748b",sw=2.2,dash=False):
    d=' stroke-dasharray="6 5"' if dash else ''
    L.append('<defs><marker id="ah%s" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="%s"/></marker></defs>'%(color.replace('#',''),color))
    L.append('<path d="M %d,%d L %d,%d" stroke="%s" stroke-width="%.1f" fill="none"%s marker-end="url(#ah%s)"/>'%(x1,y1,x2,y2,color,sw,d,color.replace('#','')))

def title(L,x,y,t,fs=24):
    L.append('<text x="%d" y="%d" fill="#0f172a" font-size="%d" font-weight="700">%s</text>'%(x,y,fs,t))

def save(L,name,wpx=2200):
    L.append('</svg>')
    out=_bump("\n".join(L)).replace('&','&amp;')
    open(name+".svg","w").write(out)

# ---------------- 01 principle ----------------
def d01():
    W,H=1680,940
    L=svg_open(W,H)
    title(L,40,52,"三框架角色拓扑与发现机制（PaaS 平台侧视角）")
    # top governance bar
    box(L,40,80,W-80,60,"#1e293b","#1e293b",
        ["PaaS 作业治理层  ·  统一提交 / gang & quota / 统一状态机 / TTL·GC"],fs=18,tcolor="#ffffff",rx=12)
    cols=[("TFJob","#2563eb","#eff6ff"),("PyTorchJob","#dc2626","#fef2f2"),("Ray (KubeRay)","#059669","#ecfdf5")]
    cw=500; gap=40; x0=60; ytop=180
    panels=[
        # title, header note, roles[(label, sub)], discovery
        ("角色异构 · 可局部容错",[("Chief","汇聚/完成判定"),("PS ×N","参数服务·有状态"),("Worker ×N","算力·可部分容错"),("Evaluator","评估(可选)")],"发现：TF_CONFIG 注入 env","单层调度（K8s 调 Pod）"),
        ("角色同构 · 同步 all-reduce",[("Master = rank0","既是协调也是算力"),("Worker ×N","对等 rank"),("(elastic)","torchrun min/max")],"发现：rendezvous c10d/etcd + MASTER","单层调度 · 差一个 rank 全卡"),
        ("Head 特殊 · 双层调度",[("Head","GCS+dashboard·硬单点"),("Worker ×N","算力·autoscaler 弹"),("Ray task/actor","Ray 内部再调度")],"发现：worker 向 GCS 注册(RAY_ADDRESS)","双层：K8s 调 Pod + Ray 调 task"),
    ]
    for i,(name,color,bg) in enumerate(cols):
        x=x0+i*(cw+gap)
        box(L,x,ytop,cw,640,bg,color,[],rx=14,sw=2.4)
        box(L,x,ytop,cw,52,color,color,[name],fs=20,tcolor="#ffffff",rx=14)
        sub,roles,disc,sched=panels[i]
        L.append('<text x="%d" y="%d" text-anchor="middle" fill="%s" font-size="15" font-weight="700">%s</text>'%(x+cw/2,ytop+78,color,sub))
        ry=ytop+100
        prevx,prevy=None,None
        for r,(rl,rs) in enumerate(roles):
            bx=x+50; bw=cw-100; bh=72
            box(L,bx,ry,bw,bh,"#ffffff",color,[rl,rs],fs=15,tcolor="#334155",lh=20,sw=2)
            if prevy is not None:
                arrow(L,x+cw/2,prevy,x+cw/2,ry,color=color,sw=2)
            prevy=ry+bh
            ry+=bh+34
        # discovery + sched bars
        box(L,x+40,ytop+560,cw-80,40,"#ffffff",color,[disc],fs=13,tcolor=color,rx=8,sw=1.6,bold_first=False)
        box(L,x+40,ytop+608,cw-80,40,color,color,[sched],fs=13,tcolor="#ffffff",rx=8,sw=1.6,bold_first=False)
        # connect governance bar to panel
        arrow(L,x+cw/2,140,x+cw/2,ytop,color="#94a3b8",sw=2,dash=True)
    # infra bar
    box(L,40,ytop+688,W-80,56,"#0f172a","#0f172a",
        ["基础设施层  ·  PyTorch all-reduce 对 RDMA/NCCL 最敏感   |   TFJob PS-Worker 多对多   |   Ray gRPC + 分布式 object store(吃内存)"],
        fs=15,tcolor="#e2e8f0",rx=12)
    save(L,"01_framework_governance_principle")

# ---------------- 02 mechanism ----------------
def d02():
    W,H=1720,1020
    L=svg_open(W,H)
    title(L,40,52,"四类 PaaS 治理机制的框架差异")
    cols=[("TFJob","#2563eb"),("PyTorchJob","#dc2626"),("Ray","#059669")]
    rows=[
        ("调度治理\n(gang+quota)","#7c3aed",
         ["K8s gang(Volcano)\n按角色画像汇总配额","gang 要求更硬\n差一个 rank 即阻塞","只保 head+min worker\nRay 内部 task 看不见"]),
        ("故障治理\n(失败粒度+退避)","#ea580c",
         ["角色级 restartPolicy\nWorker 可局部重试","任务级 all-or-nothing\n一个挂全重启→需熔断","app级容错(actor重建)\nHead=硬单点重点护"]),
        ("资源/弹性治理","#0891b2",
         ["提交即静态\n适配潮汐/待退资源","torchrun elastic min/max\nrendezvous 要重集合","原生 autoscaler\n与 K8s quota 易打架"]),
        ("可观测·生命周期","#db2777",
         ["operator condition\n角色 Pod 日志","rank 退出码/NCCL\n按 rank0 判完成","须采 dashboard/GCS\nPod 健康≠task 健康"]),
    ]
    lx=40; lw=240; cw=460; gap=20; cx0=lx+lw+gap; ytop=90; rh=200; rgap=18
    # header
    for j,(cn,cc) in enumerate(cols):
        x=cx0+j*(cw+gap)
        box(L,x,ytop,cw,52,cc,cc,[cn],fs=20,tcolor="#ffffff",rx=10)
    ry=ytop+52+rgap
    for ri,(rl,rc,cells) in enumerate(rows):
        box(L,lx,ry,lw,rh,rc,rc,rl.split("\n"),fs=16,tcolor="#ffffff",rx=10,lh=24)
        for j,(cn,cc) in enumerate(cols):
            x=cx0+j*(cw+gap)
            box(L,x,ry,cw,rh,"#ffffff",cc,cells[j].split("\n"),fs=16,tcolor="#334155",rx=10,lh=28,sw=2,bold_first=False)
        ry+=rh+rgap
    save(L,"02_framework_governance_mechanism")

# ---------------- 03 scenario ----------------
def d03():
    W,H=1640,860
    L=svg_open(W,H)
    title(L,40,52,"SAI 平台承接三类负载的运行时拓扑")
    box(L,40,80,W-80,58,"#1e293b","#1e293b",["SAI 训推平台  ·  统一提交入口 / 任务画像 / gang & quota / 统一状态机 / 可观测"],fs=17,tcolor="#fff",rx=12)
    cards=[
        ("TFJob 主力承接","#2563eb","#eff6ff",
         ["承接量：主力 (我熟·实践)","画像：静态·可重试·checkpoint 可控","资源：潮汐 / 在线低峰 / 待退实例","风险：夜间回收触发失败 → 退避回离线"]),
        ("PyTorchJob（数字分身多模态）","#dc2626","#fef2f2",
         ["承接量：业务承接 (我了解平台侧)","画像：同步 all-reduce·拓扑敏感","资源：专用训练池 + 拓扑感知调度","风险：少一 worker 卡 rendezvous / NCCL 超时"]),
        ("Ray 少量负载","#059669","#ecfdf5",
         ["承接量：少量 (我对标了解)","画像：双层调度·Head 单点","资源：稳定节点护 Head·避待退/Spot","风险：Pod Running 但 task 死 / Head 挂集群废"]),
    ]
    cw=500; gap=30; x0=50; ytop=180
    for i,(name,color,bg,items) in enumerate(cards):
        x=x0+i*(cw+gap)
        arrow(L,x+cw/2,138,x+cw/2,ytop,color="#94a3b8",sw=2)
        box(L,x,ytop,cw,540,bg,color,[],rx=14,sw=2.4)
        box(L,x,ytop,cw,54,color,color,[name],fs=18,tcolor="#fff",rx=14)
        iy=ytop+90
        for it in items:
            box(L,x+30,iy,cw-60,86,"#ffffff",color,it.split("：",1) if "：" in it else [it],fs=15,tcolor="#334155",lh=24,sw=1.8)
            iy+=104
    save(L,"03_framework_governance_scenario")

# ---------------- 04 troubleshooting ----------------
def d04():
    W,H=1720,980
    L=svg_open(W,H)
    title(L,40,52,"三框架统一作业排障决策树")
    box(L,40,90,300,70,"#0f172a","#0f172a",["作业异常","先判：卡在哪一层？"],fs=18,tcolor="#fff",lh=24,rx=12)
    branches=[
        ("症状：一直 Pending/起不来","#7c3aed",
         "假设：gang 没满足 / 配额不足 / 拓扑约束太严",
         "验证：PodGroup 状态 + 未调度 Pod events + quota 余量",
         "判据：部分角色 Running、部分 Pending = gang 没生效",
         "结论：补 gang / 放宽硬约束；Ray 看 head+min worker"),
        ("症状：起来了但卡死不前进","#2563eb",
         "假设：PyTorch 卡 rendezvous/NCCL；TFJob 连不上 PS；Ray 注册不上 GCS",
         "验证：rank0/Master rendezvous 等待 & NCCL 超时；Worker→PS；Worker→GCS",
         "判据：卡在握手 ≠ 卡在计算（发现层 vs 计算层）",
         "结论：修发现层(后端可达·MASTER/head 先就绪)+拓扑亲和"),
        ("症状：Pod Running 但任务已死","#ea580c",
         "假设：只采了 Pod phase，没采框架内部信号",
         "验证：PyTorch rank 退出码 / Ray job status / TFJob condition",
         "判据：框架内部信号与 Pod phase 不一致",
         "结论：完成判定接框架信号源，纠正统一状态机"),
        ("症状：反复失败抖动","#dc2626",
         "假设：无脑重试无退避；PyTorch 一 worker 反复挂触发整体重启；Ray Head 在不稳定节点",
         "验证：失败次数曲线 + 失败角色分布 + Head 节点稳定性",
         "判据：失败是否集中在某角色/某节点",
         "结论：按失败粒度退避熔断；Head/PS 上稳定节点避待退/Spot"),
    ]
    bx=420; bw=W-bx-40; ytop=92; bh=200; vgap=16
    cy_src=125
    for i,(sym,color,a,v,j,c) in enumerate(branches):
        y=ytop+i*(bh+vgap)
        arrow(L,340,cy_src,bx-12,y+bh/2,color="#94a3b8",sw=2)
        box(L,bx,y,300,bh,color,color,sym.split("：",1),fs=16,tcolor="#fff",lh=26,rx=12)
        steps=[("假设",a,"#faf5ff"),("验证",v,"#eff6ff"),("判据",j,"#fff7ed"),("结论",c,"#ecfdf5")]
        sx=bx+316; sw_=(bw-316)
        # 2x2 layout
        cellw=(sw_-16)/2; cellh=(bh-12)/2
        for k,(lab,txt,cbg) in enumerate(steps):
            r=k//2; cc=k%2
            cxx=sx+cc*(cellw+16); cyy=y+r*(cellh+12)
            L.append('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="8" fill="%s" stroke="%s" stroke-width="1.5"/>'%(cxx,cyy,cellw,cellh,cbg,color))
            L.append('<text x="%.0f" y="%.0f" fill="%s" font-size="13" font-weight="700">%s</text>'%(cxx+12,cyy+24,color,lab))
            # wrap text
            words=txt; maxc=26
            segs=[words[t:t+maxc] for t in range(0,len(words),maxc)]
            for si,sg in enumerate(segs[:3]):
                L.append('<text x="%.0f" y="%.0f" fill="#334155" font-size="12.5">%s</text>'%(cxx+12,cyy+46+si*18,sg))
    save(L,"04_framework_governance_troubleshooting")

# ---------------- 05 project connection ----------------
def d05():
    W,H=1480,720
    L=svg_open(W,H)
    title(L,40,52,"平台侧治理面与三框架的安全连接（措辞分层）")
    # center governance
    box(L,540,300,400,120,"#1e293b","#1e293b",["PaaS 作业治理面","统一提交·gang·quota·状态机·TTL","(不是统一/联邦调度器)"],fs=16,tcolor="#fff",lh=26,rx=14)
    items=[
        ("TFJob","#2563eb","实践型","主力承接 + 潮汐/待退调度","静态·画像清晰·可重试·回退成本低",140),
        ("PyTorchJob","#dc2626","了解型","数字分身多模态承接在平台","懂治理差异·不深 NCCL/rendezvous",330),
        ("Ray","#059669","对标型","少量负载","懂双层调度/Head 单点·未大规模运维",520),
    ]
    for name,color,lvl,a,b,y in items:
        box(L,40,y,420,130,"#ffffff",color,[name+"  ·  "+lvl,a,b],fs=16,tcolor="#334155",lh=30,rx=12,sw=2.4)
        arrow(L,462,y+65,540,360,color=color,sw=2.4)
    # ownership legend
    box(L,980,260,460,200,"#f1f5f9","#94a3b8",[],rx=12,sw=1.5)
    L.append('<text x="1010" y="300" fill="#0f172a" font-size="17" font-weight="700">措辞边界（不能说的话）</text>')
    notes=["× 不声称自研统一/联邦调度器","× 不声称深度调优 NCCL","× 不声称大规模生产运维 Ray","× 不把数字分身训练说成我主导实现","√ 我负责平台侧承接与治理差异"]
    for i,nt in enumerate(notes):
        col="#059669" if nt.startswith("√") else "#dc2626"
        L.append('<text x="1010" y="%d" fill="%s" font-size="15">%s</text>'%(335+i*26,col,nt))
    save(L,"05_framework_governance_project_connection")

d01(); d02(); d03(); d04(); d05()
print("all svg generated")
