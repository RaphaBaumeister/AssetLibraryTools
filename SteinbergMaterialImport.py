bl_info = {
    "name": "Steinberg Material Import",
    "description": "AssetLibraryTools is a free addon which aims to speed up the process of creating asset libraries with the asset browser, This addon is currently very much experimental as is the asset browser in blender.",
    "author": "Lucian James (LJ3D), adapted by RB",
    "version": (0, 2, 7),
    "blender": (3, 3, 0),
    "location": "View3D > Toolbar > Steinberg",
    #"warning": "Developed in 3.0, primarily the alpha. May be unstable or broken in future versions", # used for warning icon and text in addons panel
    "wiki_url": "https://github.com/LJ3D/AssetLibraryTools/wiki",
    "tracker_url": "https://github.com/LJ3D/AssetLibraryTools",
    "category": "3D View"
}

import bpy
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       )
import pathlib
import re
import os
import time
import random
import shutil

from threading import Thread


# ------------------------------------------------------------------------
#    Stuff
# ------------------------------------------------------------------------


diffNames = ["diffuse", "diff", "albedo", "base", "col", "color", "d", "basecolor"]
sssNames = ["sss", "subsurface"]
metNames = ["metallic", "metalness", "metal", "mtl", "met"]
specNames = ["specularity", "specular", "spec", "spc"]
roughNames = ["roughness", "rough", "rgh", "gloss", "glossy", "glossiness", "r"]
normNames = ["normal", "nor", "nrm", "nrml", "norm", "n"]
dispNames = ["displacement", "displace", "disp", "dsp", "height", "heightmap", "bump", "bmp", "b", "dp"]
alphaNames = ["alpha", "opacity"]
emissiveNames = ["emissive", "emission"]

nameLists = [diffNames, sssNames, metNames, specNames, roughNames, normNames, dispNames, alphaNames, emissiveNames]
texTypes = ["diff", "sss", "met", "spec", "rough", "norm", "disp", "alpha", "emission"]

def task(mat):
    mat.asset_generate_preview()


# Find the type of PBR texture a file is based on its name
def FindPBRTextureType(fname):
    PBRTT = None
    startname = fname
    '''
    # Remove digits
    fname = ''.join(i for i in fname if not i.isdigit())
    # Separate CamelCase by space
    fname = re.sub("([a-z])([A-Z])","\g<1> \g<2>",fname)
    # Replace common separators with SPACE
    seperators = ['_', '.', '-', '__', '--', '#']
    for sep in seperators:
        fname = fname.replace(sep, ' ')
    # Set entire string to lower case
    fname = fname.lower()
    '''
    file_name = startname.split(".")[0]
    if len(file_name.rsplit('_')) > 1:
        file_name = file_name.rsplit("_", 1)[1]
    # Find PBRTT
    i = 0
    for nameList in nameLists:
        for name in nameList:
            if name == file_name.lower():
                PBRTT = texTypes[i]
        i+=1
    return PBRTT


