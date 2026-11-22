bl_info = {
    "name": "Event Hall Controls",
    "description": "One-click views, design colors, lighting and export for the event hall scene",
    "blender": (4, 2, 0),
    "category": "3D View",
    "location": "3D Viewport > Sidebar (N) > Hall",
}
# Control panel for the event hall scene. Lives in the .blend as a registered text block,
# and also installs as a regular add-on. Everything it does can be undone with Ctrl+Z or by reopening the file.
import bpy, math, os, time
from bpy.props import FloatVectorProperty, FloatProperty, EnumProperty, BoolProperty

VIEWS = [  # (camera object, button label)
    ("CAM_Entrance", "Entrance"), ("CAM_Table", "Table close-up"), ("CAM_DanceFloor", "Dance floor & stage"),
    ("CAM_LongTable", "Long table"), ("CAM_SideHall", "Side hall"), ("CAM_Overview", "Overview (cutaway)"),
]
METALS = {
    "GOLD": (.83, .60, .30), "CHAMPAGNE": (.86, .73, .52), "ROSE": (.86, .56, .46), "SILVER": (.80, .80, .80),
}
THEMES = {  # flowers main, flowers accent, cloth, cushion, metal
    "CLASSIC": ((.86, .84, .80), (.84, .66, .62), (.82, .79, .74), (.80, .76, .70), "GOLD"),
    "BLUSH":   ((.88, .70, .68), (.80, .48, .50), (.86, .78, .74), (.84, .72, .68), "ROSE"),
    "IVORY":   ((.88, .84, .74), (.80, .74, .60), (.84, .80, .70), (.82, .78, .68), "CHAMPAGNE"),
    "SILVER":  ((.88, .88, .88), (.70, .74, .82), (.86, .86, .86), (.78, .78, .80), "SILVER"),
}

def base_color(mat_name, rgb):
    m = bpy.data.materials.get(mat_name)
    if not m or not m.node_tree: return
    p = m.node_tree.nodes.get("Principled BSDF")
    if p: p.inputs["Base Color"].default_value = (*rgb, 1)

def upd_flowers(self, ctx):
    base_color("rose_white", self.hall_flowers)
    base_color("rose_ivory", tuple(min(1, c*1.02) for c in self.hall_flowers))
def upd_accent(self, ctx): base_color("rose_blush", self.hall_accent)
def upd_cloth(self, ctx): base_color("linen", self.hall_cloth)
def upd_cushion(self, ctx): base_color("cushion", self.hall_cushion)
def upd_metal(self, ctx):
    for n in ("gold_leaf", "gold_satin"): base_color(n, METALS[self.hall_metal])
def upd_lights(self, ctx):
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            if "base_energy" not in o: o["base_energy"] = o.data.energy
            o.data.energy = o["base_energy"]*self.hall_light
def upd_mood(self, ctx):
    ctx.scene.view_settings.exposure = self.hall_mood

def view3d_areas(ctx):
    for area in ctx.screen.areas:
        if area.type == "VIEW_3D": yield area

class HALL_OT_view(bpy.types.Operator):
    bl_idname = "hall.view"; bl_label = "Go to view"; bl_description = "Look through this camera"
    cam: bpy.props.StringProperty()
    def execute(self, ctx):
        cam = bpy.data.objects.get(self.cam)
        if not cam: self.report({"ERROR"}, "Camera not found: " + self.cam); return {"CANCELLED"}
        ctx.scene.camera = cam
        cutaway = self.cam == "CAM_Overview"
        for o in bpy.data.objects:
            if o.get("group") in ("ceiling", "chandelier"): o.visible_camera = not cutaway
        for area in view3d_areas(ctx): area.spaces.active.region_3d.view_perspective = "CAMERA"
        return {"FINISHED"}

class HALL_OT_walk(bpy.types.Operator):
    bl_idname = "hall.walk"; bl_label = "Walk around"
    bl_description = "Walk freely at eye height: W/A/S/D to move, mouse to look, E/Q up/down, click to stop"
    def execute(self, ctx):
        cam = ctx.scene.camera or bpy.data.objects.get("CAM_Entrance")
        for area in view3d_areas(ctx):
            r3d = area.spaces.active.region_3d
            r3d.view_perspective = "PERSP"
            r3d.view_matrix = cam.matrix_world.inverted()
            area.spaces.active.lens = 24
            with ctx.temp_override(area=area, region=[r for r in area.regions if r.type == "WINDOW"][0]):
                bpy.ops.view3d.walk("INVOKE_DEFAULT")
            break
        return {"FINISHED"}

