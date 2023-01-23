bl_info = {
    "name": "AssetLibraryTools",
    "description": "AssetLibraryTools is a free addon which aims to speed up the process of creating asset libraries with the asset browser, This addon is currently very much experimental as is the asset browser in blender.",
    "author": "Lucian James (LJ3D)",
    "version": (0, 2, 2),
    "blender": (3, 0, 0),
    "location": "3D View > Tools",
    "warning": "Developed in 3.0, primarily the alpha. May be unstable or broken in future versions", # used for warning icon and text in addons panel
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


# ------------------------------------------------------------------------
#    Stuff
# ------------------------------------------------------------------------ 

diffNames = ["diffuse", "diff", "albedo", "base", "col", "color"]
sssNames = ["sss", "subsurface"]
metNames = ["metallic", "metalness", "metal", "mtl", "met"]
specNames = ["specularity", "specular", "spec", "spc"]
roughNames = ["roughness", "rough", "rgh", "gloss", "glossy", "glossiness"]
normNames = ["normal", "nor", "nrm", "nrml", "norm"]
dispNames = ["displacement", "displace", "disp", "dsp", "height", "heightmap", "bump", "bmp"]
alphaNames = ["alpha", "opacity"]
emissiveNames = ["emissive", "emission"]

nameLists = [diffNames, sssNames, metNames, specNames, roughNames, normNames, dispNames, alphaNames, emissiveNames]
texTypes = ["diff", "sss", "met", "spec", "rough", "norm", "disp", "alpha", "emission"]

# Find the type of PBR texture a file is based on its name
def FindPBRTextureType(fname):
    PBRTT = None
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
    # Find PBRTT
    i = 0
    for nameList in nameLists:
        for name in nameList:
            if name in fname:
                PBRTT = texTypes[i]
        i+=1
    return PBRTT


# Display a message in the blender UI
def DisplayMessageBox(message = "", title = "Info", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)


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
        node_output = shaderSetup.createNode(mat, "ShaderNodeOutputMaterial", "node_output", (250,0))
        node_principled = shaderSetup.createNode(mat, "ShaderNodeBsdfPrincipled", "node_principled", (-300,0))
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
                links.new(node_imTexRoughnessColourRamp.outputs['Color'], node_principled.inputs['Roughness'])
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
            node_displacement = shaderSetup.createNode(mat, "ShaderNodeDisplacement", "node_displacement", (-200,-600))
            links.new(node_imTexDisplacement.outputs['Color'], node_displacement.inputs['Height'])
            links.new(node_displacement.outputs['Displacement'], node_output.inputs['Displacement'])
            links.new(node_mapping.outputs['Vector'], node_imTexDisplacement.inputs['Vector'])
            shaderSetup.setMapping(node_imTexDisplacement)
            imported_tex_nodes += 1
        
        return mat


# This code is bad!!!!
# But i dont want to fix it!!!!
def listDownloadAttribs(scene, context):
    scene = context.scene
    tool = scene.assetlibrarytools
    if tool.showAllDownloadAttribs == True:
        attribs = ['None', '1K-JPG', '1K-PNG', '2K-JPG', '2K-PNG', '4K-JPG', '4K-PNG', '8K-JPG', '8K-PNG', '12K-HDR', '16K-HDR', '1K-HDR', '2K-HDR', '4K-HDR', '8K-HDR', '12K-TONEMAPPED', '16K-TONEMAPPED', '1K-TONEMAPPED', '2K-TONEMAPPED', '4K-TONEMAPPED', '8K-TONEMAPPED', '12K-JPG', '12K-PNG', '16K-JPG', '16K-PNG', '1K-HQ-JPG', '1K-HQ-PNG', '1K-LQ-JPG', '1K-LQ-PNG', '1K-SQ-JPG', '1K-SQ-PNG', '2K-HQ-JPG', '2K-HQ-PNG', '2K-LQ-JPG', '2K-LQ-PNG', '2K-SQ-JPG', '2K-SQ-PNG', '4K-HQ-JPG', '4K-HQ-PNG', '4K-LQ-JPG', '4K-LQ-PNG', '4K-SQ-JPG', '4K-SQ-PNG', 'HQ', 'LQ', 'SQ', '24K-JPG', '24K-PNG', '32K-JPG', '32K-PNG', '6K-JPG', '6K-PNG', '2K', '4K', '8K', '1K', 'CustomImages', '16K', '9K', '1000K', '250K', '25K', '5K-JPG', '5K-PNG', '2kPNG', '4kPNG', '2kPNG-PNG', '4kPNG-PNG', '9K-JPG', '10K-JPG', '7K-JPG', '7K-PNG', '3K-JPG', '3K-PNG', '9K-PNG', '33K-JPG', '33K-PNG', '15K-JPG', '15K-PNG']
    else:
        attribs = ['None', '1K-JPG', '1K-PNG', '2K-JPG', '2K-PNG', '4K-JPG', '4K-PNG', '8K-JPG', '8K-PNG']
    items = []
    for a in attribs:
        items.append((a, a, ""))
    return items


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
    
    
    # Model import properties
    model_import_path : StringProperty(
        name = "Import directory",
        description = "Choose a directory to batch import models from.\nSubdirectories are checked recursively",
        default = "",
        maxlen = 1024,
        subtype = 'DIR_PATH'
        )
    hide_after_import : BoolProperty(
        name = "Hide models after import",
        description = "Reduces viewport polycount, prevents low framerate/crashes.\nHides each model individually straight after import",
        default = False
        )
    move_to_new_collection_after_import : BoolProperty(
        name = "Move models to new collection after import",
        description = "",
        default = False
        )
    join_new_objects : BoolProperty(
        name = "Join all models in each file together after import",
        description = "",
        default = False
        )
    import_fbx : BoolProperty(
        name = "Import FBX files",
        description = "",
        default = True
        )
    import_gltf : BoolProperty(
        name = "Import GLTF files",
        description = "",
        default = True
        )
    import_obj : BoolProperty(
        name = "Import OBJ files",
        description = "",
        default = True
        )
    import_x3d : BoolProperty(
        name = "Import X3D files",
        description = "",
        default = True
        )
        
        
    # Batch append properties
    append_path : StringProperty(
        name = "Import directory",
        description = "Choose a directory to batch append from.",
        default = "",
        maxlen = 1024,
        subtype = 'DIR_PATH'
        )
    append_recursive_search : BoolProperty(
        name = "Search for .blend files in subdirs recursively",
        description = "",
        default = False
        )
    append_move_to_new_collection_after_import : BoolProperty(
        name = "Move objects to new collection after import",
        description = "",
        default = False
        )
    append_join_new_objects : BoolProperty(
        name = "Join all objects in each file together after import",
        description = "",
        default = False
        )
    appendType : EnumProperty(
        name="Append",
        description="Choose type to append",
        items=[ ('objects', "Objects", ""),
                ('materials', "Materials", ""),
                ]
        )
    deleteLights : BoolProperty(
        name = "Dont append lights",
        description = "",
        default = True
        )
    deleteCameras : BoolProperty(
        name = "Dont append cameras",
        description = "",
        default = True
        )
    
    
    # Asset management properties
    markunmark : EnumProperty(
        name="Operation",
        description="Choose whether to mark assets, or unmark assets",
        items=[ ('mark', "Mark assets", ""),
                ('unmark', "Unmark assets", ""),
               ]
        )
    assettype : EnumProperty(
        name="On type",
        description="Choose a type of asset to mark/unmark",
        items=[ ('objects', "Objects", ""),
                ('materials', "Materials", ""),
                ('images', "Images", ""),
                ('textures', "Textures", ""),
                ('meshes', "Meshes", ""),
               ]
        )
    previewgentype : EnumProperty(
        name="Asset type",
        description="Choose a type of asset to mark/unmark",
        items=[ ('objects', "Objects", ""),
                ('materials', "Materials", ""),
                ('images', "Images", ""),
                ('textures', "Textures", ""),
                ('meshes', "Meshes", ""),
               ]
        )
    
    
    # Utilities panel properties
    deleteType : EnumProperty(
        name="Delete all",
        description="Choose type to batch delete",
        items=[ ('objects', "Objects", ""),
                ('materials', "Materials", ""),
                ('images', "Images", ""),
                ('textures', "Textures", ""),
                ('meshes', "Meshes", ""),
               ]
        )
    dispNewScale: FloatProperty(
        name = "New Displacement Scale",
        description = "A float property",
        default = 0.1,
        min = 0.0001
        )
    
    
    # Asset snapshot panel properties
    resolution : IntProperty(
            name="Preview Resolution",
            description="Resolution to render the preview",
            min=1,
            soft_max=500,
            default=256
            )
    
    
    # CC0AssetDownloader properties
    downloader_save_path : StringProperty(
        name = "Save location",
        description = "Choose a directory to save assets to",
        default = "",
        maxlen = 1024,
        subtype = 'DIR_PATH'
        )
    keywordFilter : StringProperty(
        name = "Keyword filter",
        description = "Enter a keyword to filter assets by, leave empty if you do not wish to filter.",
        default = "",
        maxlen = 1024,
        )
    showAllDownloadAttribs: BoolProperty(
        name = "Show all download attributes",
        description = "",
        default = True
        )
    attributeFilter : EnumProperty(
        name="Attribute filter",
        description="Choose attribute to filter assets by",
        items=listDownloadAttribs
        )
    extensionFilter : EnumProperty(
        name="Extension filter",
        description="Choose file extension to filter assets by",
        items=[ ('None', "None", ""),
                ('zip', "ZIP", ""),
                ('obj', "OBJ", ""),
                ('exr', "EXR", ""),
                ('sbsar', "SBSAR", ""),
               ]
        )
    unZip : BoolProperty(
        name = "Unzip downloaded zip files",
        description = "",
        default = True
        )
    deleteZips : BoolProperty(
        name = "Delete zip files after they have been unzipped",
        description = "",
        default = True
        )
    skipDuplicates : BoolProperty(
        name = "Dont download files which already exist",
        description = "",
        default = True
        )
    terminal : EnumProperty(
        name="Terminal",
        description="Choose terminal to run script with",
        items=[ ('cmd', "cmd", ""),
                ('gnome-terminal', "gnome-terminal", ""),
                ('konsole', 'konsole', ""),
                ('xterm', 'xterm', ""),
               ]
        )
    
    
    # SBSAR import properties
    sbsar_import_path : StringProperty(
        name = "Import directory",
        description = "Choose a directory to batch import sbsar files from.\nSubdirectories are checked recursively",
        default = "",
        maxlen = 1024,
        subtype = 'DIR_PATH'
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
    modelImport_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )
    modelImportOptions_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )
    assetBrowserOpsRow_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )
    utilRow_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )
    snapshotRow_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )
    assetDownloaderRow_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )
    sbsarImport_expanded : BoolProperty(
        name = "Click to expand",
        description = "",
        default = False
        )

