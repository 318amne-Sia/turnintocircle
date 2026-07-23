"""Step 3: 二值化 —— 用 Otsu 閾值把圖分成「Au / 背景」兩類

規則:亮度 < 閾值 (131) 的像素 → 255 (白) = Au 顆粒
      亮度 >= 閾值        的像素 → 0   (黑) = 背景

注意方向是「反的」(THRESH_BINARY_INV):
影像處理的慣例是「前景 = 白 (255)、背景 = 黑 (0)」,
之後 findContours 只會找白色區域的輪廓。
我們的目標 Au 在原圖是暗的,所以要反轉,讓 Au 變成白色前景。
"""
import cv2
import numpy as np
from PIL import Image

img = np.array(Image.open("data/Au_10nm-spin 65_120000.0V_38000X_0001.tif").convert("L"))

# THRESH_OTSU: 自動算閾值(忽略我們傳入的 0)
# THRESH_BINARY_INV: 小於閾值 → 255,大於等於 → 0(反向二值化)
otsu_t, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
print(f"使用閾值: {otsu_t:.0f}")
print(f"mask 中只有兩種值: {np.unique(mask)}")
print(f"白色(Au)比例: {(mask == 255).mean():.1%}")

# 存全解析度的遮罩
cv2.imwrite("output/mask.png", mask)

# 並排比較圖:左 = 原圖,右 = 遮罩(各縮成 512 寬,方便一眼對照)
small_img = cv2.resize(img, (512, 512))
small_mask = cv2.resize(mask, (512, 512), interpolation=cv2.INTER_NEAREST)
side = np.hstack([small_img, np.full((512, 8), 128, np.uint8), small_mask])
cv2.imwrite("output/step3_compare.png", side)
print("已儲存 output/mask.png 與 output/step3_compare.png(左原圖、右遮罩)")
