# Builds the event hall (Italian palace, evening) as a Blender/Cycles scene from the sketch layout.
# Usage: python build_hall.py <out.blend> <texdir>
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix
from PIL import Image, ImageDraw, ImageFilter

OUT, TEX = sys.argv[1], sys.argv[2]
os.makedirs(TEX, exist_ok=True)
random.seed(4)
S = 12.37/368; OX, OY = 385, 990
H = 5.0                      # ceiling height (m)
def W(px, py): return ((px-OX)*S, -(py-OY)*S)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
COL = scene.collection

# ------------------------------------------------------------------ materials
def nt(m): return m.node_tree
def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, nt(m).nodes, nt(m).links, nt(m).nodes['Principled BSDF']
def socket(node, name, typ, out=False):
    for s in (node.outputs if out else node.inputs):
        if s.name == name and s.type == typ: return s
    raise KeyError(name)
def mix_rgb(nodes, links, fac, a, b):
    m = nodes.new('ShaderNodeMix'); m.data_type = 'RGBA'
    links.new(fac, m.inputs[0])
    for src, idx in ((a, 6), (b, 7)):
        if isinstance(src, tuple): m.inputs[idx].default_value = (*src, 1)
        else: links.new(src, m.inputs[idx])
    return m.outputs[2]
def principled(name, color, rough=.5, metal=0., **kw):
    m, n, l, p = new_mat(name)
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    for k, v in kw.items():
        sk = p.inputs[k]
        if isinstance(v, tuple) and len(sk.default_value) == 4: v = (*v, 1)
        sk.default_value = v
    return m
def emission(name, color, strength):
    m, n, l, p = new_mat(name)
    n.remove(p); e = n.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    l.new(e.outputs[0], n['Material Output'].inputs[0]); return m
def glass(name, ior=1.5, tint=(1, 1, 1), rough=0.0):
    m, n, l, p = new_mat(name)
    n.remove(p); g = n.new('ShaderNodeBsdfGlass')
    g.inputs['Color'].default_value = (*tint, 1); g.inputs['IOR'].default_value = ior
    g.inputs['Roughness'].default_value = rough
    l.new(g.outputs[0], n['Material Output'].inputs[0]); return m
def marble(name, base, vein, vein2, grout=None, tile=1.2, coat=.6, rough=.12, scale=.22):
    m, n, l, p = new_mat(name)
    tc = n.new('ShaderNodeTexCoord')
    def noise(sc, det, dist, rgh=.6):
        t = n.new('ShaderNodeTexNoise'); t.inputs['Scale'].default_value = sc
        t.inputs['Detail'].default_value = det; t.inputs['Distortion'].default_value = dist
        t.inputs['Roughness'].default_value = rgh
        l.new(tc.outputs['Object'], t.inputs['Vector']); return t
    def ramp(src, stops):
        r = n.new('ShaderNodeValToRGB'); cr = r.color_ramp
        for i, (pos, c) in enumerate(stops):
            e = cr.elements[i] if i < 2 else cr.elements.new(pos)
            e.position = pos; e.color = (*c, 1)
        l.new(src, r.inputs[0]); return r.outputs[0]
    n1 = noise(scale, 12, 2.4); n2 = noise(scale*3.1, 10, 3.5)
    v1 = ramp(n1.outputs['Fac'], [(0, base), (.475, base), (.5, vein), (.525, base), (1, base)])
    v2 = ramp(n2.outputs['Fac'], [(0, (1, 1, 1)), (.49, (1, 1, 1)), (.5, vein2), (.51, (1, 1, 1)), (1, (1, 1, 1))])
    mul = n.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1
    l.new(v1, mul.inputs[6]); l.new(v2, mul.inputs[7]); col = mul.outputs[2]
    rough_src = None
    if grout:
        b = n.new('ShaderNodeTexBrick'); b.offset = 0; b.squash = 1
        for k, v in (('Scale', 1), ('Mortar Size', .0025), ('Mortar Smooth', .3), ('Brick Width', tile), ('Row Height', tile), ('Bias', 0)):
            b.inputs[k].default_value = v
        l.new(tc.outputs['Object'], b.inputs['Vector'])
        col = mix_rgb(n, l, b.outputs['Fac'], col, grout)
        mr = n.new('ShaderNodeMath'); mr.operation = 'MULTIPLY_ADD'
        l.new(b.outputs['Fac'], mr.inputs[0]); mr.inputs[1].default_value = .5; mr.inputs[2].default_value = rough
        rough_src = mr.outputs[0]
    l.new(col, p.inputs['Base Color'])
    if rough_src: l.new(rough_src, p.inputs['Roughness'])
    else: p.inputs['Roughness'].default_value = rough
    p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = .03
    return m

M = {}
M['floor']   = marble('calacatta', (.86, .84, .80), (.42, .39, .35), (.62, .55, .44), grout=(.55, .52, .47))
M['stone']   = marble('ivory_stone', (.84, .80, .74), (.66, .62, .56), (.72, .66, .58), coat=.35, rough=.2, scale=.5)
M['paint']   = principled('ivory_paint', (.80, .74, .65), .55)
M['ceil']    = principled('ceiling_paint', (.66, .60, .52), .7)
M['gold']    = principled('gold_leaf', (.83, .60, .30), .24, 1.)
M['gold_s']  = principled('gold_satin', (.80, .58, .30), .38, 1.)
M['mirror']  = principled('antique_mirror', (.70, .62, .52), .04, 1.)
M['led']     = emission('cove_led', (1., .58, .28), 14.)
M['cloth']   = principled('linen', (.82, .79, .74), .8, **{'Sheen Weight': .7, 'Sheen Roughness': .4, 'Subsurface Weight': .05})
M['velvet']  = principled('velvet', (.62, .55, .45), .85, **{'Sheen Weight': 1., 'Sheen Roughness': .35})
M['cushion'] = principled('cushion', (.80, .76, .70), .75, **{'Sheen Weight': .5})
M['porcelain'] = principled('porcelain', (.86, .85, .82), .08, **{'Coat Weight': .6})
M['glass']   = principled('glass', (1., 1., 1.), 0., **{'Transmission Weight': 1., 'IOR': 1.45, 'Thin Wall': True, 'Specular IOR Level': .6})
M['crystal'] = glass('crystal', 1.62)
M['wax']     = principled('wax', (.85, .80, .70), .4, **{'Subsurface Weight': .6, 'Subsurface Radius': (.05, .03, .02)})
M['flame']   = emission('flame', (1., .55, .2), 60.)
M['bulb']    = emission('bulb', (1., .72, .45), 40.)
M['runner']  = principled('runner', (.72, .65, .55), .95)
M['rose_w']  = principled('rose_white', (.86, .84, .80), .6, **{'Subsurface Weight': .25})
M['rose_i']  = principled('rose_ivory', (.86, .80, .70), .6, **{'Subsurface Weight': .25})
M['rose_b']  = principled('rose_blush', (.84, .66, .62), .6, **{'Subsurface Weight': .25})
M['leaf']    = principled('leaf', (.09, .16, .08), .45)
M['dark']    = principled('dark', (.03, .03, .03), .5)

