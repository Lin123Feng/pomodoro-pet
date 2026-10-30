"""番茄桌宠 (Pomodoro Pet)

悬浮在桌面上的小番茄，专注时陪你倒计时，到点会跳起来提醒你。
配色遵循 Callie 规范：晨曦青碧 #4f9ec9 主色，番茄红 #e05a4a 警示，成功绿 #3aa675。

运行：
    D:\\Users\\miniconda3\\envs\\myenv\\pythonw.exe pomodoro_pet.py
自测（专注/休息各 4 秒，方便看提醒）：
    D:\\Users\\miniconda3\\envs\\myenv\\python pomodoro_pet.py --demo

依赖：PyQt6（myenv 已装）。不再使用 plyer —— 旧版用它发托盘气球，
而 Win10/11 已废弃那套 API，所以"时间到了没提示"。现在改走自家置顶卡片 + 系统提示音。
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import threading
import time
import traceback
from datetime import date, datetime
from pathlib import Path

import winsound
from PyQt6.QtCore import (
    QEasingCurve, QLockFile, QObject, QPoint, QPointF, QPropertyAnimation,
    QRect, QRectF, QSize, QTimer, Qt, pyqtSignal,
)
from PyQt6.QtGui import (
    QAction, QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QMenu, QMessageBox, QPushButton, QSpinBox, QSystemTrayIcon, QVBoxLayout,
    QWidget,
)

# 打包成 exe 后 __file__ 指向临时解包目录，重启就没了 —— 存档必须另找地方
if getattr(sys, "frozen", False):
    APP_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "PomodoroPet"
else:
    APP_DIR = Path(__file__).resolve().parent
APP_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = APP_DIR / "pomodoro_state.json"
ERROR_LOG = APP_DIR / "pomodoro_error.log"

# ---------------------------------------------------------------- 配色 / 尺寸
C_PRIMARY = "#4f9ec9"      # 晨曦青碧（主行动色）
C_PRIMARY_D = "#3f8bb4"
C_PRIMARY_L = "#eaf4f9"
C_DANGER = "#e05a4a"       # 番茄红 / 警示
C_SUCCESS = "#3aa675"      # 成功 / 休息
C_TEXT = "#2b3a42"
C_SUBTLE = "#7d8b93"
C_LINE = "#e3e9ec"
C_TRACK = "#edf1f3"

FONT = "Microsoft YaHei UI"

PET_SIZE = 140
PANEL_W = 400
PANEL_H = 588


# ---------------------------------------------------------------- 小工具
def fmt_clock(seconds: float) -> str:
    """剩余秒数 → mm:ss（向上取整，避免最后一秒提前显示 00:00）"""
    total = int(math.ceil(max(0.0, seconds) - 1e-6))
    return f"{total // 60:02d}:{total % 60:02d}"


def fmt_span(seconds: int) -> str:
    """专注时长 → 1h15m / 45m"""
    m = int(round(seconds / 60))
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m" if m else f"{h}h"
    return f"{m}m"


def fmt_notice_meta(fired: datetime, now: datetime) -> tuple[str, bool]:
    """提醒卡片上那行实时信息 → (文案, 是否已经明显错过)

    人可能开着卡片就去忙别的了，回来要能一眼看出「我错过了多久」。
    """
    diff = int((now - fired).total_seconds())
    hhmm = now.strftime("%H:%M")
    if diff < 60:
        return f"现在 {hhmm} · 刚刚提醒", False
    mins = diff // 60
    if mins < 60:
        return f"现在 {hhmm} · 已过 {mins} 分钟", mins >= 5
    hours, rest = divmod(mins, 60)
    tail = f"{hours} 小时 {rest} 分钟" if rest else f"{hours} 小时"
    return f"现在 {hhmm} · 已过 {tail}", True


def visible_on_some_screen(pos: QPoint, w: int, h: int) -> bool:
    """窗口是否至少和一个屏幕的可见区域有交集（拖到屏幕外就再也找不回来了）"""
    rect = QRect(pos, QSize(w, h))
    return any(scr.availableGeometry().intersects(rect) for scr in QApplication.screens())


def play_alert(reason: str) -> None:
    """系统提示音。工作结束三声下行，休息结束两声上行。"""
    def _run() -> None:
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            time.sleep(0.30)
            if reason == "work":
                for freq in (988, 784, 659):
                    winsound.Beep(freq, 170)
            else:
                for freq in (659, 988):
                    winsound.Beep(freq, 200)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def make_tomato_icon(size: int = 64, body: str = C_DANGER) -> QIcon:
    """用矢量画一个番茄当托盘/标题图标"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = size * 0.34
    cx, cy = size / 2, size * 0.55
    grad = QRadialGradient(cx - r * 0.35, cy - r * 0.45, r * 1.9)
    grad.setColorAt(0.0, QColor(body).lighter(126))
    grad.setColorAt(1.0, QColor(body))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, cy), r, r * 0.97)
    leaf = QColor(C_SUCCESS)
    p.setBrush(QBrush(leaf))
    for i in range(5):
        ang = math.pi * (-0.15 - 0.175 * i)
        lx = cx + math.cos(ang) * r * 0.55
        ly = cy - r * 0.78 + math.sin(ang) * r * 0.22
        p.drawEllipse(QPointF(lx, ly), r * 0.26, r * 0.13)
    p.setBrush(QBrush(leaf.darker(112)))
    p.drawEllipse(QPointF(cx, cy - r * 0.92), r * 0.10, r * 0.16)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------- 数据
