# 项目命名统一改造 - 人工回归测试用例

> 适用范围：阶段1（改造1/2/3/7/9/10/11）+ 阶段2（改造4/5/6/8）
> 测试环境：Windows + 应用程序 `autodoor_behavior_tree`
> 前置条件：已部署包含全部改造的代码版本

---

## 测试用例总览

| 用例编号 | 所属阶段 | 改造点 | 测试目标 | 预计耗时 |
|---------|---------|--------|---------|---------|
| TC-01 | 阶段1 | 改造1/9 | 新建项目目录结构与 project.json 字段 | 2 分钟 |
| TC-02 | 阶段1 | 改造2/3 | 项目名解析以文件夹名为权威源 | 2 分钟 |
| TC-03 | 阶段1 | 改造7 | tree.json 的 format_type/version 统一 | 3 分钟 |
| TC-04 | 阶段1 | 改造10 | app_version 动态读取 build_info.json | 1 分钟 |
| TC-05 | 阶段1 | 改造11 | ZIP 导入后 project_info.name 强制同步 | 3 分钟 |
| TC-06 | 阶段2 | 改造4 | Tab 双击重命名（仅改 project_info.name） | 5 分钟 |
| TC-07 | 阶段2 | 改造4 | 运行中禁止重命名 | 2 分钟 |
| TC-08 | 阶段2 | 改造4 | 未保存项目禁止重命名 | 2 分钟 |
| TC-09 | 阶段2 | 改造5 | 打开项目时一致性校验弹窗 | 4 分钟 |
| TC-10 | 阶段2 | 改造6 | 导出 ZIP 时一致性校验弹窗 | 4 分钟 |
| TC-11 | 阶段2 | 改造8 | 保存后 tree.json 路径强制正斜杠 | 3 分钟 |
| TC-12 | 阶段2 | 改造8 | 子树引用路径规范化 | 3 分钟 |
| TC-13 | 跨阶段 | 全部 | ZIP 导出→导入闭环一致性 | 5 分钟 |
| TC-14 | 跨阶段 | 全部 | 旧项目（旧 format_type）向后兼容 | 3 分钟 |

---

## 阶段1 测试用例

### TC-01 新建项目目录结构与 project.json 字段

**改造点**：改造1（constants.py 集中化）、改造9（清除 resources 死代码）

**步骤**：
1. 启动应用程序
2. 点击"新建项目"，在 `D:\test_workspace` 下创建名为 `TestProject01` 的项目
3. 用文件管理器打开 `D:\test_workspace\TestProject01`

**预期结果**：
- [ ] 目录结构包含以下子目录：
  - `images/templates`、`images/screenshots`
  - `scripts/script`、`scripts/code`
  - `audio/alarms`、`data/config`
  - `cache`、`docs`
- [ ] 根目录存在 `project.json` 和 `tree.json`
- [ ] `project.json` 内容中：
  - `format_type` 字段值为 `"behavior_tree_project"`
  - `project_info.name` 字段值为 `"TestProject01"`（与文件夹名一致）
  - `project_info.app_version` 字段存在且非空
  - **不存在** `resources` 字段（死代码已清除）
- [ ] `tree.json` 内容中：
  - `version` 字段值为 `"2.1"`
  - `format_type` 字段值为 `"behavior_tree"`

---

### TC-02 项目名解析以文件夹名为权威源

**改造点**：改造2（resolve_project_name）、改造3（替换 os.path.basename）

**步骤**：
1. 创建项目 `TestProject02`，在 Tab 中观察显示名
2. 关闭应用
3. 在文件管理器中将文件夹 `TestProject02` 重命名为 `RenamedProject`
4. 重新启动应用，打开 `RenamedProject`

