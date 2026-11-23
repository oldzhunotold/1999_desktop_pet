# -*- coding: utf-8 -*-
"""桌宠设置：读写 settings.json + 深色设置面板。"""

import json

from PySide6.QtCore import Property, QPointF, QRectF, Qt, QTimer, QPropertyAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

DEFAULTS = {
    "scale": 0.6,
    "char_ms": 45,
    "hold_ms": 1000,
    "show_seconds": 90,
    "auto_sleep": False,
    "sleep_minutes": 3,
    "wake_minutes": 10,
    "autostart": False,
    "always_on_top": True,
    "hide_fullscreen": True,
    "click_through_hidden_cursor": True,
    "allow_cross_screen": False,
    "allow_offscreen": True,
    "initial_char": "",
    "initial_outfit": "",
}

VERSION = "v1.1.1"

STYLE = """
QDialog { background: #1b1c21; border: 1px solid #2b2c32; }
QWidget#titlebar { background: #17181c; }
QLabel#winTitle { font-size: 14px; font-weight: bold; color: #f0f0f3; }
QPushButton#closeBtn { background: transparent; border: none; color: #b9bac1; font-size: 15px; }
QPushButton#closeBtn:hover { background: #3a2630; border-radius: 6px; color: #ff6b8a; }
QWidget { color: #e6e6ea; font-family: "Microsoft YaHei"; font-size: 13px; }
QListWidget { background: #1b1c21; border: none; outline: none; }
QListWidget::item { padding: 9px 14px; border-radius: 8px; color: #b9bac1; }
QListWidget::item:selected { background: #2a2b32; color: #ffffff; }
QListWidget::item:hover { background: #24252b; }
QLabel#pageTitle { font-size: 20px; font-weight: bold; color: #ffffff; }
QLabel#sectionTitle { font-size: 15px; font-weight: bold; color: #ffffff; padding-top: 6px; }
QLabel#rowTitle { font-size: 13px; color: #ececf0; }
QLabel#rowDesc { color: #8f9099; font-size: 12px; }
QLabel#hint { color: #8f9099; font-size: 12px; }
QFrame#card { background: #232429; border-radius: 10px; }
QSpinBox, QDoubleSpinBox {
    background: #2c2d34; border: 1px solid #3a3b43; border-radius: 6px;
    padding: 4px 8px; color: #ffffff; min-width: 90px;
}
QCheckBox::indicator {
    width: 38px; height: 20px; border-radius: 10px; background: #3a3b43;
}
QCheckBox::indicator:checked { background: #e8578a; }
QPushButton#saveBtn {
    background: #2c2d34; border: 1px solid #3a3b43; border-radius: 8px;
    padding: 8px 12px; color: #ffffff; text-align: left;
}
QPushButton#saveBtn:hover { background: #35363e; }
QPushButton#resetBtn {
    background: transparent; border: none; border-radius: 8px;
    padding: 8px 12px; color: #b9bac1; text-align: left;
}
QPushButton#resetBtn:hover { background: #24252b; }
QScrollArea { border: none; background: #1b1c21; }
QScrollArea > QWidget > QWidget { background: #1b1c21; }
QStackedWidget { background: #1b1c21; }
"""


def load(path: str) -> dict:
    data = dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            got = json.load(f)
        if isinstance(got, dict):
            for k in DEFAULTS:
                if k in got:
                    data[k] = got[k]
    except Exception:
        pass
    return data


def save(path: str, data: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _row(title: str, desc: str, control: QWidget) -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    lay = QHBoxLayout(card)
    lay.setContentsMargins(14, 10, 14, 10)
    text = QVBoxLayout()
    text.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("rowTitle")
    d = QLabel(desc)
    d.setObjectName("rowDesc")
    d.setWordWrap(True)
    text.addWidget(t)
    text.addWidget(d)
    lay.addLayout(text, 1)
    lay.addWidget(control, 0, Qt.AlignVCenter)
    return card


def _page(title: str):
    page = QWidget()
    page.setStyleSheet("background: #1b1c21;")
    outer = QVBoxLayout(page)
    outer.setContentsMargins(24, 18, 24, 18)
    outer.setSpacing(10)
    h = QLabel(title)
    h.setObjectName("pageTitle")
    outer.addWidget(h)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("background: #1b1c21; border: none;")
    inner = QWidget()
    inner.setStyleSheet("background: #1b1c21;")
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 6, 0, 6)
    v.setSpacing(8)
    scroll.setWidget(inner)
    outer.addWidget(scroll, 1)
    return page, v


ON_COLOR = QColor(223, 105, 49)
OFF_COLOR = QColor(58, 59, 67)
KNOB_COLOR = QColor(255, 255, 255)


