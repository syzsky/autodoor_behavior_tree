# 脚本相对坐标转换功能实现计划

## 概述

为脚本节点（ScriptNode）添加坐标转换功能，包括：
1. **转换按钮**：将录制时保存的屏幕绝对坐标转换为窗口相对坐标
2. **执行时转换**：脚本执行时将窗口相对坐标转换回屏幕绝对坐标

## 实现任务

### 任务 1：新增 ScriptConvertField 组件

**文件**: `bt_gui/bt_editor/property.py`

**实现内容**:
1. 创建 `ScriptConvertField` 类，继承自 `FieldWidget`
2. 实现按钮组件创建
3. 实现获取脚本路径的方法
4. 实现获取开始节点窗口绑定配置的方法

**代码结构**:
```python
class ScriptConvertField(FieldWidget):
    def __init__(self, master, label, key, on_change, app, **kwargs):
        self.app = app
        super().__init__(master, label, key, on_change, **kwargs)
    
    def _create_widget(self):
        # 创建转换按钮
        pass
    
    def _get_script_path(self) -> str:
        # 从属性面板其他字段获取脚本路径
        pass
    
    def _get_start_node_config(self) -> dict:
        # 获取开始节点的窗口绑定配置
        pass
```

**验收标准**:
- [ ] 组件正确显示在属性面板中
- [ ] 按钮样式与主题一致

---

### 任务 2：实现窗口标记检查功能

**文件**: `bt_gui/bt_editor/property.py`

**实现内容**:
1. 实现检查脚本是否已存在窗口标记的方法
2. 解析脚本开头的 `# Window:` 行

**代码结构**:
```python
def _check_window_marker(self, content: str) -> dict:
    """
    检查脚本是否已存在窗口标记
    
    Returns:
        dict: {"has_marker": bool, "window_title": str}
    """
    for line in content.splitlines():
        if line.startswith("# Window:"):
            return {
                "has_marker": True,
                "window_title": line[10:].strip()
            }
    return {"has_marker": False, "window_title": ""}
```

**验收标准**:
- [ ] 正确识别已转换的脚本
- [ ] 正确解析窗口标题

---

### 任务 3：实现脚本备份功能

**文件**: `bt_gui/bt_editor/property.py`

**实现内容**:
1. 实现备份原脚本文件的方法
2. 备份文件名为 `<原文件名>.bak`
3. 如果备份文件已存在则覆盖

**代码结构**:
```python
def _backup_script(self, script_path: str) -> str:
    """
    备份原脚本文件
    
    Returns:
        str: 备份文件路径
    """
    import shutil
    backup_path = script_path + ".bak"
    shutil.copy2(script_path, backup_path)
    return backup_path
```

**验收标准**:
- [ ] 备份文件正确创建
- [ ] 备份内容与原文件一致

---

### 任务 4：实现坐标转换功能（转换按钮）

**文件**: `bt_gui/bt_editor/property.py`

**实现内容**:
1. 解析脚本中的 `MoveTo` 命令
2. 使用 `CoordinateConverter.absolute_to_window()` 转换坐标
3. 在脚本开头添加窗口标记

**代码结构**:
```python
def _convert_coordinates(self, content: str, hwnd: int, window_title: str) -> str:
    """
    转换脚本中的坐标（屏幕绝对 → 窗口相对）
    
    使用: CoordinateConverter.absolute_to_window()
    """
    import re
    from bt_utils.coordinate import CoordinateConverter
    
    converted_count = 0
    
    def replace_coord(match):
        nonlocal converted_count
        x, y = int(match.group(1)), int(match.group(2))
        result = CoordinateConverter.absolute_to_window(x, y, hwnd)
        if result:
            converted_count += 1
            return f"MoveTo {result[0]}, {result[1]}"
        return match.group(0)
    
    new_content = re.sub(r'MoveTo\s+(\d+)\s*,\s*(\d+)', replace_coord, content)
    
    # 添加窗口标记
    rect = CoordinateConverter.get_window_rect(hwnd)
    header = f"# Window: {window_title}\n# WindowRect: {rect[0]}, {rect[1]}, {rect[2]}, {rect[3]}\n"
    
    return header + new_content, converted_count
```

**验收标准**:
- [ ] 所有 `MoveTo` 命令的坐标被正确转换
- [ ] 窗口标记正确添加到脚本开头
- [ ] 其他命令不受影响

---

### 任务 5：实现转换按钮点击逻辑

**文件**: `bt_gui/bt_editor/property.py`