class Store:
    """所有设置 + 今日统计，落在 pomodoro_state.json"""

    DEFAULT = {
        "work_min": 25,
        "break_min": 5,
        "pet_pos": None,
        "panel_pos": None,
        "today": {"date": "", "count": 0, "focus_sec": 0},
        "history": {},
    }

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(json.dumps(self.DEFAULT))
        self.load()

    # -- 读写
    def load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    if k in ("today", "history") and isinstance(v, dict):
                        self.data[k] = v
                    elif k in self.DEFAULT:
                        self.data[k] = v
        except Exception:
            traceback.print_exc()
        self._roll_day()

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            traceback.print_exc()

    # -- 跨天滚动：昨天的成绩归档进 history
    def _roll_day(self) -> None:
        today = date.today().isoformat()
        t = self.data.get("today") or {}
        if t.get("date") != today:
            if t.get("date") and (t.get("count") or t.get("focus_sec")):
                self.data.setdefault("history", {})[t["date"]] = {
                    "count": t.get("count", 0),
                    "focus_sec": t.get("focus_sec", 0),
                }
                hist = self.data["history"]
                for old in sorted(hist)[:-60]:
                    hist.pop(old, None)
            self.data["today"] = {"date": today, "count": 0, "focus_sec": 0}
            self.save()

    # -- 设置
    @property
    def work_min(self) -> int:
        return int(self.data.get("work_min") or 25)

    @work_min.setter
    def work_min(self, v: int) -> None:
        self.data["work_min"] = max(1, min(180, int(v)))
        self.save()

    @property
    def break_min(self) -> int:
        return int(self.data.get("break_min") or 5)

    @break_min.setter
    def break_min(self, v: int) -> None:
        self.data["break_min"] = max(1, min(60, int(v)))
        self.save()

    # -- 位置
    def saved_pos(self, key: str):
        v = self.data.get(key)
        if isinstance(v, list) and len(v) == 2:
            return QPoint(int(v[0]), int(v[1]))
        return None

    def save_pos(self, key: str, pt: QPoint) -> None:
        self.data[key] = [pt.x(), pt.y()]
        self.save()

    # -- 统计
    def add_pomodoro(self, seconds: int) -> None:
        self._roll_day()
        t = self.data["today"]
        t["count"] = int(t.get("count", 0)) + 1
        t["focus_sec"] = int(t.get("focus_sec", 0)) + int(seconds)
        self.save()

    @property
    def today_count(self) -> int:
        self._roll_day()
        return int(self.data["today"].get("count", 0))

    @property
    def today_focus(self) -> int:
        self._roll_day()
        return int(self.data["today"].get("focus_sec", 0))


# ---------------------------------------------------------------- 计时状态机
class Controller(QObject):
    """phase = work / break ；state = idle / running / paused / finished"""

    state_changed = pyqtSignal()
    phase_finished = pyqtSignal(str)      # "work" | "break"

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self.phase = "work"
        self.state = "idle"
        self.demo = None                  # (work_sec, break_sec) 仅自测用
        self.remaining = float(self._total())
        self.deadline = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)

    # -- 派生值
    def _total(self) -> float:
        if self.demo:
            return float(self.demo[0] if self.phase == "work" else self.demo[1])
        return float((self.store.work_min if self.phase == "work" else self.store.break_min) * 60)

    @property
    def total(self) -> float:
        return self._total()

    def progress(self) -> float:
        """剩余比例 0..1，环形进度用"""
        t = self.total
        return max(0.0, min(1.0, self.remaining / t)) if t > 0 else 0.0

    def time_text(self) -> str:
        return fmt_clock(self.remaining)

    def status_text(self) -> str:
        if self.state == "paused":
            return "已暂停"
        if self.state == "finished":
            return "等待确认"
        if self.phase == "work":
            return "专注中" if self.state == "running" else "准备开始"
        return "休息中" if self.state == "running" else "休息待开始"

    def is_running(self) -> bool:
        return self.state == "running"

    # -- 操作
    def start(self) -> None:
        if self.state == "running":
            return
        if self.remaining <= 0:
            self.remaining = self.total
        self.deadline = time.monotonic() + self.remaining
        self.state = "running"
        self.timer.start()
        self.state_changed.emit()

    def pause(self) -> None:
        if self.state != "running":
            return
        self.remaining = max(0.0, self.deadline - time.monotonic())
        self.timer.stop()
        self.state = "paused"
        self.state_changed.emit()

    def toggle(self) -> None:
        self.pause() if self.state == "running" else self.start()

    def reset(self) -> None:
        """重置当前这一轮，不计入统计"""
        self.timer.stop()
        self.remaining = self.total
        self.state = "idle"
        self.state_changed.emit()

    def switch_phase(self) -> None:
        """切到另一阶段，停在那儿等用户点开始（不自动开始）"""
        self.timer.stop()
        self.phase = "break" if self.phase == "work" else "work"
        self.remaining = self.total
        self.state = "idle"
        self.state_changed.emit()

    def skip_break(self) -> None:
        """跳过休息，直接回到待开始的专注轮"""
        self.timer.stop()
        self.phase = "work"
        self.remaining = self.total
        self.state = "idle"
        self.state_changed.emit()

    def set_durations(self, work_min: int, break_min: int) -> None:
        self.store.work_min = work_min
        self.store.break_min = break_min
        self.timer.stop()
        self.phase = "work"
        self.remaining = self.total
        self.state = "idle"
        self.state_changed.emit()

    # -- 心跳
    def _tick(self) -> None:
        self.remaining = self.deadline - time.monotonic()
        if self.remaining <= 0:
            self.remaining = 0.0
            self.timer.stop()
            self.state = "finished"
            if self.phase == "work":
                self.store.add_pomodoro(int(self.total))
            self.state_changed.emit()
            self.phase_finished.emit(self.phase)
            return
        self.state_changed.emit()