# ------------------------------------------------------------------------
#    Operators
# ------------------------------------------------------------------------

class OT_BatchImportPBR(Operator):
    bl_label = "Import PBR textures"
    bl_idname = "alt.batchimportpbr"
    def execute(self, context):
        scene = context.scene
        tool = scene.assetlibrarytools
        n_imp = 0 # Number of materials imported
        n_del = 0 # Number of materials deleted (due to no textures after import)
        n_skp = 0 # Number of materials skipped due to them already existing
        existing_mat_names = []
        subdirectories = [x for x in pathlib.Path(tool.mat_import_path).iterdir() if x.is_dir()] # Get subdirs in directory selected in UI
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
            else:
                n_skp += 1
        if (n_del > 0) and (n_skp > 0):
            DisplayMessageBox("Complete, {0} materials imported, {1} were deleted after import because they contained no textures (No recognised textures were found in the folder), {2} skipped because they already exist".format(n_imp,n_del,n_skp))
        elif n_skp > 0:
            DisplayMessageBox("Complete, {0} materials imported. {1} skipped because they already exist".format(n_imp, n_skp))
        elif n_del > 0:
            DisplayMessageBox("Complete, {0} materials imported, {1} were deleted after import because they contained no textures (No recognised textures were found in the folder)".format(n_imp,n_del))
        else:
            DisplayMessageBox("Complete, {0} materials imported".format(n_imp))
        return{'FINISHED'}