**实现内容**:
1. 实现完整的转换流程
2. 添加错误处理和用户提示
3. 使用 `messagebox` 显示提示信息

**代码结构**:
```python
def _on_convert_click(self):
    """
    转换按钮点击回调
    """
    import tkinter.messagebox as messagebox
    from bt_utils.window_manager import WindowManager
    
    try:
        # 1. 检查脚本路径
        script_path = self._get_script_path()
        if not script_path:
            messagebox.showwarning("提示", "请先选择脚本文件")
            return
        
        # 2. 检查窗口标记
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        marker = self._check_window_marker(content)
        if marker["has_marker"]:
            messagebox.showwarning("提示", 
                f"该脚本已完成相对坐标转换（窗口：{marker['window_title']}），不要重复执行")
            return
        
        # 3. 获取窗口绑定配置
        start_config = self._get_start_node_config()
        if not start_config.get("bind_window"):
            messagebox.showinfo("提示", "当前项目未进行窗口绑定，无需转换相对坐标")
            return
        
        # 4. 查找绑定窗口
        hwnd, _ = WindowManager.find_window_smart(
            start_config.get("window_pid"),
            start_config.get("window_title")
        )
        if not hwnd:
            messagebox.showerror("错误", "未找到绑定窗口，请确保窗口已打开")
            return
        
        # 5. 备份脚本
        backup_path = self._backup_script(script_path)
        
        # 6. 转换坐标
        new_content, count = self._convert_coordinates(
            content, hwnd, start_config.get("window_title")
        )
        
        # 7. 保存脚本
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 8. 显示成功提示
        messagebox.showinfo("成功", 
            f"转换完成，已将 {count} 个坐标转换为窗口相对坐标\n原脚本已备份至 {backup_path}")
        
    except Exception as e:
        messagebox.showerror("错误", f"转换失败: {str(e)}")
```

**验收标准**:
- [ ] 所有错误场景正确处理
- [ ] 用户提示信息清晰准确
- [ ] 转换成功后脚本文件正确更新

---

### 任务 6：更新 NODE_CONFIG_SCHEMAS

**文件**: `bt_gui/bt_editor/property.py`

**实现内容**:
1. 在 `ScriptNode` 的配置中添加 `convert_coords` 字段
2. 在 `_create_field` 方法中添加 `script_convert` 类型处理

**代码结构**:
```python
NODE_CONFIG_SCHEMAS = {
    # ...
    "ScriptNode": [
        {"key": "script_path", "label": "脚本路径", "type": "script", ...},
        {"key": "loop", "label": "循环执行", "type": "bool", ...},
        {"key": "convert_coords", "label": "", "type": "script_convert"},
    ],
    # ...
}

def _create_field(self, field, value, parent_frame=None):
    # ...
    elif field_type == "script_convert":
        field_widget = ScriptConvertField(container, label, key, self._on_field_change, self.app)
    # ...
```

**验收标准**:
- [ ] 脚本节点属性面板正确显示转换按钮
- [ ] 按钮位置在"循环执行"选项下方

---

### 任务 7：ScriptNode 新增窗口标记解析方法

**文件**: `bt_nodes/actions/script.py`

**实现内容**:
1. 新增 `_parse_window_marker` 方法
2. 解析脚本中的 `# Window:` 标记

**代码结构**:
```python
def _parse_window_marker(self, content: str) -> dict:
    """
    解析脚本中的窗口标记
    
    Returns:
        dict: {"has_marker": bool, "window_title": str}
    """
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# Window:"):
            return {
                "has_marker": True,
                "window_title": line[10:].strip()
            }
    return {"has_marker": False, "window_title": ""}
```

**验收标准**:
- [ ] 正确识别窗口标记
- [ ] 正确解析窗口标题

---

### 任务 8：ScriptNode 新增坐标转换方法

**文件**: `bt_nodes/actions/script.py`

**实现内容**:
1. 新增 `_convert_to_absolute_coords` 方法
2. 使用 `context.convert_to_screen_coords()` 转换坐标

**代码结构**:
```python
def _convert_to_absolute_coords(self, content: str, context) -> str:
    """
    将脚本中的窗口相对坐标转换为屏幕绝对坐标
    
    使用: context.convert_to_screen_coords()
    """
    import re
    
    def replace_coord(match):
        x, y = int(match.group(1)), int(match.group(2))
        result = context.convert_to_screen_coords((x, y))
        if result:
            return f"MoveTo {result[0]}, {result[1]}"
        return match.group(0)
    
    return re.sub(r'MoveTo\s+(\d+)\s*,\s*(\d+)', replace_coord, content)
```

