import os
import json, math, re, os

SP=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
D=json.load(open(f'{SP}/mapdata.json'))
ALIAS={'MID':'MAO','GOL':'LYO','TYN':'TYS','NAT':'NAO','NRG':'NWG'}
PV={ALIAS.get(k,k):v for k,v in D['provinces'].items()}
CO=D['coastAnchors']
LAYER=D['layer']   # every MapLayer shape, in document order
P=json.load(open(f'{SP}/palette.json'))   # derived from Radix Colors (MIT)

POW=['AUSTRIA','ENGLAND','FRANCE','GERMANY','ITALY','RUSSIA','TURKEY']
ABBR={'AUSTRIA':'AUS','ENGLAND':'ENG','FRANCE':'FRA','GERMANY':'GER','ITALY':'ITA','RUSSIA':'RUS','TURKEY':'TUR'}
FILL=P['fill']; TOK=P['token']; INK=P['ink']
C=TOK                                  # "the power's colour" = its solid token colour
SEA=P['sea']; SEA_LINE=P['seaLine']; NEUTRAL=P['neutral']
COASTINK=P['coast']; HALO='#ffffff'
MAPINK=P['slate']['12']; SHUT=P['sand']['8']
BORDERINK='#1E2227'; UNPLAYABLE='#C2C7CA'
BRASS='#C8912F'; BRASS_HI='#E7B85E'; FAILINK='#15181C'
CH0='#0F141B'; CH1='#161D26'; CH2='#1F2833'; CH3='#2B3644'; CH4='#3A4757'
HI='#E7ECF2'; MID='#9AA8B8'; LO='#69768A'; OK='#4E8C6A'
PAPER=SEA

def mix(a,b,t):
    a=a.lstrip('#'); b=b.lstrip('#')
    if len(a)==3: a=''.join(c*2 for c in a)
    if len(b)==3: b=''.join(c*2 for c in b)
    f=lambda s,i:int(s[i:i+2],16)
    return '#%02x%02x%02x'%tuple(round(f(a,i)+(f(b,i)-f(a,i))*t) for i in (0,2,4))
def tint(power): return FILL[power]
def dtint(power): return mix('#131A22', TOK[power], 0.42)

FONTS=('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
 'family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400'
 '&amp;family=Barlow:wght@400;500;600&amp;family=IBM+Plex+Mono:wght@400;500&amp;display=swap">')
FD='"Newsreader",Georgia,"Times New Roman",serif'
FU='"Barlow","Helvetica Neue",Arial,sans-serif'
FM='"IBM Plex Mono",Menlo,Consolas,monospace'
FU_SVG='Barlow, Helvetica Neue, Arial, sans-serif'

def a(p):
    if p in CO: return CO[p]['u']
    return PV[p]['unit']
def lab(p): return PV[p]['label']
def sc(p): return PV[p]['scDot']
def bbox(path):
    n=[float(x) for x in re.findall(r'-?\d+\.?\d*',path)]
    return min(n[0::2]),min(n[1::2]),max(n[0::2]),max(n[1::2])
def in_box(p,box):
    x0,y0,x1,y1=bbox(PV[p]['path'])
    return x0<box[2] and x1>box[0] and y0<box[3] and y1>box[1]
def crop_keys(box): return [k for k in PV if in_box(k,box)]

# ---------------------------------------------------------------- map layers
def shapes(keys, owners, dark=False, glow=(), dim=()):
    """Render MapLayer exactly as standard.svg builds it.

    The file opens MapLayer with <rect fill="black" width="1835" height="1360">, then
    lays every shape on top with a small gap between neighbours. THE GAPS ARE THE
    BORDERS -- the backing shows through them. Put sea colour back there and every
    border becomes a channel of water between the countries. No province stroke is
    wanted. Shapes are drawn in document order because the decorative fills
    (Iceland and Ireland, the Danish and Bosphorus straits) are interleaved with the
    sea polygons and must land in the right place.
    """
    keys=set(keys)
    sea_f  = '#16232D' if dark else SEA
    land_n = '#1B222B' if dark else NEUTRAL
    unp    = '#232C36' if dark else UNPLAYABLE
    backing= '#000000' if dark else BORDERINK
    o=[f'<rect x="0" y="0" width="1835" height="1360" fill="{backing}"/>']
    for e in LAYER:
        prov, cls, d = e['p'], e['c'], e['d']
        if prov is not None and prov not in keys: continue
        if cls=='water':
            f=sea_f
        elif cls=='neutral':
            f=unp
        elif cls=='impassable':
            f='url(#shut)'
        else:
            ow=owners.get(prov) if prov else None
            f=(dtint(ow) if dark else FILL[ow]) if ow else land_n
            if prov in dim: f=mix(f, sea_f, 0.5)
        o.append(f'<path d="{d}" fill="{f}"/>')
    for k in glow:
        if k in PV:
            o.append(f'<path d="{PV[k]["path"]}" fill="{BRASS}" fill-opacity="0.38" '
                     f'stroke="{BRASS_HI}" stroke-width="3" stroke-dasharray="8 5"/>')
    return chr(10).join(o)

