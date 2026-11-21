# Usage: python render_shot.py <hall.blend> <shot> <out.png> <width> <height> <samples> [exposure]
import bpy, sys, math, time
from mathutils import Vector
blend, shot, out, w, h, spp = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
expo = float(sys.argv[7]) if len(sys.argv) > 7 else 0.0
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene; cam = sc.camera; cd = cam.data
SHOTS = {
  # name: (camera, target, lens mm, shift_y, dof focus target or None, fstop, hide ceiling/chandeliers)
  'hero':     ((0, -25.6, 1.6), (0, 10, 1.6), 18, .03, None, 0, False),
  'dance':    ((5.6, 12.6, 2.4), (-.6, 22.0, 1.0), 22, 0, None, 0, False),
  'detail':   ((.35, 7.55, 1.45), (-2.35, 10.42, 1.25), 38, 0, (-2.35, 10.42, 1.3), 3.2, False),
  'longtable':((-2.05, -6.5, 1.55), (.2, 6, 1.1), 28, .05, None, 0, False),
  'side':     ((10.9, 5.2, 1.7), (17.5, 14.5, 1.5), 22, .06, None, 0, False),
  'overview': ((23, -39, 33), (1.2, -2.2, 0), None, 0, None, 0, True),
}
pos, tgt, lens, shift, focus, fstop, cutaway = SHOTS[shot]
cam.location = pos
d = Vector(tgt) - Vector(pos)
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cd.sensor_width = 36
if lens: cd.lens = lens
else: cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(45)
cd.shift_y = shift; cd.clip_start = .05; cd.clip_end = 300
cd.dof.use_dof = focus is not None
if focus: cd.dof.focus_distance = (Vector(focus)-Vector(pos)).length; cd.dof.aperture_fstop = fstop
for o in bpy.data.objects:
    if o.get('group') in ('ceiling', 'chandelier'): o.visible_camera = not cutaway
if cutaway:
    sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.012, .011, .010, 1)
r = sc.render; r.resolution_x = w; r.resolution_y = h; r.resolution_percentage = 100
sc.cycles.samples = spp
sc.view_settings.exposure = expo
r.filepath = out
t = time.time(); bpy.ops.render.render(write_still=True); print('RENDER', shot, w, h, spp, '%.0fs' % (time.time()-t))
