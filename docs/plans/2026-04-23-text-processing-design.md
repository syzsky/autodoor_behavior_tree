# 文本处理功能设计文档

## 1 概述

### 1.1 背景

当前 AutoDoor 行为树系统缺少文本输入和文本提取功能，无法实现动态文本交互场景：
- 无法输入预设文本或动态文本
- 无法从屏幕区域提取文本内容
- 无法实现验证码识别和输入等场景

### 1.2 目标

新增文本处理功能模块：
1. **文本输入节点**：支持多种输入源（预设文本、黑板文本、文件文本）
2. **文本提取节点**：从指定区域提取文本并保存到黑板

### 1.3 设计原则

- **多种输入源**：支持预设文本、黑板文本、文件文本
- **灵活执行模式**：支持顺序执行和随机执行
- **与现有系统集成**：复用 OCR 识别功能，与黑板系统集成

---

## 2 架构设计

### 2.1 模块划分

```
新增模块：
├── bt_nodes/
│   ├── actions/
│   │   └── text_input.py          # 文本输入节点
│   └── conditions/
│       └── text_extract.py        # 文本提取节点
└── bt_gui/
    └── bt_editor/
        └── constants.py           # 新增节点类型常量
```

### 2.2 类图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TextInputNode (动作节点)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ + input_mode: str                                                            │
│ + preset_texts: List[str]                                                    │
│ + execution_mode: str                                                        │
│ + blackboard_key: str                                                        │
│ + file_path: str                                                             │
│ + position: Tuple[int, int]                                                  │
│ + use_blackboard: bool                                                       │
│ + position_key: str                                                          │
│ + input_delay: int                                                           │
│ + clear_before_input: bool                                                   │
│ + save_input_text: bool                                                      │
│ + output_key: str                                                            │
│ - _current_text_index: int                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ + _execute_action(context) -> NodeStatus                                     │
│ + _get_text(context) -> str                                                  │
│ + _get_next_preset_text(context) -> str                                      │
│ + _get_random_preset_text() -> str                                           │
│ + _input_text(context, text) -> None                                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       TextExtractNode (条件节点)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ + extract_mode: str                                                          │
│ + region: Tuple[int, int, int, int]                                          │
│ + keywords: str                                                              │
│ + language: str                                                              │
│ + preprocess_mode: str                                                       │
│ + output_key: str                                                            │
│ + save_all_text: bool                                                        │
│ + all_text_key: str                                                          │
│ + save_position: bool                                                        │
│ + position_key: str                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ + _check_condition(context) -> bool                                          │
│ + _extract_all_text(text) -> str                                             │
│ + _extract_keywords_text(text, keywords) -> str                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3 详细设计

### 3.1 文本输入节点

**节点类型：** 动作节点

**功能：** 向目标位置输入文本，支持多种输入源和执行模式

**参数配置：**

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| input_mode | str | 输入模式 | "preset" |
| preset_texts | List[str] | 预设文本列表（input_mode="preset"时使用） | [] |
| execution_mode | str | 执行模式（input_mode="preset"时使用） | "sequential" |
| blackboard_key | str | 黑板变量名（input_mode="blackboard"时使用） | "extracted_text" |
| file_path | str | 文件路径（input_mode="file"时使用） | "" |
| position | Tuple[int, int] | 输入位置（None表示当前位置） | None |
| use_blackboard | bool | 是否从黑板获取位置 | False |
| position_key | str | 位置的黑板变量名 | "last_detection_position" |
| input_delay | int | 字符输入间隔（毫秒） | 50 |
| clear_before_input | bool | 输入前是否清空 | False |
| save_input_text | bool | 是否将输入的文本保存到黑板 | False |
| output_key | str | 输入文本保存的黑板变量名 | "last_input_text" |

**输入模式说明：**

| 模式 | 说明 |
|------|------|
| preset | 从预设文本列表中选择文本输入 |
| blackboard | 从黑板读取文本 |
| file | 从文件读取文本 |

**执行模式说明（仅preset模式）：**

