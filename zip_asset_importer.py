bl_info = {
    "name": "ZIP Asset Importer",
    "author": "Drune",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > ZIP Import",
    "description": "Extract a model ZIP, import the best supported 3D file, and build a Node Wrangler-style PBR material",
    "category": "Import-Export",
}

import os
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, Panel
from mathutils import Vector


MODEL_EXTENSIONS = {
    ".fbx": 100,
    ".glb": 95,
    ".gltf": 94,
    ".obj": 90,
    ".usd": 85,
    ".usda": 84,
    ".usdc": 84,
    ".usdz": 83,
    ".abc": 78,
    ".dae": 74,
    ".blend": 70,
    ".ply": 62,
    ".stl": 60,
    ".x3d": 50,
    ".wrl": 48,
}

IMAGE_EXTENSIONS = {
    ".bmp",
    ".dds",
    ".exr",
    ".hdr",
    ".jpeg",
    ".jpg",
    ".png",
    ".tga",
    ".tif",
    ".tiff",
    ".webp",
}

IMAGE_EXTENSION_SCORE = {
    ".exr": 50,
    ".tif": 45,
    ".tiff": 45,
    ".png": 40,
    ".tga": 35,
    ".webp": 32,
    ".jpg": 30,
    ".jpeg": 30,
    ".dds": 25,
    ".bmp": 20,
    ".hdr": 20,
}

MAP_DEFINITIONS = [
    ("displacement", "Displacement", {"displacement", "displace", "disp", "dsp", "height", "heightmap"}),
    ("base_color", "Base Color", {"diffuse", "diff", "albedo", "base", "col", "color", "basecolor"}),
    ("metallic", "Metallic", {"metallic", "metalness", "metal", "mtl"}),
    ("specular", "Specular IOR Level", {"specularity", "specular", "spec", "spc"}),
    ("roughness", "Roughness", {"roughness", "rough", "rgh"}),
    ("gloss", "Gloss", {"gloss", "glossy", "glossiness"}),
    ("bump", "Bump", {"bump", "bmp"}),
    ("normal", "Normal", {"normal", "nor", "nrm", "nrml", "norm"}),
    ("transmission", "Transmission Weight", {"transmission", "transparency"}),
    ("emission", "Emission Color", {"emission", "emissive", "emit"}),
    ("alpha", "Alpha", {"alpha", "opacity"}),
    ("ao", "Ambient Occlusion", {"ao", "ambient", "occlusion", "ambientocclusion"}),
    ("cavity", "Cavity", {"cavity", "cavities", "cav"}),
]


def _split_into_components(name):
    stem = Path(name).stem
    stem = "".join(char for char in stem if not char.isdigit())
    stem = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    for separator in ("_", ".", "-", "__", "--", "#"):
        stem = stem.replace(separator, " ")
    return [component.lower() for component in stem.split() if component]


def _remove_common_prefix(names_to_tags):
    if not names_to_tags:
        return False
    first_tags = next(iter(names_to_tags.values()))
    if not first_tags:
        return False
    common = first_tags[0]
    if any(not tags or tags[0] != common for tags in names_to_tags.values()):
        return False
    for name in list(names_to_tags):
        names_to_tags[name] = names_to_tags[name][1:]
    return True


def _remove_common_suffix(names_to_tags):
    if not names_to_tags:
        return False
    first_tags = next(iter(names_to_tags.values()))
    if not first_tags:
        return False
    common = first_tags[-1]
    if any(not tags or tags[-1] != common for tags in names_to_tags.values()):
        return False
    for name in list(names_to_tags):
        names_to_tags[name] = names_to_tags[name][:-1]
    return True


def _clean_texture_tags(image_paths):
    names_to_tags = {path.name: _split_into_components(path.name) for path in image_paths}
    all_map_tags = set()
    for _map_id, _label, tags in MAP_DEFINITIONS:
        all_map_tags.update(tags)

    while len(names_to_tags) > 1:
        changed = False
        changed |= _remove_common_prefix(names_to_tags)
        changed |= _remove_common_suffix(names_to_tags)

        removable = []
        for name, tags in names_to_tags.items():
            if not any(tag in all_map_tags for tag in tags):
                removable.append(name)
        for name in removable:
            del names_to_tags[name]
            changed = True

        if not changed:
            break

    return names_to_tags


