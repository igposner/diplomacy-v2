import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *

# ---------- Fall 1902 position ----------
OWN={}
for pw,scs in {
 'FRANCE':['PAR','BRE','MAR','SPA','POR','BEL'],
 'ENGLAND':['LON','EDI','LVP','NWY'],
 'GERMANY':['BER','KIE','MUN','HOL','DEN','SWE'],
 'ITALY':['ROM','NAP','VEN','TRI'],
 'AUSTRIA':['VIE','BUD','SER'],
 'RUSSIA':['MOS','WAR','SEV','STP','RUM','BUL'],
 'TURKEY':['ANK','CON','SMY']}.items():
    for s in scs: OWN[s]=pw
UNITS=[('FRANCE','A','PAR'),('FRANCE','A','BUR'),('FRANCE','A','PIC'),('FRANCE','A','BEL'),
       ('FRANCE','F','ENG'),('FRANCE','F','MAO'),
       ('ENGLAND','F','NTH'),('ENGLAND','F','NWG'),('ENGLAND','A','YOR'),('ENGLAND','F','LON'),
       ('GERMANY','A','MUN'),('GERMANY','A','RUH'),('GERMANY','A','KIE'),('GERMANY','F','DEN'),
       ('GERMANY','F','BAL'),('GERMANY','A','SIL'),
       ('ITALY','A','VEN'),('ITALY','F','TYS'),('ITALY','A','TRI'),('ITALY','F','ION'),
       ('AUSTRIA','A','VIE'),('AUSTRIA','A','BUD'),('AUSTRIA','A','SER'),
       ('RUSSIA','A','WAR'),('RUSSIA','A','MOS'),('RUSSIA','F','SEV'),('RUSSIA','F','BOT'),
       ('RUSSIA','A','UKR'),('RUSSIA','A','RUM'),
       ('TURKEY','F','ANK'),('TURKEY','A','CON'),('TURKEY','A','SMY')]
SCOUNT={p:sum(1 for v in OWN.values() if v==p) for p in POW}

OWN_VIEW=dict(OWN)
for _pw,_k,_pr in UNITS:
    OWN_VIEW.setdefault(_pr.split('/')[0], _pw)
KEYS=list(PV)
VB="45 35 1545 1292"

def board():
    o=[DEFS, shapes(KEYS, OWN_VIEW), coastline(KEYS), sc_marks(KEYS, OWN_VIEW)]
    # order layer (France only, pre-adjudication)
    o.append('<g id="orders">')
    o.append(arrow('BUR','MUN','FRANCE','move'))
    o.append(arrow('PAR','MUN','FRANCE','support'))
    o.append(arrow('BEL','LON','FRANCE','convoy',bend=26))
    o.append(hold_ring('ENG','FRANCE'))
    o.append(arrow('PIC','ENG','FRANCE','support'))
    o.append(arrow('MAO','SPA/SC','FRANCE','move',bend=-18))
    o.append('</g>')
    o.append('<g filter="url(#soft)">')
    for pw,k,pr in UNITS:
        st='' if pw!='FRANCE' else ''
        o.append(token(pw,k,a(pr),st))
    o.append('</g>')
    o.append(labels(KEYS))
    return '\n'.join(o)

def chip(pw):
    return (f'<div style="background:{CH2};border:1px solid {CH3};border-radius:4px;padding:5px 0 6px;text-align:center">'
      f'<div style="height:3px;background:{C[pw]};border-radius:2px;margin:-5px 6px 5px"></div>'
      f'<div style="font:500 9.5px/1 {FU};letter-spacing:0.9px;color:{MID}">{ABBR[pw]}</div>'
      f'<div style="font:500 15px/1.2 {FM};color:{HI};margin-top:2px">{SCOUNT[pw]}</div></div>')

ORDERS=[('A','Burgundy','→ Munich','A BUR - MUN',False),
        ('A','Paris','supports Burgundy → Munich','A PAR S A BUR - MUN',True),
        ('A','Belgium','→ London, by convoy','A BEL - LON VIA',False),
        ('F','Channel','convoys Belgium → London','F ENG C A BEL - LON',False),
        ('F','Picardy','supports the Channel fleet','A PIC S F ENG',False),
        ('F','Mid-Atlantic','→ Spain (south coast)','F MAO - SPA/SC',False)]