class HALL_OT_quality(bpy.types.Operator):
    bl_idname = "hall.quality"; bl_label = "Quality"
    mode: EnumProperty(items=[("FAST", "Fast", ""), ("REAL", "Realistic", ""), ("EDIT", "Light preview", "")])
    @classmethod
    def description(cls, ctx, props):
        return {"FAST": "Live, game-like view (EEVEE). Best for walking around and for videos",
                "REAL": "Full realism (Cycles on the GPU). Slower; use for final images",
                "EDIT": "Lightweight view without lighting. Use when the laptop gets hot"}[props.mode]
    def execute(self, ctx):
        sc = ctx.scene
        if self.mode == "REAL":
            sc.render.engine = "CYCLES"
            try:
                prefs = ctx.preferences.addons["cycles"].preferences
                for t in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
                    try: prefs.compute_device_type = t; break
                    except TypeError: continue
                prefs.get_devices()
                for d in prefs.devices: d.use = True
                sc.cycles.device = "GPU"
            except Exception as e: self.report({"WARNING"}, "GPU not available, using CPU: %s" % e)
        elif self.mode == "FAST":
            sc.render.engine = "BLENDER_EEVEE"
        for area in view3d_areas(ctx):
            area.spaces.active.shading.type = "MATERIAL" if self.mode == "EDIT" else "RENDERED"
        return {"FINISHED"}

class HALL_OT_theme(bpy.types.Operator):
    bl_idname = "hall.theme"; bl_label = "Theme"; bl_description = "Apply a ready-made color combination"
    theme: bpy.props.StringProperty()
    def execute(self, ctx):
        f, a, c, cu, m = THEMES[self.theme]; sc = ctx.scene
        sc.hall_flowers, sc.hall_accent, sc.hall_cloth, sc.hall_cushion, sc.hall_metal = f, a, c, cu, m
        return {"FINISHED"}

def out_dir(sub):
    base = bpy.path.abspath("//") or os.path.expanduser("~/Desktop")
    d = os.path.join(base, sub); os.makedirs(d, exist_ok=True); return d

class HALL_OT_image(bpy.types.Operator):
    bl_idname = "hall.image"; bl_label = "Render image"
    bl_description = "Render the current view and save it next to the .blend file, in the Renders folder"
    def execute(self, ctx):
        sc = ctx.scene; r = sc.render
        if sc.camera and sc.camera.name == "CAM_Tour": sc.camera = bpy.data.objects.get("CAM_Entrance")
        r.resolution_x, r.resolution_y = (1080, 1920) if sc.hall_vertical else (1920, 1080)
        r.resolution_percentage = 100
        set_still_format(r)
        name = (sc.camera.name if sc.camera else "view").replace("CAM_", "")
        r.filepath = os.path.join(out_dir("Renders"), "%s_%s.png" % (name, time.strftime("%Y%m%d-%H%M%S")))
        bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)
        return {"FINISHED"}

def set_still_format(r):
    try: r.image_settings.media_type = "IMAGE"
    except Exception: pass
    r.image_settings.file_format = "PNG"

class HALL_OT_video(bpy.types.Operator):
    bl_idname = "hall.video"; bl_label = "Render tour video"
    bl_description = "Render the camera tour as an MP4 into the Video folder next to the .blend file. Use Fast quality first"
    def execute(self, ctx):
        sc = ctx.scene; r = sc.render
        tour = bpy.data.objects.get("CAM_Tour")
        if not tour: self.report({"ERROR"}, "Tour camera missing"); return {"CANCELLED"}
        sc.camera = tour
        for o in bpy.data.objects:
            if o.get("group") in ("ceiling", "chandelier"): o.visible_camera = True
        r.resolution_x, r.resolution_y = (1080, 1920) if sc.hall_vertical else (1920, 1080)
        r.resolution_percentage = 100 if sc.hall_full_res else 50
        r.fps = 30; sc.frame_start = 1; sc.frame_end = 900
        try: r.image_settings.media_type = "VIDEO"
        except Exception: pass
        r.image_settings.file_format = "FFMPEG"
        r.ffmpeg.format = "MPEG4"; r.ffmpeg.codec = "H264"; r.ffmpeg.constant_rate_factor = "HIGH"
        r.filepath = os.path.join(out_dir("Video"), "hall_tour_%s_" % time.strftime("%Y%m%d-%H%M"))
        for area in view3d_areas(ctx): area.spaces.active.region_3d.view_perspective = "CAMERA"
        bpy.ops.render.render("INVOKE_DEFAULT", animation=True)
        return {"FINISHED"}

