#!/usr/bin/env python3
"""
rpg2md.py - RPG PDF to GitHub-Flavored Markdown Converter
Powered by Docling v2, IBM Granite Docling VLM, Apple Vision, and Local VLMs.

Converts tabletop RPG PDFs in `_input/` to clean Markdown in `_output/<DocName>/`,
extracting high-res images into `_output/<DocName>/_assets/` with AI alt-text.
"""

import os
import sys

# Silence noisy PyTorch Dynamo and low-level C++ tracing warnings before importing libraries
os.environ["TORCHDYNAMO_DISABLE"] = "1"
os.environ["TORCH_CPP_LOG_LEVEL"] = "ERROR"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import argparse
import base64
import html
import itertools
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__version__ = "1.3.3"

# Base directory anchoring (resolves reliably regardless of current working directory)
BASE_DIR = Path(__file__).resolve().parent

# Target logging & warning suppression on third-party libraries
warnings.filterwarnings("ignore", module="transformers")
warnings.filterwarnings("ignore", module="torch")
warnings.filterwarnings("ignore", module="docling")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
logging.getLogger("docling").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# Docling Imports
from docling.datamodel import vlm_model_specs
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorOptions,
    EasyOcrOptions,
    HeadingHierarchyOptions,
    OcrMacOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TableFormerMode,
    TableStructureOptions,
    TesseractOcrOptions,
    VlmPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.pipeline.vlm_pipeline import VlmPipeline
from docling_core.types.doc import ImageRefMode


# ---------------------------------------------------------------------------
# Hardware & Environment Detection
# ---------------------------------------------------------------------------

def get_optimal_threads() -> int:
    """Detect available CPU cores and calculate optimal worker threads."""
    cores = os.cpu_count() or 4
    return max(1, cores - 2) if cores > 4 else cores


def get_pdf_page_count(pdf_path: Path) -> int:
    """Quickly read total page count of a PDF file using pypdfium2."""
    try:
        import pypdfium2
        doc = pypdfium2.PdfDocument(str(pdf_path))
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Model Cache Verification & Preflight Downloader
# ---------------------------------------------------------------------------

def is_hf_model_cached(repo_id: str) -> bool:
    """Check if Hugging Face repo has a valid downloaded snapshot in ~/.cache/huggingface/hub/."""
    hub_dir = Path.home() / ".cache" / "huggingface" / "hub"
    folder_name = f"models--{repo_id.replace('/', '--')}"
    target_dir = hub_dir / folder_name
    snapshots_dir = target_dir / "snapshots"
    if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
        return True
    return False


def prefetch_hf_model(repo_id: str, display_name: str, est_size_mb: int) -> bool:
    """Download Hugging Face model with visual status if not already cached in ~/.cache/huggingface/hub/."""
    if is_hf_model_cached(repo_id):
        print(f"  ✔ Model '{display_name}' verified in cache.")
        return True

    print(f"\n⬇ Downloading {display_name} weights (~{est_size_mb} MB) from Hugging Face Hub...")
    print(f"  Cache Path: ~/.cache/huggingface/hub/models--{repo_id.replace('/', '--')}/")
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=repo_id)
        print(f"  ✔ {display_name} downloaded successfully!")
        return True
    except Exception as e:
        print(f"  ⚠️ Hugging Face prefetch notice: {e}. Proceeding with dynamic loader.", file=sys.stderr)
        return False


def is_easyocr_cached() -> bool:
    """Check if EasyOCR PyTorch weights exist in ~/.EasyOCR/model/."""
    easyocr_dir = Path.home() / ".EasyOCR" / "model"
    craft_file = easyocr_dir / "craft_mlt_25k.pth"
    return craft_file.exists()


def prefetch_easyocr() -> bool:
    """Download EasyOCR PyTorch weights if missing."""
    if is_easyocr_cached():
        print("  ✔ EasyOCR weights verified in cache (~/.EasyOCR/model/).")
        return True

    print("\n⬇ Downloading EasyOCR PyTorch weights (~45 MB)...")
    try:
        import easyocr
        easyocr.Reader(["en"], verbose=False)
        print("  ✔ EasyOCR weights downloaded successfully!")
        return True
    except Exception as e:
        print(f"  ⚠️ EasyOCR prefetch notice: {e}", file=sys.stderr)
        return False


def ensure_models_ready(args: argparse.Namespace):
    """Preflight check for built-in models selected in the active configuration."""
    # 1. Granite Docling VLM
    if getattr(args, "pipeline", "modular") in ("vlm", "granite"):
        prefetch_hf_model("ibm-granite/granite-docling-258M", "IBM Granite Docling (258M VLM)", 512)

    # 2. SmolVLM-256M Alt-Text
    if not getattr(args, "no_images", False) and getattr(args, "vlm", "smolvlm") == "smolvlm":
        prefetch_hf_model("HuggingFaceTB/SmolVLM-256M-Instruct", "SmolVLM-256M", 550)

    # 3. EasyOCR
    if getattr(args, "pipeline", "modular") == "modular" and getattr(args, "ocr", "none") == "easyocr":
        prefetch_easyocr()