def coastline(keys, dark=False):
    return ''   # kept for call-compatibility; the coast is drawn inside shapes()

def _star(x,y,r,fill,stroke,sw):
    pts=[]
    for i in range(10):
        ang=-math.pi/2+i*math.pi/5
        rr=r if i%2==0 else r*0.44
        pts.append(f'{x+rr*math.cos(ang):.1f},{y+rr*math.sin(ang):.1f}')
    return (f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linejoin="round"/>')

def sc_marks(keys, owners, dark=False, homes=None, size=1.0):
    o=[]
    for k in keys:
        p=PV[k]
        if not p['sc'] or not p['scDot']: continue
        x,y=p['scDot']; r=7.4*size
        if p['home']:
            o.append(f'<circle cx="{x}" cy="{y}" r="{r+3.6:.1f}" fill="none" stroke="{COASTINK}" '
                     f'stroke-width="1.5" stroke-opacity="0.55"/>')
        o.append(_star(x,y,r,'#FFFFFF',COASTINK,1.5*size))
    return '\n'.join(o)

def labels(keys, dark=False, size=11.5):
    col='#C3D1DD' if dark else MAPINK
    halo='#101820' if dark else '#FFFFFF'
    o=[]
    for k in keys:
        p=PV[k]
        if not p['label']: continue
        x,y=p['label']
        op='0.72' if p['kind']=='sea' else '0.95'
        o.append(f'<text x="{x}" y="{y}" font-family="{FU_SVG}" font-size="{size}" font-weight="600" '
                 f'letter-spacing="0.6" fill="{col}" fill-opacity="{op}" stroke="{halo}" stroke-width="2.6" '
                 f'stroke-opacity="0.8" paint-order="stroke" stroke-linejoin="round">{k[:3]}</text>')
    return '\n'.join(o)

# ---------------------------------------------------------------- units
def token(power, kind, xy, state='', scale=1.0):
    x,y=xy; s=scale; col=TOK[power]; edge='#FFFFFF'; rim=INK[power]
    op='0.45' if state=='ghost' else '1'
    o=[f'<g opacity="{op}">']
    if state=='sel':
        o.append(f'<circle cx="{x}" cy="{y}" r="{19*s:.1f}" fill="{BRASS}" fill-opacity="0.28"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="{16.5*s:.1f}" fill="none" stroke="{BRASS_HI}" stroke-width="{2.8*s:.1f}"/>')
    if state=='unordered':
        o.append(f'<circle cx="{x}" cy="{y}" r="{17*s:.1f}" fill="none" stroke="{BRASS}" '
                 f'stroke-width="{2*s:.1f}" stroke-dasharray="3 3.4"/>')
    o.append(f'<ellipse cx="{x}" cy="{y+9.5*s:.1f}" rx="{10*s:.1f}" ry="{3*s:.1f}" fill="#0B1015" fill-opacity="0.22"/>')
    if kind=='A':
        o.append(f'<circle cx="{x}" cy="{y}" r="{10.6*s:.1f}" fill="{col}" stroke="{edge}" stroke-width="{2.2*s:.1f}"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="{10.6*s:.1f}" fill="none" stroke="{rim}" stroke-width="{0.9*s:.1f}" stroke-opacity="0.5"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="{4.2*s:.1f}" fill="{edge}" fill-opacity="0.55"/>')
    else:
        h=(f'M {x-11.4*s:.1f} {y-2.6*s:.1f} L {x+11.4*s:.1f} {y-2.6*s:.1f} '
           f'L {x+7*s:.1f} {y+8*s:.1f} L {x-7*s:.1f} {y+8*s:.1f} Z')
        o.append(f'<path d="{h}" fill="{col}" stroke="{edge}" stroke-width="{2.2*s:.1f}" stroke-linejoin="round"/>')
        o.append(f'<path d="M {x:.1f} {y-3.2*s:.1f} L {x:.1f} {y-12.4*s:.1f}" stroke="{edge}" stroke-width="{2.2*s:.1f}"/>')
        o.append(f'<path d="M {x:.1f} {y-11.8*s:.1f} L {x+7.4*s:.1f} {y-7.6*s:.1f} L {x:.1f} {y-6*s:.1f} Z" fill="{edge}"/>')
    if state=='dislodged':
        o.append(f'<path d="M {x-13*s:.1f} {y+12*s:.1f} L {x+13*s:.1f} {y-12*s:.1f}" stroke="{FAILINK}" '
                 f'stroke-width="{3.6*s:.1f}" stroke-linecap="round"/>')
    o.append('</g>')
    return '\n'.join(o)

# ---------------------------------------------------------------- order glyphs
def _trim(p,q,r0,r1):
    (x0,y0),(x1,y1)=p,q
    dx,dy=x1-x0,y1-y0; L=math.hypot(dx,dy) or 1
    return (x0+dx/L*r0, y0+dy/L*r0), (x1-dx/L*r1, y1-dy/L*r1)
def _head(p,q,col,hollow=False,s=1.0):
    (x0,y0),(x1,y1)=p,q
    ang=math.atan2(y1-y0,x1-x0); L=13*s; w=0.42
    a1=(x1-L*math.cos(ang-w), y1-L*math.sin(ang-w))
    a2=(x1-L*math.cos(ang+w), y1-L*math.sin(ang+w))
    d=f'M {x1:.1f} {y1:.1f} L {a1[0]:.1f} {a1[1]:.1f} L {a2[0]:.1f} {a2[1]:.1f} Z'
    if hollow:
        return f'<path d="{d}" fill="{HALO}" stroke="{col}" stroke-width="{2.6*s:.1f}" stroke-linejoin="round"/>'
    return (f'<path d="{d}" fill="{col}" stroke="{HALO}" stroke-width="{1.4*s:.1f}" stroke-linejoin="round"/>')

def arrow(frm,to,power,kind='move',halo=None,s=1.0,bend=0.0):
    col=INK[power]; p,q=_trim(a(frm),a(to),15*s,21*s)
    if bend:
        mx,my=(p[0]+q[0])/2,(p[1]+q[1])/2
        dx,dy=q[0]-p[0],q[1]-p[1]; L=math.hypot(dx,dy) or 1
        mx-=dy/L*bend; my+=dx/L*bend
        d=f'M {p[0]:.1f} {p[1]:.1f} Q {mx:.1f} {my:.1f} {q[0]:.1f} {q[1]:.1f}'
    else:
        d=f'M {p[0]:.1f} {p[1]:.1f} L {q[0]:.1f} {q[1]:.1f}'
    w={'move':3.6,'support':2.8,'convoy':2.8}[kind]*s
    dash=' stroke-dasharray="9 6"' if kind=='convoy' else ''
    return '\n'.join([
      f'<path d="{d}" fill="none" stroke="{HALO}" stroke-width="{w+4.4:.1f}" stroke-opacity="0.9" stroke-linecap="round"/>',
      f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w:.1f}" stroke-linecap="round"{dash}/>',
      _head(p,q,col,hollow=(kind=='support'),s=s)])

