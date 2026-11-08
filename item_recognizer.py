# -*- coding: utf-8 -*-
"""物品识别模块（YOLO11 ONNX 推理）。

本模块由 PR #24 的 lostfound_rip/ 原型改造而来，修掉了原型里几处硬伤：
  * `_postprocess` 实参个数错误（原代码一调用就 TypeError）
  * 不存在 `close()` 导致退出崩溃
  * 写死 Linux V4L2 摄像头后端
  * 模型路径写死相对路径、仓库里又没有模型

对外只暴露三样东西：
    recognizer = get_recognizer()          # 单例，模型缺失时返回 None
    items = recognizer.recognize(frame)    # -> [{'label':'suitcase','label_cn':'行李箱','score':0.9,'box':(x,y,w,h)}]
    cap = open_camera(0)                   # 跨平台摄像头封装
"""

import os
import sys

import cv2
import numpy as np

# ---------------------------------------------------------------- 类别定义
# 失物招领常见物品，取自 COCO 80 类（索引与官方一致）
TARGET_CLASSES = {
    24: "背包",
    26: "手提包",
    28: "行李箱",
    39: "瓶子",
    41: "杯子",
    67: "手机",
    73: "书本",
}

UNKNOWN_LABEL_CN = "其他"

COCO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]

MODEL_FILENAME = "yolo11n.onnx"