def download_all_builtin_models():
    """Command to download all built-in models up front for offline use."""
    print("=" * 60)
    print("          RPG2MD - Pre-downloading Built-in AI Models         ")
    print("=" * 60)
    prefetch_hf_model("ibm-granite/granite-docling-258M", "IBM Granite Docling (258M VLM)", 512)
    prefetch_hf_model("HuggingFaceTB/SmolVLM-256M-Instruct", "SmolVLM-256M", 550)
    prefetch_hf_model("docling-project/docling-layout-heron", "Docling Layout Heron", 150)
    prefetch_easyocr()
    print("\n" + "=" * 60)
    print("🎉 All built-in models are downloaded and verified in local cache!")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Preset Management
# ---------------------------------------------------------------------------

def get_presets_dir() -> Path:
    """Get the presets directory path, creating it if needed."""
    presets_dir = BASE_DIR / "presets"
    presets_dir.mkdir(parents=True, exist_ok=True)
    return presets_dir


def list_presets(presets_dir: Path) -> List[Path]:
    """List all available .json presets in the presets directory."""
    return sorted(list(presets_dir.glob("*.json")))


def save_preset(
    name: str,
    args: Any,
    presets_dir: Path,
    description: str = ""
) -> Path:
    """Serialize conversion settings into a named JSON preset file."""
    clean_name = slugify(name, max_length=50)
    preset_file = presets_dir / f"{clean_name}.json"

    preset_data = {
        "name": clean_name,
        "description": description or f"Custom preset '{clean_name}'",
        "pipeline": getattr(args, "pipeline", "modular"),
        "scale": getattr(args, "scale", 3.0),
        "no_images": getattr(args, "no_images", False),
        "naming_scheme": getattr(args, "naming_scheme", "sequential"),
        "custom_prefix": getattr(args, "custom_prefix", "img"),
        "vlm": getattr(args, "vlm", "smolvlm"),
        "vlm_url": getattr(args, "vlm_url", "http://127.0.0.1:8888/v1"),
        "vlm_model": getattr(args, "vlm_model", "Qwen2.5-VL-7B-Instruct-GGUF"),
        "vlm_words": getattr(args, "vlm_words", 5),
        "ocr": getattr(args, "ocr", "none"),
        "ocr_scale": getattr(args, "ocr_scale", 3.0),
        "force_ocr": getattr(args, "force_ocr", False),
        "table_mode": getattr(args, "table_mode", "accurate"),
        "table_images": getattr(args, "table_images", False),
        "no_headings": getattr(args, "no_headings", False),
        "device": getattr(args, "device", "auto"),
        "threads": getattr(args, "threads", get_optimal_threads()),
    }

    preset_file.write_text(json.dumps(preset_data, indent=2), encoding="utf-8")
    return preset_file


def load_preset_file(preset_path: Path, args: Any) -> Any:
    """Load JSON preset file and populate the arguments namespace."""
    if not preset_path.exists():
        print(f"Error: Preset file '{preset_path.name}' not found.", file=sys.stderr)
        return args

    try:
        data = json.loads(preset_path.read_text(encoding="utf-8"))
        for k, v in data.items():
            if hasattr(args, k) and k not in ("file", "pages", "overwrite", "interactive", "download_models"):
                setattr(args, k, v)
        return args
    except Exception as e:
        print(f"Error reading preset '{preset_path.name}': {e}", file=sys.stderr)
        return args


# ---------------------------------------------------------------------------
# Interactive Menu Utilities & Input Validation
# ---------------------------------------------------------------------------

def prompt_choice_custom(
    title: str,
    options: List[str],
    default_idx: int = 1,
    prompt_label: str = "Choice [DEFAULT=1]: "
) -> int:
    """Prompt user with formatted options and robust numeric choice validation."""
    print(f"\n{title}")
    for idx, opt in enumerate(options, 1):
        print(f"[{idx}] {opt}")

    while True:
        choice = input(prompt_label).strip()
        if not choice:
            return default_idx
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice)
        print(f"Invalid selection. Please enter a number between 1 and {len(options)}.")


def prompt_text(title: str, default: str = "", prompt_prefix: str = "") -> str:
    """Prompt user for text input with optional default value."""
    prefix = f"{prompt_prefix} " if prompt_prefix else ""
    default_str = f" [DEFAULT={default}]" if default else ""
    val = input(f"{prefix}{title}{default_str}: ").strip()
    return val if val else default


def prompt_int(title: str, default: int, prompt_prefix: str = "", min_val: int = 1) -> int:
    """Prompt user for integer input with retry validation."""
    prefix = f"{prompt_prefix} " if prompt_prefix else ""
    while True:
        val = input(f"{prefix}{title} [DEFAULT={default}]: ").strip()
        if not val:
            return default
        try:
            int_val = int(val)
            if int_val >= min_val:
                return int_val
            print(f"Please enter an integer greater than or equal to {min_val}.")
        except ValueError:
            print("Invalid input. Please enter a valid whole number.")


