# -*- coding: utf-8 -*-
"""拍照 + 物品识别。

拍照流程：打开摄像头实时预览 → 预览画面上直接框出识别到的物品 →
按空格拍照（对原始帧再做一次识别确认）→ 返回照片与识别结果。
按 ESC 取消。没有摄像头时填 config.CAMERA_TEST_IMAGE 可用图片模拟拍摄。
"""

import os

import cv2
from PIL import Image, ImageTk
import tkinter.messagebox as messagebox

import config
import item_recognizer

WINDOW_NAME = "Take Photo - SPACE: capture   ESC: cancel"
TEMP_PHOTO_NAME = "a.jpg"
PREVIEW_MAX = (400, 300)


def temp_photo_path():
    """拍照暂存路径：files/temp/a.jpg"""
    return os.path.join(config.TEMP_DIR, TEMP_PHOTO_NAME)


def _recognizer():
    if not config.ENABLE_RECOGNITION:
        return None
    return item_recognizer.get_recognizer()


def _best(frame, recognizer):
    if recognizer is None or frame is None:
        return None
    items = recognizer.recognize(frame)
    return items[0] if items else None


def capture_item_photo():
    """拍照并自动识别物品。

    返回 (是否成功拍照, 识别结果)。
    识别结果形如 {'label': 'suitcase', 'label_cn': '行李箱', 'score': 0.9, 'box': [...]}；
    没识别到物品时返回 None（照片仍然有效）。
    """
    photo_path = temp_photo_path()

    # ---- 无摄像头联调模式 ----
    if config.CAMERA_TEST_IMAGE:
        if not os.path.isfile(config.CAMERA_TEST_IMAGE):
            messagebox.showerror("错误", "CAMERA_TEST_IMAGE 指向的图片不存在：\n%s"
                                 % config.CAMERA_TEST_IMAGE)
            return False, None
        frame = cv2.imread(config.CAMERA_TEST_IMAGE)
        if frame is None:
            messagebox.showerror("错误", "无法读取测试图片：\n%s" % config.CAMERA_TEST_IMAGE)
            return False, None
        cv2.imwrite(photo_path, frame)
        return True, _best(frame, _recognizer())

    # ---- 摄像头模式 ----
    recognizer = _recognizer()
    cap = item_recognizer.open_camera(config.CAMERA_INDEX)
    if cap is None:
        messagebox.showerror(
            "错误",
            "无法打开摄像头（序号 %s）。\n请检查摄像头连接，或在 files/config.json 中调整 CAMERA_INDEX。"
            % config.CAMERA_INDEX,
        )
        return False, None

    captured = False
    result = None
    items = []
    index = 0
    try:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 960, 720)
    except cv2.error:
        pass

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            # 预览降频识别：每 3 帧一次，够用又不卡
            if recognizer is not None and index % 3 == 0:
                items = recognizer.recognize(frame)
            index += 1

            if recognizer is None:
                hint = "未加载识别模型 · 空格=拍照  ESC=取消"
            elif items:
                hint = "识别到：%s %.0f%% · 空格=拍照  ESC=取消" % (
                    items[0]["label_cn"], items[0]["score"] * 100)
            else:
                hint = "请把物品对准摄像头 · 空格=拍照  ESC=取消"

            cv2.imshow(WINDOW_NAME, item_recognizer.draw_items(frame, items, hint))
            key = cv2.waitKey(1) & 0xFF
            if key == 32:  # 空格
                cv2.imwrite(photo_path, frame)
                captured = True
                # 用原始帧复算一次，保证存档照片与识别结果一致
                result = _best(frame, recognizer)
                break
            if key in (27, ord("q")):  # ESC / q
                break
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        try:
            cv2.destroyWindow(WINDOW_NAME)
        except cv2.error:
            pass
        cv2.waitKey(1)

    return captured, result


def show_photo_preview(photo_label, photo_path):
    """在给定的Label控件上显示照片预览"""
    if not os.path.exists(photo_path):
        return
    image = Image.open(photo_path)
    # 限制预览大小
    max_width, max_height = PREVIEW_MAX
    img_width, img_height = image.size
    scale = min(max_width / img_width, max_height / img_height)
    new_size = (int(img_width * scale), int(img_height * scale))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(resized)
    photo_label.config(image=photo, text="")
    photo_label.image = photo  # 保持引用
