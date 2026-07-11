# 项目名称统一方案

> **创建日期**：2026-07-03
> **目标**：分析当前工程中项目脚本文件夹、项目名称、`tree.json`、`project.json` 中多个名称字段的来源和赋值方法，设计统一方案，保证多平台读取时不存在命名错乱问题。

***

## 一、现状分析：名称字段的来源与赋值

### 1.1 项目脚本文件夹名（硬编码常量，3 处独立定义）

| 字符串值               | 出现位置                                                                                                  | 用途                  |
| ------------------ | ----------------------------------------------------------------------------------------------------- | ------------------- |
| `scripts/script`   | `bt_utils/project_manager.py:30`、`bt_utils/resource_service.py:29`、`bt_utils/resource_importer.py:56` | Python/Bat/Shell 脚本 |
| `scripts/code`     | 同上 3 文件下一行                                                                                            | 代码片段                |
| `images/templates` | 同上                                                                                                    | 模板图片                |
| `audio/alarms`     | 同上                                                                                                    | 报警音频                |
| `subtrees`         | **仅** `bt_utils/resource_service.py:33`                                                               | 子树（importer 缺失）     |
| `data/other`       | resource\_service / resource\_importer                                                                | 其他资源                |

**问题**：3 处硬编码，且 `resource_importer.py` 的 TYPE\_DIR\_MAP 缺少 `subtree`、`other`，已与 `resource_service.py` 不同步。

### 1.2 "项目名称"实际有 4 种语义（最核心问题）

```
[用户在 NewProjectDialog 输入 name]
       │
       ├──→ project_info.name (写入 project.json)
       │
       ├──→ 文件夹名 = os.path.join(location, name)        ← editor.py:1615, 1986
       │       │
       │       └──→ os.path.basename(project_root)         ← 派生，运行时主流
       │              ├──→ TreeInstance.name               ← editor.py:458, 299
       │              ├──→ 窗口标题                        ← app.py:117
       │              ├──→ ZIP 默认文件名                   ← package_exporter.py:26
       │              └──→ README 标题                      ← package_exporter.py:59
       │
       └──→ (不会反向同步：用户重命名文件夹后，project_info.name 不变)
```

**4 种来源冲突点**：

| 调用入口                        | Tab 名来源               | 文件:行号                             |
| --------------------------- | --------------------- | --------------------------------- |
| `open_project`              | `project_info.name`   | `bt_gui/bt_editor/editor.py:2057` |
| `import_project_to_new_tab` | 文件夹名 basename         | `bt_gui/bt_editor/editor.py:289`  |
| `load_tree`                 | 文件夹名 basename         | `bt_gui/bt_editor/editor.py:1139` |
| `_get_project_name`         | 文件夹名 basename / "未命名" | `bt_gui/bt_editor/editor.py:490`  |

→ **同一项目通过不同入口打开，会显示不同的 Tab 名**。

### 1.3 `tree.json` 中的名称字段

| 字段                               | 来源                 | 风险                                                                                                                                                    |
| -------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `format_type`                    | 硬编码（3 个不同值！）       | `project_manager.py:65`="behavior\_tree\_editor"、`serializer.py:51`="behavior\_tree\_standalone"、`serializer.py:298`="behavior\_tree\_with\_subtrees" |
| `version`                        | 硬编码（"2.0" 或 "2.1"） | 无版本迁移代码                                                                                                                                               |
| `nodes[id].config.script_path`   | 用户选择               | **强耦合** `./scripts/script/xxx`                                                                                                                        |
| `nodes[id].config.code_path`     | 用户选择               | **强耦合** `./scripts/code/xxx`                                                                                                                          |
| `nodes[id].config.template_path` | 用户选择               | **强耦合** `./images/templates/xxx`                                                                                                                      |
| `nodes[id].config.subtree_path`  | 用户选择               | **强耦合** `./subtrees/xxx`                                                                                                                              |
| `metadata.app_version`           | 硬编码 "1.0.0"        | 不读取 main.py 真实 VERSION                                                                                                                                |

### 1.4 `project.json` 中的名称字段

