"""量一下面板里各控件的真实几何，确认没有溢出/不等宽"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pomodoro_pet as P
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
TMP = HERE / "_tmp_metrics.json"
if TMP.exists():
    TMP.unlink()
store = P.Store(TMP)
ctrl = P.Controller(store)
pet = P.PetWindow(ctrl, store)
panel = P.Panel(ctrl, store, pet)
panel.move(-4000, -4000)
panel.show()
for _ in range(5):
    app.processEvents()

card = panel.card
left, right = panel.kpi_count[0], panel.kpi_focus[0]
g = lambda w: w.geometry()

print(f"面板窗口      : {panel.width()} x {panel.height()}")
print(f"白卡片        : x={card.x()} y={card.y()} w={card.width()} h={card.height()}")
print(f"卡片内容右侧界: {card.x() + card.width() - 22}")
print(f"KPI 左卡      : x={left.geometry().x()} w={left.width()}  右缘={left.geometry().right()}")
print(f"KPI 右卡      : x={right.geometry().x()} w={right.width()}  右缘={right.geometry().right()}")
print(f"两卡等宽      : {left.width() == right.width()}")
print(f"主按钮        : x={panel.btn_main.geometry().x()} w={panel.btn_main.width()}")
print(f"重置按钮      : x={panel.btn_reset.geometry().x()} w={panel.btn_reset.width()}")
print(f"环形          : x={panel.ring.geometry().x()} w={panel.ring.width()}")
print(f"设置行 spin 宽度: {panel.spin_work.width()} / {panel.spin_break.width()}")
inner_w = card.width() - 44
print(f"卡片内容可用宽 : {inner_w}")
print(f"两卡+间距合计  : {left.width() + right.width() + 12}  (应 <= {inner_w})")
print(f"是否溢出       : {left.width() + right.width() + 12 > inner_w}")
