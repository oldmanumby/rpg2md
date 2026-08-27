# RPG2MD — RPG PDF to Markdown Converter

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Docling v2](https://img.shields.io/badge/Docling-v2.120%2B-green.svg)](https://github.com/docling-project/docling)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: macOS / Linux / Windows](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

**RPG2MD** is an automated conversion tool built to transform tabletop roleplaying game (TTRPG) rulebooks, adventure modules, and supplements into clean, structured **GitHub-flavored Markdown**.

Powered by **Docling v2** and **IBM Granite Docling (258M VLM)**, it solves the most common PDF conversion hurdles in tabletop gaming books:
- **Self-Contained Book Folders**: Every converted PDF generates its own dedicated project folder (`_output/<DocName>/`) with `_assets/` and `<DocName>.md` for 100% portability (ideal for Obsidian, Zed, static site generators, and web publishing).
- **Dual Pipeline Architecture**: Choose between the blazing-fast **Modular Pipeline** (for modern digital rulebooks) or the end-to-end **VLM Passover** via IBM Granite Docling 258M (for tricky scans, warped pages, and complex visual sidebars).
- **Preset Management System**: Save your customized wizard settings as named `.json` presets in `./presets/` and recall them instantly via wizard or CLI flag.
- **Automated Model Preflight**: Built-in models (**Granite Docling 258M**, **SmolVLM**, **EasyOCR**) are automatically verified in `~/.cache/huggingface/hub/` and downloaded on-demand with visual status rather than pausing silently.
- **Multi-Column Layout Preservation**: Accurately tracks reading flow across 2-column and 3-column layouts without jumping across gutters.
- **Dynamic Image Naming**: Automatically names extracted images sequentially (`img_001.png`), with custom prefixes (`dnd5e_001.png`), or based on the **preceding section heading** (`combat_rules_001.png`, `ancient_red_dragon_001.png`).
- **AI-Powered Image Descriptions (Alt-Text)**: Automatically generates concise 5-word Markdown image alt-text using built-in local models (**SmolVLM-256M**) or local Vision LLM endpoints (**Qwen2.5-VL**, **DeepSeek-OCR-2**).
- **Multi-Engine OCR**: Seamlessly switch between Native Digital Text (0% error rate), **Apple Vision** (M2/M3 Neural Engine), **Docling RapidOCR**, **EasyOCR** (for vintage/weathered scans), and **Tesseract OCR**.
- **Complex Table & Stat Block Parsing**: Uses IBM TableFormer and DocTags OTSL vocabulary for multi-line wrapped cells, spell progression charts, and monster stat blocks.
- **Continuous Multi-Batch Conversion**: Interactive post-job continuation loop allows converting multiple PDFs or folders consecutively with retained or adjusted settings without restarting the script.

---

## 📁 Directory Structure

```text
rpg2md/
├── _input/                   # Drop your PDF files here
├── _output/                  # Generated self-contained project folders
│   └── <DocName>/            # Dedicated book project folder
│       ├── _assets/          # Isolated book assets (img_001.png, combat_001.png, ...)
│       └── <DocName>.md      # Converted Markdown document
├── presets/                  # Saved conversion presets (*.json)
│   ├── digital_rulebook.json
│   └── vintage_scans.json
├── tests/                    # Automated unit tests
│   └── test_rpg2md.py
├── .venv/                    # Virtual environment
├── requirements.txt          # Project dependencies
├── rpg2md.py                 # Main conversion script
├── LICENSE                   # MIT License
├── CHANGELOG.md              # Release history
└── README.md                 # Documentation & usage guide
```

---

## 📦 Installation & Setup

### 1. Prerequisites
- **Python 3.10 or higher** (Python 3.12 recommended).
- Git installed on your system.

> [!NOTE]
> `pip install -r requirements.txt` installs everything needed for all conversion modes, including the OCR engines. Be aware that **EasyOCR pulls in PyTorch (~2 GB)** even if you never use OCR. If you only need digital-text PDFs and want a lighter install, you can skip it by installing Docling alone:
> ```bash
> pip install "docling>=2.120.0"
> ```
> Optional extras: **Tesseract OCR** requires the [Tesseract engine](https://github.com/tesseract-ocr/tesseract) installed at the system level (e.g. `brew install tesseract` on macOS or `apt install tesseract-ocr` on Debian/Ubuntu); **Apple Silicon MLX acceleration** can be added afterwards with `pip install mlx-vlm`.

### 2. Clone the Repository
```bash
git clone https://github.com/your-username/rpg2md.git
cd rpg2md
```

### 3. Create a Virtual Environment & Install Dependencies

#### On macOS & Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### On Windows:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4. (Optional) Apple Silicon MLX Acceleration
For ultra-fast neural inference on Apple Silicon Macs:
```bash
pip install mlx-vlm
```

### 5. (Optional) Pre-download Built-in AI Models for Offline Use
```bash
./.venv/bin/python rpg2md.py --download-models
```
*(On Windows: `.\.venv\Scripts\python rpg2md.py --download-models`)*

---

## 🚀 Quick Start

1. Drop your `.pdf` files into the `_input/` folder.
2. Run the script:

```bash
./.venv/bin/python rpg2md.py
```
*(On Windows: `.\.venv\Scripts\python rpg2md.py`)*

> [!TIP]
> Running the script with no arguments automatically launches the **Interactive Setup Wizard**. To run directly with a saved preset or CLI flags, pass arguments (e.g. `./.venv/bin/python rpg2md.py --preset digital_rulebook`).

---

## 🧙 Interactive Setup Wizard

```text
============================================================
             RPG2MD - Interactive Setup Wizard              
============================================================

Select Wizard Mode:
[1] Standard Setup (Essential settings)
[2] Advanced Setup (More granular control)
[3] Load a Saved Preset (from ./presets/)
Choice [DEFAULT=1]: 

Select Pipeline Engine:
[1] Modular Pipeline (Fastest vector text + OCR; best for modern PDFs)
[2] VLM Passover (End-to-end neural vision; best for complex/legacy/scans)
Choice [DEFAULT=1]: 

Image Resolution Scale:
[1] 3.0x Higher Resolution
[2] 2.0x Standard Resolution
[3] 1.0x Lower-Resolution
[4] Custom Scale Factor
[5] Discard all images
Choice [DEFAULT=1]: 
   ↳ (If [4] Custom is chosen): Enter Custom Scale Factor [DEFAULT=3.0]: 

Vision AI for Image Descriptions (Alt-Text):
[1] SmolVLM-256M (Fastest built-in model)
[2] Local LLM via Endpoint (e.g. Qwen2.5-VL)
[3] None: Standard `![Image](link)`
Choice [DEFAULT=1]: 
   ↳ (If [2] Local LLM is chosen):
       Local VLM Endpoint URL (e.g. http://127.0.0.1:8888/v1): 
       Local Model ID (e.g. Qwen2.5-VL-7B-Instruct-GGUF): 
       Max Words per Alt-Text [DEFAULT=5]: 

OCR Engine:  (Shown for Standard Pipeline)
[1] None (Digital text; fastest, most accurate for modern PDFs)
[2] Docling Default (Built-in RapidOCR; good for majority of PDFs)
[3] Apple Vision Framework (Neural Engine; better OCR accuracy)
[4] EasyOCR (Built-in PyTorch; best for legacy PDFs/scans)
[5] Tesseract OCR (Open source OCR engine)
Choice [DEFAULT=1]: 

------------------------------------------------------------
-- Advanced Settings (Only shown if [2] Advanced was chosen)
------------------------------------------------------------

Enable automatic heading hierarchy (#, ##, ###)? (Y/n): 

Image Naming Scheme:
[1] "img_001.png"
[2] "<YourPrefix>_001.png"
[3] "<PreviousHeading>_001.png"
Choice [DEFAULT=1]: 
   ↳ (If [2] Custom is chosen): Enter Custom Prefix [DEFAULT=img]: 

Save snapshot images of tables as assets? (y/N): 

Force full-page OCR across all pages? (y/N):  (Only shown if an OCR engine was selected)

Page Range (e.g. '1-10', '5', or Enter for All) [DEFAULT=all]: 

Table Recognition Mode:  (Standard Pipeline)
[1] Accurate (IBM TableFormer; best for complex tables)
[2] Fast (Grid matching)
[3] None (Treat tables as text)
Choice [DEFAULT=1]: 

Compute Accelerator Device:
[1] Auto (Detect Best Available)
[2] Apple Silicon MPS (Metal Performance Shaders)
[3] CPU
Choice [DEFAULT=1]: 

Worker CPU Threads [Auto Detected=??]: 

Save these settings as a reusable preset? (y/N): 
   ↳ (If 'y'): Enter Preset Name [DEFAULT=my_preset]: 
   ↳ Enter Optional Description: 

------------------------------------------------------------
-- Final Confirmation
-------------------------------------------------------------

Overwrite existing files in _output/? (y/N): 

============================================================
Configuration complete! Starting conversion...
============================================================
  ✔ Finished 'Rulebook.pdf' in 14.2s | Pages: 12 | Images: 8
  📁 Project  : _output/Rulebook/
  📄 Markdown : _output/Rulebook/Rulebook.md
  🖼️  Assets   : _output/Rulebook/_assets/

============================================================
🎉 All done! Successfully converted 1/1 document(s) in 14.2s.
============================================================

Do you wish to run another conversion? (y/N): 
   ↳ (If 'y'): Use the same settings? (Y/n): 
```

---

## 💾 Preset Management System

Save time on repeated conversions by creating named presets:

### 1. Saving a Preset
When you finish configuring your settings in the interactive wizard, answer `y` to:
```text
Save these settings as a reusable preset? (y/N): y
   ↳ Enter Preset Name [DEFAULT=my_preset]: dnd5e_custom
   ↳ Enter Optional Description: High-res conversion for 5E adventure modules
```
Your settings will be saved to `./presets/dnd5e_custom.json`.

### 2. Loading a Preset via Wizard
Choose **`[3] Load a Saved Preset`** at the top of the wizard to pick from your list of saved presets.

### 3. Loading a Preset via CLI (1-Click Run)
Run directly from terminal without prompts:
```bash
./.venv/bin/python rpg2md.py --preset digital_rulebook
./.venv/bin/python rpg2md.py --preset vintage_scans
```

---

## 🛠️ Command Line Interface (CLI) Reference

```bash
./.venv/bin/python rpg2md.py [OPTIONS]
```

| Flag | Type / Choices | Default | Description |
| :--- | :--- | :---: | :--- |
| `-i`, `--interactive` | *flag* | `False` | Explicitly launch the interactive wizard. |
| `-v`, `--version` | *flag* | — | Show program version number and exit. |
| `--preset <name>` | *string* | `None` | Load settings from a named preset in `./presets/`. |
| `--download-models` | *flag* | `False` | Download all built-in AI models to local cache and exit. |
| `--file <filename>` | *string* | `None` | Process only a specific PDF in `_input/`. |
| `--pages <range>` | *string* | `None` | Page range to convert (e.g. `--pages 1-10` or `--pages 5`). |
| `--pipeline` | `modular` \| `granite` \| `vlm` | `modular` | `modular` uses fast vector parsing + TableFormer; `granite` uses IBM Granite Docling 258M VLM. |
| `--overwrite` | *flag* | `False` | Overwrite existing `.md` files and asset folders. |
| `--scale <float>` | *float* | `3.0` | Image extraction resolution scale (1.0× to 4.0×). |
| `--no-images` | *flag* | `False` | Disable image/map extraction entirely (text and tables only). |
| `--naming-scheme` | `sequential` \| `custom` \| `heading` | `sequential` | `heading` dynamically names images after the preceding section header (e.g. `combat_rules_001.png`). |
| `--custom-prefix` | *string* | `img` | Custom prefix if `--naming-scheme custom` is selected. |
| `--vlm` | `smolvlm` \| `local` \| `none` | `smolvlm` | Vision AI model for Markdown alt-text descriptions. |
| `--vlm-url` | *string* | `http://127.0.0.1:8888/v1` | OpenAI-compatible API URL for local vision inference. |
| `--vlm-model` | *string* | `Qwen2.5-VL-7B-Instruct-GGUF` | Model name for local vision inference. |
| `--vlm-words` | *integer* | `5` | Maximum word count for generated image alt-text. |
| `--ocr` | `none` \| `docling` \| `apple` \| `easyocr` \| `tesseract` | `none` | OCR backend engine (for Modular pipeline). |
| `--ocr-scale` | *float* | `3.0` | Raster upscaling factor before OCR processing. |
| `--force-ocr` | *flag* | `False` | Force full-page raster OCR across every page. |
| `--table-mode` | `accurate` \| `fast` \| `none` | `accurate` | `accurate` uses IBM TableFormer for multi-column wrapped stat blocks. |
| `--table-images` | *flag* | `False` | Save cropped visual snapshot PNGs of tables. |
| `--no-headings` | *flag* | `False` | Disable automatic heading hierarchy detection (`#`, `##`, `###`). |
| `--device` | `auto` \| `mps` \| `cpu` \| `cuda` | `auto` | Compute device (`mps` for Apple Silicon GPU, `cuda` for NVIDIA GPU, `cpu` for generic CPU). |
| `--threads` | *integer* | *Auto* | CPU worker threads (auto-detects hardware topology). |

---

## 🧪 Running Automated Unit Tests

```bash
./.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📖 Common Conversion Recipes

### 1. Modern Digital Books (Fastest Execution)
```bash
./.venv/bin/python rpg2md.py --preset digital_rulebook
```

### 2. End-to-End Neural Vision on Weathered Scans (Granite Docling VLM)
```bash
./.venv/bin/python rpg2md.py --preset vintage_scans
```

### 3. Heading-Based Image Naming
Names all artwork after the section it appears under (e.g. `combat_rules_001.png`, `ancient_red_dragon_001.png`):
```bash
./.venv/bin/python rpg2md.py --naming-scheme heading
```

### 4. Convert a Specific Chapter or Page Range (e.g. Pages 10 to 25)
```bash
./.venv/bin/python rpg2md.py --file "Rulebook.pdf" --pages 10-25
```

### 5. Apple Silicon Neural OCR (macOS)
```bash
./.venv/bin/python rpg2md.py --ocr apple --scale 3.0
```

### 6. Local Vision AI for Fantasy Image Alt-Text (Qwen2.5-VL)
```bash
./.venv/bin/python rpg2md.py --vlm local --vlm-model "Qwen2.5-VL-7B-Instruct-GGUF" --vlm-words 5
```

---

## 🧠 OCR & Vision Models: Architecture & Cache Guide

| Engine / Model | Type | Cache Location | How It Is Managed |
| :--- | :--- | :--- | :--- |
| **IBM Granite Docling (258M)** | End-to-End Vision Model | `~/.cache/huggingface/hub/models--ibm-granite--granite-docling-258M/` | Verified & downloaded on first run via `huggingface_hub`. |
| **SmolVLM-256M** | Compact Vision Model | `~/.cache/huggingface/hub/models--HuggingFaceTB--SmolVLM-256M-Instruct/` | Verified & downloaded on first run for image alt-text. |
| **Docling Layout Heron** | CNN Layout Detector | `~/.cache/huggingface/hub/models--docling-project--docling-layout-heron/` | Auto-cached by Docling for multi-column parsing. |
| **EasyOCR** | PyTorch (CRAFT + ResNet) | `~/.EasyOCR/model/` | PyTorch neural network weights for legacy scans. |
| **Tesseract OCR** | Open Source OCR Engine | System binaries (`tesseract`) | Standard OCR engine for non-scanned layout text. |
| **Apple Vision (`ocrmac`)** | macOS Native Framework | **0 MB** (Built into macOS) | Native Apple Silicon Neural Engine execution. |
| **DeepSeek-OCR-2 / Qwen2.5-VL** | Frontier VLM (GGUF) | User-managed endpoint | Served locally via **LM Studio / Unsloth / `llama-server`** at `http://127.0.0.1:8888/v1`. |

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/oldmanumby/rpg2md/issues).

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
