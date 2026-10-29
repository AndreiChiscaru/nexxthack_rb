"""Calm cartoon rendering of the approved layout and its actual entrance graph."""
from pathlib import Path
import re, math, random

ROOT = Path(__file__).resolve().parents[1]
assets = ROOT/'assets/raiff'
s = (ROOT/'scripts/frontend/city_map.gd').read_text(encoding='utf-8')
n = {k:(float(x),float(y)) for k,x,y in re.findall(r'"(\w+)": Vector2\(([-\d.]+),\s*([-\d.]+)\)',s.split('const NODES := {')[1].split('}')[0])}
edges = re.findall(r'\["(\w+)",\s*"(\w+)"\]',s.split('const EDGES := [')[1].split('const GRASS')[0])
buildings = [(float(x),float(y)) for x,y in re.findall(r'"position": Vector2\(([-\d.]+),\s*([-\d.]+)\)',s)]
props = (assets/'city_props.svg').read_text(encoding='utf-8').split('<defs>')[1].split('</defs>')[0]
# Same bench seen from behind: the backrest moves to the far edge, so it faces down-left.
bench_back = '<g id="bench_back"><path d="M-17 2v12m27-7v12" stroke="#4d5740" stroke-width="3"/><path d="M-22-1L-10-7 23 10 11 16Z" fill="#b28245" stroke="#79633f"/><path d="M-10-7v-12L23-2v12" fill="#d6a35c" stroke="#79633f"/><path d="M-10-13L23 4" stroke="#917244"/></g>'
out = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="2150.4" height="1433.6" viewBox="0 0 2150.4 1433.6"><defs>',props,bench_back,'</defs><rect width="2150.4" height="1433.6" fill="#bccb91"/>']
def emit(x): out.append(x)
def use(name,x,y,scale=1): emit(f'<use xlink:href="#{name}" transform="translate({x},{y}) scale({scale})"/>')
# Soft lighter meadows under everything, so the grass is not one flat colour.
for x,y,rx,ry in [(520,260,260,150),(1600,250,300,140),(880,1180,280,130),(1700,1180,260,140),(420,880,200,160),(1950,820,180,200),(1127,60,360,60)]:
 emit(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="#c9d99c" opacity=".55"/>')
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
# Plaza furniture.
# The bench prop faces up-right; bench_back shows it from behind, facing down-left. Mirroring each one
# gives four directions, and every bench takes the one closest to the fountain.
def bench(x,y,scale):
 name = 'bench' if FOUNTAIN[1] < y else 'bench_back'
 facing_right = FOUNTAIN[0] > x
 flip = -1 if (name=='bench') != facing_right else 1
 emit(f'<use xlink:href="#{name}" transform="translate({x},{y}) scale({flip*scale},{scale})"/>')
FOUNTAIN = (1127,672)
# Plaza benches near the rim, 80% of the way from the fountain to the middle of each plaza side.
for x,y in [(981,577),(1273,577),(981,767),(1273,767)]: bench(x,y,1.25)
# Lively park dressing on the grass only: never on roads, the plaza, the river, a building or its label.
# Seeded, so the map is identical on every rebuild.
rng = random.Random(7)
def bezier(p0,p1,p2,p3,steps=24):
 return [((1-t)**3*p0[0]+3*(1-t)**2*t*p1[0]+3*(1-t)*t*t*p2[0]+t**3*p3[0],
          (1-t)**3*p0[1]+3*(1-t)**2*t*p1[1]+3*(1-t)*t*t*p2[1]+t**3*p3[1]) for t in (i/steps for i in range(steps+1))]
# Centre line of the river path above (each S segment mirrors the previous control point).
river_line = bezier((15,-100),(90,30),(205,120),(185,300))+bezier((185,300),(165,480),(55,620),(115,850))+bezier((115,850),(175,1080),(5,1110),(100,1330))+[(160,1420),(220,1510)]
def river_gap(x,y): return min(math.hypot(x-px,y-py) for px,py in river_line)
def free(x,y,road,river=95,building=(185,300,70)):
 if not (20<x<2130 and 20<y<1415): return False
 if paved(x,y) or river_gap(x,y)<river: return False
 if any(dist((x,y),a,b)<road for a,b in segments): return False
 bw,up,down = building
 return not any(bx-bw<x<bx+bw and by-up<y<by+down for bx,by in buildings)
props_out = []
# Footprint radius of each prop; two props never get closer than the sum of their radii.
RADIUS = {'tree':38,'bench':30,'lamp':16,'flowers':30}
def spaced(name,x,y,scale=1):
 r = RADIUS[name]*scale
 return all(math.hypot(x-px,y-py) > r+RADIUS[pn]*ps for _,pn,px,py,ps in props_out)
def place(name,x,y,scale=1):
 props_out.append((y,name,x,y,scale))
# Benches sit right at the edge of a road, facing it; lamps stand at the roadside too.
long_roads = 0
for a,b in segments:
 length = math.hypot(b[0]-a[0],b[1]-a[1])
 if length<220: continue
 nx,ny = -(b[1]-a[1])/length, (b[0]-a[0])/length
 # A bench on every third long road, on the side facing the fountain so none end up outside the city.
 mid = ((a[0]+b[0])/2,(a[1]+b[1])/2)
 inward = 1 if nx*(1127-mid[0])+ny*(672-mid[1]) > 0 else -1
 long_roads += 1
 kinds = ((.5,'lamp'),(.28,'bench')) if long_roads%3==0 else ((.5,'lamp'),)
 for t,kind in kinds:
  reach = 33 + (abs(nx)*27 + abs(ny)*18 if kind=='bench' else 10)
  for side in ((inward,) if kind=='bench' else (inward,-inward)):
   x,y = a[0]+(b[0]-a[0])*t+nx*side*reach, a[1]+(b[1]-a[1])*t+ny*side*reach
   if free(x,y,reach-2,building=(185,300,40)) and spaced(kind,x,y,1.1):
    place(kind,x,y,1.1); break
# Trees: a loose jittered grid, so they spread over the parks without touching each other.
for gy in range(50,1420,100):
 for gx in range(40,2140,100):
  x,y = gx+rng.uniform(-34,34), gy+rng.uniform(-30,30)
  scale = round(rng.uniform(.9,1.25),2)
  if free(x,y,66) and spaced('tree',x,y,scale) and rng.random()<.55: place('tree',x,y,scale)
for _,name,x,y,scale in sorted(props_out):
 if name=='bench': bench(round(x,1),round(y,1),scale)
 else: use(name,round(x,1),round(y,1),scale)
# Reeds and stones along both river banks.
for i,(px,py) in enumerate(river_line[2:-2]):
 if i%2: continue
 for side in (-1,1):
  x,y = px+side*rng.uniform(72,92), py+rng.uniform(-12,12)
  if not (0<y<1430) or any(dist((x,y),a,b)<34 for a,b in segments) or abs(y-651)<45: continue
  if rng.random()<.6:
   emit(f'<path d="M{x:.0f} {y:.0f}l-4-20m4 20 3-24m-3 24 8-17" stroke="#6f8a45" stroke-width="2.2" stroke-linecap="round" fill="none"/>')
  else:
   emit(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="9" ry="5" fill="#9aa08a"/><ellipse cx="{x-2:.0f}" cy="{y-2:.0f}" rx="6" ry="3" fill="#c4c7b2"/>')
emit('</svg>')
(assets/'city_cartoon_terrain.svg').write_text('\n'.join(out),encoding='utf-8')
