"""GUI 常量动态合并工具 — 将插件节点信息合并到 GUI 常量中"""


def merge_plugin_nodes(node_category_map, node_display_names,
                       node_descriptions, plugin_display_info):
    """将插件节点信息合并到 GUI 常量中

    Args:
        node_category_map: Dict[str, str] — 节点类型→分类
        node_display_names: Dict[str, str] — 节点类型→显示名
        node_descriptions: Dict[str, str] — 节点类型→描述
        plugin_display_info: Dict[str, dict] — 插件返回的节点显示信息
            {"CustomNode": {"display_name": "自定义", "description": "desc", "category": "plugin"}}
    """
    for node_type, info in plugin_display_info.items():
        category = info.get("category", "plugin")
        node_category_map[node_type] = category
        node_display_names[node_type] = info.get("display_name", node_type)
        node_descriptions[node_type] = info.get("description", "")


def merge_plugin_schemas(existing_schemas, plugin_schemas):
    """将插件节点 schema 合并到属性面板配置中

    Args:
        existing_schemas: Dict[str, list] — 现有 schema 字典
        plugin_schemas: Dict[str, list] — 插件提供的 schema
    """
    for node_type, schema in plugin_schemas.items():
        existing_schemas[node_type] = schema


def merge_plugin_palette(categories_dict, plugin_nodes, color="#6B7280", icon="★"):
    """将插件节点添加到节点面板的分类中

    Args:
        categories_dict: dict — build_node_categories() 返回的分类字典
        plugin_nodes: list of tuples — [(node_type, display_name, description), ...]
        color: str — 插件分类的颜色
        icon: str — 插件分类的图标
    """
    if "插件节点" not in categories_dict:
        categories_dict["插件节点"] = {
            "icon": icon,
            "color": color,
            "nodes": []
        }
    categories_dict["插件节点"]["nodes"].extend(plugin_nodes)
