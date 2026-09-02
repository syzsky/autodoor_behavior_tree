# bt_cli/commands/ai.py
"""ai 命令组 — AI 编排自动化"""
import sys
import os
import json

from bt_cli.errors import exit_with_code, EXIT_CONFIG_ERROR, EXIT_GENERIC_ERROR


def cmd_ai(args):
    """AI 编排命令入口"""
    action = args.ai_action

    if action is None:
        print("请指定操作: plan/select/nodes/scan/generate/validate/test/refine/create/run")
        sys.exit(1)

    if action == "nodes":
        _cmd_nodes(args)
    elif action == "plan":
        _cmd_plan(args)
    elif action == "select":
        _cmd_select(args)
    elif action == "scan":
        _cmd_scan(args)
    elif action == "generate":
        _cmd_generate(args)
    elif action == "validate":
        _cmd_validate(args)
    elif action == "test":
        _cmd_test(args)
    elif action == "refine":
        _cmd_refine(args)
    elif action == "create":
        _cmd_create(args)
    elif action == "run":
        _cmd_run(args)
    else:
        print(f"未知操作: {action}")
        sys.exit(1)


def _check_api_key():
    """检查 API Key 是否已配置，未配置则退出"""
    from config.settings_manager import get_settings_manager

    sm = get_settings_manager()
    api_key = sm.get("ai.llm.api_key", "")
    if not api_key:
        exit_with_code(
            EXIT_CONFIG_ERROR,
            "错误: 未配置 AI API Key\n"
            "请运行: autodoor-bt config set ai.llm.api_key \"your-key\""
        )