def hold_ring(prov,power,s=1.0):
    x,y=a(prov); r=16.5*s; col=INK[power]
    pts=' '.join(f'{x+r*math.cos(math.radians(k*45-22.5)):.1f},{y+r*math.sin(math.radians(k*45-22.5)):.1f}' for k in range(8))
    return (f'<polygon points="{pts}" fill="none" stroke="{HALO}" stroke-width="{5*s:.1f}" stroke-opacity="0.9"/>'
            f'<polygon points="{pts}" fill="none" stroke="{col}" stroke-width="{2.6*s:.1f}"/>')

def bounce(prov,s=1.0):
    x,y=a(prov); r=11*s
    return (f'<g><circle cx="{x}" cy="{y}" r="{r+4:.1f}" fill="{HALO}" fill-opacity="0.9"/>'
            f'<path d="M {x-r:.1f} {y-r:.1f} L {x+r:.1f} {y+r:.1f} M {x+r:.1f} {y-r:.1f} L {x-r:.1f} {y+r:.1f}" '
            f'stroke="{FAILINK}" stroke-width="{4*s:.1f}" stroke-linecap="round"/></g>')

def cut(frm,to,s=1.0):
    p,q=_trim(a(frm),a(to),15*s,21*s)
    mx,my=(p[0]+q[0])/2,(p[1]+q[1])/2
    dx,dy=q[0]-p[0],q[1]-p[1]; L=math.hypot(dx,dy) or 1
    nx,ny=-dy/L*9*s,dx/L*9*s
    return (f'<path d="M {mx-nx:.1f} {my-ny:.1f} L {mx+nx:.1f} {my+ny:.1f}" stroke="{HALO}" stroke-width="{6.4*s:.1f}"/>'
            f'<path d="M {mx-nx:.1f} {my-ny:.1f} L {mx+nx:.1f} {my+ny:.1f}" stroke="{FAILINK}" stroke-width="{3.2*s:.1f}" stroke-linecap="round"/>')

DEFS=f'''<defs>
<pattern id="shut" width="7" height="7" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
<rect width="7" height="7" fill="{SHUT}"/><path d="M0 0 V7" stroke="{COASTINK}" stroke-width="1.6" stroke-opacity="0.45"/></pattern>
<filter id="soft" x="-30%" y="-30%" width="160%" height="160%">
<feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#0B1015" flood-opacity="0.3"/></filter>
</defs>'''

def dc(body, props=None, logic=None, css=''):
    p=f" data-props='{props}'" if props else ''
    script=''
    if props or logic:
        script=f'\n<script data-dc-script{p}>\nclass Component extends DCLogic {{{logic or ""}}}\n</script>'
    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  {FONTS}
  <style>
  *{{box-sizing:border-box}}
  body{{margin:0}}
  a{{color:{BRASS}}} a:hover{{color:{BRASS_HI}}}
  {css}
  </style>
</helmet>
{body}
</x-dc>{script}
</body>
</html>
'''
