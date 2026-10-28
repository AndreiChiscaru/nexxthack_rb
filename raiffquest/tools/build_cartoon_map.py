"""Calm cartoon rendering of the approved layout and its actual entrance graph."""
from pathlib import Path
import re, math

ROOT = Path(__file__).resolve().parents[1]
assets = ROOT/'assets/raiff'
s = (ROOT/'scripts/frontend/city_map.gd').read_text(encoding='utf-8')
n = {k:(float(x),float(y)) for k,x,y in re.findall(r'"(\w+)": Vector2\(([-\d.]+),\s*([-\d.]+)\)',s.split('const NODES := {')[1].split('}')[0])}
edges = re.findall(r'\["(\w+)",\s*"(\w+)"\]',s.split('const EDGES := [')[1].split('const GRASS')[0])
buildings = [(float(x),float(y)) for x,y in re.findall(r'"position": Vector2\(([-\d.]+),\s*([-\d.]+)\)',s)]
props = (assets/'city_props.svg').read_text(encoding='utf-8').split('<defs>')[1].split('</defs>')[0]
out = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="2150.4" height="1433.6" viewBox="0 0 2150.4 1433.6"><defs>',props,'</defs><rect width="2150.4" height="1433.6" fill="#bccb91"/>']
def emit(x): out.append(x)
def use(name,x,y,scale=1): emit(f'<use xlink:href="#{name}" transform="translate({x},{y}) scale({scale})"/>')
# Simple water bands: no photographic texture, bloom or neon greens.
river='M15 -100C90 30 205 120 185 300S55 620 115 850S5 1110 100 1330L220 1510'
for w,c in [(164,'#a8ba7e'),(146,'#ddd5ad'),(116,'#79a7ad'),(72,'#6d9ca6')]:
 emit(f'<path d="{river}" fill="none" stroke="{c}" stroke-width="{w}"/>')
emit(f'<path d="{river}" fill="none" stroke="#a5cbca" stroke-width="3" opacity=".55"/>')
segments=[(n[a],n[b]) for a,b in edges if b!='bridgewest']
def hull(points):
 points=sorted(set(points))
 def cross(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
 lo=[];hi=[]
 for p in points:
  while len(lo)>1 and cross(lo[-2],lo[-1],p)<=0: lo.pop()
  lo.append(p)
 for p in reversed(points):
  while len(hi)>1 and cross(hi[-2],hi[-1],p)<=0: hi.pop()
  hi.append(p)
 return lo[:-1]+hi[:-1]
path=' '.join(f'M{a[0]} {a[1]}L{b[0]} {b[1]}' for a,b in segments)
for width,col in [(58,'#94a37b'),(54,'#f3eed8'),(44,'#dfdbc7')]:
 emit(f'<path d="{path}" fill="none" stroke="{col}" stroke-width="{width}"/>')
 for node in n.values():
  points=[node]
  for a,b in segments:
   other=b if a==node else a if b==node else None
   if other is None: continue
   dx,dy=other[0]-node[0],other[1]-node[1]; length=math.hypot(dx,dy)
   if length:
    px,py=-dy/length*width/2,dx/length*width/2
    points.extend([(node[0]+px,node[1]+py),(node[0]-px,node[1]-py)])
  h=hull(points)
  if len(h)>2: emit('<polygon points="'+' '.join(f'{x},{y}' for x,y in h)+f'" fill="{col}"/>')
emit('<path d="M770 672L1127 434 1484 672 1127 910Z" fill="#dfdbc7"/>')
def dist(p,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1]; den=dx*dx+dy*dy
 t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
 return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
def paved(x,y):
 return abs(x-1127)/357+abs(y-672)/238<.98 or any(dist((x,y),a,b)<21 for a,b in segments)
# Faint large tiles, not a high-frequency stone texture.
for row,y in enumerate(range(70,1380,22)):
 for x in range(240+(row%2)*22,2120,44):
  if all(paved(px,py) for px,py in [(x,y),(x+41,y),(x+41,y+19),(x,y+19)]):
   emit(f'<path d="M{x} {y}h41v19h-41Z" fill="none" stroke="#c9c8b4" stroke-opacity=".45" stroke-width="1"/>')
# Bridge aligned with the graph.
emit('<path d="M15 629H238V675H15Z" fill="#bba276" stroke="#786c4e" stroke-width="3"/>')
for x in range(24,238,17): emit(f'<path d="M{x} 630v44" stroke="#d9c69a" stroke-width="2"/>')
for y in [624,668]:
 emit(f'<path d="M15 {y}H238" stroke="#76694a" stroke-width="4"/>')
 for x in range(20,238,36): emit(f'<path d="M{x} {y-5}v20" stroke="#76694a" stroke-width="3"/>')
# Round, illustrated fountain with clean shapes and a restrained palette.
emit('''<g transform="translate(1127,672)">
<ellipse cx="9" cy="24" rx="102" ry="58" fill="#7c8c64" opacity=".18"/>
<path d="M-96 0A96 54 0 0 0 96 0V23A96 54 0 0 1-96 23Z" fill="#9bb9ac" stroke="#819e91" stroke-width="2"/>
<ellipse rx="96" ry="54" fill="#f1eddb" stroke="#aab69c" stroke-width="2"/>
<ellipse rx="77" ry="41" fill="#7eb8b4"/><ellipse cy="3" rx="55" ry="29" fill="none" stroke="#c0dfcc" stroke-width="3"/>
<ellipse cy="3" rx="30" ry="15" fill="none" stroke="#c0dfcc" stroke-width="2"/>
<path d="M-25 0Q-25-100 0-120Q25-100 25 0L16 0Q16-87 0-105Q-16-87-16 0Z" fill="#a8d6ce" opacity=".8"/>
<path d="M0 0V-105" stroke="#e2efdc" stroke-width="4" stroke-linecap="round"/>
</g>''')
# Deliberately sparse props; no bushes filling every available patch.
for x,y,scale in [(650,210,1.2),(720,490,1.15),(580,590,.9),(1520,570,1.1),(1520,790,1.05),(720,810,1.1),(1850,190,1.15),(230,1240,1.1),(2000,1230,1.1)]:
 if all(dist((x,y),a,b)>70 for a,b in segments) and not any(bx-180<x<bx+180 and by-290<y<by+25 for bx,by in buildings): use('tree',x,y,scale)
for x,y in [(950,600),(1300,600),(950,755),(1300,755)]: use('flowers',x,y,1.4)
for x,y in [(1020,540),(1230,540),(1020,815),(1230,815)]: use('bench',x,y,1.25)
for x,y in [(1075,385),(1165,970),(715,700),(1540,700),(580,68),(1610,68),(2150,1050),(600,1370),(1690,1380)]: use('lamp',x,y,1.1)
emit('</svg>')
(assets/'city_cartoon_terrain.svg').write_text('\n'.join(out),encoding='utf-8')
