# 脚本相对坐标转换功能实现计划

## 概述

为脚本节点（ScriptNode）添加坐标转换功能，将录制时保存的屏幕绝对坐标转换为窗口相对坐标，以适配窗口绑定功能。

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
        # 获取当前脚本路径
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
2. 解析脚本开头的 `# Window:` 和 `# WindowRect:` 行

**代码结构**:
```python
def _check_window_marker(self, content: str) -> dict:
    """
    检查脚本是否已存在窗口标记
    
    Returns:
        dict: {"has_marker": bool, "window_title": str, "window_rect": tuple}
    """
    pass
```

**验收标准**:
- [ ] 正确识别已转换的脚本
- [ ] 正确解析窗口标题和矩形区域

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
    pass
```

**验收标准**:
- [ ] 备份文件正确创建
- [ ] 备份内容与原文件一致
- [ ] 已存在的备份文件被正确覆盖

---

### 任务 4：实现坐标转换功能

**文件**: `bt_gui/bt_editor/property.py`

**实现内容**:
1. 实现解析脚本中的 `MoveTo` 命令
2. 实现屏幕绝对坐标转窗口相对坐标
3. 实现在脚本开头添加窗口标记

**代码结构**:
```python
def _convert_coordinates(self, content: str, window_rect: tuple) -> str:
    """
    转换脚本中的坐标
    
    Args:
        content: 脚本内容
        window_rect: 窗口矩形区域 (left, top, right, bottom)
    
    Returns:
        str: 转换后的脚本内容
    """
    pass

def _add_window_marker(self, content: str, window_title: str, window_rect: tuple) -> str:
    """
    在脚本开头添加窗口标记
    """
    pass
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
    try:
        # 1. 检查脚本路径
        # 2. 检查窗口标记
        # 3. 获取窗口绑定配置
        # 4. 查找绑定窗口
        # 5. 备份脚本
        # 6. 转换坐标
        # 7. 保存脚本
        # 8. 显示成功提示
    except Exception as e:
        # 显示错误提示
        pass
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

### 任务 7：测试与验证

**测试内容**:
1. 正常转换流程测试
2. 异常场景测试
3. 坐标转换准确性验证

**测试用例**:
| 测试场景 | 预期结果 |
|---------|---------|
| 未选择脚本文件 | 提示"请先选择脚本文件" |
| 脚本文件不存在 | 提示"脚本文件不存在" |
| 未绑定窗口 | 提示"当前项目未进行窗口绑定，无需转换相对坐标" |
| 绑定窗口未打开 | 提示"未找到绑定窗口，请确保窗口已打开" |
| 重复转换 | 提示"该脚本已完成相对坐标转换，不要重复执行" |
| 正常转换 | 脚本正确转换，备份文件创建成功 |

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
任务 4: 实现坐标转换功能
    │
    ▼
任务 5: 实现转换按钮点击逻辑
    │
    ▼
任务 6: 更新 NODE_CONFIG_SCHEMAS
    │
    ▼
任务 7: 测试与验证
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
| 任务 7 | 10 分钟 |
| **总计** | **60 分钟** |

## 依赖关系

- 依赖 `bt_utils/window_manager.py` 中的窗口查找方法
- 依赖 `bt_utils/coordinate.py` 中的坐标转换方法
- 依赖 `tkinter.messagebox` 显示提示信息

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 脚本文件编码问题 | 可能导致读取/写入失败 | 使用 `utf-8` 编码，添加异常处理 |
| 窗口查找失败 | 无法转换坐标 | 提示用户确保窗口已打开 |
| 坐标转换错误 | 脚本执行位置不正确 | 添加备份功能，用户可恢复 |
