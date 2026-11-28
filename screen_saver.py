# -*- coding: utf-8 -*-
"""空闲熄屏：30 秒无操作就把显示屏关掉（保护屏幕），一触摸就亮。

树莓派（labwc/Wayland）用 wlopm 控制输出电源；Windows 用 SC_MONITORPOWER。
同时铺一层纯黑遮罩，既保证"黑屏"，也顺手吞掉唤醒的那一下点击，不会误触按钮。
"""

import os
import platform
import subprocess
import time

import tkinter as tk

_WINDOWS = platform.system() == "Windows"


def _wayland_env():
    env = dict(os.environ)
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % uid)
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    return env


def detect_output():
    """返回第一个 Wayland 输出名，例如 HDMI-A-1。"""
    try:
        out = subprocess.run(["wlopm"], capture_output=True, text=True,
                             timeout=5, env=_wayland_env())
        for line in (out.stdout or "").splitlines():
            parts = line.split()
            if parts:
                return parts[0]
    except Exception:
        pass
    return "HDMI-A-1"


def set_display_power(on):
    """打开/关闭显示屏。"""
    if _WINDOWS:
        try:
            import ctypes

            HWND_BROADCAST = 0xFFFF
            WM_SYSCOMMAND = 0x0112
            SC_MONITORPOWER = 0xF170
            ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND,
                                              SC_MONITORPOWER, 2 if not on else -1)
        except Exception:
            pass
        return

    output = detect_output()
    env = _wayland_env()
    for args in (["wlopm", "--on" if on else "--off", output],
                 ["wlr-randr", "--output", output, "--on" if on else "--off"]):
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=8, env=env)
            if result.returncode == 0:
                return
        except Exception:
            continue


class ScreenSaver:
    """空闲自动熄屏 + 触摸唤醒。"""

    def __init__(self, root, idle_seconds=30, on_before_sleep=None, enabled=True):
        self.root = root
        self.idle_seconds = float(idle_seconds)
        self.on_before_sleep = on_before_sleep
        self.enabled = enabled
        self.last_activity = time.time()
        self.off = False
        self.overlay = None

        # 启动时确保屏幕是亮的（避免上次异常退出把屏幕留在关闭状态）
        if self.enabled:
            set_display_power(True)

        root.bind_all("<Button-1>", self._on_activity, add="+")
        root.bind_all("<Key>", self._on_activity, add="+")
        root.after(1000, self._tick)

    # ------------------------------------------------------------ 计时
    def _on_activity(self, _event=None):
        self.last_activity = time.time()
        if self.off:
            self.wake()

    def _tick(self):
        try:
            if not self.off and time.time() - self.last_activity >= self.idle_seconds:
                self.sleep()
        except Exception:
            pass
        try:
            self.root.after(1000, self._tick)
        except tk.TclError:
            pass

    # ------------------------------------------------------------ 熄灭 / 唤醒
    def sleep(self):
        if self.off:
            return
        self.off = True
        if self.on_before_sleep:
            try:
                self.on_before_sleep()
            except Exception:
                pass
        self._show_overlay()
        self.root.update_idletasks()
        if self.enabled:
            set_display_power(False)

    def wake(self):
        if not self.off:
            return
        self.off = False
        if self.enabled:
            set_display_power(True)
        self._hide_overlay()
        self.last_activity = time.time()

    # ------------------------------------------------------------ 黑屏遮罩
    def _show_overlay(self):
        if self.overlay is not None:
            try:
                self.overlay.lift()
                return
            except tk.TclError:
                self.overlay = None
        self.overlay = tk.Frame(self.root, bg="black")
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.overlay.lift()
        # 点任意位置都只负责唤醒
        self.overlay.bind("<Button-1>", lambda _e: self.wake())

    def _hide_overlay(self):
        if self.overlay is not None:
            try:
                self.overlay.destroy()
            except tk.TclError:
                pass
            self.overlay = None

    def shutdown(self):
        """退出前把屏幕恢复，避免黑屏留在现场。"""
        self.off = False
        self._hide_overlay()
        if self.enabled:
            set_display_power(True)
