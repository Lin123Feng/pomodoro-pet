"""提醒卡片时间行自测：文案边界 + 卡片真的会刷新"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import pomodoro_pet as P
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
ok, fail = 0, []


def check(name, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail.append(name)
        print(f"  [FAIL] {name} {extra}")


FIRED = datetime(2026, 10, 30, 15, 0, 0)


def at(seconds):
    return P.fmt_notice_meta(FIRED, FIRED + timedelta(seconds=seconds))


print("\n1. fmt_notice_meta 文案边界")
cases = [
    (0,    "现在 15:00 · 刚刚提醒", False),
    (59,   "现在 15:00 · 刚刚提醒", False),
    (60,   "现在 15:01 · 已过 1 分钟", False),
    (299,  "现在 15:04 · 已过 4 分钟", False),
    (300,  "现在 15:05 · 已过 5 分钟", True),
    (720,  "现在 15:12 · 已过 12 分钟", True),
    (3900, "现在 16:05 · 已过 1 小时 5 分钟", True),
    (7200, "现在 17:00 · 已过 2 小时", True),
]
for sec, want_text, want_late in cases:
    text, late = at(sec)
    check(f"{sec}s → 「{want_text}」", text == want_text, f"实际「{text}」")
    check(f"{sec}s → late={want_late}", late == want_late, f"实际 {late}")

print("\n2. 卡片：提醒时刻 + 实时行真的显示出来")
card = P.NoticeCard()
card.move(-4000, -4000)
card.show_card("work", "专注结束", "这一轮记下了。休息 5 分钟？",
               "休息 5 分钟", "跳过休息", lambda: None, lambda: None)
for _ in range(3):
    app.processEvents()
check("提醒时刻是 HH:MM", len(card.fired_label.text()) == 5 and ":" in card.fired_label.text(),
      card.fired_label.text())
check("刚开始显示「刚刚提醒」", "刚刚提醒" in card.meta.text(), card.meta.text())
check("计时器在跑（10 秒刷新）", card._clock.isActive())

print("\n3. 把提醒时间改成 12 分钟前 → 文案自动变成「已过 12 分钟」且变警示色")
card._fired_at = datetime.now() - timedelta(minutes=12)
card._refresh_meta()
check("文案含「已过 12 分钟」", "已过 12 分钟" in card.meta.text(), card.meta.text())
check("错过 ≥5 分钟后变橙 #e8a13c", "#e8a13c" in card.meta.styleSheet(), card.meta.styleSheet())

print("\n4. 收起卡片后停止刷新（不白耗 CPU）")
card.hide()
for _ in range(3):
    app.processEvents()
check("计时器已停", not card._clock.isActive())

print("\n5. 卡片高度够放三行，且按钮没被挤掉")
card.show_card("break", "休息结束", "准备好了就继续，节奏你说了算。",
               "开始下一轮", "稍后", lambda: None, lambda: None)
for _ in range(3):
    app.processEvents()
check("卡片高度 196", card.height() == 196, card.height())
check("两个按钮都在", card.btn1.text() == "开始下一轮" and card.btn2.text() == "稍后")

print(f"\n结果：{ok} 项通过，{len(fail)} 项失败")
sys.exit(1 if fail else 0)