def glyph(kind,col,s=9):
    if kind=='A':
        return f'<svg width="20" height="20" viewBox="0 0 20 20"><circle cx="10" cy="10" r="{s-1}" fill="{col}" stroke="#FBF8F1" stroke-width="1.6"/></svg>'
    return (f'<svg width="20" height="20" viewBox="0 0 20 20"><path d="M2.2 8.6 H17.8 L15 15 H5 Z" fill="{col}" '
            f'stroke="#FBF8F1" stroke-width="1.6" stroke-linejoin="round"/><path d="M10 8.2 V2.6" stroke="#FBF8F1" stroke-width="1.6"/>'
            f'<path d="M10 3.2 L15 6 L10 7.2 Z" fill="#FBF8F1"/></svg>')

def order_row(kind,who,what,eng,sel):
    bl=f'border-left:2.5px solid {BRASS};' if sel else 'border-left:2.5px solid transparent;'
    bg=CH2 if sel else 'transparent'
    return (f'<div class="orow" style="{bl}background:{bg}">'
      f'<div style="flex:none;display:flex;align-items:center">{glyph(kind,C["FRANCE"])}</div>'
      f'<div style="min-width:0;flex:1">'
      f'<div style="font:500 12.5px/1.3 {FU};color:{HI};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
      f'<span style="font-family:{FD};font-size:13.5px;font-weight:500">{who}</span> {what}</div>'
      f'<div style="font:400 10.5px/1.4 {FM};color:{LO};letter-spacing:0.2px;margin-top:1px">{eng}</div></div>'
      f'<button class="x" aria-label="Clear order">'
      f'<svg width="11" height="11" viewBox="0 0 11 11"><path d="M1.5 1.5 L9.5 9.5 M9.5 1.5 L1.5 9.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
      f'</button></div>')

CHANNELS=[('Global',None,0),('England','ENGLAND',1),('Germany','GERMANY',2),('Italy','ITALY',0),
          ('Austria','AUSTRIA',0),('Russia','RUSSIA',1),('Turkey','TURKEY',0)]
def pchip(name,pw,unread,active=False):
    dot=(f'<span style="width:7px;height:7px;border-radius:50%;background:{C[pw]};flex:none"></span>'
         if pw else f'<svg width="9" height="9" viewBox="0 0 9 9" style="flex:none"><circle cx="4.5" cy="4.5" r="3.6" fill="none" stroke="{MID}" stroke-width="1.3"/><path d="M0.9 4.5 H8.1 M4.5 1 C6 2.6 6 6.4 4.5 8 C3 6.4 3 2.6 4.5 1" stroke="{MID}" stroke-width="0.9" fill="none"/></svg>')
    b=(f'background:{CH3};border-color:{BRASS};' if active else f'background:{CH2};border-color:{CH3};')
    badge=(f'<span style="margin-left:auto;min-width:15px;height:15px;border-radius:8px;background:{BRASS};'
           f'color:#22190A;font:600 9.5px/15px {FU};text-align:center;flex:none;padding:0 4px">{unread}</span>' if unread else '')
    return (f'<button class="pchip" style="{b}"><span style="display:flex;align-items:center;gap:6px;width:100%">{dot}'
      f'<span style="font:500 11px/1 {FU};color:{HI if active else MID};letter-spacing:0.2px">{name}</span>{badge}</span></button>')

MSGS=[('ENGLAND','Spring 1902','Your fleet in the Channel is a dagger pointed at London. Withdraw it and I leave Belgium alone all year.',False),
      ('FRANCE','Spring 1902','The Channel is a road, not a dagger. I have no designs on your island — but I will not give up the sea while Germany builds in Kiel.',True),
      ('ENGLAND','Fall 1902','Then we understand each other. I am moving north to Norway. Do not make me regret turning my back.',False)]