# ------------------------------------------------------------------ bmesh helpers
class Builder:
    def __init__(self, mats): self.bm = bmesh.new(); self.mats = mats; self.idx = {k: i for i, k in enumerate(mats)}
    def _tag(self, verts, mat, smooth):
        fs = {f for v in verts for f in v.link_faces}
        for f in fs: f.material_index = self.idx[mat]; f.smooth = smooth
    def box(self, c, size, mat, rz=0.):
        r = bmesh.ops.create_cube(self.bm, size=1., matrix=Matrix.Translation(Vector(c)) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Diagonal((*size, 1)))
        self._tag(r['verts'], mat, False)
    def cyl(self, c, r1, r2, h, mat, segs=24, mtx=None, smooth=True):
        mt = Matrix.Translation(Vector(c)) @ (mtx or Matrix()) @ Matrix.Translation((0, 0, h/2))
        r = bmesh.ops.create_cone(self.bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=h, matrix=mt)
        self._tag(r['verts'], mat, smooth)
    def ico(self, c, rad, mat, sub=2, scale=(1, 1, 1), mtx=None):
        mt = Matrix.Translation(Vector(c)) @ (mtx or Matrix()) @ Matrix.Diagonal((*scale, 1))
        r = bmesh.ops.create_icosphere(self.bm, subdivisions=sub, radius=rad, matrix=mt)
        self._tag(r['verts'], mat, True); return r['verts']
    def lathe(self, prof, mat, segs=24, mtx=Matrix(), smooth=True):
        rings = []
        for (rr, z) in prof:
            ring = []
            for i in range(segs):
                a = i/segs*2*math.pi
                ring.append(self.bm.verts.new(mtx @ Vector((rr*math.cos(a), rr*math.sin(a), z))))
            rings.append(ring)
        fs = []
        for a, b in zip(rings, rings[1:]):
            for i in range(segs):
                j = (i+1) % segs
                try: fs.append(self.bm.faces.new((a[i], a[j], b[j], b[i])))
                except ValueError: pass
        for f in fs: f.material_index = self.idx[mat]; f.smooth = smooth
    def torus(self, c, R, r, mat, seg=48, ring=10, mtx=Matrix()):
        vs = []
        for i in range(seg):
            a = i/seg*2*math.pi; row = []
            for j in range(ring):
                b = j/ring*2*math.pi
                p = Vector(((R+r*math.cos(b))*math.cos(a), (R+r*math.cos(b))*math.sin(a), r*math.sin(b)))
                row.append(self.bm.verts.new(Vector(c) + mtx @ p))
            vs.append(row)
        for i in range(seg):
            for j in range(ring):
                f = self.bm.faces.new((vs[i][j], vs[(i+1) % seg][j], vs[(i+1) % seg][(j+1) % ring], vs[i][(j+1) % ring]))
                f.material_index = self.idx[mat]; f.smooth = True
    def tube(self, pts, r, mat, segs=8):  # sweep along polyline, capped at both ends
        prev = None; first = None
        for k, p in enumerate(pts):
            p = Vector(p); d = (Vector(pts[min(k+1, len(pts)-1)]) - Vector(pts[max(k-1, 0)])).normalized()
            q = d.to_track_quat('Z', 'Y').to_matrix()
            ring = [self.bm.verts.new(p + q @ Vector((r*math.cos(i/segs*6.283), r*math.sin(i/segs*6.283), 0))) for i in range(segs)]
            if prev:
                for i in range(segs):
                    f = self.bm.faces.new((prev[i], prev[(i+1) % segs], ring[(i+1) % segs], ring[i])); f.material_index = self.idx[mat]; f.smooth = True
            else: first = ring
            prev = ring
        for cap in (first, prev[::-1]):
            f = self.bm.faces.new(cap); f.material_index = self.idx[mat]
    def poly(self, pts, mat, z=0., smooth=False):
        f = self.bm.faces.new([self.bm.verts.new((x, y, z)) for x, y in pts]); f.material_index = self.idx[mat]; f.smooth = smooth; return f
    def mesh(self, name):
        me = bpy.data.meshes.new(name); self.bm.normal_update(); self.bm.to_mesh(me); self.bm.free()
        for k in self.mats: me.materials.append(M[k])
        return me
def place(name, me, loc=(0, 0, 0), rz=0., scale=1., bevel=0.):
    o = bpy.data.objects.new(name, me); o.location = loc; o.rotation_euler = (0, 0, rz); o.scale = (scale,)*3
    COL.objects.link(o)
    if bevel:
        b = o.modifiers.new('bevel', 'BEVEL'); b.width = bevel; b.segments = 2; b.limit_method = 'ANGLE'; b.harden_normals = True
    return o
def light(kind, loc, energy, color=(1., .72, .45), size=.1, direction=None, spot=40, blend=.3, cam=False, gloss=False):
    d = bpy.data.lights.new('L', kind); d.energy = energy; d.color = color
    if kind in ('POINT', 'SPOT'): d.shadow_soft_size = size
    if kind == 'SPOT': d.spot_size = math.radians(spot); d.spot_blend = blend
    if kind == 'AREA': d.size = size
    o = bpy.data.objects.new('L', d); o.location = loc; COL.objects.link(o)
    if direction is not None: o.rotation_euler = Vector(direction).to_track_quat('-Z', 'Y').to_euler()
    o.visible_camera = cam; o.visible_glossy = gloss
    return o

# ------------------------------------------------------------------ plan data
MAIN = [(118, 152), (650, 152), (650, 1325), (690, 1325), (690, 1830), (78, 1830), (78, 1330), (118, 1330)]
SIDE = [(650, 152), (1005, 152), (1005, 850), (720, 850), (720, 1325), (650, 1325)]
def inside(pt, poly):
    x, y = pt; c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:]+poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: c = not c
    return c
def interior(pt): return inside(pt, MAIN) or inside(pt, SIDE)

# ------------------------------------------------------------------ floors (+ medallion texture)
def floor_obj(name, pts, mat):
    b = Builder([mat]); verts = [b.bm.verts.new((*W(*p), 0)) for p in pts]
    f = b.bm.faces.new(verts); f.normal_update()
    if f.normal.z < 0: f.normal_flip()
    return place(name, b.mesh(name))
floor_obj('floor_main', MAIN, 'floor'); floor_obj('floor_side', SIDE, 'floor')

def medallion_png(path, w=2688, h=1452):
    im = Image.new('RGB', (w, h), (232, 228, 220)); d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y = random.random()*w, random.random()*h; pts = [(x, y)]
        for k in range(12): x += random.uniform(-90, 140); y += random.uniform(-90, 90); pts.append((x, y))
        d.line(pts, fill=(170, 160, 148), width=random.randint(1, 4))
    im = im.filter(ImageFilter.GaussianBlur(1.6)); d = ImageDraw.Draw(im)
    def band(m, c): d.rectangle((m, m, w-m, h-m), fill=c)
    band(0, (24, 24, 26)); band(56, (190, 150, 86)); band(68, (236, 232, 224))
    d.rectangle((140, 140, w-140, h-140), outline=(24, 24, 26), width=20)
    d.rectangle((168, 168, w-168, h-168), outline=(190, 150, 86), width=6)
    cx, cy = w/2, h/2
    for r, c in ((600, (24, 24, 26)), (584, (190, 150, 86)), (564, (238, 234, 226)), (420, (40, 40, 42)), (400, (190, 150, 86)), (384, (244, 240, 233))):
        d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=c)
    def star(R, r, nn, c, rot=0):
        pts = [(cx+math.cos(i*math.pi/nn+rot)*(r if i % 2 else R), cy+math.sin(i*math.pi/nn+rot)*(r if i % 2 else R)) for i in range(nn*2)]
        d.polygon(pts, fill=c)
    star(540, 190, 8, (190, 150, 86), math.pi/8); star(500, 160, 8, (40, 40, 42)); star(360, 140, 8, (210, 176, 112), math.pi/8); star(300, 110, 8, (244, 240, 233))
    d.ellipse((cx-68, cy-68, cx+68, cy+68), fill=(190, 150, 86)); d.ellipse((cx-36, cy-36, cx+36, cy+36), fill=(24, 24, 26))
    for (x, y, a) in ((180, 180, 0), (w-180, 180, 90), (w-180, h-180, 180), (180, h-180, 270)):
        d.pieslice((x-180, y-180, x+180, y+180), a, a+90, fill=(190, 150, 86)); d.pieslice((x-140, y-140, x+140, y+140), a, a+90, fill=(40, 40, 42))
    im.save(path)
