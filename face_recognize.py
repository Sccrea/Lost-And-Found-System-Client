"""取物人脸识别：本机取帧 → 送服务端比对，预览渲染在 Tk 主窗口内。

异步接口：
    FaceRecognition().run_recognition(root, on_done)
    on_done({'status': 'ok'|'cancelled'|'error'|'no_face', 'name': ..., 'detail': ...})
"""

import threading
import time

import requests

import camera_source
import config
import network_manager
import ui_preview


class FaceRecognition:
    """Capture camera frames locally and ask the configured server to identify them."""

    def __init__(self, camera_index=None, request_interval=0.5):
        # 默认用配置里指定的人脸摄像头（树莓派上通常是 1 号相机）
        self.camera_index = config.FACE_CAMERA_INDEX if camera_index is None else camera_index
        self.request_interval = request_interval

    def run_recognition(self, root, on_done):
        """打开相机并循环请求服务端，识别到人后回调 on_done。"""
        timeout = float(getattr(config, "FACE_TIMEOUT_SEC", 30))          # 30 秒未识别人脸就返回
        idle_timeout = float(getattr(config, "PREVIEW_IDLE_TIMEOUT_SEC", 30))  # 30 秒无触摸也返回
        started = time.time()
        activity = {"last": time.time()}
        state = {
            "stop": False,
            "latest": None,      # frame_bgr
            "status": "正在打开摄像头…",
            "result": None,      # 识别成功的人名
            "error": None,
            "error_kind": None,
        }
        lock = threading.Lock()
        finished = {"done": False}

        def worker():
            # 相机在采集线程内打开：picamera2 跨线程 capture 取不到新帧
            cap = camera_source.open_camera(self.camera_index, backend=config.CAMERA_BACKEND)
            if cap is None:
                with lock:
                    state["error_kind"] = "camera"
                    state["error"] = ("无法打开人脸摄像头（序号 %s）。\n"
                                      "请检查连接或在 files/config.json 中调整 FACE_CAMERA_INDEX。"
                                      % self.camera_index)
                return
            next_request_at = 0.0
            try:
                while not state["stop"]:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        time.sleep(0.05)
                        continue
                    with lock:
                        state["latest"] = frame

                    now = time.monotonic()
                    if now < next_request_at:
                        continue
                    next_request_at = now + self.request_interval

                    ok, encoded = _encode(frame)
                    if not ok:
                        with lock:
                            state["status"] = "画面编码失败"
                        continue
                    try:
                        name = network_manager.recognize_face(encoded)
                    except requests.exceptions.RequestException as exc:
                        with lock:
                            state["error_kind"] = "server"
                            state["error"] = str(exc) or exc.__class__.__name__
                        return
                    with lock:
                        if name:
                            state["result"] = name
                            state["status"] = "识别到：%s" % name
                            return
                        state["status"] = "未识别到已登记的人脸，请正对摄像头"
            finally:
                cap.release()

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

        preview = ui_preview.CameraPreview(root, "取物 · 请正对摄像头",
                                           on_cancel=cancel, on_activity=touch)

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
                frame = state["latest"]
                status = state["status"]
                result = state["result"]
                error = state["error"]

            preview.update_frame(frame, "%s · %d 秒后自动返回" % (status, int(left)))

            if result:
                finish({"status": "ok", "name": result})
                return
            if error:
                if state.get("error_kind") == "camera":
                    finish({"status": "error", "detail": error})
                else:
                    finish({"status": "error",
                            "detail": "人脸识别服务器不可用，请检查服务器、人脸库和模型配置。\n%s"
                                      % error[:200]})
                return

            root.after(100, tick)

        root.escape_handler = cancel
        threading.Thread(target=worker, daemon=True).start()
        root.after(100, tick)


def _encode(frame, quality=80):
    import cv2

    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return False, b""
    return True, buf.tobytes()
