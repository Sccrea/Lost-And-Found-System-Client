# -*- coding: utf-8 -*-
"""终端心跳 + 远程开柜指令。

每 HEARTBEAT_SEC 秒向服务端上报一次（服务端据此判断在线），
同时取回网页端下发的开柜指令并执行，执行结果再回报给服务端。
"""

import threading

import config
import network_manager
import open_lock


def _execute(command):
    """执行一条指令，返回 (ok, message)。"""
    action = command.get("action")
    locker_id = command.get("locker_id")
    if action != "open":
        return False, "未知指令: %s" % action
    try:
        open_lock.open_lock(lock_number=int(locker_id))
        return True, "已下发开锁指令（柜号 %s）" % locker_id
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


def _loop(stop_event):
    while not stop_event.is_set():
        try:
            data = network_manager.heartbeat()
            for command in data.get("commands", []):
                ok, message = _execute(command)
                try:
                    network_manager.report_command(int(command["id"]), ok, message)
                except Exception as exc:
                    print("[心跳] 回报指令结果失败:", exc)
                print("[心跳] 执行远程指令 #%s 柜%s -> %s" % (command.get("id"), command.get("locker_id"), ok))
        except Exception as exc:
            print("[心跳] 上报失败:", exc)
        stop_event.wait(max(3.0, float(getattr(config, "HEARTBEAT_SEC", 10))))


def start():
    """启动后台心跳线程（daemon）。"""
    stop_event = threading.Event()
    thread = threading.Thread(target=_loop, args=(stop_event,), daemon=True)
    thread.start()
    return stop_event