medallion_png(os.path.join(TEX, 'medallion.png'))
mm, n, l, p = new_mat('medallion')
it = n.new('ShaderNodeTexImage'); it.image = bpy.data.images.load(os.path.abspath(os.path.join(TEX, 'medallion.png'))); it.image.pack()
l.new(it.outputs['Color'], p.inputs['Base Color']); p.inputs['Roughness'].default_value = .1
p.inputs['Coat Weight'].default_value = .7; p.inputs['Coat Roughness'].default_value = .02
M['medallion'] = mm
(x0, y0), (x1, y1) = W(218, 325), W(550, 505)
b = Builder(['medallion']); f = b.poly([(x0, y1), (x1, y1), (x1, y0), (x0, y0)], 'medallion', .012)
uv = b.bm.loops.layers.uv.new()
for lp in f.loops:
    co = lp.vert.co; lp[uv].uv = ((co.x-x0)/(x1-x0), (co.y-y1)/(y0-y1))
place('dance_floor', b.mesh('dance_floor'))

# runners (ivory carpet with gold edge)
def stadium(px0, py0, px1, py1, inset=0., n=24):
    (ax, ay), (bx, by) = W(px0, py0), W(px1, py1)
    cx, cy, w, ln = (ax+bx)/2, (ay+by)/2, abs(bx-ax)-2*inset, abs(by-ay)-2*inset
    r = w/2; pts = []
    for i in range(n+1): a = math.pi*i/n; pts.append((cx+r*math.cos(a), cy+(ln/2-r)+r*math.sin(a)))
    for i in range(n+1): a = math.pi+math.pi*i/n; pts.append((cx+r*math.cos(a), cy-(ln/2-r)+r*math.sin(a)))
    return pts
b = Builder(['runner', 'gold'])
for r in ((330, 850, 440, 1285), (335, 1520, 435, 1760)):
    outer = stadium(*r); inner = stadium(*r, inset=.08)
    b.poly(inner, 'runner', .008)
    for (p0, p1), (q0, q1) in zip(zip(outer, outer[1:]+outer[:1]), zip(inner, inner[1:]+inner[:1])):
        f = b.bm.faces.new([b.bm.verts.new((*p0, .009)), b.bm.verts.new((*p1, .009)), b.bm.verts.new((*q1, .009)), b.bm.verts.new((*q0, .009))]); f.material_index = 1
place('runners', b.mesh('runners'))

# ------------------------------------------------------------------ architecture
A = Builder(['paint', 'stone', 'gold', 'mirror', 'led', 'velvet', 'floor', 'dark'])
pilaster_spots = []; sconces = []
def wall(p0, p1, h=H, t=.32, mirrors=False):
    (ax, ay), (bx, by) = W(*p0), W(*p1)
    L = math.hypot(bx-ax, by-ay)
    if L < .05: return
    d = Vector(((bx-ax)/L, (by-ay)/L, 0)); rz = math.atan2(d.y, d.x)
    c = Vector(((ax+bx)/2, (ay+by)/2, 0))
    def at(s, off, z): return c + d*s + nrm*off + Vector((0, 0, z))
    if h < 2:   # balustrade
        nrm = Vector((-d.y, d.x, 0))
        A.box(c+Vector((0, 0, .08)), (L, t, .16), 'stone', rz)
        A.box(c+Vector((0, 0, h-.05)), (L+.1, t+.1, .1), 'stone', rz)
        A.box(c+Vector((0, 0, h+.005)), (L+.1, t+.12, .012), 'gold', rz)
        nb = int(L/.18)
        for i in range(nb):
            s = -L/2+(i+.5)*L/nb; q = c+d*s
            A.lathe([(0, .16), (.05, .16), (.05, .22), (.032, .27), (.06, .45), (.07, .55), (.035, .75), (.03, .8), (.05, .84), (.05, h-.1), (0, h-.1)], 'stone', 12, Matrix.Translation((q.x, q.y, 0)))
        return
    A.box(c+Vector((0, 0, h/2)), (L+t, t, h), 'paint', rz)
    pxm = ((p0[0]+p1[0])/2, (p0[1]+p1[1])/2)
    for side in (1, -1):
        nrm = Vector((-d.y, d.x, 0))*side
        probe = (pxm[0]+nrm.x/S*0.6, pxm[1]-nrm.y/S*0.6)
        if not interior(probe): continue
        f0 = t/2
        A.box(at(0, f0+.012, .09), (L, .025, .18), 'stone', rz)                 # skirting
        A.box(at(0, f0+.03, .98), (L, .06, .08), 'stone', rz)                   # dado rail
        A.box(at(0, f0+.06, .985), (L, .006, .012), 'gold', rz)
        # cornice: stepped profile, LED cove on top washing the ceiling
        for k, (dz, dep, hh) in enumerate(((H-.62, .06, .12), (H-.52, .12, .1), (H-.44, .2, .08), (H-.38, .26, .06))):
            A.box(at(0, f0+dep/2, dz), (L+(.0 if k < 3 else .0), dep, hh), 'stone', rz)
        A.box(at(0, f0+.17, H-.705), (L, .01, .02), 'gold', rz)
        A.box(at(0, f0+.2, H-.335), (L, .03, .01), 'led', rz)
        nb = max(1, round(L/3.3)); bw = L/nb
        for i in range(nb+1):
            s = -L/2+i*bw
            if L < 1.5 and i not in (0,): continue
            # pilaster with gold capital
            A.box(at(s, f0+.06, .22), (.62, .12, .44), 'stone', rz)
            A.box(at(s, f0+.05, (H-.65)/2+.2), (.5, .1, H-.65-.4), 'stone', rz)
            for k in range(-2, 3): A.box(at(s+k*.08, f0+.1, (H-.65)/2+.25), (.025, .012, H-1.4), 'paint', rz)
            A.box(at(s, f0+.08, H-.82), (.6, .16, .14), 'gold', rz)
            A.box(at(s, f0+.1, H-.7), (.68, .2, .08), 'stone', rz)
            pilaster_spots.append((at(s, f0+.35, .05), nrm))
        for i in range(nb):
            s = -L/2+(i+.5)*bw; wbay = bw-.9
            if wbay < .5: continue
            def frame(z0, z1, inset=0., mat='stone', prof=.07, dep=.035):
                ww = wbay-2*inset; hh = z1-z0
                A.box(at(s, f0+dep/2, z1-prof/2), (ww, dep, prof), mat, rz)
                A.box(at(s, f0+dep/2, z0+prof/2), (ww, dep, prof), mat, rz)
                A.box(at(s-ww/2+prof/2, f0+dep/2, (z0+z1)/2), (prof, dep, hh), mat, rz)
                A.box(at(s+ww/2-prof/2, f0+dep/2, (z0+z1)/2), (prof, dep, hh), mat, rz)
            top = H-1.05
            frame(1.3, top); frame(1.42, top-.12, .12, 'gold', .014, .012)
            frame(.24, .8); frame(.32, .72, .08, 'gold', .01, .01)
            if mirrors and i % 2 == 0:
                A.box(at(s, f0+.008, (1.5+top-.2)/2), (wbay-.36, .012, top-.2-1.5), 'mirror', rz)
            # sconce
            sc = at(s, f0, 2.45); sconces.append((sc, nrm, d))
        # frieze medallions above cornice
    return

