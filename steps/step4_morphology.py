"""Step 4: 形態學運算 —— 清理二值化遮罩上的雜訊

兩個基本操作(都用一個小的「結構元素 kernel」在圖上掃):
  侵蝕 erode  : 白色區域向內縮一圈 → 小白點直接消失
  膨脹 dilate : 白色區域向外長一圈 → 小黑洞被填平

組合技:
  開運算 opening = 先侵蝕再膨脹
    → 小白點在侵蝕時消失,大顆粒縮了又長回來,形狀幾乎不變
  閉運算 closing = 先膨脹再侵蝕
    → 小黑洞在膨脹時被填掉,大顆粒長了又縮回來

kernel 大小決定「多小算雜訊」:5x5 橢圓 → 半徑 2~3 像素以下的點會被清掉
"""
import cv2
import numpy as np
from PIL import Image

img = np.array(Image.open("data/Au_10nm-spin 65_120000.0V_38000X_0001.tif").convert("L"))
_, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)


def count_blobs(m, name):
    """數一數遮罩裡有幾塊互相分離的白色區域(連通區域)"""
    n, _ = cv2.connectedComponents(m)
    print(f"{name}: {n - 1} 塊白色區域")  # -1 是扣掉背景
    return n - 1


count_blobs(mask, "清理前        ")

kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

# 開運算:清掉背景上的細碎白點
opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
count_blobs(opened, "開運算後      ")

# 閉運算:填掉顆粒內部的小黑洞
cleaned = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
count_blobs(cleaned, "開+閉運算後   ")

cv2.imwrite("output/mask_cleaned.png", cleaned)

# 對照圖:取右下 512x512 的「原尺寸」小區域(不縮圖,雜訊點才看得清楚)
y, x = 1200, 1200
crop_before = mask[y:y + 512, x:x + 512]
crop_after = cleaned[y:y + 512, x:x + 512]
side = np.hstack([crop_before, np.full((512, 8), 128, np.uint8), crop_after])
cv2.imwrite("output/step4_compare.png", side)
print("已儲存 output/mask_cleaned.png 與 output/step4_compare.png(左清理前、右清理後,1:1 裁切)")
