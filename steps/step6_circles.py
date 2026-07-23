"""Step 6: 距離變換 + 貪婪圓形填充 —— 把每個 Au 島「拼成一堆圓」

核心概念:距離變換 (distance transform)
  對遮罩裡每個白色像素,計算「到最近的黑色邊界」的距離。
  → 距離值最大的像素 = 能塞下最大內切圓的圓心,距離值 = 半徑。

貪婪填充演算法(對每個島獨立進行):
  1. 算距離變換,找最大值 → 放下一顆最大內切圓
  2. 把這顆圓從工作遮罩上挖掉(塗黑)
  3. 重複,直到剩餘空間塞不下半徑 >= R_MIN 的圓
  每次挖掉後重算距離變換,下一顆圓自然會避開已放的圓。
"""
import cv2
import numpy as np
from PIL import Image

R_MIN = 4      # 最小圓半徑(px):塞不下這麼大的圓就停,值越小拼得越細
MIN_AREA = 100  # 沿用 detect_au.py 的顆粒面積過濾

img = np.array(Image.open("data/Au_10nm-spin 65_120000.0V_38000X_0001.tif").convert("L"))

# --- 前面步驟的成果:乾淨遮罩 + 輪廓 ---
_, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
mask[-160:, :420] = 0  # 遮比例尺
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
particles = [c for c in contours if cv2.contourArea(c) >= MIN_AREA]

# --- 教學用:把整張圖的距離變換存成偽彩色圖,親眼看看「山峰」在哪 ---
dist_full = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
dist_vis = cv2.applyColorMap(
    cv2.normalize(dist_full, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8),
    cv2.COLORMAP_JET)
cv2.imwrite("output/step6_distance.png", cv2.resize(dist_vis, (768, 768)))

# --- 對每個島做貪婪圓形填充 ---
# 只在島的外接矩形內運算(小圖),比每次對整張 2048² 重算快非常多
circles = []  # (cx, cy, r) 全圖座標
for c in particles:
    x, y, w, h = cv2.boundingRect(c)
    # 在小畫布上畫出「只有這個島」的實心遮罩
    # (不能直接裁 mask:外接矩形可能包到隔壁島的一角)
    work = np.zeros((h, w), np.uint8)
    cv2.drawContours(work, [c], -1, 255, -1, offset=(-x, -y))

    while True:
        dist = cv2.distanceTransform(work, cv2.DIST_L2, 5)
        _, r, _, (px, py) = cv2.minMaxLoc(dist)  # 最大距離值與其位置
        if r < R_MIN:
            break
        circles.append((x + px, y + py, r))
        cv2.circle(work, (px, py), int(r), 0, -1)  # 挖掉這顆圓

print(f"{len(particles)} 個島 → 拼出 {len(circles)} 顆圓")
radii = np.array([r for _, _, r in circles])
print(f"半徑範圍 {radii.min():.0f} ~ {radii.max():.0f} px, 中位數 {np.median(radii):.0f} px")

# 覆蓋率:所有圓的聯集面積 / 島的總面積
cover = np.zeros_like(mask)
for cx, cy, r in circles:
    cv2.circle(cover, (int(cx), int(cy)), int(round(r)), 255, -1)
coverage = (cover & mask).sum() / mask.sum()
print(f"圓形覆蓋了島面積的 {coverage:.1%}(剩下的是圓與圓之間的縫隙)")

# --- 視覺化 1:圓疊在原圖上 ---
overlay = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
for cx, cy, r in circles:
    cv2.circle(overlay, (int(cx), int(cy)), int(round(r)), (0, 220, 0), 2)
cv2.imwrite("output/step6_overlay.png", overlay)

# --- 視覺化 2:左 = 原始島形狀,右 = 純圓形重建,並排比較 ---
recon = np.full((2048, 2048), 255, np.uint8)
for cx, cy, r in circles:
    cv2.circle(recon, (int(cx), int(cy)), int(round(r)), 90, -1)
side = np.hstack([cv2.resize(255 - mask, (768, 768)),
                  np.full((768, 8), 0, np.uint8),
                  cv2.resize(recon, (768, 768))])
cv2.imwrite("output/step6_compare.png", side)
print("已儲存 output/step6_distance.png, step6_overlay.png, step6_compare.png")
