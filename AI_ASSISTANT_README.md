# AutoDoor AI 挂机助手 - 完整版

集成AutoDoor原始项目 + AI行为树生成 + VLM视觉监控

## 功能特性

### 1. AI行为树生成
- 自然语言描述挂机需求
- 自动生成完整行为树（3阶段：意图→节点→树）
- 自动保存到AutoDoor项目目录

### 2. VLM视觉监控
- 每5秒截图分析游戏画面
- 检测：血量、红名、怪物、背包、NPC位置
- 使用Agnes API（同一key）

### 3. 自动执行动作
- 喝药（按键1）
- 逃跑（按键ESC）
- 回城（按键T）
- 寻怪（WASD移动）

### 4. 后台运行
- `--bg` 后台模式
- `--silent` 静默模式
- 不干扰前台操作

## 使用方法

```bash
# 交互模式
python game_bot_assistant.py

# 后台模式
python game_bot_assistant.py --bg

# 静默后台（推荐长期挂机）
python game_bot_assistant.py --bg --silent

# 指定游戏路径
python game_bot_assistant.py --bg --game "C:\Games\传奇.exe"
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 输出目录

```
~/autodoor_projects/
├── {项目名}_{时间戳}/
│   ├── tree.json          # 行为树（导入AutoDoor）
│   ├── plan.json          # 任务计划
│   ├── structure.json     # 节点结构
│   └── metadata.json      # 元数据
├── screenshots/           # 截图存档
└── logs/                  # 运行日志
```

## 支持的游戏类型

- 传奇类（热血传奇、各类私服）
- 吉他江湖
- MOBA游戏
- FPS射击游戏
- 自定义游戏

## 配置

编辑 `game_bot_assistant.py` 顶部的 `Config` 类：

```python
class Config:
    API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
    API_KEY = "你的API密钥"
    MODEL = "agnes-2.5-flash"
    
    AUTO_DOOR_PATH = r"C:\Program Files\AutoDoor\autodoor.exe"
    GAMES_DIR = Path.home() / "games"
    
    SCREENSHOT_INTERVAL = 5  # 截图间隔（秒）
```

## 系统要求

- Windows 10/11
- Python 3.8+
- AutoDoor已安装
- 稳定网络连接

## 依赖包

- Pillow (图像处理)
- pyautogui (按键模拟)

## 注意事项

1. 使用外挂可能违反游戏服务条款
2. 仅用于个人学习研究
3. 请遵守游戏官方规定
4. 自行承担使用风险

## 版本

v7.0 - 完整版（集成AutoDoor原始项目）