| 模式 | 说明 |
|------|------|
| sequential | 依次执行预设文本列表，每次执行选择下一个文本 |
| random | 随机从预设文本列表中选择一个文本执行 |

**执行流程：**

```
1. 根据输入模式获取文本内容：
   - preset模式：
     - 如果 execution_mode == "sequential"：
       - 获取当前索引（从黑板读取或初始化为0）
       - 选择 preset_texts[current_index]
       - 更新索引：(current_index + 1) % len(preset_texts)
       - 保存新索引到黑板
     - 如果 execution_mode == "random"：
       - 随机选择 preset_texts 中的一个文本
   
   - blackboard模式：
     - 从黑板读取 blackboard_key 对应的文本
   
   - file模式：
     - 读取文件内容

2. 获取输入位置（可选）

3. 移动鼠标到目标位置（如果指定了位置）

4. 可选：清空现有内容（Ctrl+A）

5. 逐字符输入文本

6. 可选：将输入的文本保存到黑板

7. 返回 SUCCESS
```

**状态管理：**

| 属性 | 说明 |
|------|------|
| _current_text_index | 当前执行的文本索引（用于顺序执行） |

**黑板变量：**

| 变量名 | 说明 |
|--------|------|
| {node_id}_text_index | 当前节点的文本索引（用于顺序执行） |
| last_input_text | 最近输入的文本（如果 save_input_text=True） |

**使用示例：**

```
场景1：依次输入多个预设文本
开始节点
  └─ 文本输入节点
      - input_mode: "preset"
      - preset_texts: ["你好", "在吗", "再见"]
      - execution_mode: "sequential"

场景2：随机输入预设文本
开始节点
  └─ 文本输入节点
      - input_mode: "preset"
      - preset_texts: ["哈哈", "嘿嘿", "呵呵"]
      - execution_mode: "random"

场景3：输入提取的文本
开始节点
  └─ 文本提取节点（提取验证码）
      └─ 文本输入节点
          - input_mode: "blackboard"
          - blackboard_key: "extracted_text"
```

---

### 3.2 文本提取节点

**节点类型：** 条件节点

**功能：** 从指定区域提取文本并保存到黑板，可用于后续文本输入或关键词检测

**参数配置：**

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| extract_mode | str | 提取模式 | "all" |
| region | Tuple[int, int, int, int] | 提取区域 | None |
| keywords | str | 关键词（extract_mode="keywords"时使用） | "" |
| language | str | OCR语言 | "简体中文" |
| preprocess_mode | str | 预处理模式 | "默认" |
| output_key | str | 提取文本保存的黑板变量名 | "extracted_text" |
| save_all_text | bool | 是否保存所有识别文本到额外变量 | False |
| all_text_key | str | 所有文本保存的黑板变量名 | "all_ocr_text" |
| save_position | bool | 是否保存检测位置 | True |
| position_key | str | 检测位置保存的黑板变量名 | "last_detection_position" |

**提取模式说明：**

| 模式 | 说明 | 输出内容 |
|------|------|----------|
| all | 提取区域内所有文本 | 完整文本字符串 |
| keywords | 仅提取包含关键词的文本行 | 匹配关键词的文本行（多行用换行符连接） |

**执行流程：**

```
1. 获取指定区域的截图

2. 执行OCR识别，获取所有文本

3. 根据提取模式处理结果：
   - all模式：
     - 直接保存所有识别文本到黑板
   
   - keywords模式：
     - 按行分割文本
     - 筛选包含关键词的行
     - 将匹配的行连接后保存到黑板

4. 可选：保存所有识别文本到额外变量

5. 可选：保存检测位置到黑板

6. 返回成功/失败状态
```

**返回值说明：**

| 情况 | 返回状态 | 黑板内容 |
|------|----------|----------|
| 成功提取文本 | SUCCESS | output_key: 提取的文本 |
| 未识别到文本 | FAILURE | output_key: 空字符串 |
| OCR识别失败 | FAILURE | output_key: 空字符串 |

**使用示例：**

