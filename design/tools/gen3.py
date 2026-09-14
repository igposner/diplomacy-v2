import os
import sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *

HOMES={'AUSTRIA':'VIE BUD TRI','ENGLAND':'LON EDI LVP','FRANCE':'PAR BRE MAR',
 'GERMANY':'BER KIE MUN','ITALY':'ROM VEN NAP','RUSSIA':'MOS WAR SEV STP','TURKEY':'ANK CON SMY'}
SEATS=[('FRANCE','You','you'),('ENGLAND','deepseek-flash','llm'),('GERMANY','deepseek-flash','llm'),
 ('ITALY','deepseek-flash','llm'),('AUSTRIA','deepseek-flash','llm'),('RUSSIA','deepseek-flash','llm'),
 ('TURKEY','HeuristicBot','bot')]

def chev():
    return (f'<svg width="9" height="9" viewBox="0 0 9 9" style="flex:none;opacity:.6">'
            f'<path d="M1.6 3 L4.5 6 L7.4 3" stroke="{MID}" stroke-width="1.4" fill="none" stroke-linecap="round"/></svg>')
def sel(text, wide=168, on=False):
    return (f'<div style="display:flex;align-items:center;gap:8px;width:{wide}px;background:{CH3 if on else CH2};'
      f'border:1px solid {BRASS if on else CH3};border-radius:4px;padding:7px 9px">'
      f'<span style="font:500 11.5px/1 {FM if not on else FU};color:{HI};flex:1;overflow:hidden;'
      f'text-overflow:ellipsis;white-space:nowrap">{text}</span>{chev()}</div>')
def switch(on=True, dim=False):
    if dim:
        return f'<span style="font:400 10px/1 {FU};color:{LO}">n/a</span>'
    bg=BRASS if on else CH3
    knob='right:2px' if on else 'left:2px'
    return (f'<span style="position:relative;display:inline-block;width:30px;height:17px;border-radius:9px;'
      f'background:{bg};vertical-align:middle">'
      f'<span style="position:absolute;{knob};top:2px;width:13px;height:13px;border-radius:50%;'
      f'background:#F6F1E6"></span></span>')

def seat(pw,ctrl,kind):
    return (f'<div style="display:flex;align-items:center;gap:13px;padding:11px 13px;border-bottom:1px solid {CH3}">'
      f'<span style="width:13px;height:13px;border-radius:3px;flex:none;background:{C[pw]}"></span>'
      f'<div style="width:148px;flex:none">'
      f'<div style="font:500 14px/1.2 {FD};color:{HI}">{pw.title()}</div>'
      f'<div style="font:400 9.5px/1.4 {FM};color:{LO};letter-spacing:.3px;margin-top:2px">{HOMES[pw]}</div></div>'
      f'{sel(ctrl, on=(kind=="you"))}'
      f'<div style="display:flex;align-items:center;gap:7px;width:132px">'
      f'<span style="font:400 10.5px/1 {FU};color:{LO}">persona</span>'
      f'{switch(on=(kind=="llm"), dim=(kind!="llm"))}</div>'
      f'<span style="flex:1"></span>'
      f'<span style="font:400 10px/1 {FU};color:{LO};letter-spacing:.5px">'
      f'{"HUMAN" if kind=="you" else ("AGENT" if kind=="llm" else "SCRIPTED")}</span></div>')

def card(title, inner):
    return (f'<div style="background:{CH1};border:1px solid {CH3};border-radius:6px;padding:13px 14px">'
      f'<div style="font:500 9.5px/1 {FU};letter-spacing:1.4px;text-transform:uppercase;color:{LO};'
      f'padding-bottom:11px">{title}</div>{inner}</div>')
def row(label, ctl):
    return (f'<div style="display:flex;align-items:center;gap:10px;padding:5px 0">'
      f'<span style="font:400 12px/1.3 {FU};color:{MID};flex:1">{label}</span>{ctl}</div>')
def radio(text,on):
    dot = ('<span style="width:6px;height:6px;border-radius:50%;background:' + BRASS + '"></span>') if on else ''
    return (f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0">'
      f'<span style="width:13px;height:13px;border-radius:50%;border:1.5px solid {BRASS if on else CH4};'
      f'display:grid;place-items:center;flex:none">{dot}</span>'
      f'<span style="font:400 12px/1.3 {FU};color:{HI if on else MID}">{text}</span></div>')

