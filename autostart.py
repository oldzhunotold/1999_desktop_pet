# -*- coding: utf-8 -*-
"""Windows 开机自启：写 HKCU Run 键。"""

import os
import sys

try:
    import winreg
except ImportError:  # 非 Windows
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "1999DesktopPet"


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "main_qmovie.py")
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.isfile(pyw) else sys.executable
    return f'"{exe}" "{script}"'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
