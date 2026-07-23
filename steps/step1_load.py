"""Step 1: 讀取 TIF 並理解「影像 = 數字矩陣」"""
import numpy as np
from PIL import Image

# 讀取 TIF。這張圖是 palette 模式(mode "P"),
# 每個像素存的是「調色盤的索引」而不是亮度值,
# 所以先 convert("L") 轉成真正的 8-bit 灰階(L = Luminance)
im = Image.open("data/Au_10nm-spin 65_120000.0V_38000X_0001.tif").convert("L")

# 轉成 numpy 陣列 —— 之後所有處理都是對這個矩陣做數學運算
img = np.array(im)

print("形狀 (高, 寬):", img.shape)
print("資料型別:", img.dtype)          # uint8 = 每個像素 0~255
print("最暗像素值:", img.min())
print("最亮像素值:", img.max())
print("平均亮度:", round(img.mean(), 1))

# 看一小塊 8x8 的像素值,感受一下「圖就是數字」
print("\n左上角 8x8 的原始像素值:")
print(img[:8, :8])

# 存一張縮小的 PNG 預覽(TIF 太大,方便快速查看)
preview = im.resize((512, 512))
preview.save("output/preview.png")
print("\n已儲存 output/preview.png (512x512 縮圖)")
