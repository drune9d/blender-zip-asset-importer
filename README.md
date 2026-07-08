# ZIP Asset Importer for Blender

**Drag a downloaded `.zip` straight into Blender — model imported, PBR material built, done.**

Stop unzipping downloads by hand. Point ZIP Asset Importer at any asset archive from **Fab**, **Quixel Megascans**, **Sketchfab**, **Poly Haven**, **CGTrader**, **TurboSquid**, **BlenderKit**, or **itch.io**, hit one button, and it will extract the archive, find the best 3D file inside, import it, auto-detect every texture map, and wire up a clean **Node Wrangler–style Principled BSDF** material for you.

No extracting. No hunting for the FBX. No manually plugging in normal, roughness, and displacement maps. One click.

---

## ✨ Features

- **One-click ZIP import** — choose the archive, press *Import ZIP Asset*, and the addon does the rest.
- **Smart model selection** — automatically scores and picks the highest-quality mesh in the archive (prefers `LOD0`/`high`, skips `proxy`, `collision`, and `low` variants). Or flip on **Import All Models** to bring in everything.
- **Wide format support** — `FBX`, `GLB`/`GLTF`, `OBJ`, `USD`/`USDA`/`USDC`/`USDZ`, `Alembic (ABC)`, `Collada (DAE)`, `BLEND`, `PLY`, `STL`, and `X3D`/`WRL`.
- **Automatic PBR texture detection** — recognizes Base Color, Metallic, Roughness, Gloss, Specular, Normal, Bump, Height/Displacement, AO, Cavity, Emission, Alpha/Opacity, and Transmission from filename conventions used by Fab, Megascans, Poliigon, ambientCG, and more.
- **Node Wrangler–style material graph** — a tidy Principled BSDF setup with a shared Mapping + Texture Coordinate node, framed texture group, correct Non-Color color spaces, Normal/Bump chaining, and real displacement.
- **Resolution & quality aware** — when an archive ships multiple resolutions, it favors the higher-res map (`4K` over `2K`, larger pixel dimensions, EXR/TIFF over JPG).
- **Gloss → Roughness fallback** — auto-inverts a gloss map into roughness when no roughness map exists.
- **AO / Cavity multiply** — optionally multiplies Ambient Occlusion and Cavity into Base Color for extra depth.
- **Quality-of-life toggles** — Shade Smooth on import, Replace existing materials, and Frame the imported model in the viewport.
- **Safe extraction** — hardened against Zip-Slip path traversal; archives are unpacked into their own tidy asset folder next to the original `.zip`.

---

## 📦 Installation

1. Download [`zip_asset_importer.py`](zip_asset_importer.py) from this repository.
2. In Blender, go to **Edit → Preferences → Add-ons → Install…** (in Blender 4.2+: the ⌄ dropdown → **Install from Disk…**).
3. Select the downloaded `zip_asset_importer.py`.
4. Enable the checkbox next to **Import-Export: ZIP Asset Importer**.

Requires **Blender 4.0 or newer**.

---

## 🚀 Usage

1. Open the **3D Viewport** and press **N** to reveal the sidebar.
2. Click the **ZIP Import** tab.
3. Set **ZIP** to your downloaded asset archive (e.g. the file you just grabbed from Fab).
4. Adjust options if you like:
   | Option | What it does |
   | --- | --- |
   | **Import All Models** | Import every supported mesh, not just the best one |
   | **Replace Materials** | Swap in the generated PBR material instead of appending |
   | **Multiply AO/Cavity** | Blend AO + Cavity maps into Base Color |
   | **Shade Smooth** | Smooth-shade imported meshes |
   | **Frame Imported** | Zoom the viewport to the new object |
5. Click **Import ZIP Asset**. 🎉

The archive is extracted into a folder beside the original `.zip`, the model is imported, and the material is built and applied automatically.

---

## 🧠 How texture detection works

Filenames are tokenized (handling `snake_case`, `CamelCase`, `kebab-case`, and separators), common prefixes/suffixes shared across the set are stripped, and each remaining token is matched against a dictionary of PBR map aliases. So `Rock_Cliff_2K_Normal.png`, `rockCliffBaseColor.jpg`, and `RGH_4K.exr` all land in the right socket — and when two candidates fit, the higher-resolution / higher-bit-depth one wins.

---

## 🗂️ Supported inputs at a glance

| Category | Formats |
| --- | --- |
| **Meshes** | FBX · GLB · GLTF · OBJ · USD · USDA · USDC · USDZ · ABC · DAE · BLEND · PLY · STL · X3D · WRL |
| **Textures** | PNG · JPG · JPEG · EXR · TIF · TIFF · TGA · WEBP · DDS · BMP · HDR |
| **Maps** | Base Color · Metallic · Roughness · Gloss · Specular · Normal · Bump · Displacement/Height · AO · Cavity · Emission · Alpha · Transmission |

---

## 🤝 Contributing

Issues and pull requests are welcome. If a naming convention from a marketplace isn't being detected, open an issue with a couple of example filenames and it can be added to the matcher.

## 📄 License

Released under the [MIT License](LICENSE) — free to use, modify, and distribute.

---

<sub>Keywords: blender addon, blender zip importer, fab importer, fab to blender, epic fab, quixel megascans blender, sketchfab importer, one click import, auto pbr material, automatic material setup, principled bsdf, node wrangler, texture auto import, fbx importer, gltf importer, obj importer, usd importer, alembic, 3d asset importer, pbr texture loader, blender 4.0, blender 4.2, import-export addon, batch import, material generator, ambientcg, poly haven, poliigon, turbosquid, cgtrader, blenderkit.</sub>
