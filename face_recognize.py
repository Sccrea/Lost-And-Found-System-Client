"""Camera capture for face recognition performed by the server."""

import time

import cv2

import camera_source
import config
import network_manager


class FaceRecognition:
    """Capture camera frames locally and ask the configured server to identify them."""

    def __init__(self, camera_index=None, request_interval=0.5):
        # 默认用配置里指定的人脸摄像头（树莓派上通常是 1 号相机）
        self.camera_index = config.FACE_CAMERA_INDEX if camera_index is None else camera_index
        self.request_interval = request_interval

    def run_recognition(self):
        """Return the recognized user's name, or ``None`` when cancelled/unavailable."""
        cap = camera_source.open_camera(self.camera_index, backend=config.CAMERA_BACKEND)
        if cap is None:
            print("[错误] 无法打开摄像头（人脸相机 %s）" % self.camera_index)
            return None

        recognized_name = None
        next_request_at = 0.0
        window_name = "Server Face Recognition, Press Q to Quit"

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                now = time.monotonic()
                status = "Searching on server..."
                if now >= next_request_at:
                    ok, encoded = cv2.imencode(
                        ".jpg", frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 80],
                    )
                    if not ok:
                        status = "Could not encode camera frame"
                    else:
                        recognized_name = network_manager.recognize_face(encoded.tobytes())
                        next_request_at = time.monotonic() + self.request_interval
                        if recognized_name:
                            status = f"Recognized: {recognized_name}"
                        else:
                            status = "No registered face recognized"

                cv2.putText(
                    frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 0) if recognized_name else (0, 0, 255), 2,
                )
                cv2.imshow(window_name, frame)

                if recognized_name:
                    cv2.waitKey(1500)
                    break
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()

        return recognized_name