| 字段                               | 来源                  | 读取处                                       | 风险                     |
| -------------------------------- | ------------------- | ----------------------------------------- | ---------------------- |
| `project_info.name`              | 用户输入                | `package_importer.py:93`、`editor.py:2057` | R5：重命名文件夹后不同步          |
| `main_tree`                      | **硬编码 "tree.json"** | `nodes.py:1702`、`multi_tree_panel.py:166` | R4：用户重命名 tree.json 后失效 |
| `resources.images/scripts/audio` | 默认 \[]              | **从未被读取**（死代码）                            | R8                     |
| `project_info.author`            | 默认 ""               | 无                                         | R10：无 UI 录入            |
| `project_info.app_version`       | 硬编码 "1.0.0"         | 无                                         | R9                     |

### 1.5 PackageImporter 的 3 级回退策略（导入命名混乱的根源）

`bt_utils/package_importer.py:65-95` 中 `get_project_name()` 的回退顺序：

1. ZIP 第一个条目的顶级文件夹名（= 导出时的项目文件夹名，可能与 project\_info.name 不同）
2. `project_info.name`
3. ZIP 文件名去扩展名

→ **同一 ZIP 通过此策略得到的项目名，可能与导出时的 project\_info.name 不一致**。

***

## 二、跨平台命名错乱的核心风险汇总

| 编号      | 风险                                                    | 严重度 | 本方案是否处理          |
| ------- | ----------------------------------------------------- | --- | ---------------- |
| **R1**  | `format_type` 三值不一致，无任何读取校验                           | 高   | ✅ 处理             |
| **R3**  | TYPE\_DIR\_MAP 重复定义且不同步（importer 缺 `subtree`/`other`） | 高   | ✅ 处理             |
| **R4**  | `main_tree` 硬编码 "tree.json"，无法配置                      | 高   | ⚠️ 提供常量引用        |
| **R5**  | `project_info.name` 不会反向同步到文件夹名                       | 高   | ✅ 处理（打开/导出时弹窗校验） |
| **R6**  | Tab 名 4 种来源不统一，同一项目显示不同名                              | 高   | ✅ 处理（统一为文件夹名）    |
| **R8**  | `resources` 字段是死代码                                    | 中   | ✅ 处理             |
| **R9**  | `app_version` 硬编码，不反映真实版本                             | 中   | ✅ 处理             |
| **R12** | Windows 大小写不敏感导致 ZIP 导入重名检测失效                         | 低   | ✅ 处理             |

***

## 三、详细名称字段总表

### 3.1 project.json 中的名称字段

| 字段                         | 行号                          | 类型       | 来源             | 读取处                                       | 文件系统耦合       | 风险  |
| -------------------------- | --------------------------- | -------- | -------------- | ----------------------------------------- | ------------ | --- |
| `project_info.name`        | `project_manager.py:45`     | str      | 用户输入           | `package_importer.py:93`、`editor.py:2057` | 间接（同时用作文件夹名） | R5  |
| `project_info.description` | `project_manager.py:46`     | str      | 用户输入           | 无                                         | 否            | —   |
| `project_info.author`      | `project_manager.py:47`     | str      | 默认""           | 无                                         | 否            | R10 |
| `project_info.created_at`  | `project_manager.py:48`     | str(ISO) | 自动             | 无                                         | 否            | —   |
| `project_info.modified_at` | `project_manager.py:49,104` | str(ISO) | 自动             | 无                                         | 否            | —   |
| `project_info.app_version` | `project_manager.py:50`     | str      | 硬编码"1.0.0"     | 无                                         | 否            | R9  |
| `main_tree`                | `project_manager.py:52`     | str      | 硬编码"tree.json" | `nodes.py:1702`、`multi_tree_panel.py:166` | 强耦合          | R4  |
| `resources.*`              | `project_manager.py:53-57`  | list     | 默认\[]          | 无                                         | 否            | R8  |
| `format_type`              | `project_manager.py:43`     | str      | 硬编码            | 无                                         | 否            | R1  |
| `version`                  | `project_manager.py:42`     | str      | 硬编码"1.0"       | 无                                         | 否            | —   |

### 3.2 tree.json 中的名称字段