def _path_quality_score(path, tags):
    score = IMAGE_EXTENSION_SCORE.get(path.suffix.lower(), 0)
    name = path.name.lower()

    res_match = re.search(r"(?<!\d)(\d{1,2})k(?![a-z])", name)
    if res_match:
        score += int(res_match.group(1)) * 10

    size_match = re.search(r"(?<!\d)(\d{3,5})[x_ -](\d{3,5})(?!\d)", name)
    if size_match:
        score += max(int(size_match.group(1)), int(size_match.group(2))) // 256

    if "high" in tags:
        score += 10
    if "low" in tags:
        score -= 10
    return score


def _classify_textures(image_paths):
    names_to_tags = _clean_texture_tags(image_paths)
    path_by_name = {path.name: path for path in image_paths}
    matches = {}

    for map_id, label, map_tags in MAP_DEFINITIONS:
        best = None
        for name, tags in names_to_tags.items():
            path = path_by_name.get(name)
            if path is None:
                continue
            if map_id == "normal" and {"dx", "directx"}.intersection(tags):
                continue
            if not map_tags.intersection(tags):
                continue

            score = _path_quality_score(path, tags)
            if map_id == "roughness":
                score += 100
            elif map_id == "gloss":
                score += 60
            candidate = (score, label, path)
            if best is None or candidate[0] > best[0]:
                best = candidate
        if best is not None:
            matches[map_id] = {"label": best[1], "path": best[2]}

    if "roughness" not in matches and "gloss" in matches:
        matches["roughness"] = {
            "label": "Roughness",
            "path": matches["gloss"]["path"],
            "invert": True,
        }

    return matches


def _safe_extract(zip_path, extract_dir):
    extract_root = Path(extract_dir).resolve()
    extract_root.mkdir(parents=True, exist_ok=True)

    extracted = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            raw_name = info.filename.replace("\\", "/")
            pure = PurePosixPath(raw_name)
            if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
                continue

            target = (extract_root / Path(*pure.parts)).resolve()
            if os.path.commonpath([str(extract_root), str(target)]) != str(extract_root):
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, open(target, "wb") as destination:
                shutil.copyfileobj(source, destination)
            extracted.append(target)

    return extracted


def _asset_folder_for_zip(zip_path):
    zip_path = Path(zip_path).resolve()
    if zip_path.parent.name.lower() == zip_path.stem.lower():
        return zip_path.parent

    base_folder = zip_path.with_suffix("")
    folder = base_folder
    counter = 2
    while (folder.exists() and not folder.is_dir()) or (folder / zip_path.name).exists():
        folder = zip_path.parent / f"{zip_path.stem}_{counter}"
        counter += 1
    return folder


def _organize_zip_for_import(zip_path):
    zip_path = Path(zip_path).resolve()
    asset_folder = _asset_folder_for_zip(zip_path)
    asset_folder.mkdir(parents=True, exist_ok=True)

    organized_zip = asset_folder / zip_path.name
    if zip_path != organized_zip:
        shutil.move(str(zip_path), str(organized_zip))

    return organized_zip, asset_folder


def _find_files(root, extensions):
    ignored_parts = {"__macosx", ".git"}
    found = []
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        if any(part.lower() in ignored_parts for part in path.parts):
            continue
        if path.suffix.lower() in extensions:
            found.append(path)
    return found


def _model_score(path):
    score = MODEL_EXTENSIONS.get(path.suffix.lower(), 0)
    tags = set(_split_into_components(path.name))

    for lod_token, lod_score in (("lod", 5), ("lod0", 18), ("lod00", 18), ("lod1", 10)):
        if lod_token in tags:
            score += lod_score
    if "high" in tags:
        score += 20
    if "source" in tags:
        score += 6
    if {"low", "proxy", "collision", "collider"}.intersection(tags):
        score -= 25
    return score


def _choose_model_files(model_paths, import_all):
    ordered = sorted(model_paths, key=lambda path: (_model_score(path), -len(path.parts), path.name.lower()), reverse=True)
    if import_all:
        return ordered
    return ordered[:1]


def _before_after_import(import_call):
    before = set(bpy.data.objects)
    import_call()
    after = set(bpy.data.objects)
    return list(after - before)


def _import_blend(filepath):
    new_objects = []
    with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)
    collection = bpy.context.collection
    for obj in data_to.objects:
        if obj is None:
            continue
        collection.objects.link(obj)
        new_objects.append(obj)
    return new_objects


