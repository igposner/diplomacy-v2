import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from lib import _star
import math

# ---- local-coordinate glyph helpers (abstract diagrams, no real geometry) ----
def lp(x,y): return (x,y)
def ltrim(p,q,r0,r1):
    dx,dy=q[0]-p[0],q[1]-p[1]; L=math.hypot(dx,dy) or 1
    return (p[0]+dx/L*r0,p[1]+dy/L*r0),(q[0]-dx/L*r1,q[1]-dy/L*r1)
def lhead(p,q,col,hollow,s=1.0):
    ang=math.atan2(q[1]-p[1],q[0]-p[0]); L=11*s; w=0.44
    a1=(q[0]-L*math.cos(ang-w),q[1]-L*math.sin(ang-w))
    a2=(q[0]-L*math.cos(ang+w),q[1]-L*math.sin(ang+w))
    d=f'M {q[0]:.1f} {q[1]:.1f} L {a1[0]:.1f} {a1[1]:.1f} L {a2[0]:.1f} {a2[1]:.1f} Z'
    return (f'<path d="{d}" fill="{HALO}" stroke="{col}" stroke-width="2.3" stroke-linejoin="round"/>'
            if hollow else f'<path d="{d}" fill="{col}" stroke="{HALO}" stroke-width="1.3" stroke-linejoin="round"/>')
def larrow(p,q,power,kind='move',r0=17,r1=21):
    col=INK[power]; p2,q2=ltrim(p,q,r0,r1)
    w={'move':3.1,'support':2.4,'convoy':2.4}[kind]
    dash=' stroke-dasharray="8 5.5"' if kind=='convoy' else ''
    d=f'M {p2[0]:.1f} {p2[1]:.1f} L {q2[0]:.1f} {q2[1]:.1f}'
    return (f'<path d="{d}" stroke="{HALO}" stroke-width="{w+4.4}" stroke-opacity=".9" stroke-linecap="round" fill="none"/>'
            f'<path d="{d}" stroke="{col}" stroke-width="{w}" stroke-linecap="round" fill="none"{dash}/>'
            + lhead(p2,q2,col,kind=='support'))
def lring(xy,power,r=16):
    x,y=xy; col=INK[power]
    pts=' '.join(f'{x+r*math.cos(math.radians(k*45-22.5)):.1f},{y+r*math.sin(math.radians(k*45-22.5)):.1f}' for k in range(8))
    return (f'<polygon points="{pts}" fill="none" stroke="{HALO}" stroke-width="4.8" stroke-opacity=".9"/>'
            f'<polygon points="{pts}" fill="none" stroke="{col}" stroke-width="2.2"/>')
def ltoken(power,kind,xy,state='',s=1.0):
    x,y=xy; col=TOK[power]; edge='#FFFFFF'
    o=[]
    if state=='sel':
        o.append(f'<circle cx="{x}" cy="{y}" r="{18*s:.1f}" fill="{BRASS}" fill-opacity=".2"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="{15.5*s:.1f}" fill="none" stroke="{BRASS_HI}" stroke-width="2.5"/>')
    if state=='unordered':
        o.append(f'<circle cx="{x}" cy="{y}" r="{16*s:.1f}" fill="none" stroke="{BRASS}" stroke-width="1.8" stroke-dasharray="3 3.4"/>')
    o.append(f'<ellipse cx="{x}" cy="{y+9*s:.1f}" rx="{9.5*s:.1f}" ry="{2.8*s:.1f}" fill="#2A2418" fill-opacity=".18"/>')
    if kind=='A':
        o.append(f'<circle cx="{x}" cy="{y}" r="{10.4*s:.1f}" fill="{col}" stroke="{edge}" stroke-width="2"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="{4.3*s:.1f}" fill="{edge}" fill-opacity=".5"/>')
    else:
        o.append(f'<path d="M {x-11.2*s:.1f} {y-2.5*s:.1f} L {x+11.2*s:.1f} {y-2.5*s:.1f} L {x+6.9*s:.1f} {y+7.8*s:.1f} L {x-6.9*s:.1f} {y+7.8*s:.1f} Z" fill="{col}" stroke="{edge}" stroke-width="2" stroke-linejoin="round"/>')
        o.append(f'<path d="M {x:.1f} {y-3:.1f} V {y-12.2*s:.1f}" stroke="{edge}" stroke-width="2"/>')
        o.append(f'<path d="M {x:.1f} {y-11.6*s:.1f} L {x+7.2*s:.1f} {y-7.4*s:.1f} L {x:.1f} {y-5.8*s:.1f} Z" fill="{edge}"/>')
    if state=='dislodged':
        o.append(f'<path d="M {x-12.6:.1f} {y+11.6:.1f} L {x+12.6:.1f} {y-11.6:.1f}" stroke="{FAILINK}" stroke-width="3.3" stroke-linecap="round"/>')
    return '\n'.join(o)
