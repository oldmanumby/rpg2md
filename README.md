# RPG2MD — RPG PDF to GitHub-Flavored Markdown Converter

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Docling v2](https://img.shields.io/badge/Docling-v2.120%2B-green.svg)](https://github.com/docling-project/docling)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: macOS / Linux / Windows](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

**RPG2MD** is an automated conversion tool built to transform tabletop roleplaying game (TTRPG) rulebooks, adventure modules, and supplements into clean, structured **GitHub-flavored Markdown**.

Powered by **[Docling v2](https://docling-project.github.io/docling)**, it solves common PDF conversion issues in tabletop gaming books:
- **Multi-Column Layout Preservation**: Automatically tracks reading flow across 2-column and 3-column page layouts without jumping across gutters.
- **High-Resolution Asset Extraction**: Crops battle maps, character portraits, item sketches, and diagrams into standalone high-res images ($1.0\times$ to $4.0\times$ retina scale).
- **Dynamic Image Naming**: Automatically names extracted images sequentially (`img_001.png`), with custom prefixes (`dnd5e_001.png`), or based on the **preceding section heading** (`combat_rules_001.png`, `ancient_red_dragon_001.png`).
- **AI-Powered Image Descriptions (Alt-Text)**: Automatically generates concise 5-word Markdown image alt-text using built-in local models (**SmolVLM-256M**) or local Vision LLM endpoints (**Qwen2.5-VL**, **DeepSeek-OCR-2**).
- **Multi-Engine OCR**: Seamlessly switch between Native Digital Text (0% error rate), **Apple Vision** (M2/M3 Neural Engine), **Docling RapidOCR**, **EasyOCR** (for vintage/weathered scans), and Local Neural Endpoints.
- **Complex Table & Stat Block Parsing**: Uses IBM TableFormer for multi-line wrapped cells, spell progression charts, and stat blocks.

---

## 📁 Directory Structure

```text
rpg2md/
├── _input/              # Drop your PDF files here
├── _output/             # Generated .md files and asset directories
│   └── _assets/         # Cropped high-resolution images & maps
│       └── <DocName>/   # Isolated per-document asset folder (img_001.png, ...)
├── .venv/               # Virtual environment (recommended)
├── requirements.txt     # Project dependencies
├── rpg2md.py            # Main conversion script
├── LICENSE              # MIT License
└── README.md            # Documentation & usage guide
```

---

## 📦 Installation & Setup

### 1. Prerequisites
- **Python 3.10 or higher** (Python 3.12 recommended).
- Git installed on your system.

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

---

## 🚀 Quick Start

1. Drop your `.pdf` files into the `_input/` folder.
2. Run the script:

```bash
./.venv/bin/python rpg2md.py
```
*(On Windows: `.\.venv\Scripts\python rpg2md.py`)*

> **Default Settings Applied:**
> - **Page Range:** All Pages.
> - **Image Resolution:** 3.0x High-Res (retina quality for maps and artwork).
> - **Asset Organization:** Isolated per-document folders (`_output/_assets/<DocName>/img_001.png`).
> - **Image Naming:** Sequential (`img_001.png`, `img_002.png`...).
> - **Vision AI:** Built-in `SmolVLM-256M` generating 5-word max alt-text.
> - **OCR:** None (direct digital vector text extraction — fastest with 100% accuracy for digital PDFs).

---

## 🧙 Interactive Setup Wizard

If you want to configure settings interactively before converting, launch the numbered setup wizard:

```bash
./.venv/bin/python rpg2md.py -i
```
*(On Windows: `.\.venv\Scripts\python rpg2md.py -i`)*

The wizard guides you through:
```text
Select Wizard Mode:
[1] Standard Setup (Essential settings) [DEFAULT]
[2] Advanced Setup (More granular control)
Choice [ENTER=1]:

Image Resolution Scale:
[1] 3.0x Higher Resolution [DEFAULT]
[2] 2.0x Standard Resolution
[3] 1.0x Lower-Resolution
[4] Custom Scale Factor
[5] Discard all images
Choice [1]:

Vision AI for Image Descriptions (Alt-Text):
[1] SmolVLM-256M (Fastest built-in model) [DEFAULT]
[2] Local LLM via Endpoint (e.g. Qwen2.5-VL)
[3] None: Standard `![Image](link)`
Choice [1]:

OCR Engine:
[1] None (Digital text; fastest, most accurate for modern PDFs) [DEFAULT]
[2] Docling Default (Built-in RapidOCR; good for majority of PDFs)
[3] Apple Vision Framework (Neural Engine; better OCR accuracy)
[4] EasyOCR (Built-in PyTorch; best for legacy PDFs/scans)
[5] Local LLM via Endpoint (e.g. DeepSeek-OCR)
Choice [1]:

-- Advanced Settings --

Enable automatic heading hierarchy (#, ##, ###)? (Y/n):

Asset Directory Organization:
[1] Seperate Assets Folder (_output/_assets/<DocName>/img_001.png) [DEFAULT]
[2] Shared Assets Folder (_output/_assets/<DocName>_001.png)
Choice [1]:

Image Naming Scheme:
[1] "img_001.png"
[2] "<YourPrefix>_001.png"
[3] "<PreviousHeading>_001.png"
Choice [1]:

Save snapshot images of tables as assets? (y/N):

Force full-page OCR across all pages? (y/N):

Page Range (e.g. '1-10', '5', or Enter for All) [All]:

Table Recognition Mode:
[1] Accurate (IBM TableFormer; best for stats & classes) [DEFAULT]
[2] Fast (Grid matching)
[3] None (Treat tables as text)
Choice [1]:

Compute Accelerator Device:
[1] Auto (Detect Best Available) [DEFAULT]
[2] Apple Silicon MPS (Metal Performance Shaders)
[3] CPU
Choice [1]:

Worker CPU Threads [8]:

Overwrite existing files in _output/? (y/N):
```

---

## 🛠️ Command Line Interface (CLI) Reference

You can pass command-line arguments directly to automate batch jobs:

```bash
./.venv/bin/python rpg2md.py [OPTIONS]
```

| Flag | Type / Choices | Default | Description |
| :--- | :--- | :---: | :--- |
| `-i`, `--interactive` | *flag* | `False` | Launch the numbered interactive wizard. |
| `--file <filename>` | *string* | `None` | Process only a specific PDF file in `_input/`. |
| `--pages <range>` | *string* | `None` | Page range to convert (e.g. `--pages 1-10` or `--pages 5`). |
| `--overwrite` | *flag* | `False` | Overwrite existing `.md` files and asset folders. |
| `--scale <float>` | *float* | `3.0` | Image extraction resolution scale ($1.0\times$ to $4.0\times$). |
| `--no-images` | *flag* | `False` | Disable image/map extraction entirely (text and tables only). |
| `--asset-layout` | `per-doc` \| `shared` | `per-doc` | `per-doc` stores images in subfolders; `shared` flattens all images into `_output/_assets/`. |
| `--naming-scheme` | `sequential` \| `custom` \| `heading` | `sequential` | `heading` dynamically names images after the preceding section header (e.g. `combat_rules_001.png`). |
| `--custom-prefix` | *string* | `img` | Custom prefix if `--naming-scheme custom` is selected. |
| `--vlm` | `smolvlm` \| `local` \| `none` | `smolvlm` | Vision AI model for Markdown alt-text. |
| `--vlm-url` | *string* | `http://127.0.0.1:8888/v1` | OpenAI-compatible API URL for local vision inference. |
| `--vlm-model` | *string* | `Qwen2.5-VL-7B-Instruct-GGUF` | Model name for local vision inference. |
| `--vlm-words` | *integer* | `5` | Maximum word count for generated image alt-text. |
| `--ocr` | `none` \| `docling` \| `apple` \| `easyocr` \| `tesseract` \| `local` | `none` | OCR engine to use. |
| `--ocr-url` | *string* | `http://127.0.0.1:8888/v1` | OpenAI-compatible API URL for local OCR models. |
| `--ocr-model` | *string* | `deepseek-ocr-2` | Model name for local OCR inference. |
| `--ocr-scale` | *float* | `3.0` | Raster upscaling factor before OCR processing. |
| `--force-ocr` | *flag* | `False` | Force full-page raster OCR across every page (for scanned image PDFs). |
| `--table-mode` | `accurate` \| `fast` \| `none` | `accurate` | `accurate` uses IBM TableFormer for multi-column wrapped stat blocks. |
| `--table-images` | *flag* | `False` | Save cropped visual snapshot PNGs of tables into `_assets/`. |
| `--no-headings` | *flag* | `False` | Disable automatic heading hierarchy detection (`#`, `##`, `###`). |
| `--device` | `auto` \| `mps` \| `cpu` | `auto` | Compute device (`mps` for Apple Silicon GPU, `cpu` for generic CPU). |
| `--threads` | *integer* | `8` | Parallel CPU worker threads. |

---

## 📖 Common Conversion Recipes

### 1. Modern Digital Books (Fastest Execution)
```bash
./.venv/bin/python rpg2md.py
```

### 2. Heading-Based Image Naming
Names all artwork after the section it appears under (e.g. `combat_rules_001.png`, `ancient_red_dragon_001.png`):
```bash
./.venv/bin/python rpg2md.py --naming-scheme heading
```

### 3. Convert a Specific Chapter or Page Range (e.g. Pages 10 to 25)
```bash
./.venv/bin/python rpg2md.py --file "Rulebook.pdf" --pages 10-25
```

### 4. Apple Silicon Neural OCR (macOS)
```bash
./.venv/bin/python rpg2md.py --ocr apple --scale 3.0
```

### 5. Weathered / Vintage Scans (OSR, AD&D 1E/2E, Zines)
```bash
# Using EasyOCR with full-page raster scanning
./.venv/bin/python rpg2md.py --ocr easyocr --force-ocr

# Using Local DeepSeek-OCR GGUF via llama-server / LM Studio
./.venv/bin/python rpg2md.py --ocr local --ocr-model "deepseek-ocr-2" --force-ocr
```

### 6. Local Vision AI for Fantasy Image Alt-Text (Qwen2.5-VL)
```bash
./.venv/bin/python rpg2md.py --vlm local --vlm-model "Qwen2.5-VL-7B-Instruct-GGUF" --vlm-words 5
```

---

## 🧠 OCR & Vision Models: Architecture Guide

| Engine / Model | Type | How It Runs & Where It Is Installed |
| :--- | :--- | :--- |
| **Docling Default (RapidOCR)** | ONNX Computer Vision | Pre-installed via `docling`. Fast baseline for standard text. |
| **Apple Vision (`ocrmac`)** | macOS Native Vision Framework | Accelerated on Apple Silicon Neural Engine (macOS only). |
| **EasyOCR** | PyTorch (CRAFT + ResNet) | Python library for weathered, parchment, or noisy scans. |
| **SmolVLM-256M** | Compact Vision-Language Model | Automatic via Hugging Face `transformers` (weights download on first use). |
| **DeepSeek-OCR-2 / Qwen2.5-VL** | Frontier Vision-Language Model | Served locally via **LM Studio / Unsloth / `llama-server`** at `http://127.0.0.1:8888/v1`. |

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/your-username/rpg2md/issues) if you have suggestions for improving table parsing or new RPG layout heuristics.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