# ---------------------------------------------------------------- 桌宠本体
class PetWindow(QWidget):
    double_clicked = pyqtSignal()
    menu_requested = pyqtSignal(QPoint)

    def __init__(self, ctrl: Controller, store: Store):
        super().__init__()
        self.ctrl = ctrl
        self.store = store
        self.setFixedSize(PET_SIZE, PET_SIZE)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("番茄桌宠 · 双击展开面板")

        self._drag_offset = None
        self._dragged = False
        self._jump = 0.0            # 到点跳动进度 1 → 0

        self.anim = QTimer(self)
        self.anim.setInterval(60)
        self.anim.timeout.connect(self._on_anim)

        self._breathe = QTimer(self)
        self._breathe.setInterval(50)
        self._breathe.timeout.connect(self.update)
        self._breathe.start()

        ctrl.state_changed.connect(self.update)

    # -- 到点庆祝
    def celebrate(self) -> None:
        self._jump = 1.0
        self.anim.start()

    def _on_anim(self) -> None:
        self._jump -= 0.028
        if self._jump <= 0:
            self._jump = 0.0
            self.anim.stop()
        self.update()

    # -- 拖动 / 交互
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragged = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and e.buttons() & Qt.MouseButton.LeftButton:
            newpos = e.globalPosition().toPoint() - self._drag_offset
            if (newpos - self.pos()).manhattanLength() > 3:
                self._dragged = True
            self.move(self._limit_pos(newpos))

    def _limit_pos(self, pos: QPoint) -> QPoint:
        """把番茄夹在屏幕可见区内：拖到边缘外不会消失"""
        center = pos + QPoint(PET_SIZE // 2, PET_SIZE // 2)
        scr = QApplication.screenAt(center) or QApplication.primaryScreen()
        g = scr.availableGeometry()
        x = min(max(pos.x(), g.left()), g.right() - PET_SIZE + 1)
        y = min(max(pos.y(), g.top()), g.bottom() - PET_SIZE + 1)
        return QPoint(x, y)

    def mouseReleaseEvent(self, e):
        self._drag_offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if self._dragged:
            self.store.save_pos("pet_pos", self.pos())

    def mouseDoubleClickEvent(self, e):
        if not self._dragged:
            self.double_clicked.emit()

    def contextMenuEvent(self, e):
        self.menu_requested.emit(e.globalPos())

    # -- 绘制
    def paintEvent(self, _e):
        ctrl = self.ctrl
        now = time.monotonic()

        # 整体缩放：到点跳动优先，平时轻微呼吸
        if self._jump > 0:
            scale = 1.0 + 0.24 * abs(math.sin((1.0 - self._jump) * math.pi * 3)) * self._jump
        else:
            scale = 1.0 + 0.012 * math.sin(now * 2.1) if ctrl.is_running() else 1.0

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(scale, scale)
        p.translate(-self.width() / 2, -self.height() / 2)

        alpha = 0.55 if ctrl.state == "paused" else 1.0
        p.setOpacity(alpha)

        is_break = ctrl.phase == "break"
        if self._jump > 0 or ctrl.state == "finished":
            body = QColor(C_DANGER)
        elif is_break:
            body = QColor("#d9786a")          # 休息也是番茄色，只是淡一点
        elif ctrl.state == "paused":
            body = QColor("#cf9a90")
        else:
            body = QColor("#e0674f")

        # --- 外圈：底环 + 剩余进度
        ring = QRectF(7, 7, self.width() - 14, self.height() - 14)
        pen = QPen(QColor(0, 0, 0, 18), 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(ring, 0, 360 * 16)

        if ctrl.remaining > 0 or ctrl.state in ("running", "finished"):
            if ctrl.state == "paused":
                ring_color = QColor("#b9c6cd")
            elif ctrl.state == "finished":
                ring_color = QColor(C_DANGER)
            elif is_break:
                ring_color = QColor(C_SUCCESS)
            else:
                ring_color = QColor(C_PRIMARY)
            pen = QPen(ring_color, 6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            span = int(360 * 16 * ctrl.progress())
            if span <= 0 and ctrl.state == "finished":
                span = 360 * 16
            if span >= 360 * 16:
                # 正好一整圈时 drawArc 首尾重合会画不出来，改用 drawEllipse 描边
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(ring)
            elif span > 0:
                p.drawArc(ring, 90 * 16, -span)

        # --- 番茄身体（脸在上半部，时间挪到球下方，避免叠字）
        cx, cy = self.width() / 2, self.height() / 2 - 6
        r = 32.0
        grad = QRadialGradient(cx - r * 0.38, cy - r * 0.45, r * 2.0)
        grad.setColorAt(0.0, body.lighter(128))
        grad.setColorAt(1.0, body)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), r, r * 0.97)

        # 高光
        p.setBrush(QBrush(QColor(255, 255, 255, 72)))
        p.drawEllipse(QPointF(cx - r * 0.34, cy - r * 0.42), r * 0.20, r * 0.14)

        # --- 叶子 + 蒂
        leaf = QColor(C_SUCCESS)
        p.setBrush(QBrush(leaf))
        for i in range(5):
            ang = math.pi * (-0.10 - 0.175 * i)
            lx = cx + math.cos(ang) * r * 0.62
            ly = cy - r * 0.72 + math.sin(ang) * r * 0.26
            p.save()
            p.translate(lx, ly)
            p.rotate(math.degrees(ang) + 90)
            p.drawEllipse(QPointF(0, 0), r * 0.30, r * 0.13)
            p.restore()
        p.setBrush(QBrush(leaf.darker(115)))
        p.drawEllipse(QPointF(cx, cy - r * 0.90), r * 0.09, r * 0.17)

        # --- 表情（整体上移到番茄上半部）
        dark = QColor("#3d2b28")
        eye_dx = r * 0.32
        eye_y = cy - r * 0.22
        if ctrl.state == "paused":
            pen = QPen(dark, max(2.0, r * 0.075))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(cx - eye_dx - r * 0.11, eye_y),
                       QPointF(cx - eye_dx + r * 0.11, eye_y))
            p.drawLine(QPointF(cx + eye_dx - r * 0.11, eye_y),
                       QPointF(cx + eye_dx + r * 0.11, eye_y))
        elif is_break:
            pen = QPen(dark, max(2.0, r * 0.07))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx - eye_dx - r * 0.12, eye_y - r * 0.07, r * 0.24, r * 0.16),
                      0, 180 * 16)
            p.drawArc(QRectF(cx + eye_dx - r * 0.12, eye_y - r * 0.07, r * 0.24, r * 0.16),
                      0, 180 * 16)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(dark))
            p.drawEllipse(QPointF(cx - eye_dx, eye_y), r * 0.085, r * 0.105)
            p.drawEllipse(QPointF(cx + eye_dx, eye_y), r * 0.085, r * 0.105)
            p.setBrush(QBrush(QColor(255, 255, 255, 210)))
            p.drawEllipse(QPointF(cx - eye_dx + r * 0.03, eye_y - r * 0.035),
                          r * 0.028, r * 0.030)
            p.drawEllipse(QPointF(cx + eye_dx + r * 0.03, eye_y - r * 0.035),
                          r * 0.028, r * 0.030)

        # 嘴
        pen = QPen(dark, max(1.8, r * 0.06))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - r * 0.16, cy + r * 0.06, r * 0.32, r * 0.22), 200 * 16, 140 * 16)

        # --- 时间：放在番茄球下方独立一行，不和脸打架
        p.setPen(QPen(QColor(C_TEXT)))
        f = QFont(FONT, 12)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, cy + r + 4, self.width(), 22),
                   Qt.AlignmentFlag.AlignCenter, ctrl.time_text())
        p.end()


