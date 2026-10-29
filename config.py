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
    "AUTH_METHOD": 0,
    "ENABLE_LOCK": True
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
AUTH_METHOD = _config.get("AUTH_METHOD", DEFAULT_CONFIG["AUTH_METHOD"])
ENABLE_LOCK = _config.get("ENABLE_LOCK", DEFAULT_CONFIG["ENABLE_LOCK"])
