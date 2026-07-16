# Asset Importer for Blender

**Drag a downloaded asset straight into Blender — model imported, PBR material built, done.**

Stop unzipping downloads and plugging in texture maps by hand. Point Asset Importer at a `.zip` from **Fab**, **Quixel Megascans**, **Sketchfab**, **Poly Haven**, **CGTrader**, **TurboSquid**, **BlenderKit**, or **itch.io** — or at a whole folder of already-extracted assets — hit one button, and it will find the best 3D file, import it, auto-detect every texture map, and wire up a clean **Node Wrangler–style Principled BSDF** material for you.

No extracting. No hunting for the FBX. No manually plugging in normal, roughness, and displacement maps. One click for a single asset, one click for an entire library.

---

## ✨ Features

### Single ZIP import
- **One-click ZIP import** — choose the archive, press *Import ZIP Asset*, and the addon does the rest.
- **Smart model selection** — automatically scores and picks the highest-quality mesh in the archive (prefers `LOD0`/`high`, skips `proxy`, `collision`, and `low` variants). Or flip on **Import All Models** to bring in everything.
- **Safe extraction** — hardened against Zip-Slip path traversal; archives are unpacked into their own tidy asset folder next to the original `.zip`.

### Batch folder import
- **Point it at a folder, walk away** — recursively scans a root folder for `.fbx`/`.glb`/`.gltf` files (already-extracted asset libraries, marketplace downloads, whatever) and imports every one of them in sequence, with the same automatic PBR material build as a single ZIP import.
- **Live progress** — a progress bar, current-file name, elapsed time, and ETA while it runs, with a **Stop Batch Import** button to cancel mid-run.
- **Resilient** — a failure on one asset is logged and skipped rather than aborting the whole run; periodic orphan-data purging keeps memory in check across large batches.
- **Run summary** — a dismissible report of how many succeeded, failed, or were skipped, with the per-file error list.