def lprov(xy,w,h,label,fill=NEUTRAL,glow=False):
    x,y=xy
    g=(f'<rect x="{x-w/2:.0f}" y="{y-h/2:.0f}" width="{w}" height="{h}" rx="10" fill="{BRASS}" fill-opacity=".22" '
       f'stroke="{BRASS_HI}" stroke-width="2.3" stroke-dasharray="7 5"/>') if glow else ''
    return (f'<rect x="{x-w/2:.0f}" y="{y-h/2:.0f}" width="{w}" height="{h}" rx="10" fill="{fill}" '
            f'stroke="{COASTINK}" stroke-width="2.2" stroke-opacity=".75"/>{g}'
            f'<text x="{x-w/2+9:.0f}" y="{y+h/2-8:.0f}" font-family="{FU_SVG}" font-size="11" font-weight="500" '
            f'letter-spacing="0.9" fill="{MAPINK}" fill-opacity=".75">{label}</text>')
def lbounce(xy,r=10):
    x,y=xy
    return (f'<circle cx="{x}" cy="{y}" r="{r+4}" fill="{HALO}" fill-opacity=".92"/>'
            f'<path d="M {x-r} {y-r} L {x+r} {y+r} M {x+r} {y-r} L {x-r} {y+r}" stroke="{FAILINK}" stroke-width="3.8" stroke-linecap="round"/>')
def lcut(p,q):
    p2,q2=ltrim(p,q,17,21); mx,my=(p2[0]+q2[0])/2,(p2[1]+q2[1])/2
    dx,dy=q2[0]-p2[0],q2[1]-p2[1]; L=math.hypot(dx,dy) or 1
    nx,ny=-dy/L*9,dx/L*9
    return (f'<path d="M {mx-nx:.1f} {my-ny:.1f} L {mx+nx:.1f} {my+ny:.1f}" stroke="{HALO}" stroke-width="6.4"/>'
            f'<path d="M {mx-nx:.1f} {my-ny:.1f} L {mx+nx:.1f} {my+ny:.1f}" stroke="{FAILINK}" stroke-width="3.1" stroke-linecap="round"/>')

F,G,E='FRANCE','GERMANY','ENGLAND'
def cell(title, eng, inner, note=''):
    en=(f'<div style="font:400 10.5px/1.4 {FM};color:{LO};letter-spacing:.2px;margin-top:3px">{eng}</div>' if eng else '')
    nt=(f'<div style="font:400 10.5px/1.45 {FU};color:{LO};margin-top:3px">{note}</div>' if note else '')
    return (f'<div style="display:flex;flex-direction:column;gap:0">'
      f'<div style="background:{SEA};border:1px solid {mix(SEA_LINE,"#000",.12)};border-radius:5px;overflow:hidden">'
      f'<svg viewBox="0 0 240 132" width="100%" style="display:block">{inner}</svg></div>'
      f'<div style="padding:7px 2px 0">'
      f'<div style="font:500 12px/1.3 {FU};color:{HI}">{title}</div>{en}{nt}</div></div>')

