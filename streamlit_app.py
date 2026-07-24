"""Au 顆粒偵測 —— 網頁介面(Streamlit)

給不熟 CLI 的使用者:上傳 TEM 影像 → 自動偵測 Au 顆粒、拼圓
→ 預覽結果並下載 FDTD 用的 circles.csv。偵測管線直接重用 detect_au.py。

本機啟動(從專案根目錄):
  .venv/bin/streamlit run streamlit_app.py
線上版部署在 Streamlit Community Cloud,push 到 master 就會自動更新。
"""
import csv
import io

import cv2
import streamlit as st

from detect_au import (annotate, annotate_circles, build_mask, circle_rows,
                       coverage_of, find_particles, load_grayscale,
                       measure_nm_per_px, pack_circles, particle_rows)

SCALEBAR_NM = 50   # Gatan 比例尺標示的實際長度 (nm)
ERASE_RATIO = 0.7  # 允許重疊時的挖除比例(同 CLI 預設)


def csv_bytes(rows):
    """把資料列轉成 CSV bytes 供 st.download_button 直接送出

    utf-8-sig(帶 BOM)讓 Excel 開啟時不會把中文欄位變亂碼。
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def analyze(upload, min_diameter, allow_overlap, min_area, has_scalebar, nm_manual):
    """跑完整管線,回傳可直接渲染的結果 dict;參數不合理時丟 ValueError"""
    upload.seek(0)  # Streamlit 每次互動都會重跑腳本,檔案指標可能停在 EOF
    img = load_grayscale(upload)  # PIL 也吃 file-like 物件,不必先落地成暫存檔

    # 比例尺區域按影像尺寸等比縮放(參考圖 2048² 時為 420×160)
    sb = ((round(img.shape[1] * 420 / 2048), round(img.shape[0] * 160 / 2048))
          if has_scalebar else (0, 0))

    # 校正:手動值優先,否則從比例尺自動量測(要在裁切前量)
    if nm_manual:
        nm_per_px, source = nm_manual, "手動輸入"
    else:
        nm_per_px, source = measure_nm_per_px(img, SCALEBAR_NM, sb), "比例尺自動量測"
    if not nm_per_px:
        raise ValueError("量不到比例尺 —— 請展開「進階設定」手動填入 nm/px 校正值")

    # 直接裁掉底部含比例尺的整條橫排:FDTD 幾何保持完整矩形,不會缺左下角
    crop_h = sb[1]
    if crop_h:
        img = img[:-crop_h, :]

    mask = build_mask(img)
    particles = find_particles(mask, min_area)
    if not particles:
        raise ValueError("沒偵測到任何顆粒 —— 試著調低「最小顆粒面積」")

    erase_ratio = ERASE_RATIO if allow_overlap else 1.0
    circles = pack_circles(particles, img.shape, (min_diameter / 2) / nm_per_px, erase_ratio)
    if not circles:
        raise ValueError("拼不出任何圓 —— 試著調低「最小圓直徑」")

    return {
        "n_particles": len(particles),
        "n_circles": len(circles),
        "coverage": coverage_of(circles, mask),
        "nm_per_px": nm_per_px,
        "source": source,
        "crop_h": crop_h,
        "size": (img.shape[1], img.shape[0]),
        "circles_img": cv2.cvtColor(annotate_circles(img, circles), cv2.COLOR_BGR2RGB),
        "contours_img": cv2.cvtColor(annotate(img, particles), cv2.COLOR_BGR2RGB),
        "circles_csv": csv_bytes(circle_rows(upload.name, circles, nm_per_px)),
        "particles_csv": csv_bytes(particle_rows(upload.name, particles)),
    }


st.set_page_config(page_title="TurnIntoCircle", page_icon="⚪", layout="wide")

st.title("TurnIntoCircle")
st.caption("上傳 TEM 影像 → 自動偵測顆粒 → 轉成 FDTD 可用的圓形清單(circles.csv)")

with st.sidebar:
    upload = st.file_uploader("TEM 影像",
                              type=["tif", "tiff", "png", "jpg", "jpeg", "bmp"])
    min_diameter = st.number_input("最小圓直徑 (nm)", value=5.0, min_value=0.1, step=0.5,
                                   help="FDTD 網格限制,小於此直徑的圓不會產生")
    allow_overlap = st.checkbox("允許圓重疊",
                                help="重疊的同材質圓在 FDTD 中取聯集,覆蓋率較高")
    min_area = st.slider("最小顆粒面積 (px²)", 0, 500, 100, step=10,
                         help="偵測靈敏度:調高可濾掉雜訊小點")

    with st.expander("進階設定"):
        has_scalebar = st.checkbox("影像左下角有 Gatan 比例尺", value=True,
                                   help="自動量測 nm/px,並把底部含比例尺的整條橫排裁掉")
        nm_manual = st.number_input("nm/px 手動校正", value=None, min_value=0.0,
                                    step=0.001, format="%.4f",
                                    help="留空 = 從比例尺自動量測;沒有比例尺的影像必填")

    run = st.button("開始偵測", type="primary", width="stretch",
                    disabled=upload is None)

# 結果存進 session_state:按下載鈕會觸發腳本重跑,不存的話畫面會整個消失
if run:
    try:
        with st.spinner("偵測中…"):
            st.session_state.result = analyze(upload, min_diameter, allow_overlap,
                                              min_area, has_scalebar, nm_manual)
        st.session_state.error = None
    except ValueError as e:
        st.session_state.result, st.session_state.error = None, str(e)

if st.session_state.get("error"):
    st.error(st.session_state.error)

res = st.session_state.get("result")
if res is None:
    st.info("請在左側上傳一張 TEM 影像,然後按「開始偵測」。")
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("偵測到的島", res["n_particles"])
    c2.metric("拼出的圓", res["n_circles"])
    c3.metric("覆蓋率", f"{res['coverage']:.1%}")

    note = f"校正:1 px = {res['nm_per_px']:.4f} nm({res['source']})"
    if res["crop_h"]:
        note += (f";已裁掉底部比例尺橫排 {res['crop_h']} px,"
                 f"輸出範圍 {res['size'][0]}×{res['size'][1]} px")
    st.caption(note)

    d1, d2 = st.columns(2)
    d1.download_button("下載 circles.csv(FDTD 幾何輸入)", res["circles_csv"],
                       file_name="circles.csv", mime="text/csv",
                       width="stretch")
    d2.download_button("下載 particles.csv(顆粒統計)", res["particles_csv"],
                       file_name="particles.csv", mime="text/csv",
                       width="stretch")

    tab1, tab2 = st.tabs(["拼圓結果", "輪廓"])
    tab1.image(res["circles_img"], caption="圓形填充", width="stretch")
    tab2.image(res["contours_img"], caption="偵測到的輪廓", width="stretch")
