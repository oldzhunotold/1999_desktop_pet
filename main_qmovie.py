# -*- coding: utf-8 -*-
"""1999 桌宠 · QMovie 版骨架

用法：
    python main_qmovie.py

素材放在 assets/noire/*.webp（idle / hit / sleep / born / special / skill1 / skill2）。
"""

import json
import os
import random
import sys

import autostart
import bubble as bubble_mod
import importer
import settings_ui

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QImageReader, QMovie, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)

from bubble import Bubble, BUBBLE_W, PAD, MAX_LINES, _wrap

try:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
except Exception:
    _user32 = None


def _cursor_hidden() -> bool:
    if _user32 is None:
        return False

    class CURSORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hCursor", wintypes.HANDLE),
            ("ptScreenPos", wintypes.POINT),
        ]

    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(ci)
    if not _user32.GetCursorInfo(ctypes.byref(ci)):
        return False
    return not (ci.flags & 0x00000001)


def _foreground_fullscreen(own_hwnd: int) -> bool:
    if _user32 is None:
        return False
    hwnd = int(_user32.GetForegroundWindow() or 0)
    if not hwnd or hwnd == own_hwnd:
        return False

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    rect = RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    hmon = _user32.MonitorFromWindow(hwnd, 2)
    if not hmon:
        return False
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(mi)
    if not _user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        return False
    m = mi.rcMonitor
    return (
        rect.left <= m.left
        and rect.top <= m.top
        and rect.right >= m.right
        and rect.bottom >= m.bottom
    )


