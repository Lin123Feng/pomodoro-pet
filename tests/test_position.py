"""位置越界自测：拖到屏幕外必须能回来（否则番茄「消失」）"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pomodoro_pet as P
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

TMP = HERE / "_tmp_pos.json"
if TMP.exists():
    TMP.unlink()
P.DATA_FILE = TMP

ok, fail = 0, []


def check(name, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail.append(name)
        print(f"  [FAIL] {name} {extra}")


g = app.primaryScreen().availableGeometry()
print(f"主屏可用区: {g.width()}x{g.height()}  (x {g.left()}..{g.right()}, y {g.top()}..{g.bottom()})")
print(f"系统里一共 {len(app.screens())} 块屏幕：")
for i, scr in enumerate(app.screens()):
    ag = scr.availableGeometry()
    print(f"  屏幕{i}: {scr.name()} 可用区 x {ag.left()}..{ag.right()}, y {ag.top()}..{ag.bottom()}"
          f"  物理 {scr.size().width()}x{scr.size().height()}  DPR={scr.devicePixelRatio()}")

print("\n1. visible_on_some_screen 判定")
check("屏幕内的位置 → True", P.visible_on_some_screen(QPoint(100, 100), 140, 140))
check("右侧远处 (x=9999) → False", not P.visible_on_some_screen(QPoint(9999, 100), 140, 140))
check("上方远处 (y=-800) → False", not P.visible_on_some_screen(QPoint(100, -800), 140, 140))

print("\n2. 存档里是真正的越界坐标 → 启动时回到主屏默认位置")
store = P.Store(TMP)
store.save_pos("pet_pos", QPoint(9999, 5000))        # 哪块屏幕都不在
win = P.App(demo=False)
pos = win.pet.pos()
check("桌宠回到可见区", P.visible_on_some_screen(pos, P.PET_SIZE, P.PET_SIZE), pos)
check("落在主屏右下角一带",
      g.right() - 400 < pos.x() <= g.right() and pos.y() > g.top() + 200, pos)

print("\n2b. 位置在第二块屏幕上 → 保留（用户自己拖过去的，别抢回来）")
win.quit()
store2 = P.Store(TMP)
sec = app.screens()[1].availableGeometry() if len(app.screens()) > 1 else None
if sec is not None:
    target = QPoint(sec.right() - 300, sec.top() + 200)
    store2.save_pos("pet_pos", target)
    win2 = P.App(demo=False)
    check("第二屏位置被保留", win2.pet.pos() == target, f"{win2.pet.pos()} vs {target}")
    win2.quit()
else:
    print("  (只有一块屏幕，跳过)")

print("\n3. 拖动时的夹取：往屏幕外拽会被拉回边界")
clamped = win.pet._limit_pos(QPoint(5000, -500))
check("x 被夹到屏幕内", g.left() <= clamped.x() <= g.right() - P.PET_SIZE + 1, clamped)
check("y 被夹到屏幕内", g.top() <= clamped.y() <= g.bottom() - P.PET_SIZE + 1, clamped)
check("夹取后仍然可见", P.visible_on_some_screen(clamped, P.PET_SIZE, P.PET_SIZE), clamped)

print("\n4. 面板位置也做同样校验")
win.panel.popup_near_pet()
pp = win.panel.pos()
check("面板在可见区", P.visible_on_some_screen(pp, P.PANEL_W, P.PANEL_H), pp)

win.quit()
print(f"\n结果：{ok} 项通过，{len(fail)} 项失败")
sys.exit(1 if fail else 0)