| 字段                                            | 行号                                             | 类型       | 来源                   | 读取处                | 文件系统耦合                        | 风险 |
| --------------------------------------------- | ---------------------------------------------- | -------- | -------------------- | ------------------ | ----------------------------- | -- |
| `format_type`                                 | `project_manager.py:65`、`serializer.py:51,298` | str      | 硬编码（3 值不一致）          | 无                  | 否                             | R1 |
| `version`                                     | `project_manager.py:64`、`serializer.py:50,297` | str      | 硬编码                  | 无                  | 否                             | R2 |
| `metadata.created_at/modified_at/app_version` | `serializer.py:53-55`                          | str      | 自动/硬编码               | 无                  | 否                             | R9 |
| `root_node`                                   | `serializer.py:58`                             | str/None | `root_node.node_id`  | `serializer.py:82` | 否                             | —  |
| `nodes[id].name`                              | `serializer.py:38`（via to\_dict）               | str      | 用户输入/默认              | 多处                 | 否                             | —  |
| `nodes[id].config.script_path`                | 节点配置                                           | str      | 用户选择                 | `script.py:60`     | **强耦合** `./scripts/script/`   | —  |
| `nodes[id].config.code_path`                  | 节点配置                                           | str      | 用户选择                 | `code.py:226`      | **强耦合** `./scripts/code/`     | —  |
| `nodes[id].config.template_path`              | 节点配置                                           | str      | 用户选择                 | 多处                 | **强耦合** `./images/templates/` | —  |
| `nodes[id].config.sound_path`                 | 节点配置                                           | str      | 用户选择                 | `alarm.py`         | **强耦合** `./audio/alarms/`     | —  |
| `nodes[id].config.subtree_path`               | 节点配置                                           | str      | 用户选择                 | `nodes.py:1686`    | **强耦合** `./subtrees/`         | —  |
| `subtree_references[id].path`                 | `serializer.py:318`                            | str      | 自动派生自 `subtree_path` | 无（仅元数据）            | 是                             | —  |

### 3.3 运行时内存中的名称字段

| 字段                                          | 定义位置                    | 类型       | 来源           | 持久化           | 风险      |
| ------------------------------------------- | ----------------------- | -------- | ------------ | ------------- | ------- |
| `ProjectManager.project_root`               | `project_manager.py:13` | str      | 调用方传入        | 否             | —       |
| `TreeInstance.name`                         | `tree_instance.py:16`   | str      | 4 种来源（见 1.2） | settings.json | R6, R11 |
| `TreeInstance.file_path`                    | `tree_instance.py:27`   | str      | 加载时设置        | settings.json | —       |
| `TreeInstance.project_root`                 | `tree_instance.py:28`   | str      | 加载时设置        | settings.json | —       |
| `BehaviorTreeEditor._fallback_project_root` | `editor.py:65`          | str/None | Tab 切换时同步    | 否             | —       |

### 3.4 脚本文件夹名（硬编码常量）

| 字符串值                   | 出现位置                                                                       | 用途                    |
| ---------------------- | -------------------------------------------------------------------------- | --------------------- |
| `"scripts/script"`     | `project_manager.py:30`、`resource_service.py:29`、`resource_importer.py:56` | Python/Bat/Shell 脚本目录 |
| `"scripts/code"`       | `project_manager.py:31`、`resource_service.py:30`、`resource_importer.py:57` | 代码片段目录                |
| `"images/templates"`   | `project_manager.py:28`、`resource_service.py:28`、`resource_importer.py:55` | 模板图片目录                |
| `"audio/alarms"`       | `project_manager.py:32`、`resource_service.py:31`、`resource_importer.py:58` | 报警音频目录                |
| `"data/config"`        | `project_manager.py:33`、`resource_service.py:32`、`resource_importer.py:59` | 数据配置目录                |
| `"subtrees"`           | `resource_service.py:33`（仅此一处）                                             | 子树目录                  |
| `"data/other"`         | `resource_service.py:34`、`resource_importer.py:60`                         | 其他资源目录                |
| `"cache"`              | `project_manager.py:34`、`resource_service.py:37`                           | 缓存目录                  |
| `"docs"`               | `project_manager.py:35`                                                    | 文档目录                  |
| `"images/screenshots"` | `project_manager.py:29`                                                    | 截图目录                  |

***

## 四、统一方案设计

### 4.1 核心设计决策（用户确认版）

