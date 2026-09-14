import os
import sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *

OWN={}
for pw,scs in {'FRANCE':['PAR','BRE','MAR','SPA','POR','BEL'],'ENGLAND':['LON','EDI','LVP','NWY'],
 'GERMANY':['BER','KIE','MUN','HOL','DEN','SWE'],'ITALY':['ROM','NAP','VEN','TRI'],
 'AUSTRIA':['VIE','BUD','SER'],'RUSSIA':['MOS','WAR','SEV','STP','RUM','BUL'],
 'TURKEY':['ANK','CON','SMY']}.items():
    for s in scs: OWN[s]=pw

OWN_VIEW=dict(OWN)
for _pw,_k,_pr in [('FRANCE','A','PAR'),('FRANCE','A','BUR'),('FRANCE','A','PIC'),
    ('FRANCE','A','BEL'),('FRANCE','F','ENG'),('FRANCE','F','MAO'),
    ('GERMANY','A','MUN'),('GERMANY','A','RUH')]:
    OWN_VIEW.setdefault(_pr.split('/')[0], _pw)
PW,PH=452,330
VA=(400,735,520,380)   # France / Low Countries
VB=(100,895,520,380)   # Iberia + Mid-Atlantic
KA=crop_keys((VA[0],VA[1],VA[0]+VA[2],VA[1]+VA[3]))
KB=crop_keys((VB[0],VB[1],VB[0]+VB[2],VB[1]+VB[3]))

def px(xy,vb):
    return ((xy[0]-vb[0])/vb[2]*PW, (xy[1]-vb[1])/vb[3]*PH)

def panel(idx,name,trigger,vb,keys,overlays,units,caption,pops='',glow=(),dim=()):
    vbs=f'{vb[0]} {vb[1]} {vb[2]} {vb[3]}'
    inner=[DEFS, shapes(keys,OWN_VIEW,glow=glow,dim=dim), coastline(keys), sc_marks(keys,OWN_VIEW)]
    inner.append(overlays)
    inner.append('<g filter="url(#soft)">')
    for u in units: inner.append(u)
    inner.append('</g>')
    inner.append(labels(keys,size=13))
    return (f'<div style="display:flex;flex-direction:column;width:{PW}px;flex:none">'
      f'<div style="display:flex;align-items:baseline;gap:8px;padding-bottom:9px">'
      f'<span style="font:500 10px/1 {FM};color:{BRASS};letter-spacing:.8px">{idx}</span>'
      f'<span style="font:500 13px/1 {FM};color:{HI};letter-spacing:.4px">{name}</span></div>'
      f'<div style="font:400 11px/1.45 {FU};color:{MID};padding-bottom:9px;min-height:32px">{trigger}</div>'
      f'<div style="position:relative;width:{PW}px;height:{PH}px;background:{SEA};border:1px solid {CH3};'
      f'border-radius:5px;overflow:hidden">'
      f'<svg viewBox="{vbs}" width="{PW}" height="{PH}" preserveAspectRatio="xMidYMid slice" '
      f'style="display:block;position:absolute;inset:0">{"".join(inner)}</svg>{pops}</div>'
      f'<div style="font:400 11px/1.5 {FU};color:{LO};padding-top:9px;min-height:46px">{caption}</div></div>')

def pop(xy,vb,html,dx=14,dy=-8,w=None):
    x,y=px(xy,vb)
    wd=f'width:{w}px;' if w else ''
    return (f'<div style="position:absolute;left:{x+dx:.0f}px;top:{y+dy:.0f}px;{wd}background:rgba(20,26,34,.96);'
      f'border:1px solid {CH4};border-radius:5px;padding:7px;box-shadow:0 6px 18px rgba(0,0,0,.4)">{html}</div>')

