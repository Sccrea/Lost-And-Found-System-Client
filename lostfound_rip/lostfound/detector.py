# lostfound/detector.py
import cv2
import numpy as np
import onnxruntime as ort

class OnnxYoloDetector:
    """ONNX Runtime CPU 推理。后续换 NCNN 只需替换本类。"""
    def __init__(self, model_path, input_size=640, score=0.55, nms=0.5):
        self.input_size = input_size
        self.score = score
        self.nms = nms
        self.session = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    def detect(self, frame_bgr):
        # letterbox 预处理
        img, ratio, (dw, dh) = self._letterbox(frame_bgr, self.input_size)
        blob = img[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        blob = np.expand_dims(blob, 0)

        outputs = self.session.run(None, {self.input_name: blob})
        return self._postprocess(outputs[0], ratio, dw, dh, frame_bgr.shape)

    def _letterbox(self, img, new_size):
        h, w = img.shape[:2]
        r = min(new_size / h, new_size / w)
        nh, nw = int(round(h * r)), int(round(w * r))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        dw, dh = (new_size - nw) / 2, (new_size - nh) / 2
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right,
            cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )
        return padded, r, (left, top)

    def _postprocess(self, pred, ratio, pad, orig_shape):
        # pred shape: (1, 84, 8400) 典型 YOLO11 输出
        pred = np.squeeze(pred).T  # (8400, 84)
        boxes, scores, class_ids = [], [], []

        for row in pred:
            cls_scores = row[4:]
            cid = int(np.argmax(cls_scores))
            conf = float(cls_scores[cid])
            if conf < self.score:
                continue
            cx, cy, bw, bh = row[:4]
            x = (cx - bw / 2 - pad[0]) / ratio
            y = (cy - bh / 2 - pad[1]) / ratio
            w, h = bw / ratio, bh / ratio
            boxes.append([int(x), int(y), int(w), int(h)])
            scores.append(conf)
            class_ids.append(cid)

        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(
            boxes, scores, self.score, self.nms
        )
        results = []
        for i in np.array(indices).flatten():
            results.append((*boxes[i], scores[i], class_ids[i]))
        return results