# lostfound/reporter.py
import time
import requests

class LostItemReporter:
    def __init__(self, url, cooldown_sec=30):
        self._url = url
        self._cooldown = cooldown_sec
        self._last = {}

    def should_report(self, category):
        now = time.time()
        if category in self._last and now - self._last[category] < self._cooldown:
            return False
        self._last[category] = now
        return True

    def report(self, label, score, box):
        payload = {
            "event": "lost_item_detected",
            "label": label,
            "score": round(score, 3),
            "box": box,
            "ts": time.time(),
        }
        try:
            resp = requests.post(self._url, json=payload, timeout=5)
            print("[report]", resp.status_code, label)
        except Exception as e:
            print("[report] failed:", e)