def mbtn(k,label,on=False,dis=False):
    bg=BRASS if on else CH2; fg='#211703' if on else (LO if dis else HI)
    bd=mix(BRASS,'#000',.3) if on else CH3
    return (f'<div style="display:flex;align-items:center;gap:6px;background:{bg};border:1px solid {bd};'
      f'border-radius:3px;padding:5px 8px;opacity:{0.5 if dis else 1}">'
      f'<span style="font:500 9px/1 {FM};color:{fg};opacity:.75">{k}</span>'
      f'<span style="font:500 10.5px/1 {FU};color:{fg};letter-spacing:.3px">{label}</span></div>')

def pill(xy,vb,text,on=False):
    x,y=px(xy,vb)
    bg=BRASS if on else 'rgba(253,250,243,.95)'; fg='#211703' if on else '#3E3829'
    return (f'<div style="position:absolute;left:{x:.0f}px;top:{y:.0f}px;transform:translate(-50%,-50%);'
      f'background:{bg};border:1.5px solid {mix(BRASS,"#000",.25)};border-radius:11px;padding:4px 9px;'
      f'font:600 10px/1 {FU};letter-spacing:.4px;color:{fg};white-space:nowrap">{text}</div>')

FR,GE='FRANCE','GERMANY'
FU4=[('FRANCE','A','PAR'),('FRANCE','A','BUR'),('FRANCE','A','PIC'),('FRANCE','A','BEL')]
GU=[('GERMANY','A','MUN'),('GERMANY','A','RUH')]
def toks(spec):  # list of (power,kind,prov,state)
    return [token(p,k,a(pr),st,scale=1.25) for p,k,pr,st in spec]

P1=panel('01','IDLE',
  'Nothing selected. A fresh movement phase.',VA,KA,'',
  toks([(p,k,pr,'unordered') for p,k,pr in FU4]+[(p,k,pr,'') for p,k,pr in GU]),
  'Your own units carry a dashed brass ring until they have an order, so what still needs you is visible without reading the list.')

P2=panel('02','UNIT_SELECTED',
  'You clicked <b style="color:'+HI+'">Army Paris</b>. Its legal destinations light up.',VA,KA,'',
  toks([('FRANCE','A','PAR','sel'),('FRANCE','A','BUR','unordered'),('FRANCE','A','PIC','unordered'),
        ('FRANCE','A','BEL','unordered'),('GERMANY','A','MUN',''),('GERMANY','A','RUH','')]),
  'Only the four provinces the engine actually permits are clickable. An illegal order cannot be built, because nothing illegal is ever offered.',
  glow=('BUR','GAS','PIC','BRE'),
  pops=pop(a('PAR'),VA,
    f'<div style="display:flex;flex-direction:column;gap:3px">'
    f'{mbtn("H","Hold")}{mbtn("M","Move",on=True)}{mbtn("S","Support")}{mbtn("C","Convoy",dis=True)}</div>'
    f'<div style="font:400 9px/1.3 {FU};color:{LO};padding:6px 2px 1px;max-width:96px">Convoy needs an adjacent fleet</div>',
    dx=18,dy=-46,w=116))

P3=panel('03','SUPPORT_TARGET',
  'Paris is selected, you pressed <b style="color:'+HI+'">S</b>, then clicked <b style="color:'+HI+'">Army Burgundy</b>.',VA,KA,
  arrow('PAR','MUN',FR,'support')+hold_ring('BUR',FR),
  toks([('FRANCE','A','PAR','sel'),('FRANCE','A','BUR',''),('FRANCE','A','PIC','unordered'),
        ('FRANCE','A','BEL','unordered'),('GERMANY','A','MUN',''),('GERMANY','A','RUH','')]),
  'Burgundy&#39;s own legal moves light up, and its province stays clickable for a support&#8209;hold. Hovering Munich previews the hollow&#8209;headed arrow.',
  glow=('MUN','RUH','MAR','GAS'))