**预期结果**：
- [ ] 创建时 Tab 显示名为 `TestProject02`
- [ ] 重命名文件夹后重新打开，Tab 显示名为 `RenamedProject`（跟随文件夹名）
- [ ] 窗口标题栏显示 `RenamedProject`
- [ ] 若此时 `project.json` 中 `project_info.name` 仍为 `TestProject02`，应触发一致性校验弹窗（见 TC-09）

---

### TC-03 tree.json 的 format_type/version 统一

**改造点**：改造7（统一 format_type/version）

**步骤**：
1. 创建项目 `TestProject03`
2. 在画布中添加一个 StartNode、一个 SequenceNode、一个 ActionNode
3. 连接节点，保存项目
4. 用文本编辑器打开 `tree.json`

**预期结果**：
- [ ] `version` 为 `"2.1"`（不再是 `"2.0"`）
- [ ] `format_type` 为 `"behavior_tree"`（不再是 `"behavior_tree_editor"`）
- [ ] 所有节点的 `config` 中无 `version`/`format_type` 字段污染

---

### TC-04 app_version 动态读取

**改造点**：改造10（app_version 动态读取 build_info.json）

**步骤**：
1. 用文本编辑器打开 `bt_utils/build_info.json`，记录 `version` 字段值（如 `1.6.1a`）
2. 创建新项目 `TestProject04`
3. 打开 `project.json`

**预期结果**：
- [ ] `project_info.app_version` 字段值与 `build_info.json` 中的 `version` 一致
- [ ] 不再是硬编码的 `"1.2.2a"` 等旧值

---

### TC-05 ZIP 导入后 project_info.name 强制同步

**改造点**：改造11（ZIP 导入命名统一）

**步骤**：
1. 创建项目 `ZipSource`，保存
2. 导出为 `ZipSource.zip`
3. 用文本编辑器修改 ZIP 内的 `project.json`，将 `project_info.name` 改为 `HackedName`（或直接在源项目中改后重新导出）
4. 导入该 ZIP 到新目录，导入时如果提示重名，使用默认名或 `ImportedProject`

**预期结果**：
- [ ] 导入成功，生成新项目文件夹
- [ ] 新项目的 `project.json` 中 `project_info.name` = **实际文件夹名**（不是 `HackedName`）
- [ ] 打开导入的项目时**不**触发一致性校验弹窗（因为已强制同步）

---

## 阶段2 测试用例

### TC-06 Tab 双击重命名（仅改 project_info.name）

**改造点**：改造4（Tab 双击重命名 UI）

**步骤**：
1. 创建并保存项目 `TabRenameTest`
2. 在 Tab 栏双击项目名 `TabRenameTest`
3. 进入编辑模式，输入新名称 `NewTabName`，按回车确认
4. 用文件管理器查看项目目录

**预期结果**：
- [ ] 双击后 Tab 名称变为可编辑输入框，原文本被全选
- [ ] 回车后 Tab 显示名更新为 `NewTabName`
- [ ] 窗口标题栏更新为 `NewTabName`
- [ ] **文件夹名保持不变**（仍为 `TabRenameTest`），客户端不修改文件夹名
- [ ] `project.json` 中 `project_info.name` 更新为 `NewTabName`
- [ ] 按 ESC 可取消编辑，名称恢复原值

**附加验证**：
- 输入空名称按回车 → 取消编辑，名称不变
- 输入与原名称相同 → 取消编辑
- 输入超长字符串（>100 字符）→ 拒绝并提示

---

### TC-07 运行中禁止重命名

**改造点**：改造4（运行时禁止重命名）

**步骤**：
1. 打开已保存的项目 `RunningRenameTest`
2. 点击 Tab 上的运行按钮 ▶ 启动行为树运行
3. 运行中双击 Tab 名称尝试重命名

**预期结果**：
- [ ] 弹出提示框："项目运行中，无法重命名。请先停止运行。"
- [ ] 不进入编辑模式
- [ ] 点击停止按钮 ■ 停止运行后，双击可正常进入编辑模式

---