def msg(who,phase,text,mine):
    al='flex-end' if mine else 'flex-start'
    bg=mix(CH2,C['FRANCE'],0.16) if mine else CH2
    bd=mix(CH3,C['FRANCE'],0.22) if mine else CH3
    nm='You'if mine else who.title()
    col=C['FRANCE'] if mine else C['ENGLAND']
    return (f'<div style="display:flex;flex-direction:column;align-items:{al};gap:3px">'
      f'<div style="display:flex;gap:6px;align-items:baseline">'
      f'<span style="font:500 11.5px/1 {FD};color:{mix(col,HI,0.45)};letter-spacing:0.3px">{nm}</span>'
      f'<span style="font:400 9.5px/1 {FM};color:{LO}">{phase}</span></div>'
      f'<div style="max-width:330px;background:{bg};border:1px solid {bd};border-radius:7px;'
      f'padding:8px 11px;font:400 12.5px/1.55 {FU};color:{mix(HI,MID,0.25)}">{text}</div></div>')

CSS=f'''
.orow{{display:flex;gap:9px;align-items:center;padding:6px 9px 6px 7px;border-radius:0 4px 4px 0}}
.orow:hover{{background:{CH2}}}
.x{{flex:none;width:20px;height:20px;border:0;background:transparent;color:{LO};cursor:pointer;
   display:grid;place-items:center;border-radius:3px}}
.x:hover{{color:#D98A82;background:{CH3}}}
.pchip{{border:1px solid;border-radius:5px;padding:6px 8px;cursor:pointer;text-align:left}}
.pchip:hover{{border-color:{CH4}}}
.zb{{width:27px;height:27px;border:1px solid rgba(60,54,40,.28);background:rgba(253,250,243,.92);
     color:#4A4438;display:grid;place-items:center;cursor:pointer;font:500 14px/1 {FU}}}
.zb:hover{{background:#fff}}
.sec{{font:500 9.5px/1 {FU};letter-spacing:1.4px;text-transform:uppercase;color:{LO}}}
'''

