# -*- coding: utf-8 -*-
import re
FONT='font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif"'
def _bump(s,k=1.0):
    return s

def svg_open(w,h,bg="#f8fafc"):
    return ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" %s>'%(w,h,FONT),
            '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>'%(w,h,bg)]

def box(L,x,y,w,h,fill,stroke,lines,fs=18,tcolor="#1f2937",rx=12,bold_first=True,lh=26,sw=2.2,align="middle"):
    L.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s" stroke="%s" stroke-width="%.1f"/>'%(x,y,w,h,rx,fill,stroke,sw))
    n=len(lines); ty=y+h/2-(n-1)*lh/2+fs/2-2
    tx = x+w/2 if align=="middle" else x+16
    for i,ln in enumerate(lines):
        fw="700" if (i==0 and bold_first) else "400"
        f = fs+1 if (i==0 and bold_first) else fs
        L.append('<text x="%d" y="%.1f" text-anchor="%s" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(tx,ty+i*lh,align,tcolor,f,fw,ln))

def arrow(L,x1,y1,x2,y2,color="#64748b",sw=2.6,dash=False):
    d=' stroke-dasharray="7 6"' if dash else ''
    mid=color.replace('#','')
    L.append('<defs><marker id="ah%s" markerWidth="10" markerHeight="10" refX="7.5" refY="3" orient="auto"><path d="M0,0 L7.5,3 L0,6 Z" fill="%s"/></marker></defs>'%(mid,color))
    L.append('<path d="M %.1f,%.1f L %.1f,%.1f" stroke="%s" stroke-width="%.1f" fill="none"%s marker-end="url(#ah%s)"/>'%(x1,y1,x2,y2,color,sw,d,mid))

def title(L,x,y,t,fs=30):
    L.append('<text x="%d" y="%d" fill="#0f172a" font-size="%d" font-weight="700">%s</text>'%(x,y,fs,t))

def tag(L,x,y,t,color,fill):
    w=len(t)*15+24
    L.append('<rect x="%d" y="%d" width="%d" height="30" rx="15" fill="%s" stroke="%s" stroke-width="1.6"/>'%(x,y,w,fill,color))
    L.append('<text x="%d" y="%d" text-anchor="middle" fill="%s" font-size="15" font-weight="700">%s</text>'%(x+w/2,y+20,color,t))
    return w

def save(L,name):
    L.append('</svg>')
    open(name+".svg","w").write("\n".join(L).replace('&','&amp;'))
    print("ok",name)

# ============ 01 architecture: 双栏运行底座对比 ============
def d01():
    W,H=2000,1280
    L=svg_open(W,H)
    title(L,40,56,"Agent 应用 ≠ 传统微服务：两套运行底座对照")
    # legend
    tag(L,1300,34,"真实生产经验",  "#059669","#ecfdf5")
    tag(L,1480,34,"理论对标(隔离运行时)","#7c3aed","#f5f3ff")
    tag(L,1760,34,"真经验可平移","#2563eb","#eff6ff")

    cw=900; gap=80; x0=50; ytop=120; colh=1080
    cols=[("传统微服务应用","#2563eb","#eff6ff","无状态请求-响应 · 长驻服务"),
          ("Agent 应用","#dc2626","#fef2f2","执行不可信代码 · 长时多步 · 会话态")]
    rows=[
        ("运行环境","#0891b2",
         ["普通容器 / Pod","共享宿主内核","进程/namespace 级隔离"],
         ["gVisor / Kata / microVM 强隔离","跑 Agent 生成的不可信代码","逃逸即宿主沦陷 → 必须强隔离"],"运行时层=理论对标"),
        ("生命周期 / 弹性","#7c3aed",
         ["分钟级调度 · 长驻","按 QPS 扩 Pod(HPA)","为长任务设计"],
         ["秒级 · 高频 · 用完即弃","Pool 预热 / Snapshot / Sleep·Resume","涌浪削峰 · 背压 · 会话态语义"],"保障层=真经验平移"),
        ("故障模型","#ea580c",
         ["崩溃重启 · 幂等重试","就绪/存活探针","副本冗余兜底"],
         ["长任务可中断可重放(durable)","死循环 / OOM 快速回收","执行失败要可解释回写"],"保障层=真经验平移"),
        ("安全保障","#dc2626",
         ["NetworkPolicy + RBAC","镜像扫描 · 最小权限","信任内部流量"],
         ["出站白名单 · syscall 裁剪","密钥注入隔离","防跨租户复用 / 数据残留"],"保障层=真经验平移"),
        ("可观测","#0ea5e9",
         ["RT / QPS / P99","Metrics + Trace","日志聚合"],
         ["全生命周期 Event 状态机","token 级指标(TTFT/TPOT)","执行链路 trace + 可解释"],"保障层=真经验平移"),
        ("发布保障","#16a34a",
         ["镜像版本 · 灰度","ArgoCD / GitOps","回滚到上一版本"],
         ["prompt/agent/工具/镜像多制品协同","运行环境瞬时就绪(Lazy Pull/预热)","保留回退到 overlayfs 直连"],"保障层=真经验平移"),
    ]
    # column headers
    for i,(nm,color,bg,sub) in enumerate(cols):
        x=x0+i*(cw+gap)
        box(L,x,ytop,cw,64,color,color,[nm],fs=24,tcolor="#ffffff",rx=14)
        L.append('<text x="%d" y="%d" text-anchor="middle" fill="%s" font-size="16" font-weight="700">%s</text>'%(x+cw/2,ytop+96,color,sub))
    ry=ytop+120; rh=145; rgap=14
    labw=0
    for r,(rl,rc,lhs,rhs,boundary) in enumerate(rows):
        # row label centered band
        L.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="10" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="1.4"/>'%(x0,ry,cw*2+gap,rh))
        L.append('<text x="%d" y="%.1f" text-anchor="middle" fill="%s" font-size="17" font-weight="700">%s</text>'%(x0+cw+gap/2,ry+26,rc,rl))
        # left card
        box(L,x0+30,ry+38,cw-360,rh-58,"#ffffff","#2563eb",lhs,fs=16,tcolor="#334155",lh=24,sw=2,align="start")
        # right card
        xr=x0+cw+gap
        box(L,xr+30,ry+38,cw-360,rh-58,"#ffffff","#dc2626",rhs,fs=16,tcolor="#334155",lh=24,sw=2,align="start")
        # left boundary chip
        L.append('<rect x="%d" y="%.1f" width="300" height="%.1f" rx="8" fill="#ecfdf5" stroke="#059669" stroke-width="1.6"/>'%(x0+cw-310,ry+38,rh-58))
        L.append('<text x="%d" y="%.1f" text-anchor="middle" fill="#047857" font-size="14" font-weight="700">真实生产经验</text>'%(x0+cw-160,ry+rh/2+4))
        # right boundary chip
        bcolor="#7c3aed" if "理论" in boundary else "#2563eb"
        bfill="#f5f3ff" if "理论" in boundary else "#eff6ff"
        L.append('<rect x="%d" y="%.1f" width="300" height="%.1f" rx="8" fill="%s" stroke="%s" stroke-width="1.6"/>'%(xr+cw-310,ry+38,rh-58,bfill,bcolor))
        L.append('<text x="%d" y="%.1f" text-anchor="middle" fill="%s" font-size="14" font-weight="700">%s</text>'%(xr+cw-160,ry+rh/2+4,bcolor,boundary))
        ry+=rh+rgap
    save(L,"00x_tmp")  # placeholder to avoid name clash; real save below
    L_ = L  # noop
    # rewrite save name
    import os
    os.replace("00x_tmp.svg","01_agent_vs_micro_architecture.svg")
    print("ok 01_agent_vs_micro_architecture")

# ============ 02 core flow: 生命周期/保障闭环对照 ============
def d02():
    W,H=2000,860
    L=svg_open(W,H)
    title(L,40,56,"运行生命周期与保障闭环：两条不同的主线")
    # lane 1 微服务
    L.append('<rect x="40" y="100" width="1920" height="320" rx="16" fill="#eff6ff" stroke="#2563eb" stroke-width="2"/>')
    box(L,40,100,260,320,"#2563eb","#2563eb",["传统微服务","保障主线"],fs=22,tcolor="#ffffff",rx=16)
    steps1=["镜像灰度发布\n(ArgoCD)","分钟级调度\n长驻 Pod","就绪/存活探针\nHPA 按 QPS 扩","崩溃→重启\n幂等重试","RT/QPS/P99\nTrace 观测"]
    x=340; y=190; bw=290; bh=140; gx=40
    px=None
    for s in steps1:
        box(L,x,y,bw,bh,"#ffffff","#2563eb",s.split("\n"),fs=17,tcolor="#1e3a8a",lh=26,sw=2.2)
        if px is not None: arrow(L,px,y+bh/2,x,y+bh/2,color="#2563eb")
        px=x+bw; x+=bw+gx
    # lane 2 agent
    L.append('<rect x="40" y="480" width="1920" height="340" rx="16" fill="#fef2f2" stroke="#dc2626" stroke-width="2"/>')
    box(L,40,480,260,340,"#dc2626","#dc2626",["Agent 应用","保障主线"],fs=22,tcolor="#ffffff",rx=16)
    steps2=["多制品就绪\nprompt/工具/镜像","Pool 取沙箱\n秒级强隔离启动","执行不可信代码\n出站白名单/限额","可中断可重放\n死循环/OOM 快回收","Snapshot/Sleep\n或用完即弃","生命周期 Event\ntoken级+可解释回写"]
    x=340; y=560; bw=250; bh=200; gx=22
    px=None
    for i,s in enumerate(steps2):
        box(L,x,y,bw,bh,"#ffffff","#dc2626",s.split("\n"),fs=16,tcolor="#7f1d1d",lh=26,sw=2.2)
        if px is not None: arrow(L,px,y+bh/2,x,y+bh/2,color="#dc2626")
        # 对账箭头回写
        px=x+bw; x+=bw+gx
    # bottom note
    box(L,40,790,1920,1,"#fef2f2","#fef2f2",[],sw=0)
    save(L,"02_agent_vs_micro_lifecycle")

# ============ 03 经验边界图 ============
def d03():
    W,H=1700,820
    L=svg_open(W,H)
    title(L,40,56,"经验边界：哪些是真经验，哪些是理论对标")
    # 真经验 left
    box(L,60,120,760,620,"#ecfdf5","#059669",[],rx=18,sw=2.4)
    box(L,60,120,760,60,"#059669","#059669",["真实生产经验（控制面 / 保障体系）"],fs=20,tcolor="#ffffff",rx=18)
    real=[
        "SAE：微服务运行底座 · 生命周期管理 · Reconcile · 灰度发布",
        "SAE：CICD 镜像构建分发(Tekton+buildx+containerd)",
        "SAI：多云 Runtime 抽象 · 状态同步 · 调度吞吐",
        "Bigeyes：Runtime Event 状态机 · 报警→根因闭环",
        "共性：生命周期 / 调度 / 状态同步 / 可观测 / 多租户治理",
    ]
    yy=210
    for t in real:
        box(L,90,yy,700,72,"#ffffff","#059669",[t],fs=16,tcolor="#065f46",sw=1.8,align="start")
        yy+=86
    # 理论对标 right
    box(L,880,120,760,620,"#f5f3ff","#7c3aed",[],rx=18,sw=2.4)
    box(L,880,120,760,60,"#7c3aed","#7c3aed",["理论对标（隔离运行时本身）"],fs=20,tcolor="#ffffff",rx=18)
    theory=[
        "gVisor / Kata / Firecracker 隔离内核",
        "Sandbox Pool 预热 / Snapshot·Restore",
        "Lazy Pull / Nydus / Dragonfly / microVM 快照",
        "会话级 Sleep / Resume（CRIU / microVM 快照）",
        "声明：没自建过隔离运行时，从 Runtime 平台视角对标",
    ]
    yy=210
    for t in theory:
        box(L,910,yy,700,72,"#ffffff","#7c3aed",[t],fs=16,tcolor="#5b21b6",sw=1.8,align="start")
        yy+=86
    # bridge
    box(L,520,760,660,46,"#1e293b","#1e293b",["桥接：把 Sandbox 当成一种特殊 Runtime，控制面/保障体系经验直接平移"],fs=15,tcolor="#e2e8f0",rx=12)
    save(L,"03_agent_vs_micro_boundary")

d01(); d02(); d03()
