# Changelog

All notable changes to the RPG2MD project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.5] - 2026-08-27

### Added
- Added interactive post-job continuation loop: upon completing a batch conversion, users are prompted whether to run another conversion and whether to keep or adjust settings.

### Fixed
- Fixed false image matching in asset post-processing by comparing exact basenames instead of substrings, preventing links like `img_1.png` from incorrectly matching assets like `raw_img_10.png`; unmatched links now retain their original reference.
- Fixed existing Markdown alt-text being clobbered during post-processing: captions already embedded by Docling/SmolVLM are preserved in non-local VLM modes, with the generic `RPG Illustration` fallback applied only when a caption is empty.
- Added regression unit tests covering exact-basename matching and alt-text preservation.

## [1.3.4] - 2026-08-19

### Fixed
- Fixed CLI `--preset` argument loading by removing the `hasattr` restriction in `load_preset_file()`, ensuring preset values correctly populate the argument parser defaults.
- Fixed SmolVLM pre-downloading in `ensure_models_ready()` by restricting it to the Modular pipeline (where Docling supports it), avoiding unnecessary downloads during Granite VLM runs.
- Fixed stale asset retention on `--overwrite` by purging existing image assets in `_output/<DocName>/_assets/` before extracting new images.
- Added automated unit tests for CLI preset preloading and namespace population.

## [1.3.3] - 2026-08-19

### Added
- Added automated unit test suite in `tests/test_rpg2md.py` covering slugification, page range validation, preset persistence, and asset post-processing.
- Added explicit input validation helpers (`prompt_int`, `prompt_float`) with retry loops in the interactive wizard.
- Added HTML entity unescaping (`html.unescape`) and spaced-out title collapse (`B A L D U R ' S  G A T E` -> `baldurs_gate`) in heading slugification.
- Added Tesseract OCR support to the interactive wizard OCR selection menu.
- Added support for `.jpeg` and `.webp` asset extraction alongside `.png` and `.jpg` with $O(1)$ dictionary lookup.
- Added `--version` / `-v` CLI flag.

### Fixed
- Fixed dead `--ocr local` option by removing it from the OCR engine selection (local LLM endpoints are properly utilized via `--vlm local` for Vision Alt-Text).
- Fixed cross-platform device handling in Granite VLM pipeline by removing hardcoded `mps` fallback, allowing native auto-detection across Linux (`cuda`/`cpu`), Windows (`cuda`/`cpu`), and macOS (`mps`).
- Fixed silent exception swallowing in `query_local_vlm()` by adding diagnostic warnings to `stderr` when local endpoints are unreachable.
- Fixed project directory anchoring by resolving `BASE_DIR = Path(__file__).resolve().parent` so the script can be executed from any working directory.
- Fixed silent full-book conversion on malformed `--pages` arguments by enforcing strict syntax parsing and error exit.
- Fixed Hugging Face cache checking in `is_hf_model_cached()` to verify snapshot integrity rather than checking folder existence alone.
- Fixed TTY awareness in `LiveActivityStatus` so background/piped logs do not spam carriage returns.

## [1.3.2] - 2026-08-19

### Added
- Added pre-conversion PDF page count detection using `pypdfium2` (`▶ Processing: <document>.pdf (XX pages)`).

### Fixed
- Fixed PyTorch Dynamo and Hugging Face warning pollution (`Graph break: from user code at...` and `generation_config`) by enforcing early environment suppression (`TORCHDYNAMO_DISABLE=1`, `TORCH_CPP_LOG_LEVEL=ERROR`), preserving a clean single-line live activity timer.

## [1.3.1] - 2026-08-19

### Added
- Standardized output structure into self-contained project folders: each PDF converts to `_output/<DocName>/<DocName>.md` with assets in `_output/<DocName>/_assets/`.
- Updated Markdown image links to use portable relative paths (`![Alt Text](_assets/img_001.png)`).

### Fixed
- Fixed duplicate preset list output when selecting `[3] Load a Saved Preset` in the interactive wizard.

## [1.3.0] - 2026-08-18

### Added
- Added **Automated Model Preflight Verification**: Automatically checks `~/.cache/huggingface/hub/` and `~/.EasyOCR/model/` for required model weights before conversion begins.
- Added visual download progress reporting for first-run downloads of IBM Granite Docling 258M, SmolVLM-256M, and EasyOCR.
- Added **`--download-models` CLI flag** allowing users to pre-download all built-in AI models up front for offline use.
- Documented cache architecture and directory paths in `README.md`.

## [1.2.0] - 2026-08-18

### Added
- Added **Preset Management System** allowing users to save wizard settings as custom-named `.json` files in `./presets/`.
- Added **Preset Loader in Wizard**: Option `[3] Load a Saved Preset (from ./presets/)` at the top of the interactive setup wizard.
- Added **CLI `--preset <name>` Flag** for instant 1-click batch conversion without going through the wizard.
- Added starter presets: `presets/digital_rulebook.json` and `presets/vintage_scans.json`.

## [1.1.0] - 2026-08-18

### Added
- Integrated **IBM Granite Docling (258M VLM)** end-to-end neural vision pipeline (`--pipeline granite` / `VLM Passover`) utilizing DocTags and OTSL structured representations for complex and legacy scans.
- Added **Wizard-First Execution**: Running `rpg2md.py` with no command-line arguments now automatically launches the Interactive Setup Wizard.
- Added active **Live Heartbeat Activity Spinner** with real-time elapsed timer (`[MM:SS elapsed]`) and sub-progress indicators for image captioning.
- Added dynamic CPU core topology auto-detection (`Worker CPU Threads [Auto Detected={count}]`).

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