def prompt_float(title: str, default: float, prompt_prefix: str = "", min_val: float = 0.1) -> float:
    """Prompt user for float input with retry validation."""
    prefix = f"{prompt_prefix} " if prompt_prefix else ""
    while True:
        val = input(f"{prefix}{title} [DEFAULT={default}]: ").strip()
        if not val:
            return default
        try:
            float_val = float(val)
            if float_val >= min_val:
                return float_val
            print(f"Please enter a number greater than or equal to {min_val}.")
        except ValueError:
            print("Invalid input. Please enter a valid decimal number.")


def prompt_yn(title: str, default_yes: bool = True) -> bool:
    """Prompt user for (Y/n) or (y/N) boolean."""
    prompt_suffix = " (Y/n): " if default_yes else " (y/N): "
    choice = input(f"{title}{prompt_suffix}").strip().lower()
    if not choice:
        return default_yes
    return choice in ("y", "yes", "true", "1")


def collapse_spaced_words(text: str) -> str:
    """Collapse spaced single characters on fantasy covers (e.g. 'B A L D U R \\' S   G A T E' -> 'BALDUR\\'S GATE')."""
    text = re.sub(r"\s*'\s*", "'", text)
    text = re.sub(r'\s{2,}', ' __WB__ ', text)
    pattern = re.compile(r'\b([A-Za-z0-9])\s+(?=[A-Za-z0-9]\b)')
    prev = ""
    while prev != text:
        prev = text
        text = pattern.sub(r'\1', text)
    text = text.replace('__WB__', ' ')
    return text


def slugify(text: str, max_length: int = 35) -> str:
    """Convert heading text into a clean snake_case filename slug, handling HTML entities and spaced letters."""
    text = html.unescape(text)
    text = collapse_spaced_words(text)
    # Strip markdown and special punctuation while preserving word chars, hyphens, and existing underscores
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text).strip('_').lower()
    text = re.sub(r'[^a-z0-9_]', '', text)
    if not text:
        return "section"
    return text[:max_length].rstrip('_')


def parse_page_range(range_str: Optional[str]) -> Tuple[int, int]:
    """Parse strings like '1-10', '5', or 'all' into a (start, end) tuple. Raises ValueError on malformed syntax."""
    if not range_str or range_str.strip().lower() in ("all", "*", ""):
        return (1, 9223372036854775807)

    clean = range_str.strip()
    if "-" in clean:
        parts = clean.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid page range format '{range_str}'. Expected format like '1-10'.")
        part0 = parts[0].strip()
        part1 = parts[1].strip()
        if not (part0.isdigit() and part1.isdigit()):
            raise ValueError(f"Invalid non-numeric page range '{range_str}'.")
        start = int(part0)
        end = int(part1)
        if start < 1:
            start = 1
        return (start, max(start, end))

    if clean.isdigit():
        page = int(clean)
        if page < 1:
            page = 1
        return (page, page)

    raise ValueError(f"Invalid page specification '{range_str}'. Expected a number, range (e.g. '1-10'), or 'all'.")


# ---------------------------------------------------------------------------
# Live Terminal Heartbeat Spinner (TTY-Aware)
# ---------------------------------------------------------------------------

class LiveActivityStatus:
    """Background thread displaying animated spinner and elapsed seconds so process never looks frozen."""

    def __init__(self, message: str):
        self.message = message
        self.stop_event = threading.Event()
        self.thread = None
        self.start_time = None
        self.is_tty = sys.stdout.isatty()

    def _spin(self):
        spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
        while not self.stop_event.is_set():
            elapsed = int(time.time() - self.start_time)
            mins, secs = divmod(elapsed, 60)
            time_str = f"{mins:02d}:{secs:02d}"
            if self.is_tty:
                sys.stdout.write(f"\r  {next(spinner)} [{time_str} elapsed] {self.message}   ")
                sys.stdout.flush()
            time.sleep(0.15)

        if self.is_tty:
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()

    def __enter__(self):
        self.start_time = time.time()
        self.stop_event.clear()
        if not self.is_tty:
            print(f"  ▶ {self.message}...")
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
        return self

    def update_message(self, message: str):
        self.message = message

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        if self.thread:
            self.thread.join()


# ---------------------------------------------------------------------------
# Local Vision LLM Query (Qwen2.5-VL / DeepSeek via OpenAI API)
# ---------------------------------------------------------------------------

def query_local_vlm(image_path: Path, url: str, model: str, max_words: int = 5) -> str:
    """Send cropped image to local LLM / VLM endpoint for a concise description with diagnostic error reporting."""
    try:
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            f"Provide a concise description of this RPG art, map, or diagram in {max_words} words or less. "
            f"Output ONLY the {max_words} words without preamble or quotes."
        )

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_data}"}}
                    ]
                }
            ],
            "max_tokens": max_words * 4,
            "temperature": 0.1
        }

        endpoint = url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            caption = data["choices"][0]["message"]["content"].strip()
            caption = re.sub(r'["\[\]\n\r]', '', caption).strip()
            words = caption.split()
            if len(words) > max_words:
                caption = " ".join(words[:max_words])
            return caption
    except Exception as e:
        print(f"\n  ⚠️ Local VLM warning ({e}). Falling back to standard alt-text.", file=sys.stderr)
        return "RPG Illustration"


