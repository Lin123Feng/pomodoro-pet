"""生成分发用的多尺寸 .ico（和桌宠同一个番茄，不许另画一个）"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from PIL import Image
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
ASSETS = HERE / "assets"
ASSETS.mkdir(exist_ok=True)


def draw(size: int, eyes: bool = True) -> QPixmap:
    """按桌宠的比例画番茄：圆身 + 五片叶 + 眼睛 + 左上高光"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = size * 0.355
    cx, cy = size / 2, size * 0.57

    grad = QRadialGradient(cx - r * 0.35, cy - r * 0.45, r * 1.9)
    grad.setColorAt(0.0, QColor("#ea7159"))
    grad.setColorAt(1.0, QColor("#d34e3a"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, cy), r, r * 0.97)

    leaf = QColor("#3aa675")
    p.setBrush(QBrush(leaf))
    for i in range(5):
        ang = math.pi * (-0.15 - 0.175 * i)
        lx = cx + math.cos(ang) * r * 0.55
        ly = cy - r * 0.78 + math.sin(ang) * r * 0.22
        p.drawEllipse(QPointF(lx, ly), r * 0.26, r * 0.13)
    p.setBrush(QBrush(leaf.darker(112)))
    p.drawEllipse(QPointF(cx, cy - r * 0.92), r * 0.10, r * 0.16)

    if eyes:
        p.setBrush(QBrush(QColor("#3d2b28")))
        for dx in (-1, 1):
            p.drawEllipse(QPointF(cx + dx * r * 0.30, cy - r * 0.05),
                          r * 0.085, r * 0.105)

    p.setBrush(QBrush(QColor(255, 255, 255, 64)))
    p.drawEllipse(QPointF(cx - r * 0.42, cy - r * 0.46), r * 0.19, r * 0.13)
    p.end()
    return pm


big = draw(512)
big.save(str(ASSETS / "tomato_512.png"))

# 小尺寸（16/24/32）不画眼睛，糊成一团更丑；用无眼版本单独渲染更好看
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
frames = {}
for w, h in sizes:
    pm = draw(w, eyes=w >= 48)
    path = ASSETS / f"_tmp_{w}.png"
    pm.save(str(path))
    frames[(w, h)] = Image.open(path).convert("RGBA")

ico = ASSETS / "pomodoro.ico"
frames[(256, 256)].save(
    ico, format="ICO",
    sizes=sizes,
    append_images=[frames[s] for s in sizes if s != (256, 256)],
)
for w, _ in sizes:
    (ASSETS / f"_tmp_{w}.png").unlink()

print("已生成:", ico, ico.stat().st_size, "字节")
print("尺寸:", ", ".join(f"{w}x{h}" for w, h in sizes))