wall((118, 152), (650, 152))
wall((118, 152), (118, 1330), mirrors=True); wall((118, 1330), (78, 1330)); wall((78, 1330), (78, 1830))
for seg in (((78, 1830), (100, 1830)), ((170, 1830), (595, 1830)), ((665, 1830), (690, 1830))): wall(*seg)
wall((690, 1830), (690, 1325)); wall((690, 1325), (650, 1325))
def gaps(p0, p1, gs, h):
    vert = p0[0] == p1[0]; a, b_ = (p0[1], p1[1]) if vert else (p0[0], p1[0]); cur = a
    for g0, g1 in gs + [(b_, b_)]:
        q0 = (p0[0], cur) if vert else (cur, p0[1]); q1 = (p0[0], g0) if vert else (g0, p0[1])
        wall(q0, q1, h); cur = g1
gaps((650, 152), (650, 1325), [(300, 340), (455, 520), (650, 710), (830, 890), (1010, 1080)], 1.0)
wall((650, 152), (1005, 152)); wall((1005, 152), (1005, 850), mirrors=True); wall((1005, 850), (720, 850))
gaps((720, 850), (720, 1325), [(1000, 1100)], H)
gaps((720, 250), (720, 850), [(290, 340), (600, 680)], 1.0)
wall((720, 1325), (690, 1325))
wall((78, 1588), (330, 1588), 1.0); wall((440, 1588), (690, 1588), 1.0)

def door(p0, p1):
    """Gilded double door with transom filling an exterior opening."""
    (ax, ay), (bx, by_) = W(*p0), W(*p1)
    L = math.hypot(bx-ax, by_-ay); d = Vector(((bx-ax)/L, (by_-ay)/L, 0)); rz = math.atan2(d.y, d.x)
    c = Vector(((ax+bx)/2, (ay+by_)/2, 0)); hd = 3.1
    A.box(c+Vector((0, 0, (hd+H)/2)), (L, .32, H-hd), 'paint', rz)
    A.box(c+Vector((0, 0, hd/2)), (L, .08, hd), 'paint', rz)
    for side in (1, -1):
        n = Vector((-d.y, d.x, 0))*side
        A.box(c+n*.06+Vector((0, 0, hd+.06)), (L+.3, .06, .14), 'stone', rz)
        for k in (-1, 1):
            for z0, z1 in ((.25, 1.25), (1.45, hd-.25)):
                cc = c+d*(k*L/4)+n*.045
                A.box(cc+Vector((0, 0, (z0+z1)/2)), (L/2-.3, .01, z1-z0), 'gold', rz)
                A.box(cc+n*.004+Vector((0, 0, (z0+z1)/2)), (L/2-.34, .01, z1-z0-.04), 'paint', rz)
        A.box(c+n*.06+Vector((0, 0, 1.1)), (.04, .03, .45), 'gold', rz)
for opening in (((100, 1830), (170, 1830)), ((595, 1830), (665, 1830)), ((720, 1000), (720, 1100))): door(*opening)

# columns
def column(px, py):
    x, y = W(px, py)
    A.box((x, y, .18), (.86, .86, .36), 'stone')
    A.torus((x, y, .42), .34, .07, 'stone'); A.torus((x, y, .53), .31, .04, 'stone')
    # fluted shaft
    segs, rings = 96, 6; hh0, hh1 = .55, H-1.05
    vs = []
    for k in range(rings+1):
        z = hh0+(hh1-hh0)*k/rings; r0 = .30-.03*k/rings; row = []
        for i in range(segs):
            a = i/segs*2*math.pi; r = r0*(1-.045*(.5+.5*math.cos(24*a))**3)
            row.append(A.bm.verts.new((x+r*math.cos(a), y+r*math.sin(a), z)))
        vs.append(row)
    for k in range(rings):
        for i in range(segs):
            f = A.bm.faces.new((vs[k][i], vs[k][(i+1) % segs], vs[k+1][(i+1) % segs], vs[k+1][i])); f.material_index = 1; f.smooth = True
    A.torus((x, y, hh1+.02), .285, .035, 'gold')
    A.lathe([(.27, hh1+.05), (.30, hh1+.12), (.38, hh1+.3), (.46, hh1+.42), (.5, hh1+.45)], 'gold', 32, Matrix.Translation((x, y, 0)))
    for k in range(16):
        a = k/16*2*math.pi
        A.ico((x+.36*math.cos(a), y+.36*math.sin(a), hh1+.26), .07, 'gold', 1, (1, 1, 1.8))
    A.box((x, y, hh1+.5), (1.0, 1.0, .1), 'stone'); A.box((x, y, hh1+.56), (1.04, 1.04, .02), 'gold')
    A.box((x, y, (hh1+.58+H)/2), (.9, .9, H-hh1-.58), 'stone')
for pt in ((340, 745), (428, 745), (222, 840), (547, 840), (222, 1283), (547, 1283), (340, 1380), (428, 1380)): column(*pt)

# stage: marble tiers, gold nosing, steps, arched backdrop with mirror and flower niches
def slab(p0, p1, z0, h, mat):
    (ax, ay), (bx, by) = W(*p0), W(*p1)
    A.box(((ax+bx)/2, (ay+by)/2, z0+h/2), (abs(bx-ax), abs(by-ay), h), mat)
slab((155, 185), (615, 280), 0, .45, 'stone'); slab((240, 215), (530, 310), 0, .8, 'stone')
(sx0, sy1), (sx1, _) = W(240, 310), W(530, 0); scx = (sx0+sx1)/2
A.box((scx, sy1-.01, .79), (sx1-sx0+.02, .04, .03), 'gold')
for k in range(2): A.box((scx, sy1-.15-k*.3, (2-k)*.2667/2), (4.2, .3, (2-k)*.2667), 'stone')
(bx0, by), (bx1, _) = W(250, 172), W(520, 0); bw = bx1-bx0
A.box((scx, by+.2, 2.5), (bw+.6, .4, 5.0), 'paint')
def arch_pts(cx, w, z0, ztop, n=24):
    r = w/2; pts = [(cx-r, z0), (cx-r, ztop-r)]
    pts += [(cx-r*math.cos(math.pi*i/n), ztop-r+r*math.sin(math.pi*i/n)) for i in range(1, n)]
    pts += [(cx+r, ztop-r), (cx+r, z0)]; return pts
def arch(cx, w, z0, ztop, fill):
    pts = arch_pts(cx, w, z0, ztop); yy = by
    for (x0_, z0_), (x1_, z1_) in zip(pts, pts[1:]):
        L = math.hypot(x1_-x0_, z1_-z0_); a = math.atan2(z1_-z0_, x1_-x0_)
        mt = Matrix.Translation(((x0_+x1_)/2, yy-.04, (z0_+z1_)/2)) @ Matrix.Rotation(-a, 4, 'Y') @ Matrix.Diagonal((L+.03, .1, .12, 1))
        r = bmesh.ops.create_cube(A.bm, size=1., matrix=mt); A._tag(r['verts'], 'gold', False)
    if fill:
        f = A.bm.faces.new([A.bm.verts.new((x, yy-.005, z)) for x, z in pts]); f.material_index = A.idx[fill]
    return pts