# ---------------------------------------------------------------------------
# Converter & Pipeline Options Builder
# ---------------------------------------------------------------------------

def build_converter(args: argparse.Namespace) -> DocumentConverter:
    """Construct DocumentConverter with either Modular Pipeline or Granite Docling VLM."""
    if args.pipeline in ("vlm", "granite"):
        vlm_opts = VlmPipelineOptions()

        use_mlx = False
        if args.device in ("mps", "auto") and sys.platform == "darwin":
            try:
                import mlx.core
                use_mlx = True
            except ImportError:
                use_mlx = False

        if use_mlx:
            vlm_opts.vlm_options = vlm_model_specs.GRANITEDOCLING_MLX
        else:
            vlm_opts.vlm_options = vlm_model_specs.GRANITEDOCLING_TRANSFORMERS

        # Clean cross-platform accelerator device handling
        vlm_opts.accelerator_options = AcceleratorOptions(
            device=args.device,
            num_threads=args.threads
        )
        vlm_opts.generate_picture_images = not args.no_images
        vlm_opts.images_scale = args.scale

        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=vlm_opts,
                )
            }
        )

    # Standard Modular Pipeline
    opts = PdfPipelineOptions()

    opts.generate_picture_images = not args.no_images
    opts.images_scale = args.scale

    if not args.no_images and args.vlm == "smolvlm":
        opts.do_picture_description = True
        opts.picture_description_options.prompt = f"Describe this RPG art or map in {args.vlm_words} words or less."
    else:
        opts.do_picture_description = False

    if args.ocr == "none":
        opts.do_ocr = False
    elif args.ocr == "docling":
        opts.do_ocr = True
        opts.ocr_options = RapidOcrOptions(
            scale=args.ocr_scale,
            force_full_page_ocr=args.force_ocr
        )
    elif args.ocr == "apple":
        opts.do_ocr = True
        opts.ocr_options = OcrMacOptions(
            scale=args.ocr_scale,
            force_full_page_ocr=args.force_ocr
        )
    elif args.ocr == "easyocr":
        opts.do_ocr = True
        opts.ocr_options = EasyOcrOptions(
            lang=["en"],
            scale=args.ocr_scale,
            force_full_page_ocr=args.force_ocr
        )
    elif args.ocr == "tesseract":
        opts.do_ocr = True
        opts.ocr_options = TesseractOcrOptions(
            lang=["eng"],
            force_full_page_ocr=args.force_ocr
        )

    if args.table_mode == "none":
        opts.do_table_structure = False
    else:
        opts.do_table_structure = True
        table_mode = TableFormerMode.ACCURATE if args.table_mode == "accurate" else TableFormerMode.FAST
        opts.table_structure_options = TableStructureOptions(mode=table_mode)
    opts.generate_table_images = args.table_images

    if not args.no_headings:
        opts.heading_hierarchy_options = HeadingHierarchyOptions(enabled=True)

    opts.accelerator_options = AcceleratorOptions(
        device=args.device,
        num_threads=args.threads
    )

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=StandardPdfPipeline,
                pipeline_options=opts
            )
        }
    )


# ---------------------------------------------------------------------------
# Interactive Setup Wizard
# ---------------------------------------------------------------------------

