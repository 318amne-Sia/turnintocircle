"""Step 5: 找輪廓並疊畫回原圖 —— 完成「把 Au 框起來」

cv2.findContours 會沿著每塊白色區域的邊界走一圈,
回傳一串「邊界點座標」(這就是輪廓 contour)。

找到輪廓後還要過濾:
  1. 面積太小的 → 殘餘雜訊,丟掉
  2. 比例尺區域(左下角)→ 不是 Au,丟掉
剩下的才是真正的 Au 顆粒,用綠線畫回原圖。
"""
import cv2
import numpy as np
from PIL import Image

img = np.array(Image.open("data/Au_10nm-spin 65_120000.0V_38000X_0001.tif").convert("L"))

# --- Step 3 + 4 的成果:乾淨的遮罩 ---
_, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

# --- 遮掉左下角的比例尺區域(直接塗黑,不參與找輪廓) ---
# 從 preview 目測比例尺在左下角約 300x100 像素的範圍(2048 解析度下)
SCALEBAR_W, SCALEBAR_H = 420, 160
mask[-SCALEBAR_H:, :SCALEBAR_W] = 0

# --- 找輪廓 ---
# RETR_EXTERNAL: 只要最外圈輪廓(顆粒裡的洞不要)
# CHAIN_APPROX_SIMPLE: 直線段只存端點,省記憶體
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"找到 {len(contours)} 個輪廓(過濾前)")

# --- 按面積過濾 ---
MIN_AREA = 100  # 像素平方;小於這個的當雜訊丟掉
particles = [c for c in contours if cv2.contourArea(c) >= MIN_AREA]
print(f"面積 >= {MIN_AREA} px² 的輪廓: {len(particles)} 個")

areas = np.array([cv2.contourArea(c) for c in particles])
print(f"面積範圍: {areas.min():.0f} ~ {areas.max():.0f} px², 中位數 {np.median(areas):.0f} px²")

# --- 疊畫:灰階原圖轉成 BGR 彩圖,才能畫綠色輪廓 ---
canvas = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
cv2.drawContours(canvas, particles, -1, (0, 220, 0), 2)  # -1 = 畫全部, 綠色, 線寬2

cv2.imwrite("output/contours_full.png", canvas)
cv2.imwrite("output/step5_preview.png", cv2.resize(canvas, (768, 768)))
print("已儲存 output/contours_full.png(全解析度)與 output/step5_preview.png(縮圖)")
