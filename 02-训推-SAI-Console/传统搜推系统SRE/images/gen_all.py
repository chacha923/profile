# -*- coding: utf-8 -*-
import re
FONT='font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif"'
def _bump(s,k=1.22):
    return re.sub(r'font-size="([\d.]+)"', lambda m:'font-size="%.1f"'%(float(m.group(1))*k), s)
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
    L.append('</svg>'); open(name+".svg","w").write(_bump("\n".join(L)).replace('&','&amp;'))
REAL="#2563eb"; KNOW="#d97706"; BIZ="#dc2626"

def mindmap():
    def N(t,*ch): return {"t":t,"children":list(ch)}
    root=N("搜推 SRE 保障",
      N("搜推在干嘛",N("召回-粗排-精排-重排 漏斗"),N("严格延迟预算"),N("模型/特征频繁更新"),N("AB 实验分流")),
      N("核心概念",N("漏斗四级 各为在线服务"),N("特征平台/实时特征"),N("模型热更新"),N("低延迟高QPS"),N("降级兜底")),
      N("SRE 排查",N("延迟突增 分段定位"),N("结果为空/劣化"),N("更新后出事 回滚"),N("高峰雪崩 限流降级")),
      N("大模型落地难",N("延迟预算对不上"),N("成本/ROI不成立"),N("增量更新慢"),N("可解释差 → 多为辅助")),
      N("如果我来做",N("分段可观测 P99"),N("分级降级体系"),N("变更安全 灰度/回滚"),N("容量过载保护")),
      N("经验边界",N("在线稳定性 可迁移"),N("算法链路 对标了解"),N("不假装算法出身")),
    )
    FS=21;ROW=46;TOP=46;GAP=55;PADW=11
    PAL=["#0891b2","#2563eb","#dc2626","#ea580c","#059669","#7c3aed"]
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
    rw=tw(root["t"],24)+48; colx={0:40,1:40+rw+GAP}
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
    L.append('<rect x="40" y="%.1f" width="%.1f" height="58" rx="11" fill="#1e293b"/>'%(rc-29,rw))
    L.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="#fff" font-size="24" font-weight="700">%s</text>'%(40+rw/2,rc+8,root["t"]))
    for n in alln:
        if n["depth"]==0: continue
        x,y,w,c=n["x"],n["y"],n["w"],n["color"]
        L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="2.4" stroke-linecap="round"/>'%(x,y,x+w,y,c))
        fw="700" if n["depth"]==1 else "400"; fill=c if n["depth"]==1 else "#1f2937"
        L.append('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+PADW,y-8,fill,FS,fw,n["t"]))
    L.append('</svg>')
    open("00_search_rec_overview_mindmap.svg","w").write("\n".join(L).replace('&','&amp;'))

def arch():
    W,H=1700,840
    L=svg_open(W,H)
    title(L,40,52,"搜推在线漏斗 + 特征平台（SRE 关注层）")
    legend(L,40,86,[(REAL,"SRE 掌控/配合"),(KNOW,"算法链路·对标了解"),(BIZ,"算法效果·业务侧")])
    # funnel
    stages=[("召回","百万→千·多路并行",KNOW),("粗排","千→百",KNOW),("精排","百→十·最重",KNOW),("重排","多样性/打散/规则",KNOW)]
    x=70; y=150; bw=300; bh=110; gap=46
    box(L,x-10,y-30,2,2,"#fff","#fff",[])
    box(L,40,y+bh/2-22,30,44,"#0f172a","#0f172a",["Client"],fs=13,tcolor="#fff",rx=6)
    px=40+30
    for i,(n,s,col) in enumerate(stages):
        cx=120+i*(bw+gap)
        bg="#fffbeb"
        box(L,cx,y,bw,bh,bg,KNOW,[n,s],fs=18,tcolor="#334155",lh=28,sw=2.4)
        arrow(L,px if i==0 else cx-gap+bw,y+bh/2,cx,y+bh/2,color="#64748b",sw=2.4) if i>0 else arrow(L,70,y+bh/2,cx,y+bh/2,color="#64748b",sw=2.4)
    # last -> return
    lastx=120+3*(bw+gap)+bw
    arrow(L,lastx,y+bh/2,lastx+46,y+bh/2,color="#64748b",sw=2.4)
    box(L,lastx+46,y+bh/2-22,70,44,"#0f172a","#0f172a",["返回"],fs=13,tcolor="#fff",rx=6)
    # delay budget banner
    L.append('<text x="120" y="%d" fill="#b45309" font-size="15" font-weight="700">整链路严格延迟预算（几十 ms 级）·每级独立超时+降级+监控</text>'%(y+bh+38))
    # side deps
    deps=[("特征平台","在线特征服务 + 实时/离线生产·进延迟预算",REAL),
          ("模型服务","频繁热更新·灰度/AB/影子/回滚",REAL),
          ("缓存层","用户/物品/结果缓存·命中率是命门",REAL),
          ("AB 实验","分流一致性·配置变更风险",REAL)]
    dy=y+bh+90; dw=380; dgap=30; dx=70
    for n,s,col in deps:
        box(L,dx,dy,dw,110,"#eff6ff",REAL,[n,s],fs=17,tcolor="#334155",lh=26,sw=2.2)
        arrow(L,dx+dw/2,dy,dx+dw/2,y+bh+8,color="#94a3b8",sw=1.8,dash=True)
        dx+=dw+dgap
    # SRE focus bar
    box(L,40,dy+150,W-80,58,"#0f172a","#0f172a",["SRE 关注：P99 长尾延迟 · 各级耗时分段 · 缓存命中 · 降级触发率 · 特征缺失率 · 模型版本 · 容量水位"],fs=16,tcolor="#e2e8f0",rx=12)
    save(L,"01_search_rec_architecture")

def trouble():
    W,H=1740,980
    L=svg_open(W,H)
    title(L,40,52,"搜推在线服务排障决策树（先降级止血，再定根因）")
    legend(L,40,84,[(REAL,"平台侧·SRE 处理"),(KNOW,"链路配置·SRE 配合"),(BIZ,"算法/特征·业务侧")])
    box(L,40,110,250,72,"#0f172a","#0f172a",["搜推报障","保:有结果不超时"],fs=16,tcolor="#fff",lh=24,rx=12)
    rows=[
        ("延迟突增 / P99 飙高",KNOW,"某级慢(精排)/特征慢/缓存掉/下游抖/容量满","按链路分段看各级耗时+缓存命中+水位","先降级慢的那级止血·容量平台扩"),
        ("结果为空 / 质量劣化",BIZ,"召回挂/特征大面积缺失/新模型劣化/降级没恢复","看召回各路返回·特征缺失率·模型版本·降级开关","召回特征定位到路·模型劣化回滚"),
        ("模型/特征更新后出事",BIZ,"新版本劣化/特征穿越/在线离线不一致/更新抖动","对比更新前后指标·特征版本·灰度AB数据","能回滚先回滚·穿越不一致甩业务"),
        ("高峰容量不够 / 雪崩",REAL,"QPS超容量/缓存击穿/依赖超时拖垮/没熔断","看水位·缓存命中·超时熔断是否生效","限流+降级+缓存兜底·扩容·补熔断"),
    ]
    bx=330; ytop=110; bh=180; vg=16; src=146
    for i,(sym,col,cause,verify,concl) in enumerate(rows):
        y=ytop+i*(bh+vg)
        arrow(L,290,src,bx-12,y+bh/2,color="#94a3b8",sw=2)
        box(L,bx,y,250,bh,col,col,[sym],fs=16,tcolor="#fff",rx=12)
        bg={REAL:"#eff6ff",KNOW:"#fffbeb",BIZ:"#fef2f2"}[col]
        cells=[("可能原因",cause,"#f1f5f9"),("怎么验证",verify,"#eef2ff"),("结论/责任方",concl,bg)]
        sx=bx+266; tot=W-sx-40; cwid=(tot-2*14)/3
        for k,(lab,txt,cbg) in enumerate(cells):
            cxx=sx+k*(cwid+14)
            L.append('<rect x="%.0f" y="%d" width="%.0f" height="%d" rx="9" fill="%s" stroke="%s" stroke-width="1.6"/>'%(cxx,y,cwid,bh,cbg,col))
            L.append('<text x="%.0f" y="%d" fill="%s" font-size="14" font-weight="700">%s</text>'%(cxx+14,y+28,col,lab))
            maxc=16
            segs=[txt[t:t+maxc] for t in range(0,len(txt),maxc)]
            for si,sg in enumerate(segs[:5]):
                L.append('<text x="%.0f" y="%d" fill="#334155" font-size="13.5">%s</text>'%(cxx+14,y+54+si*22,sg))
    save(L,"02_search_rec_troubleshooting")

def gap():
    W,H=1320,820
    L=svg_open(W,H,bg="#ffffff")
    title(L,40,52,"大模型为什么在搜推难替代精排（约束 → 务实落地）")
    cons=[("延迟预算","精排几十ms打分上千候选·大模型上百ms·量级对不上","#dc2626"),
          ("成本 / ROI","搜推超高QPS·每请求过大模型算力成本高·ROI 不成立","#ea580c"),
          ("增量 / 实时更新","搜推靠小时级特征+模型更新跟数据·大模型重训慢","#d97706"),
          ("特征体系","海量稀疏ID/交叉特征 vs 大模型文本语义范式·迁移成本高","#0891b2"),
          ("可解释 / 可控","搜推要业务规则/打散/合规可控·大模型黑盒难控","#7c3aed")]
    y=110; bw=W-80; bh=92; gap=14
    for n,s,col in cons:
        box(L,40,y,bw,bh,"#ffffff",col,[n+"：  "+s],fs=17,tcolor="#334155",sw=2.4,bold_first=True)
        L.append('<rect x="40" y="%d" width="9" height="%d" rx="4" fill="%s"/>'%(y,bh,col))
        y+=bh+gap
    box(L,40,y+8,bw,96,"#0f172a","#0f172a",
        ["务实落地：大模型在搜推多为「辅助」而非「替代」",
         "语义向量召回 · 内容理解 · 冷启动 · 生成式补充  —  不端到端取代精排"],
        fs=18,tcolor="#e2e8f0",lh=32,rx=12)
    save(L,"03_search_rec_llm_gap")

mindmap(); arch(); trouble(); gap()
print("ok")