def _cmd_nodes(args):
    """列出所有可用节点规格"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_spec_exporter import NodeSpecExporter

    register_all_nodes()
    exporter = NodeSpecExporter()
    specs = exporter.export_all()

    # 按分类输出
    categories = {"composite": "复合节点", "condition": "条件节点",
                  "action": "动作节点", "other": "其他节点"}

    for cat, cat_name in categories.items():
        cat_nodes = {k: v for k, v in specs.items() if v["category"] == cat}
        if not cat_nodes:
            continue
        print(f"\n{'='*60}")
        print(f"  {cat_name}（{len(cat_nodes)} 个）")
        print(f"{'='*60}")
        for node_type, spec in cat_nodes.items():
            print(f"\n  [{node_type}]")
            print(f"    描述: {spec['description']}")
            print(f"    基类: {spec['base_class']}")
            if spec["parameters"]:
                print(f"    参数:")
                for p in spec["parameters"]:
                    default = p["default"]
                    if isinstance(default, str):
                        default_str = f'"{default}"' if default else '""'
                    else:
                        default_str = str(default)
                    print(f"      {p['name']} ({p['type']}) = {default_str}  — {p['desc']}")

    print(f"\n共 {len(specs)} 个节点")


def _cmd_plan(args):
    """阶段① 意图分析"""
    from bt_cli.ai.intent_analyzer import IntentAnalyzer, IntentAnalysisError

    _check_api_key()

    description = args.description
    print(f"正在分析任务描述: {description}")

    try:
        analyzer = IntentAnalyzer()
        plan = analyzer.analyze(description)
    except IntentAnalysisError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"意图分析失败: {e}")

    # 保存到 .ai/ 目录
    ai_dir = _ensure_ai_dir()
    output_path = os.path.join(ai_dir, "plan.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存计划文件失败: {e}")

    print(f"\n任务计划已生成: {output_path}")
    print(f"  任务概述: {plan.get('task_summary', 'N/A')}")
    loop = plan.get("loop", {})
    loop_enabled = loop.get("enabled", False) if isinstance(loop, dict) else False
    if loop_enabled:
        interval = loop.get("interval_ms", "N/A")
        print(f"  循环: 是 (间隔 {interval}ms)")
    else:
        print(f"  循环: 否")
    print(f"  阶段数: {len(plan.get('phases', []))}")
    print(f"\n确认后运行: autodoor-bt ai select plan.json")


def _cmd_select(args):
    """阶段② 节点选型"""
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_selector import NodeSelector, NodeSelectionError

    _check_api_key()

    plan_path = args.plan_file
    if not os.path.exists(plan_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {plan_path}")

    try:
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except json.JSONDecodeError as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: plan.json 解析失败: {e}")
    except OSError as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 读取文件失败: {e}")

    register_all_nodes()
    print("正在进行节点选型...")

    try:
        selector = NodeSelector()
        structure = selector.select(plan)
    except NodeSelectionError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"节点选型失败: {e}")

    # 保存
    ai_dir = _ensure_ai_dir()
    output_path = os.path.join(ai_dir, "structure.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(structure, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存结构文件失败: {e}")

    print(f"\n节点结构已生成: {output_path}")
    print(f"  节点数: {len(structure['nodes'])}")
    for node in structure["nodes"]:
        empty = node.get("empty_params", [])
        empty_str = f" [待填充: {', '.join(empty)}]" if empty else ""
        print(f"    {node['id']} ({node['type']}){empty_str}")
    print(f"\n确认后运行: autodoor-bt ai scan structure.json")


def _cmd_scan(args):
    """阶段③ VLM 屏幕感知"""
    from config.settings_manager import get_settings_manager

    sm = get_settings_manager()
    api_key = sm.get("ai.vlm.api_key", "")
    if not api_key:
        exit_with_code(
            EXIT_CONFIG_ERROR,
            "错误: 未配置 VLM API Key\n"
            "请运行: autodoor-bt config set ai.vlm.api_key \"your-key\""
        )

    structure_path = args.structure_file
    if not os.path.exists(structure_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {structure_path}")

    try:
        with open(structure_path, "r", encoding="utf-8") as f:
            structure = json.load(f)
    except json.JSONDecodeError as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: structure.json 解析失败: {e}")
    except OSError as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 读取文件失败: {e}")

    # 截图
    screenshot_path = os.path.join(_ensure_ai_dir(), "screenshot.png")
    print("正在截取屏幕...")
    _take_screenshot(screenshot_path)

    # 获取任务上下文
    plan_path = os.path.join(os.path.dirname(structure_path), "plan.json")
    task_context = ""
    if os.path.exists(plan_path):
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                plan = json.load(f)
                task_context = plan.get("task_summary", "")
        except (json.JSONDecodeError, OSError):
            pass  # task_context 是可选的，读取失败不阻断流程

    print("VLM 正在分析截图...")

    from bt_cli.ai.vlm_analyzer import VLMAnalyzer, VLMAnalysisError
    try:
        analyzer = VLMAnalyzer()
        suggestions = analyzer.analyze(screenshot_path, structure, task_context)
        filled = analyzer.fill_structure(structure, suggestions)
    except VLMAnalysisError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"VLM 分析失败: {e}")

    # 保存
    ai_dir = _ensure_ai_dir()
    output_path = os.path.join(ai_dir, "structure_filled.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(filled, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存结构文件失败: {e}")

    print(f"\n参数填充完成: {output_path}")
    print(f"  填充建议数: {len(suggestions)}")
    for sug in suggestions:
        conf_mark = "✓" if sug["confidence"] >= 0.8 else "⚠"
        print(f"    {conf_mark} {sug['node_id']}.{sug['param']} = {sug['suggested_value']}"
              f" (置信度: {sug['confidence']:.0%}) — {sug.get('note', '')}")
    print(f"\n确认后运行: autodoor-bt ai generate structure_filled.json")


def _cmd_generate(args):
    """阶段④ 生成 JSON"""
    structure_path = args.structure_file
    if not os.path.exists(structure_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {structure_path}")

    try:
        with open(structure_path, "r", encoding="utf-8") as f:
            structure = json.load(f)
    except json.JSONDecodeError as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: structure.json 解析失败: {e}")
    except OSError as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 读取文件失败: {e}")

    print("正在生成行为树 JSON...")

    from bt_cli.ai.tree_generator import TreeGenerator

    gen = TreeGenerator()
    tree_data, errors = gen.generate_and_validate(structure, canvas_name="AI生成流程")

    if errors:
        print(f"\n校验发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"  - {e}")
        exit_with_code(EXIT_GENERIC_ERROR, "生成失败，请检查节点结构")
    else:
        print("校验通过 ✓")

    # 保存
    ai_dir = _ensure_ai_dir()
    output_path = os.path.join(ai_dir, "tree.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存行为树文件失败: {e}")

    print(f"\n行为树已生成: {output_path}")
    print(f"  节点数: {len(tree_data['nodes'])}")
    print(f"  连接数: {len(tree_data['connections'])}")
    print(f"\n可运行: autodoor-bt run {output_path} --headless")
    print(f"或试运行: autodoor-bt ai test {output_path}")


def _cmd_validate(args):
    """校验 JSON 结构"""
    tree_path = args.tree_file
    if not os.path.exists(tree_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {tree_path}")

    try:
        with open(tree_path, "r", encoding="utf-8") as f:
            tree_data = json.load(f)
    except json.JSONDecodeError as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: tree.json 解析失败: {e}")
    except OSError as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 读取文件失败: {e}")

    from bt_cli.ai.tree_validator import TreeValidator

    validator = TreeValidator()
    errors = validator.validate_with_serializer(tree_data)

    if errors:
        print(f"校验失败，发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"  ✗ {e}")
        exit_with_code(EXIT_GENERIC_ERROR, "校验失败")
    else:
        print("校验通过 ✓")
        print(f"  节点数: {len(tree_data.get('nodes', {}))}")
        print(f"  连接数: {len(tree_data.get('connections', []))}")


def _take_screenshot(output_path: str):
    """截取屏幕并保存"""
    from bt_utils.screenshot import ScreenshotManager
    try:
        sm = ScreenshotManager()
        img = sm.get_full_screenshot()
        img.save(output_path)
    except Exception as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"截图失败: {e}")


def _cmd_test(args):
    """阶段⑤ 试运行"""
    tree_path = args.tree_file
    if not os.path.exists(tree_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {tree_path}")

    from config.settings_manager import get_settings_manager
    sm = get_settings_manager()
    timeout_ms = getattr(args, "timeout", None) or sm.get("ai.iteration.test_timeout_ms", 30000)

    from bt_cli.ai.iteration_engine import IterationEngine

    engine = IterationEngine()
    print(f"正在试运行（超时 {timeout_ms}ms）...")

    report = engine.run_test(tree_path, timeout_ms=timeout_ms)

    # 保存报告
    ai_dir = _ensure_ai_dir()
    report_path = os.path.join(ai_dir, "test_report.json")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存报告失败: {e}")

    if report["success"]:
        print(f"\n试运行成功 ✓")
        print(f"报告已保存: {report_path}")
    else:
        print(f"\n试运行失败 ✗")
        print(f"报告已保存: {report_path}")
        print(f"\n执行日志（最后 10 行）:")
        for line in report["logs"][-10:]:
            print(f"  {line}")
        print(f"\n可运行迭代修正: autodoor-bt ai refine {tree_path}")


def _cmd_refine(args):
    """阶段⑤ 迭代修正"""
    _check_api_key()

    tree_path = args.tree_file
    if not os.path.exists(tree_path):
        exit_with_code(EXIT_CONFIG_ERROR, f"错误: 文件不存在: {tree_path}")

    from config.settings_manager import get_settings_manager
    sm = get_settings_manager()
    max_rounds = getattr(args, "max_rounds", None) or sm.get("ai.iteration.max_rounds", 3)

    # 获取任务上下文
    task_context = ""
    plan_path = os.path.join(os.path.dirname(tree_path), "plan.json")
    if os.path.exists(plan_path):
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                plan = json.load(f)
                task_context = plan.get("task_summary", "")
        except (json.JSONDecodeError, OSError):
            pass

    from bt_cli.ai.iteration_engine import IterationEngine

    engine = IterationEngine()
    try:
        result = engine.iterate(tree_path, max_rounds=max_rounds, task_context=task_context)
    except (json.JSONDecodeError, OSError) as e:
        exit_with_code(EXIT_CONFIG_ERROR, f"读取或解析行为树失败: {e}")

    if result["success"]:
        print(f"\n迭代成功！共 {result['rounds']} 轮")
    else:
        print(f"\n迭代未完全成功，共试运行 {result['rounds']} 轮")
        print(f"最终版本已保存: {tree_path}")
        print(f"建议手动检查或调整参数后重试")


def _cmd_create(args):
    """完整创建流程"""
    _check_api_key()

    from config.settings_manager import get_settings_manager
    sm = get_settings_manager()

    description = args.description
    print(f"=== AI 行为树创建流程 ===")
    print(f"任务描述: {description}\n")

    # 阶段① 意图分析
    print("--- 阶段 1/5: 意图分析 ---")
    from bt_cli.ai.intent_analyzer import IntentAnalyzer, IntentAnalysisError
    try:
        analyzer = IntentAnalyzer()
        plan = analyzer.analyze(description)
    except IntentAnalysisError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"意图分析失败: {e}")

    ai_dir = _ensure_ai_dir()
    plan_path = os.path.join(ai_dir, "plan.json")
    try:
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存计划文件失败: {e}")
    print(f"  任务概述: {plan.get('task_summary', 'N/A')}")
    print(f"  阶段数: {len(plan.get('phases', []))}")

    if not _confirm("是否继续节点选型？"):
        print(f"任务计划已保存: {plan_path}")
        print(f"后续可运行: autodoor-bt ai select {plan_path}")
        return

    # 阶段② 节点选型
    print("\n--- 阶段 2/5: 节点选型 ---")
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_selector import NodeSelector, NodeSelectionError
    register_all_nodes()
    try:
        selector = NodeSelector()
        structure = selector.select(plan)
    except NodeSelectionError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"节点选型失败: {e}")

    structure_path = os.path.join(ai_dir, "structure.json")
    try:
        with open(structure_path, "w", encoding="utf-8") as f:
            json.dump(structure, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存结构文件失败: {e}")
    print(f"  节点数: {len(structure['nodes'])}")

    if not _confirm("是否继续屏幕感知？"):
        print(f"节点结构已保存: {structure_path}")
        print(f"后续可运行: autodoor-bt ai scan {structure_path}")
        return

    # 阶段③ 屏幕感知
    print("\n--- 阶段 3/5: VLM 屏幕感知 ---")
    vlm_key = sm.get("ai.vlm.api_key", "")
    if not vlm_key:
        print("  跳过：未配置 VLM API Key")
        print("  节点结构保持原样（参数需手动补充）")
        filled = structure
    else:
        screenshot_path = os.path.join(ai_dir, "screenshot.png")
        print("  正在截取屏幕...")
        _take_screenshot(screenshot_path)

        from bt_cli.ai.vlm_analyzer import VLMAnalyzer, VLMAnalysisError
        try:
            vlm = VLMAnalyzer()
            suggestions = vlm.analyze(screenshot_path, structure, plan.get("task_summary", ""))
            filled = vlm.fill_structure(structure, suggestions)
            print(f"  填充建议数: {len(suggestions)}")
        except VLMAnalysisError as e:
            print(f"  VLM 分析失败: {e}")
            print("  节点结构保持原样")
            filled = structure

    filled_path = os.path.join(ai_dir, "structure_filled.json")
    try:
        with open(filled_path, "w", encoding="utf-8") as f:
            json.dump(filled, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存填充结构失败: {e}")

    if not _confirm("是否继续生成行为树？"):
        print(f"填充结构已保存: {filled_path}")
        print(f"后续可运行: autodoor-bt ai generate {filled_path}")
        return

    # 阶段④ 生成
    print("\n--- 阶段 4/5: 生成 JSON ---")
    from bt_cli.ai.tree_generator import TreeGenerator
    gen = TreeGenerator()
    tree_data, errors = gen.generate_and_validate(filled, canvas_name=plan.get("task_summary", "AI生成流程"))
    if errors:
        print(f"  校验发现问题:")
        for e in errors:
            print(f"    - {e}")
        exit_with_code(EXIT_GENERIC_ERROR, "生成失败")
    print("  校验通过 ✓")

    tree_path = os.path.join(ai_dir, "tree.json")
    try:
        with open(tree_path, "w", encoding="utf-8") as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        exit_with_code(EXIT_GENERIC_ERROR, f"保存行为树文件失败: {e}")
    print(f"  行为树已生成: {tree_path}")

    if not _confirm("是否继续试运行？"):
        print(f"\n可运行: autodoor-bt run {tree_path} --headless")
        return

    # 阶段⑤ 试运行
    print("\n--- 阶段 5/5: 试运行 ---")
    from bt_cli.ai.iteration_engine import IterationEngine
    engine = IterationEngine()
    timeout_ms = sm.get("ai.iteration.test_timeout_ms", 30000)
    report = engine.run_test(tree_path, timeout_ms=timeout_ms)

    if report["success"]:
        print("\n试运行成功 ✓")
        print(f"最终行为树: {tree_path}")
    else:
        print("\n试运行失败 ✗")
        report_path = os.path.join(ai_dir, "test_report.json")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except OSError:
            print(f"  警告: 保存报告失败")
        print(f"报告: {report_path}")
        if _confirm("是否进行 AI 迭代修正？"):
            max_rounds = sm.get("ai.iteration.max_rounds", 3)
            try:
                result = engine.iterate(tree_path, max_rounds=max_rounds,
                                        task_context=plan.get("task_summary", ""))
            except (json.JSONDecodeError, OSError) as e:
                exit_with_code(EXIT_CONFIG_ERROR, f"读取或解析行为树失败: {e}")
            if result["success"]:
                print(f"\n迭代成功！最终行为树: {tree_path}")
            else:
                print(f"\n迭代未完全成功，最终版本: {tree_path}")

    print(f"\n=== 完成 ===")
    print(f"行为树文件: {tree_path}")
    print(f"中间文件目录: {ai_dir}")


def _ensure_ai_dir() -> str:
    """确保 .ai/ 目录存在"""
    ai_dir = os.path.join(os.getcwd(), ".ai")
    os.makedirs(ai_dir, exist_ok=True)
    return ai_dir


def _confirm(message: str) -> bool:
    """交互式确认"""
    try:
        answer = input(f"{message} (y/n): ")
        return answer.lower() in ("y", "yes", "")
    except EOFError:
        return False


def _cmd_run(args):
    """一键非交互生成行为树（供外部 Agent / Hermes 调用）"""
    _check_api_key()

    from config.settings_manager import get_settings_manager
    sm = get_settings_manager()

    # 中间产物目录（默认 cwd/.ai，可用 --workdir 覆盖）
    workdir = os.path.abspath(args.workdir) if getattr(args, "workdir", None) else os.path.join(os.getcwd(), ".ai")
    os.makedirs(workdir, exist_ok=True)

    # 最终行为树输出路径
    tree_path = os.path.abspath(getattr(args, "output", None) or os.path.join(workdir, "tree.json"))
    os.makedirs(os.path.dirname(tree_path), exist_ok=True)

    plan_summary = ""
    stages_done = []
    screen_filled = 0
    skipped_screen = False

    def _die(phase: str, reason: str):
        if getattr(args, "json", False):
            print(json.dumps({
                "success": False,
                "stages": stages_done,
                "tree_file": None,
                "nodes": 0,
                "connections": 0,
                "screen_filled": 0,
                "skipped_screen": skipped_screen,
                "test": {"ran": False},
                "error": f"{phase}: {reason}",
            }, ensure_ascii=False))
        else:
            print(f"[{phase}] 失败: {reason}", file=sys.stderr)
        sys.exit(1)

    # 阶段① 意图分析
    from bt_cli.ai.intent_analyzer import IntentAnalyzer, IntentAnalysisError
    try:
        plan = IntentAnalyzer().analyze(args.description)
    except IntentAnalysisError as e:
        _die("plan", str(e))
    stages_done.append("plan")
    plan_summary = plan.get("task_summary", "")

    plan_path = os.path.join(workdir, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    # 阶段② 节点选型
    from bt_core.registry import register_all_nodes
    from bt_cli.ai.node_selector import NodeSelector, NodeSelectionError
    register_all_nodes()
    try:
        structure = NodeSelector().select(plan)
    except NodeSelectionError as e:
        _die("select", str(e))
    stages_done.append("select")

    structure_path = os.path.join(workdir, "structure.json")
    with open(structure_path, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    # 判断是否需要屏幕感知（存在空参数才需要）
    def _has_empty_params(st):
        return any(node.get("empty_params") for node in st.get("nodes", []))

    filled = structure
    need_screen = not getattr(args, "no_screen", False) and _has_empty_params(structure)

    # 阶段③ VLM 屏幕感知（可跳过、可容错）
    if need_screen:
        shot = None
        if getattr(args, "screenshot", None):
            shot = args.screenshot
            if not os.path.exists(shot):
                _die("screen", f"指定截图不存在: {shot}")
        else:
            vlm_key = sm.get("ai.vlm.api_key", "")
            if vlm_key:
                shot = os.path.join(workdir, "screenshot.png")
                # 截图失败不阻断，静默跳过屏幕感知
                try:
                    from bt_utils.screenshot import ScreenshotManager
                    sm_shot = ScreenshotManager()
                    img = sm_shot.get_full_screenshot()
                    img.save(shot)
                except Exception as e:
                    print(f"[screen] 截图失败，跳过屏幕感知: {e}", file=sys.stderr)
                    shot = None
        if shot is not None:
            from bt_cli.ai.vlm_analyzer import VLMAnalyzer, VLMAnalysisError
            try:
                vlm = VLMAnalyzer()
                suggestions = vlm.analyze(shot, structure, plan_summary)
                filled = vlm.fill_structure(structure, suggestions)
                screen_filled = len(suggestions)
                stages_done.append("screen")
            except VLMAnalysisError as e:
                print(f"[screen] VLM 分析失败，保留原结构: {e}", file=sys.stderr)
                skipped_screen = True
        else:
            skipped_screen = True
    else:
        skipped_screen = True

    filled_path = os.path.join(workdir, "structure_filled.json")
    with open(filled_path, "w", encoding="utf-8") as f:
        json.dump(filled, f, ensure_ascii=False, indent=2)

    # 阶段④ 生成 JSON
    from bt_cli.ai.tree_generator import TreeGenerator
    canvas_name = getattr(args, "canvas", None) or plan_summary or "AI生成流程"
    gen = TreeGenerator()
    tree_data, errors = gen.generate_and_validate(filled, canvas_name=canvas_name)
    if errors:
        _die("generate", "; ".join(errors))
    stages_done.append("generate")

    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree_data, f, ensure_ascii=False, indent=2)

    nodes = len(tree_data.get("nodes", {}))
    connections = len(tree_data.get("connections", []))

    # 阶段⑤ 试运行（默认关闭）
    test = {"ran": False}
    if getattr(args, "test", False):
        timeout_ms = getattr(args, "timeout", None) or sm.get("ai.iteration.test_timeout_ms", 30000)
        from bt_cli.ai.iteration_engine import IterationEngine
        engine = IterationEngine()
        try:
            report = engine.run_test(tree_path, timeout_ms=timeout_ms)
        except Exception as e:
            _die("test", f"试运行异常: {e}")
        test = {"ran": True, "success": report.get("success", False)}
        if not report.get("success", False) and not getattr(args, "no_refine", False):
            max_rounds = getattr(args, "max_rounds", None) or sm.get("ai.iteration.max_rounds", 3)
            try:
                result = engine.iterate(tree_path, max_rounds=max_rounds, task_context=plan_summary)
                test["refine_rounds"] = result.get("rounds", 0)
                test["success"] = result.get("success", False)
            except Exception as e:
                test["refine_error"] = str(e)
        report_path = os.path.join(workdir, "test_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        test["report"] = report_path
        if not test.get("success", False):
            # 试运行失败仍返回 tree_file（已生成），但标记 success=false 供上层决策
            if getattr(args, "json", False):
                print(json.dumps({
                    "success": False,
                    "stages": stages_done,
                    "tree_file": tree_path,
                    "nodes": nodes,
                    "connections": connections,
                    "screen_filled": screen_filled,
                    "skipped_screen": skipped_screen,
                    "test": test,
                    "error": "test: 试运行未通过（可手动检查后重试或 --no-refine 关闭）",
                }, ensure_ascii=False))
            else:
                print(f"[test] 试运行未通过，树文件仍已生成: {tree_path}")
            sys.exit(1)

    # 输出结果
    result = {
        "success": True,
        "stages": stages_done,
        "tree_file": tree_path,
        "nodes": nodes,
        "connections": connections,
        "screen_filled": screen_filled,
        "skipped_screen": skipped_screen,
        "test": test,
        "error": None,
    }
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"行为树已生成: {tree_path}")
        print(f"  节点数: {nodes}")
        print(f"  连接数: {connections}")
        if stages_done[-1:] == ["screen"] or "screen" in stages_done:
            print(f"  屏幕感知: 填充 {screen_filled} 项" if screen_filled else "  屏幕感知: 已跳过")
        print(f"\n可运行: autodoor-bt run {tree_path} --headless")