P4=panel('04','COAST_PICK',VA and
  'You moved <b style="color:'+HI+'">Fleet Mid&#8209;Atlantic</b> to Spain, which has two coasts.',VB,KB,
  arrow('MAO','SPA/SC',FR,'move',bend=-14),
  [token('FRANCE','F',a('MAO'),'sel',scale=1.25)],
  'A fleet must name a coast; the order is <span style="font-family:'+FM+'">F MAO - SPA/SC</span>, never bare Spain. An army moving to Spain never sees this step.',
  glow=('SPA',),
  pops=pill(a('SPA/NC'),VB,'north coast')+pill(a('SPA/SC'),VB,'south coast',on=True))

P5=panel('05','RETREAT',
  'Burgundy was dislodged by Munich. Only dislodged units are selectable.',VA,KA,
  arrow('MUN','BUR',GE,'move'),
  toks([('FRANCE','A','BUR','dislodged'),('FRANCE','A','PAR',''),('FRANCE','A','PIC',''),
        ('FRANCE','A','BEL',''),('GERMANY','A','MUN',''),('GERMANY','A','RUH','')]),
  'Munich is excluded: a unit may not retreat into the province that dislodged it. Occupied and bounced provinces are excluded too. With no option left, the only order is disband.',
  glow=('GAS','MAR'),
  pops=pop(a('BUR'),VA,
    f'<div style="font:500 9px/1 {FU};letter-spacing:1px;color:{LO};padding:1px 2px 6px">RETREAT TO</div>'
    f'<div style="display:flex;gap:4px;flex-wrap:wrap;max-width:150px">'
    f'{mbtn("","Gascony")}{mbtn("","Marseilles")}</div>'
    f'<div style="height:1px;background:{CH3};margin:7px 0"></div>'
    f'<div style="display:flex;align-items:center;gap:6px;background:transparent;border:1px solid #6E3B35;'
    f'border-radius:3px;padding:5px 8px"><span style="font:500 10.5px/1 {FU};color:#D98A82">Disband</span></div>',
    dx=16,dy=-30,w=166))

P6=panel('06','BUILD',
  'Winter 1902. France took Munich, so one build is owed.',VA,KA,'',
  toks([('FRANCE','A','PAR',''),('FRANCE','A','BUR',''),('FRANCE','A','PIC',''),('FRANCE','A','BEL','')]),
  'Only unoccupied home centres you still own can build. Brest is coastal so it offers both; Paris, inland, would offer army only. Unused builds are waived, not lost.',
  glow=('BRE','MAR'),
  pops=pop(a('BRE'),VA,
    f'<div style="font:500 9px/1 {FU};letter-spacing:1px;color:{LO};padding:1px 2px 6px">BUILD IN BREST</div>'
    f'<div style="display:flex;gap:4px">{mbtn("A","Army")}{mbtn("F","Fleet",on=True)}</div>',
    dx=14,dy=-40,w=142)
  + f'<div style="position:absolute;right:9px;bottom:9px;display:flex;gap:5px">'
    f'<div style="background:{CH2};border:1px solid {CH3};border-radius:3px;padding:5px 9px;'
    f'font:500 10px/1 {FU};color:{MID}">Waive the build</div></div>')

body=f'''<div style="width:1464px;background:{CH0};padding:28px;font-family:{FU};color:{HI}">
  <div style="padding-bottom:18px;border-bottom:1px solid {CH3}">
    <div style="font:500 26px/1.1 {FD};color:{HI}">Order entry, state by state</div>
    <div style="font:400 12.5px/1.55 {FU};color:{MID};margin-top:6px;max-width:96ch">
      Every clickable target comes from the engine&#39;s own list of legal orders, so an illegal order can never be
      constructed. Right&#8209;click clears a unit. Esc returns to idle. Tab cycles whatever is still unordered.
      These six states cover all of movement, retreat and adjustment.</div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,{PW}px);gap:30px 26px;padding-top:24px">
    {P1}{P2}{P3}{P4}{P5}{P6}
  </div>
</div>'''

open('OrderStates.dc.html','w').write(dc(body, props='{"$preview":{"width":1464,"height":1060}}'))
print('OrderStates.dc.html', len(open('OrderStates.dc.html').read())//1024,'KB')
print('crop A keys',len(KA),'crop B keys',len(KB))