LBODY=f'''<div style="width:1180px;height:860px;background:{CH0};font-family:{FU};color:{HI};
     padding:26px 28px;display:flex;flex-direction:column;overflow:hidden">
  <div style="flex:none;display:flex;align-items:flex-end;gap:16px;padding-bottom:18px;border-bottom:1px solid {CH3}">
    <div style="flex:1">
      <div style="font:500 26px/1.1 {FD};color:{HI}">New game</div>
      <div style="font:400 12.5px/1.5 {FU};color:{MID};margin-top:5px">
        Pick a power, then decide who holds the other six. Any seat can be you, an agent, or a scripted bot.</div>
    </div>
    <div style="text-align:right">
      <div style="font:400 9.5px/1 {FU};letter-spacing:1.2px;text-transform:uppercase;color:{LO}">Map</div>
      <div style="font:500 13px/1.3 {FD};color:{HI};margin-top:4px">Standard, seven powers</div>
    </div>
  </div>

  <div style="flex:1;display:flex;gap:22px;padding-top:20px;min-height:0">
    <div style="flex:1;min-width:0;display:flex;flex-direction:column">
      <div style="display:flex;gap:13px;padding:0 13px 9px;font:500 9.5px/1 {FU};
           letter-spacing:1.3px;text-transform:uppercase;color:{LO}">
        <span style="width:13px;flex:none"></span><span style="width:148px;flex:none">Power</span>
        <span style="width:168px;flex:none">Controlled by</span><span>Options</span>
      </div>
      <div style="border:1px solid {CH3};border-radius:6px;overflow:hidden;background:{CH1}">
        {''.join(seat(*s) for s in SEATS)}
      </div>
      <div style="font:400 11px/1.6 {FU};color:{LO};padding:11px 3px 0;max-width:78ch">
        Persona gives an agent the character of its power — Austria weary and formal, Italy theatrical,
        Turkey terse. Turning it off leaves a plain strategist, which is the control condition for the benchmark.</div>
    </div>

    <div style="width:352px;flex:none;display:flex;flex-direction:column;gap:12px">
      {card('Negotiation', radio('Full press — every power may write to any other', True)
        + radio('Public press only', False) + radio('No press', False)
        + f'<div style="height:1px;background:{CH3};margin:9px 0"></div>'
        + row('Rounds per movement phase', sel('3', wide=66))
        + row('Round timer', sel('none', wide=100)))}
      {card('Length', row('Solo victory at', sel('18 centres', wide=118))
        + row('Year cap', sel('1920', wide=88))
        + row('Phase deadline', sel('none', wide=88))
        + f'<div style="font:400 10.5px/1.55 {FU};color:{LO};padding-top:8px">'
          f'At the cap the game is scored by centre share rather than left unfinished.</div>')}
      {card('Spending', row('Per-game cap', sel('$3.00', wide=88))
        + f'<div style="background:{CH2};border:1px solid {CH3};border-radius:5px;padding:10px 11px;margin-top:9px">'
          f'<div style="font:400 11px/1.6 {FU};color:{MID}">Six agents on <span style="font-family:{FM};'
          f'color:{HI}">deepseek-flash</span>, ten game-years:</div>'
          f'<div style="display:flex;align-items:baseline;gap:8px;margin-top:7px">'
          f'<span style="font:500 21px/1 {FM};color:{BRASS_HI}">$1.40</span>'
          f'<span style="font:400 10.5px/1 {FU};color:{LO}">peak &#183; about $0.70 off-peak</span></div>'
          f'<div style="font:400 10px/1.5 {FU};color:{LO};margin-top:7px">The game stops and logs if the cap is reached.</div></div>')}
      <span style="flex:1"></span>
      <button style="width:100%;border:1px solid {mix(BRASS,'#000',.28)};background:{BRASS};color:#211703;
           font:600 12.5px/1 {FU};letter-spacing:.9px;text-transform:uppercase;padding:14px;
           border-radius:5px;cursor:pointer">Begin Spring 1901</button>
    </div>
  </div>
</div>'''
open('Lobby.dc.html','w').write(dc(LBODY, props='{"$preview":{"width":1180,"height":860}}'))

# ============================= direction alternates (low-fi) =============================
OWN={}
for pw,scs in {'FRANCE':['PAR','BRE','MAR','SPA','POR','BEL'],'ENGLAND':['LON','EDI','LVP','NWY'],
 'GERMANY':['BER','KIE','MUN','HOL','DEN','SWE'],'ITALY':['ROM','NAP','VEN','TRI'],
 'AUSTRIA':['VIE','BUD','SER'],'RUSSIA':['MOS','WAR','SEV','STP','RUM','BUL'],
 'TURKEY':['ANK','CON','SMY']}.items():
    for s in scs: OWN[s]=pw
K=list(PV); VBM="80 50 1480 1245"

def minimap(dark):
    return (f'<svg viewBox="{VBM}" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" '
      f'style="display:block;position:absolute;inset:0">{DEFS}'
      f'{shapes(K,OWN,dark=dark)}{coastline(K,dark=dark)}{sc_marks(K,OWN,dark=dark,size=.8)}</svg>')

def bar(w,col,h=7,mb=6):
    return f'<div style="width:{w};height:{h}px;border-radius:3px;background:{col};margin-bottom:{mb}px"></div>'

