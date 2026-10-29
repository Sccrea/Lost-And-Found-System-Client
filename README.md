# Lost-And-Found-System-Client

失物招领系统客户端，使用Python语言编写。

[WinSCP与DB Browser for SQLite下载](https://wwbwa.lanzoue.com/ipOoc3mlazpc)

## 运行与调试
### 启动
使用**Python3.8**以获得最佳支持

**运行main_app.py以启动**

安装依赖:

```bash
pip install -r requirements.txt
```

或使用国内清华大学镜像源安装:

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 调试
#### 配置文件
运行程序自动生成配置文件，位于`./files/config.json`
| 字段 | 类型 | 默认值 | 作用与意义 |
| :--- | :--- | :--- | :--- |
| **`TERMINAL_ID`** | String | `"0"` | **终端唯一标识符**。用于向服务端区分不同的失物招领终端设备（如设备序列号或自定义编号）。服务端会依据此 ID 记录物品是由哪个终端存入的，并在查询柜子状态时进行隔离。 |
| **`LOCATION`** | String | `"1号楼1层"` | **终端位置描述**。用于在主界面顶部显示（如“当前位置：1号楼1层”），同时在上传终端信息时会发送给服务端，方便管理员在后台查看设备分布。 |
| **`SERVER_URL`** | String | `"https://127.0.0.1:5000"` | **服务端接口地址**。客户端所有网络请求（存物、取物、查询状态等）都会基于此 URL 拼接路由（如 `/api/store`）。默认指向本机 HTTPS 端口，实际部署时需修改为服务端的真实 IP 和端口（例如 `https://192.168.1.100:5000`）。 |
| **`AUTH_METHOD`** | Integer | `0` | **取物认证方式**。`1`启用人脸识别；当前刷卡认证尚未实现，`0`和`2`暂不可用。人脸模型和人脸库由服务端管理。|
| **`ENABLE_LOCK`** | Boolean | `true` | **电锁功能开关**。控制实际是否通过串口操作物理电锁。若设为 `false`，点击“存物”或“取物”时，程序会跳过串口开锁指令（仅打印日志），适合**无硬件环境的开发调试**或纯软件演示模式。 |

---

**如果设备上没有连接锁硬件，请将`ENABLE_LOCK`值设为`false`以禁止发送指令到锁信息**

### 服务端人脸识别

人脸摄像头连接在客户端终端上。客户端只采集并压缩摄像头画面，然后通过 `/api/face-recognize` 把画面发送到 `SERVER_URL`；服务器负责运行 InsightFace 模型并与服务器端的人脸库比对。客户端不再安装或运行人脸识别模型。

启用前请先按服务端仓库 README 配置服务器模型和私有人脸库，然后在 `./files/config.json` 中设置：

```json
{
    "SERVER_URL": "https://服务器地址:5000",
    "AUTH_METHOD": 1
}
```

`SERVER_URL` 要填写客户端能够访问的服务器地址。识别时，客户端摄像头画面会发送给该服务器；请只在你信任并已配置好的网络与服务器上使用。

## 构建可执行文件
可用Pyinstaller编译:
```bash
pip install pyinstaller
```

```bash
pyinstaller --onefile main_app.py
```
## 函数意义解释
以下是失物招领管理系统客户端中所有函数的意义解释，按模块划分。(部分内容已过时，仅供参考)(更新时间: 2026年8月5日 3:28)

---

### 目录
1. [config.py](#1-configpy)  
2. [network_manager.py](#2-network_managerpy)  
3. [open_lock.py](#3-open_lockpy)  
4. [photo_manager.py](#4-photo_managerpy)  
5. [store_ui.py（类 `StoreUI`）](#5-store_uipy类-storeui)  
6. [take_ui.py（类 `TakeUI`）](#6-take_uipy类-takeui)  
7. [main_app.py（类 `LostAndFoundApp` 与 `main()`）](#7-main_apppy类-lostandfoundapp-与-main)

---

### 1. config.py

客户端配置管理模块，负责加载 `files/config.json` 并定义全局路径常量。

#### 全局变量

| 变量名 | 意义 |
|--------|------|
| `BASE_DIR` | 客户端可执行文件或脚本所在目录（打包环境下为 `sys.executable` 所在目录）。 |
| `FILES_DIR` | 数据存储根目录（`BASE_DIR/files/`）。 |
| `TEMP_DIR` | 临时文件目录（`FILES_DIR/temp/`），存放拍照时的临时照片。 |
| `CONFIG_JSON_PATH` | 客户端配置文件 `config.json` 的完整路径。 |
| `TERMINAL_ID` | 终端唯一标识，从 `config.json` 读取，默认为 `"0"`。 |
| `LOCATION` | 终端位置描述，从 `config.json` 读取，默认为 `"1号楼1层"`。 |
| `SERVER_URL` | 服务端基础 URL（例如 `https://127.0.0.1:5000`），从 `config.json` 读取。 |
| `AUTH_METHOD` | 预留认证方式字段，当前未使用，默认为 `0`。 |
| `ENABLE_LOCK` | 是否启用实际电锁控制（`True`/`False`），默认 `True`。 |

#### 函数

| 函数名 | 参数 | 返回值 | 意义 |
|--------|------|--------|------|
| `ensure_config()` | 无 | `dict` | 检查 `CONFIG_JSON_PATH` 是否存在且有效；若缺失或损坏则使用 `DEFAULT_CONFIG` 覆盖，并返回完整配置字典。该函数在模块导入时自动执行，填充全局变量。 |

---

### 2. network_manager.py

客户端网络通信模块，封装所有与服务端交互的 API 调用。

| 函数名 | 参数 | 返回值 | 意义 |
|--------|------|--------|------|
| `get_lockers_status()` | 无 | `dict`（键为柜号 int，值为包含 `status`、`terminal_id`、`photo_name` 的字典） | 向服务端 `GET /api/lockers` 请求当前终端下所有柜子的占用状态（0=空闲，1=已用）。 |
| `store_item(locker_id, photo_path)` | `locker_id`：int 柜号<br>`photo_path`：str 照片本地路径 | `dict`（含 `message`、`photo_name`、`id`） | 向服务端 `POST /api/store` 上传照片和柜号，完成存物操作。成功返回服务器响应。 |
| `take_item(locker_id, taker_name)` | `locker_id`：int 柜号<br>`taker_name`：str 取物人姓名 | `dict`（含 `message`） | 向服务端 `POST /api/take` 通知取物，服务端更新对应记录的取物时间和取物人。 |
| `get_photo_url(photo_name)` | `photo_name`：str 照片文件名 | `str`（完整 URL） | 根据照片文件名拼接完整的访问 URL（`{SERVER_URL}/images/{photo_name}`）。 |
| `get_all_records()` | 无 | `list`（每个元素为记录字典） | 向服务端 `GET /get_data` 获取所有存取记录（含已取），用于数据预览。 |
| `register_terminal()` | 无 | `dict`（含 `terminal_id`、`location` 等） | 向服务端 `POST /api/register` 上报当前终端的 ID 和位置，服务端记录或更新终端信息。 |

> 所有函数在请求失败时抛出 `requests.exceptions.RequestException`，调用方需处理异常。

---

### 3. open_lock.py

电锁控制模块，通过串口（RS‑485）操作锁控板。

#### 全局函数

| 函数名 | 参数 | 返回值 | 意义 |
|--------|------|--------|------|
| `crc16(data)` | `data`：bytes 或 bytearray 类型 | `int` | 计算 Modbus RTU 标准 CRC‑16 校验值（多项式 0x8005，初始 0xFFFF，输入/输出反转）。 |
| `control_lock(serial_port, device_addr, lock_num, action, duration=5)` | `serial_port`：已打开的 `serial.Serial` 对象<br>`device_addr`：int 设备地址（1‑255）<br>`lock_num`：int 锁路号（0‑7）<br>`action`：int（0=关锁，1=开锁）<br>`duration`：int 开锁持续时间（秒），默认 5 | 无 | 构造 Modbus 指令并发送至串口，控制指定锁路的开关。若 `duration>0` 则附加持续时间字段（非标准扩展）。发送后等待 100ms 并读取响应。 |
| `open_lock(lock_number)` | `lock_number`：int 锁路号（1‑8） | 无 | 根据 `config.ENABLE_LOCK` 决定是否实际开锁：若为 `True`，则打开串口 `/dev/ttyUSB0`（9600,8N1）向地址 0x00 发送开锁指令。若禁用，则仅打印柜号（调试用）。 |

---

### 4. photo_manager.py

摄像头拍照与图片预览工具。

| 函数名 | 参数 | 返回值 | 意义 |
|--------|------|--------|------|
| `take_photo()` | 无 | `bool` | 打开摄像头（索引0），显示实时画面。按 `Space` 键拍照保存至 `TEMP_DIR/a.jpg` 并返回 `True`；按 `ESC` 取消拍照返回 `False`。 |
| `show_photo_preview(photo_label, photo_path)` | `photo_label`：tkinter.Label 控件<br>`photo_path`：str 照片路径 | 无 | 读取 `photo_path` 并缩放至最大 400×300 像素，显示在 `photo_label` 上。若文件不存在则无操作。 |

---

### 5. store_ui.py（类 `StoreUI`）

存物品流程的用户界面及控制逻辑。

#### 类属性（实例）

| 属性 | 意义 |
|------|------|
| `parent` | 主应用实例（`LostAndFoundApp`），用于界面切换。 |
| `root` | Tkinter 根窗口。 |
| `photo_label` | 用于显示照片预览的 Label 控件。 |

#### 方法

| 方法名 | 参数 | 返回值 | 意义 |
|--------|------|--------|------|
| `__init__(parent_app)` | `parent_app`：主应用实例 | 无 | 保存父应用引用。 |
| `show()` | 无 | 无 | 显示存物品主界面：包含“拍照”按钮、照片预览区域和“存物品”按钮。 |
| `_clear_window()` | 无 | 无 | 清空根窗口所有子控件（用于界面切换）。 |
| `_take_photo_wrapper()` | 无 | 无 | 调用 `photo_manager.take_photo()` 拍照，若成功则更新照片预览。 |
| `_next_step()` | 无 | 无 | 检查是否已拍照，若无则提示；否则从服务端获取柜子状态，查找空闲柜子，若有则调用 `_confirm_store()`，若无则提示无空闲柜子。 |
| `_confirm_store(locker_id, temp_photo_path)` | `locker_id`：int 柜号<br>`temp_photo_path`：str 临时照片路径 | 无 | 弹出确认对话框，确认后调用 `network_manager.store_item()` 上传照片和柜号，成功后调用 `open_lock.open_lock()` 开锁，显示成功信息并返回主界面。若网络异常则提示错误。 |

---

### 6. take_ui.py（类 `TakeUI`）

取物品流程的用户界面及控制逻辑。

#### 类属性（实例）

| 属性 | 意义 |
|------|------|
| `parent` | 主应用实例。 |
| `root` | Tkinter 根窗口。 |
| `taker_name` | 暂存取物人姓名。 |
| `selected_locker_id` | 当前选中柜子的编号。 |
| `lockers_data` | 从服务端获取的最新柜子状态字典。 |
| `locker_buttons` | 存储 8 个柜子按钮的列表，用于高亮操作。 |
| `info_frame` | 显示物品详情的 Frame 容器。 |
| `name_var` | `tk.StringVar`，绑定姓名输入框。 |

#### 方法

| 方法名 | 参数 | 返回值 | 意义 |
|--------|------|--------|------|
| `__init__(parent_app)` | `parent_app`：主应用实例 | 无 | 保存父应用引用。 |
| `show_name_input()` | 无 | 无 | 显示姓名输入界面：输入框 + “下一步”按钮。 |
| `_show_locker_selection()` | 无 | 无 | 读取姓名后，调用 `network_manager.get_lockers_status()` 获取柜子状态，显示 8 个按钮（有物品绿色可点，无物品灰色禁用）。点击绿色按钮触发 `_select_locker()`。 |
| `_show_default_info()` | 无 | 无 | 在 `info_frame` 中显示“请选择上方柜子查看物品信息”的提示。 |
| `_select_locker(locker_id)` | `locker_id`：int 柜号 | 无 | 高亮选中按钮，调用 `_show_item_info()` 显示该柜子的物品信息。 |
| `_show_item_info(locker_id)` | `locker_id`：int 柜号 | 无 | 在 `info_frame` 中显示该柜子的照片（从服务端下载）、并放置“确认取物”按钮。 |
| `_download_photo(photo_name)` | `photo_name`：str 照片文件名 | `str` 或 `None` | 从服务端下载照片到 `TEMP_DIR`，成功返回本地路径，失败返回 `None`。 |
| `_confirm_take(locker_id, item)` | `locker_id`：int 柜号<br>`item`：dict（该柜子物品信息） | 无 | 弹出确认对话框，确认后调用 `network_manager.take_item()` 通知服务端，然后调用 `open_lock.open_lock()` 开锁，显示成功信息并返回主界面。 |
| `_clear_window()` | 无 | 无 | 清空根窗口所有子控件。 |

---

### 7. main_app.py（类 `LostAndFoundApp` 与 `main()`）

主应用程序入口，管理界面切换和全局状态。

#### 类 `LostAndFoundApp`

##### 类属性（实例）

| 属性 | 意义 |
|------|------|
| `root` | Tkinter 根窗口。 |
| `store_ui` | `StoreUI` 实例。 |
| `take_ui` | `TakeUI` 实例。 |

##### 方法

| 方法名 | 参数 | 返回值 | 意义 |
|--------|------|--------|------|
| `__init__(root)` | `root`：Tkinter 根窗口 | 无 | 初始化窗口标题和大小，创建 `StoreUI` 和 `TakeUI` 实例，显示主界面，并调用 `_register_terminal()` 上传终端信息。 |
| `_register_terminal()` | 无 | 无 | 调用 `network_manager.register_terminal()` 向服务端注册终端（异常时仅打印日志）。 |
| `show_main_interface()` | 无 | 无 | 显示主界面：位置标签、“取物品”和“存物品”大按钮，以及“数据预览”按钮。 |
| `_show_data_preview()` | 无 | 无 | 弹出新窗口，以表格（`ttk.Treeview`）展示所有存取记录（调用 `network_manager.get_all_records()`）。 |
| `_clear_window()` | 无 | 无 | 清空根窗口所有子控件。 |

#### 顶层函数

| 函数名 | 参数 | 返回值 | 意义 |
|--------|------|--------|------|
| `main()` | 无 | 无 | 程序入口：创建 `tk.Tk` 实例，实例化 `LostAndFoundApp`，启动 Tkinter 主事件循环。 |

---
