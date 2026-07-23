"""Step 2: 灰階直方圖 —— 看「Au 顆粒」和「背景」的亮度分佈

直方圖 = 統計每個亮度值 (0~255) 各有多少個像素。
如果顆粒和背景的亮度差異明顯,直方圖會出現「兩座山」:
  - 左邊的山:暗像素 → Au 顆粒
  - 右邊的山:亮像素 → 背景
二值化就是在兩座山之間的「谷底」選一條分界線(閾值)。
"""
import cv2
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

img = np.array(Image.open("data/Au_10nm-spin 65_120000.0V_38000X_0001.tif").convert("L"))

# 統計每個亮度值的像素數量(256 個 bin,範圍 0~255)
hist, _ = np.histogram(img, bins=256, range=(0, 256))

# Otsu 法:自動找閾值的經典演算法。
# 原理:嘗試每一個可能的閾值,選出讓「兩群的組內變異數總和最小」
# (等價於兩群分得最開)的那一個 —— 不用人工猜谷底在哪。
otsu_t, _ = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
print(f"Otsu 自動選出的閾值: {otsu_t:.0f}")
print(f"亮度 < {otsu_t:.0f} 的像素會被判定為 Au(暗),>= 則是背景(亮)")

dark_ratio = (img < otsu_t).mean()
print(f"被判為 Au 的像素比例: {dark_ratio:.1%}")

# 畫直方圖並標出 Otsu 閾值的位置
fig, ax = plt.subplots(figsize=(10, 5))
ax.fill_between(range(256), hist, color="gray", alpha=0.7)
ax.axvline(otsu_t, color="red", linestyle="--", linewidth=2,
           label=f"Otsu threshold = {otsu_t:.0f}")
ax.set_xlabel("Gray level (0=black, 255=white)")
ax.set_ylabel("Pixel count")
ax.set_title("Histogram: dark peak = Au, bright peak = background")
ax.set_xlim(0, 255)
ax.legend()
fig.tight_layout()
fig.savefig("output/histogram.png", dpi=120)
print("已儲存 output/histogram.png")
