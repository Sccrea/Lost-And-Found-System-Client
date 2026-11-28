# -*- coding: utf-8 -*-
"""内嵌模态框：在主窗口里画一层遮罩 + 卡片，替代系统 messagebox。

为什么不用 messagebox：它是独立窗口，在 Wayland/触屏上会出现"不居中、被主窗口顶到后面、
点不到"的问题。这里全部画在主窗口内部，按钮也做得足够大，手能点中。
"""

import tkinter as tk

import config


_PALETTE = {
    "info": ("#4a90e2", "#eef6ff"),
    "ok": ("#2e9e5b", "#eafaf0"),
    "error": ("#d64545", "#fdeeee"),
    "question": ("#4a90e2", "#eef6ff"),
}


def _timeout_seconds():
    return float(getattr(config, "PREVIEW_IDLE_TIMEOUT_SEC", 30))


class Dialog:
    """主窗口内的模态遮罩层。"""

    def __init__(self, root, title, message, buttons, kind="info", timeout=None, on_close=None):
        self.root = root
        self.on_close = on_close
        self.closed = False

        accent, tint = _PALETTE.get(kind, _PALETTE["info"])

        self.overlay = tk.Frame(root, bg="#0b1220")
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.overlay.lift()

        width = max(int(root.winfo_width() * 0.72), 560)
        card = tk.Frame(self.overlay, bg="#ffffff")
        card.place(relx=0.5, rely=0.5, anchor="center", width=width)

        header = tk.Frame(card, bg=accent, height=8)
        header.pack(fill="x")

        tk.Label(card, text=title, bg="#ffffff", fg=accent,
                 font=('微软雅黑', 26, 'bold')).pack(pady=(28, 10), padx=30)

        tk.Label(card, text=message, bg="#ffffff", fg="#333333",
                 font=('微软雅黑', 18), wraplength=int(width * 0.86),
                 justify="center").pack(pady=(0, 26), padx=30)

        row = tk.Frame(card, bg="#ffffff")
        row.pack(pady=(0, 28))
        for index, (text, value) in enumerate(buttons):
            primary = (index == 0)
            btn = tk.Button(
                row, text=text,
                bg=(accent if primary else "#e2e8f0"),
                fg=("#ffffff" if primary else "#334155"),
                font=('微软雅黑', 24, 'bold'), bd=0, width=10, height=1,
                activebackground=(accent if primary else "#cbd5e1"),
                activeforeground=("#ffffff" if primary else "#334155"),
                command=lambda v=value: self.close(v),
            )
            btn.pack(side="left", padx=14)

        self._timer = None
        if timeout is None:
            timeout = _timeout_seconds()
        if timeout and timeout > 0:
            self._timer = self.root.after(int(timeout * 1000), self._on_timeout)

    def _on_timeout(self):
        # 超时按默认（第一个）按钮处理
        self.close(getattr(self, "default_value", True))

    def close(self, value=True):
        if self.closed:
            return
        self.closed = True
        try:
            if self._timer is not None:
                self.root.after_cancel(self._timer)
        except Exception:
            pass
        try:
            self.overlay.destroy()
        except tk.TclError:
            pass
        if self.on_close:
            self.on_close(value)


def show(root, title, message, buttons=None, kind="info", timeout=None, on_close=None):
    """显示内嵌模态框；点按钮/超时后回调 on_close(按钮值)。"""
    buttons = buttons or [("确定", True)]
    dialog = Dialog(root, title, message, buttons, kind=kind, timeout=timeout, on_close=on_close)
    dialog.default_value = buttons[-1][1] if len(buttons) > 1 else buttons[0][1]
    return dialog


def info(root, title, message, on_close=None, timeout=None):
    return show(root, title, message, [("确定", True)], kind="ok", timeout=timeout, on_close=on_close)


def error(root, title, message, on_close=None, timeout=None):
    return show(root, title, message, [("确定", True)], kind="error", timeout=timeout, on_close=on_close)


def confirm(root, title, message, on_yes=None, on_no=None, timeout=None):
    """确认框：默认按钮是「取消」，避免手滑开锁/退出。"""
    def handle(value):
        if value and on_yes:
            on_yes()
        elif not value and on_no:
            on_no()

    return show(root, title, message,
                [("确认", True), ("取消", False)], kind="question",
                timeout=timeout, on_close=handle)
