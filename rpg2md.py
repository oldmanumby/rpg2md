#!/usr/bin/env python3
"""
rpg2md.py - RPG PDF to GitHub-Flavored Markdown Converter
Powered by Docling, Apple Vision, and Local Vision-Language Models (VLM).

Converts PDFs in `_input/` to Markdown in `_output/`, extracting images
sequentially into `_output/_assets/` with AI-generated alt-text descriptions.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Docling Imports
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorOptions,
    EasyOcrOptions,
    HeadingHierarchyOptions,
    OcrMacOptions,
    PdfPipelineOptions,
    PictureDescriptionBaseOptions,
    RapidOcrOptions,
    TableFormerMode,
    TableStructureOptions,
    TesseractOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode


# ---------------------------------------------------------------------------
# Interactive Menu Utilities
# ---------------------------------------------------------------------------

def prompt_choice_custom(
    title: str,
    options: List[str],
    default_idx: int = 1,
    prompt_label: str = "Choice [1]: "
) -> int:
    """Prompt user with a list of formatted options and custom prompt label."""
    print(f"\n{title}")
    for idx, opt in enumerate(options, 1):
        marker = " [DEFAULT]" if (idx == default_idx and "[DEFAULT]" not in opt) else ""
        print(f"[{idx}] {opt}{marker}")

    while True:
        choice = input(prompt_label).strip()
        if not choice:
            return default_idx
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice)
        print(f"Invalid selection. Please enter a number between 1 and {len(options)}.")


def prompt_text(title: str, default: str = "") -> str:
    """Prompt user for text input with optional default value."""
    default_str = f" [{default}]" if default else ""
    val = input(f"{title}{default_str}: ").strip()
    return val if val else default


def prompt_yn(title: str, default_yes: bool = True) -> bool:
    """Prompt user for (Y/n) or (y/N) boolean."""
    prompt_suffix = " (Y/n): " if default_yes else " (y/N): "
    choice = input(f"{title}{prompt_suffix}").strip().lower()
    if not choice:
        return default_yes
    return choice in ("y", "yes", "true", "1")


def slugify(text: str, max_length: int = 35) -> str:
    """Convert any heading text (chapters, monsters, spells, rules, appendices) into a clean snake_case filename slug."""
    # Strip HTML entities, markdown markers, and punctuation
    text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
    text = re.sub(r'[#*_`\[\]()\'"<>:?,.!/\\|~+={}$^]', '', text)
    text = re.sub(r'[-\s]+', '_', text).strip('_').lower()
    text = re.sub(r'[^a-z0-9_]', '', text)
    if not text:
        return "section"
    return text[:max_length].rstrip('_')


def parse_page_range(range_str: Optional[str]) -> Tuple[int, int]:
    """Parse strings like '1-10', '5', or 'all' into a (start, end) tuple for Docling."""
    if not range_str or range_str.strip().lower() in ("all", "*", ""):
        return (1, 9223372036854775807)
    
    clean = range_str.strip()
    if "-" in clean:
        parts = clean.split("-")
        try:
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            return (max(1, start), max(start, end))
        except ValueError:
            return (1, 9223372036854775807)
    elif clean.isdigit():
        page = int(clean)
        return (max(1, page), max(1, page))
    
    return (1, 9223372036854775807)


# ---------------------------------------------------------------------------
# Local Vision LLM Query (Qwen2.5-VL / DeepSeek via OpenAI API)
# ---------------------------------------------------------------------------

def query_local_vlm(image_path: Path, url: str, model: str, max_words: int = 5) -> str:
    """Send cropped image to local LLM / VLM endpoint for a 5-word description."""
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
    except Exception:
        return "RPG Illustration"


# ---------------------------------------------------------------------------
# Pipeline Options Builder
# ---------------------------------------------------------------------------

def build_pipeline_options(args: argparse.Namespace) -> PdfPipelineOptions:
    """Assemble Docling PdfPipelineOptions based on CLI / Wizard parameters."""
    opts = PdfPipelineOptions()

    # 1. Images & Assets
    opts.generate_picture_images = not args.no_images
    opts.images_scale = args.scale

    # 2. Vision AI (Alt-Text)
    if not args.no_images and args.vlm == "smolvlm":
        opts.do_picture_description = True
        opts.picture_description_options.prompt = f"Describe this RPG art or map in {args.vlm_words} words or less."
        opts.picture_description_options.generation_config["max_new_tokens"] = args.vlm_words * 4
    else:
        opts.do_picture_description = False

    # 3. OCR Engine Configuration
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
    elif args.ocr == "local":
        opts.do_ocr = False

    # 4. Tables & Stat Blocks
    if args.table_mode == "none":
        opts.do_table_structure = False
    else:
        opts.do_table_structure = True
        table_mode = TableFormerMode.ACCURATE if args.table_mode == "accurate" else TableFormerMode.FAST
        opts.table_structure_options = TableStructureOptions(mode=table_mode)
    opts.generate_table_images = args.table_images

    # 5. Headings & Hierarchy
    if not args.no_headings:
        opts.heading_hierarchy_options = HeadingHierarchyOptions(enabled=True)

    # 6. Hardware Acceleration
    opts.accelerator_options = AcceleratorOptions(
        device=args.device,
        num_threads=args.threads
    )

    return opts


# ---------------------------------------------------------------------------
# Interactive Wizard
# ---------------------------------------------------------------------------

def run_interactive_wizard(args: argparse.Namespace) -> argparse.Namespace:
    """Walk user through exact custom numbered prompts."""
    print("=" * 60)
    print("             RPG2MD - Interactive Setup Wizard              ")
    print("=" * 60)

    # 1. Wizard Mode
    mode_choice = prompt_choice_custom(
        "Select Wizard Mode:",
        [
            "Standard Setup (Essential settings) [DEFAULT]",
            "Advanced Setup (More granular control)"
        ],
        default_idx=1,
        prompt_label="Choice [ENTER=1]: "
    )
    is_advanced = (mode_choice == 2)

    # 2. Image Resolution Scale
    scale_choice = prompt_choice_custom(
        "Image Resolution Scale:",
        [
            "3.0x Higher Resolution [DEFAULT]",
            "2.0x Standard Resolution",
            "1.0x Lower-Resolution",
            "Custom Scale Factor",
            "Discard all images"
        ],
        default_idx=1,
        prompt_label="Choice [1]: "
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
        args.scale = float(prompt_text("Enter Custom Scale Factor", "3.0"))
        args.no_images = False
    elif scale_choice == 5:
        args.no_images = True

    # 3. Vision AI for Image Descriptions (Alt-Text)
    if not args.no_images:
        vlm_choice = prompt_choice_custom(
            "Vision AI for Image Descriptions (Alt-Text):",
            [
                "SmolVLM-256M (Fastest built-in model) [DEFAULT]",
                "Local LLM via Endpoint (e.g. Qwen2.5-VL)",
                "None: Standard `![Image](link)`"
            ],
            default_idx=1,
            prompt_label="Choice [1]: "
        )
        if vlm_choice == 1:
            args.vlm = "smolvlm"
            args.vlm_words = 5
        elif vlm_choice == 2:
            args.vlm = "local"
            args.vlm_url = prompt_text("Local VLM Endpoint URL", args.vlm_url)
            args.vlm_model = prompt_text("Model Name", args.vlm_model)
            args.vlm_words = int(prompt_text("Max Words per Alt-Text", "5"))
        elif vlm_choice == 3:
            args.vlm = "none"
    else:
        args.vlm = "none"

    # 4. OCR Engine
    ocr_choice = prompt_choice_custom(
        "OCR Engine:",
        [
            "None (Digital text; fastest, most accurate for modern PDFs) [DEFAULT]",
            "Docling Default (Built-in RapidOCR; good for majority of PDFs)",
            "Apple Vision Framework (Neural Engine; better OCR accuracy)",
            "EasyOCR (Built-in PyTorch; best for legacy PDFs/scans)",
            "Local LLM via Endpoint (e.g. DeepSeek-OCR)"
        ],
        default_idx=1,
        prompt_label="Choice [1]: "
    )
    ocr_map = {1: "none", 2: "docling", 3: "apple", 4: "easyocr", 5: "local"}
    args.ocr = ocr_map[ocr_choice]

    if args.ocr == "local":
        args.ocr_url = prompt_text("Local OCR Endpoint URL", args.ocr_url)
        args.ocr_model = prompt_text("Local OCR Model Name", args.ocr_model)

    # 5. Advanced Settings
    if is_advanced:
        print("\n-- Advanced Settings --\n")

        # Heading hierarchy
        args.no_headings = not prompt_yn("Enable automatic heading hierarchy (#, ##, ###)?", default_yes=True)

        # Asset Directory Organization
        if not args.no_images:
            asset_choice = prompt_choice_custom(
                "Asset Directory Organization:",
                [
                    "Seperate Assets Folder (_output/_assets/<DocName>/img_001.png) [DEFAULT]",
                    "Shared Assets Folder (_output/_assets/<DocName>_001.png)"
                ],
                default_idx=1,
                prompt_label="Choice [1]: "
            )
            args.asset_layout = "per-doc" if asset_choice == 1 else "shared"

            # Image Naming Scheme
            naming_choice = prompt_choice_custom(
                "Image Naming Scheme:",
                [
                    '"img_001.png"',
                    '"<YourPrefix>_001.png"',
                    '"<PreviousHeading>_001.png"'
                ],
                default_idx=1,
                prompt_label="Choice [1]: "
            )
            if naming_choice == 1:
                args.naming_scheme = "sequential"
                args.custom_prefix = "img"
            elif naming_choice == 2:
                args.naming_scheme = "custom"
                args.custom_prefix = prompt_text("Enter Custom Prefix", "art")
            elif naming_choice == 3:
                args.naming_scheme = "heading"

        # Table Snapshots
        args.table_images = prompt_yn("Save snapshot images of tables as assets?", default_yes=False)

        # Force OCR (if OCR is active)
        if args.ocr != "none":
            args.force_ocr = prompt_yn("Force full-page OCR across all pages?", default_yes=False)

        # Page Range
        page_range_input = prompt_text("Page Range (e.g. '1-10', '5', or Enter for All)", "All")
        args.pages = page_range_input if page_range_input.lower() != "all" else None

        # Table Recognition Mode
        table_choice = prompt_choice_custom(
            "Table Recognition Mode:",
            [
                "Accurate (IBM TableFormer; best for stats & classes) [DEFAULT]",
                "Fast (Grid matching)",
                "None (Treat tables as text)"
            ],
            default_idx=1,
            prompt_label="Choice [1]: "
        )
        args.table_mode = {1: "accurate", 2: "fast", 3: "none"}[table_choice]

        # Compute Accelerator Device
        device_choice = prompt_choice_custom(
            "Compute Accelerator Device:",
            [
                "Auto (Detect Best Available) [DEFAULT]",
                "Apple Silicon MPS (Metal Performance Shaders)",
                "CPU"
            ],
            default_idx=1,
            prompt_label="Choice [1]: "
        )
        args.device = {1: "auto", 2: "mps", 3: "cpu"}[device_choice]

        # Worker CPU Threads
        args.threads = int(prompt_text("Worker CPU Threads", str(args.threads)))

    # Overwrite
    args.overwrite = prompt_yn("Overwrite existing files in _output/?", default_yes=False)

    print("\n" + "=" * 60)
    print("Configuration complete! Starting conversion...")
    print("=" * 60 + "\n")
    return args


# ---------------------------------------------------------------------------
# Post-Processing: Asset Normalization & Heading-Based Naming
# ---------------------------------------------------------------------------

def postprocess_assets_and_links(
    md_path: Path,
    raw_assets_dir: Path,
    target_assets_dir: Path,
    doc_stem: str,
    asset_layout: str,
    naming_scheme: str,
    custom_prefix: str,
    vlm_mode: str,
    vlm_url: str,
    vlm_model: str,
    vlm_words: int
) -> int:
    """Normalize assets (sequential, custom prefix, or any heading-based name) and rewrite links."""
    if not md_path.exists():
        return 0

    content = md_path.read_text(encoding="utf-8")
    target_assets_dir.mkdir(parents=True, exist_ok=True)

    raw_images = sorted(list(raw_assets_dir.glob("*.png")) + list(raw_assets_dir.glob("*.jpg")))
    if not raw_images:
        return 0

    # Build image map with heading tracking
    image_counter = 1
    heading_counters: Dict[str, int] = {}
    current_heading = "cover"

    lines = content.splitlines()
    raw_to_new_name: Dict[str, Tuple[str, str]] = {}  # raw_name -> (clean_name, rel_link)

    for line in lines:
        # Detect any markdown heading of any level (#, ##, ###, ####, etc.)
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
        if heading_match:
            current_heading = slugify(heading_match.group(2))

        # Check for image links
        img_match = re.search(r'!\[(.*?)\]\(([^)]+)\)', line)
        if img_match:
            raw_target = img_match.group(2)
            # Match against raw images
            for raw_img in raw_images:
                if raw_img.name in raw_target:
                    if raw_img.name not in raw_to_new_name:
                        if naming_scheme == "heading":
                            heading_counters[current_heading] = heading_counters.get(current_heading, 0) + 1
                            count_val = heading_counters[current_heading]
                            clean_name = f"{current_heading}_{count_val:03d}.png"
                        elif naming_scheme == "custom":
                            clean_name = f"{custom_prefix}_{image_counter:03d}.png"
                        else:
                            clean_name = f"img_{image_counter:03d}.png"

                        if asset_layout == "per-doc":
                            rel_link = f"_assets/{doc_stem}/{clean_name}"
                        else:
                            clean_name = f"{doc_stem}_{clean_name}"
                            rel_link = f"_assets/{clean_name}"

                        raw_to_new_name[raw_img.name] = (clean_name, rel_link)
                        image_counter += 1
                    break

    # Process files and generate VLM captions
    for raw_img in raw_images:
        if raw_img.name in raw_to_new_name:
            clean_name, rel_link = raw_to_new_name[raw_img.name]
        else:
            clean_name = f"img_{image_counter:03d}.png"
            rel_link = f"_assets/{doc_stem}/{clean_name}" if asset_layout == "per-doc" else f"_assets/{doc_stem}_{clean_name}"
            image_counter += 1

        dest_img_path = target_assets_dir / clean_name
        if raw_img != dest_img_path:
            raw_img.replace(dest_img_path)

        # Generate alt-text
        if vlm_mode == "local":
            alt_text = query_local_vlm(dest_img_path, vlm_url, vlm_model, vlm_words)
        else:
            alt_text = "RPG Illustration"

        # Regex replacement in full content
        old_ref_pattern = re.escape(raw_img.name)
        content = re.sub(
            rf'!\[(.*?)\]\([^)]*{old_ref_pattern}\)',
            lambda m: f'![{alt_text if vlm_mode == "local" else (m.group(1) or alt_text)}]({rel_link})',
            content
        )

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
    """Convert one PDF document into GitHub-flavored Markdown and assets."""
    doc_stem = pdf_path.stem
    out_md = output_dir / f"{doc_stem}.md"

    if out_md.exists() and not args.overwrite:
        print(f"  ⏭  Skipping '{pdf_path.name}' (already converted. Use --overwrite to re-process).")
        return True

    print(f"\n▶ Processing: {pdf_path.name}")
    start_time = time.time()

    if args.asset_layout == "per-doc":
        target_assets = output_dir / "_assets" / doc_stem
    else:
        target_assets = output_dir / "_assets"

    temp_raw_assets = output_dir / f"_temp_assets_{doc_stem}"
    temp_raw_assets.mkdir(parents=True, exist_ok=True)

    page_range = parse_page_range(getattr(args, "pages", None))

    try:
        # Convert with specified page range
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
                doc_stem=doc_stem,
                asset_layout=args.asset_layout,
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
        page_count = doc.num_pages() if hasattr(doc, "num_pages") else "N/A"
        print(f"  ✔ Finished '{pdf_path.name}' in {elapsed:.1f}s | Pages: {page_count} | Images: {img_count}")
        print(f"  📄 Markdown: {out_md.relative_to(Path.cwd()) if out_md.is_relative_to(Path.cwd()) else out_md}")
        return True

    except Exception as e:
        print(f"  ❌ Error converting '{pdf_path.name}': {e}", file=sys.stderr)
        if temp_raw_assets.exists():
            import shutil
            shutil.rmtree(temp_raw_assets, ignore_errors=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert RPG PDFs from _input to GitHub-flavored Markdown in _output with high-res assets & VLM alt-text.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # General & Wizard
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive numbered setup wizard")
    parser.add_argument("--file", type=str, default=None, help="Convert a single specific PDF in _input/")
    parser.add_argument("--pages", type=str, default=None, help="Page range to convert (e.g. '1-10', '5', or 'all')")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .md files and asset folders")

    # Image & Asset Settings
    parser.add_argument("--scale", type=float, default=3.0, help="Image extraction resolution scale (3.0 = High-Res)")
    parser.add_argument("--no-images", action="store_true", help="Disable image and map extraction")
    parser.add_argument("--asset-layout", choices=["per-doc", "shared"], default="per-doc", help="Asset directory organization")
    parser.add_argument("--naming-scheme", choices=["sequential", "custom", "heading"], default="sequential", help="Image naming scheme")
    parser.add_argument("--custom-prefix", type=str, default="img", help="Custom prefix if naming-scheme is custom")

    # Vision AI (Alt-Text)
    parser.add_argument("--vlm", choices=["smolvlm", "local", "none"], default="smolvlm", help="Vision AI model for alt-text")
    parser.add_argument("--vlm-url", type=str, default="http://127.0.0.1:8888/v1", help="Local VLM OpenAI-compatible API URL")
    parser.add_argument("--vlm-model", type=str, default="Qwen2.5-VL-7B-Instruct-GGUF", help="Model name for local VLM")
    parser.add_argument("--vlm-words", type=int, default=5, help="Max words for AI image description")

    # OCR Engines
    parser.add_argument("--ocr", choices=["none", "docling", "apple", "easyocr", "tesseract", "local"], default="none", help="OCR backend engine")
    parser.add_argument("--ocr-url", type=str, default="http://127.0.0.1:8888/v1", help="Local OCR API URL")
    parser.add_argument("--ocr-model", type=str, default="deepseek-ocr-2", help="Local OCR Model Name")
    parser.add_argument("--ocr-scale", type=float, default=3.0, help="Raster upscaling factor before OCR")
    parser.add_argument("--force-ocr", action="store_true", help="Force full-page OCR across all pages")

    # Tables & Structure
    parser.add_argument("--table-mode", choices=["accurate", "fast", "none"], default="accurate", help="Table structure mode")
    parser.add_argument("--table-images", action="store_true", help="Save visual snapshot images of tables in _assets/")
    parser.add_argument("--no-headings", action="store_true", help="Disable automatic heading hierarchy (#, ##, ###)")

    # Performance
    parser.add_argument("--device", choices=["auto", "mps", "cpu"], default="auto", help="Compute accelerator device")
    parser.add_argument("--threads", type=int, default=8, help="Number of CPU worker threads")

    args = parser.parse_args()

    # Launch wizard if requested
    if args.interactive:
        args = run_interactive_wizard(args)

    base_dir = Path.cwd()
    input_dir = base_dir / "_input"
    output_dir = base_dir / "_output"

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

    print("=" * 60)
    print("           RPG2MD - PDF to Markdown Batch Converter          ")
    print("=" * 60)
    print(f"📁 Input Directory  : {input_dir.name}/ ({len(pdf_files)} PDF{'s' if len(pdf_files) > 1 else ''} found)")
    print(f"📁 Output Directory : {output_dir.name}/")
    print(f"📄 Page Range       : {range_display}")
    print(f"🖼️  Image Scale      : {'None (Discarded)' if args.no_images else f'{args.scale}x'}")
    print(f"🖼️  Asset Layout     : {args.asset_layout}")
    print(f"🏷️  Naming Scheme    : {args.naming_scheme}")
    print(f"🤖 Vision AI        : {args.vlm.upper()} ({args.vlm_words} words max alt-text)")
    print(f"🔍 OCR Engine       : {args.ocr.upper()} {'[Force Full Page]' if args.force_ocr else ''}")
    print("=" * 60)

    pipeline_opts = build_pipeline_options(args)
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)}
    )

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