def _call_importer(filepath):
    ext = Path(filepath).suffix.lower()
    filepath = str(filepath)

    if ext == ".blend":
        return _import_blend(filepath)

    def call(operator, **kwargs):
        return _before_after_import(lambda: operator(**kwargs))

    if ext == ".fbx":
        return call(bpy.ops.import_scene.fbx, filepath=filepath)
    if ext in {".glb", ".gltf"}:
        return call(bpy.ops.import_scene.gltf, filepath=filepath)
    if ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            return call(bpy.ops.wm.obj_import, filepath=filepath)
        return call(bpy.ops.import_scene.obj, filepath=filepath)
    if ext in {".usd", ".usda", ".usdc", ".usdz"}:
        return call(bpy.ops.wm.usd_import, filepath=filepath)
    if ext == ".abc":
        return call(bpy.ops.wm.alembic_import, filepath=filepath)
    if ext == ".dae":
        return call(bpy.ops.wm.collada_import, filepath=filepath)
    if ext == ".ply":
        if hasattr(bpy.ops.wm, "ply_import"):
            return call(bpy.ops.wm.ply_import, filepath=filepath)
        return call(bpy.ops.import_mesh.ply, filepath=filepath)
    if ext == ".stl":
        if hasattr(bpy.ops.wm, "stl_import"):
            return call(bpy.ops.wm.stl_import, filepath=filepath)
        return call(bpy.ops.import_mesh.stl, filepath=filepath)
    if ext in {".x3d", ".wrl"}:
        return call(bpy.ops.import_scene.x3d, filepath=filepath)

    raise RuntimeError(f"No importer is configured for {ext}")


def _mesh_objects_from(objects):
    meshes = []
    seen = set()

    def visit(obj):
        if obj in seen:
            return
        seen.add(obj)
        if obj.type == "MESH":
            meshes.append(obj)
        for child in obj.children:
            visit(child)

    for obj in objects:
        visit(obj)
    return meshes


def _set_non_color(image):
    if image is None:
        return
    try:
        image.colorspace_settings.is_data = True
    except Exception:
        try:
            image.colorspace_settings.name = "Non-Color"
        except Exception:
            pass


def _socket(sockets, *names):
    for name in names:
        socket = sockets.get(name)
        if socket is not None:
            return socket
    return None


def _link(links, output_socket, input_socket):
    if output_socket is None or input_socket is None:
        return None
    return links.new(output_socket, input_socket)


def _image_output(node, prefer_fac=False):
    if prefer_fac:
        return node.outputs.get("Fac") or node.outputs.get("Alpha") or node.outputs[0]
    return node.outputs.get("Color") or node.outputs[0]


def _create_image_node(nodes, path, label, is_data):
    node = nodes.new(type="ShaderNodeTexImage")
    node.label = label
    node.name = label
    node.image = bpy.data.images.load(str(path), check_existing=True)
    if is_data:
        _set_non_color(node.image)
    return node


def _new_multiply_node(nodes, label):
    try:
        node = nodes.new(type="ShaderNodeMixRGB")
        node.blend_type = "MULTIPLY"
        node.inputs[0].default_value = 1.0
    except Exception:
        node = nodes.new(type="ShaderNodeMix")
        node.data_type = "RGBA"
        node.blend_type = "MULTIPLY"
        factor = _socket(node.inputs, "Factor")
        if factor is not None:
            factor.default_value = 1.0
    node.label = label
    node.name = label
    return node


def _multiply_inputs(node):
    if node.bl_idname == "ShaderNodeMixRGB":
        return node.inputs[1], node.inputs[2], node.outputs[0]

    input_a = _socket(node.inputs, "A", "Color A", "Image")
    input_b = _socket(node.inputs, "B", "Color B", "Image_001")
    color_inputs = [sock for sock in node.inputs if sock.type in {"RGBA", "VECTOR"}]
    if input_a is None and color_inputs:
        input_a = color_inputs[0]
    if input_b is None and len(color_inputs) > 1:
        input_b = color_inputs[1]
    return input_a, input_b, node.outputs[0]


def _set_material_displacement(mat):
    for value in ("BOTH", "DISPLACEMENT"):
        try:
            mat.displacement_method = value
            return
        except Exception:
            pass
    cycles = getattr(mat, "cycles", None)
    if cycles:
        for value in ("BOTH", "DISPLACEMENT"):
            try:
                cycles.displacement_method = value
                return
            except Exception:
                pass


