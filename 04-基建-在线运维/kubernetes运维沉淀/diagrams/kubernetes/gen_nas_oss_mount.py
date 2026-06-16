# -*- coding: utf-8 -*-
# NAS / OSS 挂载给 Pod 的端到端链路图
FONT='font-family="-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif"'

NAS="#2563eb"   # NAS 共享文件
OSS="#d97706"   # OSS 对象桶
GRY="#475569"   # 通用 / 前置
GRN="#059669"   # 验证

def esc(s): return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

L=[]
W,H=1760,920
def svg_open():
    L.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" %s>'%(W,H,FONT))
    L.append('<rect x="0" y="0" width="%d" height="%d" fill="#f8fafc"/>'%(W,H))

def box(x,y,w,h,fill,stroke,lines,fs=18,tcolor="#1f2937",rx=12,lh=27,sw=2.4,tfs=21):
    L.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s" stroke="%s" stroke-width="%g"/>'%(x,y,w,h,rx,fill,stroke,sw))
    n=len(lines); ty=y+h/2-(n-1)*lh/2+fs/2-2
    for i,ln in enumerate(lines):
        fw="700" if i==0 else "400"
        size=tfs if i==0 else fs
        L.append('<text x="%d" y="%.1f" text-anchor="middle" fill="%s" font-size="%d" font-weight="%s">%s</text>'%(x+w/2,ty+i*lh,tcolor,size,fw,esc(ln)))

def arrow(x1,y1,x2,y2,color="#64748b",sw=2.6,dash=False):
    d=' stroke-dasharray="7 5"' if dash else ''
    mid=color.replace('#','')
    L.append('<defs><marker id="ah%s" markerWidth="10" markerHeight="10" refX="7.5" refY="3.2" orient="auto"><path d="M0,0 L8,3.2 L0,6.4 Z" fill="%s"/></marker></defs>'%(mid,color))
    L.append('<path d="M %d,%d L %d,%d" stroke="%s" stroke-width="%.1f" fill="none"%s marker-end="url(#ah%s)"/>'%(x1,y1,x2,y2,color,sw,d,mid))

def text(x,y,t,fs=20,color="#0f172a",w="700",anchor="start"):
    L.append('<text x="%d" y="%d" fill="%s" font-size="%d" font-weight="%s" text-anchor="%s">%s</text>'%(x,y,color,fs,w,anchor,esc(t)))

def legend(x,y,items):
    for i,(c,t) in enumerate(items):
        xx=x+i*230
        L.append('<rect x="%d" y="%d" width="24" height="18" rx="4" fill="%s"/>'%(xx,y-14,c))
        L.append('<text x="%d" y="%d" fill="#334155" font-size="17">%s</text>'%(xx+32,y,esc(t)))

svg_open()
text(44,54,"NAS / OSS 挂载给 Pod 的端到端链路",fs=31)
legend(960,50,[(NAS,"NAS 共享文件 RWX"),(OSS,"OSS 对象桶 ROX"),(GRN,"验证逐层确认")])

# ---- 前置准备 band ----
text(44,98,"前置准备：四步验通再写 YAML",fs=21,color=GRY)
pre=[
 ("① CSI 插件就绪",["csi-plugin / provisioner","NAS·OSS 驱动 Running"]),
 ("② 建存储资源",["NAS 文件系统+挂载点","或 OSS Bucket"]),
 ("③ 打通网络",["节点 VPC 可达挂载点","OSS 内网 endpoint"]),
 ("④ 准备凭证",["OSS AK/SK 最小权限","NAS 免凭证"]),
]
px=[44,476,908,1340]
for (t,b),x in zip(pre,px):
    box(x,112,388,94,"#eef2f7",GRY,[t]+b,fs=17,tfs=20)
# band down arrows to lanes
arrow(238,206,238,256,color=GRY)
arrow(1102,206,1102,256,color=GRY,dash=True)

# ---- NAS lane ----
text(44,272,"NAS 路径",fs=20,color=NAS)
ny=282
box(44,ny,346,104,"#eff6ff",NAS,["NAS 文件系统",
    "挂载点域名 :2049","子目录按业务隔离"],fs=17,tfs=20)
box(430,ny,346,104,"#eff6ff",NAS,["PV 或 StorageClass",
    "静态:手动建 PV","动态:SC volumeAs=subpath"],fs=17,tfs=20)
box(816,ny,346,104,"#eff6ff",NAS,["PVC (RWX)",
    "ReadWriteMany","多节点共享读写"],fs=17,tfs=20)
arrow(390,ny+52,430,ny+52,color=NAS)
arrow(776,ny+52,816,ny+52,color=NAS)

# ---- OSS lane ----
text(44,462,"OSS 路径",fs=20,color=OSS)
oy=472
box(44,oy,346,104,"#fff7ed",OSS,["OSS Bucket + Secret",
    "bucket / 内网 endpoint","AK 存入 Secret"],fs=17,tfs=20)
box(430,oy,346,104,"#fff7ed",OSS,["PV (ossplugin)",
    "ossfs 模拟文件系统","nodePublishSecretRef"],fs=17,tfs=20)
box(816,oy,346,104,"#fff7ed",OSS,["PVC (ROX)",
    "ReadOnlyMany","数据集只读优先"],fs=17,tfs=20)
arrow(390,oy+52,430,oy+52,color=OSS)
arrow(776,oy+52,816,oy+52,color=OSS)

# ---- merge to Pod ----
box(1262,ny+18,330,150,"#f1f5f9","#334155",["Pod",
    "volumeMounts","mountPath: /data","claimName: <pvc>"],fs=18,tfs=23,lh=30)
arrow(1162,ny+52,1262,ny+78,color=NAS)
arrow(1162,oy+52,1262,oy+128,color=OSS)

# ---- Node / kubelet ----
box(1262,612,330,104,"#f1f5f9","#334155",["Node / kubelet",
    "CSI Node 完成 mount","卷挂进容器 /data"],fs=17,tfs=21)
arrow(1427,ny+168,1427,612,color="#334155")

# ---- 验证 band ----
text(44,760,"验证：逐层确认，不止看 Pod Running",fs=21,color=GRN)
ver=[("PVC Bound",[]),("PV Bound",[]),("Pod Running",[]),
     ("exec ls /data",[]),("touch 验写 (NAS)",[])]
vx=44
for t,_ in ver:
    box(vx,776,296,72,"#ecfdf5",GRN,[t],fs=19,tfs=20)
    if vx>44:
        arrow(vx-20,812,vx,812,color=GRN)
    vx+=316

L.append('</svg>')
open("k8s-interview-nas-oss-mount.svg","w").write("\n".join(L))
print("wrote svg")