# ---------------------------------------------------------------- 环形进度（面板用）
class RingWidget(QWidget):
    def __init__(self, ctrl: Controller, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.setFixedSize(184, 184)
        ctrl.state_changed.connect(self.update)

    def paintEvent(self, _e):
        ctrl = self.ctrl
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        ring = QRectF(12, 12, self.width() - 24, self.height() - 24)

        p.setPen(QPen(QColor(C_TRACK), 9))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(ring)

        color = QColor(C_SUCCESS if ctrl.phase == "break" else C_PRIMARY)
        if ctrl.state == "finished":
            color = QColor(C_DANGER)
        pen = QPen(color, 9)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        # 到点（remaining=0）也画满一圈，别让环突然消失
        span = int(360 * 16 * ctrl.progress())
        if span <= 0 and ctrl.state == "finished":
            span = 360 * 16
        # 正好 360° 时 drawArc 会因首尾重合画不出来，改用 drawEllipse 描边
        if span >= 360 * 16:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(ring)
        elif span > 0:
            p.drawArc(ring, 90 * 16, -span)

        # 时间垂直居中；状态文字交给顶部徽章，这里不重复写一遍
        p.setPen(QPen(QColor(C_TEXT)))
        f = QFont(FONT, 30)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, self.height() / 2 - 24, self.width(), 48),
                   Qt.AlignmentFlag.AlignCenter, ctrl.time_text())
        p.end()


class TodayDots(QWidget):
    """今日番茄点阵：完成的实心，未完成的空圈"""

    def __init__(self, store: Store, ctrl: Controller, target: int = 5, parent=None):
        super().__init__(parent)
        self.store = store
        self.target = target
        self.setFixedHeight(24)
        ctrl.state_changed.connect(self.update)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        done = self.store.today_count
        shown = max(self.target, min(done, 10))
        r = 5.0
        gap = 16.0
        total_w = shown * gap
        x0 = (self.width() - total_w) / 2 + gap / 2
        cy = self.height() / 2
        for i in range(shown):
            cx = x0 + i * gap
            if i < done:
                p.setBrush(QBrush(QColor(C_DANGER)))
                p.setPen(Qt.PenStyle.NoPen)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor("#dfe6ea"), 1.4))
            p.drawEllipse(QPointF(cx, cy), r, r)
        p.end()


