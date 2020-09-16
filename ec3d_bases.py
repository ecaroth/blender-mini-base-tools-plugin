bl_info = {
    "name": "EC3D Base Tools",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "3D View > Sidebar",
    "category": "Object"
}

import bpy, bmesh, math, os, mathutils
from bpy_extras.io_utils import ExportHelper

BOTTOM_TOLERANCE = 0.05
BOTTOM_MERGE_VERTS_DISTANCE = .01

BASE_BEVEL_DEPTH = .7
SIMPLE_BEVEL_SHRINK_DISTANCE = .5

BOTTOM_TRIM_VALUE_SHORT = .05
BOTTOM_TRIM_VALUE_TALL = .1

# ------- UI --------
class VIEW3D_PT_EC3D_Bases_Tools_Panel(bpy.types.Panel):
    bl_label = "EC3D Base Tools"
    bl_category = "Bases"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'OBJECT', 'EDIT'}

    def draw(self, context):
        layout = self.layout

        layout.label(text="RESIN BASE TOOLS")
        col1 = layout.column(align=True)
        col1.operator("ec3d_bases.bevel_simple", text="Simple Bevel", icon='MOD_BEVEL')
        col1.operator("ec3d_bases.bevel_simple_additive", text="Simple Bevel (Additive)", icon='MOD_BEVEL')
        col1.operator("ec3d_bases.bevel_fancy_small", text="Channeled Bevel (1 inch)", icon='OUTLINER_OB_MESH')
        col1.operator("ec3d_bases.bevel_fancy_small_additive", text="Channeled Bevel (1 inch, Additive)", icon='OUTLINER_OB_MESH')
        col1.operator("ec3d_bases.bevel_fancy_large", text="Channeled Bevel (2+ inch)", icon='OUTLINER_OB_MESH')
        col1.operator("ec3d_bases.bevel_fancy_large_additive", text="Channeled Bevel (2+ inch, Additive)", icon='OUTLINER_OB_MESH')
        layout.label(text="GENERAL")
        col2 = layout.column(align=True)
        #col2.operator("ec3d_bases.fix_bottom", text="Fix bottom", icon='TRIA_DOWN_BAR')
        col2.operator("ec3d_bases.trim_bottom_small", text="Trim bottom (small)", icon='TRIA_DOWN_BAR')
        col2.operator("ec3d_bases.trim_bottom_large", text="Trim bottom (large)", icon='TRIA_DOWN_BAR')
        col3 = layout.column(align=True)
        col3.operator("ec3d_bases.export_to_stl", text="STL Export", icon='FILE_NEW')

        export_folder = context.scene.ec3d.export_path
        if export_folder != "//":
            # truncate to last 3 dirs
            dirs = export_folder.split(os.sep)
            shorter = os.sep.join(dirs[-3:])
            layout.label(text="> " + shorter)

            col3.operator("ec3d.export_repeat", text="Repeat Export", icon='RECOVER_LAST')

# ------- HELPER FUNCTIONS -----
def bottomZ(obj):
    bottom_z = 10000
    for v in obj.data.vertices:
        z = gco(obj, v.co)[2]
        if z < bottom_z:
            bottom_z = z

    return bottom_z

def topZ(obj):
    top_z = -10000
    for v in obj.data.vertices:
        z = v.co[2]
        if z > top_z:
            top_z = z

    return top_z

# get global coordss
def gco(obj, co):
    return obj.matrix_world @ co