arch(scx, 3.2, .8, 4.3, 'mirror')
niche_pts = [arch(scx-3.2, 1.8, .8, 3.5, None), arch(scx+3.2, 1.8, .8, 3.5, None)]
A.box((scx, by-.05, 4.6), (bw+.8, .3, .2), 'stone'); A.box((scx, by-.08, 4.48), (bw+.8, .32, .02), 'gold')
stage_cols = [scx-bw/2-.1, scx+bw/2+.1]
for x in stage_cols:
    A.box((x, by-.25, .95), (.6, .6, .3), 'stone')
    A.lathe([(0, 1.1), (.24, 1.1), (.22, 1.2), (.2, 4.1), (.0, 4.1)], 'stone', 32, Matrix.Translation((x, by-.25, 0)))
    A.lathe([(.2, 4.1), (.3, 4.2), (.38, 4.35), (0, 4.35)], 'gold', 32, Matrix.Translation((x, by-.25, 0)))

# lounges, counters
def sofa(p0, p1, facing):
    (ax, ay), (bx, by_) = W(*p0), W(*p1); cx, cy, L = (ax+bx)/2, (ay+by_)/2, abs(by_-ay)
    A.box((cx, cy, .25), (.9, L, .34), 'velvet'); A.box((cx-facing*.36, cy, .65), (.2, L, .5), 'velvet')
    A.box((cx, cy+L/2-.1, .55), (.9, .2, .26), 'velvet'); A.box((cx, cy-L/2+.1, .55), (.9, .2, .26), 'velvet')
    A.box((cx+facing*.06, cy, .46), (.7, L-.42, .12), 'velvet')
    A.box((cx, cy, .04), (.92, L+.02, .08), 'gold')
    A.cyl((cx+facing*1.05, cy, 0), .12, .04, .46, 'gold'); A.cyl((cx+facing*1.05, cy, .46), .36, .36, .04, 'stone')
sofa((135, 365), (152, 545), 1); sofa((618, 365), (635, 545), -1); sofa((180, 365), (198, 515), 1); sofa((570, 365), (588, 515), -1)
def counter(p0, p1, h=1.08):
    (ax, ay), (bx, by_) = W(*p0), W(*p1)
    A.box(((ax+bx)/2, (ay+by_)/2, (h-.05)/2), (abs(bx-ax), abs(by_-ay), h-.05), 'paint')
    A.box(((ax+bx)/2, (ay+by_)/2, h-.025), (abs(bx-ax)+.12, abs(by_-ay)+.12, .05), 'stone')
    A.box(((ax+bx)/2, (ay+by_)/2, .1), (abs(bx-ax)+.01, abs(by_-ay)+.01, .03), 'gold')
counter((95, 675), (150, 745), 1.15); counter((795, 265), (853, 287))
for a_, b_ in ((385, 430), (565, 610), (742, 800), (915, 960)): counter((658, a_), (700, b_))
# plinths for urns (diamond marks)
urn_spots = []
for pt in ((266, 770), (505, 770), (263, 1355), (505, 1355)):
    x, y = W(*pt); A.box((x, y, .55), (.62, .62, 1.1), 'stone'); A.box((x, y, 1.12), (.72, .72, .04), 'gold'); urn_spots.append((x, y, 1.14))
arch_obj = place('architecture', A.mesh('architecture'), bevel=.006)

# ceiling: coffered grid with gold fillets, rosettes, recessed trays over the dance floor and long table
C = Builder(['ceil', 'gold', 'led'])
def ceil_poly(pts):
    f = C.bm.faces.new([C.bm.verts.new((*W(*p), H)) for p in pts]); f.normal_update()
    if f.normal.z > 0: f.normal_flip()
    f.material_index = 0
ceil_poly(MAIN); ceil_poly([(650, 152), (1005, 152), (1005, 850), (650, 850)]); ceil_poly([(650, 850), (720, 850), (720, 1325), (650, 1325)])
def beams(px0, py0, px1, py1, step=3.3):
    (ax, ay), (bx, by_) = W(px0, py0), W(px1, py1)
    xa, xb, ya, yb = min(ax, bx), max(ax, bx), min(ay, by_), max(ay, by_)
    nx_, ny_ = max(1, round((xb-xa)/step)), max(1, round((yb-ya)/step))
    for i in range(1, nx_):
        x = xa+(xb-xa)*i/nx_; C.box((x, (ya+yb)/2, H-.16), (.34, yb-ya, .32), 'ceil'); C.box((x, (ya+yb)/2, H-.325), (.06, yb-ya, .01), 'gold')
    for j in range(1, ny_):
        y = ya+(yb-ya)*j/ny_; C.box(((xa+xb)/2, y, H-.15), (xb-xa, .34, .30), 'ceil'); C.box(((xa+xb)/2, y, H-.305), (xb-xa, .06, .01), 'gold')
    for i in range(nx_):
        for j in range(ny_):
            x = xa+(xb-xa)*(i+.5)/nx_; y = ya+(yb-ya)*(j+.5)/ny_
            C.cyl((x, y, H-.03), .22, .16, .03, 'gold', 24); C.ico((x, y, H-.04), .06, 'gold', 2)
beams(118, 152, 650, 1330); beams(78, 1330, 690, 1830); beams(720, 152, 1005, 850)
ceiling_obj = place('ceiling', C.mesh('ceiling'), bevel=.01)

# ------------------------------------------------------------------ reusable furniture meshes
def chair_mesh():
    b = Builder(['gold', 'cushion'])
    for x, y in ((-.2, .19), (.2, .19), (-.2, -.19), (.2, -.19)):
        b.tube([(x, y, 0), (x*.97, y*.97, .44)], .014, 'gold')
    for x in (-.2, .2): b.tube([(x, -.19, .44), (x*1.02, -.235, .7), (x*1.04, -.265, .96)], .016, 'gold')
    for z in (.62, .8, .94): b.tube([(-.21, -.2-(z-.44)*.28, z), (.21, -.2-(z-.44)*.28, z)], .011, 'gold')
    for x in (-.1, 0, .1): b.tube([(x, -.2-.62*0+(-.18*.28), .62), (x, -.2-(.94-.44)*.28, .94)], .008, 'gold')
    for (p0, p1) in (((-.2, .19, .44), (.2, .19, .44)), ((-.2, -.19, .44), (.2, -.19, .44)), ((-.2, .19, .44), (-.2, -.19, .44)), ((.2, .19, .44), (.2, -.19, .44)),
                     ((-.2, .19, .2), (.2, .19, .2)), ((-.2, -.19, .2), (.2, -.19, .2))):
        b.tube([p0, p1], .011, 'gold')
    b.box((0, 0, .475), (.42, .4, .06), 'cushion')
    return b.mesh('chair')
def setting_mesh():
    b = Builder(['gold', 'porcelain', 'cloth', 'glass'])
    b.cyl((0, .21, 0), .158, .158, .006, 'gold', 40)
    b.lathe([(0, .006), (.08, .006), (.09, .009), (.125, .014), (.135, .02), (.133, .022), (.12, .017), (.085, .013), (0, .013)], 'porcelain', 40, Matrix.Translation((0, .21, 0)))
    b.box((0, .21, .032), (.17, .1, .03), 'cloth')
    b.box((0, .21, .032), (.03, .102, .032), 'gold')
    for x in (-.2, -.225): b.box((x, .2, .003), (.014, .19, .004), 'gold')
    for x in (.2, .225): b.box((x, .2, .003), (.012, .2, .004), 'gold')
    def goblet(x, y, cup_r, cup_h, stem):
        prof = [(0, 0), (.035, 0), (.035, .004), (.005, .008), (.004, stem), (cup_r*.4, stem+.01), (cup_r*.9, stem+cup_h*.45), (cup_r, stem+cup_h),
                (cup_r-.0015, stem+cup_h), (cup_r*.9-.0015, stem+cup_h*.45), (cup_r*.4-.002, stem+.014), (0, stem+.014)]
        b.lathe(prof, 'glass', 28, Matrix.Translation((x, y, 0)))
    goblet(.16, .42, .038, .1, .1); goblet(.07, .45, .042, .09, .08)
    return b.mesh('setting')
