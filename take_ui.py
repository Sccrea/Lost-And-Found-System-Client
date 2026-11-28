import tkinter as tk
from tkinter import messagebox, ttk
import os
import requests
from PIL import Image, ImageTk

import open_lock
import config
import network_manager
import photo_manager
import ui_dialog
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
        self.parent.current_view = "take"
        self._clear_window()   # 先清掉主界面，预览层独占窗口
        fr = FaceRecognition()
        # 预览渲染在主窗口内，识别完成/取消后走回调
        fr.run_recognition(self.root, self._on_face_done)

    def _on_face_done(self, result):
        status = result.get("status")
        if status in ("cancelled", "timeout", "no_face"):
            # 触屏：取消 / 30 秒无操作或未识别 → 直接回主界面
            self.parent.show_main_interface()
            return
        if status == "error":
            ui_dialog.show(self.root, "识别失败",
                           result.get("detail") or "人脸识别服务器不可用，请检查服务器、人脸库和模型配置",
                           [("确定", True)], kind="error",
                           on_close=lambda _v: self.parent.show_main_interface())
            return
        self.taker_name = result.get("name")
        if self.taker_name:
            self._show_locker_selection()

    def _show_locker_selection(self):
        """第二步：单页显示物品照片 + 柜子下拉选择 + 确认取物（不需要滚动）。"""
        self._clear_window()

        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(expand=True, fill='both')

        # ---------- 顶栏 ----------
        top_bar = tk.Frame(main_frame, bg='#f0f0f0', height=64)
        top_bar.pack(fill='x', padx=16, pady=(12, 4))
        top_bar.pack_propagate(False)

        tk.Button(top_bar, text="返回", bg='#CCCCCC', font=('微软雅黑', 16, 'bold'), width=8,
                  command=self.parent.show_main_interface).pack(side='left')

        tk.Label(top_bar, text="取物人：%s" % (self.taker_name or ""), bg='#f0f0f0',
                 font=('微软雅黑', 20, 'bold'), fg='#1f6feb').pack(side='left', padx=24)

        tk.Label(top_bar, text="位置：%s" % config.LOCATION, bg='#f0f0f0',
                 font=('微软雅黑', 14), fg='#555555').pack(side='right')

        # ---------- 主体：左图右信息 ----------
        body = tk.Frame(main_frame, bg='#f0f0f0')
        body.pack(fill='both', expand=True, padx=16, pady=(0, 12))

        # 右栏先 pack，保证贴住窗口右侧
        right = tk.Frame(body, bg='#f0f0f0', width=340)
        right.pack(side='right', fill='y', padx=(18, 0))
        right.pack_propagate(False)

        left = tk.Frame(body, bg='#e2e8f0')
        left.pack(side='left', fill='both', expand=True)

        self.photo_label = tk.Label(left, bg='#e2e8f0', text="正在加载物品照片…",
                                    font=('微软雅黑', 14), fg='#64748b')
        self.photo_label.pack(fill='both', expand=True)

        # 从服务端获取柜子状态
        try:
            self.lockers_data = network_manager.get_lockers_status()
        except requests.exceptions.RequestException:
            ui_dialog.show(self.root, "网络错误", "无法连接至服务器，请检查网络连接",
                           [("确定", True)], kind="error",
                           on_close=lambda _v: self.parent.show_main_interface())
            return

        # 柜子下拉列表（8 个柜子合成一个下拉框，节省空间）
        tk.Label(right, text="选择柜子", bg='#f0f0f0', font=('微软雅黑', 16, 'bold'),
                 anchor='w').pack(fill='x', pady=(6, 4))

        self.locker_options = []
        for lid in range(1, 9):
            status = self.lockers_data.get(lid, {}).get('status', 0)
            label = "%d 号柜（%s）" % (lid, "有物品" if status == 1 else "空闲")
            self.locker_options.append((label, lid))

        # 用大按钮代替下拉框：点开是整屏大按钮面板，触屏点得中
        self.locker_var = tk.StringVar(value="请选择柜子")
        self.locker_button = tk.Button(
            right, textvariable=self.locker_var, font=('微软雅黑', 20, 'bold'),
            bg='#ffffff', fg='#1f2937', activebackground='#e2e8f0',
            relief='ridge', bd=2, height=2, anchor='w', padx=12,
            command=self._open_locker_picker,
        )
        self.locker_button.pack(fill='x')

        # 物品信息
        self.info_frame = tk.Frame(right, bg='#f0f0f0')
        self.info_frame.pack(fill='both', expand=True, pady=(14, 0))

        # 确认取物
        self.take_btn = tk.Button(right, text="确认取物", bg='#4CAF50', fg='white',
                                  font=('微软雅黑', 22, 'bold'), width=12, height=2,
                                  state='disabled', command=self._on_take_clicked)
        self.take_btn.pack(side='bottom', pady=(10, 6))

        # 默认选中第一个有物品的柜子
        default_index = None
        for index, (label, lid) in enumerate(self.locker_options):
            if self.lockers_data.get(lid, {}).get('status', 0) == 1:
                default_index = index
                break
        if default_index is None:
            self.locker_var.set("当前没有可取的物品")
            self._show_empty_info()
        else:
            self._select_locker_index(default_index)

    # ------------------------------------------------------------ 下拉框事件
    def _selected_locker_id(self):
        return self.selected_locker_id

    def _select_locker_index(self, index):
        if not (0 <= index < len(self.locker_options)):
            return
        label, locker_id = self.locker_options[index]
        self.locker_var.set(label + "  ▾")
        self.selected_locker_id = locker_id
        item = self.lockers_data.get(locker_id) or {}
        if item.get('status') == 1:
            self.take_btn.config(state='normal')
            self._show_item_info(locker_id, item)
        else:
            self.take_btn.config(state='disabled')
            self._show_empty_info(locker_id)

    def _on_locker_chosen(self, event=None):
        self._select_locker_index(0 if self.selected_locker_id is None else
                                  [lid for _, lid in self.locker_options].index(self.selected_locker_id))

    # ------------------------------------------------------------ 柜子选择面板
    def _open_locker_picker(self):
        """整屏面板：8 个大按钮，2 列 4 行，单手可点。"""
        self.picker = tk.Frame(self.root, bg='#0b1220')
        self.picker.place(x=0, y=0, relwidth=1, relheight=1)
        self.picker.lift()

        card = tk.Frame(self.picker, bg='#ffffff')
        card.place(relx=0.5, rely=0.5, anchor='center', width=760)

        tk.Label(card, text="选择柜子", bg='#ffffff', fg='#4a90e2',
                 font=('微软雅黑', 26, 'bold')).pack(pady=(22, 6))
        tk.Label(card, text="绿色 = 有物品   灰色 = 空闲", bg='#ffffff',
                 fg='#64748b', font=('微软雅黑', 14)).pack(pady=(0, 14))

        grid = tk.Frame(card, bg='#ffffff')
        grid.pack(padx=20, pady=(0, 16))

        for index, (label, locker_id) in enumerate(self.locker_options):
            status = self.lockers_data.get(locker_id, {}).get('status', 0)
            bg = '#4CAF50' if status == 1 else '#9E9E9E'
            btn = tk.Button(
                grid, text="%d 号柜\n%s" % (locker_id, "有物品" if status == 1 else "空闲"),
                bg=bg, fg='white', font=('微软雅黑', 22, 'bold'),
                width=8, height=3, bd=0,
                activebackground=('#43a047' if status == 1 else '#8d8d8d'),
                activeforeground='white',
                command=lambda i=index: self._pick_locker(i),
            )
            btn.grid(row=index // 4, column=index % 4, padx=8, pady=8)

        tk.Button(card, text="关闭", bg='#e2e8f0', fg='#334155',
                  font=('微软雅黑', 18, 'bold'), width=10, height=1,
                  bd=0, command=self._close_locker_picker).pack(pady=(0, 20))

    def _pick_locker(self, index):
        self._close_locker_picker()
        self._select_locker_index(index)

    def _close_locker_picker(self):
        picker = getattr(self, 'picker', None)
        if picker is not None:
            try:
                picker.destroy()
            except tk.TclError:
                pass
            self.picker = None

    def _on_take_clicked(self):
        locker_id = self.selected_locker_id
        if locker_id is None:
            return
        item = self.lockers_data.get(locker_id) or {}
        if item.get('status') != 1:
            return
        self._confirm_take(locker_id, item)

    # ------------------------------------------------------------ 信息区
    def _show_empty_info(self, locker_id=None):
        for widget in self.info_frame.winfo_children():
            widget.destroy()
        text = "%d 号柜是空的" % locker_id if locker_id else "当前没有可取的物品"
        tk.Label(self.info_frame, text=text, bg='#f0f0f0', font=('微软雅黑', 16),
                 fg='#9E9E9E').pack(anchor='w', pady=10)
        self.photo_label.config(image='', text="（该柜子没有物品）",
                                font=('微软雅黑', 14), fg='#94a3b8')
        self.photo_label.image = None

    def _show_item_info(self, locker_id, item=None):
        """右侧显示柜号/类别/存入时间，左侧显示物品照片。"""
        item = item or self.lockers_data.get(locker_id) or {}
        for widget in self.info_frame.winfo_children():
            widget.destroy()

        rows = [("柜号", "%d 号柜" % locker_id), ("状态", "有物品")]
        if item.get('store_time'):
            rows.append(("存入时间", item['store_time']))
        for key, value in rows:
            row = tk.Frame(self.info_frame, bg='#f0f0f0')
            row.pack(fill='x', pady=4)
            tk.Label(row, text=key, bg='#f0f0f0', font=('微软雅黑', 14),
                     fg='#64748b', width=8, anchor='w').pack(side='left')
            tk.Label(row, text=value, bg='#f0f0f0', font=('微软雅黑', 15, 'bold'),
                     fg='#1f2937', anchor='w', wraplength=240, justify='left').pack(side='left')

        photo_name = item.get('photo_name')
        self.photo_label.config(image='', text="正在加载物品照片…",
                                font=('微软雅黑', 14), fg='#64748b')
        self.photo_label.image = None
        if not photo_name:
            self.photo_label.config(text="（该物品没有照片）")
            return

        self.photo_label.after(10, lambda: self._load_photo(photo_name))

    def _load_photo(self, photo_name):
        path = self._download_photo(photo_name)
        if not path:
            self.photo_label.config(text="图片加载失败", fg='#d64545')
            return
        # 布局还没完成时先等一会儿，否则会按 1x1 的尺寸缩放
        if self.photo_label.winfo_width() < 120 or self.photo_label.winfo_height() < 120:
            self.photo_label.after(200, lambda: self._load_photo(photo_name))
            return

        try:
            image = Image.open(path)
            max_w = max(self.photo_label.winfo_width() - 24, 320)
            max_h = max(self.photo_label.winfo_height() - 24, 240)
            scale = min(max_w / image.width, max_h / image.height)
            image = image.resize((max(1, int(image.width * scale)),
                                  max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.photo_label.config(image=photo, text='')
            self.photo_label.image = photo
        except Exception as exc:
            print("显示物品照片失败:", exc)
            self.photo_label.config(text="图片无法显示", fg='#d64545')

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
            self._alert("网络错误", "无法连接至服务器，请检查网络连接")
            return None
        except Exception as e:
            print(f"下载照片失败: {e}")
            return None

    def _confirm_take(self, locker_id, item):
        ui_dialog.confirm(
            self.root, "确认取物",
            "确认从 %s 号柜取物吗？\n\n位置：%s\n取物人：%s"
            % (locker_id, config.LOCATION, self.taker_name),
            on_yes=lambda: self._do_take(locker_id),
            on_no=lambda: None,
        )

    def _do_take(self, locker_id):
        try:
            network_manager.take_item(locker_id, self.taker_name)
            open_lock.open_lock(lock_number=locker_id)
            ui_dialog.show(
                self.root, "取物成功",
                "%s 号柜已打开\n\n取物人：%s\n请取走物品并关好柜门。"
                % (locker_id, self.taker_name),
                [("知道了", True)], kind="ok",
                on_close=lambda _v: self.parent.show_main_interface(),
            )
        except requests.exceptions.RequestException:
            self._alert("网络错误", "无法连接至服务器，请检查网络连接")
        except Exception as e:
            self._alert("取物失败", "取物失败：%s" % e)

    def _alert(self, title, message, kind="error"):
        ui_dialog.show(self.root, title, message, [("确定", True)], kind=kind,
                       on_close=lambda _v: self.parent.show_main_interface())

    def _clear_window(self):
        """清空主窗口"""
        for widget in self.root.winfo_children():
            widget.destroy()
