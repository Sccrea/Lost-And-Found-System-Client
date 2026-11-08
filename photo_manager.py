# -*- coding: utf-8 -*-
"""全自动存物拍照：打开摄像头 → 实时识别 → 识别到物品立刻裁剪保存。

流程（无需用户操作）：
    capture_item_auto()
      ├─ 打开摄像头，逐帧推理
      ├─ 连续 N 帧识别到同一类物品（N = AUTO_CAPTURE_CONFIRM_FRAMES）
      ├─ 按检测框裁剪（外扩 CROP_PADDING_RATIO），保存到 files/temp/item.jpg
      └─ 返回识别结果，交给 store_ui 继续「上传 → 开锁」

返回值统一为 dict：
    {'status': 'ok',        'item': {...}, 'path': '...'}
    {'status': 'cancelled'}                    用户按 ESC
    {'status': 'no_item'}                      超时未识别到物品
    {'status': 'camera_error', 'detail': '...'} 摄像头打不开
"""

import os
import time

import cv2
from PIL import Image, ImageTk
import tkinter.messagebox as messagebox

import config
import item_recognizer

WINDOW_NAME = "Store Item - auto capture   (ESC: cancel)"
TEMP_PHOTO_NAME = "item.jpg"
PREVIEW_MAX = (400, 300)


def temp_photo_path():
    """裁剪后的物品图：files/temp/item.jpg"""
    return os.path.join(config.TEMP_DIR, TEMP_PHOTO_NAME)


def _recognizer():
    if not config.ENABLE_RECOGNITION:
        return None
    return item_recognizer.get_recognizer()


def crop_item(frame, box, padding=None):
    """按检测框裁剪物品，四周按比例外扩一点避免切边。"""
    if frame is None or not box:
        return None
    ratio = config.CROP_PADDING_RATIO if padding is None else padding
    h, w = frame.shape[:2]
    x, y, bw, bh = [int(v) for v in box]
    px, py = int(bw * ratio), int(bh * ratio)
    x0, y0 = max(0, x - px), max(0, y - py)
    x1, y1 = min(w, x + bw + px), min(h, y + bh + py)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return frame[y0:y1, x0:x1]


def _save_crop(frame, box):
    """裁剪并保存，返回 (路径, 裁剪尺寸) 或 (None, None)。"""
    crop = crop_item(frame, box)
    if crop is None:
        return None, None
    path = temp_photo_path()
    ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        return None, None
    buf.tofile(path)
    return path, (crop.shape[1], crop.shape[0])


class _StillImageSource:
    """无摄像头自检：把一张图片当作"摄像头画面"喂给同一个识别循环。"""

    def __init__(self, path):
        self.frame = cv2.imread(path)
        self.path = path

    def read(self):
        return (self.frame is not None), self.frame

    def release(self):
        pass


def capture_item_auto():
    """打开摄像头并自动抓拍物品。返回见模块文档。"""
    # 清掉上一次的裁剪图，避免误传旧图
    stale = temp_photo_path()
    if os.path.exists(stale):
        try:
            os.remove(stale)
        except OSError:
            pass

    recognizer = _recognizer()
    if recognizer is None:
        return {"status": "camera_error",
                "detail": "未加载物品识别模型，无法自动识别。\n请检查 models/yolo11n.onnx。"}

    # 自检模式与真实摄像头走同一套循环，只是画面来源不同
    if config.CAMERA_TEST_IMAGE:
        cap = _StillImageSource(config.CAMERA_TEST_IMAGE)
        if cap.frame is None:
            return {"status": "camera_error",
                    "detail": "无法读取测试图片：\n%s" % config.CAMERA_TEST_IMAGE}
    else:
        cap = item_recognizer.open_camera(config.CAMERA_INDEX)
        if cap is None:
            return {"status": "camera_error",
                    "detail": "无法打开摄像头（序号 %s）。\n请检查摄像头连接，"
                              "或在 files/config.json 中调整 CAMERA_INDEX。" % config.CAMERA_INDEX}

    confirm_frames = max(1, int(config.AUTO_CAPTURE_CONFIRM_FRAMES))
    timeout = float(config.AUTO_TIMEOUT_SEC)
    started = time.time()

    status = "no_item"
    detail = None
    item = None
    path = None
    stable = 0
    last_label = None
    read_fails = 0

    try:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 960, 720)
    except cv2.error:
        pass

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                # 有些后端（如 Windows MSMF）会"打开成功但读不到帧"，不能死等
                read_fails += 1
                if read_fails > 60:
                    status = "camera_error"
                    detail = ("摄像头已打开但读不到画面（序号 %s）。\n"
                              "请检查摄像头是否被其他程序占用，"
                              "或在 files/config.json 中调整 CAMERA_INDEX。" % config.CAMERA_INDEX)
                    break
                time.sleep(0.03)
                continue
            read_fails = 0

            items = recognizer.recognize(frame)
            best = items[0] if items else None

            if best is None:
                stable, last_label = 0, None
                hint = "请把物品放进取景框 · ESC 取消"
            else:
                # 连续同一类才算稳定，避免单帧误检直接开柜
                if best["label"] == last_label:
                    stable += 1
                else:
                    stable, last_label = 1, best["label"]
                hint = "识别到 %s %.0f%% · 正在存放…" % (
                    best["label_cn"], best["score"] * 100)

            cv2.imshow(WINDOW_NAME, item_recognizer.draw_items(frame, items, hint))
            key = cv2.waitKey(1) & 0xFF

            if key in (27, ord("q")):
                status = "cancelled"
                break

            if best is not None and stable >= confirm_frames:
                saved, size = _save_crop(frame, best["box"])
                if saved:
                    status = "ok"
                    item = dict(best, crop_size=size)
                    path = saved
                    break

            if timeout > 0 and time.time() - started > timeout:
                status = "no_item"
                break

            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                status = "cancelled"
                break
    finally:
        cap.release()
        try:
            cv2.destroyWindow(WINDOW_NAME)
        except cv2.error:
            pass
        cv2.waitKey(1)

    result = {"status": status, "item": item, "path": path}
    if detail:
        result["detail"] = detail
    return result


def show_photo_preview(photo_label, photo_path):
    """在给定的Label控件上显示照片预览"""
    if not os.path.exists(photo_path):
        return
    image = Image.open(photo_path)
    max_width, max_height = PREVIEW_MAX
    img_width, img_height = image.size
    scale = min(max_width / img_width, max_height / img_height)
    new_size = (int(img_width * scale), int(img_height * scale))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(resized)
    photo_label.config(image=photo, text="")
    photo_label.image = photo