# Class with functions for setting up shaders
class shaderSetup():
    
    def createNode(mat, type, name="newNode", location=(0,0)):
        nodes = mat.node_tree.nodes
        n = nodes.new(type=type)
        n.name = name
        n.location = location
        return n
    
    def setMapping(node):
        tool = bpy.context.scene.assetlibrarytools
        if tool.texture_mapping == 'Object':
                node.projection = 'BOX'
                node.projection_blend = 1
    
    def simplePrincipledSetup(name, files):
        tool = bpy.context.scene.assetlibrarytools
        # Create a new empty material
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links 
        nodes.clear() # Delete all nodes
        
        # Load textures
        diffuseTexture = None
        sssTexture = None
        metallicTexture = None
        specularTexture = None
        roughnessTexture = None
        emissionTexture = None
        alphaTexture = None
        normalTexture = None
        displacementTexture = None
        for i in files:
            t = FindPBRTextureType(i.name)
            if t == "diff":
                diffuseTexture = bpy.data.images.load(str(i))
            elif t == "sss":
                sssTexture = bpy.data.images.load(str(i))
                sssTexture.colorspace_settings.name = 'Non-Color'
            elif t == "met":
                metallicTexture = bpy.data.images.load(str(i))
                metallicTexture.colorspace_settings.name = 'Non-Color'
            elif t == "spec":
                specularTexture = bpy.data.images.load(str(i))
                specularTexture.colorspace_settings.name = 'Non-Color'
            elif t == "rough":
                roughnessTexture = bpy.data.images.load(str(i))
                roughnessTexture.colorspace_settings.name = 'Non-Color'
            elif t == "emission":
                emissionTexture = bpy.data.images.load(str(i))  
            elif t == "alpha":
                alphaTexture = bpy.data.images.load(str(i))
                alphaTexture.colorspace_settings.name = 'Non-Color'
            elif t == "norm":
                normalTexture = bpy.data.images.load(str(i))
                normalTexture.colorspace_settings.name = 'Non-Color'
            elif t == "disp":
                displacementTexture = bpy.data.images.load(str(i))
                displacementTexture.colorspace_settings.name = 'Non-Color'
        
        # Create base nodes
        node_output = shaderSetup.createNode(mat, "ShaderNodeOutputMaterial", "node_output", (550,0))
        node_principled = shaderSetup.createNode(mat, "ShaderNodeBsdfPrincipled", "node_principled", (0,0))
        links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
        node_mapping = shaderSetup.createNode(mat, "ShaderNodeMapping", "node_mapping", (-1300,0))
        node_texCoord = shaderSetup.createNode(mat, "ShaderNodeTexCoord", "node_texCoord", (-1500,0))
        links.new(node_texCoord.outputs[tool.texture_mapping], node_mapping.inputs['Vector'])
        if tool.add_extranodes:
            node_scaleValue = shaderSetup.createNode(mat, "ShaderNodeValue", "node_scaleValue", (-1500, -300))
            node_scaleValue.outputs['Value'].default_value = 1
            links.new(node_scaleValue.outputs['Value'], node_mapping.inputs['Scale'])
        
        # Create, fill, and link texture nodes
        imported_tex_nodes = 0
        if diffuseTexture != None and tool.import_diff != False:
            node_imTexDiffuse = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexDiffuse", (-800,300-(300*imported_tex_nodes)))
            node_imTexDiffuse.image = diffuseTexture
            links.new(node_imTexDiffuse.outputs['Color'], node_principled.inputs['Base Color'])
            links.new(node_mapping.outputs['Vector'], node_imTexDiffuse.inputs['Vector'])
            shaderSetup.setMapping(node_imTexDiffuse)
            imported_tex_nodes += 1
            
        if sssTexture != None and tool.import_sss != False:
            node_imTexSSS = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexSSS", (-800,300-(300*imported_tex_nodes)))
            node_imTexSSS.image = sssTexture
            links.new(node_imTexSSS.outputs['Color'], node_principled.inputs['Subsurface'])
            links.new(node_mapping.outputs['Vector'], node_imTexSSS.inputs['Vector'])
            shaderSetup.setMapping(node_imTexSSS)
            imported_tex_nodes += 1
            
        if metallicTexture != None and tool.import_met != False:
            node_imTexMetallic = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexMetallic", (-800,300-(300*imported_tex_nodes)))
            node_imTexMetallic.image = metallicTexture
            links.new(node_imTexMetallic.outputs['Color'], node_principled.inputs['Metallic'])
            links.new(node_mapping.outputs['Vector'], node_imTexMetallic.inputs['Vector'])
            shaderSetup.setMapping(node_imTexMetallic)
            imported_tex_nodes += 1
            
        if specularTexture != None and tool.import_spec != False:
            node_imTexSpecular = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexSpecular", (-800,300-(300*imported_tex_nodes)))
            node_imTexSpecular.image = specularTexture
            links.new(node_imTexSpecular.outputs['Color'], node_principled.inputs['Specular'])
            links.new(node_mapping.outputs['Vector'], node_imTexSpecular.inputs['Vector'])
            shaderSetup.setMapping(node_imTexSpecular)
            imported_tex_nodes += 1
            
        if roughnessTexture != None and tool.import_rough != False:
            node_imTexRoughness = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexRoughness", (-800,300-(300*imported_tex_nodes)))
            node_imTexRoughness.image = roughnessTexture
            if tool.add_extranodes:
                node_imTexRoughnessColourRamp = shaderSetup.createNode(mat, "ShaderNodeValToRGB", "node_imTexRoughnessColourRamp", (-550,300-(300*imported_tex_nodes)))
                links.new(node_imTexRoughness.outputs['Color'], node_imTexRoughnessColourRamp.inputs['Fac'])
                node_imTexRoughnessColourMix = shaderSetup.createNode(mat, "ShaderNodeMixRGB", "node_imTexRoughnessColourMix", (-250,300-(300*imported_tex_nodes)))
                links.new(node_imTexRoughnessColourRamp.outputs['Color'], node_imTexRoughnessColourMix.inputs['Color1'])
                links.new(node_imTexRoughnessColourMix.outputs['Color'], node_principled.inputs['Roughness'])
            else:
                links.new(node_imTexRoughness.outputs['Color'], node_principled.inputs['Roughness'])

            links.new(node_mapping.outputs['Vector'], node_imTexRoughness.inputs['Vector'])
            shaderSetup.setMapping(node_imTexRoughness)
            imported_tex_nodes += 1
            
        if emissionTexture != None and tool.import_emission != False:
            node_imTexEmission = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexEmission", (-800,300-(300*imported_tex_nodes)))
            node_imTexEmission.image = emissionTexture
            links.new(node_imTexEmission.outputs['Color'], node_principled.inputs['Emission'])
            links.new(node_mapping.outputs['Vector'], node_imTexEmission.inputs['Vector'])
            shaderSetup.setMapping(node_imTexEmission)
            imported_tex_nodes += 1
            
        if alphaTexture != None and tool.import_alpha != False:
            node_imTexAlpha = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexAlpha", (-800,300-(300*imported_tex_nodes)))
            node_imTexAlpha.image = alphaTexture
            links.new(node_imTexAlpha.outputs['Color'], node_principled.inputs['Alpha'])
            links.new(node_mapping.outputs['Vector'], node_imTexAlpha.inputs['Vector'])
            shaderSetup.setMapping(node_imTexAlpha)
            imported_tex_nodes += 1
            
        if normalTexture != None and tool.import_norm != False:
            node_imTexNormal = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexNormal", (-800,300-(300*imported_tex_nodes)))
            node_imTexNormal.image = normalTexture
            node_normalMap = shaderSetup.createNode(mat, "ShaderNodeNormalMap", "node_normalMap", (-500,300-(300*imported_tex_nodes)))
            links.new(node_imTexNormal.outputs['Color'], node_normalMap.inputs['Color'])
            links.new(node_normalMap.outputs['Normal'], node_principled.inputs['Normal'])
            links.new(node_mapping.outputs['Vector'], node_imTexNormal.inputs['Vector'])
            shaderSetup.setMapping(node_imTexNormal)
            imported_tex_nodes += 1
            
        if displacementTexture != None and tool.import_disp != False:
            node_imTexDisplacement = shaderSetup.createNode(mat, "ShaderNodeTexImage", "node_imTexDisplacement", (-800,300-(300*imported_tex_nodes)))
            node_imTexDisplacement.image = displacementTexture
            node_imTexDisplacement.interpolation = 'Smart'
            if normalTexture != None:
                node_displacement = shaderSetup.createNode(mat, "ShaderNodeDisplacement", "node_displacement", (-200,-800))
                links.new(node_imTexDisplacement.outputs['Color'], node_displacement.inputs['Height'])
                links.new(node_displacement.outputs['Displacement'], node_output.inputs['Displacement'])
            else:
                node_bump = shaderSetup.createNode(mat, "ShaderNodeBump", "node_bump", (-500,200-(300*imported_tex_nodes)))
                node_bump.inputs['Strength'].default_value = 0.075
                node_bump.inputs['Distance'].default_value = 0.05
                links.new(node_imTexDisplacement.outputs['Color'], node_bump.inputs['Height'])
                links.new(node_bump.outputs['Normal'], node_principled.inputs['Normal'])
            links.new(node_mapping.outputs['Vector'], node_imTexDisplacement.inputs['Vector'])
            shaderSetup.setMapping(node_imTexDisplacement)
            imported_tex_nodes += 1
        
        return mat

