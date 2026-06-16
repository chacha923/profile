# -*- coding: utf-8 -*-
"""Shared helpers for GPU util diagrams. Big fonts, no overlap, wrapping chips."""

FONT = '-apple-system, PingFang SC, Microsoft YaHei, Helvetica, Arial, sans-serif'

def tw(s, fs):
    return sum((fs*1.02 if ord(c) > 0x2E80 else fs*0.56) for c in s)

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

class SVG:
    def __init__(self, w, h, bg="#ffffff"):
        self.w, self.h = w, h
        self.L = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="%s">' % (w, h, FONT),
                  '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>' % (w, h, bg)]

    def rect(self, x, y, w, h, fill, stroke="none", rx=12, sw=2):
        self.L.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" fill="%s" stroke="%s" stroke-width="%d"/>' % (x, y, w, h, rx, fill, stroke, sw))

    def text(self, x, y, s, fs, fill="#1f2937", anchor="start", weight="400"):
        self.L.append('<text x="%.1f" y="%.1f" text-anchor="%s" fill="%s" font-size="%d" font-weight="%s">%s</text>' % (x, y, anchor, fill, fs, weight, esc(s)))

    def line(self, x1, y1, x2, y2, stroke, sw=2.4, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ''
        self.L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f" stroke-linecap="round"%s/>' % (x1, y1, x2, y2, stroke, sw, d))

    def arrow(self, x1, y1, x2, y2, stroke, sw=3):
        import math
        self.L.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%.1f" stroke-linecap="round"/>' % (x1, y1, x2, y2, stroke, sw))
        ang = math.atan2(y2-y1, x2-x1); al=16; aw=0.42
        ax1=x2-al*math.cos(ang-aw); ay1=y2-al*math.sin(ang-aw)
        ax2=x2-al*math.cos(ang+aw); ay2=y2-al*math.sin(ang+aw)
        self.L.append('<path d="M %.1f,%.1f L %.1f,%.1f L %.1f,%.1f Z" fill="%s"/>' % (x2,y2,ax1,ay1,ax2,ay2,stroke))

    def path(self, d, stroke, sw=2.4, fill="none"):
        self.L.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%.1f" stroke-linecap="round"/>' % (d, fill, stroke, sw))

    def chips(self, x, y, maxw, items, fs=20, fill="#ffffff", txt="#1f2937", gap=14, vgap=14, padx=16, ch=44):
        """Lay chips left->right wrapping inside width maxw. Returns bottom y."""
        cx, cy = x, y
        for s in items:
            cw = tw(s, fs) + padx*2
            if cx + cw > x + maxw and cx > x:
                cx = x; cy += ch + vgap
            self.rect(cx, cy, cw, ch, fill, stroke="#cbd5e1", rx=10, sw=1.5)
            self.text(cx+cw/2, cy+ch/2+fs*0.36, s, fs, txt, anchor="middle")
            cx += cw + gap
        return cy + ch

    def wrap(self, s, maxw, fs):
        """Wrap text: CJK per char, Latin words intact. Returns list of lines."""
        import re
        tokens = re.findall(r'[A-Za-z0-9_./%+\-]+|\s+|[^\sA-Za-z0-9_./%+\-]', s)
        lines, cur, cw = [], "", 0
        for t in tokens:
            w = tw(t, fs)
            if t.isspace():
                if cur and cw + w <= maxw: cur += t; cw += w
                continue
            if cw + w > maxw and cur:
                lines.append(cur.rstrip()); cur, cw = t, w
            else:
                cur += t; cw += w
        if cur.strip(): lines.append(cur.rstrip())
        return lines

    def wraptext(self, cx, y, s, maxw, fs, fill="#1f2937", weight="400", lh=None, anchor="middle"):
        lh = lh or fs*1.3
        lines = self.wrap(s, maxw, fs)
        for i, ln in enumerate(lines):
            self.text(cx, y + i*lh, ln, fs, fill, anchor=anchor, weight=weight)
        return len(lines)

    def save(self, path):
        self.L.append('</svg>')
        open(path, "w").write("\n".join(self.L))