# ---------------------------------------------------------------- 路径处理
def app_base_dir():
    """打包成 exe 时返回 exe 所在目录，否则返回本文件目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundled_dir():
    """PyInstaller 解包目录（--add-data 的落地点）。"""
    return getattr(sys, "_MEIPASS", app_base_dir())


def resolve_model_path():
    """按优先级找模型：环境变量 > exe 同级 models/ > 打包内置 models/。

    exe 同级 models/ 优先，方便现场替换模型而不必重新打包。
    """
    candidates = [
        os.environ.get("LOSTFOUND_MODEL_PATH"),
        os.path.join(app_base_dir(), "models", MODEL_FILENAME),
        os.path.join(bundled_dir(), "models", MODEL_FILENAME),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


# ---------------------------------------------------------------- 摄像头
def open_camera(index=0, width=640, height=480):
    """打开摄像头，按平台选择后端；打不开返回 None。"""
    if sys.platform == "win32":
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    elif sys.platform == "darwin":
        backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    else:
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]

    for backend in backends:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            continue
        # MJPG 能显著降低 USB2 带宽占用；失败也不要紧
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap
    return None


# ---------------------------------------------------------------- 绘制
_FONT_CANDIDATES = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "msyh.ttc"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "simhei.ttf"),
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


def _load_font(size):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_items(frame_bgr, items, hint=None):
    """在画面上画出识别框与中文标签，返回新画面。"""
    if not items and not hint:
        return frame_bgr
    from PIL import Image, ImageDraw

    image = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    font = _load_font(20)
    small = _load_font(16)

    for item in items:
        x, y, w, h = item["box"]
        draw.rectangle([x, y, x + w, y + h], outline=(0, 200, 80), width=3)
        text = "%s %.0f%%" % (item["label_cn"], item["score"] * 100)
        tw, th = draw.textbbox((0, 0), text, font=font)[2:]
        ty = max(y - th - 8, 0)
        draw.rectangle([x, ty, x + tw + 12, ty + th + 8], fill=(0, 200, 80))
        draw.text((x + 6, ty + 3), text, font=font, fill=(255, 255, 255))

    if hint:
        tw, th = draw.textbbox((0, 0), hint, font=small)[2:]
        draw.rectangle([0, 0, tw + 16, th + 12], fill=(0, 0, 0))
        draw.text((8, 5), hint, font=small, fill=(255, 255, 255))

    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


# ---------------------------------------------------------------- 识别器
class ItemRecognizer:
    """YOLO11 ONNX 检测器（CPU 推理）。"""

    def __init__(self, model_path, input_size=640, score=0.5, nms=0.45):
        self.model_path = model_path
        self.input_size = input_size
        self.score = score
        self.nms = nms
        self._session = None
        self._input_name = None
        self.last_error = None

    # -- 生命周期 ---------------------------------------------------
    def _ensure_session(self):
        if self._session is not None:
            return True
        try:
            import onnxruntime as ort

            so = ort.SessionOptions()
            so.log_severity_level = 3
            self._session = ort.InferenceSession(
                self.model_path, sess_options=so, providers=["CPUExecutionProvider"]
            )
            self._input_name = self._session.get_inputs()[0].name
            return True
        except Exception as exc:  # 模型损坏 / 缺 DLL / 无 onnxruntime
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            return False

    def close(self):
        self._session = None
        self._input_name = None

    # -- 推理 -------------------------------------------------------
    def _letterbox(self, img, new_size):
        h, w = img.shape[:2]
        r = min(new_size / h, new_size / w)
        nh, nw = int(round(h * r)), int(round(w * r))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        dw, dh = (new_size - nw) / 2.0, (new_size - nh) / 2.0
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right,
            cv2.BORDER_CONSTANT, value=(114, 114, 114),
        )
        return padded, r, (left, top)

    def recognize(self, frame_bgr):
        """返回按置信度排序的物品列表，只保留 TARGET_CLASSES 中的类别。"""
        if frame_bgr is None or not self._ensure_session():
            return []

        img, ratio, pad = self._letterbox(frame_bgr, self.input_size)
        blob = img[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        blob = np.expand_dims(blob, 0)

        try:
            outputs = self._session.run(None, {self._input_name: blob})
        except Exception as exc:
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            return []

        return self._postprocess(outputs[0], ratio, pad, frame_bgr.shape)

    def _postprocess(self, pred, ratio, pad, orig_shape):
        """pred: (1, 84, N) —— 4 个框参数 + N 个类别分数。"""
        pred = np.squeeze(pred)
        if pred.ndim != 2:
            return []
        if pred.shape[0] < pred.shape[1]:      # (84, 8400) -> (8400, 84)
            pred = pred.T

        boxes, scores, class_ids = [], [], []
        for row in pred:
            cls_scores = row[4:]
            cid = int(np.argmax(cls_scores))
            conf = float(cls_scores[cid])
            if conf < self.score:
                continue
            if cid not in TARGET_CLASSES:       # 提前过滤，省掉一堆无关框
                continue
            cx, cy, bw, bh = row[0], row[1], row[2], row[3]
            x = (cx - bw / 2.0 - pad[0]) / ratio
            y = (cy - bh / 2.0 - pad[1]) / ratio
            w = bw / ratio
            h = bh / ratio
            boxes.append([int(x), int(y), int(w), int(h)])
            scores.append(conf)
            class_ids.append(cid)

        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(boxes, scores, self.score, self.nms)
        if indices is None or len(indices) == 0:
            return []

        h_img, w_img = orig_shape[:2]
        results = []
        for i in np.array(indices).flatten():
            x, y, w, h = boxes[int(i)]
            # 裁到画面内，避免画框越界
            x = max(0, min(x, w_img - 1))
            y = max(0, min(y, h_img - 1))
            w = max(1, min(w, w_img - x))
            h = max(1, min(h, h_img - y))
            cid = class_ids[int(i)]
            results.append({
                "label": COCO_LABELS[cid],
                "label_cn": TARGET_CLASSES[cid],
                "score": float(scores[int(i)]),
                "box": [int(x), int(y), int(w), int(h)],
            })
        results.sort(key=lambda r: r["score"], reverse=True)
        return results


# ---------------------------------------------------------------- 单例
_recognizer = None
_init_done = False


def get_recognizer():
    """全局单例；模型不存在或加载失败时返回 None（界面降级为不识别）。"""
    global _recognizer, _init_done
    if not _init_done:
        _init_done = True
        path = resolve_model_path()
        if path is None:
            print("[识别] 未找到模型文件 %s，将跳过识别" % MODEL_FILENAME)
        else:
            rec = ItemRecognizer(path, score=0.5)
            if rec._ensure_session():
                print("[识别] 模型加载成功: %s" % path)
                _recognizer = rec
            else:
                print("[识别] 模型加载失败: %s" % rec.last_error)
    return _recognizer


def best_item(items):
    """取置信度最高的一个。"""
    return items[0] if items else None
