# -*- coding: utf-8 -*-
"""全自动存物拍照：打开摄像头 → 实时识别 → 识别到物品立刻裁剪保存。

预览画面直接渲染在 Tk 主窗口内（不再弹 cv2 独立窗口），因此始终居中、
也不会被主窗口顶掉。ESC 可取消。

异步接口：
    capture_item_auto(root, on_done)      # 不阻塞 Tk 主循环
    on_done(result) 收到 dict：
        {'status': 'ok',        'item': {...}, 'path': '...'}
        {'status': 'cancelled'}                     用户按 ESC
        {'status': 'no_item'}                       超时未识别到物品
        {'status': 'camera_error', 'detail': '...'} 摄像头打不开

实现：读帧 + 推理放在工作线程，Tk 主线程只负责渲染与状态判定，界面不卡。
"""

import os
import threading
import time

import cv2
from PIL import Image, ImageTk

import config
import item_recognizer
import ui_preview

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


def capture_item_auto(root, on_done):
    """打开摄像头并自动抓拍物品，完成后回调 on_done(result)。"""
    stale = temp_photo_path()
    if os.path.exists(stale):
        try:
            os.remove(stale)
        except OSError:
            pass

    recognizer = _recognizer()
    if recognizer is None:
        on_done({"status": "camera_error",
                 "detail": "未加载物品识别模型，无法自动识别。\n请检查 models/yolo11n.onnx。"})
        return

    if config.CAMERA_TEST_IMAGE:
        cap = _StillImageSource(config.CAMERA_TEST_IMAGE)
        if cap.frame is None:
            on_done({"status": "camera_error",
                     "detail": "无法读取测试图片：\n%s" % config.CAMERA_TEST_IMAGE})
            return
    else:
        # 真机相机交给采集线程自己打开（见 worker），避免跨线程 capture 取不到帧
        cap = None

    confirm_frames = max(1, int(config.AUTO_CAPTURE_CONFIRM_FRAMES))
    timeout = float(config.AUTO_TIMEOUT_SEC)                    # 30 秒未识别到物品就返回
    idle_timeout = float(getattr(config, "PREVIEW_IDLE_TIMEOUT_SEC", 30))  # 30 秒无触摸也返回
    started = time.time()
    activity = {"last": time.time()}

    state = {"stop": False, "latest": None, "stable": 0, "last_label": None, "error": None}
    lock = threading.Lock()
    finished = {"done": False}

    def worker():
        # 相机在采集线程内打开/启动：picamera2 跨线程 capture 会取不到新帧
        local_cap = cap
        try:
            if local_cap is None:
                local_cap = item_recognizer.open_camera(config.CAMERA_INDEX)
                if local_cap is None:
                    with lock:
                        state["error"] = "无法打开摄像头（序号 %s）。\n请检查摄像头连接，" \
                                         "或在 files/config.json 中调整 CAMERA_INDEX。" % config.CAMERA_INDEX
                    return
            while not state["stop"]:
                ok, frame = local_cap.read()
                if not ok or frame is None:
                    time.sleep(0.03)
                    continue
                items = recognizer.recognize(frame)
                with lock:
                    state["latest"] = (frame, items)
        except Exception as exc:      # 相机被占用等
            with lock:
                state["error"] = "%s: %s" % (type(exc).__name__, exc)
        finally:
            if local_cap is not None:
                local_cap.release()

    def finish(result):
        if finished["done"]:
            return
        finished["done"] = True
        state["stop"] = True
        if getattr(root, "escape_handler", None) is not None:
            root.escape_handler = None
        preview.close()
        on_done(result)

    def cancel(_event=None):
        finish({"status": "cancelled"})

    def touch():
        activity["last"] = time.time()

    preview = ui_preview.CameraPreview(
        root, "存入物品 · 请把物品放进取景框",
        on_cancel=cancel, on_activity=touch,
    )

    def tick():
        if finished["done"]:
            return
        now = time.time()
        left = min(timeout - (now - started) if timeout > 0 else 1e9,
                   idle_timeout - (now - activity["last"]) if idle_timeout > 0 else 1e9)
        if left <= 0:
            finish({"status": "timeout"})
            return

        with lock:
            latest = state["latest"]
            error = state["error"]

        if error:
            finish({"status": "camera_error", "detail": error})
            return

        tail = " · %d 秒后自动返回" % int(left)
        if latest is None:
            preview.update_frame(None, "正在打开摄像头…" + tail)
        if latest is not None:
            frame, items = latest
            best = items[0] if items else None
            if best is None:
                state["stable"], state["last_label"] = 0, None
                hint = "请把物品放进取景框" + tail
            else:
                if best["label"] == state["last_label"]:
                    state["stable"] += 1
                else:
                    state["stable"], state["last_label"] = 1, best["label"]
                hint = "识别到 %s %.0f%% · 正在存放…" % (best["label_cn"], best["score"] * 100)

            preview.update_frame(item_recognizer.draw_items(frame, items, None), hint)

            if best is not None and state["stable"] >= confirm_frames:
                saved, size = _save_crop(frame, best["box"])
                if saved:
                    finish({"status": "ok", "item": dict(best, crop_size=size), "path": saved})
                    return

        root.after(30, tick)

    # ESC 交给主窗口的分发器，避免覆盖全局 ESC 绑定
    root.escape_handler = cancel
    threading.Thread(target=worker, daemon=True).start()
    root.after(30, tick)


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