def run_interactive_wizard(args: argparse.Namespace) -> argparse.Namespace:
    """Walk user through interactive configuration prompts with preset support and validation."""
    print("=" * 60)
    print("             RPG2MD - Interactive Setup Wizard              ")
    print("=" * 60)

    presets_dir = get_presets_dir()
    available_presets = list_presets(presets_dir)

    # 1. Wizard Mode
    mode_options = [
        "Standard Setup (Essential settings)",
        "Advanced Setup (More granular control)"
    ]
    if available_presets:
        mode_options.append("Load a Saved Preset (from ./presets/)")

    mode_choice = prompt_choice_custom(
        "Select Wizard Mode:",
        mode_options,
        default_idx=1,
        prompt_label="Choice [DEFAULT=1]: "
    )

    # Handle Preset Loading
    if mode_choice == 3 and available_presets:
        p_choice = prompt_choice_custom(
            "Select Preset to Load:",
            [p.stem for p in available_presets],
            default_idx=1,
            prompt_label="Choice [DEFAULT=1]: "
        )
        chosen_preset = available_presets[p_choice - 1]
        args = load_preset_file(chosen_preset, args)
        print(f"\n✔ Loaded preset '{chosen_preset.stem}' successfully!")

        print("\n------------------------------------------------------------")
        print("-- Final Confirmation")
        print("------------------------------------------------------------\n")
        args.overwrite = prompt_yn("Overwrite existing files in _output/?", default_yes=False)

        print("\n" + "=" * 60)
        print("Configuration complete! Starting conversion...")
        print("=" * 60 + "\n")
        return args

    is_advanced = (mode_choice == 2)

    # 2. Pipeline Engine
    pipeline_choice = prompt_choice_custom(
        "Select Pipeline Engine:",
        [
            "Modular Pipeline (Fastest vector text + OCR; best for modern PDFs)",
            "VLM Passover (End-to-end neural vision; best for complex/legacy/scans)"
        ],
        default_idx=1,
        prompt_label="Choice [DEFAULT=1]: "
    )
    args.pipeline = "modular" if pipeline_choice == 1 else "granite"

    # 3. Image Resolution Scale
    scale_choice = prompt_choice_custom(
        "Image Resolution Scale:",
        [
            "3.0x Higher Resolution",
            "2.0x Standard Resolution",
            "1.0x Lower-Resolution",
            "Custom Scale Factor",
            "Discard all images"
        ],
        default_idx=1,
        prompt_label="Choice [DEFAULT=1]: "
    )
    if scale_choice == 1:
        args.scale = 3.0
        args.no_images = False
    elif scale_choice == 2:
        args.scale = 2.0
        args.no_images = False
    elif scale_choice == 3:
        args.scale = 1.0
        args.no_images = False
    elif scale_choice == 4:
        args.scale = prompt_float("Enter Custom Scale Factor", 3.0, prompt_prefix="   ↳")
        args.no_images = False
    elif scale_choice == 5:
        args.no_images = True

    # 4. Vision AI for Image Descriptions (Alt-Text)
    if not args.no_images:
        vlm_choice = prompt_choice_custom(
            "Vision AI for Image Descriptions (Alt-Text):",
            [
                "SmolVLM-256M (Fastest built-in model)",
                "Local LLM via Endpoint (e.g. Qwen2.5-VL)",
                "None: Standard `![Image](link)`"
            ],
            default_idx=1,
            prompt_label="Choice [DEFAULT=1]: "
        )
        if vlm_choice == 1:
            args.vlm = "smolvlm"
            args.vlm_words = 5
        elif vlm_choice == 2:
            args.vlm = "local"
            args.vlm_url = prompt_text("Local VLM Endpoint URL (e.g. http://127.0.0.1:8888/v1)", args.vlm_url, prompt_prefix="       ↳")
            args.vlm_model = prompt_text("Local Model ID (e.g. Qwen2.5-VL-7B-Instruct-GGUF)", args.vlm_model, prompt_prefix="       ↳")
            args.vlm_words = prompt_int("Max Words per Alt-Text", 5, prompt_prefix="       ↳")
        elif vlm_choice == 3:
            args.vlm = "none"
    else:
        args.vlm = "none"

    # 5. OCR Engine (Shown for Modular Pipeline)
    if args.pipeline == "modular":
        ocr_choice = prompt_choice_custom(
            "OCR Engine:  (Shown for Standard Pipeline)",
            [
                "None (Digital text; fastest, most accurate for modern PDFs)",
                "Docling Default (Built-in RapidOCR; good for majority of PDFs)",
                "Apple Vision Framework (Neural Engine; better OCR accuracy)",
                "EasyOCR (Built-in PyTorch; best for legacy PDFs/scans)",
                "Tesseract OCR (Open source OCR engine)"
            ],
            default_idx=1,
            prompt_label="Choice [DEFAULT=1]: "
        )
        ocr_map = {1: "none", 2: "docling", 3: "apple", 4: "easyocr", 5: "tesseract"}
        args.ocr = ocr_map[ocr_choice]
    else:
        args.ocr = "none"

    # 6. Advanced Settings
    if is_advanced:
        print("\n------------------------------------------------------------")
        print("-- Advanced Settings (Only shown if [2] Advanced was chosen)")
        print("------------------------------------------------------------\n")

        args.no_headings = not prompt_yn("Enable automatic heading hierarchy (#, ##, ###)?", default_yes=True)

        if not args.no_images:
            naming_choice = prompt_choice_custom(
                "Image Naming Scheme:",
                [
                    '"img_001.png"',
                    '"<YourPrefix>_001.png"',
                    '"<PreviousHeading>_001.png"'
                ],
                default_idx=1,
                prompt_label="Choice [DEFAULT=1]: "
            )
            if naming_choice == 1:
                args.naming_scheme = "sequential"
                args.custom_prefix = "img"
            elif naming_choice == 2:
                args.naming_scheme = "custom"
                args.custom_prefix = prompt_text("Enter Custom Prefix", "img", prompt_prefix="   ↳")
            elif naming_choice == 3:
                args.naming_scheme = "heading"

        args.table_images = prompt_yn("Save snapshot images of tables as assets?", default_yes=False)

        if args.pipeline == "modular" and args.ocr != "none":
            args.force_ocr = prompt_yn("Force full-page OCR across all pages?", default_yes=False)

        while True:
            page_range_input = prompt_text("Page Range (e.g. '1-10', '5', or Enter for All)", "all")
            try:
                parse_page_range(page_range_input)
                args.pages = page_range_input if page_range_input.lower() != "all" else None
                break
            except ValueError as e:
                print(f"  ⚠️ {e} Please try again.")

        if args.pipeline == "modular":
            table_choice = prompt_choice_custom(
                "Table Recognition Mode:  (Standard Pipeline)",
                [
                    "Accurate (IBM TableFormer; best for complex tables)",
                    "Fast (Grid matching)",
                    "None (Treat tables as text)"
                ],
                default_idx=1,
                prompt_label="Choice [DEFAULT=1]: "
            )
            args.table_mode = {1: "accurate", 2: "fast", 3: "none"}[table_choice]

        device_choice = prompt_choice_custom(
            "Compute Accelerator Device:",
            [
                "Auto (Detect Best Available)",
                "Apple Silicon MPS (Metal Performance Shaders)",
                "CPU"
            ],
            default_idx=1,
            prompt_label="Choice [DEFAULT=1]: "
        )
        args.device = {1: "auto", 2: "mps", 3: "cpu"}[device_choice]

        optimal_threads = get_optimal_threads()
        args.threads = prompt_int("Worker CPU Threads", optimal_threads, prompt_prefix=f"[Auto Detected={optimal_threads}]")

    # 7. Save Settings as Preset Option
    save_preset_choice = prompt_yn("\nSave these settings as a reusable preset?", default_yes=False)
    if save_preset_choice:
        preset_name = prompt_text("Enter Preset Name", "my_preset", prompt_prefix="   ↳")
        preset_desc = prompt_text("Enter Optional Description", "", prompt_prefix="   ↳")
        saved_path = save_preset(preset_name, args, presets_dir, description=preset_desc)
        print(f"  ✔ Preset saved as 'presets/{saved_path.name}'")

    # 8. Final Confirmation: Overwrite
    print("\n------------------------------------------------------------")
    print("-- Final Confirmation")
    print("------------------------------------------------------------\n")
    args.overwrite = prompt_yn("Overwrite existing files in _output/?", default_yes=False)

    print("\n" + "=" * 60)
    print("Configuration complete! Starting conversion...")
    print("=" * 60 + "\n")
    return args


