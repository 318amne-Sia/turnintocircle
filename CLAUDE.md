# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

An image-organization tool for TEM (transmission electron microscopy) micrographs. The first feature: on loading an image, detect the Au (gold) nanoparticles — which appear as bright/white regions in these TEM images — and outline them with contours.

No source code exists yet; the project is being designed from scratch.

## Layout

- `detect_au.py` — the main tool: full detection pipeline (scalebar calibration → bottom-strip crop → Otsu threshold → morphology cleanup → contour finding → area filter → greedy circle packing), CLI with argparse. Outputs per image: annotated `<stem>_contours.png` and `<stem>_circles.png`; combined `particles.csv` (area, perimeter, circularity, centroid) and `circles.csv` (circle positions/diameters in nm, for FDTD simulation input).
- `app.py` — Gradio web UI over the same pipeline (imports the functions from `detect_au.py`; CSV row-building is shared via `particle_rows`/`circle_rows`). Exposes min-diameter, overlap toggle (default OFF in the UI — the CLI default allows overlap), min-area, and a manual nm/px override for images without a scalebar; everything else uses defaults. UI display name: "TurnIntoCircle". Same crop behavior as the CLI, but the strip height auto-scales with image size (160 px at 2048²). Gradio footer links are hidden via launch(css=...).
- `data/` — input TEM images (the reference TIF lives here)
- `steps/` — numbered learning scripts (`step1_load.py` ... `step5_contours.py`) that build up the pipeline one concept at a time; the user is learning image processing step by step, so keep these small and well-commented (Traditional Chinese comments). `detect_au.py` is the consolidated version — new features go there, steps/ stays as the learning record.
- `output/` — generated images/results, gitignored
- Run scripts from the repo root: paths inside scripts are relative to the root

## Domain Notes

- These are bright-field TEM images: Au particles are DARK, background is bright. Thresholding uses `THRESH_BINARY_INV` so Au becomes the white foreground.
- The Gatan scalebar burned into the bottom-left corner (~420×160 px at 2048²) must be excluded before contour finding or it is detected as a particle. Both CLI and UI handle this by cropping the entire bottom strip (scalebar height) after measuring nm/px — a full-width crop, not a corner mask, so circles.csv covers a complete rectangle for FDTD (no missing bottom-left corner).
- Particles are heavily coalesced islands; each contour may be several merged grains. Watershed segmentation is the known next step if per-grain counting is needed.
- End goal of circle packing: the circle list (`circles.csv`) is handed off as geometry input for FDTD optical simulation. Circles must respect a minimum diameter (`--min-diameter`, default 5 nm — an FDTD constraint, may change) and may overlap (overlapping same-material objects union in FDTD tools); `--no-overlap` disables overlap at the cost of coverage (~93% → ~82%).
- Calibration: nm/px is auto-measured from the burned-in scalebar (longest dark horizontal run in the scalebar region; 50 nm ≈ 209 px ≈ 0.239 nm/px on the reference image). `--nm-per-px` overrides when no scalebar is present.

## Sample Data

`data/Au_10nm-spin 65_120000.0V_38000X_0001.tif` — the reference input image:
- 2048×2048, 8-bit palette mode (grayscale ramp palette), single frame
- Created by Gatan Digital Micrograph (TIFF tag 270), so expect Gatan-specific private TIFF tags (65024–65027)
- Filename encodes acquisition parameters: 10 nm Au particles, 120 kV, 38000× magnification
- Convert to grayscale (`Image.open(...).convert("L")`) before processing; do not assume RGB

## Environment

- Windows 11, Python 3.11.7
- Always use the project venv at `.venv/`, never the system Python: `.venv\Scripts\python.exe`
- Dependencies are pinned in `requirements.txt` (numpy, Pillow, opencv-python); the venv is gitignored — rebuild with `python -m venv .venv` then `.venv\Scripts\python.exe -m pip install -r requirements.txt`

## Commands

- Launch the web UI: `.venv\Scripts\python.exe app.py` (opens http://127.0.0.1:7860; `share=True` in `launch()` for a temporary public link)
- Run the tool on all TIFs in data/: `.venv\Scripts\python.exe detect_au.py data`
- Single image / options: `.venv\Scripts\python.exe detect_au.py data\xxx.tif --min-area 200 --scalebar 420 160` (`--scalebar 0 0` disables masking)
- Add a dependency: install it into the venv AND add it to `requirements.txt`

(No build, lint, or test tooling is configured yet — update this section when it is.)
