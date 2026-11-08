import os
import sys
import threading
import traceback
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox
from store_ui import StoreUI
from take_ui import TakeUI
import config
import item_recognizer
import network_manager
import requests

class LostAndFoundApp:
    def __init__(self, root):
        self.root = root
        self.root.title("失物招领管理系统")
        self.root.geometry("700x600")
        self.root.configure(bg='#f0f0f0')

        # 获取屏幕尺寸用于自适应
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        # ---------- 设置全屏 ----------
        self.root.attributes('-fullscreen', True)
        # 绑定 ESC 键退出全屏（按 ESC 可切换回窗口模式，不退出程序）
        self.root.bind('<Escape>', self._quit_app)

        # 初始化UI子模块
        self.store_ui = StoreUI(self)
        self.take_ui = TakeUI(self)

        # 显示主界面
        self.show_main_interface()
        self._register_terminal()

    def _register_terminal(self):
        try:
            result = network_manager.register_terminal()
            print(f"终端信息上传成功: {result['terminal_id']}，位置: {result['location']}")
        except Exception as e:
            print(f"终端信息上传失败: {e}，可能网络不可用，使用本地缓存")

    def show_main_interface(self):
        self._clear_window()
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(expand=True, fill='both')

        # 根据屏幕尺寸计算字体大小（取宽高较小值除以20，最小16）
        base_size = min(self.screen_width, self.screen_height) // 20
        if base_size < 16:
            base_size = 16
        location_font = ('微软雅黑', base_size, 'bold')
        button_font = ('微软雅黑', base_size * 2, 'bold')

        # 位置标签（顶部）
        location_label = tk.Label(main_frame, text=f"当前位置：{config.LOCATION}",
                                  bg='#f0f0f0', font=location_font, fg='#333333')
        location_label.pack(pady=(30, 10))

        # 按钮容器（占据剩余全部空间）
        button_container = tk.Frame(main_frame, bg='#f0f0f0')
        button_container.pack(expand=True, fill='both')

        # 取物品按钮（左）
        take_btn = tk.Button(button_container, text="取物品", bg='#4A90E2', fg='white',
                             font=button_font,
                             command=self.take_ui.show)
        # 存物品按钮（右）
        store_btn = tk.Button(button_container, text="存物品", bg='#F5A623', fg='white',
                              font=button_font,
                              command=self.store_ui.show)

        # 两个按钮从左到右排列，均分容器宽度，高度填满，并留边距
        take_btn.pack(side=tk.LEFT, expand=True, fill='both', padx=20, pady=40)
        store_btn.pack(side=tk.LEFT, expand=True, fill='both', padx=20, pady=40)

    def _clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def _quit_app(self, event=None):
        """退出应用程序"""
        if messagebox.askyesno("确认退出", "确定要退出失物招领系统吗？"):
            self.root.quit()
            self.root.destroy()

def _write_crash_log(exc_text):
    """打包成 windowed exe 后没有控制台，把异常落到 files/error.log 便于排查。"""
    try:
        os.makedirs(config.FILES_DIR, exist_ok=True)
        path = os.path.join(config.FILES_DIR, "error.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("[%s]\n%s\n\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), exc_text))
    except Exception:
        pass


def main():
    try:
        root = tk.Tk()
        app = LostAndFoundApp(root)
        # 后台预热识别模型，避免第一次拍照卡顿
        if config.ENABLE_RECOGNITION:
            threading.Thread(target=item_recognizer.get_recognizer, daemon=True).start()
        root.mainloop()
    except Exception:
        _write_crash_log(traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            messagebox.showerror("程序异常", "程序发生异常，详情见 files/error.log")
        except Exception:
            pass
        sys.exit(1)