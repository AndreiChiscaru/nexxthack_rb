"""Regenerate the cartoon terrain from city_map.gd's navigation geometry.

Run with Python from any directory. Roads and avatar routes share one layout.
"""
from pathlib import Path
import math
import random
import re

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/raiff'
source = (ROOT/'scripts/frontend/city_map.gd').read_text(encoding='utf-8')
node_block = source.split('const NODES := {')[1].split('}')[0]
nodes = {k:(float(x),float(y)) for k,x,y in re.findall(r'"(\w+)": Vector2\(([-\d.]+),\s*([-\d.]+)\)',node_block)}
edge_block = source.split('const EDGES := [')[1].split('const GRASS')[0]
edges = re.findall(r'\["(\w+)",\s*"(\w+)"\]',edge_block)
places = re.findall(r'"(\w+)": \{"name": "[^"]+", "position": Vector2\((\d+),\s*(\d+)\)\}',source)
buildings = [(float(x),float(y)) for _,x,y in places]
props=(ASSETS/'city_props.svg').read_text(encoding='utf-8').split('<defs>')[1].split('</defs>')[0]
out=['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1800" height="1080" viewBox="-230 -90 1800 1080"><defs>',props,
'''<pattern id="paving" width="32" height="20" patternUnits="userSpaceOnUse"><rect width="32" height="20" fill="#ddd7bd"/><path d="M0 0H32M0 10H32M0 20H32M16 0V10M0 10V20M32 10V20" fill="none" stroke="#c8c3ac" stroke-width=".65"/><path d="M1 1H31M1 11H15" stroke="#eee9d3" stroke-width=".7"/></pattern>
<linearGradient id="river" x1="0" x2="1"><stop stop-color="#338fba"/><stop offset=".55" stop-color="#42a9c2"/><stop offset="1" stop-color="#67c0ca"/></linearGradient>
<g id="shrub"><ellipse cy="4" rx="17" ry="7" fill="#587836" opacity=".18"/><path d="M-14 2Q-24-9-12-15Q-12-26 0-22Q12-27 16-14Q26-8 14 3Z" fill="#78a53c" stroke="#608c35" stroke-width="1"/><path d="M-12-13Q-10-23 0-19Q11-23 13-13Q3-8-12-13" fill="#97bf4d"/></g>
<g id="flower"><path d="M0 2V-9M0 2Q-8-7-9-3M0 1Q6-6 8-4" fill="none" stroke="#69913a" stroke-width="2"/><g fill="#fff9da"><circle cy="-12" r="2.4"/><circle cx="-3" cy="-9" r="2.4"/><circle cx="3" cy="-9" r="2.4"/><circle cy="-6" r="2.4"/></g><circle cy="-9" r="1.8" fill="#f9d855"/></g>
</defs><rect x="-230" y="-90" width="1800" height="1080" fill="#b4ce78"/>''']
def emit(s): out.append(s)
def use(name,x,y,scale=1): emit(f'<use xlink:href="#{name}" transform="translate({x:.1f},{y:.1f}) scale({scale:.2f})"/>')
def rx(y): return -45+34*math.sin((y+50)/125)
riverpts=[(rx(y),y) for y in range(-120,1021,12)]
d='M'+'L'.join(f'{x:.1f},{y}' for x,y in riverpts)
for width,color in [(112,'#9db864'),(96,'#dfd69e'),(82,'#f2e3ad'),(70,'url(#river)')]:
 emit(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"/>')
for offset,width,color,opacity in [(-21,7,'#8cdae0',.35),(13,9,'#227fae',.22),(-5,3,'#a0dfe0',.19)]:
 path='M'+'L'.join(f'{x+offset:.1f},{y}' for x,y in riverpts)
 emit(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>')
rng=random.Random(23)
for y in range(-40,980,45):
 x=rx(y)+rng.uniform(-18,18)
 emit(f'<path d="M{x:.1f} {y}q5 3 11 0m-7 5h5" fill="none" stroke="#b3e8df" stroke-width="1.2" opacity=".6"/>')
# Draw all paths in passes so junctions remain seamless.
segments=[(nodes[a],nodes[b]) for a,b in edges if b!='bridgewest']

paths=' '.join(f'M{a[0]} {a[1]}L{b[0]} {b[1]}' for a,b in segments)
def convex_hull(points):
 points=sorted(set(points))
 def cross(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
 lower=[]
 for p in points:
  while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0: lower.pop()
  lower.append(p)
 upper=[]
 for p in reversed(points):
  while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0: upper.pop()
  upper.append(p)
 return lower[:-1]+upper[:-1]
# Bevel joins at graph nodes close diagonal corners without rounded dead ends.
def junctions(width,color):
 for origin in nodes.values():
  points=[origin]
  for a,b in segments:
   target=b if a==origin else a if b==origin else None
   if target is None: continue
   dx,dy=target[0]-origin[0],target[1]-origin[1]; length=math.hypot(dx,dy)
   if length==0: continue
   px,py=-dy/length*width/2,dx/length*width/2
   points.extend([(origin[0]+px,origin[1]+py),(origin[0]-px,origin[1]-py)])
  hull=convex_hull(points)
  if len(hull)>2:
   coords=' '.join(f'{x:.2f},{y:.2f}' for x,y in hull)
   emit(f'<polygon points="{coords}" fill="{color}"/>')
for width,color in [(43,'#94aa65'),(40,'#f4efd4'),(32,'#ded8be')]:
 emit(f'<path d="{paths}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="bevel" stroke-linecap="butt"/>')
 junctions(width,color)
emit('<path d="M470 480L650 350 830 480 650 610Z" fill="#ded8be"/>')
# Godot's SVG importer does not render pattern fills: emit real paving stones.
def segment_distance(p,a,b):
 vx,vy=b[0]-a[0],b[1]-a[1]; den=vx*vx+vy*vy
 t=max(0,min(1,((p[0]-a[0])*vx+(p[1]-a[1])*vy)/den)) if den else 0
 return math.hypot(p[0]-a[0]-t*vx,p[1]-a[1]-t*vy)
def paved(x,y):
 return abs(x-650)/180+abs(y-480)/130<.98 or any(segment_distance((x,y),a,b)<15.5 for a,b in segments)
for row,y in enumerate(range(0,980,9)):
 for x in range(-130+(row%2)*9,1550,18):
  if all(paved(px,py) for px,py in [(x,y),(x+16,y),(x+16,y+7),(x,y+7)]):
   fill=['#e2dcc5','#dad4ba','#e8e1cc','#ded8c0'][(row+x//18)%4]
   emit(f'<path d="M{x} {y}h16v7h-16Z" fill="{fill}" stroke="#c8c3ac" stroke-width=".45"/><path d="M{x+1} {y+1}h14" stroke="#f2ebd5" stroke-width=".5"/>')
# Wooden river crossing.
emit('<path d="M-120 451H30V485H-120Z" fill="#536e54" opacity=".25"/><path d="M-120 447H30V480H-120Z" fill="#ba9457" stroke="#6e623e" stroke-width="2"/>')
for x in range(-116,30,11): emit(f'<path d="M{x} 448v31" stroke="#e3bf7f" stroke-width="2"/>')
for y in [442,473]:
 emit(f'<path d="M-122 {y}H32" stroke="#695c3c" stroke-width="3"/>')
 for x in range(-120,33,25): emit(f'<path d="M{x} {y-2}v13" stroke="#695c3c" stroke-width="2"/>')
# Fountain: clean turquoise bowl, rounded stone volume and a translucent jet.
emit('''<g transform="translate(650,480) scale(1.35)"><ellipse cx="5" cy="19" rx="50" ry="26" fill="#647b47" opacity=".17"/><path d="M-45-1A45 26 0 0 0 45-1V12A45 26 0 0 1-45 12Z" fill="#9fb9a4" stroke="#849d8c"/><ellipse rx="45" ry="26" fill="#eeebd2"/><ellipse rx="36" ry="20" fill="#50b2bb"/><ellipse cy="2" rx="27" ry="14" fill="none" stroke="#a1ddd4" stroke-width="2"/><ellipse cy="2" rx="14" ry="7" fill="none" stroke="#b7e5d7" stroke-width="1.5"/><path d="M-18 0Q-18-57 0-67Q18-57 18 0L12 0Q12-46 0-57Q-12-46-12 0Z" fill="#83d8d5" opacity=".67"/><path d="M0 0V-57" stroke="#cdf4e4" stroke-width="3" stroke-linecap="round"/><path d="M0-68Q-9-58 0-54Q9-58 0-68" fill="#c6f0df"/></g>''')
def distance(p,a,b):
 vx,vy=b[0]-a[0],b[1]-a[1]; den=vx*vx+vy*vy
 t=max(0,min(1,((p[0]-a[0])*vx+(p[1]-a[1])*vy)/den)) if den else 0
 return math.hypot(p[0]-a[0]-t*vx,p[1]-a[1]-t*vy)
def clear(x,y,margin=25):
 if abs(x-rx(y))<85 or math.hypot((x-650),(y-480)*1.4)<215: return False
 if any(bx-140-margin<x<bx+140+margin and by-220-margin<y<by+40+margin for bx,by in buildings): return False
 return all(distance((x,y),a,b)>margin+28 for a,b in segments)
# Scatter only on open lawn; never cover building entrances or routes.
trees=[]
for _ in range(900):
 x,y=rng.uniform(-190,1510),rng.uniform(-20,970)
 if clear(x,y,36) and all(math.hypot(x-a,y-b)>100 for a,b in trees):
  trees.append((x,y))
  if len(trees)==25: break
for x,y in sorted(trees,key=lambda p:p[1]): use('tree',x,y,rng.uniform(.9,1.25))
for _ in range(85):
 x,y=rng.uniform(-200,1530),rng.uniform(-40,970)
 if clear(x,y,10) and all(math.hypot(x-a,y-b)>55 for a,b in trees):
  if rng.random()<.22: use('shrub',x,y,rng.uniform(.6,.9))
  elif rng.random()<.5:
   use('flower',x,y,.9); use('flower',x+6,y+3,.65)
  else:
   emit(f'<path d="M{x:.1f} {y:.1f}l-3-5m4 5 1-7m1 7 4-4" stroke="#92b75b" stroke-width="2" stroke-linecap="round" opacity=".6"/>')
for x,y in [(535,450),(760,515),(600,580),(725,405)]: use('flowers',x,y,1.2)
for x,y in [(570,406),(740,565),(510,520)]: use('bench',x,y,.95)
for x,y in [(483,435),(815,515),(635,335),(635,645),(195,390),(190,700),(825,160),(1450,600),(930,720),(500,750)]: use('lamp',x,y,.9)
emit('</svg>')
(ASSETS/'city_terrain.svg').write_text('\n'.join(out),encoding='utf-8')