| 决策点         | 内容                                                    | 说明                       |
| ----------- | ----------------------------------------------------- | ------------------------ |
| **权威源**     | **文件夹名称**                                             | 用户通过外部文件管理器修改文件夹名是唯一权威来源 |
| **派生字段**    | `project_info.name` 自动同步 = 文件夹名                       | 客户端可写                    |
| **文件夹名修改**  | **客户端永远不修改**                                          | 仅用户通过外部文件管理器修改           |
| **Tab 重命名** | 双击 Tab 仅修改 `project_info.name`                        | 不涉及文件夹重命名                |
| **校验时机**    | 仅在**打开项目**和**导出 ZIP** 时校验                             | 不在保存时校验，避免频繁打扰           |
| **校验失败处理**  | 弹窗让用户选择 ① 同步 project\_info.name 为文件夹名 ② 手动修改文件夹名 ③ 忽略 | 系统不自动修改                  |
| **运行时限制**   | 项目运行中禁止重命名 Tab                                        | 防止状态错乱                   |

### 4.2 方案核心原则

| 原则                        | 说明                                            |
| ------------------------- | --------------------------------------------- |
| **文件夹名为单一权威源（SSOT）**      | 所有显示名、ZIP 名、Tab 名均派生自文件夹名                     |
| **客户端只读文件夹名**             | 客户端任何代码路径都不允许调用 `os.rename` 修改项目文件夹           |
| **project\_info.name 可写** | 仅作为元数据，与文件夹名保持一致；不一致时以文件夹名为准                  |
| **路径常量集中**                | 所有脚本文件夹名集中到 `bt_core/constants.py`，3 处硬编码改为引用 |
| **校验而非强制**                | 检测到不一致时弹窗提示，由用户决策，不自动同步                       |
| **跨平台路径统一**               | JSON 中所有路径强制用正斜杠 `/` 存储，禁止 `os.sep`           |
| **格式版本统一**                | `format_type` 和 `version` 集中到常量，移除三值不一致       |

### 4.3 派生关系图谱（修订版）

```
[用户在 NewProjectDialog 输入 name]
       │
       ├──→ 文件夹名 = os.path.join(location, name)        [权威源]
       │       │
       │       │  ← 用户可通过外部文件管理器重命名文件夹
       │       │  ← 客户端永远不修改
       │       │
       │       └──→ os.path.basename(project_root)         [派生入口]
       │              │
       │              ├──→ project_info.name               [派生，可被 Tab 双击修改]
       │              │       ↑
       │              │       │ 打开/导出时校验：
       │              │       │ 不一致 → 弹窗让用户选择
       │              │       │  ① 同步 project_info.name = 文件夹名
       │              │       │  ② 手动改文件夹名（用户在外部操作）
       │              │       │  ③ 忽略
       │              │       ↓
       │              ├──→ TreeInstance.name               [派生，与文件夹名一致]
       │              ├──→ 窗口标题                        [派生]
       │              ├──→ ZIP 默认文件名                   [派生]
       │              └──→ README 标题                      [派生]
       │
       └──→ Tab 双击重命名 → 仅修改 project_info.name（不动文件夹）
```

***

## 五、具体改造方案

### 改造 1：新增 `bt_core/constants.py` 统一所有名称常量

```python
# bt_core/constants.py
class ProjectConstants:
    """项目命名与路径的单一权威源"""
    
    # ===== 资源目录常量（消除 3 处硬编码）=====
    RESOURCE_DIRS = {
        'image':      'images/templates',
        'script':     'scripts/script',
        'code':       'scripts/code',
        'audio':      'audio/alarms',
        'data':       'data/config',
        'subtree':    'subtrees',
        'other':      'data/other',
        'screenshot': 'images/screenshots',
        'cache':      'cache',
        'docs':       'docs',
    }
    
    # ===== 文件名常量 =====
    PROJECT_META_FILE = 'project.json'
    MAIN_TREE_FILE = 'tree.json'          # 默认主树文件名
    
    # ===== 格式版本常量（消除三值不一致）=====
    PROJECT_FORMAT_TYPE = 'behavior_tree_project'
    PROJECT_FORMAT_VERSION = '1.0'
    
    TREE_FORMAT_TYPE = 'behavior_tree'    # 统一为一个值
    TREE_FORMAT_VERSION = '2.1'           # 统一为最高版本
    
    # ===== 路径分隔符（跨平台）=====
    PATH_SEPARATOR = '/'                  # JSON 中存储统一用正斜杠
```