**验收标准**:
- [ ] 所有 `MoveTo` 命令的坐标被正确转换
- [ ] 其他命令不受影响

---

### 任务 9：修改 ScriptNode._start_script 方法

**文件**: `bt_nodes/actions/script.py`

**实现内容**:
1. 读取脚本内容后检查窗口标记
2. 如果有窗口标记且绑定了窗口，转换坐标
3. 传给 `ScriptExecutor` 执行

**代码结构**:
```python
def _start_script(self, absolute_script_path, script_path, context):
    """启动脚本执行"""
    # 读取脚本内容
    with open(absolute_script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查窗口标记
    marker = self._parse_window_marker(content)
    
    if marker["has_marker"]:
        # 有窗口标记，需要转换坐标
        bound_window = context.get_bound_window()
        if bound_window:
            content = self._convert_to_absolute_coords(content, context)
            print(f"[DEBUG] ScriptNode: 已将窗口相对坐标转换为屏幕绝对坐标")
    
    # 检查脚本内容是否为空
    # ...
    
    # 执行脚本
    self._executor.run_script(content, loop=use_loop)
```

**验收标准**:
- [ ] 有窗口标记时正确转换坐标
- [ ] 无窗口标记时直接执行
- [ ] 未绑定窗口时直接执行

---

### 任务 10：测试与验证

**测试内容**:
1. 正常转换流程测试
2. 脚本执行测试
3. 异常场景测试

**测试用例**:
| 测试场景 | 预期结果 |
|---------|---------|
| 未选择脚本文件 | 提示"请先选择脚本文件" |
| 脚本文件不存在 | 提示"脚本文件不存在" |
| 未绑定窗口 | 提示"当前项目未进行窗口绑定，无需转换相对坐标" |
| 绑定窗口未打开 | 提示"未找到绑定窗口，请确保窗口已打开" |
| 重复转换 | 提示"该脚本已完成相对坐标转换，不要重复执行" |
| 正常转换 | 脚本正确转换，备份文件创建成功 |
| 脚本执行（有窗口标记+绑定窗口） | 鼠标移动到正确位置 |
| 脚本执行（有窗口标记+未绑定窗口） | 脚本执行但坐标可能不正确 |

**验收标准**:
- [ ] 所有测试用例通过
- [ ] 无语法错误
- [ ] 无运行时异常

---

## 执行顺序

```
任务 1: 新增 ScriptConvertField 组件
    │
    ▼
任务 2: 实现窗口标记检查功能
    │
    ▼
任务 3: 实现脚本备份功能
    │
    ▼
任务 4: 实现坐标转换功能（转换按钮）
    │
    ▼
任务 5: 实现转换按钮点击逻辑
    │
    ▼
任务 6: 更新 NODE_CONFIG_SCHEMAS
    │
    ▼
任务 7: ScriptNode 新增窗口标记解析方法
    │
    ▼
任务 8: ScriptNode 新增坐标转换方法
    │
    ▼
任务 9: 修改 ScriptNode._start_script 方法
    │
    ▼
任务 10: 测试与验证
```

## 预计工作量

| 任务 | 预计时间 |
|------|---------|
| 任务 1 | 10 分钟 |
| 任务 2 | 5 分钟 |
| 任务 3 | 5 分钟 |
| 任务 4 | 10 分钟 |
| 任务 5 | 15 分钟 |
| 任务 6 | 5 分钟 |
| 任务 7 | 5 分钟 |
| 任务 8 | 10 分钟 |
| 任务 9 | 10 分钟 |
| 任务 10 | 15 分钟 |
| **总计** | **90 分钟** |

## 依赖关系

- 依赖 `bt_utils/window_manager.py` 中的窗口查找方法
- 依赖 `bt_utils/coordinate.py` 中的坐标转换方法
- 依赖 `bt_core/context.py` 中的 `convert_to_screen_coords` 方法
- 依赖 `tkinter.messagebox` 显示提示信息

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 脚本文件编码问题 | 可能导致读取/写入失败 | 使用 `utf-8` 编码，添加异常处理 |
| 窗口查找失败 | 无法转换坐标 | 提示用户确保窗口已打开 |
| 坐标转换错误 | 脚本执行位置不正确 | 添加备份功能，用户可恢复 |
| 未绑定窗口执行有标记的脚本 | 坐标可能不正确 | 日志提示，建议用户绑定窗口 |