class ToggleSwitch(QCheckBox):
    """iOS 风格开关：橙色选中、白色圆钮、带滑动动画。"""

    W = 44
    H = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self.W, self.H)
        self._offset = 1.0 if self.isChecked() else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self.toggled.connect(self._animate)

    def _get_offset(self):
        return self._offset

    def _set_offset(self, value):
        self._offset = float(value)
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = self.H / 2.0
        p.setBrush(ON_COLOR if self.isChecked() else OFF_COLOR)
        p.drawRoundedRect(QRectF(0, 0, self.W, self.H), r, r)
        d = self.H - 6
        x = 3 + self._offset * (self.W - d - 6)
        p.setBrush(KNOB_COLOR)
        p.drawEllipse(QRectF(x, 3, d, d))


class SettingsDialog(QDialog):
    def __init__(
        self, parent, values: dict, on_apply, choices=None, on_import=None
    ):
        super().__init__(parent)
        self.setWindowTitle("桌宠设置")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setMinimumSize(720, 520)
        self.resize(880, 680)
        self.setStyleSheet(STYLE)
        self._on_apply = on_apply
        self._choices = choices or {}
        self._on_import = on_import
        self._drag = None
        self._title_h = 44

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        titlebar = QWidget()
        titlebar.setObjectName("titlebar")
        titlebar.setFixedHeight(self._title_h)
        tb = QHBoxLayout(titlebar)
        tb.setContentsMargins(16, 0, 10, 0)
        win_title = QLabel("桌宠设置")
        win_title.setObjectName("winTitle")
        btn_close = QPushButton("✕")
        btn_close.setObjectName("closeBtn")
        btn_close.setFixedSize(28, 28)
        btn_close.clicked.connect(self.close)
        tb.addWidget(win_title)
        tb.addStretch(1)
        tb.addWidget(btn_close)
        outer.addWidget(titlebar)

        content = QWidget()
        root = QHBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        outer.addWidget(content, 1)

        # ---- 左侧导航 ----
        left = QWidget()
        left.setFixedWidth(210)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(14, 16, 14, 14)
        left_lay.setSpacing(8)

        self.nav = QListWidget()
        for name in ("常规", "桌宠", "气泡", "动作", "关于"):
            self.nav.addItem(name)
        left_lay.addWidget(self.nav, 1)

        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("saveBtn")
        self.btn_save.clicked.connect(self._save)
        left_lay.addWidget(self.btn_save)

        btn_reset = QPushButton("恢复默认")
        btn_reset.setObjectName("resetBtn")
        btn_reset.clicked.connect(self._reset)
        left_lay.addWidget(btn_reset)

        ver = QLabel(VERSION)
        ver.setObjectName("hint")
        ver.setAlignment(Qt.AlignCenter)
        left_lay.addWidget(ver)

        root.addWidget(left)

        # ---- 右侧分页 ----
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # 常规
        page, v = _page("常规")
        sec = QLabel("桌宠")
        sec.setObjectName("sectionTitle")
        v.addWidget(sec)

        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.2, 1.5)
        self.scale.setSingleStep(0.05)
        self.scale.setValue(float(values.get("scale", 0.6)))
        v.addWidget(_row("桌宠大小", "桌宠在屏幕上显示的大小，1.0 为原始尺寸。", self.scale))

        top_box = QWidget()
        th = QHBoxLayout(top_box)
        th.setContentsMargins(0, 0, 0, 0)
        th.addStretch(1)
        self.always_on_top = ToggleSwitch()
        self.always_on_top.setChecked(bool(values.get("always_on_top", True)))
        th.addWidget(self.always_on_top)
        v.addWidget(
            _row("窗口置顶", "始终将桌宠保持在其他窗口上方。", top_box)
        )

        full_box = QWidget()
        fh = QHBoxLayout(full_box)
        fh.setContentsMargins(0, 0, 0, 0)
        fh.addStretch(1)
        self.hide_fullscreen = ToggleSwitch()
        self.hide_fullscreen.setChecked(bool(values.get("hide_fullscreen", True)))
        fh.addWidget(self.hide_fullscreen)
        v.addWidget(
            _row("全屏时自动隐藏", "全屏游戏或视频期间自动隐藏桌宠。", full_box)
        )

        pass_box = QWidget()
        ph = QHBoxLayout(pass_box)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.addStretch(1)
        self.click_through = ToggleSwitch()
        self.click_through.setChecked(
            bool(values.get("click_through_hidden_cursor", True))
        )
        ph.addWidget(self.click_through)
        v.addWidget(
            _row(
                "光标隐藏时自动穿透",
                "系统隐藏光标时，桌宠自动穿透点击；光标出现立刻恢复。",
                pass_box,
            )
        )

        cross_box = QWidget()
        ch = QHBoxLayout(cross_box)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.addStretch(1)
        self.cross_screen = ToggleSwitch()
        self.cross_screen.setChecked(bool(values.get("allow_cross_screen", False)))
        ch.addWidget(self.cross_screen)
        off_box = QWidget()
        oh = QHBoxLayout(off_box)
        oh.setContentsMargins(0, 0, 0, 0)
        oh.addStretch(1)
        self.allow_offscreen = ToggleSwitch()
        self.allow_offscreen.setChecked(bool(values.get("allow_offscreen", True)))
        oh.addWidget(self.allow_offscreen)
        v.addWidget(
            _row(
                "允许移出屏幕",
                "可以把桌宠拖到屏幕边缘外，至少保留一小块可见。",
                off_box,
            )
        )

        v.addWidget(
            _row(
                "允许桌宠跨屏",
                "开启后可拖到任意一块显示器；关闭时只能在当前屏幕内移动。",
                cross_box,
            )
        )

        start_box = QWidget()
        sh = QHBoxLayout(start_box)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.addStretch(1)
        self.autostart = ToggleSwitch()
        self.autostart.setChecked(bool(values.get("autostart", False)))
        sh.addWidget(self.autostart)
        v.addWidget(_row("开机自启", "登录 Windows 后自动启动桌宠（默认关闭）。", start_box))
        v.addStretch(1)
        self.stack.addWidget(page)

        # 桌宠
        page, v = _page("桌宠")
        sec = QLabel("启动时显示")
        sec.setObjectName("sectionTitle")
        v.addWidget(sec)

        self.char_combo = QComboBox()
        self.outfit_combo = QComboBox()
        for combo in (self.char_combo, self.outfit_combo):
            combo.setMinimumWidth(220)
            combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            combo.setMinimumContentsLength(10)
        chars = self._choices.get("characters", [])
        for folder, label in chars:
            self.char_combo.addItem(label, folder)
        cur_char = values.get("initial_char") or (chars[0][0] if chars else "")
        idx = self.char_combo.findData(cur_char)
        if idx >= 0:
            self.char_combo.setCurrentIndex(idx)
        self._refresh_outfits(values.get("initial_outfit") or "")
        self.char_combo.currentIndexChanged.connect(self._on_char_changed)
        self.outfit_combo.currentIndexChanged.connect(self._autosave_pet)

        self.btn_import = QPushButton("导入角色…")
        self.btn_import.clicked.connect(self._do_import)
        v.addWidget(_row("导入角色", "导入自己准备的角色素材（文件夹或 zip）。", self.btn_import))

        v.addWidget(_row("初始角色", "启动桌宠时显示哪个角色。", self.char_combo))
        v.addWidget(_row("初始服装", "该角色启动时穿哪套衣服。", self.outfit_combo))
        tip = QLabel("保存后立即切换；下次启动也用它。")
        tip.setObjectName("hint")
        v.addWidget(tip)
        v.addStretch(1)
        self.stack.addWidget(page)

        # 气泡
        page, v = _page("气泡")
        sec = QLabel("显示")
        sec.setObjectName("sectionTitle")
        v.addWidget(sec)

        self.char_ms = QSpinBox()
        self.char_ms.setRange(10, 200)
        self.char_ms.setSuffix(" ms")
        self.char_ms.setValue(int(values.get("char_ms", 45)))
        v.addWidget(_row("打字速度", "每个字出现的间隔，越小越快。", self.char_ms))

        self.hold_ms = QSpinBox()
        self.hold_ms.setRange(200, 8000)
        self.hold_ms.setSingleStep(100)
        self.hold_ms.setSuffix(" ms")
        self.hold_ms.setValue(int(values.get("hold_ms", 1000)))
        v.addWidget(_row("每段停留", "一段念完后停留多久，再开始下一段。", self.hold_ms))

        v.addStretch(1)
        self.stack.addWidget(page)

        # 动作
        page, v = _page("动作")
        sec = QLabel("自动行为")
        sec.setObjectName("sectionTitle")
        v.addWidget(sec)

        self.show_seconds = QSpinBox()
        self.show_seconds.setRange(0, 900)
        self.show_seconds.setSuffix(" 秒")
        self.show_seconds.setSpecialValueText("关闭")
        self.show_seconds.setValue(int(values.get("show_seconds", 90)))
        v.addWidget(
            _row("自动表演", "一段时间没互动，自己挑个动作表演；0 为关闭。", self.show_seconds)
        )

        sleep_box = QWidget()
        h = QHBoxLayout(sleep_box)
        h.setContentsMargins(0, 0, 0, 0)
        h.addStretch(1)
        self.auto_sleep = ToggleSwitch()
        self.auto_sleep.setChecked(bool(values.get("auto_sleep", False)))
        h.addWidget(self.auto_sleep)
        v.addWidget(_row("自动睡觉", "长时间没人理就进入睡眠姿态，点一下会醒。", sleep_box))

        self.sleep_minutes = QSpinBox()
        self.sleep_minutes.setRange(1, 120)
        self.sleep_minutes.setSuffix(" 分钟")
        self.sleep_minutes.setValue(int(values.get("sleep_minutes", 3)))
        v.addWidget(_row("多久后睡觉", "多久没有互动后入睡。", self.sleep_minutes))

        self.wake_minutes = QSpinBox()
        self.wake_minutes.setRange(1, 240)
        self.wake_minutes.setSuffix(" 分钟")
        self.wake_minutes.setValue(int(values.get("wake_minutes", 10)))
        v.addWidget(_row("睡多久醒来", "睡够这么久会自己醒来，回到待机。", self.wake_minutes))

        v.addStretch(1)
        self.stack.addWidget(page)

        # 关于
        page, v = _page("关于")
        about = QLabel(
            "重返未来 1999 · 桌面宠物\n\n"
            "用 PySide6 写的桌宠：透明置顶、多角色与服装切换、逐字台词气泡。\n"
            "素材版权归 Bluepoch 所有，仅供学习与个人使用。"
        )
        about.setWordWrap(True)
        v.addWidget(about)
        v.addStretch(1)
        self.stack.addWidget(page)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch(1)
        grip_row.addWidget(QSizeGrip(self))
        outer.addLayout(grip_row)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self._ready = True

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < self._title_h:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag = None
        super().mouseReleaseEvent(event)

    def _do_import(self):
        if self._on_import:
            self._on_import(self)

    def _on_char_changed(self, _index: int = 0):
        self._refresh_outfits("")
        self._autosave_pet()

    def _autosave_pet(self):
        if getattr(self, "_ready", False):
            self._on_apply(self._collect())

    def _refresh_outfits(self, preferred: str = ""):
        self.outfit_combo.clear()
        char = self.char_combo.currentData()
        outfits = self._choices.get("outfits", {}).get(char, [])
        for folder, label in outfits:
            self.outfit_combo.addItem(label, folder)
        if not outfits:
            return
        idx = self.outfit_combo.findData(preferred) if preferred else -1
        if idx < 0:
            idx = self.outfit_combo.findData("Default")
        self.outfit_combo.setCurrentIndex(max(0, idx))

    def _save(self):
        self._on_apply(self._collect())
        self.btn_save.setText("已保存")
        QTimer.singleShot(1200, lambda: self.btn_save.setText("保存"))

    def _collect(self) -> dict:
        return {
            "scale": round(self.scale.value(), 2),
            "char_ms": self.char_ms.value(),
            "hold_ms": self.hold_ms.value(),
            "show_seconds": self.show_seconds.value(),
            "auto_sleep": self.auto_sleep.isChecked(),
            "sleep_minutes": self.sleep_minutes.value(),
            "wake_minutes": self.wake_minutes.value(),
            "autostart": self.autostart.isChecked(),
            "always_on_top": self.always_on_top.isChecked(),
            "hide_fullscreen": self.hide_fullscreen.isChecked(),
            "click_through_hidden_cursor": self.click_through.isChecked(),
            "allow_cross_screen": self.cross_screen.isChecked(),
            "allow_offscreen": self.allow_offscreen.isChecked(),
            "initial_char": self.char_combo.currentData() or "",
            "initial_outfit": self.outfit_combo.currentData() or "",
        }

    def _reset(self):
        self.scale.setValue(DEFAULTS["scale"])
        self.char_ms.setValue(DEFAULTS["char_ms"])
        self.hold_ms.setValue(DEFAULTS["hold_ms"])
        self.show_seconds.setValue(DEFAULTS["show_seconds"])
        self.auto_sleep.setChecked(DEFAULTS["auto_sleep"])
        self.autostart.setChecked(DEFAULTS["autostart"])
        self.always_on_top.setChecked(DEFAULTS["always_on_top"])
        self.hide_fullscreen.setChecked(DEFAULTS["hide_fullscreen"])
        self.click_through.setChecked(DEFAULTS["click_through_hidden_cursor"])
        self.cross_screen.setChecked(DEFAULTS["allow_cross_screen"])
        self.allow_offscreen.setChecked(DEFAULTS["allow_offscreen"])
        self.sleep_minutes.setValue(DEFAULTS["sleep_minutes"])
        self.wake_minutes.setValue(DEFAULTS["wake_minutes"])

    def accept(self):
        self._on_apply(self._collect())
        super().accept()