### 改造 2：项目名解析统一函数（以文件夹名为权威源）

在 `bt_utils/project_manager.py` 中新增唯一的项目名解析入口：

```python
class ProjectManager:
    @staticmethod
    def resolve_project_name(project_root: str) -> str:
        """
        项目名解析的唯一入口（SSOT）。
        权威源：文件夹名（os.path.basename(project_root)）
        所有调用方必须使用此方法，禁止直接 os.path.basename。
        """
        if not project_root:
            return "未命名"
        basename = os.path.basename(project_root.rstrip(os.sep))
        return basename if basename else "未命名"
    
    @staticmethod
    def read_project_info_name(project_root: str) -> str:
        """读取 project.json 中存储的 project_info.name（仅用于一致性校验）"""
        meta_path = os.path.join(project_root, ProjectConstants.PROJECT_META_FILE)
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                return meta.get("project_info", {}).get("name", "").strip()
            except (json.JSONDecodeError, OSError):
                pass
        return ""
    
    @staticmethod
    def check_name_consistency(project_root: str) -> dict:
        """
        检查文件夹名与 project_info.name 是否一致。
        返回：{"consistent": bool, "folder_name": str, "project_info_name": str}
        """
        folder_name = ProjectManager.resolve_project_name(project_root)
        info_name = ProjectManager.read_project_info_name(project_root)
        return {
            "consistent": (not info_name) or (info_name == folder_name),
            "folder_name": folder_name,
            "project_info_name": info_name,
        }
```

### 改造 3：统一所有 Tab 名/窗口标题/ZIP 名的来源

将以下 6 处 `os.path.basename` 调用全部替换为 `ProjectManager.resolve_project_name()`：

| 文件:行号                       | 原代码                                                 | 替换为                                                                |
| --------------------------- | --------------------------------------------------- | ------------------------------------------------------------------ |
| `editor.py:490`             | `os.path.basename(self._fallback_project_root)`     | `ProjectManager.resolve_project_name(self._fallback_project_root)` |
| `editor.py:1139`            | `os.path.basename(project_root)`                    | `ProjectManager.resolve_project_name(project_root)`                |
| `editor.py:289`             | `os.path.basename(project_path)`                    | `ProjectManager.resolve_project_name(project_path)`                |
| `app.py:117`                | `os.path.basename(self.behavior_tree.project_root)` | `ProjectManager.resolve_project_name(...)`                         |
| `package_exporter.py:26`    | `os.path.basename(self.project_root)`               | `ProjectManager.resolve_project_name(self.project_root)`           |
| `package_importer.py:65-95` | 3 级回退                                               | **简化为**：先读 project\_info.name，否则 basename，否则 zipname               |

### 改造 4：Tab 双击重命名功能（仅修改 project\_info.name）

**核心约束**：双击 Tab 重命名**只修改** **`project_info.name`**，绝不修改文件夹名。

#### 4.1 UI 行为

- 双击 Tab 标签 → 进入编辑模式（inline Entry）
- 显示当前 `project_info.name` 作为初始值
- ESC 取消，Enter 确认，失焦确认
- 空值或未变更 → 退出编辑模式，不触发保存
- 项目运行中（`engine.is_running()` 为真）→ 禁止进入编辑模式，显示 tooltip "请先停止运行"

#### 4.2 校验规则

```python
def validate_project_info_name(name: str) -> tuple[bool, str]:
    """校验 project_info.name（注意：这不是文件夹名校验）"""
    name = name.strip()
    if not name:
        return False, "名称不能为空"
    if len(name) > 100:
        return False, "名称过长（>100 字符）"
    # project_info.name 是元数据，允许更宽泛的字符（包括文件夹名禁用字符）
    # 但仍禁止控制字符
    if any(ord(c) < 32 for c in name):
        return False, "名称包含非法控制字符"
    return True, ""
```

#### 4.3 保存逻辑

