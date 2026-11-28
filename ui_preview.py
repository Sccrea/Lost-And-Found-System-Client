# -*- coding: utf-8 -*-
"""把摄像头画面嵌进 Tk 主窗口（替代 cv2.imshow 独立窗口）。

之前用 cv2.imshow 会弹出一个独立窗口：不居中、点主程序还会把它顶到后面。
这里改成在主窗口内铺满一层预览层（Canvas 居中绘制），ESC 取消，
退出时销毁该层恢复原界面。
"""

import tkinter as tk

import cv2
from PIL import Image, ImageTk


def bgr_to_photo(bgr, max_w, max_h):
    """把 BGR 帧等比缩放到 (max_w, max_h) 内并转成 PhotoImage。"""
    h, w = bgr.shape[:2]
    if w <= 0 or h <= 0:
        return None
    scale = min(max_w / float(w), max_h / float(h), 1.0)   # 只缩小，不放大
    if scale <= 0:
        return None
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    if (new_w, new_h) != (w, h):
        bgr = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return ImageTk.PhotoImage(Image.fromarray(rgb))


class CameraPreview:
    """主窗口内的全屏预览层（Canvas 居中显示画面 + 底部提示）。"""

    def __init__(self, root, title=""):
        self.root = root
        self.container = tk.Frame(root, bg='#101010')
        self.container.pack(expand=True, fill='both')

        if title:
            tk.Label(self.container, text=title, bg='#101010', fg='#DDDDDD',
                     font=('微软雅黑', 14)).pack(fill='x', pady=(10, 6))

        self.canvas = tk.Canvas(self.container, bg='#101010', highlightthickness=0)
        self.canvas.pack(expand=True, fill='both')

        self._photo = None
        self._hint = ""

    def _size(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 100 or h < 100:      # 还没完成布局
            w = max(self.root.winfo_width(), 640)
            h = max(self.root.winfo_height() - 80, 480)
        return w, h

    def update_frame(self, bgr, hint=None):
        if hint is not None:
            self._hint = hint
        w, h = self._size()

        self.canvas.delete("all")
        if bgr is not None:
            photo = bgr_to_photo(bgr, w, h)
            if photo is not None:
                self._photo = photo
                self.canvas.create_image(w // 2, h // 2, image=photo, anchor="center")

        if self._hint:
            self.canvas.create_text(w // 2, h - 24, text=self._hint, anchor="center",
                                    fill="#FFFFFF", font=('微软雅黑', 16, 'bold'))

    def close(self):
        try:
            self.container.destroy()
        except tk.TclError:
            pass
