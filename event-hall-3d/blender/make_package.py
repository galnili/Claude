# Turns hall.blend into the hand-off file: named cameras, an animated tour camera, EEVEE settings,
# the control panel embedded (auto-registers on open), viewport set up. Usage: python make_package.py in.blend panel.py out.blend
import bpy, sys, math
from mathutils import Vector
src, panel_path, out = sys.argv[1:4]
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene; COL = sc.collection

def look(obj, pos, tgt):
    obj.location = pos; obj.rotation_euler = (Vector(tgt)-Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
def camera(name, pos, tgt, lens=None, shift=0., angle_y=None, focus=None, fstop=0):
    cd = bpy.data.cameras.new(name); o = bpy.data.objects.new(name, cd); COL.objects.link(o)
    cd.sensor_width = 36; cd.clip_start = .05; cd.clip_end = 300; cd.shift_y = shift
    if lens: cd.lens = lens
    if angle_y: cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(angle_y)
    if focus: cd.dof.use_dof = True; cd.dof.focus_distance = (Vector(focus)-Vector(pos)).length; cd.dof.aperture_fstop = fstop
    look(o, pos, tgt); return o

camera('CAM_Entrance', (0, -25.6, 1.6), (0, 10, 1.6), 18, .03)
camera('CAM_Table', (.35, 7.55, 1.45), (-2.35, 10.42, 1.25), 38, 0, focus=(-2.35, 10.42, 1.3), fstop=3.2)
camera('CAM_DanceFloor', (5.6, 12.6, 2.4), (-.6, 22.0, 1.0), 22)
camera('CAM_LongTable', (-2.05, -6.5, 1.55), (.2, 6, 1.1), 28, .05)
camera('CAM_SideHall', (10.9, 5.2, 1.7), (17.5, 14.5, 1.5), 22, .06)
camera('CAM_Overview', (23, -39, 33), (1.2, -2.2, 0), angle_y=45)
old = bpy.data.objects.get('Camera')
if old: bpy.data.objects.remove(old)

# tour: eye-level walk along the aisles, 30 s at 30 fps
tour = camera('CAM_Tour', (0, -26.5, 1.7), (0, 0, 1.7), 22)
tgt = bpy.data.objects.new('CAM_Tour_target', None); COL.objects.link(tgt); tgt.empty_display_size = .3
con = tour.constraints.new('TRACK_TO'); con.target = tgt; con.track_axis = 'TRACK_NEGATIVE_Z'; con.up_axis = 'UP_Y'
KEYS = [  # seconds, camera, look-at
    (0,  (0, -26.5, 1.7), (0, 0, 1.8)),
    (5,  (0, -19.0, 1.7), (0, -5, 1.6)),
    (9,  (-1.9, -10.0, 1.75), (-.5, 2, 1.3)),
    (13, (-1.9, 1.5, 1.75), (0, 12, 1.5)),
    (17, (0, 10.5, 1.8), (0, 24, 1.5)),
    (21, (0, 15.8, 1.9), (0, 26, 1.9)),
    (25, (3.5, 17.5, 1.85), (14, 12, 1.4)),
    (30, (9.8, 9.5, 1.9), (17, 14, 1.3)),
]
for t, p, l in KEYS:
    f = 1+round(t*30)
    tour.location = p; tour.keyframe_insert('location', frame=f)
    tgt.location = l; tgt.keyframe_insert('location', frame=f)
for ob in (tour, tgt):
    for fc in ob.animation_data.action.fcurves if hasattr(ob.animation_data.action, 'fcurves') else []:
        for k in fc.keyframe_points: k.interpolation = 'BEZIER'; k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
sc.frame_start, sc.frame_end, sc.render.fps = 1, 900, 30

# EEVEE (fast mode) settings, ready for the switch
for attr, val in (('use_raytracing', True), ('use_shadows', True), ('shadow_ray_count', 2), ('shadow_step_count', 8),
                  ('use_fast_gi', True), ('taa_render_samples', 64), ('taa_samples', 16), ('use_volumetric_shadows', False)):
    try: setattr(sc.eevee, attr, val)
    except Exception as e: print('eevee', attr, e)
try: sc.eevee.ray_tracing_options.resolution_scale = '2'
except Exception as e: print('eevee rt', e)
# Cycles defaults tuned for a laptop GPU
sc.cycles.samples = 128; sc.cycles.preview_samples = 32; sc.cycles.use_preview_denoising = True
sc.render.engine = 'BLENDER_EEVEE'
sc.camera = bpy.data.objects['CAM_Entrance']
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.filepath = '//Renders/'

# embed and register the panel
txt = bpy.data.texts.new('hall_panel.py'); txt.from_string(open(panel_path).read()); txt.use_module = True
ns = {'__name__': 'hall_panel'}; exec(compile(txt.as_string(), 'hall_panel.py', 'exec'), ns); ns['register']()

# viewport: camera view, material preview, sidebar open on the Hall tab
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            sp = area.spaces.active; sp.shading.type = 'MATERIAL'; sp.show_region_ui = True
            sp.region_3d.view_perspective = 'CAMERA'; sp.clip_end = 400
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print('packaged', out)