def rose(b, pos, q, s, mat):
    """Rose head of radius ~s: a tight bud plus three rings of cupped petals opening outward."""
    pos = Vector(pos); spin = random.random()*6.283
    b.ico(pos+q.to_3x3() @ Vector((0, 0, .35*s)), 1, mat, 1, (.32*s, .32*s, .42*s), q)
    for ring, (n, open_, rad, hgt) in enumerate(((4, .25, .22, .75), (5, .6, .48, .7), (7, 1.0, .72, .62))):
        for k in range(n):
            phi = spin+k/n*2*math.pi+ring*.5
            rows = []
            for vi in range(5):
                v = vi/4; wdt = .55*s*rad*1.6*math.sin(math.pi*(.15+.85*v))**.7+.02*s
                row = []
                for ui in range(5):
                    u = ui/4-.5
                    lx = u*wdt*2
                    ly = (-(u*u)*1.4*wdt) + v*v*open_*.55*s       # cupped, curling outward toward the tip
                    lz = v*hgt*s
                    pl = Vector((lx, rad*s+ly, lz))
                    pl = Matrix.Rotation(phi, 3, 'Z') @ pl
                    row.append(b.bm.verts.new(pos + q.to_3x3() @ pl))
                rows.append(row)
            for vi in range(4):
                for ui in range(4):
                    f = b.bm.faces.new((rows[vi][ui], rows[vi][ui+1], rows[vi+1][ui+1], rows[vi+1][ui]))
                    f.material_index = b.idx[mat]; f.smooth = True
def bloom_cluster(b, center, R, n, size, flat=1., hemi=False, spread=1., leaves=.12):
    mats = ['rose_w', 'rose_w', 'rose_i', 'rose_b']
    for i in range(n):
        u, v = random.random(), random.random(); th = 2*math.pi*u
        ph = math.acos(v if hemi else 2*v-1); r = R*(.9+random.random()*.14)
        dirv = Vector((math.sin(ph)*math.cos(th)*spread, math.sin(ph)*math.sin(th)*spread, math.cos(ph)*flat)).normalized()
        pos = Vector(center)+Vector((math.sin(ph)*math.cos(th)*r*spread, math.sin(ph)*math.sin(th)*r*spread, math.cos(ph)*r*flat))
        q = dirv.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        if random.random() < leaves:
            s = size*1.3; b.ico(pos, 1, 'leaf', 1, (s*1.1, s*.5, s*.12), q @ Matrix.Rotation(random.random()*6, 4, 'Z'))
        else:
            rose(b, pos, q, size*(.75+random.random()*.55), random.choice(mats))
def candle(b, x, y, z, h=.12, r=.012):
    b.cyl((x, y, z), r, r, h, 'wax', 12); b.ico((x, y, z+h+.022), 1, 'flame', 2, (.008, .008, .02))
def centerpiece_tall():
    b = Builder(['gold', 'wax', 'flame', 'rose_w', 'rose_i', 'rose_b', 'leaf', 'glass'])
    b.lathe([(0, 0), (.13, 0), (.13, .015), (.09, .03), (.05, .05), (.03, .12), (.045, .2), (.02, .3), (.017, .55), (.03, .6), (.02, .62), (0, .62)], 'gold', 32)
    for k in range(5):
        a = k/5*2*math.pi; ex, ey = .27*math.cos(a), .27*math.sin(a)
        b.tube([(0, 0, .45), (ex*.5, ey*.5, .4), (ex*.9, ey*.9, .45), (ex, ey, .53)], .008, 'gold')
        b.lathe([(0, .53), (.03, .53), (.035, .56), (0, .56)], 'gold', 16, Matrix.Translation((ex, ey, 0)))
        candle(b, ex, ey, .56, .14, .011)
    b.lathe([(0, .6), (.12, .62), (.16, .7), (0, .7)], 'gold', 32)
    bloom_cluster(b, (0, 0, .98), .3, 230, .045)
    for k in range(10):   # trailing greenery
        a = random.random()*6.28; b.ico((.3*math.cos(a), .3*math.sin(a), .78+random.random()*.1), 1, 'leaf', 1, (.05, .02, .006),
                                        Matrix.Rotation(a, 4, 'Z') @ Matrix.Rotation(.9, 4, 'Y'))
    return b.mesh('centerpiece_tall')
def centerpiece_low():
    b = Builder(['gold', 'wax', 'flame', 'rose_w', 'rose_i', 'rose_b', 'leaf', 'glass'])
    b.lathe([(0, 0), (.12, 0), (.12, .02), (.1, .06), (0, .06)], 'gold', 32)
    bloom_cluster(b, (0, 0, .07), .2, 70, .034, .75, True, 1.6)
    for dx in (-.42, .42):
        b.lathe([(0, 0), (.055, 0), (.058, .02), (.06, .22), (.057, .22), (.055, .02), (0, .02)], 'glass', 24, Matrix.Translation((dx, 0, 0)))
        candle(b, dx, 0, .02, .12, .035)
    return b.mesh('centerpiece_low')
def urn_arrangement():
    b = Builder(['gold', 'wax', 'flame', 'rose_w', 'rose_i', 'rose_b', 'leaf', 'glass'])
    b.lathe([(0, 0), (.14, 0), (.1, .06), (.12, .1), (.24, .22), (.27, .36), (.24, .42), (0, .42)], 'gold', 40)
    bloom_cluster(b, (0, 0, .7), .45, 420, .058, .85, leaves=.2)
    return b.mesh('urn_arrangement')
def flower_wall(pts, yy):
    b = Builder(['rose_w', 'rose_i', 'rose_b', 'leaf'])
    xs = [p[0] for p in pts]; zs = [p[1] for p in pts]; xa, xb, za, zb = min(xs), max(xs), min(zs), max(zs)
    poly = [(p[0], p[1]) for p in pts]
    for i in range(1400):
        x, z = random.uniform(xa, xb), random.uniform(za, zb)
        if not inside((x, z), poly): continue
        s = .055*(.75+random.random()*.6); q = Matrix.Rotation(math.pi/2, 4, 'X')
        m = random.choice(['rose_w', 'rose_w', 'rose_i', 'rose_b']) if random.random() > .1 else 'leaf'
        if m == 'leaf': b.ico((x, yy-.06, z), 1, m, 1, (s*1.2, s*.5, s*.1), q)
        else: rose(b, (x, yy-.03-random.random()*.04, z), q.inverted(), s, m)
    return b.mesh('flower_wall')
