"""交互自测：双击展开面板、拖动保存位置、按钮回调"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pomodoro_pet as P
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
TMP = HERE / "_tmp_inter.json"
if TMP.exists():
    TMP.unlink()

store = P.Store(TMP)
ctrl = P.Controller(store)
pet = P.PetWindow(ctrl, store)
panel = P.Panel(ctrl, store, pet)
pet.double_clicked.connect(panel.toggle_visible)
pet.move(-4000, -4000)
pet.show()
for _ in range(3):
    app.processEvents()

ok, fail = 0, []


def check(name, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail.append(name)
        print(f"  [FAIL] {name} {extra}")


print("\n1. 双击桌宠 → 面板展开")
check("面板初始隐藏", not panel.isVisible())
QTest.mouseDClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(70, 70))
for _ in range(3):
    app.processEvents()
check("双击后面板可见", panel.isVisible(), panel.isVisible())
QTest.mouseDClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(70, 70))
for _ in range(3):
    app.processEvents()
check("再双击一次收起来", not panel.isVisible(), panel.isVisible())

print("\n2. 拖动桌宠 → 位置变化并写入 state")
before = pet.pos()
QTest.mousePress(pet, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
QTest.mouseMove(pet, QPoint(260, 220))
QTest.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=QPoint(260, 220))
for _ in range(3):
    app.processEvents()
after = pet.pos()
check("位置已改变", after != before, f"{before} -> {after}")
saved = store.saved_pos("pet_pos")
check("位置已落盘", saved is not None and saved == after, saved)

print("\n3. 面板主按钮：待开始 → 运行 → 暂停")
ctrl.reset()
check("初始 idle", ctrl.state == "idle")
panel._on_main()
check("点一下变 running", ctrl.state == "running", ctrl.state)
panel._on_main()
check("再点一下变 paused", ctrl.state == "paused", ctrl.state)
panel._on_main()
check("再点继续 running", ctrl.state == "running", ctrl.state)

print("\n4. 到点后主按钮变成「开始休息」并正确切换阶段")
ctrl.timer.stop()
ctrl.state = "finished"
ctrl.remaining = 0.0
panel.refresh()
check("按钮文案=开始休息", panel.btn_main.text() == "开始休息", panel.btn_main.text())
panel._on_main()
check("阶段切到 break", ctrl.phase == "break", ctrl.phase)
check("并已开始计时", ctrl.state == "running", ctrl.state)

print("\n5. 重置按钮")
panel.btn_reset.click()
check("重置回 idle", ctrl.state == "idle", ctrl.state)

print(f"\n结果：{ok} 项通过，{len(fail)} 项失败")
sys.exit(1 if fail else 0)
