# lostfound/pipeline.py
import cv2
import time
import lostfound.config as cfg
from lostfound.camera import UVCCamera
from lostfound.detector import OnnxYoloDetector
from lostfound.reporter import LostItemReporter

def run():
    cam = UVCCamera(cfg.CAM_INDEX, cfg.CAM_WIDTH, cfg.CAM_HEIGHT, cfg.CAM_FPS)
    detector = OnnxYoloDetector(
        cfg.MODEL_PATH, cfg.INPUT_SIZE, cfg.SCORE_THRESHOLD, cfg.NMS_THRESHOLD
    )
    reporter = LostItemReporter(cfg.REPORT_URL, cfg.COOLDOWN_SEC)
    print("[pipeline] started")

    try:
        while True:
            frame = cam.read()
            if frame is None:
                time.sleep(0.02)
                continue

            detections = detector.detect(frame)
            for x, y, w, h, score, category in detections:
                if category not in cfg.TARGET_CLASSES:
                    continue
                if not reporter.should_report(category):
                    continue
                label = (
                    cfg.COCO_LABELS[category]
                    if category < len(cfg.COCO_LABELS)
                    else str(category)
                )
                print("[detect]", label, round(score, 3), (x, y, w, h))
                reporter.report(label, score, (x, y, w, h))

                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(
                    frame, f"{label} {score:.2f}", (x, max(y - 8, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1
                )

            cv2.imshow("Lost & Found", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        detector.close()
        cam.release()
        cv2.destroyAllWindows()
        print("[pipeline] stopped")