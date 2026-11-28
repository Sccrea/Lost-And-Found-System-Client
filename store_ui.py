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
import ui_dialog


class StoreUI:
    """存物品界面及逻辑（自动识别 + 自动开锁）"""

    def __init__(self, parent_app):
        self.parent = parent_app
        self.root = parent_app.root

    # ------------------------------------------------------------ 入口
    def show(self):
        """点击「存物品」后立即打开摄像头开始识别。"""
        self.parent.current_view = "store"
        self._clear_window()
        self._show_progress("正在打开摄像头…", "请把物品朝向镜头")
        # 先让状态页画出来，再清空窗口启动（非阻塞的）内嵌预览
        self.root.after(120, self._start_preview)

    def _start_preview(self):
        self._clear_window()
        photo_manager.capture_item_auto(self.root, self._on_capture_done)

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
    def _on_capture_done(self, result):
        status = result.get("status")

        if status in ("cancelled", "timeout"):
            # 触屏：点「取消」或 30 秒无操作/未识别，都直接回主界面，不弹框挡路
            self._back_to_main()
            return

        if status == "no_item":
            self._back_to_main()
            return

        if status == "camera_error":
            self._alert("摄像头异常", result.get("detail", "无法打开摄像头"))
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
            self._alert("网络错误", "无法连接至服务器，请检查网络连接")
            return

        free_lock = None
        for lid, info in sorted(lockers.items()):
            if info.get("status") == 0:
                free_lock = lid
                break
        if free_lock is None:
            self._alert("无空闲柜子", "当前没有空闲柜子，请稍后再试。")
            return

        # 3) 上传裁剪后的物品图 + 识别结果
        try:
            network_manager.store_item(
                free_lock, photo_path,
                category=category, confidence=confidence,
            )
        except requests.exceptions.RequestException:
            self._alert("网络错误", "无法连接至服务器，物品未存入，请检查网络连接")
            return
        except Exception as exc:
            self._alert("存物失败", "上传物品信息失败：%s" % exc)
            return

        # 4) 直接开锁（不做二次确认）
        lock_error = None
        try:
            open_lock.open_lock(lock_number=free_lock)
        except Exception as exc:
            lock_error = exc

        # 5) 返回结果
        if lock_error is not None:
            self._alert("开锁失败",
                        "物品已登记到 %s 号柜，但柜门未能打开：%s\n\n"
                        "请联系管理员处理（检查电锁与串口配置）。" % (free_lock, lock_error))
        else:
            ui_dialog.show(
                self.root, "开锁成功",
                "%s 号柜已打开\n\n物品：%s（置信度 %.0f%%）\n请将物品放入柜中并关好柜门。"
                % (free_lock, category, confidence * 100),
                [("知道了", True)], kind="ok",
                on_close=lambda _v: self._back_to_main(),
            )

    # ------------------------------------------------------------ 内嵌提示框
    def _alert(self, title, message, kind="error"):
        """内嵌错误提示：点「确定」或 30 秒后回到主界面。"""
        ui_dialog.show(self.root, title, message, [("确定", True)], kind=kind,
                       on_close=lambda _v: self._back_to_main())