def fixBottom(obj, remove_depth=None):
    # make sure scale and rotation are applied or numbers won't work right
    bpy.ops.object.transform_apply(rotation=True, scale=True)

    bottom_z = bottomZ(obj)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    modified = 0

    if remove_depth:
        bottom_z = bottom_z + remove_depth
        # move all verts below the remove depth UP to that depth
        for v in bm.verts:
            if v.co[2] < bottom_z:
                v.co[2] = bottom_z

    # Fix any close tolerance verts to bottom Z
    bottom_verts = []
    bottom_edges = []
    for v in bm.verts:
        if (bottom_z + BOTTOM_TOLERANCE) > v.co[2] and bottom_z != v.co[2]:
            modified += 1
            v.co[2] = bottom_z

    # select all verts and do merge by distance, then reslect only bottom verts that are left
    bmesh.ops.remove_doubles(bm, verts=bottom_verts, dist=BOTTOM_MERGE_VERTS_DISTANCE)
    for v in bm.verts:
        if v.co[2] == bottom_z:
            bottom_verts.append(v)


    # now select all edges and perform limited dissolve
    for edge in bm.edges:
        if edge.verts[0].co[2] == bottom_z and edge.verts[1].co[2] == bottom_z:
            bottom_verts.append(edge.verts[0])
            bottom_verts.append(edge.verts[1])
            bottom_edges.append(edge)

    # Then limited dissolve bottom
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1), verts=list(set(bottom_verts)), edges=list(set(bottom_edges)))

    bm.to_mesh(obj.data)
    obj.data.update()

    return modified

def exportToFolder(context, filepath, add_folder=None):
    # Path comes in with /path/blah/whatever.stl or as just a dir

    save_to = filepath
    if filepath.endswith(".stl"):
        save_to = os.path.dirname(filepath)

    if add_folder:
        save_to = os.path.join(save_to, add_folder)

    if not os.path.isdir(save_to):
        os.makedirs(save_to)

    context.scene.ec3d.export_path = save_to
    print("NEW LOCATION = " + save_to)

    orig_selection = context.selected_objects
    for obj in orig_selection:
        bpy.ops.object.select_all(action='DESELECT')

        fname = obj.name
        fpath = os.path.join(save_to, fname + ".stl")

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        bpy.ops.export_mesh.stl(filepath=fpath, check_existing=False, use_selection=True)

    # reselect
    for obj in orig_selection:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

    return len(orig_selection)

def duplicate(context, name_append=None):
    orig_name = context.object.name
    bpy.ops.object.duplicate(linked=False)
    new_obj = context.object
    # set origin to center of geometry
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
    # rename it appropriately
    if name_append:
        new_obj.name = orig_name+" ["+name_append+"]"

    # move it X to the width of the obj
    width = new_obj.dimensions[0]
    new_obj.location.x = new_obj.location.x-width

    return new_obj

def scaleCubeToChanne(obj):
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.transform.resize(value=(1.0, 100, .8))

    top_z = topZ(obj)
    selected = []
    for v in obj.data.vertices:
        if v.co[2] == top_z:
            v.select = True
            selected.append(v)
        else:
            v.select = False

    bpy.ops.object.mode_set(mode='EDIT')
    # now that all verts are selected scale 50% on X axis
    bpy.ops.transform.resize(value=(.04, 1.0, 1.0))
    bpy.ops.object.mode_set(mode='OBJECT')


def selectBottomVerts(context, obj):
    #NOTE this operation assumes fix_bottom has been run, so if not you might miss many vertices
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    bottom_z = bottomZ(obj)

    selected = []
    for v in obj.data.vertices:
        if v.co[2] == bottom_z:
            v.select = True
            selected.append(v)
        else:
            v.select = False

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type="VERT")
    context.view_layer.objects.active = context.view_layer.objects.active
    return selected

def basicBevel(context, additive=False):
    bpy.ops.object.mode_set(mode='OBJECT')
    obj = duplicate(context, 'simple_base_bevel')
    fixBottom(obj, remove_depth=None if additive else BASE_BEVEL_DEPTH)

    # select bottom verts, then put 3D cursor to center of selected
    selectBottomVerts(context, obj)
    # now extrude down the right distance
    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0.0, 0.0, 0 - BASE_BEVEL_DEPTH)})
    obj.data.update()

    selected_verts = [v for v in obj.data.vertices if v.select]
    coords = []
    for vert in selected_verts:
        coords.append([vert.co[0], vert.co[1]])

    x_coordinates, y_coordinates = zip(*coords)
    bounding_box = [(min(x_coordinates), min(y_coordinates)), (max(x_coordinates), max(y_coordinates))]

    # rudimentary, we're just gonna find the width of the bounding box, an scale down till its roughly th size
    # we want based on SIMPLE_BEVEL_SHRINK_DISTANCE
    width = abs(bounding_box[1][0] - bounding_box[0][0])
    target_width = width - (SIMPLE_BEVEL_SHRINK_DISTANCE * 2)
    scale = target_width / width

    bpy.ops.transform.resize(value=(scale, scale, 1.0))
    obj.data.update()

    # now snap cursor to bottom center
    bpy.ops.view3d.snap_cursor_to_selected()
    bpy.ops.object.mode_set(mode='OBJECT')

    return obj