def direction(name, tag, ink, panel_bg, panel_bd, top_bg, dark, label_col, accent):
    return f'''<div style="width:900px;height:600px;background:{top_bg};display:flex;flex-direction:column;
      font-family:{FU};overflow:hidden;border:1px solid {panel_bd}">
  <div style="flex:none;height:44px;background:{top_bg};border-bottom:1px solid {panel_bd};
       display:flex;align-items:center;gap:12px;padding:0 14px">
    <span style="font:500 15px/1 {FD};color:{ink}">{name}</span>
    <span style="font:400 10px/1 {FU};letter-spacing:1.2px;text-transform:uppercase;color:{label_col}">{tag}</span>
    <span style="flex:1"></span>
    {bar('70px',label_col,9,0)}
    <span style="width:52px;height:20px;border-radius:3px;background:{accent}"></span>
  </div>
  <div style="flex:1;display:flex;min-height:0">
    <div style="flex:1;position:relative;background:{'#16232D' if dark else SEA}">{minimap(dark)}</div>
    <div style="width:278px;flex:none;background:{panel_bg};border-left:1px solid {panel_bd};padding:14px">
      {bar('54px',label_col,8,12)}
      {''.join(bar(w,label_col) for w in ['100%','86%','92%'])}
      <div style="height:14px"></div>
      {bar('44px',label_col,8,10)}
      <div style="border:1px solid {panel_bd};border-radius:5px;padding:10px;margin-bottom:10px">
        {''.join(bar(w,label_col,6,5) for w in ['78%','62%'])}
      </div>
      <div style="border:1px solid {panel_bd};border-radius:5px;padding:10px;margin-bottom:10px">
        {''.join(bar(w,label_col,6,5) for w in ['84%','56%'])}
      </div>
      <span style="display:block;width:100%;height:30px;border-radius:4px;background:{accent}"></span>
      <div style="height:16px"></div>
      {bar('62px',label_col,8,10)}
      {''.join(bar(w,label_col,6,5) for w in ['92%','74%','88%','66%'])}
    </div>
  </div>
</div>'''


# ============================= canvas.json =============================
canvas={
 "artboards":[
  {"file":"Main.dc.html","x":0,"y":0,"w":1440,"h":900,"title":"Game screen"},
  {"file":"OrderStates.dc.html","x":1540,"y":0,"w":1464,"h":1060,"title":"Order entry states"},
  {"file":"MapLanguage.dc.html","x":3104,"y":0,"w":1080,"h":1000,"title":"Map language"},
  {"file":"Press.dc.html","x":0,"y":1200,"w":560,"h":880,"title":"Press panel","is_interactive":True},
  {"file":"Lobby.dc.html","x":660,"y":1200,"w":1180,"h":860,"title":"Lobby"}
 ],
 "annotations":[
  {"id":"brief","x":0,"y":-190,"w":620,"text":"Classic board, dark chrome.\nThe board matches the reference you sent: flat saturated fills, white stars for centres, pale sea, thin white borders between provinces. Colours come from Radix Colors (MIT), one hue per power.\nType is Newsreader for anything diplomatic, Barlow for controls, IBM Plex Mono for order strings.\nBoard is Fall 1902. France is convoying into London while England looks north — read the England thread."},
  {"id":"note-states","x":1540,"y":-190,"w":620,"text":"The six states are the whole interaction model, movement through adjustment.\nEvery clickable target is generated from the engine's own legal-order list, so an illegal order cannot be constructed. This is what v1 was missing."},
  {"id":"note-lang","x":3104,"y":-190,"w":560,"text":"One deliberate change from PLAN.md: support arrows are drawn supporter → destination with a hollow head, not supporter → origin. It reads as intent and matches Backstabbr and webDiplomacy. Say if you prefer the original.\nFailures are drawn in near-black ink so they never collide with Austria's red."},
  {"id":"note-press","x":0,"y":2090,"w":560,"text":"This panel is clickable — pick a power on the left and the thread changes. Seven real negotiations, mid-game.\nThe game screen uses a compressed chip version of the same thing to save width."},
  {"id":"note-lobby","x":660,"y":2090,"w":560,"text":"Any seat can be you, an agent, or a scripted bot, which is what makes one build serve both the game and the benchmark.\nThe cost figure is real: six deepseek-flash agents over ten game-years."},
  {"id":"note-open","x":3104,"y":1060,"w":560,"text":"Known gap: Austria and Italy sit next to each other and land on the same lightness, so they are the hardest pair in grayscale and for red-green colour blindness. A faint per-power hatch fill inside each province would fix it without changing the colours. Want it?"}
 ],
 "launch":{"view":"canvas"}
}
open('canvas.json','w').write(json.dumps(canvas, indent=2, ensure_ascii=False))
import os
for f in sorted(os.listdir('.')):
    print(f'{f:26s} {os.path.getsize(f)//1024:5d} KB')