def chandelier_mesh():
    f = Builder(['gold', 'wax', 'bulb']); c = Builder(['crystal'])
    f.lathe([(0, -.55), (.03, -.5), (.06, -.38), (.03, -.3), (.05, -.15), (.09, -.05), (.05, .05), (.03, .2), (.05, .3), (.025, .45), (.02, .9), (0, .9)], 'gold', 24)
    f.torus((0, 0, 0), .58, .016, 'gold'); f.torus((0, 0, .32), .34, .013, 'gold'); f.torus((0, 0, .55), .16, .01, 'gold')
    def arm_ring(R, z, n, phase=0):
        for k in range(n):
            a = k/n*2*math.pi+phase; ex, ey = R*math.cos(a), R*math.sin(a)
            f.tube([(0, 0, z-.12), (ex*.4, ey*.4, z-.2), (ex*.85, ey*.85, z-.1), (ex, ey, z)], .01, 'gold')
            f.lathe([(0, z), (.035, z), (.04, z+.025), (0, z+.025)], 'gold', 16, Matrix.Translation((ex, ey, 0)))
            f.cyl((ex, ey, z+.025), .012, .012, .09, 'wax', 10)
            f.ico((ex, ey, z+.13), 1, 'bulb', 2, (.016, .016, .028))
    arm_ring(.58, .02, 10); arm_ring(.34, .34, 6, .3)
    def prism(p, s=.018, L=1.9):
        c.ico(p, 1, 'crystal', 1, (s, s, s*L))
    for R, z, n, k in ((.58, -.01, 30, 3), (.34, .31, 18, 2)):
        for i in range(n):
            a = i/n*2*math.pi
            for j in range(k): prism((R*math.cos(a), R*math.sin(a), z-.05-j*.065))
    for i in range(10):   # swags between arms
        a0, a1 = i/10*2*math.pi, (i+1)/10*2*math.pi
        for t in range(1, 9):
            u = t/9; a = a0+(a1-a0)*u
            prism((.6*math.cos(a), .6*math.sin(a), .0-.14*math.sin(math.pi*u)), .011, 1.0)
    for j in range(7): prism((0, 0, -.6-j*.06), .03*(1-j*.09), 1.3)
    return f.mesh('chandelier_frame'), c.mesh('chandelier_crystals')
def sconce_mesh():
    b = Builder(['gold', 'wax', 'bulb'])
    b.box((0, .015, 0), (.12, .03, .32), 'gold'); b.ico((0, .04, .17), .04, 'gold', 2)
    for s in (-1, 1):
        b.tube([(0, .03, -.08), (s*.08, .1, -.06), (s*.15, .14, .02)], .009, 'gold')
        b.lathe([(0, 0), (.03, 0), (.035, .02), (0, .02)], 'gold', 16, Matrix.Translation((s*.15, .14, .02)))
        b.cyl((s*.15, .14, .04), .011, .011, .08, 'wax', 10); b.ico((s*.15, .14, .15), 1, 'bulb', 2, (.014, .014, .025))
    return b.mesh('sconce')

CHAIR, SETTING = chair_mesh(), setting_mesh()
CP_TALL, CP_LOW, URN = centerpiece_tall(), centerpiece_low(), urn_arrangement()
CH_F, CH_C = chandelier_mesh(); SCONCE = sconce_mesh()

# ------------------------------------------------------------------ tables with draped cloths
def resample(pts, step=.03, closed=True):
    out = []; seq = pts+[pts[0]] if closed else pts
    for p, q in zip(seq, seq[1:]):
        L = math.dist(p, q); n = max(1, int(L/step))
        out += [(p[0]+(q[0]-p[0])*i/n, p[1]+(q[1]-p[1])*i/n) for i in range(n)]
    return out
def cloth(outline, top=.76, drop=.745, flare=.07):
    b = Builder(['cloth']); pts = resample(outline)
    area = sum(p[0]*q[1]-q[0]*p[1] for p, q in zip(pts, pts[1:]+pts[:1]))
    if area < 0: pts = pts[::-1]
    N = len(pts); s = 0; arc = [0]
    for i in range(1, N): s += math.dist(pts[i], pts[i-1]); arc.append(s)
    ph = random.random()*10
    rings = []
    for k in range(9):
        t = k/8; z = top-drop*t if k else top
        ring = []
        for i, (x, y) in enumerate(pts):
            p0, p1 = pts[i-1], pts[(i+1) % N]; dx, dy = p1[0]-p0[0], p1[1]-p0[1]; ln = math.hypot(dx, dy) or 1
            nx_, ny_ = dy/ln, -dx/ln
            fold = .02*math.sin(arc[i]*2*math.pi/.17+ph+.6*math.sin(arc[i]*3.1))*(t**1.3)
            off = (.012 if k else 0)+flare*t**1.6+fold
            zz = top-.012 if k == 1 else z
            if k == 1: off = .012
            ring.append(b.bm.verts.new((x+nx_*off, y+ny_*off, zz)))
        rings.append(ring)
    f = b.bm.faces.new(rings[0]); f.material_index = 0
    for a, c in zip(rings, rings[1:]):
        for i in range(N):
            ff = b.bm.faces.new((a[i], a[(i+1) % N], c[(i+1) % N], c[i])); ff.smooth = True
    return place('cloth', b.mesh('cloth'))
chairs = []; settings = []; pieces = []; tall_spots = []; chand = []
def chair_at(x, y, fx, fy):
    a = math.atan2(fy-y, fx-x); chairs.append((x, y, a-math.pi/2))
    settings.append((x+math.cos(a)*.4, y+math.sin(a)*.4, a-math.pi/2))
def round_table(px, py, seats, r=.9, cp='tall', hang=True):
    x, y = W(px, py)
    cloth([(x+r*math.cos(i/96*2*math.pi), y+r*math.sin(i/96*2*math.pi)) for i in range(96)])
    for i in range(seats):
        a = i/seats*2*math.pi+.2; chair_at(x+math.cos(a)*(r+.4), y+math.sin(a)*(r+.4), x, y)
    if cp: pieces.append((cp, x, y, random.random()*6.28))
    if hang: chand.append((x, y, 1.0))
def rect_table(px, py, ln, wd, axis, per, ends):
    x, y = W(px, py)
    hx, hy = (ln/2, wd/2) if axis == 'x' else (wd/2, ln/2)
    cloth([(x-hx, y-hy), (x+hx, y-hy), (x+hx, y+hy), (x-hx, y+hy)])
    for i in range(per):
        t = -ln/2+(i+.5)*ln/per
        if axis == 'x': chair_at(x+t, y-wd/2-.4, x+t, y); chair_at(x+t, y+wd/2+.4, x+t, y)
        else: chair_at(x-wd/2-.4, y+t, x, y+t); chair_at(x+wd/2+.4, y+t, x, y+t)
    for e in range(ends):
        s_ = 1 if e else -1
        chair_at(x+s_*(ln/2+.4), y, x, y) if axis == 'x' else chair_at(x, y+s_*(ln/2+.4), x, y)
    n = max(1, round(ln/2.2))
    for i in range(n):
        t = -ln/2+(i+.5)*ln/n; pieces.append(('low', x+t, y, 0) if axis == 'x' else ('low', x, y+t, math.pi/2))
def square_table(px, py, size, per):
    x, y = W(px, py); h = size/2
    cloth([(x-h, y-h), (x+h, y-h), (x+h, y+h), (x-h, y+h)])
    for i in range(per):
        t = -h+(i+.5)*size/per; o = h+.4
        chair_at(x+t, y-o, x+t, y); chair_at(x+t, y+o, x+t, y); chair_at(x-o, y+t, x, y+t); chair_at(x+o, y+t, x, y+t)
    pieces.append(('low', x, y, .785))
def arc_pts(cx, cy, r, a0, a1, n=16):
    return [(cx+r*math.cos(math.radians(a0+(a1-a0)*i/n)), cy+r*math.sin(math.radians(a0+(a1-a0)*i/n))) for i in range(n+1)]
