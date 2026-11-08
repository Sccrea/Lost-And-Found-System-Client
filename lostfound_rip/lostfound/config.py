# lostfound/config.py

REPORT_URL = "http://192.168.1.100:8080/lost-item"
COOLDOWN_SEC = 30

# 摄像头：先 640x480 @ 15fps 起步；USB 必须插在蓝色 USB 3.0 口
CAM_INDEX = 0
CAM_WIDTH = 640
CAM_HEIGHT = 480
CAM_FPS = 15

# 推理：ONNX 模型路径；YOLO11n 输入通常为 640x640
MODEL_PATH = "models/yolo11n.onnx"
INPUT_SIZE = 640
SCORE_THRESHOLD = 0.55
NMS_THRESHOLD = 0.5

TARGET_CLASSES = {24, 26, 28, 39, 41, 67, 73}

COCO_LABELS = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck","boat",
    "traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat",
    "dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack",
    "umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball",
    "kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket",
    "bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple",
    "sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair",
    "couch","potted plant","bed","dining table","toilet","tv","laptop","mouse",
    "remote","keyboard","cell phone","microwave","oven","toaster","sink",
    "refrigerator","book","clock","vase","scissors","teddy bear","hair drier",
    "toothbrush"
]