CELLS=[
 cell('Move','A BUR - MUN',
   lprov((58,66),88,66,'BUR')+lprov((182,66),88,66,'MUN')+
   larrow(lp(58,66),lp(182,66),F)+ltoken(F,'A',(58,66))),
 cell('Support a move','A PAR S A BUR - MUN',
   lprov((44,40),74,54,'PAR')+lprov((44,100),74,50,'BUR')+lprov((188,70),80,62,'MUN')+
   larrow(lp(44,100),lp(188,70),F)+larrow(lp(44,40),lp(188,70),F,'support')+
   ltoken(F,'A',(44,40))+ltoken(F,'A',(44,100)),
   'Hollow head, drawn to the destination'),
 cell('Support a hold','A PIC S F ENG',
   lprov((56,36),80,52,'PIC')+lprov((150,92),96,60,'ENG')+
   lring((150,92),F)+larrow(lp(56,36),lp(150,92),F,'support',r1=26)+
   ltoken(F,'A',(56,36))+ltoken(F,'F',(150,92))),
 cell('Hold','A MAR H',
   lprov((120,66),100,72,'MAR')+lring((120,66),F)+ltoken(F,'A',(120,66))),
 cell('Convoy','F ENG C A BEL - LON &#183; A BEL - LON VIA',
   lprov((198,32),72,46,'BEL')+lprov((40,104),72,46,'LON')+lprov((118,66),104,44,'ENG')+
   larrow(lp(198,32),lp(40,104),F,'convoy')+
   f'<circle cx="118" cy="66" r="15" fill="none" stroke="{C[F]}" stroke-width="2.2" stroke-dasharray="4 3.4"/>'+
   ltoken(F,'A',(198,32))+ltoken(F,'F',(118,66))),
 cell('Bounce','both moves fail',
   lprov((40,34),70,44,'PAR')+lprov((40,100),70,44,'MAR')+lprov((186,66),84,62,'BUR')+
   larrow(lp(40,34),lp(186,66),F)+larrow(lp(40,100),lp(186,66),G)+
   ltoken(F,'A',(40,34))+ltoken(G,'A',(40,100))+lbounce((186,66))),
 cell('Support cut','A RUH - MUN cuts the support',
   lprov((44,36),74,50,'PAR')+lprov((44,100),74,48,'BUR')+lprov((186,68),84,62,'MUN')+
   larrow(lp(44,100),lp(186,68),F)+larrow(lp(44,36),lp(186,68),F,'support')+
   lcut(lp(44,36),lp(186,68))+ltoken(F,'A',(44,36))+ltoken(F,'A',(44,100))),
 cell('Dislodged','A BUR R PAR &#183; or A BUR D',
   lprov((58,66),88,66,'BUR')+lprov((182,66),88,66,'MUN')+
   larrow(lp(182,66),lp(58,66),G)+ltoken(G,'A',(182,66))+ltoken(F,'A',(58,66),'dislodged')),
]

def pow_col(pw):
    return (f'<div style="display:flex;flex-direction:column;gap:7px">'
      f'<div style="height:30px;border-radius:4px;background:{tint(pw)};border:1px solid {COASTINK};'
      f'display:grid;place-items:center">'
      f'<span style="font:500 9.5px/1 {FU};letter-spacing:1.1px;color:{COASTINK}">{ABBR[pw]}</span></div>'
      f'<div style="background:{tint(pw)};border:1px solid {COASTINK};border-radius:4px;padding:6px 0">'
      f'<svg viewBox="0 0 120 46" width="100%" style="display:block">'
      f'{ltoken(pw,"A",(28,24),s=1.05)}{ltoken(pw,"F",(66,24),s=1.05)}'
      f'<circle cx="100" cy="24" r="10.6" fill="none" stroke="{COASTINK}" stroke-width="1.5" stroke-opacity=".55"/>'
      f'{_star(100,24,7.4,"#FFFFFF",COASTINK,1.5)}</svg></div>'
      f'<div style="font:500 11.5px/1.2 {FD};color:{HI};text-align:center">{pw.title()}</div>'
      f'<div style="font:400 9.5px/1 {FM};color:{LO};text-align:center">{FILL[pw]}</div></div>')

