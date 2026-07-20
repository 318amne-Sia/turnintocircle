"""Au 顆粒偵測工具 —— 整合 steps/ 學到的完整管線

流程:讀圖 → Otsu 二值化 → 形態學清理 → 遮比例尺 → 找輪廓 → 面積過濾
      → 貪婪圓形填充(供 FDTD 建模)
輸出:每張圖
  <原檔名>_contours.png  輪廓標註圖
  <原檔名>_circles.png   拼圓標註圖
  加上彙整的 particles.csv(顆粒統計)與 circles.csv(FDTD 用圓形清單, nm 單位)

用法(從專案根目錄執行):
  .venv\\Scripts\\python.exe detect_au.py data                # 處理整個資料夾
  .venv\\Scripts\\python.exe detect_au.py data\\xxx.tif       # 處理單張
  .venv\\Scripts\\python.exe detect_au.py data --min-area 200 # 調整過濾參數
  .venv\\Scripts\\python.exe detect_au.py data --min-diameter 5 --erase-ratio 0.7
"""
import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def load_grayscale(path):
    """讀取影像並轉成 8-bit 灰階矩陣(step1)"""
    return np.array(Image.open(path).convert("L"))


def build_mask(img, kernel_size=5):
    """Otsu 二值化(暗 = Au = 白色前景)+ 開閉運算清理(step2~4)"""
    _, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def mask_scalebar(mask, width, height):
    """把左下角比例尺區域塗黑,排除在偵測之外(step5)"""
    if width > 0 and height > 0:
        mask[-height:, :width] = 0
    return mask


def find_particles(mask, min_area):
    """找最外圈輪廓並按面積過濾(step5)"""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [c for c in contours if cv2.contourArea(c) >= min_area]


def measure(contour):
    """量測單一顆粒:面積、周長、圓形度、質心

    圓形度 circularity = 4πA / P²,正圓 = 1.0,越不圓越接近 0
    """
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, closed=True)
    circularity = 4 * math.pi * area / perimeter**2 if perimeter > 0 else 0
    m = cv2.moments(contour)
    cx = m["m10"] / m["m00"] if m["m00"] else 0
    cy = m["m01"] / m["m00"] if m["m00"] else 0
    return {
        "area_px2": round(area, 1),
        "perimeter_px": round(perimeter, 1),
        "circularity": round(circularity, 3),
        "centroid_x": round(cx, 1),
        "centroid_y": round(cy, 1),
    }


def measure_nm_per_px(img, scalebar_nm, scalebar_region):
    """從左下角比例尺自動校正 nm/px(step6 之後加入)

    在比例尺區域內找「最長的連續暗像素橫條」= 比例尺本體,
    其像素長度對應 scalebar_nm 標示的實際長度。
    """
    w, h = scalebar_region
    if w <= 0 or h <= 0:
        return None
    region = img[-h:, :w]
    best = 0
    for row in region < 50:  # 暗於 50 視為比例尺的黑色
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        if starts.size:
            best = max(best, int((ends - starts).max()))
    return scalebar_nm / best if best > 0 else None


def pack_circles(particles, shape, r_min_px, erase_ratio):
    """貪婪最大內切圓填充(step6):把每個島拼成一堆圓

    對每個島:距離變換找最大內切圓 → 放圓 → 挖掉 → 重複,
    直到塞不下半徑 >= r_min_px 的圓。
    erase_ratio < 1.0 時挖掉的圓比放的圓小,後面的圓可部分重疊
    (重疊的圓在 FDTD 中取聯集,可把縫隙補回來);1.0 = 完全不重疊。
    回傳 [(island_id, cx, cy, r), ...](px 座標,原點 = 影像左上角)。
    """
    circles = []
    for island_id, c in enumerate(particles, start=1):
        x, y, w, h = cv2.boundingRect(c)
        # 小畫布上只畫這個島(直接裁遮罩會包到隔壁島的角)
        work = np.zeros((h, w), np.uint8)
        cv2.drawContours(work, [c], -1, 255, -1, offset=(-x, -y))
        while True:
            dist = cv2.distanceTransform(work, cv2.DIST_L2, 5)
            _, r, _, (px, py) = cv2.minMaxLoc(dist)
            if r < r_min_px:
                break
            circles.append((island_id, x + px, y + py, r))
            cv2.circle(work, (px, py), max(1, int(r * erase_ratio)), 0, -1)
    return circles


def coverage_of(circles, mask):
    """圓的聯集蓋住島面積的比例(檢查拼圓還原度)"""
    cover = np.zeros_like(mask)
    for _, cx, cy, r in circles:
        cv2.circle(cover, (int(cx), int(cy)), int(round(r)), 255, -1)
    total = mask.sum()
    return (cover & mask).sum() / total if total else 0


