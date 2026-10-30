"""番茄桌宠 · 视觉自测：把四种桌宠状态 + 面板 + 提醒卡片拼成一张图，供人工检查

运行：D:\\Users\\miniconda3\\envs\\myenv\\python pomodoro_test\\test_shots.py
输出：pomodoro_test/out/*.png
"""
import sys
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))

import pomodoro_pet as P
from PyQt6.QtCore import QPoint  # noqa: F401
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

OUT = HERE / "out"
OUT.mkdir(parents=True, exist_ok=True)

app = QApplication(sys.argv)

TMP_STATE = HERE / "_tmp_state.json"
if TMP_STATE.exists():
    TMP_STATE.unlink()
store = P.Store(TMP_STATE)
store.data["today"] = {"date": P.date.today().isoformat(), "count": 3, "focus_sec": 3 * 25 * 60}

BG = QColor("#eef3f6")


def shot(widget: P.QWidget, name: str) -> QPixmap:
    # 挪到屏幕外再显示：拿到真实字体渲染，又不打扰正在用电脑的人
    widget.move(-4000, -4000)
    widget.show()
    for _ in range(3):
        app.processEvents()
    pm = widget.grab()
    canvas = QPixmap(pm.size())
    canvas.fill(BG)
    p = QPainter(canvas)
    p.drawPixmap(0, 0, pm)
    p.end()
    canvas.save(str(OUT / name))
    return canvas


# ---------------------------------------------------------------- 桌宠四态
cases = [
    ("工作 · 进行中", "work", "running", 25 * 60 * 0.62),
    ("工作 · 已暂停", "work", "paused", 25 * 60 * 0.38),
    ("休息 · 进行中", "break", "running", 5 * 60 * 0.55),
    ("到点 · 等确认", "work", "finished", 0.0),
]
pet_shots = []
for label, phase, state, remain in cases:
    ctrl = P.Controller(store)
    ctrl.phase = phase
    ctrl.state = state
    ctrl.remaining = remain
    pet = P.PetWindow(ctrl, store)
    pet_shots.append((label, shot(pet, f"pet_{state}_{phase}.png")))

# ---------------------------------------------------------------- 面板
ctrl2 = P.Controller(store)
ctrl2.phase = "work"
ctrl2.state = "running"
ctrl2.remaining = 25 * 60 * 0.62
pet2 = P.PetWindow(ctrl2, store)
panel = P.Panel(ctrl2, store, pet2)
panel_shot = shot(panel, "panel.png")

# ---------------------------------------------------------------- 提醒卡片
def grab_widget(widget) -> QPixmap:
    widget.move(-4000, -4000)
    widget.show()
    for _ in range(3):
        app.processEvents()
    pm = widget.grab()
    canvas = QPixmap(pm.size())
    canvas.fill(BG)
    p = QPainter(canvas)
    p.drawPixmap(0, 0, pm)
    p.end()
    return canvas


def make_card(minutes_late: int = 0, name: str = "notice.png") -> QPixmap:
    n = P.NoticeCard()
    n.show_card("work", "专注结束",
                "这一轮记下了。休息 5 分钟，还是直接开始下一轮？",
                "休息 5 分钟", "跳过休息", lambda: None, lambda: None)
    if minutes_late:
        n._fired_at = P.datetime.now() - timedelta(minutes=minutes_late)
        n.fired_label.setText(n._fired_at.strftime("%H:%M"))
        n._refresh_meta()
    pm = grab_widget(n)
    pm.save(str(OUT / name))
    return pm


card_canvas = make_card(0, "notice_fresh.png")
card_late = make_card(12, "notice_late.png")

# ---------------------------------------------------------------- 拼图
PAD = 26
row1_w = 4 * P.PET_SIZE + 3 * PAD
row2_w = panel_shot.width() + PAD + card_canvas.width()
W = max(row1_w, row2_w) + PAD * 2
H = (52 + P.PET_SIZE + 44
     + max(panel_shot.height(), card_canvas.height())
     + card_late.height() + 66 + PAD)

board = QPixmap(W, H)
board.fill(BG)
p = QPainter(board)
p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

p.setPen(QColor(P.C_TEXT))
f = QFont(P.FONT, 13)
f.setBold(True)
p.setFont(f)
p.drawText(PAD, 30, "番茄桌宠 · 四种状态")

x = PAD
y = 48
for label, pm in pet_shots:
    p.drawPixmap(x, y, pm)
    p.setPen(QColor(P.C_SUBTLE))
    p.setFont(QFont(P.FONT, 9))
    p.drawText(x, y + P.PET_SIZE + 18, label)
    x += P.PET_SIZE + PAD

y2 = y + P.PET_SIZE + 40
p.setPen(QColor(P.C_TEXT))
f2 = QFont(P.FONT, 12)
f2.setBold(True)
p.setFont(f2)
p.drawText(PAD, y2 + 2, "展开面板 / 到点提醒")
p.drawPixmap(PAD, y2 + 10, panel_shot)
p.drawPixmap(PAD + panel_shot.width() + PAD, y2 + 10, card_canvas)

y3 = y2 + 10 + max(panel_shot.height(), card_canvas.height()) + 36
p.setPen(QColor(P.C_TEXT))
p.setFont(f2)
p.drawText(PAD, y3, "人走开 12 分钟后再看这张卡片（时间行变橙）")
p.drawPixmap(PAD, y3 + 10, card_late)
p.end()

board.save(str(OUT / "board.png"))
print("已生成:", OUT / "board.png")
print("尺寸:", board.width(), "x", board.height())
