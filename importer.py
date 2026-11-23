# -*- coding: utf-8 -*-
"""导入用户自备的角色素材（文件夹或 zip，zip 直接流式读取不解压到临时目录）。"""

import json
import os
import shutil
import zipfile
import zlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

IDLE_NAMES = ("idle.webp", "idle_special.webp")


def _is_idle(name: str) -> bool:
    return name.rsplit("/", 1)[-1].lower() in IDLE_NAMES


def _scan_zip(path: str) -> dict:
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if _is_idle(n)]
    if not names:
        return {"zip": path, "char": os.path.splitext(os.path.basename(path))[0], "outfits": []}
    dirs = sorted({n.rsplit("/", 1)[0] for n in names})
    parents = {d.rsplit("/", 1)[0] if "/" in d else "" for d in dirs}
    if len(parents) == 1:
        parent = parents.pop()
        char = parent.rsplit("/", 1)[-1] if parent else os.path.splitext(
            os.path.basename(path)
        )[0]
    else:
        char = os.path.splitext(os.path.basename(path))[0]
    outfits = []
    for d in dirs:
        folder = d.rsplit("/", 1)[-1]
        outfits.append({"kind": "zip", "zip": path, "prefix": d + "/", "folder": folder})
    return {"zip": path, "char": char, "outfits": outfits}


def scan_source(path: str) -> dict:
    if path.lower().endswith(".zip"):
        return _scan_zip(path)

    if any(os.path.isfile(os.path.join(path, n)) for n in IDLE_NAMES):
        folder = os.path.basename(os.path.abspath(path))
        return {
            "char": folder,
            "outfits": [{"kind": "dir", "path": os.path.abspath(path), "folder": folder}],
        }

    outfits = []
    for name in sorted(os.listdir(path)):
        sub = os.path.join(path, name)
        if os.path.isdir(sub) and any(
            os.path.isfile(os.path.join(sub, n)) for n in IDLE_NAMES
        ):
            outfits.append({"kind": "dir", "path": os.path.abspath(sub), "folder": name})
    return {"char": os.path.basename(os.path.abspath(path)), "outfits": outfits}


def _existing_labels(assets_root: str) -> dict:
    labels = {}
    if not os.path.isdir(assets_root):
        return labels
    for name in os.listdir(assets_root):
        path = os.path.join(assets_root, name)
        if not os.path.isdir(path):
            continue
        label = name
        try:
            with open(os.path.join(path, "char.json"), "r", encoding="utf-8") as f:
                label = (json.load(f).get("label") or name).strip()
        except Exception:
            pass
        labels[label] = name
    return labels


def _unique_dir(base: str) -> str:
    idx = 2
    while True:
        cand = f"{base}_{idx}"
        if not os.path.exists(cand):
            return cand
        idx += 1


def _copy_outfit(outfit: dict, target: str) -> None:
    os.makedirs(target, exist_ok=True)
    if outfit["kind"] == "dir":
        shutil.copytree(outfit["path"], target, dirs_exist_ok=True)
        return
    prefix = outfit["prefix"]
    with zipfile.ZipFile(outfit["zip"]) as z:
        for info in z.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            rel = info.filename[len(prefix):]
            if not rel or ".." in rel:
                continue
            dest = os.path.join(target, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(info) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)


def do_import(assets_root: str, char_folder: str, char_label: str, outfits, mode: str) -> str:
    """outfits: [(outfit_dict, 中文名)]；mode: overwrite / rename / cancel。"""
    dest = os.path.join(assets_root, char_folder)
    if os.path.exists(dest):
        if mode == "cancel":
            return ""
        if mode == "overwrite":
            shutil.rmtree(dest)
        else:
            dest = _unique_dir(dest)
    os.makedirs(dest, exist_ok=True)

    for outfit, label in outfits:
        target = os.path.join(dest, outfit["folder"])
        _copy_outfit(outfit, target)
        with open(os.path.join(target, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"label": label}, f, ensure_ascii=False, indent=2)

    with open(os.path.join(dest, "char.json"), "w", encoding="utf-8") as f:
        json.dump({"label": char_label, "source": "imported"}, f, ensure_ascii=False, indent=2)
    return dest