# ------------------------------------------------------------------------
#    UI
# ------------------------------------------------------------------------

class OBJECT_PT_panel(Panel):
    bl_label = "AssetLibraryTools"
    bl_idname = "OBJECT_PT_assetlibrarytools_panel"
    bl_category = "AssetLibraryTools"
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
        matImportBox = layout.box()
        matImportRow = matImportBox.row()
        matImportRow.prop(obj, "matImport_expanded",
            icon="TRIA_DOWN" if obj.matImport_expanded else "TRIA_RIGHT",
            icon_only=True, emboss=False
        )
        matImportRow.label(text="Batch import PBR texture sets as simple materials")
        if obj.matImport_expanded:
            matImportBox.prop(tool, "mat_import_path")
            matImportBox.label(text='Make sure to uncheck "Relative Path"!', icon="ERROR")
            matImportBox.operator("alt.batchimportpbr")
            matImportOptionsRow = matImportBox.row()
            matImportOptionsRow.prop(obj, "matImportOptions_expanded",
                icon="TRIA_DOWN" if obj.matImportOptions_expanded else "TRIA_RIGHT",
                icon_only=True, emboss=False
            )
            matImportOptionsRow.label(text="Import options: ")
            if obj.matImportOptions_expanded:
                matImportOptionsRow = matImportBox.row()
                matImportBox.label(text="Import settings:")
                matImportBox.prop(tool, "skip_existing")
                matImportBox.prop(tool, "tex_ignore_filter")
                matImportBox.separator()
                matImportBox.label(text="Material settings:")
                matImportBox.prop(tool, "use_fake_user")
                matImportBox.prop(tool, "use_real_displacement")
                matImportBox.prop(tool, "add_extranodes")
                matImportBox.prop(tool, "texture_mapping")
                matImportBox.separator()
                matImportBox.label(text="Import following textures into materials (if found):")
                matImportBox.prop(tool, "import_diff")
                matImportBox.prop(tool, "import_sss")
                matImportBox.prop(tool, "import_met")
                matImportBox.prop(tool, "import_spec")
                matImportBox.prop(tool, "import_rough")
                matImportBox.prop(tool, "import_emission")
                matImportBox.prop(tool, "import_alpha")
                matImportBox.prop(tool, "import_norm")
                matImportBox.prop(tool, "import_disp")


# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = (
    properties,
    OT_BatchImportPBR,
    OBJECT_PT_panel
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