# ------------------------------------------------------------------------
#    Properties
# ------------------------------------------------------------------------ 

class properties(PropertyGroup):
    
    # Material import properties
    mat_import_path : StringProperty(
        name = "Import directory",
        description = "Choose a directory to batch import PBR texture sets from.\nFormat your files like this: ChosenDirectory/PBRTextureName/textureFiles",
        default = "",
        maxlen = 1024,
        subtype = 'DIR_PATH'
        )
    skip_existing : BoolProperty(
        name = "Skip existing",
        description = "Dont import materials if a material with the same name already exists",
        default = True
        )
    tex_ignore_filter : StringProperty(
        name = "Tex name filter",
        description = "Filter unwanted textures by a common string in the name (such as DX, which denotes a directX normal map)",
        default = "",
        maxlen = 1024,
        )
    use_fake_user : BoolProperty(
        name = "Use fake user",
        description = "Use fake user on imported materials",
        default = True
        )
    use_real_displacement : BoolProperty(
        name = "Use real displacement",
        description = "Enable real geometry displacement in the material settings (cycles only)",
        default = False
        )
    add_extranodes : BoolProperty(
        name = "Add utility nodes",
        description = "Adds nodes to the imported materials for easy control",
        default = False
        )
    texture_mapping : EnumProperty(
        name='Mapping',
        default='UV',
        items=[('UV', 'UV', 'Use UVs to control mapping'),
        ('Object', 'Object', 'Wrap texture along world coords')])
    import_diff : BoolProperty(
        name = "Import diffuse",
        description = "",
        default = True
        )
    import_sss : BoolProperty(
        name = "Import SSS",
        description = "",
        default = True
        )
    import_met : BoolProperty(
        name = "Import metallic",
        description = "",
        default = True
        )
    import_spec : BoolProperty(
        name = "Import specularity",
        description = "",
        default = True
        )   
    import_rough : BoolProperty(
        name = "Import roughness",
        description = "",
        default = True
        )
    import_emission : BoolProperty(
        name = "Import emission",
        description = "",
        default = True
        )
    import_alpha : BoolProperty(
        name = "Import alpha",
        description = "",
        default = True
        )
    import_norm : BoolProperty(
        name = "Import normal",
        description = "",
        default = True
        )
    import_disp : BoolProperty(
        name = "Import displacement",
        description = "",
        default = True
        )


    # UI properties
    matImport_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )
    matImportOptions_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )
    append_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )

# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------

class OT_PreviewGenerator(Operator):
    bl_label = "Generate Preview for All Materials"
    bl_idname = "alt.previewgenerate"

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        idx_start, idx_end = 0, 500  # That's your batch numbers
        i = -1
        for mat in bpy.data.materials:
            print(mat.name)
            if not mat.asset_data:
                continue
            i += 1
            if i < idx_start:
                continue
            if i >= idx_end:
                break
            # create a thread
            thread = Thread(target=task, args=(mat,))
            # run the thread
            thread.start()
            # wait for the thread to finish
            thread.join()

        return{'FINISHED'}


class OT_BatchImportPBR(Operator):
    bl_label = "Import PBR textures"
    bl_idname = "alt.batchimportpbr"

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        scene = context.scene
        tool = scene.assetlibrarytools
        n_imp = 0 # Number of materials imported
        n_del = 0 # Number of materials deleted (due to no textures after import)
        n_skp = 0 # Number of materials skipped due to them already existing
        existing_mat_names = []
        mat_directory = tool.mat_import_path
        if not mat_directory:
            mat_directory = os.getcwd()
        subdirectories = [x for x in pathlib.Path(mat_directory).iterdir() if x.is_dir()] # Get subdirs in directory selected in UI
        for sd in subdirectories:
            filePaths = [x for x in pathlib.Path(sd).iterdir() if x.is_file()] # Get filepaths of textures
            if tool.tex_ignore_filter != "": # Remove filepaths of textures which contain a filtered string, if a filter is chosen.
                for fp in filePaths:
                    if tool.tex_ignore_filter in fp.name:
                        filePaths.pop(filePaths.index(fp))
            # Get existing material names if skipping existing materials is turned on
            if tool.skip_existing == True:
                existing_mat_names = []
                for mat in bpy.data.materials:
                    existing_mat_names.append(mat.name)
            # check if the material thats about to be imported exists or not, or if we dont care about skipping existing materials.
            if (sd.name not in existing_mat_names) or (tool.skip_existing != True):
                mat = shaderSetup.simplePrincipledSetup(sd.name, filePaths) # Create shader using filepaths of textures
                if tool.use_fake_user == True: # Enable fake user (if desired)
                    mat.use_fake_user = True
                if tool.use_real_displacement == True: # Enable real displacement (if desired)
                    mat.cycles.displacement_method = 'BOTH'
                # Delete the material if it contains no textures
                hasTex = False
                for n in mat.node_tree.nodes:
                    if n.type == 'TEX_IMAGE': # Check if shader contains textures, if yes, then its worth keeping
                        hasTex = True
                if hasTex == False:
                    bpy.data.materials.remove(mat) # Delete material if it contains no textures
                    n_del += 1
                else:
                    n_imp += 1
                mat.asset_mark()
                mat.asset_generate_preview()

            else:
                n_skp += 1
        return{'FINISHED'}