def _create_node_wrangler_style_material(name, texture_matches, use_ao_cavity):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = Vector((500, 0))
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = Vector((120, 0))
    _link(links, bsdf.outputs.get("BSDF"), _socket(output.inputs, "Surface"))

    texture_nodes = []
    helper_nodes = []
    texture_by_id = {}

    def add_texture(map_id, label=None, is_data=True):
        info = texture_matches.get(map_id)
        if not info:
            return None
        node = _create_image_node(nodes, info["path"], label or info["label"], is_data)
        texture_nodes.append(node)
        texture_by_id[map_id] = node
        return node

    ao_node = add_texture("ao", "Ambient Occlusion", True)
    cavity_node = add_texture("cavity", "Cavity", True)
    base_node = add_texture("base_color", "Base Color", False)

    if base_node:
        base_output = _image_output(base_node)
        if use_ao_cavity:
            for map_id, label in (("ao", "Base Color x AO"), ("cavity", "Base Color x Cavity")):
                map_node = texture_by_id.get(map_id)
                if map_node is None:
                    continue
                multiply = _new_multiply_node(nodes, label)
                helper_nodes.append(multiply)
                input_a, input_b, output_color = _multiply_inputs(multiply)
                _link(links, base_output, input_a)
                _link(links, _image_output(map_node), input_b)
                base_output = output_color
        _link(links, base_output, _socket(bsdf.inputs, "Base Color"))

    metallic_node = add_texture("metallic", "Metallic", True)
    if metallic_node:
        _link(links, _image_output(metallic_node), _socket(bsdf.inputs, "Metallic"))

    specular_node = add_texture("specular", "Specular IOR Level", True)
    if specular_node:
        _link(links, _image_output(specular_node), _socket(bsdf.inputs, "Specular IOR Level", "Specular"))

    roughness_node = add_texture("roughness", "Roughness", True)
    if roughness_node:
        rough_output = _image_output(roughness_node)
        if texture_matches.get("roughness", {}).get("invert"):
            invert = nodes.new(type="ShaderNodeInvert")
            invert.label = "Invert Gloss"
            invert.name = "Invert Gloss"
            helper_nodes.append(invert)
            _link(links, rough_output, _socket(invert.inputs, "Color") or invert.inputs[1])
            rough_output = _socket(invert.outputs, "Color") or invert.outputs[0]
        _link(links, rough_output, _socket(bsdf.inputs, "Roughness"))

    alpha_node = add_texture("alpha", "Alpha", True)
    if alpha_node:
        _link(links, _image_output(alpha_node), _socket(bsdf.inputs, "Alpha"))
        try:
            mat.blend_method = "BLEND"
            mat.use_screen_refraction = True
        except Exception:
            pass

    transmission_node = add_texture("transmission", "Transmission Weight", True)
    if transmission_node:
        _link(links, _image_output(transmission_node), _socket(bsdf.inputs, "Transmission Weight", "Transmission"))

    emission_node = add_texture("emission", "Emission Color", False)
    if emission_node:
        _link(links, _image_output(emission_node), _socket(bsdf.inputs, "Emission Color", "Emission"))
        strength = _socket(bsdf.inputs, "Emission Strength", "Strength")
        if strength is not None and not strength.is_linked:
            strength.default_value = 1.0

    bump_texture = add_texture("bump", "Bump", True)
    bump_node = None
    if bump_texture:
        bump_node = nodes.new(type="ShaderNodeBump")
        bump_node.label = "Bump"
        bump_node.name = "Bump"
        helper_nodes.append(bump_node)
        _link(links, _image_output(bump_texture), _socket(bump_node.inputs, "Height"))
        _link(links, _socket(bump_node.outputs, "Normal"), _socket(bsdf.inputs, "Normal"))

    normal_texture = add_texture("normal", "Normal", True)
    if normal_texture:
        normal_node = nodes.new(type="ShaderNodeNormalMap")
        normal_node.label = "Normal Map"
        normal_node.name = "Normal Map"
        helper_nodes.append(normal_node)
        _link(links, _image_output(normal_texture), _socket(normal_node.inputs, "Color"))
        normal_output = _socket(normal_node.outputs, "Normal")
        if bump_node:
            _link(links, normal_output, _socket(bump_node.inputs, "Normal"))
        else:
            _link(links, normal_output, _socket(bsdf.inputs, "Normal"))

    displacement_texture = add_texture("displacement", "Displacement", True)
    if displacement_texture:
        displacement_node = nodes.new(type="ShaderNodeDisplacement")
        displacement_node.label = "Displacement"
        displacement_node.name = "Displacement"
        displacement_node.location = bsdf.location + Vector((100, -700))
        helper_nodes.append(displacement_node)
        _link(links, _image_output(displacement_texture), _socket(displacement_node.inputs, "Height"))
        _link(links, _socket(displacement_node.outputs, "Displacement"), _socket(output.inputs, "Displacement"))
        _set_material_displacement(mat)

    for index, texture_node in enumerate(texture_nodes):
        texture_node.location = bsdf.location + Vector((-550, (index * -280) + 200))

    for node in helper_nodes:
        if node.location == Vector((0, 0)):
            related = None
            for link in links:
                if link.to_node == node and link.from_node in texture_nodes:
                    related = link.from_node
                    break
            node.location = (related.location if related else bsdf.location) + Vector((300, 0))

    if texture_nodes:
        mapping = nodes.new(type="ShaderNodeMapping")
        mapping.location = bsdf.location + Vector((-1050, 0))
        tex_coord = nodes.new(type="ShaderNodeTexCoord")
        tex_coord.location = mapping.location + Vector((-200, 0))
        _link(links, _socket(tex_coord.outputs, "UV") or tex_coord.outputs[2], _socket(mapping.inputs, "Vector") or mapping.inputs[0])

        if len(texture_nodes) > 1:
            reroute = nodes.new(type="NodeReroute")
            texture_nodes_for_frame = texture_nodes + [reroute]
            average_y = sum(node.location.y for node in texture_nodes_for_frame) / len(texture_nodes_for_frame)
            reroute.location = Vector((texture_nodes[0].location.x - 50, average_y - 120))
            for texture_node in texture_nodes:
                _link(links, reroute.outputs[0], _socket(texture_node.inputs, "Vector") or texture_node.inputs[0])
            _link(links, _socket(mapping.outputs, "Vector") or mapping.outputs[0], reroute.inputs[0])
        else:
            _link(links, _socket(mapping.outputs, "Vector") or mapping.outputs[0], _socket(texture_nodes[0].inputs, "Vector") or texture_nodes[0].inputs[0])
            texture_nodes_for_frame = texture_nodes

        mapping_frame = nodes.new(type="NodeFrame")
        mapping_frame.label = "Mapping"
        mapping.parent = mapping_frame
        tex_coord.parent = mapping_frame
        mapping_frame.update()

        texture_frame = nodes.new(type="NodeFrame")
        texture_frame.label = "Textures"
        for texture_node in texture_nodes_for_frame:
            texture_node.parent = texture_frame
        texture_frame.update()

    mat.node_tree.update_tag()
    return mat