body=f'''<div style="width:1440px;height:900px;background:{CH0};display:flex;flex-direction:column;
     font-family:{FU};color:{HI};overflow:hidden">

  <div style="height:54px;flex:none;background:{CH1};border-bottom:1px solid {CH3};
       display:flex;align-items:center;gap:0;padding:0 16px">
    <div style="display:flex;align-items:center;gap:10px">
      <svg width="24" height="24" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10.5" fill="none" stroke="{BRASS}" stroke-width="1.3"/><circle cx="12" cy="12" r="7" fill="none" stroke="{BRASS}" stroke-width="0.8" stroke-opacity="0.6"/><path d="M12 2.6 V21.4 M2.6 12 H21.4" stroke="{BRASS}" stroke-width="0.7" stroke-opacity="0.45"/></svg>
      <div>
        <div style="font:500 14px/1.15 {FD};color:{HI};letter-spacing:0.2px">Cordial Entente</div>
        <div style="font:400 9.5px/1.2 {FM};color:{LO}">game 7f3a2c · full press</div>
      </div>
    </div>
    <div style="width:1px;height:30px;background:{CH3};margin:0 18px"></div>
    <div style="display:flex;align-items:baseline;gap:9px">
      <span style="font:500 21px/1 {FD};color:{HI}">Fall 1902</span>
      <span style="font:500 10px/1 {FU};letter-spacing:1.5px;text-transform:uppercase;color:{BRASS}">Movement</span>
    </div>
    <div style="display:flex;align-items:center;gap:6px;margin-left:18px;background:{CH2};
         border:1px solid {CH3};border-radius:4px;padding:5px 9px">
      <span style="width:6px;height:6px;border-radius:50%;background:{BRASS}"></span>
      <span style="font:500 12px/1 {FM};color:{mix(HI,MID,0.3)};letter-spacing:0.4px">04:11:38</span>
      <span style="font:400 9.5px/1 {FU};color:{LO};letter-spacing:0.5px">left</span>
    </div>
    <div style="flex:1"></div>
    <div style="display:flex;align-items:center;gap:7px;margin-right:14px">
      <span style="width:11px;height:11px;border-radius:2px;background:{C['FRANCE']}"></span>
      <span style="font:500 12.5px/1 {FD};color:{HI};letter-spacing:0.3px">France</span>
      <span style="font:400 9.5px/1 {FU};color:{LO};letter-spacing:0.6px">YOU</span>
    </div>
    <button style="border:1px solid {mix(BRASS,'#000',0.25)};background:{BRASS};color:#211703;
         font:600 11.5px/1 {FU};letter-spacing:0.7px;text-transform:uppercase;padding:9px 15px;
         border-radius:4px;cursor:pointer">Ready</button>
  </div>

  <div style="flex:1;display:flex;min-height:0">

    <div style="flex:1;min-width:0;position:relative;background:{SEA}">
      <svg viewBox="{VB}" width="100%" height="100%" preserveAspectRatio="xMidYMid slice"
           style="display:block;position:absolute;inset:0">
        {board()}
      </svg>

      <div style="position:absolute;right:12px;bottom:58px;display:flex;flex-direction:column;
           border:1px solid rgba(60,54,40,.28);border-radius:4px;overflow:hidden">
        <button class="zb" style="border:0;border-bottom:1px solid rgba(60,54,40,.22)">+</button>
        <button class="zb" style="border:0;border-bottom:1px solid rgba(60,54,40,.22)">−</button>
        <button class="zb" style="border:0;font-size:12px">↺</button>
      </div>

      <div style="position:absolute;left:12px;top:12px;background:rgba(253,250,243,.9);
           border:1px solid rgba(60,54,40,.22);border-radius:4px;padding:7px 10px">
        <div style="font:500 9px/1 {FU};letter-spacing:1.3px;text-transform:uppercase;color:#7A7160;margin-bottom:5px">Your orders shown</div>
        <div style="display:flex;gap:11px;align-items:center">
          <span style="display:flex;gap:4px;align-items:center;font:400 10px/1 {FU};color:#4A4438">
            <svg width="22" height="8" viewBox="0 0 22 8"><path d="M0 4 H15" stroke="{INK['FRANCE']}" stroke-width="2.8"/><path d="M14 0.6 L20.5 4 L14 7.4 Z" fill="{INK['FRANCE']}"/></svg>move</span>
          <span style="display:flex;gap:4px;align-items:center;font:400 10px/1 {FU};color:#4A4438">
            <svg width="22" height="8" viewBox="0 0 22 8"><path d="M0 4 H14" stroke="{INK['FRANCE']}" stroke-width="2.2"/><path d="M13.6 1 L20 4 L13.6 7 Z" fill="#FFFFFF" stroke="{INK['FRANCE']}" stroke-width="1.7"/></svg>support</span>
          <span style="display:flex;gap:4px;align-items:center;font:400 10px/1 {FU};color:#4A4438">
            <svg width="22" height="8" viewBox="0 0 22 8"><path d="M0 4 H20" stroke="{INK['FRANCE']}" stroke-width="2.2" stroke-dasharray="5 3.5"/></svg>convoy</span>
        </div>
      </div>

      <div style="position:absolute;left:0;right:0;bottom:0;height:46px;background:{CH1};
           border-top:1px solid {CH3};display:flex;align-items:center;gap:12px;padding:0 12px">
        <button class="zb" style="width:22px;height:22px;border:1px solid {CH3};background:{CH2};color:{MID};font-size:11px">‹</button>
        <div style="flex:1;display:flex;align-items:flex-end;gap:14px;height:26px">
          {''.join(
            f'<div style="display:flex;flex-direction:column;gap:3px;align-items:flex-start">'
            f'<div style="display:flex;gap:2.5px">'+''.join(
               f'<span style="width:11px;height:{7 if t!="M" else 11}px;border-radius:1px;'
               f'background:{BRASS if (y==1902 and t=="M2") else CH4}"></span>' for t in yr)+'</div>'
            f'<span style="font:400 9px/1 {FM};color:{LO}">{y}</span></div>'
            for y,yr in [(1901,['M','R','M2','A']),(1902,['M','R','M2'])])}
          <span style="font:400 9.5px/1 {FU};color:{LO};padding-bottom:11px">now</span>
        </div>
        <span style="font:400 9.5px/1 {FU};letter-spacing:0.6px;color:{LO}">7 phases played</span>
      </div>
    </div>

    <div style="width:428px;flex:none;background:{CH1};border-left:1px solid {CH3};
         display:flex;flex-direction:column;min-height:0">

      <div style="flex:none;padding:9px 12px 10px;border-bottom:1px solid {CH3};
           display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px">
        {''.join(chip(p) for p in POW)}
      </div>

      <div style="flex:none;padding:11px 12px 0;display:flex;align-items:baseline;gap:8px">
        <span class="sec">Orders</span>
        <span style="font:400 10.5px/1 {FM};color:{OK}">6 of 6 units ordered</span>
        <span style="flex:1"></span>
        <button style="border:0;background:transparent;color:{LO};font:400 10.5px/1 {FU};
             cursor:pointer;text-decoration:underline;text-underline-offset:2px">clear all</button>
      </div>
      <div style="flex:none;padding:7px 8px 0;display:flex;flex-direction:column;gap:1px">
        {''.join(order_row(*o) for o in ORDERS)}
      </div>
      <div style="flex:none;padding:10px 12px 12px">
        <button style="width:100%;border:1px solid {CH4};background:{CH2};color:{HI};
             font:600 11.5px/1 {FU};letter-spacing:0.8px;text-transform:uppercase;padding:11px;
             border-radius:4px;cursor:pointer">Submit orders</button>
      </div>

      <div style="flex:none;height:1px;background:{CH3}"></div>

      <div style="flex:none;padding:11px 12px 0;display:flex;align-items:baseline;gap:8px">
        <span class="sec">Press</span>
        <span style="font:400 10.5px/1 {FU};color:{LO}">4 unread</span>
      </div>
      <div style="flex:none;padding:8px 12px 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px">
        {''.join(pchip(n,p,u,active=(n=='England')) for n,p,u in CHANNELS)}
      </div>

      <div style="flex:1;min-height:0;overflow-y:auto;padding:13px 12px;display:flex;
           flex-direction:column;gap:13px">
        {''.join(msg(*m) for m in MSGS)}
        <div style="display:flex;gap:6px;align-items:center;font:400 10.5px/1 {FU};color:{LO};font-style:italic">
          <span style="display:flex;gap:2.5px">
            <span style="width:4px;height:4px;border-radius:50%;background:{LO}"></span>
            <span style="width:4px;height:4px;border-radius:50%;background:{LO};opacity:.6"></span>
            <span style="width:4px;height:4px;border-radius:50%;background:{LO};opacity:.3"></span>
          </span>Germany is drafting a reply
        </div>
      </div>

      <div style="flex:none;border-top:1px solid {CH3};padding:10px 12px 12px">
        <div style="background:{CH2};border:1px solid {CH3};border-radius:5px;padding:9px 10px;
             font:400 12.5px/1.5 {FU};color:{LO};min-height:52px">Reply to England…</div>
        <div style="display:flex;align-items:center;gap:10px;margin-top:8px">
          <span style="font:400 9.5px/1 {FU};color:{LO}">Sent when you press Ready</span>
          <span style="flex:1"></span>
          <button style="border:1px solid {mix(BRASS,'#000',0.3)};background:{BRASS};color:#211703;
               font:600 10.5px/1 {FU};letter-spacing:0.7px;text-transform:uppercase;
               padding:8px 14px;border-radius:4px;cursor:pointer">Send</button>
        </div>
      </div>
    </div>
  </div>
</div>'''

props='{"$preview":{"width":1440,"height":900}}'
open('Main.dc.html','w').write(dc(body, props=props, css=CSS))
print('Main.dc.html', len(open('Main.dc.html').read())//1024, 'KB')