# ---------------------------------------------------------------------------
# Post-Processing: Per-Document Asset Isolation & Heading-Based Naming
# ---------------------------------------------------------------------------

def postprocess_assets_and_links(
    md_path: Path,
    raw_assets_dir: Path,
    target_assets_dir: Path,
    naming_scheme: str,
    custom_prefix: str,
    vlm_mode: str,
    vlm_url: str,
    vlm_model: str,
    vlm_words: int
) -> int:
    """Isolate assets into _output/<DocName>/_assets/ and normalize links in markdown."""
    if not md_path.exists():
        return 0

    content = md_path.read_text(encoding="utf-8")
    target_assets_dir.mkdir(parents=True, exist_ok=True)

    # Collect all image formats generated by Docling
    supported_extensions = ("*.png", "*.jpg", "*.jpeg", "*.webp")
    raw_images = []
    for ext in supported_extensions:
        raw_images.extend(raw_assets_dir.glob(ext))
    raw_images.sort()

    if not raw_images:
        return 0

    raw_images_by_name = {img.name: img for img in raw_images}

    image_counter = 1
    heading_counters: Dict[str, int] = {}
    current_heading = "cover"

    lines = content.splitlines()
    raw_to_new_name: Dict[str, Tuple[str, str]] = {}

    for line in lines:
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
        if heading_match:
            current_heading = slugify(heading_match.group(2))

        img_matches = re.finditer(r'!\[(.*?)\]\(([^)]+)\)', line)
        for img_match in img_matches:
            raw_target = img_match.group(2)
            for raw_name, raw_img in raw_images_by_name.items():
                if raw_name in raw_target:
                    if raw_name not in raw_to_new_name:
                        if naming_scheme == "heading":
                            heading_counters[current_heading] = heading_counters.get(current_heading, 0) + 1
                            count_val = heading_counters[current_heading]
                            clean_name = f"{current_heading}_{count_val:03d}{raw_img.suffix}"
                        elif naming_scheme == "custom":
                            clean_name = f"{custom_prefix}_{image_counter:03d}{raw_img.suffix}"
                        else:
                            clean_name = f"img_{image_counter:03d}{raw_img.suffix}"

                        rel_link = f"_assets/{clean_name}"
                        raw_to_new_name[raw_name] = (clean_name, rel_link)
                        image_counter += 1
                    break

    for idx, raw_img in enumerate(raw_images, 1):
        if raw_img.name in raw_to_new_name:
            clean_name, rel_link = raw_to_new_name[raw_img.name]
        else:
            clean_name = f"img_{image_counter:03d}{raw_img.suffix}"
            rel_link = f"_assets/{clean_name}"
            image_counter += 1

        dest_img_path = target_assets_dir / clean_name
        if raw_img != dest_img_path:
            raw_img.replace(dest_img_path)

        if vlm_mode == "local":
            if sys.stdout.isatty():
                sys.stdout.write(f"\r  ↳ [Image {idx}/{len(raw_images)}] Generating VLM alt-text for '{clean_name}'...   ")
                sys.stdout.flush()
            alt_text = query_local_vlm(dest_img_path, vlm_url, vlm_model, vlm_words)
        else:
            alt_text = "RPG Illustration"

        old_ref_pattern = re.escape(raw_img.name)
        content = re.sub(
            rf'!\[(.*?)\]\([^)]*{old_ref_pattern}\)',
            lambda m: f'![{alt_text if vlm_mode == "local" else (m.group(1) or alt_text)}]({rel_link})',
            content
        )

    if vlm_mode == "local" and sys.stdout.isatty():
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()

    md_path.write_text(content, encoding="utf-8")
    return len(raw_images)


