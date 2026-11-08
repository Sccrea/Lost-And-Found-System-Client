import os
import sys
import json

# 判断是否在打包环境中
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 各子目录路径
FILES_DIR = os.path.join(BASE_DIR, "files")
TEMP_DIR = os.path.join(FILES_DIR, "temp")
CONFIG_JSON_PATH = os.path.join(FILES_DIR, "config.json")

# 确保目录存在
os.makedirs(TEMP_DIR, exist_ok=True)

# 默认配置（可扩展其他项）
DEFAULT_CONFIG = {
    "TERMINAL_ID": "0",
    "LOCATION": "1号楼1层",
    "SERVER_URL": "https://127.0.0.1:5000",
    "SERVER_CERT_PATH": "",
    "ENABLE_LOCK": True,
    # ---- 物品识别（新增）----
    "ENABLE_RECOGNITION": True,   # 关闭后拍照不做识别，只保留拍照流程
    "CAMERA_INDEX": 0,            # 摄像头序号，多摄像头时改这里
    "SCORE_THRESHOLD": 0.5,       # 置信度阈值
    "CAMERA_TEST_IMAGE": ""       # 无摄像头联调用：填图片路径，拍照时直接用该图
}

def ensure_config():
    """确保 config.json 存在且有效，返回配置字典"""
    if not os.path.exists(CONFIG_JSON_PATH):
        with open(CONFIG_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_JSON_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        # 补全缺失的字段（遍历 DEFAULT_CONFIG）
        for key, default_val in DEFAULT_CONFIG.items():
            if key not in config_data:
                config_data[key] = default_val
        return config_data
    except Exception as e:
        print(f"读取 config.json 失败，使用默认配置并覆盖原文件: {e}")
        with open(CONFIG_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
        return DEFAULT_CONFIG.copy()

# 加载配置（模块导入时自动执行）
_config = ensure_config()
TERMINAL_ID = _config.get("TERMINAL_ID", DEFAULT_CONFIG["TERMINAL_ID"])
LOCATION = _config.get("LOCATION", DEFAULT_CONFIG["LOCATION"])
SERVER_URL = _config.get("SERVER_URL", DEFAULT_CONFIG["SERVER_URL"])
SERVER_CERT_PATH = _config.get("SERVER_CERT_PATH", DEFAULT_CONFIG["SERVER_CERT_PATH"])
if SERVER_CERT_PATH and not os.path.isabs(SERVER_CERT_PATH):
    SERVER_CERT_PATH = os.path.join(BASE_DIR, SERVER_CERT_PATH)
ENABLE_LOCK = _config.get("ENABLE_LOCK", DEFAULT_CONFIG["ENABLE_LOCK"])
ENABLE_RECOGNITION = bool(_config.get("ENABLE_RECOGNITION", True))
CAMERA_INDEX = int(_config.get("CAMERA_INDEX", 0))
SCORE_THRESHOLD = float(_config.get("SCORE_THRESHOLD", 0.5))
CAMERA_TEST_IMAGE = _config.get("CAMERA_TEST_IMAGE", "") or ""
if CAMERA_TEST_IMAGE and not os.path.isabs(CAMERA_TEST_IMAGE):
    CAMERA_TEST_IMAGE = os.path.join(BASE_DIR, CAMERA_TEST_IMAGE)