class OP_GroupFilesByName(Operator):
    bl_label = "Group files by name"
    bl_idname = "alt.groupfilesbyname"

    def execute(self, context):
        return self.invoke(context, None)

    def invoke(self, context, event):
        mat_dir = context.scene.assetlibrarytools.mat_import_path
        self.group_files_by_name(mat_dir)
        return{'FINISHED'}

    def group_files_by_name(self, mat_directory):
        if not mat_directory:
            mat_directory = os.getcwd()
        files = os.listdir(mat_directory)
        for file in files:
            if not file.endswith(('.ras', '.xwd', '.bmp', '.jpe', '.jpg', '.jpeg', '.xpm', '.ief', '.pbm', '.tif',
                                  '.gif', '.ppm', '.xbm', '.tiff', '.rgb', '.pgm', '.png', '.pnm', '.exr')):
                continue
            # Get the name of the file without the content behind the last underscore and the extension
            file_name = file.split(".")[0]
            file_name = file_name.rsplit("_", 1)[0]
            # Create a new folder with the file name if it doesn't exist
            if not os.path.exists(os.path.join(mat_directory, file_name)):
                os.makedirs(os.path.join(mat_directory, file_name))
            # Move the file to the new folder
            shutil.move(os.path.join(mat_directory, file), os.path.join(mat_directory, file_name, file))

# ------------------------------------------------------------------------
#    UI
# ------------------------------------------------------------------------

class OBJECT_PT_panel(Panel):
    bl_label = "Steinberg Material Import"
    bl_idname = "OBJECT_PT_assetlibrarytools_panel"
    bl_category = "Steinberg Tools"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    
    @classmethod
    def poll(self,context):
        return context.mode

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        tool = scene.assetlibrarytools
        obj = context.scene.assetlibrarytools
        
        # Material import UI
        matImportRow = layout.row()
        matImportRow.prop(obj, "matImport_expanded",
            icon="TRIA_DOWN" if obj.matImport_expanded else "TRIA_RIGHT",
            icon_only=True, emboss=False
        )
        matImportRow.label(text="Batch import PBR texture sets as simple materials")
        if obj.matImport_expanded:
            layout.prop(tool, "mat_import_path")
            layout.label(text='Make sure to uncheck "Relative Path"!', icon="ERROR")
            layout.operator("alt.groupfilesbyname", icon='FILE')
            layout.operator("alt.batchimportpbr")
            matImportOptionsRow = layout.row()
            matImportOptionsRow.prop(obj, "matImportOptions_expanded",
                icon="TRIA_DOWN" if obj.matImportOptions_expanded else "TRIA_RIGHT",
                icon_only=True, emboss=False
            )
            matImportOptionsRow.label(text="Import options: ")
            if obj.matImportOptions_expanded:
                matImportOptionsRow = layout.row()
                layout.label(text="Import settings:")
                layout.prop(tool, "skip_existing")
                layout.prop(tool, "tex_ignore_filter")
                layout.separator()
                layout.label(text="Material settings:")
                layout.prop(tool, "use_fake_user")
                layout.prop(tool, "use_real_displacement")
                layout.prop(tool, "add_extranodes")
                layout.prop(tool, "texture_mapping")
                layout.separator()
                layout.label(text="Import following textures into materials (if found):")
                layout.prop(tool, "import_diff")
                layout.prop(tool, "import_sss")
                layout.prop(tool, "import_met")
                layout.prop(tool, "import_spec")
                layout.prop(tool, "import_rough")
                layout.prop(tool, "import_emission")
                layout.prop(tool, "import_alpha")
                layout.prop(tool, "import_norm")
                layout.prop(tool, "import_disp")
            layout.operator("alt.previewgenerate")


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    properties,
    OT_BatchImportPBR,
    OBJECT_PT_panel,
    OP_GroupFilesByName,
    OT_PreviewGenerator,
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.assetlibrarytools = PointerProperty(type=properties)
    
def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.assetlibrarytools

if __name__ == "__main__":
    register()
    # Batch code
    directory = os.getcwd()
    picturename = "created_material_assets.blend"
    file_target = os.path.join(directory, picturename)
    bpy.ops.alt.groupfilesbyname()
    bpy.ops.alt.batchimportpbr()
    #bpy.ops.alt.previewgenerate()

    bpy.ops.wm.save_as_mainfile(filepath=file_target)