def _apply_material(mesh_objects, material, replace):
    for obj in mesh_objects:
        if replace:
            obj.data.materials.clear()
        if not obj.data.materials:
            obj.data.materials.append(material)
        elif material.name not in {slot.material.name for slot in obj.material_slots if slot.material}:
            obj.data.materials.append(material)


def _shade_smooth(mesh_objects):
    for obj in mesh_objects:
        for poly in obj.data.polygons:
            poly.use_smooth = True


def _select_objects(objects):
    bpy.ops.object.select_all(action="DESELECT")
    active = None
    for obj in objects:
        obj.select_set(True)
        if active is None and obj.type == "MESH":
            active = obj
    if active is None and objects:
        active = objects[0]
    bpy.context.view_layer.objects.active = active


class ZIPASSETIMPORTER_OT_import_zip(Operator):
    bl_idname = "zip_asset_importer.import_zip"
    bl_label = "Import ZIP Asset"
    bl_description = "Extract the selected ZIP, import its model, and build a Node Wrangler-style material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        zip_path = bpy.path.abspath(scene.zip_asset_importer_zip_path)
        if not zip_path or not os.path.isfile(zip_path):
            self.report({"ERROR"}, "Choose a valid ZIP file")
            return {"CANCELLED"}
        if not zipfile.is_zipfile(zip_path):
            self.report({"ERROR"}, "Selected file is not a ZIP archive")
            return {"CANCELLED"}

        try:
            organized_zip, asset_folder = _organize_zip_for_import(zip_path)
        except Exception as exc:
            self.report({"ERROR"}, f"Could not organize ZIP: {exc}")
            return {"CANCELLED"}

        zip_path = str(organized_zip)
        extract_dir = asset_folder
        scene.zip_asset_importer_zip_path = zip_path

        try:
            _safe_extract(zip_path, extract_dir)
        except Exception as exc:
            self.report({"ERROR"}, f"Could not extract ZIP: {exc}")
            return {"CANCELLED"}

        model_paths = _find_files(extract_dir, set(MODEL_EXTENSIONS))
        image_paths = _find_files(extract_dir, IMAGE_EXTENSIONS)
        if not model_paths:
            self.report({"ERROR"}, "No supported 3D model file found in the ZIP")
            return {"CANCELLED"}

        selected_models = _choose_model_files(model_paths, scene.zip_asset_importer_import_all_models)
        imported_objects = []
        import_errors = []
        for model_path in selected_models:
            try:
                imported_objects.extend(_call_importer(model_path))
            except Exception as exc:
                import_errors.append(f"{model_path.name}: {exc}")

        if not imported_objects:
            message = "Could not import model"
            if import_errors:
                message += f" ({import_errors[0]})"
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        mesh_objects = _mesh_objects_from(imported_objects)
        texture_matches = _classify_textures(image_paths)
        if mesh_objects and texture_matches:
            material_name = f"{Path(zip_path).stem}_PBR"
            material = _create_node_wrangler_style_material(
                material_name,
                texture_matches,
                scene.zip_asset_importer_use_ao_cavity,
            )
            _apply_material(mesh_objects, material, scene.zip_asset_importer_replace_materials)

        if scene.zip_asset_importer_shade_smooth:
            _shade_smooth(mesh_objects)

        _select_objects(imported_objects)
        if scene.zip_asset_importer_focus_view and getattr(context, "screen", None):
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    region = next((r for r in area.regions if r.type == "WINDOW"), None)
                    if region is None:
                        continue
                    override = {"area": area, "region": region}
                    with context.temp_override(**override):
                        bpy.ops.view3d.view_selected(use_all_regions=False)
                    break

        map_names = ", ".join(sorted(texture_matches)) if texture_matches else "no textures"
        model_names = ", ".join(path.name for path in selected_models)
        report = f"Imported {model_names}; matched {map_names}"
        if import_errors:
            report += f"; {len(import_errors)} import issue(s)"
        self.report({"INFO"}, report)
        return {"FINISHED"}


