"""整体装配自测：App 里桌宠↔面板↔提醒卡片是否真的串起来了"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pomodoro_pet as P
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

TMP = HERE / "_tmp_app.json"
if TMP.exists():
    TMP.unlink()
P.DATA_FILE = TMP          # 用临时存档，别动用户的真实统计

ok, fail = 0, []


def check(name, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail.append(name)
        print(f"  [FAIL] {name} {extra}")


win = P.App(demo=False)
win.pet.move(-4000, -4000)
for _ in range(4):
    app.processEvents()

print("\n1. 启动后只有桌宠露面")
check("桌宠可见", win.pet.isVisible())
check("面板初始隐藏", not win.panel.isVisible())
check("托盘图标已创建", win.tray is not None and win.tray.isVisible())

print("\n2. 双击桌宠 → 面板展开（走 App 内部接线）")
QTest.mouseDClick(win.pet, Qt.MouseButton.LeftButton, pos=QPoint(70, 70))
for _ in range(4):
    app.processEvents()
check("双击后面板出现", win.panel.isVisible(), win.panel.isVisible())

print("\n3. 到点 → 桌宠跳动 + 提醒卡片弹出 + 统计入账")
win.panel.hide()
win.ctrl.start()
win.ctrl.deadline = time.monotonic() - 1
win.ctrl._tick()
for _ in range(4):
    app.processEvents()
check("状态变 finished", win.ctrl.state == "finished", win.ctrl.state)
check("提醒卡片已弹出", win.notice.isVisible(), win.notice.isVisible())
check("卡片标题=专注结束", win.notice.title.text() == "专注结束", win.notice.title.text())
check("卡片主按钮含休息时长", "休息" in win.notice.btn1.text(), win.notice.btn1.text())
check("今日番茄记为 1", win.store.today_count == 1, win.store.today_count)
check("桌宠进入跳动动画", win.pet._jump > 0 or win.pet.anim.isActive(),
      f"jump={win.pet._jump}")

print("\n4. 点卡片「休息」→ 进入休息并开始计时")
win.notice._on1()
for _ in range(4):
    app.processEvents()
check("卡片已关闭", not win.notice.isVisible())
check("阶段切到 break", win.ctrl.phase == "break", win.ctrl.phase)
check("休息计时运行中", win.ctrl.state == "running", win.ctrl.state)

print("\n5. 休息到点 → 卡片提示手动开始下一轮")
win.ctrl.deadline = time.monotonic() - 1
win.ctrl._tick()
for _ in range(4):
    app.processEvents()
check("卡片标题=休息结束", win.notice.title.text() == "休息结束", win.notice.title.text())
check("主按钮=开始下一轮", win.notice.btn1.text() == "开始下一轮", win.notice.btn1.text())
check("休息结束不加番茄数", win.store.today_count == 1, win.store.today_count)

print("\n6. 点「开始下一轮」→ 回到专注且手动启动")
win.notice._on1()
for _ in range(4):
    app.processEvents()
check("阶段回到 work", win.ctrl.phase == "work", win.ctrl.phase)
check("计时运行中", win.ctrl.state == "running", win.ctrl.state)

win.quit()
print(f"\n结果：{ok} 项通过，{len(fail)} 项失败")
sys.exit(1 if fail else 0)