def channelCutout(context, obj, is_large=False):
    # we know cursor is at the center bottom due to previous op (fixBottom)
    cursor = bpy.context.scene.cursor.location

    # Create center sphere
    bpy.ops.mesh.primitive_uv_sphere_add(segments=50, ring_count=25, radius=3.5,
                                         location=(cursor[0], cursor[1], cursor[2] - 2))
    sphere = bpy.context.active_object
    sphere.name = "_basetemp_center"

    # Create first cube (cutout)
    bpy.ops.mesh.primitive_cube_add(size=2.2, location=(cursor[0], cursor[1], cursor[2] + .5))
    cube1 = bpy.context.active_object
    cube1.name = "_basetemp_cube1"
    scaleCubeToChanne(cube1)
    bpy.ops.object.origin_set(type='GEOMETRY_ORIGIN')
    # Duplicate cube and rotate 90 degrees
    bpy.ops.object.duplicate(linked=False)
    cube2 = bpy.context.active_object
    cube2.name = "_basetemp_cube2"
    bpy.ops.transform.rotate(value=math.radians(90), orient_axis='Z', orient_type='GLOBAL')
    if is_large:
        bpy.ops.object.duplicate(linked=False)
        cube3 = bpy.context.active_object
        cube3.name = "_basetemp_cube3"
        bpy.ops.transform.translate(value=(0.0,0.0,.01))
        bpy.ops.transform.rotate(value=math.radians(45), orient_axis='Z', orient_type='GLOBAL')
        bpy.ops.object.duplicate(linked=False)
        cube4 = bpy.context.active_object
        cube4.name = "_basetemp_cube4"
        bpy.ops.transform.rotate(value=math.radians(90), orient_axis='Z', orient_type='GLOBAL')

    # Create 3rd cube to cut top flat where we want it
    cube_size = 200
    bpy.ops.mesh.primitive_cube_add(size=cube_size, location=(cursor[0], cursor[1], cursor[2] + (cube_size/2) + BASE_BEVEL_DEPTH - .01))
    cut_cube = bpy.context.active_object
    cut_cube.name = "_basetemp_cutcube"

    # Now create all modifiers
    cube_1_add_mod = "_basetemp_mod1"
    bool_add1 = sphere.modifiers.new(type="BOOLEAN", name=cube_1_add_mod)
    bool_add1.object = cube1
    bool_add1.operation = 'UNION'
    cube_2_add_mod = "_basetemp_mod2"
    bool_add1 = sphere.modifiers.new(type="BOOLEAN", name=cube_2_add_mod)
    bool_add1.object = cube2
    bool_add1.operation = 'UNION'
    if is_large:
        cube_3_add_mod = "_basetemp_mod2"
        bool_add1 = sphere.modifiers.new(type="BOOLEAN", name=cube_3_add_mod)
        bool_add1.object = cube3
        bool_add1.operation = 'UNION'
        cube_4_add_mod = "_basetemp_mod2"
        bool_add1 = sphere.modifiers.new(type="BOOLEAN", name=cube_4_add_mod)
        bool_add1.object = cube4
        bool_add1.operation = 'UNION'

    cut_cube_cut_mod = "_basetemp_mod3"
    bool_cut1 = sphere.modifiers.new(type="BOOLEAN", name=cut_cube_cut_mod)
    bool_cut1.object = cut_cube
    bool_cut1.operation = 'DIFFERENCE'
    obj_cut_mod = "_basetemp_mod4"
    bool_cut2 = obj.modifiers.new(type="BOOLEAN", name=obj_cut_mod)
    bool_cut2.object = sphere
    bool_cut1.operation = 'DIFFERENCE'

    # Now apply modifier for final channel cut obj to base
    context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=obj_cut_mod)

    # Finally delete all the temp objects
    obj.select_set(False)
    sphere.select_set(True)
    cube1.select_set(True)
    cube2.select_set(True)
    if is_large:
        cube3.select_set(True)
        cube4.select_set(True)
    cut_cube.select_set(True)
    bpy.ops.object.delete()
    obj.select_set(True)
    context.view_layer.objects.active = obj

