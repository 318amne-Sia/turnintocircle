"""Au 顆粒偵測 — 網頁介面(Gradio)

給不熟 CLI 的使用者:拖曳上傳 TEM 影像 → 自動偵測 Au 顆粒、拼圓
→ 預覽結果並下載 FDTD 用的 circles.csv。偵測管線直接重用 detect_au.py。

啟動(從專案根目錄):
  .venv\\Scripts\\python.exe app.py
瀏覽器會自動開 http://127.0.0.1:7860;
要產生臨時公開連結給別人用,把最後一行改成 demo.launch(share=True)。
"""
import csv
import tempfile
from pathlib import Path

import cv2
import gradio as gr

from detect_au import (annotate, annotate_circles, build_mask, circle_rows,
                       coverage_of, find_particles, load_grayscale,
                       measure_nm_per_px, pack_circles, particle_rows)

SCALEBAR_NM = 50   # Gatan 比例尺標示的實際長度 (nm)
ERASE_RATIO = 0.7  # 允許重疊時的挖除比例(同 CLI 預設)


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def analyze(file, min_diameter, allow_overlap, min_area, has_scalebar, nm_per_px_manual):
    if file is None:
        raise gr.Error("請先上傳影像")
    path = Path(file)
    img = load_grayscale(path)

    # 比例尺區域按影像尺寸等比縮放(參考圖 2048² 時為 420×160)
    sb = ((round(img.shape[1] * 420 / 2048), round(img.shape[0] * 160 / 2048))
          if has_scalebar else (0, 0))

    # 校正:手動值優先,否則從比例尺自動量測(要在裁切前量)
    if nm_per_px_manual:
        nm_per_px, source = nm_per_px_manual, "手動輸入"
    else:
        nm_per_px, source = measure_nm_per_px(img, SCALEBAR_NM, sb), "比例尺自動量測"
    if not nm_per_px:
        raise gr.Error("量不到比例尺 — 請展開「進階設定」手動填入 nm/px 校正值")

    # 直接裁掉底部含比例尺的整條橫排:FDTD 幾何保持完整矩形,不會缺左下角
    crop_h = sb[1]
    if crop_h:
        img = img[:-crop_h, :]

    mask = build_mask(img)
    particles = find_particles(mask, min_area)
    if not particles:
        raise gr.Error("沒偵測到任何顆粒 — 試著調低「最小顆粒面積」")

    erase_ratio = ERASE_RATIO if allow_overlap else 1.0
    circles = pack_circles(particles, img.shape, (min_diameter / 2) / nm_per_px, erase_ratio)
    if not circles:
        raise gr.Error("拼不出任何圓 — 試著調低「最小圓直徑」")

    out_dir = Path(tempfile.mkdtemp(prefix="au_"))
    p_csv, c_csv = out_dir / "particles.csv", out_dir / "circles.csv"
    write_csv(p_csv, particle_rows(path.name, particles))
    write_csv(c_csv, circle_rows(path.name, circles, nm_per_px))

    summary = (f"偵測到 **{len(particles)}** 個島,拼出 **{len(circles)}** 顆圓,"
               f"覆蓋率 **{coverage_of(circles, mask):.1%}**  \n"
               f"校正:1 px = {nm_per_px:.4f} nm({source})"
               + (f";已裁掉底部比例尺橫排 {crop_h} px,輸出範圍 "
                  f"{img.shape[1]}×{img.shape[0]} px" if crop_h else ""))
    contours_img = cv2.cvtColor(annotate(img, particles), cv2.COLOR_BGR2RGB)
    circles_img = cv2.cvtColor(annotate_circles(img, circles), cv2.COLOR_BGR2RGB)
    return circles_img, contours_img, summary, str(c_csv), str(p_csv)


with gr.Blocks(title="TurnIntoCircle") as demo:
    gr.Markdown("# TurnIntoCircle\n"
                "上傳 TEM 影像 → 自動偵測顆粒 → 轉成 FDTD 可用的圓形清單(circles.csv)。")
    with gr.Row():
        with gr.Column(scale=1):
            file_in = gr.File(label="TEM 影像",
                              file_types=[".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"])
            min_diameter = gr.Number(value=5.0, label="最小圓直徑 (nm)",
                                     info="FDTD 網格限制,小於此直徑的圓不會產生")
            allow_overlap = gr.Checkbox(value=False, label="允許圓重疊",
                                        info="重疊的同材質圓在 FDTD 中取聯集,覆蓋率較高")
            min_area = gr.Slider(0, 500, value=100, step=10,
                                 label="最小顆粒面積 (px²)",
                                 info="偵測靈敏度:調高可濾掉雜訊小點")
            with gr.Accordion("進階設定", open=False):
                has_scalebar = gr.Checkbox(value=True, label="影像左下角有 Gatan 比例尺",
                                           info="自動量測 nm/px,並把底部含比例尺的整條橫排裁掉")
                nm_manual = gr.Number(value=None, label="nm/px 手動校正",
                                      info="留空 = 從比例尺自動量測;沒有比例尺的影像必填")
            btn = gr.Button("開始偵測", variant="primary")
        with gr.Column(scale=2):
            summary_out = gr.Markdown()
            with gr.Tabs():
                with gr.Tab("拼圓結果"):
                    circles_out = gr.Image(label="圓形填充", interactive=False)
                with gr.Tab("輪廓"):
                    contours_out = gr.Image(label="偵測到的輪廓", interactive=False)
            with gr.Row():
                c_csv_out = gr.File(label="circles.csv(FDTD 幾何輸入)")
                p_csv_out = gr.File(label="particles.csv(顆粒統計)")

    btn.click(analyze,
              inputs=[file_in, min_diameter, allow_overlap, min_area, has_scalebar, nm_manual],
              outputs=[circles_out, contours_out, summary_out, c_csv_out, p_csv_out])

if __name__ == "__main__":
    # css 藏掉頁尾的「透過 API 使用/使用 Gradio 建構/設定」三個連結
    demo.launch(inbrowser=True, css="footer {display: none !important}")
