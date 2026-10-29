import requests
import config

SERVER_URL = config.SERVER_URL

def get_lockers_status():
    resp = requests.get(f"{SERVER_URL}/api/lockers", params={'terminal_id': config.TERMINAL_ID}, timeout=5, verify=False)
    resp.raise_for_status()
    data = resp.json()
    # 将 JSON 返回的字符串键转为整数键
    return {int(k): v for k, v in data.items()}

def store_item(locker_id, photo_path):
    """存物：上传照片和数据，失败时抛出异常"""
    url = f"{SERVER_URL}/api/store"
    with open(photo_path, 'rb') as f:
        files = {'photo': f}
        data = {
            'terminal_id': config.TERMINAL_ID,
            'locker_id': locker_id
        }
        resp = requests.post(url, data=data, files=files, timeout=10, verify=False)
        resp.raise_for_status()
        return resp.json()

def take_item(locker_id, taker_name):
    """取物：通知服务端更新记录，失败时抛出异常"""
    url = f"{SERVER_URL}/api/take"
    payload = {
        'terminal_id': config.TERMINAL_ID,
        'locker_id': locker_id,
        'taker_name': taker_name,
    }
    resp = requests.post(url, json=payload, timeout=5, verify=False)
    resp.raise_for_status()
    return resp.json()

def recognize_face(image_bytes):
    """Send one camera frame to the server and return the recognized name, if any."""
    files = {"image": ("camera-frame.jpg", image_bytes, "image/jpeg")}
    resp = requests.post(
        f"{SERVER_URL}/api/face-recognize",
        files=files,
        timeout=60,
        verify=False,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("recognized") and isinstance(data.get("name"), str):
        return data["name"]
    return None

def get_photo_url(photo_name):
    """获取照片的完整URL"""
    return f"{SERVER_URL}/images/{photo_name}"

def register_terminal():
    url = f"{SERVER_URL}/api/register"
    payload = {
        'terminal_id': config.TERMINAL_ID,
        'location': config.LOCATION
    }
    resp = requests.post(url, json=payload, timeout=5, verify=False)
    resp.raise_for_status()
    return resp.json()