def spec(label, inner, w=112):
    return (f'<div style="display:flex;flex-direction:column;gap:6px;align-items:center">'
      f'<div style="width:{w}px;background:{tint("FRANCE")};border:1px solid {COASTINK};border-radius:4px">'
      f'<svg viewBox="0 0 {w} 56" width="100%" style="display:block">{inner}</svg></div>'
      f'<div style="font:400 10px/1.3 {FU};color:{MID};text-align:center;max-width:{w+16}px">{label}</div></div>')

SC_SPECS=''.join([
 spec('Centre', _star(56,28,7.4,'#FFFFFF',COASTINK,1.5)),
 spec('Home centre', f'<circle cx="56" cy="28" r="11" fill="none" stroke="{COASTINK}" stroke-width="1.5" stroke-opacity=".55"/>'+_star(56,28,7.4,'#FFFFFF',COASTINK,1.5)),
 spec('Owner is the fill', f'<rect x="8" y="6" width="44" height="44" fill="{FILL["FRANCE"]}"/><rect x="52" y="6" width="52" height="44" fill="{FILL["GERMANY"]}"/>'+_star(30,28,7.4,'#FFFFFF',COASTINK,1.5)+_star(78,28,7.4,'#FFFFFF',COASTINK,1.5)),
 spec('At rest', ltoken(F,'A',(56,28))),
 spec('Selected', ltoken(F,'A',(56,28),'sel')),
 spec('Not yet ordered', ltoken(F,'A',(56,28),'unordered')),
 spec('Legal target', f'<rect x="16" y="10" width="80" height="36" rx="8" fill="{BRASS}" fill-opacity=".34" stroke="{BRASS_HI}" stroke-width="2.6" stroke-dasharray="8 5"/>'),
 spec('Impassable', f'<rect x="16" y="10" width="80" height="36" rx="8" fill="url(#shut)" stroke="{COASTINK}" stroke-width="1.6" stroke-opacity=".7"/>'),
])

body=f'''<div style="width:1080px;background:{CH0};padding:26px 24px 30px;font-family:{FU};color:{HI}">
  {DEFS}
  <div style="display:flex;align-items:flex-end;gap:14px;padding-bottom:16px;border-bottom:1px solid {CH3}">
    <div>
      <div style="font:500 26px/1.1 {FD};color:{HI}">Map language</div>
      <div style="font:400 12.5px/1.5 {FU};color:{MID};margin-top:5px;max-width:60ch">
        Every mark the board can draw. Powers keep their traditional colours; order glyphs are told apart by
        line weight and arrowhead, and failures are drawn in ink so they never collide with Austria&#39;s red.</div>
    </div>
  </div>

  <div style="font:500 9.5px/1 {FU};letter-spacing:1.4px;text-transform:uppercase;color:{LO};margin:22px 0 11px">
    Seven powers &#183; province tint, army, fleet, centre</div>
  <div style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px">
    {''.join(pow_col(p) for p in POW)}
  </div>
  <div style="font:400 11px/1.5 {FU};color:{LO};margin-top:9px;max-width:86ch">
    Russia departs from the traditional white, which disappears on a paper map. England stays navy and France
    stays sky so the two read apart at token size.</div>

  <div style="font:500 9.5px/1 {FU};letter-spacing:1.4px;text-transform:uppercase;color:{LO};margin:26px 0 11px">
    Order glyphs</div>
  <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px 14px">
    {''.join(CELLS)}
  </div>

  <div style="font:500 9.5px/1 {FU};letter-spacing:1.4px;text-transform:uppercase;color:{LO};margin:28px 0 11px">
    Centres, units, affordances</div>
  <div style="display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:12px">
    {SC_SPECS}
  </div>
</div>'''

open('MapLanguage.dc.html','w').write(dc(body, props='{"$preview":{"width":1080,"height":1000}}'))
print('MapLanguage.dc.html', len(open('MapLanguage.dc.html').read())//1024,'KB')