```python
def _on_tab_rename_confirm(self, tab_id: str, new_name: str) -> bool:
    """Tab 重命名确认：仅修改 project_info.name"""
    ok, err = validate_project_info_name(new_name)
    if not ok:
        self._show_toast(err)
        return False
    
    instance = self._instances[tab_id]
    if not instance.project_root:
        return False
    
    # 1. 更新 project.json 中的 project_info.name
    self._update_project_info_name(instance.project_root, new_name)
    
    # 2. 更新 TreeInstance.name（仅显示用，权威源仍是文件夹名）
    instance.name = new_name
    
    # 3. 更新 Tab 标签显示
    self._update_tab_label(tab_id, new_name)
    
    # 4. 更新窗口标题
    self._update_window_title()
    
    # 5. 持久化 settings.json
    self._save_tabs_state()
    
    # 6. 日志提示
    self.log_panel.info(
        f"已修改项目显示名为 '{new_name}'。"
        f"注意：文件夹名未改变，下次打开时若与文件夹名不一致会提示同步。"
    )
    return True
```

#### 4.4 边界场景

| 场景                      | 处理                        |
| ----------------------- | ------------------------- |
| 项目运行中                   | 禁止双击编辑，显示 tooltip         |
| 输入为空                    | 恢复原值，不保存                  |
| 输入与原值相同                 | 退出编辑，不触发保存                |
| 输入含控制字符                 | 拒绝并提示                     |
| project\_root 为空（未保存项目） | 禁止编辑，提示先保存                |
| 保存 project.json 失败      | 回滚 TreeInstance.name，提示错误 |

### 改造 5：打开项目时的一致性校验（弹窗）

在 `BehaviorTreeEditor.open_project()` 中加入校验：

```python
def open_project(self, project_root: str) -> None:
    # ... 原有加载逻辑 ...
    
    # 一致性校验
    check = ProjectManager.check_name_consistency(project_root)
    if not check["consistent"]:
        self._prompt_name_mismatch_on_open(
            project_root, 
            check["folder_name"], 
            check["project_info_name"]
        )
    
    # Tab 名以文件夹名为准
    tab_name = ProjectManager.resolve_project_name(project_root)
    # ... 创建 Tab ...

def _prompt_name_mismatch_on_open(self, project_root, folder_name, info_name):
    """
    弹窗：文件夹名与 project_info.name 不一致
    选项：
      ① 同步 project_info.name 为文件夹名（推荐）
      ② 我已手动修改文件夹名，重新检查
      ③ 忽略，本次按文件夹名显示
    """
    result = messagebox.askyesno(
        "项目名称不一致",
        f"检测到名称不一致：\n\n"
        f"  文件夹名：{folder_name}\n"
        f"  project_info.name：{info_name}\n\n"
        f"系统将以文件夹名 '{folder_name}' 作为权威源显示。\n"
        f"是否同步更新 project_info.name 为 '{folder_name}'？\n\n"
        f"（是 = 同步 project_info.name；否 = 仅本次按文件夹名显示，不修改文件）",
        icon=messagebox.WARNING,
    )
    if result:
        self._update_project_info_name(project_root, folder_name)
        self.log_panel.info(f"已同步 project_info.name: '{info_name}' → '{folder_name}'")
    else:
        self.log_panel.info(f"未同步 project_info.name，本次以文件夹名 '{folder_name}' 显示")
```

### 改造 6：导出 ZIP 时的一致性校验（弹窗）

在 `PackageExporter.export()` 中加入校验：

```python
def export(self, zip_path: str) -> str:
    # 一致性校验
    check = ProjectManager.check_name_consistency(self.project_root)
    if not check["consistent"]:
        result = self._prompt_name_mismatch_on_export(
            check["folder_name"], 
            check["project_info_name"]
        )
        if result == "sync":
            self._update_project_info_name(self.project_root, check["folder_name"])
        elif result == "cancel":
            return ""  # 取消导出
    
    # ... 原有导出逻辑 ...
    # ZIP 内文件夹名 = 当前文件夹名
    # project_info.name 已同步
```

### 改造 7：统一 `format_type` / `version`

- 将 `project_manager.py:65` 的 "behavior\_tree\_editor"、`serializer.py:51` 的 "behavior\_tree\_standalone"、`serializer.py:298` 的 "behavior\_tree\_with\_subtrees" **统一为** `ProjectConstants.TREE_FORMAT_TYPE = "behavior_tree"`。
- 在 `Serializer.deserialize()` 中加入 `format_type` 校验，遇到未知值发出警告但不报错（向后兼容）。