def annotate(img, particles):
    """把輪廓和編號疊畫在原圖上"""
    canvas = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.drawContours(canvas, particles, -1, (0, 220, 0), 2)
    for i, c in enumerate(particles, start=1):
        m = cv2.moments(c)
        if m["m00"]:
            pos = (int(m["m10"] / m["m00"]) - 10, int(m["m01"] / m["m00"]) + 8)
            cv2.putText(canvas, str(i), pos, cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 100, 255), 2)
    return canvas


def annotate_circles(img, circles):
    """把拼出的圓疊畫在原圖上"""
    canvas = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for _, cx, cy, r in circles:
        cv2.circle(canvas, (int(cx), int(cy)), int(round(r)), (0, 220, 0), 2)
    return canvas


def process_image(path, out_dir, args):
    """處理一張圖,回傳 (顆粒統計列, 圓形清單列)"""
    img = load_grayscale(path)

    # 先量比例尺再遮掉它;量不到就退回 --nm-per-px 手動值
    nm_per_px = measure_nm_per_px(img, args.scalebar_nm, args.scalebar) or args.nm_per_px
    if not nm_per_px:
        raise SystemExit(f"{path.name}: 量不到比例尺,請用 --nm-per-px 手動指定校正值")

    mask = mask_scalebar(build_mask(img), *args.scalebar)
    particles = find_particles(mask, args.min_area)

    out_png = out_dir / f"{path.stem}_contours.png"
    cv2.imwrite(str(out_png), annotate(img, particles))

    # 拼圓:最小直徑 (nm) → 最小半徑 (px)
    erase_ratio = 1.0 if args.no_overlap else args.erase_ratio
    r_min_px = (args.min_diameter / 2) / nm_per_px
    circles = pack_circles(particles, img.shape, r_min_px, erase_ratio)
    cv2.imwrite(str(out_dir / f"{path.stem}_circles.png"), annotate_circles(img, circles))

    print(f"{path.name}: {len(particles)} 個島, 拼出 {len(circles)} 顆圓 "
          f"(覆蓋率 {coverage_of(circles, mask):.1%}, 1px = {nm_per_px:.4f} nm) → {out_png}")

    particle_rows = [{"image": path.name, "particle_id": i, **measure(c)}
                     for i, c in enumerate(particles, start=1)]
    # FDTD 用的圓形清單:座標原點 = 影像左上角, y 向下, 單位 nm
    circle_rows = [{
        "image": path.name,
        "island_id": iid,
        "circle_id": i,
        "x_nm": round(cx * nm_per_px, 2),
        "y_nm": round(cy * nm_per_px, 2),
        "diameter_nm": round(2 * r * nm_per_px, 2),
        "x_px": cx,
        "y_px": cy,
        "radius_px": round(r, 2),
    } for i, (iid, cx, cy, r) in enumerate(circles, start=1)]
    return particle_rows, circle_rows


def main():
    parser = argparse.ArgumentParser(description="偵測 TEM 影像中的 Au 顆粒並框出輪廓")
    parser.add_argument("input", help="TIF 檔案或資料夾")
    parser.add_argument("--out", default="output", help="輸出資料夾(預設 output)")
    parser.add_argument("--min-area", type=int, default=100,
                        help="最小顆粒面積 px²,小於此值視為雜訊(預設 100)")
    parser.add_argument("--scalebar", type=int, nargs=2, default=[420, 160],
                        metavar=("W", "H"),
                        help="左下角比例尺遮蔽區域的寬高,0 0 表示不遮(預設 420 160)")
    parser.add_argument("--scalebar-nm", type=float, default=50,
                        help="比例尺標示的實際長度 nm,用於自動校正(預設 50)")
    parser.add_argument("--nm-per-px", type=float, default=None,
                        help="手動指定 nm/px 校正值(預設從比例尺自動量測)")
    parser.add_argument("--min-diameter", type=float, default=5.0,
                        help="拼圓的最小圓直徑 nm,FDTD 網格限制(預設 5)")
    parser.add_argument("--erase-ratio", type=float, default=0.7,
                        help="拼圓時挖除半徑比例,<1 允許圓部分重疊補縫隙(預設 0.7)")
    parser.add_argument("--no-overlap", action="store_true",
                        help="禁止圓互相重疊(等同 --erase-ratio 1.0,覆蓋率會下降)")
    args = parser.parse_args()

    src = Path(args.input)
    files = sorted(src.glob("*.tif")) if src.is_dir() else [src]
    if not files:
        parser.error(f"{src} 裡沒有 .tif 檔案")

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)

    particle_rows, circle_rows = [], []
    for f in files:
        p_rows, c_rows = process_image(f, out_dir, args)
        particle_rows.extend(p_rows)
        circle_rows.extend(c_rows)

    for name, rows in [("particles.csv", particle_rows), ("circles.csv", circle_rows)]:
        csv_path = out_dir / name
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"{name}: {len(rows)} 筆 → {csv_path}")


if __name__ == "__main__":
    main()
