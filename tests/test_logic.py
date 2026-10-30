"""番茄桌宠 · 逻辑自测（无头，不需要看界面）

验证：计时状态机、结束后不自动开始、统计落库、设置持久化、跨天滚动
运行：D:\\Users\\miniconda3\\envs\\myenv\\python pomodoro_test\\test_logic.py
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))

import pomodoro_pet as P
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)

TMP = HERE / "_tmp_logic.json"
if TMP.exists():
    TMP.unlink()

ok = 0
fail = []


def check(name, cond, extra=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {name}")
    else:
        fail.append(name)
        print(f"  [FAIL] {name} {extra}")


print("\n1. 初始状态")
store = P.Store(TMP)
ctrl = P.Controller(store)
check("phase=work", ctrl.phase == "work")
check("state=idle", ctrl.state == "idle")
check("剩余=25:00", ctrl.time_text() == "25:00", ctrl.time_text())

print("\n2. 开始 → 运行中")
ctrl.start()
check("state=running", ctrl.state == "running")
check("timer 已启动", ctrl.timer.isActive())

print("\n3. 暂停 → 保留剩余时间")
ctrl.pause()
frozen = ctrl.remaining
check("state=paused", ctrl.state == "paused")
check("timer 已停止", not ctrl.timer.isActive())
check("剩余时间保留", 0 < frozen <= 25 * 60, frozen)

print("\n4. 时间到 → 结束且不自动开始下一轮")
ctrl.start()
ctrl.deadline = time.monotonic() - 1        # 伪造已过期
fired = []
ctrl.phase_finished.connect(lambda ph: fired.append(ph))
ctrl._tick()
check("state=finished", ctrl.state == "finished", ctrl.state)
check("timer 已停止（不自动跑下一轮）", not ctrl.timer.isActive())
check("发出 phase_finished('work')", fired == ["work"], fired)
check("今日番茄 +1", store.today_count == 1, store.today_count)
check("专注时长 +1500s", store.today_focus == 1500, store.today_focus)

print("\n5. 手动进入休息 → 停在待开始")
ctrl.switch_phase()
check("phase=break", ctrl.phase == "break")
check("state=idle（等人点）", ctrl.state == "idle", ctrl.state)
check("剩余=05:00", ctrl.time_text() == "05:00", ctrl.time_text())

print("\n6. 休息结束 → 不自动开始工作，也不加统计")
ctrl.start()
ctrl.deadline = time.monotonic() - 1
ctrl._tick()
check("state=finished", ctrl.state == "finished")
check("今日番茄仍为 1（休息不计）", store.today_count == 1, store.today_count)
check("专注时长仍为 1500s", store.today_focus == 1500, store.today_focus)

print("\n7. 重置本轮")
ctrl.reset()
check("state=idle", ctrl.state == "idle")
check("剩余回到本轮全长 05:00", ctrl.time_text() == "05:00", ctrl.time_text())

print("\n8. 跳过休息 → 回到专注待开始")
ctrl.skip_break()
check("phase=work", ctrl.phase == "work")
check("剩余=25:00", ctrl.time_text() == "25:00", ctrl.time_text())

print("\n9. 改时长 → 立刻重置本轮并落盘")
ctrl.set_durations(45, 10)
check("本轮剩余=45:00", ctrl.time_text() == "45:00", ctrl.time_text())
store2 = P.Store(TMP)
check("重新读取仍是 45 分钟", store2.work_min == 45, store2.work_min)
check("重新读取仍是 10 分钟休息", store2.break_min == 10, store2.break_min)

print("\n10. 跨天滚动 → 昨天的成绩归档")
store3 = P.Store(TMP)
store3.data["today"] = {"date": "2020-01-01", "count": 7, "focus_sec": 7 * 1500}
store3._roll_day()
check("today 已重置", store3.data["today"]["count"] == 0, store3.data["today"])
check("2020-01-01 归档进 history",
      store3.data["history"].get("2020-01-01", {}).get("count") == 7,
      store3.data["history"])

print("\n11. 位置记忆")
store3.save_pos("pet_pos", P.QPoint(123, 456))
store4 = P.Store(TMP)
pos = store4.saved_pos("pet_pos")
check("位置读回一致", pos is not None and pos.x() == 123 and pos.y() == 456, pos)

print(f"\n结果：{ok} 项通过，{len(fail)} 项失败")
if fail:
    print("失败项：", "、".join(fail))
sys.exit(1 if fail else 0)