def path_table(pxpts, seats, wid=1.0):
    pts = [Vector(W(*p)) for p in pxpts]
    cum = [0.]
    for i in range(1, len(pts)): cum.append(cum[-1]+(pts[i]-pts[i-1]).length)
    L = cum[-1]
    def at(s):
        i = 1
        while i < len(cum)-1 and cum[i] < s: i += 1
        a, b_ = pts[i-1], pts[i]; f = (s-cum[i-1])/((cum[i]-cum[i-1]) or 1)
        p = a.lerp(b_, f); t = (b_-a).normalized(); return p, Vector((-t.y, t.x))
    left, right = [], []
    for k in range(int(L/.05)+1):
        p, nrm = at(min(L, k*.05)); left.append(tuple(p+nrm*wid/2)); right.append(tuple(p-nrm*wid/2))
    cloth(left+right[::-1])
    n1 = math.ceil(seats/2); n2 = seats-n1
    for n_, s_ in ((n1, 1), (n2, -1)):
        for i in range(n_):
            p, nrm = at((i+.5)/n_*L); q = p+nrm*s_*(wid/2+.4); chair_at(q.x, q.y, p.x, p.y)
    n = max(1, round(L/2.2))
    for i in range(n):
        p, nrm = at((i+.5)/n*L); pieces.append(('low', p.x, p.y, math.atan2(nrm.y, nrm.x)+math.pi/2))

for pt in ((315, 680), (228, 712), (173, 792), (453, 685), (541, 712), (596, 792), (173, 1328), (228, 1402), (313, 1437), (455, 1437), (540, 1402), (596, 1328)):
    round_table(*pt, 12)
path_table(arc_pts(300, 680, 150, 195, 264), 23); path_table(arc_pts(470, 680, 150, 345, 276), 23)
path_table(arc_pts(345, 865, 70, 270, 180)+[(275, 985)], 30); path_table(arc_pts(425, 865, 70, 270, 360)+[(495, 985)], 30)
path_table([(275, 1145)]+arc_pts(345, 1260, 70, 180, 90), 30); path_table([(495, 1145)]+arc_pts(425, 1260, 70, 0, 90), 30)
rect_table(385, 1080, 12.1, 1.2, 'z', 24, 2)
for pt in ((170, 900), (170, 975), (170, 1150), (170, 1225), (598, 900), (598, 975), (598, 1150), (598, 1225)): rect_table(*pt, 2.4, 1.2, 'x', 5, 2)
rect_table(215, 1060, 5.0, 1.2, 'x', 12, 2); rect_table(555, 1060, 5.0, 1.2, 'x', 11, 1)
for pt in ((140, 1445), (140, 1530), (237, 1530), (530, 1530), (625, 1530), (625, 1445)): square_table(*pt, 1.6, 3)
for x in (125, 205, 285, 483, 563, 643): rect_table(x, 1675, 3.9, 1.2, 'z', 8, 0)
for pt in ((768, 535), (866, 535), (963, 535), (797, 782), (922, 782)): rect_table(*pt, 2.4, 1.2, 'z', 5, 0)
for pt in ((807, 658), (918, 658)): round_table(*pt, 10)
round_table(962, 305, 4, .35, 'low', False); round_table(962, 365, 4, .35, 'low', False)

for (x, y, a) in chairs: place('chair', CHAIR, (x, y, 0), a)
for (x, y, a) in settings: place('setting', SETTING, (x, y, .76), a)
for kind, x, y, a in pieces:
    if kind == 'tall':
        place('cp_tall', CP_TALL, (x, y, .76), a); tall_spots.append((x, y))
        light('POINT', (x, y, .76+.66), 6, (1., .6, .3), .05)
    else:
        place('cp_low', CP_LOW, (x, y, .76), a); light('POINT', (x, y, .76+.2), 1.5, (1., .6, .3), .04)
for (x, y, z) in urn_spots: place('urn', URN, (x, y, z), random.random()*6)
for x in (scx-1.9, scx+1.9): place('urn', URN, (x, sy1+.5, .8), 0, .9)
for pts in niche_pts: place('flower_wall', flower_wall(pts, by), (0, 0, 0))

# chandeliers
grand = W(384, 415)
chand += [(grand[0], grand[1], 1.9), (grand[0]-3.8, grand[1], 1.25), (grand[0]+3.8, grand[1], 1.25)]
for pt in ((385, 920), (385, 1080), (385, 1240), (215, 1060), (555, 1060), (205, 1675), (563, 1675), (188, 1488), (580, 1488), (862, 330), (385, 1640)):
    chand.append((*W(*pt), 1.1))
chand_objs = []
for (x, y, s) in chand:
    z = H-1.25*s-.25
    fo = place('chandelier', CH_F, (x, y, z), 0, s); co = place('crystals', CH_C, (x, y, z), 0, s)
    co.visible_shadow = False
    b = Builder(['gold']); b.tube([(0, 0, .9*s), (0, 0, H-z)], .012*s, 'gold', 6)
    cho = place('chain', b.mesh('chain'), (x, y, z))
    chand_objs += [fo, co, cho]
    light('POINT', (x, y, z+.1*s), 120*s*s, (1., .66, .38), .55*s)
# sconces + their light
for (p, nrm, d) in sconces:
    rz = math.atan2(nrm.y, nrm.x)-math.pi/2
    place('sconce', SCONCE, p, rz)
    light('POINT', p+nrm*.16+Vector((0, 0, .14)), 14, (1., .68, .4), .06)
# amber uplights grazing the pilasters
for (p, nrm) in pilaster_spots:
    light('SPOT', p, 110, (1., .5, .18), .05, direction=(-nrm.x*.18, -nrm.y*.18, 1), spot=26, blend=.6)
# pin spots on every tall centerpiece, soft wash on the long tables, stage wash
for (x, y) in tall_spots: light('SPOT', (x+.4, y+.4, H-.35), 170, (1., .82, .62), .03, direction=(-.4, -.4, -(H-.35-1.6)), spot=12, blend=.5)
for kind, x, y, a in pieces:
    if kind == 'low': light('SPOT', (x, y, H-.35), 70, (1., .82, .62), .03, direction=(0, 0, -1), spot=18, blend=.6)
for k in (-3, 0, 3): light('SPOT', (scx+k, sy1+-6, H-.4), 320, (1., .8, .58), .1, direction=(-k*.1, 6, -(H-.4-1.6)), spot=35, blend=.5)
light('AREA', (scx, by-2.0, 4.6), 150, (1., .78, .5), 5, direction=(0, 1, -.5))   # wash on the backdrop

# ------------------------------------------------------------------ world, render settings
world = bpy.data.worlds.new('night'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (.002, .002, .002, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1
r = scene.render; c = scene.cycles
r.engine = 'CYCLES'; c.device = 'CPU'; r.threads_mode = 'AUTO'
c.samples = 128; c.use_adaptive_sampling = True; c.adaptive_threshold = .03
c.use_denoising = True; c.denoiser = 'OPENIMAGEDENOISE'
c.max_bounces = 8; c.diffuse_bounces = 3; c.glossy_bounces = 3; c.transmission_bounces = 8; c.transparent_max_bounces = 8
c.caustics_reflective = False; c.caustics_refractive = False; c.blur_glossy = 1.0
c.sample_clamp_indirect = 6.0; c.use_light_tree = True
r.use_persistent_data = True
scene.view_settings.view_transform = 'AgX'
try: scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception as e: print('look', e)
scene.view_settings.exposure = 0.0
r.image_settings.file_format = 'PNG'

# tag groups for per-shot visibility
for o in [ceiling_obj]: o['group'] = 'ceiling'
for o in chand_objs: o['group'] = 'chandelier'
cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera')); COL.objects.link(cam); scene.camera = cam
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT, 'objects', len(bpy.data.objects), 'lights', len([o for o in bpy.data.objects if o.type == 'LIGHT']))
