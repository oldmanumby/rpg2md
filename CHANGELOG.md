# Changelog

All notable changes to the RPG2MD project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
