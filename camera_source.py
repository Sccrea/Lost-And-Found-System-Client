# -*- coding: utf-8 -*-
"""统一的摄像头抽象：优先用 Picamera2（树莓派 CSI 摄像头），退化为 OpenCV。

树莓派 5 + Camera Module 3 的 CSI 摄像头不会出现在普通 UVC 设备里，
OpenCV 的 VideoCapture 打不开，必须走 libcamera/Picamera2。
本模块把"取帧"这一件事统一成 read()/release()，其余代码无感知。

用法：
    from camera_source import open_camera
    cap = open_camera(0)          # 0 = Picamera2 相机编号 / OpenCV 设备号
    ok, bgr = cap.read()
    cap.release()

后端选择：config.CAMERA_BACKEND = "auto" | "picamera2" | "opencv"
"""

import sys
import time

import cv2

DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480


def _picamera2_available():
    try:
        import picamera2  # noqa: F401
        from libcamera import controls  # noqa: F401
        return True
    except Exception:
        return False


def list_cameras():
    """列出 Picamera2 能看到的相机；不可用时返回空列表。"""
    try:
        from picamera2 import Picamera2
        return Picamera2.global_camera_info()
    except Exception:
        return []


class PiCamera2Source:
    """Picamera2 封装，read() 返回 BGR 帧。"""

    def __init__(self, index, width, height, exposure_compensation=0.0):
        from picamera2 import Picamera2
        from libcamera import controls

        self.index = int(index)
        self.width = width
        self.height = height
        self._picam = Picamera2(self.index)
        cfg = self._picam.create_preview_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        self._picam.configure(cfg)
        self._picam.start()
        # Camera Module 3 支持自动对焦，打开连续对焦否则画面永远是糊的
        controls_wanted = {
            "AfMode": controls.AfModeEnum.Continuous,
            "AfSpeed": controls.AfSpeedEnum.Fast,
            "AfRange": controls.AfRangeEnum.Normal,
            # 限制在 30fps：曝光时间不超过 33ms，真人轻微移动也不会糊成一团
            "FrameDurationLimits": (33333, 33333),
            # 优先短曝光（宁可提高增益），减少运动模糊
            "AeExposureMode": controls.AeExposureModeEnum.Short,
            # 中央加权测光：人脸在画面中间时不会因为背光而欠曝
            "AeMeteringMode": controls.AeMeteringModeEnum.CentreWeighted,
        }
        if exposure_compensation:
            controls_wanted["ExposureValue"] = float(exposure_compensation)
        try:
            self._picam.set_controls(controls_wanted)
        except Exception:
            # 某些机型不支持个别控制项，逐个兜底
            for key in ("AeMeteringMode", "AeExposureMode", "FrameDurationLimits", "ExposureValue"):
                controls_wanted.pop(key, None)
            try:
                self._picam.set_controls(controls_wanted)
            except Exception:
                pass
        time.sleep(0.8)  # 等曝光/白平衡/对焦稳定

    def read(self):
        try:
            arr = self._picam.capture_array()
        except Exception:
            return False, None
        if arr is None or arr.size == 0:
            return False, None
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        return True, cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    def release(self):
        try:
            self._picam.stop()
        except Exception:
            pass
        try:
            self._picam.close()
        except Exception:
            pass

    # 兼容 cv2.VideoCapture 的常用调用
    def isOpened(self):
        return True

    def set(self, *args, **kwargs):
        return False

    def get(self, *_args):
        return 0

    def grab(self):
        ok, _ = self.read()
        return ok


class OpenCvSource:
    """OpenCV VideoCapture 封装（Windows 摄像头 / UVC 摄像头）。"""

    def __init__(self, index, width, height, backend=None):
        if backend is None:
            if sys.platform == "win32":
                backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
            elif sys.platform == "darwin":
                backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
            else:
                backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
        else:
            backends = [backend]
        self.cap = None
        for be in backends:
            cap = cv2.VideoCapture(index, be)
            if cap.isOpened():
                self.cap = cap
                break
            cap.release()
        if self.cap is None:
            self.cap = cv2.VideoCapture(index)  # 最后再试默认后端
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self):
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return False, None
        return True, frame

    def release(self):
        try:
            self.cap.release()
        except Exception:
            pass

    def isOpened(self):
        return self.cap is not None and self.cap.isOpened()


def open_camera(index=0, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, backend="auto",
                exposure_compensation=0.0):
    """打开摄像头；失败返回 None。"""
    index = int(index)
    if backend in ("auto", "picamera2") and _picamera2_available():
        try:
            return PiCamera2Source(index, width, height, exposure_compensation)
        except Exception as e:
            print("[camera] Picamera2 打开相机 %s 失败: %s" % (index, e))
            if backend == "picamera2":
                return None
    if backend == "picamera2":
        return None
    src = OpenCvSource(index, width, height)
    return src if src.isOpened() else None


def describe_environment():
    """给启动日志用：报告识别到的相机。"""
    info = list_cameras()
    lines = ["[camera] picamera2 可用: %s" % _picamera2_available()]
    if info:
        for cam in info:
            lines.append("[camera] #%s %s (%s)" % (cam.get("Num"), cam.get("Model"), cam.get("Id", "")))
    else:
        lines.append("[camera] 未检测到 Picamera2 相机（将尝试 OpenCV 后端）")
    return "\n".join(lines)
