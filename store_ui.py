# -*- coding: utf-8 -*-
"""存物品界面：拍照 → 自动识别物品 → 选择/更正类别 → 上传服务端 → 开柜。"""

import os

import tkinter as tk
from tkinter import ttk, messagebox
import requests

import config
import item_recognizer
import network_manager
import open_lock
import photo_manager

CATEGORY_CHOICES = list(item_recognizer.TARGET_CLASSES.values()) + [item_recognizer.UNKNOWN_LABEL_CN]


class StoreUI:
    """存物品界面及逻辑"""

    def __init__(self, parent_app):
        self.parent = parent_app  # 主应用实例，用于切换界面
        self.root = parent_app.root
        self.recognition = None           # 最近一次识别结果
        self.photo_label = None
        self.result_label = None
        self.category_var = None

    # ------------------------------------------------------------ 界面
    def show(self):
        """显示存物品主界面（拍照、识别结果、类别选择）"""
        self._clear_window()
        self.recognition = None

        # 清掉上一次的暂存照片，避免误存旧照片
        stale = photo_manager.temp_photo_path()
        if os.path.exists(stale):
            try:
                os.remove(stale)
            except OSError:
                pass

        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)

        # 滚动条支持
        canvas = tk.Canvas(main_frame, bg='#f0f0f0')
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f0f0f0')
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 返回按钮
        back_btn = tk.Button(scrollable_frame, text="返回", bg='#CCCCCC', font=('微软雅黑', 10), width=8,
                             command=self.parent.show_main_interface)
        back_btn.grid(row=0, column=0, sticky='nw', pady=(0, 20))

        tk.Label(scrollable_frame, text="存放物品", bg='#f0f0f0',
                 font=('微软雅黑', 18, 'bold')).grid(row=1, column=0, sticky='w', pady=(0, 10))

        start_row = 2
        if item_recognizer.get_recognizer() is not None and config.ENABLE_RECOGNITION:
            tk.Label(scrollable_frame,
                     text="拍照后会自动识别物品；若识别有误，可在下拉框中更正。",
                     bg='#f0f0f0', fg='#666666', font=('微软雅黑', 10)).grid(
                row=start_row, column=0, sticky='w', pady=(0, 12))
        else:
            tk.Label(scrollable_frame,
                     text="未加载识别模型或识别已关闭，拍照后请手动选择物品类别。",
                     bg='#f0f0f0', fg='#C62828', font=('微软雅黑', 10)).grid(
                row=start_row, column=0, sticky='w', pady=(0, 12))

        # 拍照按钮
        photo_btn = tk.Button(scrollable_frame, text="拍照", bg='#2196F3', fg='white',
                              font=('微软雅黑', 12, 'bold'), width=10, height=2,
                              command=self._take_photo_wrapper)
        photo_btn.grid(row=3, column=0, sticky='w', pady=(10, 10))

        # 照片预览区域
        preview_frame = tk.Frame(scrollable_frame, bg='#f0f0f0')
        preview_frame.grid(row=4, column=0, sticky='w', pady=(0, 16))
        tk.Label(preview_frame, text="照片预览:", bg='#f0f0f0',
                 font=('微软雅黑', 10)).pack(anchor='w', pady=(0, 5))
        self.photo_label = tk.Label(preview_frame, text="暂无照片", bg='#e0e0e0',
                                    relief='solid', borderwidth=1)
        self.photo_label.pack(anchor='w')

        # 识别结果区域
        result_frame = tk.Frame(scrollable_frame, bg='#f0f0f0')
        result_frame.grid(row=5, column=0, sticky='w', pady=(0, 16))

        tk.Label(result_frame, text="识别结果:", bg='#f0f0f0',
                 font=('微软雅黑', 10)).grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.result_label = tk.Label(result_frame, text="等待拍照…", bg='#f0f0f0',
                                     fg='#666666', font=('微软雅黑', 14, 'bold'))
        self.result_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 10))

        tk.Label(result_frame, text="物品类别（可更正）:", bg='#f0f0f0',
                 font=('微软雅黑', 10)).grid(row=2, column=0, sticky='w', pady=(0, 5))
        self.category_var = tk.StringVar(value=item_recognizer.UNKNOWN_LABEL_CN)
        self.category_box = ttk.Combobox(result_frame, textvariable=self.category_var,
                                         values=CATEGORY_CHOICES, state='readonly', width=16,
                                         font=('微软雅黑', 12))
        self.category_box.grid(row=3, column=0, sticky='w')

        # 存物品按钮
        next_btn = tk.Button(scrollable_frame, text="存物品", bg='#4CAF50', fg='white',
                             font=('微软雅黑', 12, 'bold'), width=10,
                             command=self._next_step)
        next_btn.grid(row=6, column=0, sticky='w', pady=(16, 0))

    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # ------------------------------------------------------------ 拍照 / 识别
    def _take_photo_wrapper(self):
        captured, result = photo_manager.capture_item_photo()
        if not captured:
            return
        self.recognition = result
        photo_manager.show_photo_preview(self.photo_label, photo_manager.temp_photo_path())
        self.result_label.config(text="识别中…", fg='#666666')
        self.root.update_idletasks()
        self._update_recognition_ui()

    def _update_recognition_ui(self):
        if not config.ENABLE_RECOGNITION:
            self.result_label.config(text="物品识别已关闭，请手动选择类别", fg='#C62828')
            return
        if item_recognizer.get_recognizer() is None:
            self.result_label.config(text="未加载识别模型，请手动选择类别", fg='#C62828')
            return

        result = self.recognition
        if result:
            self.result_label.config(
                text="已识别：%s（置信度 %.0f%%）" % (result['label_cn'], result['score'] * 100),
                fg='#2E7D32',
            )
            self.category_var.set(result['label_cn'])
        else:
            self.result_label.config(text="未识别到常见物品，请手动选择类别", fg='#C62828')
            self.category_var.set(item_recognizer.UNKNOWN_LABEL_CN)

    # ------------------------------------------------------------ 存物
    def _next_step(self):
        temp_photo = photo_manager.temp_photo_path()
        if not os.path.exists(temp_photo):
            messagebox.showwarning("输入错误", "请先拍照！")
            return

        category = self.category_var.get() if self.category_var else item_recognizer.UNKNOWN_LABEL_CN
        confidence = self.recognition['score'] if self.recognition else None

        # 从服务端获取柜子状态
        try:
            lockers = network_manager.get_lockers_status()
        except requests.exceptions.RequestException:
            messagebox.showerror("网络错误", "无法连接至服务器，请检查网络连接")
            return

        free_lock = None
        for lid, info in lockers.items():
            if info['status'] == 0:
                free_lock = lid
                break
        if free_lock is None:
            messagebox.showerror("无空闲柜子", "当前没有空闲柜子，请稍后再试。")
            return

        self._confirm_store(free_lock, temp_photo, category, confidence)

    def _confirm_store(self, locker_id, temp_photo_path, category, confidence):
        detail = "物品：%s" % category
        if self.recognition:
            detail += "（自动识别 %s，置信度 %.0f%%）" % (
                self.recognition['label_cn'], self.recognition['score'] * 100)
        confirm = messagebox.askyesno(
            "确认存放",
            "确认将物品存放至 %s 号柜吗？\n\n%s" % (locker_id, detail),
        )
        if not confirm:
            return

        try:
            result = network_manager.store_item(
                locker_id, temp_photo_path,
                category=category, confidence=confidence,
            )
            open_lock.open_lock(lock_number=locker_id)
            messagebox.showinfo(
                "操作成功",
                "正在打开 %s 号柜...\n\n物品存放成功！\n物品类别：%s" % (locker_id, category),
            )
            self.parent.show_main_interface()
        except requests.exceptions.RequestException:
            messagebox.showerror("网络错误", "无法连接至服务器，请检查网络连接")
        except Exception as e:
            messagebox.showerror("错误", "存物失败：%s" % e)
