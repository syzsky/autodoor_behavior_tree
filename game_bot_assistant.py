#!/usr/bin/env python3
"""
AutoDoor AI 挂机助手 - 完整集成版
集成AutoDoor原始项目 + AI行为树生成 + VLM视觉监控
"""
import json
import urllib.request
import os
import sys
import subprocess
import time
import base64
import io
import logging
import threading
from pathlib import Path
from datetime import datetime
from queue import Queue
import argparse

# ============ 配置 ============
class Config:
    # API配置
    API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
    API_KEY = "sk-0GNMHbHn3pxsNSxN18CSxpkRagYMeojoRViTNCvcw2IgtbQ4"
    MODEL = "agnes-2.5-flash"
    
    # AutoDoor路径
    AUTO_DOOR_PATH = r"C:\Program Files\AutoDoor\autodoor.exe"
    
    # 项目路径
    PROJECTS_DIR = Path.home() / "autodoor_projects"
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR = PROJECTS_DIR / "screenshots"
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR = PROJECTS_DIR / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    GAMES_DIR = Path.home() / "games"
    SCREENSHOT_INTERVAL = 5

# ============ 日志系统 ============
class Logger:
    def __init__(self, log_file=None, silent=False):
        self.log_dir = Config.LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        if log_file:
            self.log_file = self.log_dir / log_file
        else:
            self.log_file = self.log_dir / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        self.silent = silent
        
        self.logger = logging.getLogger("GameBot")
        self.logger.setLevel(logging.DEBUG)
        
        fh = logging.FileHandler(self.log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        if not silent:
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
    
    def info(self, msg):
        self.logger.info(msg)
        if not self.silent:
            print(f"[INFO] {msg}")
    
    def warning(self, msg):
        self.logger.warning(msg)
        if not self.silent:
            print(f"[WARN] {msg}")
    
    def error(self, msg):
        self.logger.error(msg)
        if not self.silent:
            print(f"[ERROR] {msg}")

# ============ AI API ============
def call_api(system_prompt, user_message, max_tokens=2000, image_b64=None, logger=None):
    messages = [{"role": "system", "content": system_prompt}]
    
    if image_b64:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_message},
                {"type": "image_url", 
                 "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "low"}}
            ]
        })
    else:
        messages.append({"role": "user", "content": user_message})
    
    payload = {
        "model": Config.MODEL,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "messages": messages
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        Config.API_URL, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {Config.API_KEY}"},
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=90 if image_b64 else 60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"].get("content", "").strip()
                return extract_json(content), content
            return None, result.get("error", "Unknown")
    except Exception as e:
        if logger:
            logger.error(f"API调用失败: {e}")
        return None, str(e)

def extract_json(text):
    text = text.strip()
    if not text or text[0] != '{':
        return None
    
    depth = 0
    end = 0
    for i, c in enumerate(text):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    
    if end == 0:
        return None
    
    try:
        return json.loads(text[:end])
    except:
        return None

# ============ 截图模块 ============
def capture_screenshot(region=None, logger=None):
    try:
        from PIL import Image, ImageGrab
        if region:
            img = ImageGrab.grab(bbox=region)
        else:
            img = ImageGrab.grab()
        return img
    except ImportError:
        if logger:
            logger.error("需要安装PIL: pip install Pillow")
        return None
    except Exception as e:
        if logger:
            logger.error(f"截图失败: {e}")
        return None

def screenshot_to_base64(img, max_size=512):
    if img is None:
        return None
    img_copy = img.copy()
    img_copy.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    if img_copy.mode == 'RGBA':
        img_copy = img_copy.convert('RGB')
    buffered = io.BytesIO()
    img_copy.save(buffered, format="PNG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode()

# ============ 行为树生成器 ============
class TreeGenerator:
    def __init__(self, logger):
        self.logger = logger
    
    def generate_intent(self, description):
        self.logger.info("阶段1: 意图分析...")
        
        system = """输出JSON：{"task_summary":"任务摘要","loop":true,"phases":[{"name":"阶段名","description":"阶段描述","node_types":["节点类型"]}],"window":"窗口标题"}
只输出JSON，不输出其他内容。"""
        
        plan, raw = call_api(system, description, 800, logger=self.logger)
        
        if plan and 'task_summary' in plan:
            self.logger.info(f"✓ 意图分析成功: {plan['task_summary'][:50]}...")
            return plan
        else:
            self.logger.error(f"✗ 意图分析失败")
            return None
    
    def generate_structure(self, plan):
        self.logger.info("阶段2: 节点选型...")
        
        system = """输出JSON：{"nodes":[{"id":"node_x","type":"NodeType","config":{},"children":["child_id"],"empty_params":[]}]}
规则：第一个节点id必须是node_start，type必须是StartNode。条件节点必须有子节点。
可用节点：StartNode, SequenceNode, SelectorNode, OCRConditionNode, ImageConditionNode, NumberConditionNode, KeyPressNode, MouseClickNode, MouseMoveNode, DelayNode, ScriptNode
只输出JSON。"""
        
        structure, raw = call_api(system, f"计划：{json.dumps(plan, ensure_ascii=False)}", 2000, logger=self.logger)
        
        if structure and 'nodes' in structure and len(structure['nodes']) > 0:
            root = structure['nodes'][0]
            if root.get('id') == 'node_start' and root.get('type') == 'StartNode':
                self.logger.info(f"✓ 节点选型成功: {len(structure['nodes'])} 节点")
                return structure
            else:
                for node in structure['nodes']:
                    if node.get('id') == 'node_start' and node.get('type') == 'StartNode':
                        structure['nodes'].insert(0, structure['nodes'].pop(structure['nodes'].index(node)))
                        self.logger.info(f"✓ 节点选型成功: {len(structure['nodes'])} 节点")
                        return structure
        else:
            self.logger.error(f"✗ 节点选型失败")
        return None
    
    def generate_tree(self, structure):
        self.logger.info("阶段3: 生成tree.json...")
        
        system = """输出JSON：{"version":"2.0","format_type":"behavior_tree_editor","canvas":{"name":"","description":""},"root_node":"node_start","nodes":{"node_id":{"id":"node_id","type":"NodeType","name":"名称","enabled":true,"config":{},"position":{"x":400,"y":100},"children":[]}},"connections":[{"parent_id":"p","child_id":"c"}]}
布局：Root在(400,50)，每层Y+100，兄弟X间距200。条件节点必须有子节点。
只输出JSON。"""
        
        tree, raw = call_api(system, f"structure：{json.dumps(structure, ensure_ascii=False)}", 3000, logger=self.logger)
        
        if tree and 'nodes' in tree:
            errors = []
            if tree.get('root_node') != 'node_start':
                errors.append("根节点ID错误")
            elif tree['nodes'].get('node_start', {}).get('type') != 'StartNode':
                errors.append("根节点类型错误")
            
            if errors:
                self.logger.error(f"✗ 树验证失败: {errors}")
                return None
            
            self.logger.info(f"✓ 树生成成功: {len(tree['nodes'])} 节点")
            return tree
        else:
            self.logger.error(f"✗ 树生成失败")
            return None
    
    def validate_tree(self, tree):
        self.logger.info("验证行为树结构...")
        
        errors = []
        
        if tree.get('root_node') not in tree.get('nodes', {}):
            errors.append("根节点不存在")
        elif tree['nodes'][tree['root_node']]['type'] != 'StartNode':
            errors.append("根节点不是StartNode")
        
        condition_types = ['OCRConditionNode', 'ImageConditionNode', 'NumberConditionNode', 'ColorConditionNode']
        for nid, node in tree['nodes'].items():
            if node['type'] in condition_types and not node.get('children'):
                errors.append(f"条件节点 {nid} 无子节点")
        
        node_ids = set(tree['nodes'].keys())
        for conn in tree.get('connections', []):
            if conn['parent_id'] not in node_ids or conn['child_id'] not in node_ids:
                errors.append(f"连接引用无效: {conn}")
        
        if errors:
            self.logger.error(f"✗ 验证失败: {errors}")
            return False
        
        self.logger.info("✓ 结构验证通过")
        return True

# ============ 视觉监控 ============
class VisionMonitorThread(threading.Thread):
    def __init__(self, logger, interval=5, game_state_callback=None):
        super().__init__(daemon=True)
        self.logger = logger
        self.interval = interval
        self.game_state_callback = game_state_callback
        self.is_running = False
        self.screenshot_count = 0
        self.last_hp = 100
        self.state_queue = Queue()
    
    def run(self):
        self.is_running = True
        self.logger.info("视觉监控线程启动")
        
        while self.is_running:
            try:
                analysis = self.analyze_screen()
                if analysis:
                    self.screenshot_count += 1
                    if self.game_state_callback:
                        self.game_state_callback(analysis)
                    self.state_queue.put(analysis)
                    
                    if self.screenshot_count % 12 == 0:
                        self.logger.info(
                            f"监控第{self.screenshot_count}次 | "
                            f"HP:{analysis.get('hp_percent', '?')}% | "
                            f"红名:{analysis.get('red_name_detected', False)} | "
                            f"怪物:{analysis.get('monster_nearby', False)}"
                        )
                
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                self.logger.info("监控已停止")
                break
            except Exception as e:
                self.logger.error(f"监控异常: {e}")
                time.sleep(5)
    
    def analyze_screen(self):
        img = capture_screenshot(logger=self.logger)
        if not img:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img.save(Config.SCREENSHOT_DIR / f"screen_{timestamp}.png")
        
        img_b64 = screenshot_to_base64(img)
        if not img_b64:
            return None
        
        prompt = """你是传奇游戏视觉分析专家。分析这张游戏截图，返回JSON：
{"hp_percent":50,"mp_percent":80,"red_name_detected":false,"monster_nearby":true,"backpack_full":false,"npc_position":[400,300],"task_hint":"任务目标","nearby_enemies":3}

检测要点：
1. 左上角血量条 - 估算百分比
2. 屏幕中央/周围 - 检测怪物和玩家
3. 右上角 - 检测背包状态
4. 对话框文字 - 读取任务提示
5. 名字颜色 - 红色表示敌对玩家"""
        
        self.logger.debug("VLM分析中...")
        result, raw = call_api(prompt, "请分析这张游戏截图", 1000, image_b64=img_b64, logger=self.logger)
        
        if result:
            return result
        else:
            self.logger.warning(f"VLM分析失败: {raw[:50]}")
            return None
    
    def stop(self):
        self.is_running = False
        self.logger.info("视觉监控线程已停止")
    
    def get_latest_state(self):
        try:
            return self.state_queue.get_nowait()
        except:
            return None

# ============ 动作执行器 ============
class ActionExecutor:
    def __init__(self, logger):
        self.logger = logger
        self.is_active = False
    
    def execute(self, action, params=None):
        self.is_active = True
        self.logger.info(f"执行动作: {action}")
        
        try:
            if action == "use_potion":
                self._press_key(params.get('key', '1') if params else '1')
            elif action == "flee":
                self._press_key('esc')
                time.sleep(0.5)
                self._press_key('s')
                time.sleep(1)
                self._press_key('s', release=True)
            elif action == "return_city":
                self._press_key('t')
                time.sleep(1)
                self._press_key('enter')
            elif action == "find_monster":
                import random
                for _ in range(3):
                    direction = random.choice(['w', 'a', 's', 'd'])
                    self._press_key(direction)
                    time.sleep(0.5)
                    self._press_key(direction, release=True)
            elif action == "click_npc":
                if params and 'x' in params and 'y' in params:
                    self._move_mouse(params['x'], params['y'])
                    time.sleep(0.1)
                    self._press_key('lbutton')
            else:
                self.logger.warning(f"未知动作: {action}")
        except Exception as e:
            self.logger.error(f"动作执行失败: {e}")
        finally:
            self.is_active = False
    
    def _press_key(self, key, release=False):
        try:
            import pyautogui
            if release:
                pyautogui.keyUp(key)
            else:
                pyautogui.keyDown(key)
                time.sleep(0.1)
                pyautogui.keyUp(key)
        except ImportError:
            self.logger.warning("需要安装pyautogui")
    
    def _move_mouse(self, x, y):
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=0.1)
        except ImportError:
            self.logger.warning("需要安装pyautogui")

# ============ 主程序 ============
class GameBotAssistant:
    def __init__(self, background=False, silent=False):
        self.background = background
        self.logger = Logger(silent=silent or background)
        self.tree_generator = TreeGenerator(self.logger)
        self.vision_monitor = None
        self.action_executor = ActionExecutor(self.logger)
        self.is_running = False
        
        self.current_game = None
        self.current_project_dir = None
    
    def start(self):
        if self.background:
            self.logger.info("后台模式启动")
            self.run_background()
        else:
            self.logger.info("交互模式启动")
            self.run_interactive()
    
    def run_interactive(self):
        self.welcome()
        
        game_path = self.setup_game()
        if not game_path:
            self.logger.error("未选择游戏")
            return
        self.current_game = game_path
        self.logger.info(f"游戏: {game_path}")
        
        self.logger.info("启动游戏和AutoDoor...")
        self.open_app(game_path)
        time.sleep(2)
        self.open_app(Config.AUTO_DOOR_PATH)
        time.sleep(5)
        
        self.chat_with_ai()
        
        self.start_vision_monitor()
        
        self.is_running = True
        self.logger.info("按 Ctrl+C 停止")
        
        try:
            while self.is_running:
                time.sleep(1)
                state = self.vision_monitor.get_latest_state() if self.vision_monitor else None
                if state:
                    self.handle_state_change(state)
        except KeyboardInterrupt:
            self.logger.info("用户停止")
        finally:
            self.stop()
    
    def run_background(self):
        self.logger.info("后台挂机模式启动")
        
        self.auto_load_project()
        
        if not self.current_game:
            self.logger.error("未找到游戏配置")
            return
        
        self.logger.info(f"游戏: {self.current_game}")
        
        self.logger.info("启动游戏和AutoDoor...")
        self.open_app(self.current_game)
        time.sleep(2)
        self.open_app(Config.AUTO_DOOR_PATH)
        time.sleep(5)
        
        self.start_vision_monitor()
        
        self.is_running = True
        self.logger.info(f"后台监控已启动，项目目录: {self.current_project_dir}")
        self.logger.info(f"日志文件: {self.logger.log_file}")
        
        try:
            while self.is_running:
                time.sleep(5)
                state = self.vision_monitor.get_latest_state() if self.vision_monitor else None
                if state:
                    self.handle_state_change(state)
        except KeyboardInterrupt:
            self.logger.info("用户停止")
        finally:
            self.stop()
    
    def welcome(self):
        print("""
╔══════════════════════════════════════════════════════════╗
║         AutoDoor AI 挂机助手 v7.0 完整版                 ║
║                                                          ║
║  集成AutoDoor原始项目 + AI行为树生成 + VLM视觉监控       ║
║                                                          ║
║  功能：                                                 ║
║  1. AI对话生成行为树 → 自动写入AutoDoor项目目录          ║
║  2. VLM视觉监控 → 实时分析游戏画面                      ║
║  3. 自动执行动作 → 喝药/逃跑/回城                       ║
║  4. 后台运行模式 → 不干扰前台操作                       ║
║                                                          ║
║  用法：                                                 ║
║  python game_bot_assistant.py          # 交互模式        ║
║  python game_bot_assistant.py --bg     # 后台模式        ║
║  python game_bot_assistant.py --bg --silent  # 静默后台  ║
╚══════════════════════════════════════════════════════════╝
""")
    
    def setup_game(self):
        print("\n📁 扫描游戏目录...")
        games = self.find_games(Config.GAMES_DIR)
        if games:
            print("找到游戏:")
            for i, g in enumerate(games, 1):
                print(f"  {i}. {os.path.basename(g)}")
            choice = input("\n选择 (序号): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(games):
                    return games[idx]
        game_path = input("\n请输入游戏路径: ").strip()
        return game_path if game_path and os.path.exists(game_path) else None
    
    def find_games(self, directory):
        games = []
        if not os.path.exists(directory):
            return games
        for f in os.listdir(directory):
            if f.endswith('.exe'):
                games.append(os.path.join(directory, f))
        return games
    
    def open_app(self, path):
        try:
            subprocess.Popen(path, shell=True)
            time.sleep(2)
            return True
        except:
            return False
    
    def chat_with_ai(self):
        print("\n" + "="*60)
        print("💬 AI助手 - 描述你的挂机需求")
        print("="*60)
        print("\n示例: '传奇挂机，血量低于30%喝药，红名逃跑'")
        print("输入 'vision' 启动视觉监控")
        print("输入 'quit' 退出\n")
        
        while True:
            try:
                user_input = input("👤 你: ").strip()
            except EOFError:
                break
            
            if user_input.lower() in ['quit', 'exit', '退出']:
                break
            
            if user_input.lower() == 'vision':
                self.start_vision_monitor()
                continue
            
            if not user_input:
                continue
            
            print("\n🤖 生成行为树...")
            
            plan = self.tree_generator.generate_intent(user_input)
            if not plan:
                print("✗ 意图分析失败"); continue
            print(f"✓ 理解: {plan.get('task_summary', '')[:50]}...")
            
            structure = self.tree_generator.generate_structure(plan)
            if not structure:
                print("✗ 节点选型失败"); continue
            print(f"✓ 节点: {len(structure['nodes'])} 个")
            
            tree = self.tree_generator.generate_tree(structure)
            if not tree:
                print("✗ 树生成失败"); continue
            print(f"✓ 树: {len(tree['nodes'])} 节点")
            
            if not self.tree_generator.validate_tree(tree):
                print("✗ 验证失败"); continue
            
            project_dir = self.save_to_autodoor(tree, plan, structure, user_input)
            
            print(f"\n✅ 完成！")
            print(f"📁 项目已保存到AutoDoor项目目录: {project_dir}")
            print(f"\n下一步:")
            print(f"  1. 打开AutoDoor，加载 {project_dir}/tree.json")
            print(f"  2. 输入 'vision' 启动视觉监控")
    
    def save_to_autodoor(self, tree, plan, structure, description):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = description.replace(" ", "_")[:30]
        project_dir = Config.PROJECTS_DIR / f"{safe_name}_{timestamp}"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        (project_dir / "tree.json").write_text(json.dumps(tree, ensure_ascii=False, indent=2))
        (project_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2))
        (project_dir / "structure.json").write_text(json.dumps(structure, ensure_ascii=False, indent=2))
        
        metadata = {
            "created_at": datetime.now().isoformat(),
            "description": description,
            "game_type": "legend",
            "node_count": len(tree['nodes']),
            "files": ["tree.json", "plan.json", "structure.json"]
        }
        (project_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        
        self.current_project_dir = project_dir
        self.logger.info(f"✓ 项目已保存: {project_dir}")
        
        return project_dir
    
    def auto_load_project(self):
        projects = list(Config.PROJECTS_DIR.glob("*/tree.json"))
        if projects:
            latest = max(projects, key=lambda p: p.stat().st_mtime)
            project_dir = latest.parent
            self.logger.info(f"自动加载项目: {project_dir}")
            
            meta_file = project_dir / "metadata.json"
            if meta_file.exists():
                meta = json.loads(meta_file.read_text())
                self.current_game = meta.get('game_path', Config.GAMES_DIR / "game.exe")
            
            self.current_project_dir = project_dir
    
    def start_vision_monitor(self):
        if self.vision_monitor:
            self.vision_monitor.stop()
        
        self.vision_monitor = VisionMonitorThread(
            logger=self.logger,
            interval=Config.SCREENSHOT_INTERVAL,
            game_state_callback=self.handle_state_change
        )
        self.vision_monitor.start()
        self.logger.info("视觉监控已启动")
    
    def handle_state_change(self, state):
        hp = state.get('hp_percent', 100)
        
        if hp < 30:
            self.action_executor.execute("use_potion")
        
        if state.get('red_name_detected'):
            self.action_executor.execute("flee")
        
        if state.get('backpack_full'):
            self.action_executor.execute("return_city")
        
        if not state.get('monster_nearby'):
            self.action_executor.execute("find_monster")
    
    def stop(self):
        self.is_running = False
        if self.vision_monitor:
            self.vision_monitor.stop()
        self.logger.info("程序已停止")

def main():
    parser = argparse.ArgumentParser(description='AutoDoor AI 挂机助手')
    parser.add_argument('--bg', action='store_true', help='后台运行模式')
    parser.add_argument('--silent', action='store_true', help='静默模式')
    parser.add_argument('--game', type=str, help='指定游戏路径')
    args = parser.parse_args()
    
    app = GameBotAssistant(
        background=args.bg,
        silent=args.silent or args.bg
    )
    
    if args.game:
        app.current_game = args.game
        app.start()
    else:
        app.start()

if __name__ == "__main__":
    main()