# ---------------------------------------------------------------------------
# Main Conversion Workflow
# ---------------------------------------------------------------------------

def convert_single_pdf(
    pdf_path: Path,
    output_dir: Path,
    converter: DocumentConverter,
    args: argparse.Namespace
) -> bool:
    """Convert one PDF document into a self-contained project folder with Markdown and _assets/."""
    doc_stem = pdf_path.stem
    doc_project_dir = output_dir / doc_stem
    out_md = doc_project_dir / f"{doc_stem}.md"

    if out_md.exists() and not args.overwrite:
        print(f"  ⏭  Skipping '{pdf_path.name}' (already converted. Use --overwrite to re-process).")
        return True

    total_pages = get_pdf_page_count(pdf_path)
    page_info = f" ({total_pages} pages)" if total_pages > 0 else ""
    print(f"\n▶ Processing: {pdf_path.name}{page_info}")
    start_time = time.time()

    doc_project_dir.mkdir(parents=True, exist_ok=True)
    target_assets = doc_project_dir / "_assets"
    target_assets.mkdir(parents=True, exist_ok=True)

    temp_raw_assets = output_dir / f"_temp_assets_{doc_stem}"
    temp_raw_assets.mkdir(parents=True, exist_ok=True)

    try:
        page_range = parse_page_range(getattr(args, "pages", None))
    except ValueError as e:
        print(f"  ❌ Error parsing page range: {e}", file=sys.stderr)
        return False

    pipeline_label = "IBM Granite Docling VLM (258M)" if args.pipeline in ("vlm", "granite") else "Modular Pipeline"

    try:
        with LiveActivityStatus(f"Converting with {pipeline_label} (Neural Layout & Tables)..."):
            result = converter.convert(str(pdf_path), page_range=page_range)
            doc = result.document

            doc.save_as_markdown(
                filename=out_md,
                artifacts_dir=temp_raw_assets,
                image_mode=ImageRefMode.REFERENCED if not args.no_images else ImageRefMode.PLACEHOLDER
            )

        img_count = 0
        if not args.no_images:
            img_count = postprocess_assets_and_links(
                md_path=out_md,
                raw_assets_dir=temp_raw_assets,
                target_assets_dir=target_assets,
                naming_scheme=getattr(args, "naming_scheme", "sequential"),
                custom_prefix=getattr(args, "custom_prefix", "img"),
                vlm_mode=args.vlm,
                vlm_url=args.vlm_url,
                vlm_model=args.vlm_model,
                vlm_words=args.vlm_words
            )

        if temp_raw_assets.exists():
            for f in temp_raw_assets.glob("*"):
                f.unlink()
            temp_raw_assets.rmdir()

        elapsed = time.time() - start_time
        processed_page_count = doc.num_pages() if hasattr(doc, "num_pages") else (total_pages or "N/A")
        print(f"  ✔ Finished '{pdf_path.name}' in {elapsed:.1f}s | Pages: {processed_page_count} | Images: {img_count}")
        print(f"  📁 Project  : {doc_project_dir.relative_to(BASE_DIR) if doc_project_dir.is_relative_to(BASE_DIR) else doc_project_dir}/")
        print(f"  📄 Markdown : {out_md.relative_to(BASE_DIR) if out_md.is_relative_to(BASE_DIR) else out_md}")
        print(f"  🖼️  Assets   : {target_assets.relative_to(BASE_DIR) if target_assets.is_relative_to(BASE_DIR) else target_assets}/")
        return True

    except Exception as e:
        print(f"  ❌ Error converting '{pdf_path.name}': {e}", file=sys.stderr)
        if temp_raw_assets.exists():
            import shutil
            shutil.rmtree(temp_raw_assets, ignore_errors=True)
        return False