class HALL_OT_play(bpy.types.Operator):
    bl_idname = "hall.play"; bl_label = "Preview tour"; bl_description = "Play the camera tour in the viewport (Esc to stop)"
    def execute(self, ctx):
        ctx.scene.camera = bpy.data.objects.get("CAM_Tour"); ctx.scene.frame_set(1)
        for area in view3d_areas(ctx): area.spaces.active.region_3d.view_perspective = "CAMERA"
        bpy.ops.screen.animation_play()
        return {"FINISHED"}

class HALL_PT_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"; bl_region_type = "UI"; bl_category = "Hall"; bl_label = "Event Hall"
    def draw(self, ctx):
        sc = ctx.scene; L = self.layout
        b = L.box(); b.label(text="1. Look", icon="CAMERA_DATA")
        col = b.column(align=True)
        for cam, label in VIEWS: col.operator("hall.view", text=label).cam = cam
        b.operator("hall.walk", icon="MOD_DYNAMICPAINT")
        b = L.box(); b.label(text="2. Quality", icon="SHADING_RENDERED")
        row = b.row(align=True)
        row.operator("hall.quality", text="Fast").mode = "FAST"
        row.operator("hall.quality", text="Realistic").mode = "REAL"
        row.operator("hall.quality", text="Light").mode = "EDIT"
        b.label(text="Now: " + ("Realistic (Cycles)" if sc.render.engine == "CYCLES" else "Fast (EEVEE)"))
        b = L.box(); b.label(text="3. Design", icon="BRUSHES_ALL")
        grid = b.grid_flow(columns=2, align=True)
        for key, label in (("CLASSIC", "White & gold"), ("BLUSH", "Blush"), ("IVORY", "Ivory"), ("SILVER", "Silver")):
            grid.operator("hall.theme", text=label).theme = key
        b.prop(sc, "hall_flowers", text="Flowers"); b.prop(sc, "hall_accent", text="Accent flowers")
        b.prop(sc, "hall_cloth", text="Tablecloths"); b.prop(sc, "hall_cushion", text="Chair cushions")
        b.prop(sc, "hall_metal", text="Metal")
        b = L.box(); b.label(text="4. Light", icon="LIGHT_SUN")
        b.prop(sc, "hall_light", text="Lights", slider=True); b.prop(sc, "hall_mood", text="Brightness", slider=True)
        b = L.box(); b.label(text="5. Export", icon="EXPORT")
        b.prop(sc, "hall_vertical", text="Vertical 9:16 (Instagram)")
        b.operator("hall.image", icon="RENDER_STILL")
        b.operator("hall.play", icon="PLAY")
        b.prop(sc, "hall_full_res", text="Full-size video (slower)")
        b.operator("hall.video", icon="RENDER_ANIMATION")
        b.label(text="Files are saved next to the .blend file")

CLASSES = (HALL_OT_view, HALL_OT_walk, HALL_OT_quality, HALL_OT_theme, HALL_OT_image, HALL_OT_video, HALL_OT_play, HALL_PT_panel)
PROPS = {
    "hall_flowers": FloatVectorProperty(subtype="COLOR", size=3, min=0, max=1, default=(.86, .84, .80), update=upd_flowers),
    "hall_accent": FloatVectorProperty(subtype="COLOR", size=3, min=0, max=1, default=(.84, .66, .62), update=upd_accent),
    "hall_cloth": FloatVectorProperty(subtype="COLOR", size=3, min=0, max=1, default=(.82, .79, .74), update=upd_cloth),
    "hall_cushion": FloatVectorProperty(subtype="COLOR", size=3, min=0, max=1, default=(.80, .76, .70), update=upd_cushion),
    "hall_metal": EnumProperty(items=[("GOLD", "Gold", ""), ("CHAMPAGNE", "Champagne", ""), ("ROSE", "Rose gold", ""), ("SILVER", "Silver", "")], default="GOLD", update=upd_metal),
    "hall_light": FloatProperty(min=.2, max=2.5, default=1., update=upd_lights),
    "hall_mood": FloatProperty(min=-2, max=2, default=0., update=upd_mood),
    "hall_vertical": BoolProperty(default=False),
    "hall_full_res": BoolProperty(default=False),
}

def register():
    for c in CLASSES:
        try: bpy.utils.register_class(c)
        except ValueError: pass
    for k, v in PROPS.items(): setattr(bpy.types.Scene, k, v)

def unregister():
    for c in reversed(CLASSES):
        try: bpy.utils.unregister_class(c)
        except RuntimeError: pass
    for k in PROPS: delattr(bpy.types.Scene, k)

if __name__ == "__main__":
    register()