### 改造 8：跨平台路径规范化

在 `bt_core/serializer.py` 的 `serialize()` 中，对所有 `*_path` 字段强制调用 `path.replace(os.sep, '/')`，确保 JSON 中存储的相对路径永远是正斜杠。

### 改造 9：清理死代码

- 移除 `project.json` 中的 `resources.images/scripts/audio` 字段（R8），或将其改为由 `ResourceService.collect_external_resources()` 动态填充并真正使用。
- 移除 `resource_importer.py` 中的 TYPE\_DIR\_MAP 局部定义，改用 `ProjectConstants.RESOURCE_DIRS`（R3）。

### 改造 10：app\_version 动态读取

将 `project_manager.py:50` 和 `serializer.py:55` 中的硬编码 "1.0.0" 改为从 `main.py` 的 `VERSION` 常量读取。

### 改造 11：ZIP 导入命名统一

`package_importer.py` 简化为：

```python
def get_project_name(self, zip_path: str) -> str:
    """
    导入时获取项目名。
    优先级：ZIP 内 project_info.name > ZIP 文件名去扩展名
    注意：导入后实际文件夹名以此返回值为准，并强制写入 project_info.name。
    """
    # 1. 优先读 ZIP 内 project.json
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.filename.endswith('project.json'):
                content = zf.read(info.filename)
                meta = json.loads(content)
                name = meta.get("project_info", {}).get("name", "").strip()
                if name:
                    return name
                break
    # 2. 回退到 ZIP 文件名（不再用"第一个条目的顶级目录"）
    return os.path.splitext(os.path.basename(zip_path))[0]
```

导入流程：

1. `name = get_project_name(zip_path)`
2. 解压到临时目录
3. 新文件夹名 = `name`（若与目标目录下已有文件夹冲突，自动追加 `_1`、`_2` 后缀）
4. 强制写入 `project_info.name = 实际新文件夹名`（处理冲突后缀的情况）
5. 确保 `project_info.name` 与实际文件夹名一致

***

## 六、改造收益

| 风险编号                   | 改造后状态                                |
| ---------------------- | ------------------------------------ |
| R1（format\_type 三值）    | ✅ 统一为常量                              |
| R3（TYPE\_DIR\_MAP 不同步） | ✅ 集中到 constants                      |
| R4（main\_tree 硬编码）     | ⚠️ 保留默认值但提供常量引用，未来可扩展                |
| R5（不反向同步）              | ✅ 打开/导出时弹窗校验，用户决策                    |
| R6（Tab 名 4 来源）         | ✅ 统一为 `resolve_project_name()`（文件夹名） |
| R8（resources 死代码）      | ✅ 清理或激活                              |
| R9（app\_version 硬编码）   | ✅ 动态读取                               |
| R12（Windows 大小写）       | ✅ 导入时统一用 project\_info.name          |

***

## 七、实施阶段建议

### 阶段 1（低风险，立即收益）

- 改造 1：新增 `bt_core/constants.py`
- 改造 2：新增 `resolve_project_name()` / `check_name_consistency()` 统一入口
- 改造 3：替换 6 处 `os.path.basename` 调用
- 改造 7：统一 `format_type` / `version`
- 改造 9：清理死代码
- 改造 10：app\_version 动态读取
- 改造 11：ZIP 导入命名统一

不改数据结构，向后兼容。

### 阶段 2（需测试）

- 改造 4：Tab 双击重命名 UI（仅修改 project\_info.name）
- 改造 5：打开项目时一致性校验弹窗
- 改造 6：导出 ZIP 时一致性校验弹窗
- 改造 8：路径规范化（影响序列化输出）

涉及 GUI 交互变更，需要充分测试。

***

## 八、附录：字段间同步状态表（修订版）