def main():
    optimal_threads = get_optimal_threads()

    parser = argparse.ArgumentParser(
        description=f"RPG2MD v{__version__} - Convert RPG PDFs from _input to GitHub-flavored Markdown in _output.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # General & Wizard
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive numbered setup wizard")
    parser.add_argument("--preset", type=str, default=None, help="Load conversion settings from a named preset in presets/")
    parser.add_argument("--download-models", action="store_true", help="Download all built-in AI models to local cache and exit")
    parser.add_argument("--file", type=str, default=None, help="Convert a single specific PDF in _input/")
    parser.add_argument("--pages", type=str, default=None, help="Page range to convert (e.g. '1-10', '5', or 'all')")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .md files and asset folders")

    # Pipeline Engine
    parser.add_argument("--pipeline", choices=["modular", "granite", "vlm"], default="modular", help="Conversion pipeline engine")

    # Image & Asset Settings
    parser.add_argument("--scale", type=float, default=3.0, help="Image extraction resolution scale (3.0 = High-Res)")
    parser.add_argument("--no-images", action="store_true", help="Disable image and map extraction")
    parser.add_argument("--naming-scheme", choices=["sequential", "custom", "heading"], default="sequential", help="Image naming scheme")
    parser.add_argument("--custom-prefix", type=str, default="img", help="Custom prefix if naming-scheme is custom")

    # Vision AI (Alt-Text)
    parser.add_argument("--vlm", choices=["smolvlm", "local", "none"], default="smolvlm", help="Vision AI model for alt-text")
    parser.add_argument("--vlm-url", type=str, default="http://127.0.0.1:8888/v1", help="Local VLM OpenAI-compatible API URL")
    parser.add_argument("--vlm-model", type=str, default="Qwen2.5-VL-7B-Instruct-GGUF", help="Model name for local VLM")
    parser.add_argument("--vlm-words", type=int, default=5, help="Max words for AI image description")

    # OCR Engines (Modular Pipeline)
    parser.add_argument("--ocr", choices=["none", "docling", "apple", "easyocr", "tesseract"], default="none", help="OCR backend engine")
    parser.add_argument("--ocr-scale", type=float, default=3.0, help="Raster upscaling factor before OCR")
    parser.add_argument("--force-ocr", action="store_true", help="Force full-page OCR across all pages")

    # Tables & Structure
    parser.add_argument("--table-mode", choices=["accurate", "fast", "none"], default="accurate", help="Table structure mode")
    parser.add_argument("--table-images", action="store_true", help="Save visual snapshot images of tables")
    parser.add_argument("--no-headings", action="store_true", help="Disable automatic heading hierarchy (#, ##, ###)")

    # Performance
    parser.add_argument("--device", choices=["auto", "mps", "cpu", "cuda"], default="auto", help="Compute accelerator device")
    parser.add_argument("--threads", type=int, default=optimal_threads, help="Number of CPU worker threads")

    # Offline download flag handler
    if "--download-models" in sys.argv:
        download_all_builtin_models()
        sys.exit(0)

    # Preset loading handler before parsing
    raw_args = sys.argv[1:]
    if "--preset" in raw_args:
        try:
            p_idx = raw_args.index("--preset")
            if p_idx + 1 < len(raw_args):
                p_name = raw_args[p_idx + 1]
                p_file = get_presets_dir() / (f"{p_name}.json" if not p_name.endswith(".json") else p_name)
                temp_ns = argparse.Namespace()
                temp_ns = load_preset_file(p_file, temp_ns)
                parser.set_defaults(**vars(temp_ns))
        except Exception as e:
            print(f"Warning: Could not pre-load preset: {e}", file=sys.stderr)

    # Wizard-First UX: If no arguments were passed, automatically launch the interactive wizard
    if len(sys.argv) == 1:
        args = parser.parse_args(["-i"])
    else:
        args = parser.parse_args()

    # Validate page range argument if provided via CLI
    if args.pages:
        try:
            parse_page_range(args.pages)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Launch wizard if requested
    if args.interactive:
        args = run_interactive_wizard(args)

    input_dir = BASE_DIR / "_input"
    output_dir = BASE_DIR / "_output"

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        target_file = input_dir / args.file if not Path(args.file).is_absolute() else Path(args.file)
        if not target_file.exists():
            print(f"Error: Specified file not found: {target_file}", file=sys.stderr)
            sys.exit(1)
        pdf_files = [target_file]
    else:
        pdf_files = sorted(list(input_dir.glob("*.pdf")) + list(input_dir.glob("*.PDF")))

    if not pdf_files:
        print(f"No PDF files found in '{input_dir.name}/'. Place PDFs there and re-run.")
        sys.exit(0)

    range_display = args.pages if args.pages else "All Pages"
    pipeline_label = "IBM Granite Docling VLM (258M)" if args.pipeline in ("vlm", "granite") else "Modular Pipeline"

    print("=" * 60)
    print(f"      RPG2MD v{__version__} - PDF to Markdown Batch Converter     ")
    print("=" * 60)
    print(f"📁 Input Directory  : {input_dir.name}/ ({len(pdf_files)} PDF{'s' if len(pdf_files) > 1 else ''} found)")
    print(f"📁 Output Directory : {output_dir.name}/")
    print(f"⚙️  Pipeline Engine  : {pipeline_label}")
    print(f"📄 Page Range       : {range_display}")
    print(f"🖼️  Image Scale      : {'None (Discarded)' if args.no_images else f'{args.scale}x'}")
    print(f"🏷️  Naming Scheme    : {args.naming_scheme}")
    print(f"🤖 Vision AI        : {args.vlm.upper()} ({args.vlm_words} words max alt-text)")
    if args.pipeline == "modular":
        print(f"🔍 OCR Engine       : {args.ocr.upper()} {'[Force Full Page]' if args.force_ocr else ''}")
    print("=" * 60)

    # Preflight check for selected built-in models
    ensure_models_ready(args)

    converter = build_converter(args)

    success_count = 0
    total_start = time.time()

    for pdf_path in pdf_files:
        if convert_single_pdf(pdf_path, output_dir, converter, args):
            success_count += 1

    total_elapsed = time.time() - total_start
    print("\n" + "=" * 60)
    print(f"🎉 All done! Successfully converted {success_count}/{len(pdf_files)} document(s) in {total_elapsed:.1f}s.")
    print("=" * 60)


if __name__ == "__main__":
    main()
