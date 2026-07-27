# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

An image-organization tool for TEM (transmission electron microscopy) micrographs. The core feature: on loading an image, detect the Au (gold) nanoparticles — which appear as **dark** regions in these bright-field images (see Domain Notes) — outline them with contours, and pack them into circles for FDTD simulation input.

## Layout

- `detect_au.py` — the main tool: full detection pipeline (scalebar calibration → bottom-strip crop → Otsu threshold → morphology cleanup → contour finding → area filter → greedy circle packing), CLI with argparse. Outputs per image: annotated `<stem>_contours.png` and `<stem>_circles.png`; combined `particles.csv` (area, perimeter, circularity, centroid) and `circles.csv` (circle positions/diameters in nm, for FDTD simulation input).
- `streamlit_app.py` — Streamlit web UI over the same pipeline (imports the functions from `detect_au.py`; CSV row-building is shared via `particle_rows`/`circle_rows`). Exposes min-diameter, overlap toggle (default OFF in the UI — the CLI default allows overlap), min-area, and a manual nm/px override for images without a scalebar; everything else uses defaults. UI display name: "TurnIntoCircle". Same crop behavior as the CLI, but the strip height auto-scales with image size (160 px at 2048²). Two Streamlit-specific details: results are stashed in `st.session_state` (a download-button click reruns the script and would otherwise blank the page), and the uploaded file is `seek(0)`-ed before reading (the stream sits at EOF after a rerun). The uploaded file object is passed straight to `load_grayscale` — PIL accepts file-like objects, so no temp file is needed. A Gradio version of this UI (`app.py`) existed until the Streamlit switch; recover it from commit a4d97b0 if ever needed.
- `data/` — input TEM images (the reference TIF lives here)
- `steps/` — numbered learning scripts (`step1_load.py` ... `step6_circles.py`) that build up the pipeline one concept at a time; the user is learning image processing step by step, so keep these small and well-commented (Traditional Chinese comments). `detect_au.py` is the consolidated version — new features go there, steps/ stays as the learning record. **`step2_histogram.py` imports matplotlib** — the only thing in the repo that does, which is why matplotlib lives in `requirements-dev.txt` and not `requirements.txt`. These scripts also need images in `data/` to run at all.
- `output/` — generated images/results, gitignored
- `docs/` — `example.png` (the README's before/after figure) and `make_example.py`, the script that builds it. The figure has a **transparent background** so it sits on both light and dark README themes; that forces PNG over JPEG, and forces the label colour to a mid-grey (~#757575) that clears 4.5:1 contrast against white *and* GitHub's dark background — pure black or white text would vanish on one of them. It is saved as a 255-colour palette PNG via `quantize(method=FASTOCTREE)` (1.3 MB → 290 KB, no visible banding on greyscale + one green); FASTOCTREE is required because it is the only PIL quantizer that carries alpha into the palette — MEDIANCUT silently drops the transparency. Tracked on purpose: the JPG is the only visual output in version control, since `data/` and `output/` are gitignored. Regenerate with `detect_au.py "data/<ref>.tif" --no-overlap` followed by `.venv/bin/python docs/make_example.py`. Three decisions are baked into that script's comments and should not be undone casually: the example uses **`--no-overlap`** (overlapping circles turn into an unreadable scribble when downscaled), the source TIF is **cropped to the output's 2048×1888** so both panels show the same field of view, and the two panels are **composited into one JPEG** rather than placed side by side in the README. That last one took three tries: a markdown table renders identically-sized images at different widths, and so does an HTML `<table>` with explicit `width="400"` — only a single image is immune to the renderer's column-width logic. The README shows input → final packing only; the intermediate contour image was dropped as noise for a first-time visitor. If pipeline defaults change, rerun the script **and** update the numbers quoted in the README's 範例 section (96 islands / 752 circles / 82.0% coverage / 0.2392 nm-per-px) plus the sample `circles.csv` rows.
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

- macOS (Apple Silicon), Python 3.13 from Homebrew at `/opt/homebrew/bin/python3.13`
- The system Python (`/usr/bin/python3`) is 3.9.6 and **cannot run this project** — Streamlit requires >= 3.10. Install a modern one with `brew install python@3.13`.
- Always use the project venv at `.venv/`, never the system Python: `.venv/bin/python`
- Dependencies are listed in `requirements.txt` (numpy, Pillow, opencv-python-headless, streamlit); the venv is gitignored — rebuild with `/opt/homebrew/bin/python3.13 -m venv .venv` then `.venv/bin/python -m pip install -r requirements.txt`
- Verified end-to-end on OpenCV 5.0.0, numpy 2.5.1, Streamlit 1.60.0 (2026-07). OpenCV 5 did not break any call this pipeline uses (`findContours` still returns a 2-tuple, `distanceTransform`/`minMaxLoc`/`moments` unchanged).
- `requirements-dev.txt` holds matplotlib, needed only by `steps/`. Keep it out of `requirements.txt` so Streamlit Community Cloud doesn't install it on every deploy.
- Use `opencv-python-headless`, not `opencv-python` — the Streamlit Community Cloud container has no `libGL`, and nothing in the codebase calls `cv2.imshow`/`waitKey`

## Searching this repo

`grep`/`rg` here honour `.gitignore`, so a recursive search **silently skips ignored paths** — `data/` and `output/` are ignored. When checking a claim like "nothing uses library X", confirm with an explicit path glob (`grep steps/*.py`) before concluding, or the absent hit may just be an unsearched directory. This exact trap produced a wrong "matplotlib is unused" conclusion once; `steps/` was listed in `.gitignore` at the time despite its files being tracked.

## Deployment

The Streamlit UI is deployed to Streamlit Community Cloud (free) so non-technical users get a URL instead of a checkout. The Cloud watches the GitHub repo directly and redeploys on every push to `master` — there is no CI workflow to maintain. Entry point is `streamlit_app.py`; `requirements.txt` at the repo root is what the container installs.

Hugging Face Spaces was evaluated first and rejected: as of 2026 HF requires a paid PRO plan ($9/mo) to create Gradio or Docker Spaces, and only Static Spaces remain free. Do not re-suggest free HF Spaces hosting for this project.

## Commands

- Launch the web UI: `.venv/bin/streamlit run streamlit_app.py` (opens http://localhost:8501)
- Run the tool on all TIFs in data/: `.venv/bin/python detect_au.py data`
- Single image / options: `.venv/bin/python detect_au.py data/xxx.tif --min-area 200 --scalebar 420 160` (`--scalebar 0 0` disables masking)
- Add a dependency: install it into the venv AND add it to `requirements.txt`

(No build, lint, or test tooling is configured yet — update this section when it is.)