# ---------------------------------------------------------------- 拖动条
class DragBar(QFrame):
    def __init__(self, target: QWidget, parent=None):
        super().__init__(parent)
        self.target = target
        self._off = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._off = e.globalPosition().toPoint() - self.target.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._off is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.target.move(e.globalPosition().toPoint() - self._off)

    def mouseReleaseEvent(self, _e):
        self._off = None


# ---------------------------------------------------------------- 到点提醒卡片
class NoticeCard(QWidget):
    """右下角置顶卡片：不点不消失，按钮推进流程"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(372, 196)
        self._cb1 = None
        self._cb2 = None
        self._anim = None
        self._fired_at = None

        # 每 10 秒刷新「现在几点 / 已过多久」，人回来能看到错过了多长时间
        self._clock = QTimer(self)
        self._clock.setInterval(10000)
        self._clock.timeout.connect(self._refresh_meta)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        self.card = QFrame()
        self.card.setObjectName("card")
        outer.addWidget(self.card)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(38)
        shadow.setColor(QColor(24, 58, 74, 70))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(9)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.dot = QFrame()
        self.dot.setFixedSize(8, 8)
        self.title = QLabel("")
        self.title.setObjectName("ntitle")
        head.addWidget(self.dot)
        head.addWidget(self.title)
        head.addStretch(1)
        self.fired_label = QLabel("")
        self.fired_label.setObjectName("ntime")
        self.fired_label.setToolTip("提醒发出的时间")
        head.addWidget(self.fired_label)
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("nclose")
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.clicked.connect(self.hide)
        head.addWidget(self.close_btn)
        lay.addLayout(head)

        self.desc = QLabel("")
        self.desc.setObjectName("ndesc")
        self.desc.setWordWrap(True)
        lay.addWidget(self.desc)

        self.meta = QLabel("")
        self.meta.setObjectName("nmeta")
        lay.addWidget(self.meta)
        lay.addStretch(1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn2 = QPushButton("")
        self.btn2.setObjectName("nghost")
        self.btn2.setFixedHeight(36)
        self.btn1 = QPushButton("")
        self.btn1.setObjectName("nprimary")
        self.btn1.setFixedHeight(36)
        btns.addWidget(self.btn2, 1)
        btns.addWidget(self.btn1, 1)
        lay.addLayout(btns)

        self.btn1.clicked.connect(self._on1)
        self.btn2.clicked.connect(self._on2)

        self.setStyleSheet(f"""
            QFrame#card {{
                background: rgba(255,255,255,0.97);
                border: 1px solid {C_LINE};
                border-radius: 12px;
            }}
            QLabel#ntitle {{ color: {C_TEXT}; font-size: 15px; font-weight: 700;
                             font-family: "{FONT}"; }}
            QLabel#ndesc  {{ color: {C_SUBTLE}; font-size: 12px; font-family: "{FONT}"; }}
            QLabel#ntime  {{ color: {C_SUBTLE}; font-size: 13px; font-weight: 600;
                             font-family: "{FONT}"; }}
            QLabel#nmeta  {{ color: {C_SUBTLE}; font-size: 11px; font-family: "{FONT}"; }}
            QPushButton#nprimary {{
                background: {C_PRIMARY}; color: #fff; border: none;
                border-radius: 10px; font-size: 13px; font-weight: 600;
                font-family: "{FONT}";
            }}
            QPushButton#nprimary:hover {{ background: {C_PRIMARY_D}; }}
            QPushButton#nghost {{
                background: #fff; color: {C_PRIMARY}; border: 1px solid #cfe1ec;
                border-radius: 10px; font-size: 13px; font-family: "{FONT}";
            }}
            QPushButton#nghost:hover {{ background: {C_PRIMARY_L}; }}
            QPushButton#nclose {{
                background: transparent; color: {C_SUBTLE}; border: none;
                font-size: 16px; border-radius: 11px;
            }}
            QPushButton#nclose:hover {{ background: #f1f5f7; color: {C_TEXT}; }}
        """)

    def show_card(self, kind: str, title: str, desc: str,
                  text1: str, text2: str, cb1, cb2, pet_rect=None) -> None:
        accent = C_DANGER if kind == "work" else C_SUCCESS
        self.dot.setStyleSheet(f"background:{accent}; border-radius:4px;")
        self.title.setText(title)
        self.desc.setText(desc)
        self.btn1.setText(text1)
        self.btn2.setText(text2)
        self._cb1, self._cb2 = cb1, cb2
        self._fired_at = datetime.now()
        self.fired_label.setText(self._fired_at.strftime("%H:%M"))
        self._refresh_meta()
        self._clock.start()

        screen = QApplication.primaryScreen().availableGeometry()
        w, h = self.width(), self.height()
        x = screen.right() - w - 24
        y = screen.bottom() - h - 24
        # 和桌宠会重叠就让开：先挪到番茄上方，上方也放不下就挪到番茄左侧
        if pet_rect is not None and pet_rect.intersects(QRect(x, y, w, h)):
            y = pet_rect.top() - h - 12
            if y < screen.top() + 12:
                y = screen.bottom() - h - 24
                x = pet_rect.left() - w - 12
                if x < screen.left() + 12:
                    x = screen.left() + 12
        self.move(x, y + 36)
        self.show()
        self.raise_()
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(280)
        self._anim.setStartValue(QPoint(x, y + 36))
        self._anim.setEndValue(QPoint(x, y))
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def _on1(self):
        cb = self._cb1
        self.hide()
        if cb:
            cb()

    def _on2(self):
        cb = self._cb2
        self.hide()
        if cb:
            cb()

    # -- 实时时间行
    def _refresh_meta(self) -> None:
        if self._fired_at is None:
            return
        text, late = fmt_notice_meta(self._fired_at, datetime.now())
        self.meta.setText(text)
        color = "#e8a13c" if late else C_SUBTLE
        self.meta.setStyleSheet(
            f"color:{color}; font-size:11px; font-family:'{FONT}';"
        )

    def showEvent(self, e):
        super().showEvent(e)
        if self._fired_at is not None:
            self._clock.start()

    def hideEvent(self, e):
        self._clock.stop()
        super().hideEvent(e)


# ---------------------------------------------------------------- 展开面板
class Panel(QWidget):
    def __init__(self, ctrl: Controller, store: Store, pet: PetWindow):
        super().__init__()
        self.ctrl = ctrl
        self.store = store
        self.pet = pet
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(PANEL_W, PANEL_H)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        self.card = QFrame()
        self.card.setObjectName("card")
        outer.addWidget(self.card)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(46)
        shadow.setColor(QColor(24, 58, 74, 62))
        shadow.setOffset(0, 10)
        self.card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(22, 16, 22, 18)
        lay.setSpacing(12)

        # --- 顶部标题（可拖动）
        head = DragBar(self, self.card)
        head.setFixedHeight(34)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(make_tomato_icon(20, C_DANGER).pixmap(20, 20))
        logo.setFixedSize(20, 20)
        title = QLabel("番茄钟")
        title.setObjectName("h1")
        self.badge = QLabel("准备开始")
        self.badge.setObjectName("badge")
        hl.addWidget(logo)
        hl.addWidget(title)
        hl.addWidget(self.badge)
        hl.addStretch(1)
        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("close")
        self.btn_min.setFixedSize(24, 24)
        self.btn_min.setToolTip("收起面板")
        self.btn_min.clicked.connect(self.hide)
        hl.addWidget(self.btn_min)
        lay.addWidget(head)

        # --- 环形进度
        self.ring = RingWidget(ctrl)
        lay.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignHCenter)

        # --- KPI
        kpi = QHBoxLayout()
        kpi.setSpacing(12)
        self.kpi_count = self._kpi_block("今日番茄", "0 个")
        self.kpi_focus = self._kpi_block("专注时长", "0m")
        kpi.addWidget(self.kpi_count[0], 1)
        kpi.addWidget(self.kpi_focus[0], 1)
        lay.addLayout(kpi)

        # --- 点阵
        self.dots = TodayDots(store, ctrl, 5)
        lay.addWidget(self.dots)

        # --- 主按钮
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_main = QPushButton("开始专注")
        self.btn_main.setObjectName("primary")
        self.btn_main.setFixedHeight(42)
        self.btn_main.clicked.connect(self._on_main)
        self.btn_reset = QPushButton("重置")
        self.btn_reset.setObjectName("ghost")
        self.btn_reset.setFixedHeight(42)
        self.btn_reset.setFixedWidth(96)
        self.btn_reset.clicked.connect(ctrl.reset)
        btns.addWidget(self.btn_main, 1)
        btns.addWidget(self.btn_reset)
        lay.addLayout(btns)

        # --- 分隔线
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{C_LINE};")
        lay.addWidget(line)

        # --- 时长设置
        cfg = QHBoxLayout()
        cfg.setSpacing(8)
        lbl = QLabel("专注")
        lbl.setObjectName("muted")
        self.spin_work = QSpinBox()
        self.spin_work.setRange(1, 180)
        self.spin_work.setValue(store.work_min)
        self.spin_work.setSuffix(" 分")
        self.spin_work.setFixedWidth(86)
        lbl2 = QLabel("休息")
        lbl2.setObjectName("muted")
        self.spin_break = QSpinBox()
        self.spin_break.setRange(1, 60)
        self.spin_break.setValue(store.break_min)
        self.spin_break.setSuffix(" 分")
        self.spin_break.setFixedWidth(86)
        cfg.addWidget(lbl)
        cfg.addWidget(self.spin_work)
        cfg.addSpacing(10)
        cfg.addWidget(lbl2)
        cfg.addWidget(self.spin_break)
        cfg.addStretch(1)
        lay.addLayout(cfg)

        hint = QLabel("结束后会停下等你确认 · 双击番茄可收起")
        hint.setObjectName("hint")
        lay.addWidget(hint)

        self.spin_work.valueChanged.connect(self._on_spin)
        self.spin_break.valueChanged.connect(self._on_spin)
        ctrl.state_changed.connect(self.refresh)
        self.setStyleSheet(self._qss())
        self.refresh()

    # -- 组件工厂
    def _kpi_block(self, caption: str, value: str):
        box = QFrame()
        box.setObjectName("kpi")
        box.setFixedWidth(154)          # 两张卡等宽，避免左边被内容撑开
        v = QVBoxLayout(box)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(1)
        num = QLabel(value)
        num.setObjectName("kpi_num")
        cap = QLabel(caption)
        cap.setObjectName("muted")
        v.addWidget(num)
        v.addWidget(cap)
        return box, num

    def _qss(self) -> str:
        return f"""
        QFrame#card {{
            background: rgba(255,255,255,0.96);
            border: 1px solid {C_LINE};
            border-radius: 14px;
        }}
        QLabel {{ color: {C_TEXT}; font-family: "{FONT}"; }}
        QLabel#h1 {{ font-size: 15px; font-weight: 700; letter-spacing: 1px; }}
        QLabel#badge {{
            background: {C_PRIMARY_L}; color: {C_PRIMARY_D};
            border-radius: 9px; padding: 2px 9px; font-size: 11px;
        }}
        QLabel#muted {{ color: {C_SUBTLE}; font-size: 12px; }}
        QLabel#hint  {{ color: #9aa8b0; font-size: 10px; }}
        QFrame#kpi {{
            background: #f8fafb; border: 1px solid #eef2f4; border-radius: 10px;
        }}
        QLabel#kpi_num {{ font-size: 22px; font-weight: 700; color: {C_TEXT}; }}
        QPushButton#primary {{
            background: {C_PRIMARY}; color: #fff; border: none; border-radius: 10px;
            font-size: 14px; font-weight: 600; font-family: "{FONT}";
        }}
        QPushButton#primary:hover {{ background: {C_PRIMARY_D}; }}
        QPushButton#primary:pressed {{ background: #357da3; }}
        QPushButton#primary:disabled {{ background: #c9d8e0; }}
        QPushButton#ghost {{
            background: #fff; color: {C_PRIMARY}; border: 1px solid #cfe1ec;
            border-radius: 10px; font-size: 13px; font-family: "{FONT}";
        }}
        QPushButton#ghost:hover {{ background: {C_PRIMARY_L}; }}
        QPushButton#close {{
            background: transparent; color: {C_SUBTLE}; border: none;
            font-size: 15px; border-radius: 12px;
        }}
        QPushButton#close:hover {{ background: #f1f5f7; color: {C_TEXT}; }}
        QSpinBox {{
            background: #fff; border: 1px solid {C_LINE}; border-radius: 8px;
            padding: 4px 6px; font-size: 12px; color: {C_TEXT};
            font-family: "{FONT}";
        }}
        QSpinBox::up-button, QSpinBox::down-button {{ width: 14px; border: none; }}
        """

    # -- 事件
    def _on_main(self):
        ctrl = self.ctrl
        if ctrl.state == "finished":
            if ctrl.phase == "work":
                ctrl.switch_phase()
            ctrl.start()
        else:
            ctrl.toggle()

    def _on_spin(self, _v):
        self.ctrl.set_durations(self.spin_work.value(), self.spin_break.value())

    def closeEvent(self, e):
        e.ignore()
        self.hide()

    # -- 刷新
    def refresh(self) -> None:
        ctrl = self.ctrl
        st = ctrl.state
        if st == "finished":
            self.btn_main.setText("开始休息" if ctrl.phase == "work" else "开始下一轮")
        elif st == "running":
            self.btn_main.setText("暂停")
        elif st == "paused":
            self.btn_main.setText("继续")
        else:
            self.btn_main.setText("开始休息" if ctrl.phase == "break" else "开始专注")
        self.btn_main.setEnabled(True)

        self.badge.setText(ctrl.status_text())
        if ctrl.phase == "break":
            self.badge.setStyleSheet(
                f"background:#e8f6ef; color:{C_SUCCESS}; border-radius:9px;"
                f"padding:2px 9px; font-size:11px;"
            )
        else:
            self.badge.setStyleSheet(
                f"background:{C_PRIMARY_L}; color:{C_PRIMARY_D}; border-radius:9px;"
                f"padding:2px 9px; font-size:11px;"
            )

        self.kpi_count[1].setText(f"{self.store.today_count} 个")
        self.kpi_focus[1].setText(fmt_span(self.store.today_focus))
        self.dots.update()

    # -- 显示
    def popup_near_pet(self) -> None:
        pos = self.store.saved_pos("panel_pos")
        if pos is None or not visible_on_some_screen(pos, PANEL_W, PANEL_H):
            g = QApplication.primaryScreen().availableGeometry()
            pet_geo = self.pet.frameGeometry()
            x = pet_geo.right() + 16
            y = pet_geo.top() - (PANEL_H - PET_SIZE) // 2
            if x + PANEL_W > g.right() - 10:
                x = pet_geo.left() - PANEL_W - 16
            y = max(g.top() + 10, min(y, g.bottom() - PANEL_H - 10))
            pos = QPoint(x, y)
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.popup_near_pet()

    def hideEvent(self, e):
        self.store.save_pos("panel_pos", self.pos())
        super().hideEvent(e)


# ---------------------------------------------------------------- 组装
class App(QObject):
    def __init__(self, demo: bool = False):
        super().__init__()
        self.store = Store(DATA_FILE)
        self.ctrl = Controller(self.store)
        if demo:
            self.ctrl.demo = (4, 4)
            self.ctrl.phase = "work"
            self.ctrl.remaining = 4.0

        self.pet = PetWindow(self.ctrl, self.store)
        self.panel = Panel(self.ctrl, self.store, self.pet)
        self.notice = NoticeCard()

        pos = self.store.saved_pos("pet_pos")
        if pos is None or not visible_on_some_screen(pos, PET_SIZE, PET_SIZE):
            g = QApplication.primaryScreen().availableGeometry()
            pos = QPoint(g.right() - PET_SIZE - 48, g.bottom() - PET_SIZE - 150)
        self.pet.move(pos)

        self.pet.double_clicked.connect(self.panel.toggle_visible)
        self.pet.menu_requested.connect(self._show_menu)
        self.ctrl.phase_finished.connect(self._on_finished)

        self.tray = QSystemTrayIcon(make_tomato_icon(64), self)
        self.tray.setToolTip("番茄桌宠")
        menu = QMenu()
        self.act_panel = QAction("展开面板", self)
        self.act_panel.triggered.connect(self.panel.toggle_visible)
        self.act_toggle = QAction("开始 / 暂停", self)
        self.act_toggle.triggered.connect(self.ctrl.toggle)
        self.act_reset = QAction("重置本轮", self)
        self.act_reset.triggered.connect(self.ctrl.reset)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.quit)
        menu.addAction(self.act_panel)
        menu.addAction(self.act_toggle)
        menu.addAction(self.act_reset)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self.pet.show()
        self.ctrl.state_changed.connect(self._sync_tooltip)
        self._sync_tooltip()

        if demo:
            QTimer.singleShot(600, self.ctrl.start)

    # -- 到点
    def _on_finished(self, phase: str) -> None:
        play_alert(phase)
        self.pet.celebrate()
        nxt = self.store.break_min
        pet_rect = self.pet.frameGeometry()
        if phase == "work":
            self.notice.show_card(
                "work", "专注结束",
                f"这一轮记下了。休息 {nxt} 分钟，还是直接开始下一轮？",
                f"休息 {nxt} 分钟", "跳过休息",
                self._start_break, self._skip_break,
                pet_rect=pet_rect,
            )
        else:
            self.notice.show_card(
                "break", "休息结束",
                "准备好了就继续，节奏你说了算。",
                "开始下一轮", "稍后",
                self._start_next, lambda: None,
                pet_rect=pet_rect,
            )

    def _start_break(self) -> None:
        if self.ctrl.phase == "work":
            self.ctrl.switch_phase()
        self.ctrl.start()

    def _skip_break(self) -> None:
        self.ctrl.skip_break()

    def _start_next(self) -> None:
        if self.ctrl.phase == "break":
            self.ctrl.switch_phase()
        self.ctrl.start()

    # -- 菜单
    def _show_menu(self, global_pos: QPoint) -> None:
        menu = QMenu()
        a1 = QAction("暂停" if self.ctrl.is_running() else "开始", menu)
        a1.triggered.connect(self.ctrl.toggle)
        a2 = QAction("重置本轮", menu)
        a2.triggered.connect(self.ctrl.reset)
        a3 = QAction("展开面板", menu)
        a3.triggered.connect(self.panel.toggle_visible)
        a4 = QAction("退出", menu)
        a4.triggered.connect(self.quit)
        menu.addAction(a1)
        menu.addAction(a2)
        menu.addSeparator()
        menu.addAction(a3)
        menu.addSeparator()
        menu.addAction(a4)
        menu.exec(global_pos)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.panel.toggle_visible()

    def _sync_tooltip(self) -> None:
        c = self.ctrl
        tip = (f"番茄桌宠 · {c.status_text()} {c.time_text()}"
               f" · 今日 {self.store.today_count} 个")
        if self.pet.toolTip() != tip:
            self.pet.setToolTip(tip)
        self.tray.setToolTip(f"番茄桌宠 {c.time_text()}")

    def quit(self) -> None:
        self.store.save_pos("pet_pos", self.pet.pos())
        self.store.save_pos("panel_pos", self.panel.pos())
        self.tray.hide()
        QApplication.quit()


# ---------------------------------------------------------------- 入口
def _install_excepthook() -> None:
    def hook(t, v, tb):
        try:
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
                f.write("".join(traceback.format_exception(t, v, tb)))
        except Exception:
            pass
    sys.excepthook = hook


def main() -> int:
    _install_excepthook()
    demo = "--demo" in sys.argv

    app = QApplication(sys.argv)
    app.setApplicationName("PomodoroPet")
    app.setQuitOnLastWindowClosed(False)

    lock_path = Path(tempfile.gettempdir()) / "pomodoro_pet.lock"
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(30000)     # 30 秒没心跳就认为锁是残留的（进程被杀会留锁）
    if not lock.tryLock(200):
        # 已经在跑了：静默退出，不弹框（用户屏幕右下角已经有番茄了）
        return 0

    window = App(demo=demo)          # noqa: F841
    window.lock = lock               # 防止被 GC 提前释放
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