```
场景1：提取验证码并输入
开始节点
  └─ 文本提取节点（提取验证码区域）
      └─ 文本输入节点（输入提取的验证码）

场景2：提取特定关键词文本
开始节点
  └─ 文本提取节点
      - extract_mode: "keywords"
      - keywords: "价格"
      └─ 变量判断节点（判断价格是否符合条件）

场景3：提取文本用于后续检测
开始节点
  └─ 文本提取节点（提取物品名称）
      └─ OCR检测节点（检测提取的名称是否存在）
```

**与现有OCR检测节点的区别：**

| 节点 | 功能 | 输出 |
|------|------|------|
| OCRConditionNode | 检测关键词是否存在 | 位置（用于点击） |
| TextExtractNode | 提取文本内容 | 文本内容（用于输入或判断） |

---

## 4 GUI设计

### 4.1 节点面板新增节点

在节点面板中新增以下节点：

**动作节点：**
- 文本输入节点

**条件节点：**
- 文本提取节点

### 4.2 属性面板字段类型

新增字段类型：

| 字段类型 | 组件 | 说明 |
|----------|------|------|
| text_list | CTkTextbox + 添加/删除按钮 | 文本列表编辑器 |

---

## 5 数据流设计

### 5.1 文本处理数据流

```
文本提取节点
    ↓
OCR识别
    ↓
提取文本
    ↓
blackboard.set(output_key, text)
    ↓
文本输入节点读取文本
    ↓
blackboard.get(blackboard_key)
    ↓
输入文本
```

---

## 6 错误处理

### 6.1 文本输入相关错误

| 错误场景 | 处理方式 |
|----------|----------|
| 预设文本列表为空 | 返回 FAILURE，记录日志 |
| 黑板变量不存在 | 返回 FAILURE，记录日志 |
| 文件不存在 | 返回 FAILURE，记录日志 |
| 文件读取失败 | 返回 FAILURE，记录日志 |

### 6.2 文本提取相关错误

| 错误场景 | 处理方式 |
|----------|----------|
| OCR识别失败 | 返回 FAILURE，记录日志 |
| 未识别到文本 | 返回 FAILURE，记录日志 |
| 关键词未匹配 | 返回 FAILURE，记录日志 |

---

## 7 测试计划

### 7.1 单元测试

| 测试项 | 测试内容 |
|--------|----------|
| TextInputNode | 多种输入模式、顺序/随机执行 |
| TextExtractNode | 全文提取、关键词提取 |

### 7.2 集成测试

| 测试场景 | 测试内容 |
|----------|----------|
| 文本提取 + 文本输入 | 完整流程测试 |

### 7.3 用户验收测试

| 测试场景 | 预期结果 |
|----------|----------|
| 提取验证码并输入 | 成功输入验证码 |
| 依次输入多个预设文本 | 按顺序输入文本 |
| 随机输入预设文本 | 随机选择文本输入 |

---

## 8 实现计划

### 8.1 开发阶段

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| 第一阶段 | 文本输入节点 | 1天 |
| 第二阶段 | 文本提取节点 | 1天 |
| 第三阶段 | GUI集成 | 0.5天 |
| 第四阶段 | 测试与修复 | 0.5天 |

### 8.2 依赖关系

```
TextInputNode
    ↓
TextExtractNode
```

---

## 9 依赖库

```python
# 图像处理
from PIL import Image

# OCR识别
from rapidocr_onnxruntime import RapidOCR

# 剪贴板
import pyperclip

# 类型提示
from typing import Optional, Tuple, List
```

**requirements.txt 新增：**
```
pyperclip>=1.8.2
```

---

## 10 风险评估

### 10.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| OCR识别准确率 | 中 | 提供预处理模式选项 |
| 文本输入速度慢 | 低 | 提供输入间隔配置 |

### 10.2 用户体验风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 文本输入速度慢 | 低 | 提供输入间隔配置 |

---

## 11 总结

本设计文档详细描述了文本处理功能的设计方案，包括文本输入节点和文本提取节点。文本输入节点支持多种输入源和执行模式，文本提取节点支持全文提取和关键词提取。两个节点通过黑板系统集成，可以实现动态文本交互场景。
