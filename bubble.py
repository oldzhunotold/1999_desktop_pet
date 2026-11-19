# -*- coding: utf-8 -*-
"""角色头顶的气泡：逐字显示，1–2 行一段，念完自动接下一段。"""

import os

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

CHAR_MS = 45          # 每个字的间隔
PUNCT_MS = 220        # 标点后多停一下
HOLD_MS = 1000        # 一段念完停多久
GAP_MS = 600          # 两段之间的间隔
BUBBLE_W = 280        # 气泡宽度
PAD = 10              # 内边距
TAIL = 8              # 小尖角高度
MAX_LINES = 2         # 每段最多几行
PUNCT = "，。！？、；：…—"


def _wrap(text: str, fm: QFontMetrics, width: int, max_lines: int):
    """把一段文字按宽度折成最多 max_lines 行，超出用省略号。"""
    lines = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            if len(lines) >= max_lines:
                break
            continue
        if fm.horizontalAdvance(cur + ch) > width:
            lines.append(cur)
            cur = ch
            if len(lines) >= max_lines:
                break
        else:
            cur += ch
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if lines and sum(len(x) for x in lines) < len(text):
        last = lines[-1]
        while last and fm.horizontalAdvance(last + "…") > width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


class Bubble(QWidget):
    def __init__(self, pet):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.pet = pet
        self.font = QFont("Microsoft YaHei", 10)
        self.fm = QFontMetrics(self.font)
        self.line_h = self.fm.height()
        self.setFixedWidth(BUBBLE_W)
        self.setFixedHeight(self.line_h * MAX_LINES + PAD * 2 + TAIL)

        self._lines = []
        self._total = 0
        self._shown = 0
        self._typing = False
        self._done_cb = None
        self._below = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.hold = QTimer(self)
        self.hold.setSingleShot(True)
        self.hold.timeout.connect(self._end)
        self._punct_wait = False

    # ---------- 对外 ----------
    def say(self, text: str, on_done=None):
        self._done_cb = on_done
        self._lines = _wrap(text.strip(), self.fm, BUBBLE_W - PAD * 2, MAX_LINES)
        self._total = sum(len(x) for x in self._lines)
        self._shown = 0
        self._typing = True
        self._punct_wait = False
        # 气泡高度随行数变化
        self.setFixedHeight(len(self._lines) * self.line_h + PAD * 2 + TAIL)
        self._place()
        self.show()
        self.raise_()
        self.timer.start(CHAR_MS)
        self.update()

    def stop(self):
        self.timer.stop()
        self.hold.stop()
        self._typing = False
        self._done_cb = None
        self.hide()

    # ---------- 内部 ----------
    def _place(self):
        g = self.pet.frameGeometry()
        scr = self.pet.screen().availableGeometry()
        x = g.center().x() - self.width() // 2
        y = g.top() - self.height() + TAIL
        if y < scr.top() + 4:
            y = g.bottom() - TAIL
            self._below = True
        else:
            self._below = False
        x = max(scr.left() + 4, min(x, scr.right() - self.width() - 4))
        self.move(x, y)

    def _tick(self):
        if not self._typing:
            return
        if self._shown >= self._total:
            self._finish_typing()
            return
        self._show_next_char()
        self.update()
        if self._punct_wait:
            self._punct_wait = False
            self.timer.start(PUNCT_MS)
        else:
            self.timer.start(CHAR_MS)

    def _text_flat(self):
        return "".join(self._lines)

    def _show_next_char(self):
        flat = self._text_flat()
        if self._shown < len(flat):
            if flat[self._shown] in PUNCT:
                self._punct_wait = True
            self._shown += 1

    def _finish_typing(self):
        self._shown = self._total
        self._typing = False
        self.timer.stop()
        self.update()
        self.hold.start(HOLD_MS)

    def _end(self):
        cb = self._done_cb
        self._done_cb = None
        if cb:
            # 还有下一段：气泡框保留，只清空文字
            self._lines = []
            self._total = 0
            self._shown = 0
            self.update()
            QTimer.singleShot(GAP_MS, cb)
        else:
            self.hide()

    # ---------- 鼠标 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._typing:
                self._finish_typing()
            else:
                self.hold.stop()
                self._done_cb = None
                self.hide()
            event.accept()

    # ---------- 绘制 ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        body = QRectF(0, 0, self.width(), self.height() - TAIL)
        path = QPainterPath()
        path.addRoundedRect(body, 10, 10)

        # 小尖角
        tail = QPainterPath()
        cx = self.width() / 2
        if self._below:  # 气泡在下方，尖角朝上
            tail.moveTo(cx - 7, body.top())
            tail.lineTo(cx, body.top() - TAIL)
            tail.lineTo(cx + 7, body.top())
        else:
            tail.moveTo(cx - 7, body.bottom())
            tail.lineTo(cx, body.bottom() + TAIL)
            tail.lineTo(cx + 7, body.bottom())
        path = path.united(tail)

        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.setBrush(QColor(28, 30, 38, 230))
        p.drawPath(path)

        p.setFont(self.font)
        p.setPen(QColor(240, 240, 245))
        left = PAD
        top = PAD + self.fm.ascent()
        remain = self._shown
        for line in self._lines:
            if remain <= 0:
                break
            part = line[:remain]
            p.drawText(left, top, part)
            remain -= len(part)
            top += self.line_h
        p.end()