class ZIPASSETIMPORTER_PT_panel(Panel):
    bl_label = "ZIP Asset Importer"
    bl_idname = "ZIPASSETIMPORTER_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ZIP Import"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.prop(scene, "zip_asset_importer_zip_path", text="ZIP")

        box = layout.box()
        box.prop(scene, "zip_asset_importer_import_all_models")
        box.prop(scene, "zip_asset_importer_replace_materials")
        box.prop(scene, "zip_asset_importer_use_ao_cavity")
        box.prop(scene, "zip_asset_importer_shade_smooth")
        box.prop(scene, "zip_asset_importer_focus_view")

        layout.operator("zip_asset_importer.import_zip", icon="IMPORT")


classes = (
    ZIPASSETIMPORTER_OT_import_zip,
    ZIPASSETIMPORTER_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.zip_asset_importer_zip_path = StringProperty(
        name="ZIP File",
        description="ZIP archive containing a 3D model and texture maps",
        subtype="FILE_PATH",
        default="",
    )
    bpy.types.Scene.zip_asset_importer_import_all_models = BoolProperty(
        name="Import All Models",
        description="Import every supported model in the ZIP instead of the highest quality candidate",
        default=False,
    )
    bpy.types.Scene.zip_asset_importer_replace_materials = BoolProperty(
        name="Replace Materials",
        description="Replace mesh materials with the generated PBR material",
        default=True,
    )
    bpy.types.Scene.zip_asset_importer_use_ao_cavity = BoolProperty(
        name="Multiply AO/Cavity",
        description="Multiply AO and cavity maps into Base Color in addition to loading them as texture nodes",
        default=True,
    )
    bpy.types.Scene.zip_asset_importer_shade_smooth = BoolProperty(
        name="Shade Smooth",
        description="Shade imported meshes smooth after import",
        default=True,
    )
    bpy.types.Scene.zip_asset_importer_focus_view = BoolProperty(
        name="Frame Imported",
        description="Frame the imported model in the active 3D View",
        default=True,
    )


def unregister():
    for prop_name in (
        "zip_asset_importer_zip_path",
        "zip_asset_importer_import_all_models",
        "zip_asset_importer_replace_materials",
        "zip_asset_importer_use_ao_cavity",
        "zip_asset_importer_shade_smooth",
        "zip_asset_importer_focus_view",
    ):
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