| 源字段                      | 目标字段                      | 同步方向     | 同步时机                | 备注            |
| ------------------------ | ------------------------- | -------- | ------------------- | ------------- |
| 用户输入 name                | 文件夹名                      | 单向写入     | 仅 create\_project 时 | 客户端永不修改       |
| 用户输入 name                | project\_info.name        | 单向写入     | 仅 create\_project 时 | 后续可被 Tab 双击修改 |
| 文件夹名（外部修改）               | project\_info.name        | **手动同步** | 打开/导出时弹窗校验          | 用户决策，不自动同步    |
| 文件夹名                     | TreeInstance.name         | 单向派生     | 打开项目时               | 权威源派生         |
| 文件夹名                     | 窗口标题 / ZIP 名 / README     | 单向派生     | 各自触发时               | 权威源派生         |
| Tab 双击重命名                | project\_info.name        | 单向写入     | 用户操作时               | **不修改文件夹名**   |
| project\_info.name       | settings.json 中的 tab name | 单向持久化    | 关闭应用时               | 重启后以文件夹名为准    |
| node.config.script\_path | 文件系统路径                    | 强耦合      | 用户选择文件时             | 相对路径，文件夹名不影响  |

***

## 九、关键代码路径清单（实施时参考）

### 9.1 需要修改的文件

| 文件                                        | 修改内容                                                                               |
| ----------------------------------------- | ---------------------------------------------------------------------------------- |
| `bt_core/constants.py`                    | **新建**，定义所有常量                                                                      |
| `bt_utils/project_manager.py`             | 新增 `resolve_project_name` / `read_project_info_name` / `check_name_consistency` 方法 |
| `bt_utils/resource_service.py`            | TYPE\_DIR\_MAP 改用 `ProjectConstants.RESOURCE_DIRS`                                 |
| `bt_utils/resource_importer.py`           | TYPE\_DIR\_MAP 改用 `ProjectConstants.RESOURCE_DIRS`                                 |
| `bt_utils/package_exporter.py:26`         | 替换为 `resolve_project_name` + 加入导出时校验                                               |
| `bt_utils/package_importer.py:65-95`      | 简化 `get_project_name` 回退策略                                                         |
| `bt_core/serializer.py:51,298`            | `format_type` 统一为常量；`*_path` 字段路径规范化                                               |
| `bt_gui/bt_editor/editor.py:490,1139,289` | 替换为 `resolve_project_name`                                                         |
| `bt_gui/bt_editor/editor.py`              | 新增 Tab 双击重命名逻辑 + 打开时校验弹窗                                                           |
| `bt_gui/bt_editor/tab_bar.py`             | Tab 双击事件绑定（如已存在则修改）                                                                |
| `bt_gui/app.py:117`                       | 替换为 `resolve_project_name`                                                         |

### 9.2 需要新增的方法

| 方法                                                                 | 位置                    | 用途                    |
| ------------------------------------------------------------------ | --------------------- | --------------------- |
| `ProjectManager.resolve_project_name(project_root)`                | `project_manager.py`  | 项目名解析 SSOT            |
| `ProjectManager.read_project_info_name(project_root)`              | `project_manager.py`  | 读取 project\_info.name |
| `ProjectManager.check_name_consistency(project_root)`              | `project_manager.py`  | 一致性校验                 |
| `BehaviorTreeEditor._on_tab_rename_confirm(tab_id, new_name)`      | `editor.py`           | Tab 重命名确认             |
| `BehaviorTreeEditor._prompt_name_mismatch_on_open(...)`            | `editor.py`           | 打开时弹窗                 |
| `BehaviorTreeEditor._update_project_info_name(project_root, name)` | `editor.py`           | 更新 project.json       |
| `PackageExporter._prompt_name_mismatch_on_export(...)`             | `package_exporter.py` | 导出时弹窗                 |

### 9.3 校验时机与行为总表

| 时机        | 校验                               | 不一致时行为                            |
| --------- | -------------------------------- | --------------------------------- |
| 打开项目      | `check_name_consistency`         | 弹窗：① 同步 project\_info.name ② 忽略本次 |
| 导出 ZIP    | `check_name_consistency`         | 弹窗：① 同步 project\_info.name ② 取消导出 |
| 保存项目      | ❌ 不校验                            | —                                 |
| Tab 双击重命名 | `validate_project_info_name`     | 仅修改 project\_info.name，不动文件夹      |
| 项目运行中     | 禁止 Tab 双击编辑                      | tooltip 提示                        |
| 导入 ZIP    | 强制 `project_info.name = 实际新文件夹名` | 自动同步，不弹窗                          |