def find_base():
    """兼容开发环境与 PyInstaller 打包（onedir / onefile）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(meipass)
    candidates.append(here)
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "assets")):
            return c
    return here


BASE = find_base()
ASSET_ROOT = os.path.join(BASE, "assets")
APP_ICON_PATH = os.path.join(BASE, "1999_desktop_pet.ico")


def app_icon():
    return QIcon(APP_ICON_PATH) if os.path.isfile(APP_ICON_PATH) else QIcon()
DEFAULT_CHAR = "菲林士多"
DEFAULT_OUTFIT = "Default"


def list_outfits(char):
    """assets/<角色>/<服装>/idle.webp 存在才算一套服装。"""
    base = os.path.join(ASSET_ROOT, char)
    if not os.path.isdir(base):
        return []
    return sorted(
        d for d in os.listdir(base)
        if os.path.isfile(os.path.join(base, d, "idle.webp")) or os.path.isfile(os.path.join(base, d, "idle_special.webp"))
    )


def list_characters():
    if not os.path.isdir(ASSET_ROOT):
        return []
    return sorted(d for d in os.listdir(ASSET_ROOT) if list_outfits(d))


def resolve_char(name):
    chars = list_characters()
    if name in chars:
        return name
    for key, label in CHAR_LABELS.items():
        if label == name and key in chars:
            return key
    env = os.environ.get("PET_CHAR", "")
    if env in chars:
        return env
    return chars[0] if chars else ""


def resolve_outfit(char, name):
    outfits = list_outfits(char)
    if name in outfits:
        return name
    for key, label in OUTFIT_LABELS.items():
        if label == name and key in outfits:
            return key
    env = os.environ.get("PET_OUTFIT", "")
    if env in outfits:
        return env
    return outfits[0] if outfits else ""

# 缩放：1.0 = 原始 512px；0.6 ≈ 307px
SCALE = 0.6

# 多久没人理她就去睡觉（毫秒）；睡下后一直保持，直到被点/被拖
IDLE_SLEEP_MS = 3 * 60 * 1000

# 多久没互动后，自己挑一个动作展示（毫秒）
IDLE_SHOW_MS = 90 * 1000

# 自动睡觉开关：关掉后不会自己睡，只能右键「睡觉」手动睡
AUTO_SLEEP = False

SETTINGS_PATH = os.path.join(BASE, "settings.json")
SETTINGS = settings_ui.load(SETTINGS_PATH)
SCALE = float(SETTINGS.get("scale", SCALE))
IDLE_SLEEP_MS = int(SETTINGS.get("sleep_minutes", 3)) * 60 * 1000
IDLE_SHOW_MS = int(SETTINGS.get("show_seconds", 90)) * 1000
AUTO_SLEEP = bool(SETTINGS.get("auto_sleep", False))
WAKE_MS = int(SETTINGS.get("wake_minutes", 10)) * 60 * 1000
bubble_mod.CHAR_MS = int(SETTINGS.get("char_ms", bubble_mod.CHAR_MS))
bubble_mod.HOLD_MS = int(SETTINGS.get("hold_ms", bubble_mod.HOLD_MS))

# 动作配置：循环的、其余都当单次播
LOOP_ACTIONS = {"idle", "sleep", "posture"}
IDLE_SPECIAL_WEIGHT = 2  # idle_special 在随机表演里的额外权重

ALWAYS_ON_TOP = bool(SETTINGS.get("always_on_top", True))
HIDE_FULLSCREEN = bool(SETTINGS.get("hide_fullscreen", True))
CLICK_THROUGH_HIDDEN = bool(SETTINGS.get("click_through_hidden_cursor", True))
ALLOW_CROSS_SCREEN = bool(SETTINGS.get("allow_cross_screen", False))
ALLOW_OFFSCREEN = bool(SETTINGS.get("allow_offscreen", True))
CHAR_LABELS = {
    "noire": "菲林士多",
    "marcus": "马库斯",
    "37":"37",
    "paper_heron":"鹭鸶剪",
    "sonetto":"十四行诗",
    "paper_heron":"鹭鸶剪",
    "sonetto":"十四行诗",
    "matilda":"玛蒂尔达",
    "kiperina":"库珀花环",
    "beryl":"贝丽尔",
    "perchta":"佩施塔",
    "baby_blue":"婴儿蓝",
    "lucy":"露西女士",
    "ulrich":"乌尔里希",
    "cheng_heguang":"程和光",
    "schneider":"斯奈德",
    "recoleta":"虚构集",
    "sentinel":"玛丽安娜",
    "jiu_niangzi":"曲娘",
    "isolde":"伊索尔德",
    "kakania":"卡卡尼亚",
    "windsong":"北方哨歌",
}
OUTFIT_LABELS = {
    "Default": "默认",
    "On_the_red_carpet": "红毯嘉宾",
    "The_trapped_trapmaster": "算尘寰",
    "A_returning_wind":"风儿吹回那日",
    "On_the_white_sand":"白沙与风",
    "The_gate_to_the_underground":"致冥府的门扉",
    "A_prime_number":"一个质数",
    "Happy_bird_catcher":"快乐的捕鸟人",
    "Down_in_the_grotto":"泉眼深处",
    "A_gift_of_nourishment":"完美的流体",
    "Downstream_of_letting_go":"新花故吾",
    "Parade_anthem":"巡礼颂",
    "Emotion_in_tranquility":"重叠的词句",
    "In_praise_of_poetry":"诗的礼赞",
    "Chef_de_madame":"首席淑女",
    "The_genius's_holiday":"天才假日",
    "The_great_taste_investigator":"尝鲜调查员",
    "A_box_of_marbles":"弹珠匣",
    "The_universe_in the_rooks_shell":"宇宙之壳",
    "A_utopia_in_painted_glass":"玻璃乌托邦",
    "Star_shepherdess":"牧于晚星",
    "The_flowing _stream's_luster":"水上浮光",
    "Plucking_the_strings_of_fate":"释命运以弦音",
    "Once_upon_a_runaway":"童话出逃日",
    "The_new_red_queen":"新“红皇后”",
    "On_the_sparrow_hills":"于麻雀山上",
    "A_robot_is_born":"一个机器人的诞生",
    "The_queens_game":"生如行棋",
    "Universe_in_the_tank":"缸中宇宙",
    "A_glimpse_of_the_cosmos": "叩响天宇一角",
    "Breaking_free_from_a_burning_cage":"檐外鹭",
    "The_third_second":"第三秒",
    "foreword":"卷首语",
    "The_knight_of_la_mancha":"拉曼却幻想",
    "The_weight_of_words":"文字，自始至终",
    "The_shackles_of_sin":"孽的锁链",
    "By_reflections_witnessed":"镜廊宣言",
    "Weighing_sin_and_justice":"称量罪与理",
    "Let_there_be_a_way_out":"天光照衣",
    "Blossom_spring_fairy":"壁上桃源",
    "Polyphony":"多重唱",
    "And_all_that_jazz":"爵士春秋",
    "The_last_fluttering_beat":"若向死振翅",
    "Reflections_within_reflections":"映像之映像",
    "Seminars_on_serenity":"心曲沙龙",
    "Guardian_of_the_broken":"时代病陪护",
    "The_gourmet_counselor":"镜中上校",
    "Measuring_the_world":"于此丈量",
    "Records_from_the_jade_hunt":"凿玉记",
    "The_nightmare's_trespasser":"魇与夜",
    "Silver_isoheight":"银色等高线",
}
ACTION_LABELS = {
    "sleep": "睡觉",
    "posture": "姿态",
    "special": "特殊动作",
    "born": "登场",
    "hit": "受击",
    "innate": "切换动作",
    "victory":"胜利",
    "idle_special":"待机特殊动作",
}


def _meta_label(path: str) -> str:
    try:
        with open(os.path.join(path, "char.json"), "r", encoding="utf-8") as f:
            return (json.load(f).get("label") or "").strip()
    except Exception:
        return ""


def _outfit_meta_label(path: str) -> str:
    try:
        with open(os.path.join(path, "meta.json"), "r", encoding="utf-8") as f:
            return (json.load(f).get("label") or "").strip()
    except Exception:
        return ""


def char_label(name: str) -> str:
    return _meta_label(os.path.join(ASSET_ROOT, name)) or CHAR_LABELS.get(name, name)


def outfit_label(char: str, name: str) -> str:
    return _outfit_meta_label(
        os.path.join(ASSET_ROOT, char, name)
    ) or OUTFIT_LABELS.get(name, name)


def action_label(name: str) -> str:
    if name in ACTION_LABELS:
        return ACTION_LABELS[name]
    if name.startswith("skill") and name[5:].isdigit():
        return f"技能 {name[5:]}"
    return name


def _split_paragraph(text: str, fm, width: int, max_lines: int = MAX_LINES):
    """先按句子切，整句能放下就整句；单句太长才按宽度硬切。"""
    sentences = []
    cur = ""
    for ch in text:
        cur += ch
        if ch in "。！？…":
            sentences.append(cur)
            cur = ""
    if cur:
        sentences.append(cur)

    parts = []
    cur = ""
    for s in sentences:
        cand = cur + s
        if cur and len(_wrap(cand, fm, width, 999)) > max_lines:
            parts.append(cur)
            cur = s
        else:
            cur = cand
    if cur:
        parts.append(cur)

    fixed = []
    for part in parts:
        if len(_wrap(part, fm, width, 999)) <= max_lines:
            fixed.append(part)
            continue
        buf = ""
        w = 0
        lines = 1
        for ch in part:
            cw = fm.horizontalAdvance(ch)
            if w + cw > width and buf:
                lines += 1
                w = 0
                if lines > max_lines:
                    fixed.append(buf)
                    buf = ""
                    lines = 1
            buf += ch
            w += cw
        if buf:
            fixed.append(buf)
    return fixed


class Pet(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.movies = {}
        self.char = resolve_char(SETTINGS.get("initial_char") or DEFAULT_CHAR)
        if not self.char:
            raise SystemExit("assets 下没有找到带服装目录的角色")
        self.outfit = resolve_outfit(
            self.char, SETTINGS.get("initial_outfit") or DEFAULT_OUTFIT
        )
        self.asset_dir = os.path.join(ASSET_ROOT, self.char, self.outfit)
        self.setWindowTitle(f"1999 桌宠 · {char_label(self.char)}")

        self.label = QLabel(self)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: transparent;")
        self.label.setScaledContents(True)

        self.bubble = Bubble(self)
        icon = app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)
            QApplication.setWindowIcon(icon)
        self._spawn_from_switch = False
        self._talk_queue = []
        self._lines_pool = []
        self._line_idx = 0
        self._load_lines()

        self._load_movies()

        # 先用 idle 的尺寸定窗口，避免第一帧还没解码时窗口是 0×0
        reader = QImageReader(os.path.join(self.asset_dir, "idle.webp"))
        sz = reader.size()
        w = max(1, int(sz.width() * SCALE)) if sz.isValid() else 307
        h = max(1, int(sz.height() * SCALE)) if sz.isValid() else 307
        # 不再给 QMovie 设 scaledSize（切动作时会被重置、导致“突然变大”），
        # 改成让 QLabel 把每一帧缩放到固定尺寸
        self.setFixedSize(w, h)
        self.label.setFixedSize(w, h)

        self.current_name = None
        self._oneshot_running = False
        self._press_pos = QPoint()
        self._dragging = False

        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self._fall_asleep)
        if AUTO_SLEEP:
            self.idle_timer.start(IDLE_SLEEP_MS)

        self.wake_timer = QTimer(self)
        self.wake_timer.setSingleShot(True)
        self.wake_timer.timeout.connect(self._wake_from_sleep)

        self._show_running = False
        self.show_timer = QTimer(self)
        self.show_timer.setSingleShot(True)
        self.show_timer.timeout.connect(self._maybe_show)
        if IDLE_SHOW_MS > 0:
            self.show_timer.start(IDLE_SHOW_MS)

        self._make_tray()
        if not ALWAYS_ON_TOP:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
        self._hidden_by_fullscreen = False
        self._drag_screen = None
        self._fs_timer = QTimer(self)
        self._fs_timer.setInterval(1000)
        self._fs_timer.timeout.connect(self._check_fullscreen)
        if HIDE_FULLSCREEN:
            self._fs_timer.start()
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(200)
        self._cursor_timer.timeout.connect(self._check_cursor)
        if CLICK_THROUGH_HIDDEN:
            self._cursor_timer.start()
        if "born" in self.movies:
            self.play("born", oneshot=True)   # 先登场，播完自动回 idle
        else:
            self.play("idle")
        self._place_bottom_right()

    # ---------- 播放 ----------
    def play(self, name: str, oneshot: bool = False):
        movie = self.movies.get(name)
        if movie is None:
            return
        # 单次动作正在播时，新的点击/右键不打断（避免重复播放）
        if oneshot and self._oneshot_running:
            return
        if self.current_name == name and not oneshot:
            return

        old = self.movies.get(self.current_name)
        if old is not None:
            old.stop()

        self.current_name = name
        movie.stop()
        movie.jumpToFrame(0)
        self._oneshot_running = oneshot
        self.label.setMovie(movie)
        movie.start()

    def _on_movie_frame(self, name: str, frame: int):
        # WebP 自带“无限循环”，finished 可能永远不来；到最后一帧就手动收尾
        if name != self.current_name or not self._oneshot_running:
            return
        m = self.movies.get(name)
        if m is not None and frame >= m.frameCount() - 1:
            QTimer.singleShot(40, self._finish_oneshot)

    def _on_movie_finished(self, name: str):
        if name == self.current_name and self._oneshot_running:
            self._finish_oneshot()

    def _finish_oneshot(self):
        if not self._oneshot_running:
            return
        was = self.current_name
        self._oneshot_running = False
        self.play("idle")
        if was == "born" and not self.bubble.isVisible():
            text = ""
            if getattr(self, "_first_meet", ""):
                text = self._first_meet
                self._first_meet = ""
                try:
                    marker = os.path.join(ASSET_ROOT, self.char, ".first_meet_done")
                    with open(marker, "w", encoding="utf-8") as f:
                        f.write("1")
                except Exception:
                    pass
            elif getattr(self, "_debut", ""):
                text = self._debut
            if text:
                self._talk_queue = _split_paragraph(text, self.bubble.fm, BUBBLE_W - PAD * 2)
                self._speak_next()
            self._spawn_from_switch = False
        if self._show_running:
            self._show_running = False
        elif AUTO_SLEEP:
            self.idle_timer.start(IDLE_SLEEP_MS)
        self._schedule_show()

    # ---------- 自己动一下 ----------
    def _schedule_show(self):
        if IDLE_SHOW_MS <= 0:
            return
        self.show_timer.start(IDLE_SHOW_MS)

    def _maybe_show(self):
        if (
            self.current_name != "idle"
            or self._oneshot_running
            or self._dragging
            or not self.isVisible()
            or getattr(self, "bubble", None) is not None and self.bubble.isVisible()
        ):
            self._schedule_show()
            return
        candidates = [
            n for n in self.movies
            if n not in LOOP_ACTIONS and n not in ("born", "hit")
        ]
        if not candidates:
            self._schedule_show()
            return
        # idle_special 作为“待机特殊动作”，出现概率稍高
        pool = list(candidates)
        if "idle_special" in pool:
            pool += ["idle_special"] * IDLE_SPECIAL_WEIGHT
        self._show_running = True
        self.play(random.choice(pool), oneshot=True)
        self._queue_talk(2)

    # ---------- 台词 ----------
    def _load_lines(self):
        self._lines_pool = []
        self._paras = []
        self._para_idx = 0
        self._line_idx = 0
        path = os.path.join(self.asset_dir, "lines.txt")
        if not os.path.exists(path):
            path = os.path.join(ASSET_ROOT, self.char, "lines.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if line:
                        chunks = _split_paragraph(line, self.bubble.fm, BUBBLE_W - PAD * 2)
                        if chunks:
                            self._paras.append(chunks)
                            self._lines_pool.extend(chunks)

        self._first_meet = ""
        fp = os.path.join(ASSET_ROOT, self.char, "first_meet.txt")
        marker = os.path.join(ASSET_ROOT, self.char, ".first_meet_done")
        if os.path.exists(fp) and not os.path.exists(marker):
            with open(fp, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                self._first_meet = text

        self._debut = ""
        dp = os.path.join(ASSET_ROOT, self.char, "debut.txt")
        if os.path.exists(dp):
            with open(dp, "r", encoding="utf-8") as f:
                self._debut = f.read().strip()

    def _next_line(self):
        if not self._lines_pool:
            return ""
        line = self._lines_pool[self._line_idx % len(self._lines_pool)]
        self._line_idx += 1
        return line

    def _queue_talk(self, count: int = 2):
        if getattr(self, "bubble", None) is None:
            return
        # 正在说话就别插队，免得把没念完的一句打断
        if self.bubble.isVisible():
            return
        self._talk_queue = []
        if not getattr(self, '_paras', None):
            return
        chunks = self._paras[self._para_idx % len(self._paras)]
        self._para_idx += 1
        self._talk_queue.extend(chunks)
        self._speak_next()

    def _speak_next(self):
        if not self._talk_queue:
            return
        line = self._talk_queue.pop(0)
        self.bubble.say(line, self._speak_next if self._talk_queue else None)

    def moveEvent(self, e):
        super().moveEvent(e)
        if getattr(self, "bubble", None) is not None and self.bubble.isVisible():
            self.bubble._place()

    # ---------- 睡觉 ----------
    def _fall_asleep(self):
        if not AUTO_SLEEP:
            return
        if self.current_name == "idle" and "sleep" in self.movies:
            self.idle_timer.stop()
            self.show_timer.stop()
            self.play("sleep")
            self.wake_timer.start(WAKE_MS)

    def _wake_from_sleep(self):
        if self.current_name == "sleep":
            self.play("idle")
            self._schedule_show()
        if AUTO_SLEEP:
            self.idle_timer.start(IDLE_SLEEP_MS)

    def _wake(self):
        self.wake_timer.stop()
        if self.current_name == "sleep":
            self.play("idle")
        if AUTO_SLEEP:
            self.idle_timer.start(IDLE_SLEEP_MS)
        self._schedule_show()

    # ---------- 角色 / 服装 ----------
    def _load_movies(self):
        for m in self.movies.values():
            m.stop()
        self.movies = {}
        for fn in os.listdir(self.asset_dir):
            if not fn.endswith(".webp"):
                continue
            path = os.path.join(self.asset_dir, fn)
            if os.path.getsize(path) == 0:
                continue
            name = fn[:-5]
            m = QMovie(path)
            m.setCacheMode(QMovie.CacheAll)
            m.finished.connect(lambda n=name: self._on_movie_finished(n))
            m.frameChanged.connect(lambda f, n=name: self._on_movie_frame(n, f))
            self.movies[name] = m
        if "idle" not in self.movies:
            alt = os.path.join(self.asset_dir, "idle_special.webp")
            if os.path.isfile(alt) and os.path.getsize(alt) > 0:
                m = QMovie(alt)
                m.setCacheMode(QMovie.CacheAll)
                m.finished.connect(lambda n="idle": self._on_movie_finished(n))
                m.frameChanged.connect(lambda f, n="idle": self._on_movie_frame(n, f))
                self.movies["idle"] = m
        if "idle" not in self.movies:
            raise SystemExit(f"找不到素材：{os.path.join(self.asset_dir, 'idle.webp')}")

    def _reload_assets(self):
        self._spawn_from_switch = True
        if getattr(self, 'bubble', None) is not None:
            self.bubble.stop()
        self._talk_queue = []
        self._load_lines()
        self.current_name = None
        self._oneshot_running = False
        self._load_movies()
        if "idle" in self.movies:
            # 用新素材的尺寸重定窗口
            reader = QImageReader(os.path.join(self.asset_dir, "idle.webp"))
            sz = reader.size()
            if sz.isValid():
                w = max(1, int(sz.width() * SCALE))
                h = max(1, int(sz.height() * SCALE))
                self.setFixedSize(w, h)
                self.label.setFixedSize(w, h)
        if "born" in self.movies:
            self.play("born", oneshot=True)
        else:
            self.play("idle")

    def _switch_char(self, name: str):
        if name == self.char:
            return
        outfits = list_outfits(name)
        if not outfits:
            return
        self.char = name
        self.outfit = "Default" if "Default" in outfits else outfits[0]
        self.asset_dir = os.path.join(ASSET_ROOT, name, self.outfit)
        self._reload_assets()

    def _switch_outfit(self, name: str):
        if name == self.outfit:
            return
        if not os.path.isdir(os.path.join(ASSET_ROOT, self.char, name)):
            return
        self.outfit = name
        self.asset_dir = os.path.join(ASSET_ROOT, self.char, name)
        self._reload_assets()

    # ---------- 位置 ----------
    def _place_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 40, screen.bottom() - self.height() - 40)

    # ---------- 鼠标 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._wake()
            self._schedule_show()
            if "posture" in self.movies:
                self.play("posture")
            self._press_pos = event.globalPosition().toPoint()
            self._drag_screen = self.screen()
            self._dragging = False
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            pos = event.globalPosition().toPoint()
            if not self._dragging and (pos - self._press_pos).manhattanLength() > 6:
                self._dragging = True
            if self._dragging:
                new_pos = self.pos() + pos - self._press_pos
                if not ALLOW_CROSS_SCREEN and self._drag_screen is not None:
                    area = self._drag_screen.availableGeometry()
                    if ALLOW_OFFSCREEN:
                        margin = 40
                        new_pos.setX(
                            max(
                                area.left() - self.width() + margin,
                                min(new_pos.x(), area.right() - margin),
                            )
                        )
                        new_pos.setY(
                            max(
                                area.top() - self.height() + margin,
                                min(new_pos.y(), area.bottom() - margin),
                            )
                        )
                    else:
                        new_pos.setX(
                            max(area.left(), min(new_pos.x(), area.right() - self.width()))
                        )
                        new_pos.setY(
                            max(area.top(), min(new_pos.y(), area.bottom() - self.height()))
                        )
                self.move(new_pos)
                self._press_pos = pos
                self.idle_timer.start(IDLE_SLEEP_MS)
                event.accept()

    def mouseReleaseEvent(self, event):
        was_drag = self._dragging
        if event.button() == Qt.LeftButton and not was_drag:
            self.play("hit", oneshot=True)
            self._queue_talk(2)
        elif event.button() == Qt.LeftButton and was_drag:
            self.play("idle")
        self._dragging = False
        event.accept()

    # ---------- 托盘 ----------
    def _make_tray(self):
        tray_icon = app_icon()
        if not tray_icon.isNull():
            pass
        else:
            tray_icon = QIcon(QPixmap(os.path.join(self.asset_dir, "idle.webp")))
        self.tray = QSystemTrayIcon(tray_icon, self)
        menu = QMenu()
        act_show = QAction("显示 / 隐藏", self)
        act_show.triggered.connect(lambda: self.setVisible(not self.isVisible()))
        act_reset = QAction("回到右下角", self)
        act_reset.triggered.connect(self._place_bottom_right)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(QApplication.quit)
        menu.addAction(act_show)
        menu.addAction(act_reset)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(f"1999 桌宠 · {char_label(self.char)}")
        self.tray.show()

    # ---------- 右键 ----------
    def contextMenuEvent(self, event):
        menu = QMenu(self)

        # 更换角色
        chars = list_characters()
        char_menu = menu.addMenu("更换角色")
        for c in chars:
            act = QAction(char_label(c) + (" ✓" if c == self.char else ""), self)
            act.triggered.connect(lambda _=False, n=c: self._switch_char(n))
            char_menu.addAction(act)
        if not chars:
            char_menu.setEnabled(False)

        # 更换服装
        outfits = list_outfits(self.char)
        outfit_menu = menu.addMenu("更换服装")
        for o in outfits:
            act = QAction(
                outfit_label(self.char, o) + (" ✓" if o == self.outfit else ""), self
            )
            act.triggered.connect(lambda _=False, n=o: self._switch_outfit(n))
            outfit_menu.addAction(act)
        if not outfits:
            outfit_menu.setEnabled(False)

        # 动作
        action_menu = menu.addMenu("动作")
        names = [n for n in self.movies if n != "idle"]
        order = ["sleep", "posture", "special", "born", "hit"]
        names.sort(key=lambda n: (order.index(n) if n in order else 99, n))
        for name in names:
            act = QAction(action_label(name), self)
            act.triggered.connect(
                lambda _=False, n=name: self._play_action(n)
            )
            action_menu.addAction(act)

        menu.addSeparator()
        act_settings = QAction("设置…", self)
        act_settings.triggered.connect(self._open_settings)
        menu.addAction(act_settings)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(QApplication.quit)
        menu.addAction(act_quit)
        menu.exec(event.globalPos())

    # ---------- 窗口行为 ----------
    def _play_action(self, name: str):
        self.play(name, oneshot=(name not in LOOP_ACTIONS))
        if name == "sleep":
            self.wake_timer.start(WAKE_MS)

    def _check_fullscreen(self):
        if not HIDE_FULLSCREEN or self._dragging:
            return
        try:
            fs = _foreground_fullscreen(int(self.winId()))
        except Exception:
            fs = False
        if fs:
            # 只在可见时因全屏而隐藏，避免把用户手动隐藏的状态改掉
            if self.isVisible() and not self._hidden_by_fullscreen:
                self._hidden_by_fullscreen = True
                self.hide()
        else:
            # 之前是被全屏藏起来的，退出全屏就恢复
            if self._hidden_by_fullscreen:
                self._hidden_by_fullscreen = False
                self.show()

    def _check_cursor(self):
        if not CLICK_THROUGH_HIDDEN:
            if self.testAttribute(Qt.WA_TransparentForMouseEvents):
                self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            return
        hidden = _cursor_hidden()
        if self.testAttribute(Qt.WA_TransparentForMouseEvents) != hidden:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, hidden)

    # ---------- 设置 ----------
    def _import_character(self, parent):
        known = {char_label(c): c for c in list_characters()}
        dlg = importer.ImportDialog(parent, ASSET_ROOT, known)
        if dlg.exec() == QDialog.Accepted and dlg.result_dir:
            folder = os.path.basename(dlg.result_dir)
            self._switch_char(folder)
            return folder
        return ""

    def _open_settings(self):
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return
        chars = list_characters()
        choices = {
            "characters": [(c, char_label(c)) for c in chars],
            "outfits": {
                c: [(o, outfit_label(c, o)) for o in list_outfits(c)] for c in chars
            },
        }
        self._settings_dlg = settings_ui.SettingsDialog(
            self, SETTINGS, self._apply_settings, choices, self._import_character
        )
        self._settings_dlg.show()

    def _apply_settings(self, data: dict):
        global SCALE, AUTO_SLEEP, IDLE_SLEEP_MS, IDLE_SHOW_MS
        SETTINGS.update(data)
        settings_ui.save(SETTINGS_PATH, SETTINGS)
        SCALE = float(data.get("scale", SCALE))
        bubble_mod.CHAR_MS = int(data.get("char_ms", bubble_mod.CHAR_MS))
        bubble_mod.HOLD_MS = int(data.get("hold_ms", bubble_mod.HOLD_MS))
        IDLE_SLEEP_MS = int(data.get("sleep_minutes", 3)) * 60 * 1000
        IDLE_SHOW_MS = int(data.get("show_seconds", 90)) * 1000
        AUTO_SLEEP = bool(data.get("auto_sleep", False))
        global WAKE_MS
        WAKE_MS = int(data.get("wake_minutes", 10)) * 60 * 1000
        if "autostart" in data:
            autostart.set_enabled(bool(data["autostart"]))
        if "always_on_top" in data:
            global ALWAYS_ON_TOP
            ALWAYS_ON_TOP = bool(data["always_on_top"])
            self.setWindowFlag(Qt.WindowStaysOnTopHint, ALWAYS_ON_TOP)
            if not self.isHidden():
                self.show()
        if "hide_fullscreen" in data:
            global HIDE_FULLSCREEN
            HIDE_FULLSCREEN = bool(data["hide_fullscreen"])
            if HIDE_FULLSCREEN:
                self._fs_timer.start()
            else:
                self._fs_timer.stop()
                if self._hidden_by_fullscreen:
                    self._hidden_by_fullscreen = False
                    self.show()
        if "click_through_hidden_cursor" in data:
            global CLICK_THROUGH_HIDDEN
            CLICK_THROUGH_HIDDEN = bool(data["click_through_hidden_cursor"])
            if CLICK_THROUGH_HIDDEN:
                self._cursor_timer.start()
            else:
                self._cursor_timer.stop()
                self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        if "allow_cross_screen" in data:
            global ALLOW_CROSS_SCREEN
            ALLOW_CROSS_SCREEN = bool(data["allow_cross_screen"])
        if "allow_offscreen" in data:
            global ALLOW_OFFSCREEN
            ALLOW_OFFSCREEN = bool(data["allow_offscreen"])
        # 初始桌宠：立即切换
        new_char = data.get("initial_char") or ""
        new_outfit = data.get("initial_outfit") or ""
        if new_char and new_char != self.char:
            self._switch_char(new_char)
        if new_outfit and new_outfit != self.outfit:
            self._switch_outfit(new_outfit)
        # 立即应用缩放
        reader = QImageReader(os.path.join(self.asset_dir, "idle.webp"))
        sz = reader.size()
        if sz.isValid():
            w = max(1, int(sz.width() * SCALE))
            h = max(1, int(sz.height() * SCALE))
            self.setFixedSize(w, h)
            self.label.setFixedSize(w, h)
        # 自动表演
        if IDLE_SHOW_MS > 0:
            self._schedule_show()
        else:
            self.show_timer.stop()
        # 自动睡觉
        if AUTO_SLEEP:
            self.idle_timer.start(IDLE_SLEEP_MS)
        else:
            self.idle_timer.stop()

    def _go_sleep(self):
        if "sleep" in self.movies:
            self.idle_timer.stop()
            self.play("sleep")


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = Pet()
    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