### Auto-layout grid
- Optionally arranges every asset the batch importer brings in onto a spaced-out grid (packed by each asset's footprint, wrapping to a new row past a configurable width) instead of leaving everything stacked at the origin. Each asset keeps its authored height off the ground plane — only X/Y position is touched.

### Texture-only folder previews
- For folders that contain texture images but **no** supported 3D model (loose material scans, trim sheets, etc.), builds a PBR material from the textures and applies it to a new UV sphere so you can see and use it. Preview spheres are always grid-placed for visibility.

### Material building (shared by every import path)
- **Automatic PBR texture detection** — recognizes Base Color, Metallic, Roughness, Gloss, Specular, Normal, Bump, Height/Displacement, AO, Cavity, Emission, Alpha/Opacity, and Transmission from filename conventions used by Fab, Megascans, Poliigon, ambientCG, and more.
- **Node Wrangler–style material graph** — a tidy Principled BSDF setup with a shared Mapping + Texture Coordinate node, framed texture group, correct Non-Color color spaces, Normal/Bump chaining, and real displacement.
- **Resolution & quality aware** — when multiple resolutions are available, it favors the higher-res map (`4K` over `2K`, larger pixel dimensions, EXR/TIFF over JPG).
- **Gloss → Roughness fallback** — auto-inverts a gloss map into roughness when no roughness map exists.
- **AO / Cavity multiply** — optionally multiplies Ambient Occlusion and Cavity into Base Color for extra depth.
- **Quality-of-life toggles** — Shade Smooth on import, Replace existing materials, and Frame the imported model in the viewport.

### Wide format support
- **Meshes**: `FBX`, `GLB`/`GLTF`, `OBJ`, `USD`/`USDA`/`USDC`/`USDZ`, `Alembic (ABC)`, `Collada (DAE)`, `BLEND`, `PLY`, `STL`, and `X3D`/`WRL` for single ZIP import (batch folder import scans for `FBX`/`GLB`/`GLTF`).

---

## 📦 Installation

1. Download [`asset_importer.py`](asset_importer.py) from this repository.
2. In Blender, go to **Edit → Preferences → Add-ons → Install…** (in Blender 4.2+: the ⌄ dropdown → **Install from Disk…**).
3. Select the downloaded `asset_importer.py`.
4. Enable the checkbox next to **Import-Export: Asset Importer**.

Requires **Blender 4.0 or newer**.

> Upgrading from the old **ZIP Asset Importer** addon? Remove/disable that one first — this is a renamed, expanded replacement and installing both side by side will conflict.

---

## 🚀 Usage

Open the **3D Viewport** and press **N** to reveal the sidebar, then click the **Asset Importer** tab. The panel has two sections:

### Import a single ZIP

1. Set **ZIP** to your downloaded asset archive (e.g. the file you just grabbed from Fab).
2. Adjust options if you like:

   | Option | What it does |
   | --- | --- |
   | **Import All Models** | Import every supported mesh, not just the best one |
   | **Replace Materials** | Swap in the generated PBR material instead of appending |
   | **Multiply AO/Cavity** | Blend AO + Cavity maps into Base Color |
   | **Shade Smooth** | Smooth-shade imported meshes |
   | **Frame Imported** | Zoom the viewport to the new object |
3. Click **Import ZIP Asset**.

The archive is extracted into a folder beside the original `.zip`, the model is imported, and the material is built and applied automatically.

### Batch import a folder

1. Under **Batch Import (Folder)**, set **Root Folder** to the top of the asset library you want to bring in.
2. Optionally enable:

   | Option | What it does |
   | --- | --- |
   | **Auto-Layout Grid** | Arrange imported assets on a spaced grid instead of stacking them at the origin |
   | **Texture-Only Folders → Spheres** | Also build materials for texture-only folders and preview them on spheres |
3. Click **Start Batch Import**. Watch the progress bar, current file, and ETA; click **Stop Batch Import** to cancel.
4. When it finishes, review the summary (succeeded/failed/skipped counts and any per-file errors) and click **Dismiss**.

---

## 🧠 How texture detection works

Filenames are tokenized (handling `snake_case`, `CamelCase`, `kebab-case`, and separators), common prefixes/suffixes shared across the set are stripped, and each remaining token is matched against a dictionary of PBR map aliases. So `Rock_Cliff_2K_Normal.png`, `rockCliffBaseColor.jpg`, and `RGH_4K.exr` all land in the right socket — and when two candidates fit, the higher-resolution / higher-bit-depth one wins.

---

## 🗂️ Supported inputs at a glance

| Category | Formats |
| --- | --- |
| **Meshes (ZIP import)** | FBX · GLB · GLTF · OBJ · USD · USDA · USDC · USDZ · ABC · DAE · BLEND · PLY · STL · X3D · WRL |
| **Meshes (batch folder import)** | FBX · GLB · GLTF |
| **Textures** | PNG · JPG · JPEG · EXR · TIF · TIFF · TGA · WEBP · DDS · BMP · HDR |
| **Maps** | Base Color · Metallic · Roughness · Gloss · Specular · Normal · Bump · Displacement/Height · AO · Cavity · Emission · Alpha · Transmission |

---

## 🤝 Contributing

Issues and pull requests are welcome. If a naming convention from a marketplace isn't being detected, open an issue with a couple of example filenames and it can be added to the matcher.

## 📄 License

Released under the [MIT License](LICENSE) — free to use, modify, and distribute.

---

<sub>Keywords: blender addon, blender asset importer, blender zip importer, fab importer, fab to blender, epic fab, quixel megascans blender, sketchfab importer, batch asset import, one click import, auto pbr material, automatic material setup, principled bsdf, node wrangler, texture auto import, fbx importer, gltf importer, obj importer, usd importer, alembic, 3d asset importer, pbr texture loader, blender 4.0, blender 4.2, import-export addon, batch import, material generator, auto layout, asset arranger, ambientcg, poly haven, poliigon, turbosquid, cgtrader, blenderkit.</sub>
