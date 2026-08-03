# 插件使用说明：文件处理 & Excel 自动化

> 版本：v1.0.0 | 更新日期：2026-07-31
> 适用版本：AutoDoor Behavior Tree v2.0+

---

## 目录

- [第一部分：文件处理插件](#第一部分文件处理插件)
  - [1. 插件概述](#1-插件概述)
  - [2. 加载与启动](#2-加载与启动)
  - [3. 节点详解](#3-节点详解)
  - [4. 使用示例](#4-使用示例)
  - [5. 典型应用场景](#5-典型应用场景)
- [第二部分：Excel 自动化插件](#第二部分excel-自动化插件)
  - [6. 插件概述](#6-插件概述)
  - [7. 前置依赖](#7-前置依赖)
  - [8. 加载与启动](#8-加载与启动)
  - [9. 节点详解](#9-节点详解)
  - [10. 使用示例](#10-使用示例)
  - [11. 适配器 API](#11-适配器-api)
  - [12. 典型应用场景](#12-典型应用场景)
- [第三部分：组合使用](#第三部分组合使用)
  - [13. 文件处理 + Excel 自动化联动示例](#13-文件处理--excel-自动化联动示例)
- [第四部分：常见问题](#第四部分常见问题)

---

# 第一部分：文件处理插件

## 1. 插件概述

**插件标识**：`file_processor`
**显示名称**：文件处理
**分类**：办公自动化
**提供节点**：3 个

| 节点 | 显示名 | 图标 | 功能 |
|------|--------|------|------|
| `FileReadNode` | 文件读取 | 📄 | 读取文件内容到黑板 |
| `FileWriteNode` | 文件写入 | 📝 | 将黑板数据写入文件 |
| `FileMoveNode` | 文件移动 | 📁 | 移动或重命名文件 |

**核心概念**：黑板（Blackboard）是节点间共享数据的机制。文件处理插件的「读取」节点将文件内容存入黑板，「写入」节点从黑板读取数据并写入文件，实现数据在行为树流程中的流转。

## 2. 加载与启动

### 通过 GUI

1. 点击顶部「🔌 插件管理」Tab
2. 在插件列表中找到「文件处理」
3. 点击「启动」按钮，状态变为绿色 ●
4. 切换到「🌲 行为树编辑器」，节点面板的「插件节点」分类将出现 3 个文件处理节点

### 通过 CLI

```bash
# 查看插件列表
python cli.py plugin list

# 启动插件
python cli.py plugin start file_processor

# 查看插件详情
python cli.py plugin info file_processor
```

## 3. 节点详解

### 3.1 文件读取（FileReadNode）

将指定文件的完整内容读取到黑板中。

**配置项**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 文件路径 `file_path` | text | (空) | 要读取的文件完整路径 |
| 编码 `encoding` | text | `utf-8` | 文件编码（如 `gbk`、`utf-16`） |
| 目标键名 `target_key` | text | `file_content` | 内容存入黑板的键名 |

**执行逻辑**：

1. 检查文件路径是否为空、文件是否存在
2. 以指定编码读取文件全部内容
3. 将内容写入黑板（键名为 `target_key`）
4. 返回 `SUCCESS`；文件不存在或读取失败返回 `FAILURE`

**使用场景**：
- 读取配置文件供后续节点使用
- 读取日志文件进行分析
- 读取模板文件作为数据来源

### 3.2 文件写入（FileWriteNode）

将黑板中的数据写入到指定文件。

**配置项**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 文件路径 `file_path` | text | (空) | 要写入的文件完整路径 |
| 源键名 `source_key` | text | `file_content` | 从黑板读取数据的键名 |
| 编码 `encoding` | text | `utf-8` | 文件编码 |
| 追加模式 `append` | bool | `False` | 勾选为追加写入，否则覆盖写入 |

**执行逻辑**：

1. 检查文件路径是否为空
2. 从黑板读取 `source_key` 对应的数据
3. 自动创建不存在的父目录
4. 根据 `append` 选择写入模式（`a` 追加 / `w` 覆盖）
5. 将数据转为字符串后写入文件
6. 返回 `SUCCESS`；数据为空或写入失败返回 `FAILURE`

**使用场景**：
- 将行为树执行结果保存到文件
- 生成日志或报告文件
- 导出数据供其他程序使用

### 3.3 文件移动（FileMoveNode）

将文件从源路径移动到目标路径（支持重命名）。

**配置项**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 源路径 `source_path` | text | (空) | 要移动的文件路径 |
| 目标路径 `target_path` | text | (空) | 移动后的目标路径 |

**执行逻辑**：

1. 检查源路径和目标路径是否都已填写
2. 检查源文件是否存在
3. 自动创建目标路径的父目录
4. 使用 `shutil.move()` 移动文件
5. 返回 `SUCCESS`；源文件不存在或移动失败返回 `FAILURE`

**使用场景**：
- 文件归档：将处理完的日志移到归档目录
- 文件整理：按规则重命名或归类文件
- 流程衔接：将上一步产出的文件移动到下一步的输入目录

## 4. 使用示例

### 示例 1：读取配置 → 修改 → 保存

```
┌─────────────────────────────────────────┐
│ StartNode                                │
│  ├── FileReadNode    读取配置文件        │
│  ├── [处理节点]      修改黑板数据        │
│  └── FileWriteNode   保存修改后的配置    │
└─────────────────────────────────────────┘
```

**FileReadNode 配置**：
- 文件路径：`D:/config/app.json`
- 编码：`utf-8`
- 目标键名：`config_data`

**FileWriteNode 配置**：
- 文件路径：`D:/config/app_updated.json`
- 源键名：`config_data`
- 编码：`utf-8`
- 追加模式：否

### 示例 2：日志归档

```
┌─────────────────────────────────────────┐
│ StartNode                                │
│  ├── FileReadNode    读取当天日志        │
│  ├── [条件节点]      检查是否有错误      │
│  └── FileMoveNode    将日志移到归档目录  │
└─────────────────────────────────────────┘
```

**FileMoveNode 配置**：
- 源路径：`D:/logs/today.log`
- 目标路径：`D:/archive/2026-07-31/today.log`

### 示例 3：追加写入报告

```
┌─────────────────────────────────────────┐
│ StartNode                                │
│  ├── FileWriteNode  追加报告标题        │
│  ├── [动作节点]     生成报告内容        │
│  └── FileWriteNode  追加报告内容        │
└─────────────────────────────────────────┘
```

**第一个 FileWriteNode 配置**：
- 文件路径：`D:/reports/daily.txt`
- 源键名：`report_title`
- 追加模式：是

**第二个 FileWriteNode 配置**：
- 文件路径：`D:/reports/daily.txt`
- 源键名：`report_content`
- 追加模式：是

## 5. 典型应用场景

| 场景 | 节点组合 | 说明 |
|------|---------|------|
| 配置文件热更新 | Read → [修改] → Write | 读取配置、修改参数、保存回文件 |
| 日志自动归档 | Read → [检查] → Move | 读取日志、检查错误、移动到归档 |
| 批量数据导出 | [生成数据] → Write | 将黑板数据导出为文件 |
| 多文件合并 | Read(文件A) → Write(合并结果) → Read(文件B) → Write | 依次读取多个文件并追加写入 |
| 文件筛选整理 | [条件判断] → Move | 根据条件将文件移动到不同目录 |

---

# 第二部分：Excel 自动化插件

## 6. 插件概述

**插件标识**：`excel_automation`
**显示名称**：Excel 自动化
**分类**：办公自动化
**提供节点**：3 个 + 1 个适配器

| 节点/适配器 | 显示名 | 图标 | 功能 |
|------------|--------|------|------|
| `ExcelReadNode` | Excel读取 | 📊 | 读取 Excel 单元格范围到黑板 |
| `ExcelWriteNode` | Excel写入 | 📈 | 将黑板数据写入 Excel 文件 |
| `ExcelFormatNode` | Excel格式化 | 🎨 | 应用单元格格式（加粗、背景色） |
| `ExcelAdapter` | Excel适配器 | — | 封装工作簿操作的适配器 |

## 7. 前置依赖

Excel 自动化插件依赖 `openpyxl` 库。

### 安装依赖

```bash
pip install openpyxl>=3.0.0
```

### 依赖检测

如果未安装 `openpyxl`，所有 Excel 节点会直接返回 `FAILURE`，不会执行任何操作。请确保在使用前已安装依赖。

## 8. 加载与启动

### 通过 GUI

1. 点击顶部「🔌 插件管理」Tab
2. 在插件列表中找到「Excel 自动化」
3. 点击「启动」按钮
4. 若未安装 `openpyxl`，节点仍会出现在面板上，但执行时会失败

### 通过 CLI

```bash
# 安装依赖
pip install openpyxl

# 启动插件
python cli.py plugin start excel_automation
```

## 9. 节点详解

### 9.1 Excel 读取（ExcelReadNode）

从 Excel 文件的指定 Sheet 中读取单元格范围，存入黑板。

**配置项**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 文件路径 `file_path` | text | (空) | Excel 文件路径（`.xlsx` 格式） |
| Sheet 名 `sheet_name` | text | (空) | 要读取的 Sheet 名，留空读取当前活动 Sheet |
| 单元格范围 `cell_range` | text | `A1:Z100` | 读取范围，如 `A1:B10`、`A1:Z100` |
| 目标键名 `target_key` | text | `excel_data` | 数据存入黑板的键名 |

**执行逻辑**：

1. 检查 `openpyxl` 是否可用
2. 打开 Excel 文件（以 `data_only=True` 模式读取公式值）
3. 定位到指定 Sheet（留空则使用活动 Sheet）
4. 解析单元格范围，逐行逐列读取数据
5. 将二维数组存入黑板
6. 返回 `SUCCESS`

**黑板数据结构**：
```python
# 读取 A1:B3 的结果
# 黑板中 target_key = "excel_data"
[
    ["姓名", "年龄"],      # 第1行
    ["张三", 25],          # 第2行
    ["李四", 30],          # 第3行
]
```

### 9.2 Excel 写入（ExcelWriteNode）

将黑板中的二维数组数据写入 Excel 文件。

**配置项**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 文件路径 `file_path` | text | (空) | Excel 文件路径 |
| Sheet 名 `sheet_name` | text | `Sheet1` | 要写入的 Sheet 名 |
| 数据键名 `data_key` | text | `table_data` | 从黑板读取数据的键名 |
| 起始单元格 `start_cell` | text | `A1` | 写入的起始位置（如 `A1`、`B2`） |

**执行逻辑**：

1. 检查 `openpyxl` 是否可用
2. 从黑板读取 `data_key` 对应的数据（必须是二维数组）
3. 如果文件已存在：打开文件，查找或创建 Sheet
4. 如果文件不存在：创建新工作簿，设置 Sheet 名
5. 从起始单元格开始，逐行逐列写入数据
6. 保存文件
7. 返回 `SUCCESS`

**黑板数据要求**：
```python
# 写入前黑板中 data_key = "table_data" 的数据
[
    ["姓名", "年龄", "城市"],
    ["张三", 25, "北京"],
    ["李四", 30, "上海"],
]
```

### 9.3 Excel 格式化（ExcelFormatNode）

对 Excel 文件的指定单元格范围应用格式。

**配置项**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 文件路径 `file_path` | text | (空) | Excel 文件路径 |
| Sheet 名 `sheet_name` | text | (空) | Sheet 名，留空使用活动 Sheet |
| 单元格范围 `cell_range` | text | `A1:A1` | 要格式化的范围 |
| 加粗 `bold` | bool | `False` | 是否设置字体加粗 |
| 背景色 `bg_color` | text | (空) | 十六进制颜色值，如 `#FF0000`，留空不设置背景色 |

**执行逻辑**：

1. 检查 `openpyxl` 是否可用
2. 打开 Excel 文件
3. 定位到指定 Sheet
4. 创建 `Font`（加粗设置）和 `PatternFill`（背景色设置）
5. 遍历范围内所有单元格，应用格式
6. 保存文件
7. 返回 `SUCCESS`

**颜色值说明**：
- 使用十六进制格式：`#RRGGBB`
- 常用颜色：`#FF0000`（红）、`#00FF00`（绿）、`#0000FF`（蓝）、`#FFFF00`（黄）、`#000000`（黑）、`#FFFFFF`（白）

## 10. 使用示例

### 示例 1：读取 Excel → 处理 → 写回

```
┌──────────────────────────────────────────┐
│ StartNode                                 │
│  ├── ExcelReadNode   读取原始数据        │
│  ├── [处理节点]      修改黑板中的数据     │
│  ├── ExcelWriteNode  写回 Excel          │
│  └── ExcelFormatNode 格式化标题行        │
└──────────────────────────────────────────┘
```

**ExcelReadNode 配置**：
- 文件路径：`D:/data/report.xlsx`
- Sheet 名：`原始数据`
- 单元格范围：`A1:D50`
- 目标键名：`raw_data`

**ExcelWriteNode 配置**：
- 文件路径：`D:/data/report_processed.xlsx`
- Sheet 名：`处理结果`
- 数据键名：`processed_data`
- 起始单元格：`A1`

**ExcelFormatNode 配置**：
- 文件路径：`D:/data/report_processed.xlsx`
- Sheet 名：`处理结果`
- 单元格范围：`A1:D1`
- 加粗：是
- 背景色：`#4472C4`

### 示例 2：生成汇总报表

```
┌──────────────────────────────────────────┐
│ StartNode                                 │
│  ├── ExcelReadNode   读取销售明细        │
│  ├── [代码节点]      汇总数据到黑板      │
│  ├── ExcelWriteNode  写入汇总表          │
│  └── ExcelFormatNode 设置表头格式        │
└──────────────────────────────────────────┘
```

### 示例 3：多 Sheet 操作

```
┌──────────────────────────────────────────┐
│ StartNode                                 │
│  ├── ExcelReadNode   读取 Sheet1 数据    │
│  ├── ExcelReadNode   读取 Sheet2 数据    │
│  ├── [合并节点]      合并两个数据集      │
│  └── ExcelWriteNode  写入新 Sheet        │
└──────────────────────────────────────────┘
```

## 11. 适配器 API

Excel 插件提供 `ExcelAdapter` 适配器，可在自定义节点中直接操作工作簿。

### 获取适配器

```python
# 在自定义节点中
adapter = self.context.get_adapter("excel")
if adapter and adapter.is_available():
    wb = adapter.open("D:/data/report.xlsx")
    # ... 操作工作簿 ...
    adapter.save("D:/data/report.xlsx")
    adapter.close("D:/data/report.xlsx")
```

### 适配器方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `is_available()` | 无 | `bool` | 检查 `openpyxl` 是否可用 |
| `open(file_path, read_only=False)` | 文件路径、只读模式 | 工作簿对象或 `None` | 打开工作簿 |
| `create(file_path)` | 文件路径 | 工作簿对象或 `None` | 创建新工作簿 |
| `save(file_path)` | 文件路径 | `bool` | 保存工作簿 |
| `close(file_path)` | 文件路径 | `None` | 关闭指定工作簿 |
| `close_all()` | 无 | `None` | 关闭所有已打开的工作簿 |

### 使用适配器的优势

- 减少重复打开/关闭文件的开销
- 在多个节点间共享工作簿实例
- 支持更复杂的操作（如公式、图表等）

## 12. 典型应用场景

| 场景 | 节点组合 | 说明 |
|------|---------|------|
| 数据导入 | ExcelReadNode → [处理] → FileWriteNode | 从 Excel 读取数据，转换后写入文本文件 |
| 报表生成 | [生成数据] → ExcelWriteNode → ExcelFormatNode | 生成 Excel 报表并设置格式 |
| 数据同步 | ExcelReadNode → [对比] → ExcelWriteNode | 读取源数据，与目标对比后更新 |
| 批量处理 | ExcelReadNode → [循环处理] → ExcelWriteNode | 读取批量数据，逐条处理后写回 |
| 数据导出 | FileReadNode → [解析] → ExcelWriteNode | 读取文本/JSON，解析后导出为 Excel |
| 格式美化 | ExcelReadNode → ExcelFormatNode | 读取 Excel 后应用统一格式 |

---

# 第三部分：组合使用

## 13. 文件处理 + Excel 自动化联动示例

### 场景：从文本日志提取数据 → 生成 Excel 报表

```
┌───────────────────────────────────────────────────────┐
│ StartNode                                              │
│  ├── FileReadNode      读取日志文件                    │
│  ├── [代码节点]        解析日志，提取关键字段到黑板     │
│  │   代码:                                             │
│  │     import re                                       │
│  │     lines = context.blackboard.get("log_content", "")│
│  │     rows = []                                       │
│  │     for line in lines.splitlines():                 │
│  │         m = re.match(r'(\d+).*(ERROR|WARN).*(.*)', line) │
│  │         if m:                                       │
│  │             rows.append([m.group(1), m.group(2), m.group(3)]) │
│  │     context.blackboard.set("report_data", rows)     │
│  ├── ExcelWriteNode    将提取的数据写入 Excel           │
│  ├── ExcelFormatNode  格式化表头                       │
│  └── FileMoveNode      将原始日志移到归档目录           │
└───────────────────────────────────────────────────────┘
```

**完整配置清单**：

| 节点 | 关键配置 |
|------|---------|
| FileReadNode | 文件路径=`D:/logs/app.log`，目标键名=`log_content` |
| 代码节点 | 从黑板读取 `log_content`，解析后写入 `report_data` |
| ExcelWriteNode | 文件路径=`D:/reports/daily_report.xlsx`，数据键名=`report_data` |
| ExcelFormatNode | 范围=`A1:D1`，加粗=是，背景色=`#4472C4` |
| FileMoveNode | 源=`D:/logs/app.log`，目标=`D:/archive/app_20260731.log` |

### 场景：读取 CSV → 写入 Excel → 格式化

虽然没有 CSV 专用节点，但可以通过文件读取 + 代码节点 + Excel 写入实现：

```
FileReadNode(读取CSV) → [代码节点(解析CSV为二维数组)] → ExcelWriteNode → ExcelFormatNode
```

---

# 第四部分：常见问题

## Q1: 节点执行总是返回 FAILURE？

**排查步骤**：

1. **文件路径是否正确**：在属性面板检查路径是否填写完整
2. **文件是否存在**：对于读取类节点，确认文件确实存在
3. **黑板数据是否为空**：对于写入类节点，确认黑板中是否有对应键名的数据
4. **依赖是否安装**：Excel 节点需要 `openpyxl`，在终端运行 `pip list | grep openpyxl`

## Q2: Excel 节点报"openpyxl 未安装"？

**解决方法**：

```bash
pip install openpyxl>=3.0.0
```

安装后重启行为树引擎（无需重启应用）即可生效。

## Q3: 文件写入后内容为空？

**排查步骤**：

1. 检查黑板中对应 `source_key` / `data_key` 是否有数据
2. 确认数据格式：
   - `FileWriteNode`：黑板中存储的是字符串
   - `ExcelWriteNode`：黑板中存储的是二维数组 `[[...], [...], ...]`
3. 在代码节点中添加 `print()` 或使用调试节点确认数据

## Q4: 中文文件乱码？

**解决方法**：在节点配置中将编码设置为 `gbk` 或 `gb2312`（Windows 中文系统常用编码）。

## Q5: Excel 读取结果中数字变成字符串？

**说明**：`ExcelReadNode` 使用 `data_only=True` 模式读取，公式单元格会返回计算结果而非公式本身。这是正常行为。

## Q6: 如何在代码节点中获取/设置黑板数据？

```python
# 读取黑板数据
data = context.blackboard.get("key_name", "默认值")

# 写入黑板数据
context.blackboard.set("key_name", value)
```

## Q7: Excel 文件被占用无法写入？

**解决方法**：
- 关闭其他正在打开该 Excel 的程序
- 使用不同的文件名写入
- 在节点配置中添加延时，等待文件释放

## Q8: 如何调试节点执行过程？

**方法**：
1. 在代码节点中使用 `print()` 输出调试信息
2. 查看终端日志（以 `[Plugin:xxx]` 开头的日志行）
3. 使用「🔌 插件管理」→ 查看插件状态

---

## 附录：节点配置速查表

### 文件处理插件

| 节点 | 关键参数 |
|------|---------|
| **文件读取** | `file_path`, `encoding`, `target_key` |
| **文件写入** | `file_path`, `source_key`, `encoding`, `append` |
| **文件移动** | `source_path`, `target_path` |

### Excel 自动化插件

| 节点 | 关键参数 |
|------|---------|
| **Excel读取** | `file_path`, `sheet_name`, `cell_range`, `target_key` |
| **Excel写入** | `file_path`, `sheet_name`, `data_key`, `start_cell` |
| **Excel格式化** | `file_path`, `sheet_name`, `cell_range`, `bold`, `bg_color` |

### 黑板数据流示意

```
FileReadNode ──► [blackboard: target_key] ──► FileWriteNode
                                                     │
                                              （同一键名）
                                                     ▼
ExcelReadNode ──► [blackboard: target_key] ──► ExcelWriteNode
ExcelWriteNode ◄── [blackboard: data_key] ◄── [代码节点/处理节点]
```