### TC-08 未保存项目禁止重命名

**改造点**：改造4（未保存项目禁止重命名）

**步骤**：
1. 启动应用，新建一个项目但**不保存**（直接在空白 Tab 上操作）
2. 双击 Tab 名称尝试重命名

**预期结果**：
- [ ] 弹出提示框："项目尚未保存，无法重命名。请先保存项目。"
- [ ] 不进入编辑模式
- [ ] 保存项目后，双击可正常进入编辑模式

---

### TC-09 打开项目时一致性校验弹窗

**改造点**：改造5（打开项目一致性校验）

**步骤**：
1. 创建项目 `ConsistencyOpenTest`，保存并关闭
2. 用文本编辑器打开 `project.json`，将 `project_info.name` 改为 `DifferentName`（与文件夹名不一致）
3. 启动应用，打开该项目

**预期结果**：
- [ ] 弹出一致性校验对话框，提示"文件夹名与项目名称不一致"
- [ ] 对话框显示两个名称：文件夹名 `ConsistencyOpenTest` vs 项目名 `DifferentName`
- [ ] 提供选项：
  - "同步项目名称为文件夹名称"（推荐）→ 选择后 `project_info.name` 改为 `ConsistencyOpenTest`
  - "手动修改文件夹名称"→ 用户自行在文件管理器改文件夹名
  - "取消"→ 不修改，照常打开
- [ ] 选择"同步"后，`project.json` 的 `project_info.name` 更新为 `ConsistencyOpenTest`
- [ ] 选择"同步"后 Tab 显示名为 `ConsistencyOpenTest`

---

### TC-10 导出 ZIP 时一致性校验弹窗

**改造点**：改造6（导出 ZIP 一致性校验）

**步骤**：
1. 创建项目 `ConsistencyExportTest`，保存
2. 双击 Tab 重命名 `project_info.name` 为 `ExportedName`（此时文件夹名仍为 `ConsistencyExportTest`）
3. 点击"导出 ZIP"

**预期结果**：
- [ ] 导出前弹出一致性校验对话框
- [ ] 提供选项：
  - "同步并继续导出"→ `project_info.name` 改回文件夹名，然后导出
  - "直接导出不同步"→ 保持不一致状态直接导出
  - "取消导出"→ 中止导出
- [ ] 选择"同步并继续"→ 导出的 ZIP 内 `project_info.name` = `ConsistencyExportTest`
- [ ] 选择"直接导出不同步"→ 导出的 ZIP 内 `project_info.name` = `ExportedName`
- [ ] 选择"取消导出"→ 不生成 ZIP 文件

---

### TC-11 保存后 tree.json 路径强制正斜杠

**改造点**：改造8（路径规范化）

**步骤**：
1. 创建项目 `PathNormalizationTest`
2. 添加一个 SubtreeNode 节点，配置 `subtree_path` 为任意子树路径
3. 添加一个带 `template_path` 的节点（如模板匹配节点），选择一个模板图片
4. 保存项目
5. 用文本编辑器打开 `tree.json`，搜索所有 `*_path` 字段

