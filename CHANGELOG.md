# Changelog

All notable changes to the RPG2MD project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-18

### Added
- Integrated **IBM Granite Docling (258M VLM)** end-to-end neural vision pipeline (`--pipeline granite` / `VLM Passover`) utilizing DocTags and OTSL structured representations for complex and legacy scans.
- Added **Wizard-First Execution**: Running `rpg2md.py` with no command-line arguments now automatically launches the Interactive Setup Wizard.
- Added active **Live Heartbeat Activity Spinner** with real-time elapsed timer (`[MM:SS elapsed]`) and sub-progress indicators for image captioning.
- Added dynamic CPU core topology auto-detection (`Worker CPU Threads [Auto Detected={count}]`).
- Standardized asset output to isolated per-document directories (`_output/<DocName>/`).

### Fixed
- Fixed Hugging Face `transformers` `generation_config` conflict deprecation warning during SmolVLM alt-text inference.
- Improved heading slugification for complex non-chapter headings and appendices.

## [1.0.0] - 2026-08-17

### Added
- Initial release of `rpg2md.py` conversion utility for converting tabletop RPG PDFs into GitHub-flavored Markdown.
- Integration with Docling v2 conversion pipeline featuring multi-column layout preservation and reading order detection.
- High-resolution image and battlemap extraction pipeline with configurable scaling factors (default 3.0x retina).
- Dynamic image naming schemes: sequential (`img_001.png`), custom prefix (`<prefix>_001.png`), and section-heading slugification (`<previous_heading>_001.png`).
- Vision-Language Model (VLM) integration supporting built-in SmolVLM-256M and local OpenAI-compatible endpoints (Qwen2.5-VL, DeepSeek-OCR) for concise 5-word Markdown alt-text generation.
- Multi-engine OCR support supporting Direct Vector Extraction (0% error rate for digital PDFs), Apple Vision Framework (Neural Engine), RapidOCR, and EasyOCR.
- IBM TableFormer table and stat block parsing with optional visual snapshot image exports.
- Numbered interactive setup wizard (`-i`) featuring Standard and Advanced configuration modes.
- Page range selector supporting custom page intervals (`--pages`).
- Project configuration including `.gitignore`, `requirements.txt`, `LICENSE` (MIT), and `README.md` documentation.
