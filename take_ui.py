import tkinter as tk
from tkinter import messagebox
import os
import requests
from PIL import Image, ImageTk

import open_lock
import config
import network_manager
import photo_manager
from face_recognize import FaceRecognition

class TakeUI:
    """取物品界面及逻辑（客户端‑服务器版）"""
    def __init__(self, parent_app):
        self.parent = parent_app
        self.root = parent_app.root
        self.taker_name = None
        self.selected_locker_id = None
        self.lockers_data = {}          # 从服务端获取的完整柜子状态
        self.locker_buttons = []        # 用于高亮

    def show(self):
        """第一步：人脸识别取物人"""
        fr = FaceRecognition()
        try:
            self.taker_name = fr.run_recognition()
        except requests.exceptions.RequestException:
            messagebox.showerror("识别失败", "人脸识别服务器不可用，请检查服务器、人脸库和模型配置")
            return
        if self.taker_name is not None:
            self._show_locker_selection()

    def _show_locker_selection(self):
        """第二步：显示柜子选择界面"""

        self._clear_window()
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)

        # 滚动区域
        canvas = tk.Canvas(main_frame, bg='#f0f0f0')
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg='#f0f0f0')
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 返回按钮
        back_btn = tk.Button(scrollable, text="返回", bg='#CCCCCC', font=('微软雅黑',10), width=8,
                             command=self.parent.show_main_interface)
        back_btn.grid(row=0, column=0, sticky='nw', pady=(0,0))

        # 图例
        top_frame = tk.Frame(scrollable, bg='#f0f0f0')
        top_frame.grid(row=1, column=0, columnspan=4, pady=(0,0), sticky='ew')
        tk.Label(top_frame, text="选择要取物的柜子", bg='#f0f0f0', font=('微软雅黑',16,'bold')).pack(side=tk.LEFT, padx=(40,10))
        legend_frame = tk.Frame(top_frame, bg='#f0f0f0')
        legend_frame.pack(side=tk.LEFT)
        tk.Label(legend_frame, text="有物品", bg='#4CAF50', fg='white', width=8).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="无物品", bg='#9E9E9E', fg='white', width=8).pack(side=tk.LEFT, padx=5)

        # 从服务端获取柜子状态
        try:
            self.lockers_data = network_manager.get_lockers_status()
        except requests.exceptions.RequestException:
            messagebox.showerror("网络错误", "无法连接至服务器，请检查网络连接")
            self.parent.show_main_interface()
            return

        self.locker_buttons = []
        for i in range(1, 9):
            row = 3 + (i-1)//4
            col = (i-1)%4
            status = self.lockers_data.get(i, {}).get('status', 0)
            bg = '#4CAF50' if status == 1 else '#9E9E9E'
            state = tk.NORMAL if status == 1 else tk.DISABLED
            text = f"{i}号柜"
            btn = tk.Button(scrollable, text=text, bg=bg, fg='white', font=('微软雅黑',10,'bold'),
                            width=10, height=3, state=state,
                            command=lambda lid=i: self._select_locker(lid))
            btn.grid(row=row, column=col, padx=10, pady=10)
            self.locker_buttons.append(btn)

        # 信息显示区
        self.info_frame = tk.Frame(scrollable, bg='#f0f0f0')
        self.info_frame.grid(row=5, column=0, columnspan=4, sticky='we', pady=(20,0))
        self._show_default_info()

    def _show_default_info(self):
        """清空信息区并显示默认提示"""
        for w in self.info_frame.winfo_children():
            w.destroy()
        tk.Label(self.info_frame, text="请选择上方柜子查看物品信息", bg='#f0f0f0', font=('微软雅黑',14)).pack(expand=True, fill='both', pady=50)

    def _select_locker(self, locker_id):
        """选中某个柜子，高亮并显示物品信息"""
        self.selected_locker_id = locker_id
        # 高亮选中的按钮
        for i, btn in enumerate(self.locker_buttons):
            if i+1 == locker_id:
                btn.config(bg='#FF9800')
            else:
                status = self.lockers_data.get(i+1, {}).get('status', 0)
                btn.config(bg='#4CAF50' if status==1 else '#9E9E9E')
        self._show_item_info(locker_id)

    def _show_item_info(self, locker_id):
        """在信息区显示该柜子的物品照片和详情"""
        for w in self.info_frame.winfo_children():
            w.destroy()

        item = self.lockers_data.get(locker_id)
        if not item or item.get('status') == 0:
            tk.Label(self.info_frame, text=f"{locker_id}号柜无物品", bg='#f0f0f0', font=('微软雅黑',14)).pack(expand=True, fill='both', pady=50)
            return

        container = tk.Frame(self.info_frame, bg='#f0f0f0')
        container.pack(expand=True, fill='both', padx=20, pady=0)
        tk.Label(container, text=f"{locker_id}号柜物品图片", bg='#f0f0f0', font=('微软雅黑',16,'bold')).pack()

        # 从服务端加载照片
        photo_name = item.get('photo_name')
        if photo_name:
            # 下载到临时目录并显示
            temp_photo_path = self._download_photo(photo_name)
            if temp_photo_path:
                img_label = tk.Label(container, bg='#f0f0f0')
                img_label.pack(pady=10)
                photo_manager.show_photo_preview(img_label, temp_photo_path)
            else:
                tk.Label(container, text="图片加载失败", bg='#f0f0f0', font=('微软雅黑',12)).pack(pady=10)

        # 取物按钮
        take_btn = tk.Button(container, text="确认取物", bg='#4CAF50', fg='white', font=('微软雅黑',12,'bold'),
                             width=15, height=2, command=lambda: self._confirm_take(locker_id, item))
        take_btn.pack(pady=20)

    def _download_photo(self, photo_name):
        url = network_manager.get_photo_url(photo_name)
        try:
            resp = requests.get(url, timeout=10, verify=network_manager.request_verify())
            resp.raise_for_status()
            temp_path = os.path.join(config.TEMP_DIR, photo_name)
            with open(temp_path, 'wb') as f:
                f.write(resp.content)
            return temp_path
        except requests.exceptions.RequestException:
            messagebox.showerror("网络错误", "无法连接至服务器，请检查网络连接")
            return None
        except Exception as e:
            print(f"下载照片失败: {e}")
            return None

    def _confirm_take(self, locker_id, item):
        confirm = messagebox.askyesno("确认取物", f"确认从 {locker_id} 号柜取物吗？\n\n位置: {config.LOCATION}\n取物人: {self.taker_name}")
        if not confirm:
            return

        try:
            network_manager.take_item(locker_id, self.taker_name)
            open_lock.open_lock(lock_number=locker_id)
            messagebox.showinfo("取物成功", f"正在打开 {locker_id} 号柜...\n\n取物成功！\n柜子：{locker_id}号柜\n取物人：{self.taker_name}")
            self.parent.show_main_interface()
        except requests.exceptions.RequestException:
            messagebox.showerror("网络错误", "无法连接至服务器，请检查网络连接")
        except Exception as e:
            messagebox.showerror("错误", f"取物失败：{e}")

    def _clear_window(self):
        """清空主窗口"""
        for widget in self.root.winfo_children():
            widget.destroy()