def trimBottom(context, obj, remove):
    bottom_z = bottomZ(obj)
    print("BOTTOM Z IS "+str(bottom_z))

    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY")
    bpy.ops.view3d.snap_cursor_to_active()
    cursor = bpy.context.scene.cursor.location

    # Create cube to cut bottom flat with
    cube_size = 200
    bpy.ops.mesh.primitive_cube_add(size=cube_size, location=(
        cursor[0], cursor[1], bottom_z - (cube_size/2) + remove ))
    cut_cube = bpy.context.active_object
    cut_cube.name = "_basetemp_cutcube"

    # add modifier
    obj_cut_mod = "_basetemp_trimmod"
    bool_cut1 = obj.modifiers.new(type="BOOLEAN", name=obj_cut_mod)
    bool_cut1.object = cut_cube
    bool_cut1.operation = 'DIFFERENCE'

    context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=obj_cut_mod)

    # Finally delete all the temp objects
    obj.select_set(False)
    cut_cube.select_set(True)
    bpy.ops.object.delete()
    obj.select_set(True)
    context.view_layer.objects.active = obj



# ------- OPERATORS ------

class OP_ExportRepeat(bpy.types.Operator):
    bl_idname = "ec3d_bases.export_repeat"
    bl_label = "Export Again"
    bl_description = "Repeat export to last destination"
    bl_options = {'REGISTER'}

    def execute(self, context):
        cnt = exportToFolder(context, context.scene.ec3d.export_path)
        self.report({"INFO"}, "%s files exported!" % cnt)
        return {'FINISHED'}

class OP_ExportToSTL(bpy.types.Operator, ExportHelper):
    bl_idname = "ec3d_bases.export_to_stl"
    bl_label = "Export Here"
    bl_description = "Export selected object to STL file"
    bl_options = {'REGISTER'}
    filename_ext = ".stl"

    filter_glob: bpy.props.StringProperty(
        default="*.stl",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        cnt = exportToFolder(context, self.filepath)
        self.report({"INFO"}, "%s files exported!" % cnt)
        return {'FINISHED'}

class OP_FixBottom(bpy.types.Operator):
    bl_idname = "ec3d_bases.fix_bottom"
    bl_label = "Fix bottom variance"
    bl_description = "Attempt to fix/cleanup the flat bottom of a model"
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}

        bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.view_layer.objects.active
        updated = fixBottom(obj)

        self.report({"INFO"}, 'Bottom fixed, updated %s verts' % updated )
        return {'FINISHED'}

class OP_TrimBottomSmall(bpy.types.Operator):
    bl_idname = "ec3d_bases.trim_bottom_small"
    bl_label = "Trim Bottom (small)"
    bl_description = "Trim the bottom of model, a little, to try and make it completely flat"
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}


        bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.view_layer.objects.active

        trimBottom(context, obj, BOTTOM_TRIM_VALUE_SHORT)

        self.report({"INFO"}, 'Bottom trimmed' )
        return {'FINISHED'}

class OP_TrimBottomLarge(bpy.types.Operator):
    bl_idname = "ec3d_bases.trim_bottom_large"
    bl_label = "Trim Bottom (large)"
    bl_description = "Trim the bottom of model, a lot, to try and make it completely flat"
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}


        bpy.ops.object.mode_set(mode='OBJECT')
        obj = context.view_layer.objects.active

        trimBottom(context, obj, BOTTOM_TRIM_VALUE_TALL)

        self.report({"INFO"}, 'Bottom trimmed' )
        return {'FINISHED'}

