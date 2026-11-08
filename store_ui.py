# -*- coding: utf-8 -*-
"""存物品：全自动一步到位。

用户点「存物品」后不再需要任何操作：
    打开摄像头 → 实时识别 → 识别到物品立刻裁剪保存 → 上传服务端 → 开锁 → 提示开锁成功
异常情况（无摄像头 / 未识别到物品 / 网络错误 / 无空闲柜）会给出明确提示并返回主界面。
"""

import os

import tkinter as tk
from tkinter import messagebox
import requests

import config
import item_recognizer
import network_manager
import open_lock
import photo_manager


class StoreUI:
    """存物品界面及逻辑（自动识别 + 自动开锁）"""

    def __init__(self, parent_app):
        self.parent = parent_app
        self.root = parent_app.root

    # ------------------------------------------------------------ 入口
    def show(self):
        """点击「存物品」后立即打开摄像头开始识别。"""
        self._clear_window()
        self._show_progress("正在打开摄像头…", "请把物品朝向镜头")
        # 先让界面画出来，再进入阻塞的摄像头循环
        self.root.after(60, self._run_auto_flow)

    # ------------------------------------------------------------ 界面
    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def _show_progress(self, text, sub=None):
        """全屏状态提示（等待摄像头时使用）。"""
        self._clear_window()
        frame = tk.Frame(self.root, bg='#f0f0f0')
        frame.pack(expand=True, fill='both')
        tk.Label(frame, text=text, bg='#f0f0f0', fg='#333333',
                 font=('微软雅黑', 28, 'bold')).pack(expand=True)
        if sub:
            tk.Label(frame, text=sub, bg='#f0f0f0', fg='#666666',
                     font=('微软雅黑', 16)).pack(pady=(0, 40))
        self.root.update_idletasks()

    def _back_to_main(self, delay=0):
        if delay:
            self.root.after(delay, self.parent.show_main_interface)
        else:
            self.parent.show_main_interface()

    # ------------------------------------------------------------ 主流程
    def _run_auto_flow(self):
        # 1) 打开摄像头 + 识别 + 裁剪保存
        result = photo_manager.capture_item_auto()
        status = result.get("status")

        if status == "cancelled":
            self._back_to_main()
            return

        if status == "no_item":
            messagebox.showwarning(
                "未识别到物品",
                "没有在画面中识别到可存放的物品。\n\n"
                "支持：背包、手提包、行李箱、瓶子、杯子、手机、书本。\n"
                "请将物品放正、靠近镜头后重试。",
            )
            self._back_to_main()
            return

        if status == "camera_error":
            messagebox.showerror("摄像头异常", result.get("detail", "无法打开摄像头"))
            self._back_to_main()
            return

        item = result["item"]
        photo_path = result["path"]
        category = item["label_cn"]
        confidence = item["score"]

        # 2) 找空闲柜
        self._show_progress("正在存放…", "%s  %.0f%%" % (category, confidence * 100))
        try:
            lockers = network_manager.get_lockers_status()
        except requests.exceptions.RequestException:
            messagebox.showerror("网络错误", "无法连接至服务器，请检查网络连接")
            self._back_to_main()
            return

        free_lock = None
        for lid, info in sorted(lockers.items()):
            if info.get("status") == 0:
                free_lock = lid
                break
        if free_lock is None:
            messagebox.showerror("无空闲柜子", "当前没有空闲柜子，请稍后再试。")
            self._back_to_main()
            return

        # 3) 上传裁剪后的物品图 + 识别结果
        try:
            network_manager.store_item(
                free_lock, photo_path,
                category=category, confidence=confidence,
            )
        except requests.exceptions.RequestException:
            messagebox.showerror("网络错误", "无法连接至服务器，物品未存入，请检查网络连接")
            self._back_to_main()
            return
        except Exception as exc:
            messagebox.showerror("存物失败", "上传物品信息失败：%s" % exc)
            self._back_to_main()
            return

        # 4) 直接开锁（不做二次确认）
        lock_error = None
        try:
            open_lock.open_lock(lock_number=free_lock)
        except Exception as exc:
            lock_error = exc

        # 5) 返回结果
        if lock_error is not None:
            messagebox.showerror(
                "开锁失败",
                "物品已登记到 %s 号柜，但柜门未能打开：%s\n\n"
                "请联系管理员处理（检查电锁与串口配置）。" % (free_lock, lock_error),
            )
        else:
            messagebox.showinfo(
                "开锁成功",
                "%s 号柜已打开\n\n物品：%s（置信度 %.0f%%）\n"
                "请将物品放入柜中并关好柜门。" % (free_lock, category, confidence * 100),
            )
        self._back_to_main()