class ImportDialog(QDialog):
    def __init__(self, parent, assets_root: str, known_labels=None):
        super().__init__(parent)
        self.assets_root = assets_root
        self._known = dict(known_labels or {})
        self._info = None
        self.result_dir = ""

        self.setWindowTitle("导入角色")
        self.setAcceptDrops(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.resize(620, 520)
        self.setStyleSheet(
            "QDialog{background:#1b1c21;color:#e6e6ea;}"
            "QLabel{color:#e6e6ea;}"
            "QLineEdit{background:#2c2d34;border:1px solid #3a3b43;border-radius:6px;padding:5px;color:#fff;}"
            "QTableWidget{background:#232429;color:#e6e6ea;gridline-color:#3a3b43;border:none;}"
            "QHeaderView::section{background:#2c2d34;color:#c9c9d1;border:none;padding:4px;}"
            "QPushButton{background:#2c2d34;border:1px solid #3a3b43;border-radius:6px;padding:6px 12px;color:#fff;}"
            "QComboBox{background:#2c2d34;border:1px solid #3a3b43;border-radius:6px;padding:4px;color:#fff;}"
        )

        root = QVBoxLayout(self)

        pick = QHBoxLayout()
        btn_dir = QPushButton("选择文件夹…")
        btn_zip = QPushButton("选择 zip…")
        btn_dir.clicked.connect(self._pick_dir)
        btn_zip.clicked.connect(self._pick_zip)
        pick.addWidget(btn_dir)
        pick.addWidget(btn_zip)
        pick.addStretch(1)
        root.addLayout(pick)

        self.info = QLabel(
            "选择一个角色素材文件夹 / zip，或把文件夹、zip 直接拖进窗口。"
        )
        self.info.setWordWrap(True)
        root.addWidget(self.info)

        root.addWidget(QLabel("角色中文名"))
        self.name_edit = QLineEdit()
        root.addWidget(self.name_edit)

        root.addWidget(QLabel("服装（可改成中文名）"))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["文件夹", "中文名"])
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        self.conflict_box = QComboBox()
        self.conflict_box.addItems(["覆盖现有角色", "改名导入（加后缀）", "取消"])
        self.conflict_box.setVisible(False)
        root.addWidget(self.conflict_box)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._drag = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.info.setText("松手即可导入…")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        if self._info is None:
            self.info.setText(
                "选择一个角色素材文件夹 / zip，或把文件夹、zip 直接拖进窗口。"
            )
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        path = paths[0]
        if len(paths) > 1:
            QMessageBox.information(self, "只导入一个", "一次拖一个角色就好，已使用第一个。")
        if os.path.isdir(path) or path.lower().endswith(".zip"):
            self._load(path)
        else:
            QMessageBox.warning(self, "不支持", "请拖文件夹或 zip。")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag = None
        super().mouseReleaseEvent(event)

    def _pick_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择角色素材文件夹")
        if path:
            self._load(path)

    def _pick_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 zip", "", "Zip (*.zip)")
        if path:
            self._load(path)

    def _load(self, path: str):
        try:
            info = scan_source(path)
        except (OSError, zipfile.BadZipFile, zlib.error) as exc:
            QMessageBox.warning(self, "导入失败", f"读不了这个素材：{exc}")
            return
        if not info["outfits"]:
            QMessageBox.warning(self, "导入失败", "没找到含 idle.webp 的服装目录。")
            return
        self._info = info
        self.name_edit.setText(info["char"])
        self.table.setRowCount(len(info["outfits"]))
        for row, outfit in enumerate(info["outfits"]):
            folder = outfit["folder"]
            name_item = QTableWidgetItem(folder)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(folder))
        exists = os.path.exists(os.path.join(self.assets_root, info["char"]))
        self.conflict_box.setVisible(exists)
        self.info.setText(
            f"来源：{os.path.basename(path)}\n"
            f"角色目录：{info['char']}，服装 {len(info['outfits'])} 套"
            + ("\n已存在同名角色，请选择处理方式。" if exists else "")
        )

    def _accept(self):
        if not self._info:
            QMessageBox.warning(self, "还没选素材", "先选文件夹或 zip。")
            return
        char_label = self.name_edit.text().strip()
        if not char_label:
            QMessageBox.warning(self, "缺名字", "给角色填个中文名。")
            return
        labels = _existing_labels(self.assets_root)
        labels.update(self._known)
        other = labels.get(char_label)
        if other and other != self._info["char"]:
            QMessageBox.warning(
                self,
                "名字重复",
                f"已经有叫「{char_label}」的角色了（{other}），换个名字。",
            )
            return
        outfits = []
        for row, outfit in enumerate(self._info["outfits"]):
            item = self.table.item(row, 1)
            label = (item.text() if item else "").strip() or outfit["folder"]
            outfits.append((outfit, label))
        exists = os.path.exists(os.path.join(self.assets_root, self._info["char"]))
        mode = "overwrite"
        if exists:
            mode = {0: "overwrite", 1: "rename", 2: "cancel"}[
                self.conflict_box.currentIndex()
            ]
            if mode == "cancel":
                return
            if mode == "overwrite":
                ok = QMessageBox.question(
                    self,
                    "确认覆盖",
                    "会删掉现有同名角色（包括它的台词和初遇记录），继续？",
                )
                if ok != QMessageBox.Yes:
                    return
        try:
            self.result_dir = do_import(
                self.assets_root, self._info["char"], char_label, outfits, mode
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        super().accept()