class OP_SimpleBevel(bpy.types.Operator):
    bl_idname = "ec3d_bases.bevel_simple"
    bl_label = "Simple bevel"
    bl_description = "Apply a simple bevel to the bottom of the model, without adding any height"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}

        obj = basicBevel(context)

        self.report({"INFO"}, 'Simple base bevel added, new model added as ' + obj.name)
        return {'FINISHED'}

class OP_SimpleBevelAdditive(bpy.types.Operator):
    bl_idname = "ec3d_bases.bevel_simple_additive"
    bl_label = "Simple bevel"
    bl_description = "Apply a simple bevel to the bottom of the model, adding to the base height slightly"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}

        obj = basicBevel(context, additive=True)

        self.report({"INFO"}, 'Simple base bevel added, new model added as ' + obj.name)
        return {'FINISHED'}

class OP_SmallFancyBevel(bpy.types.Operator):
    bl_idname = "ec3d_bases.bevel_fancy_small"
    bl_label = "Cutout bevel (1 inch)"
    bl_description = "Apply bevel and channel cutouts to the bottom of the model, not altering model height"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}

        obj = basicBevel(context)

        channelCutout(context, obj)

        self.report({"INFO"}, 'Small channel cutout base bevel added, new model added as ' + obj.name)
        return {'FINISHED'}

class OP_SmallFancyBevelAdditive(bpy.types.Operator):
    bl_idname = "ec3d_bases.bevel_fancy_small_additive"
    bl_label = "Cutout bevel (1 inch, Additive)"
    bl_description = "Apply bevel and channel cutouts to the bottom of the model, adding height slightly"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}

        obj = basicBevel(context, additive=True)

        channelCutout(context, obj, is_large=False)

        self.report({"INFO"}, 'Small channel cutout base bevel added, new model added as ' + obj.name)
        return {'FINISHED'}

class OP_LargeFancyBevel(bpy.types.Operator):
    bl_idname = "ec3d_bases.bevel_fancy_large"
    bl_label = "Cutout bevel (2+ inch)"
    bl_description = "Apply bevel and channel cutouts to the bottom of the model, keeping height the same"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}

        obj = basicBevel(context)

        channelCutout(context, obj, is_large=True)

        self.report({"INFO"}, 'Large channel cutout base bevel added, new model added as ' + obj.name)
        return {'FINISHED'}

class OP_LargeFancyBevelAdditive(bpy.types.Operator):
    bl_idname = "ec3d_bases.bevel_fancy_large_additive"
    bl_label = "Cutout bevel (2+ inch)"
    bl_description = "Apply bevel and channel cutouts to the bottom of the model, adding height to the model"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if len(context.selected_objects) != 1:
            self.report({"WARNING"}, "No object selected")
            return {"CANCELLED"}

        obj = basicBevel(context, additive=True)

        channelCutout(context, obj, is_large=True)

        self.report({"INFO"}, 'Large channel cutout base bevel added, new model added as ' + obj.name)
        return {'FINISHED'}

class SceneProperties(bpy.types.PropertyGroup):
    export_path: bpy.props.StringProperty(
        name="Export Directory",
        description="Path to directory where the files are created",
        default="//",
        maxlen=1024,
        subtype="DIR_PATH",
    )

classes = (
    VIEW3D_PT_EC3D_Bases_Tools_Panel,
    OP_FixBottom,
    OP_ExportToSTL,
    OP_ExportRepeat,
    OP_SimpleBevel,
    OP_SimpleBevelAdditive,
    OP_LargeFancyBevel,
    OP_LargeFancyBevelAdditive,
    OP_SmallFancyBevel,
    OP_SmallFancyBevelAdditive,
    OP_TrimBottomSmall,
    OP_TrimBottomLarge,
    SceneProperties
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.ec3d = bpy.props.PointerProperty(type=SceneProperties)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()