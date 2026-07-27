"""產生 README 用的範例對照圖(docs/example.jpg)。

把「原圖」和「圓形填充結果」併成**單一張**圖片,標題直接畫在圖上。

為什麼要合成一張:README 裡用 markdown 表格或 HTML table 並排兩張圖時,
不同的 markdown 渲染器(GitHub、VSCode 預覽)會用各自的排版規則分配欄寬,
就算兩張圖的像素尺寸完全一樣,實際顯示出來還是會一大一小。
合成一張就沒有排版可言,到哪裡看都一致。

用法(在 repo 根目錄):
    .venv/bin/python detect_au.py "data/<參考圖>.tif" --no-overlap
    .venv/bin/python docs/make_example.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STEM = "Au_10nm-spin 65_120000.0V_38000X_0001"
SRC_TIF = Path("data") / f"{STEM}.tif"
SRC_CIRCLES = Path("output") / f"{STEM}_circles.png"
DST = Path("docs/example.png")  # 要透明底就不能用 JPEG

PANEL_W = 700  # 每個面板縮到這麼寬
PAD = 28  # 外框留白
GAP = 32  # 兩張圖中間的間距
LABEL_H = 46  # 標題列高度
BG = (0, 0, 0, 0)  # 透明,讓 README 在淺色/深色主題下都融入背景
# 底色透明代表標題會直接落在使用者的主題背景上,純黑或純白都會有一邊看不見,
# 因此挑一個對白底和 GitHub 深色底對比度都約 4.5:1 的中灰。
FG = (117, 117, 117, 255)
BORDER = (150, 150, 150, 255)
FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"


def load_panels():
    """讀入兩張圖,裁成相同範圍後縮到 PANEL_W。"""
    circles = Image.open(SRC_CIRCLES).convert("RGB")
    original = Image.open(SRC_TIF).convert("L").convert("RGB")

    # detect_au.py 會裁掉底部含比例尺的橫排,原圖也裁成同樣範圍,
    # 兩張才會是同一個視野、同樣尺寸。
    original = original.crop((0, 0, circles.width, circles.height))

    h = round(circles.height * PANEL_W / circles.width)
    size = (PANEL_W, h)
    return (original.resize(size, Image.LANCZOS),
            circles.resize(size, Image.LANCZOS))


def main():
    left, right = load_panels()
    panel_h = left.height

    canvas = Image.new("RGBA",
                       (PAD * 2 + PANEL_W * 2 + GAP, PAD * 2 + LABEL_H + panel_h),
                       BG)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT_PATH, 28)

    for i, (panel, label) in enumerate([(left, "輸入:TEM 原圖"),
                                        (right, "輸出:圓形填充")]):
        x = PAD + i * (PANEL_W + GAP)
        y = PAD + LABEL_H
        draw.text((x, PAD + 4), label, font=font, fill=FG)
        canvas.paste(panel, (x, y))
        # 圖的背景偏白,加一圈細框才不會跟畫布融在一起
        draw.rectangle([x, y, x + PANEL_W - 1, y + panel_h - 1], outline=BORDER)

    # 直接存 RGBA PNG 是 1.3 MB;縮成 255 色調色盤只剩約 290 KB,
    # 而且畫面是灰階 + 單一綠色,看不出色階斷層。
    # 必須用 FASTOCTREE —— 只有它會把 alpha 一起量化進調色盤(存成 tRNS),
    # 換成預設的 MEDIANCUT 透明底就會不見。
    canvas.quantize(colors=255, method=Image.FASTOCTREE).save(DST, optimize=True)
    print(f"{DST} {canvas.size} {DST.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
