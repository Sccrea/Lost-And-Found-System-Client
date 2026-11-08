# lostfound/camera.py
import cv2
import time

class UVCCamera:
    def __init__(self, index, width, height, fps):
        self.cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError("无法打开摄像头，检查 /dev/video* 和 USB 3.0 口")

        # 强制 MJPEG，避免 YUYV 回退打满 USB 2.0 带宽
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 减小缓冲，降低端到端延迟

        time.sleep(0.5)  # 等自动曝光稳定

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        return frame

    def release(self):
        self.cap.release()