**预期结果**：
- [ ] 所有 `template_path`、`script_path`、`code_path`、`sound_path`、`file_path`、`subtree_path` 字段值均使用**正斜杠 `/`**
- [ ] 不出现反斜杠 `\`（Windows 路径分隔符）
- [ ] 路径前缀 `./` 保持不变
- [ ] 重新打开项目，节点配置路径正确加载，功能正常

---

### TC-12 子树引用路径规范化

**改造点**：改造8（subtree_references.path 规范化）

**步骤**：
1. 创建项目 `SubtreeRefTest`
2. 添加 SubtreeNode，引用一个子树项目（`subtree_path` 指向 `./subtrees/ChildTree`）
3. 保存项目
4. 检查 `tree.json` 是否包含 `subtree_references` 字段

**预期结果**：
- [ ] `subtree_references` 中每个引用的 `path` 字段使用正斜杠
- [ ] `resolved_path` 字段允许使用系统原生分隔符（仅运行时使用，不要求统一）
- [ ] 子树能正常加载和执行

---

## 跨阶段综合测试

### TC-13 ZIP 导出→导入闭环一致性

**改造点**：全部（端到端验证）

**步骤**：
1. 创建项目 `E2ELoop`，添加若干节点（含 SubtreeNode 和带资源的 ActionNode）
2. 保存项目
3. 导出为 ZIP
4. 删除原项目文件夹
5. 导入 ZIP 到新位置

**预期结果**：
- [ ] 导入成功，新项目可正常打开
- [ ] 新项目 Tab 显示名 = 新文件夹名（resolve_project_name 生效）
- [ ] 新项目 `project_info.name` = 新文件夹名（强制同步生效）
- [ ] 新项目 `tree.json` 中所有路径使用正斜杠
- [ ] 新项目 `format_type` = `"behavior_tree"`、`version` = `"2.1"`
- [ ] 节点结构、连接关系、资源配置完整保留
- [ ] 子树引用能正常解析（若子树项目一同导入）

---

### TC-14 旧项目（旧 format_type）向后兼容

**改造点**：改造7（向后兼容）

**步骤**：
1. 找一个改造前创建的旧项目（`tree.json` 中 `format_type` 为 `behavior_tree_editor` 或 `behavior_tree_standalone`，`version` 为 `2.0`）
2. 用改造后的应用打开该旧项目
3. 修改并保存

**预期结果**：
- [ ] 打开时不报错（向后兼容，仅可能输出警告日志）
- [ ] 打开后节点结构完整，可正常编辑
- [ ] 保存后 `tree.json` 的 `format_type` 更新为 `"behavior_tree"`、`version` 更新为 `"2.1"`
- [ ] 保存后路径规范化生效（反斜杠转正斜杠）

---

## 自动化测试执行

以下自动化测试已全部通过，可作为人工测试的补充：

```bash
# 阶段2-改造8 路径规范化 + 阶段1回归（12 项）
python tests\test_stage2_path_normalization.py

# 阶段2 改造4/5/6 验证（8 项）
python tests\test_stage2_gui_verification.py

# 全面集成测试（3 项）
python tests\test_full_integration.py
```

**自动化测试覆盖矩阵**：

| 改造点 | 自动化测试 | 人工测试 |
|--------|-----------|---------|
| 改造1 constants.py | test_constants_ssot_consistency | TC-01 |
| 改造2 resolve_project_name | test_stage1_resolve_project_name | TC-02 |
| 改造3 替换 basename | test_resolve_project_name_used_everywhere | TC-02 |
| 改造4 Tab 重命名 | test_tab_bar_has_rename_logic, test_editor_has_stage2_methods | TC-06/07/08 |
| 改造5 打开校验 | test_open_callback_wiring, test_consistency_check_uses_project_manager | TC-09 |
| 改造6 导出校验 | test_export_callback_wiring | TC-10 |
| 改造7 format_type 统一 | test_serializer_serialize_applies_normalization | TC-03/14 |
| 改造8 路径规范化 | test_normalize_node_paths_*, test_serializer_serialize_applies_normalization | TC-11/12 |
| 改造9 死代码清除 | test_stage1_create_project_uses_constants | TC-01 |
| 改造10 app_version | （隐式覆盖） | TC-04 |
| 改造11 ZIP 导入同步 | test_stage1_zip_import_forces_sync | TC-05/13 |

---

## 缺陷报告模板

如发现缺陷，请按以下格式记录：

```
缺陷编号：BUG-XXX
关联用例：TC-XX
严重等级：致命/严重/一般/轻微
环境：Windows XX, Python XX
复现步骤：
1. 
2. 
3. 
预期结果：
实际结果：
附件：（截图/日志）
```
