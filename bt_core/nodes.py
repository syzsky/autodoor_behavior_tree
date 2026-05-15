from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import uuid
import time

from .status import NodeStatus
from .config import NodeConfig
from bt_utils.helpers import get_random_interval

if TYPE_CHECKING:
    from .context import ExecutionContext


class Node(ABC):
    """节点抽象基类

    所有行为树节点的基类，定义了节点的通用接口和行为。

    Args:
        node_id: 节点唯一标识
        config: 节点配置
    """
    NODE_TYPE = "Node"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        self.node_id = node_id or str(uuid.uuid4())[:8]
        self.config = config or NodeConfig()
        self.name = self.config.name
        self.description = self.config.description
        self.enabled = self.config.enabled
        self.status = NodeStatus.SUCCESS
        self.children: List["Node"] = []
        self.parent: Optional["Node"] = None
        self._tick_count = 0
        self._is_protected = False  # 节点保护标记,防止被删除
        self._retry_count = 0
        self._repeat_count = 0
        self._start_time: Optional[float] = None
        self._child_index = 0
        self._children_running = False

    @abstractmethod
    def tick(self, context: "ExecutionContext") -> NodeStatus:
        """执行节点逻辑

        Args:
            context: 执行上下文

        Returns:
            节点执行状态
        """
        pass

    def _execute_with_decorators(self, context: "ExecutionContext", 
                                   execute_func: callable) -> NodeStatus:
        if not self.config.enabled:
            return NodeStatus.SUCCESS

        if self.status != NodeStatus.RUNNING:
            context.notify_node_status(self.node_id, "running")

        if self._start_time is None:
            self._start_time = context.elapsed_time

        timeout_ms = self.config.timeout_ms
        if timeout_ms > 0:
            elapsed_ms = (context.elapsed_time - self._start_time) * 1000
            if elapsed_ms >= timeout_ms:
                self.status = NodeStatus.FAILURE
                context.notify_node_status(self.node_id, "failure")
                context.record_node_stats(self.node_id, self.NODE_TYPE, self.name, "failure", timeout_ms)
                return NodeStatus.FAILURE

        start_time = time.perf_counter()
        status = execute_func(context)
        duration_ms = (time.perf_counter() - start_time) * 1000
        self.status = status

        from bt_utils.log_manager import LogManager
        LogManager.debug_print(
            f"[DEBUG] _execute_with_decorators: {self.NODE_TYPE} '{self.name}' "
            f"(id={self.node_id}) execute_func returned {status.name}, "
            f"retry_count={self.config.retry_count}, _retry_count={self._retry_count}, "
            f"repeat_count={self.config.repeat_count}, _repeat_count={self._repeat_count}"
        )

        retry_count = self.config.retry_count
        if status == NodeStatus.FAILURE and retry_count != 0:
            if retry_count == -1 or self._retry_count < retry_count:
                self._retry_count += 1
                
                LogManager.debug_print(
                    f"[DEBUG] _execute_with_decorators: {self.NODE_TYPE} '{self.name}' "
                    f"RETRY #{self._retry_count}, retry_count config={retry_count}"
                )

                repeat_interval_ms = self.config.repeat_interval_ms
                repeat_interval_ms_random = self.config.get_int("repeat_interval_ms_random", 0)
                if repeat_interval_ms > 0 or repeat_interval_ms_random > 0:    
                    actual_interval = get_random_interval(repeat_interval_ms, repeat_interval_ms_random)
                    if actual_interval > 0:
                        elapsed = 0
                        while elapsed < actual_interval / 1000 and context.check_running():
                            sleep_time = min(0.01, actual_interval / 1000 - elapsed)
                            time.sleep(sleep_time)
                            elapsed += sleep_time

                if not context.check_running():
                    return NodeStatus.ABORTED

                self._reset_for_retry()

                LogManager.debug_print(
                    f"[DEBUG] _execute_with_decorators: {self.NODE_TYPE} '{self.name}' "
                    f"after _reset_for_retry: status={self.status.name}, "
                    f"current_index={getattr(self, 'current_index', 'N/A')}"
                )

                return NodeStatus.RUNNING

        repeat_count = self.config.repeat_count
        if status == NodeStatus.SUCCESS and repeat_count != 0:
            if repeat_count == -1 or self._repeat_count < repeat_count:
                self._repeat_count += 1
                
                repeat_interval_ms = self.config.repeat_interval_ms
                repeat_interval_ms_random = self.config.get_int("repeat_interval_ms_random", 0)
                if repeat_interval_ms > 0 or repeat_interval_ms_random > 0:    
                    actual_interval = get_random_interval(repeat_interval_ms, repeat_interval_ms_random)
                    if actual_interval > 0:
                        elapsed = 0
                        while elapsed < actual_interval / 1000 and context.check_running():
                            sleep_time = min(0.01, actual_interval / 1000 - elapsed)
                            time.sleep(sleep_time)
                            elapsed += sleep_time

                if not context.check_running():
                    return NodeStatus.ABORTED

                self._reset_for_repeat()
                return NodeStatus.RUNNING

        status_str = "success" if status == NodeStatus.SUCCESS else "failure" if status == NodeStatus.FAILURE else "running"
        context.record_node_stats(self.node_id, self.NODE_TYPE, self.name, status_str, duration_ms)

        if status == NodeStatus.SUCCESS:
            context.notify_node_status(self.node_id, "success")
        elif status == NodeStatus.FAILURE:
            context.notify_node_status(self.node_id, "failure")

        return status

    def _reset_for_retry(self) -> None:
        from bt_utils.log_manager import LogManager
        LogManager.debug_print(
            f"[DEBUG] _reset_for_retry: {self.NODE_TYPE} '{self.name}' (id={self.node_id}) "
            f"BEFORE: status={self.status.name}, current_index={getattr(self, 'current_index', 'N/A')}, "
            f"_child_index={self._child_index}, _children_running={self._children_running}"
        )
        self.status = NodeStatus.RUNNING
        self._tick_count = 0
        self._start_time = None
        self._child_index = 0
        self._children_running = False
        if hasattr(self, 'current_index'):
            self.current_index = 0
        if hasattr(self, '_last_child_finish_time'):
            self._last_child_finish_time = None
        for child in self.children:
            LogManager.debug_print(
                f"[DEBUG] _reset_for_retry: resetting child {child.NODE_TYPE} '{child.name}' "
                f"(id={child.node_id}), child.status BEFORE reset={child.status.name}"
            )
            child.reset()
            LogManager.debug_print(
                f"[DEBUG] _reset_for_retry: child {child.NODE_TYPE} '{child.name}' "
                f"(id={child.node_id}), child.status AFTER reset={child.status.name}"
            )
        LogManager.debug_print(
            f"[DEBUG] _reset_for_retry: {self.NODE_TYPE} '{self.name}' (id={self.node_id}) "
            f"AFTER: status={self.status.name}, current_index={getattr(self, 'current_index', 'N/A')}, "
            f"_child_index={self._child_index}, _children_running={self._children_running}"
        )

    def _reset_for_repeat(self) -> None:
        """重复执行时重置状态（保留重复计数器）"""
        saved_repeat_count = self._repeat_count
        self.reset(reset_counters=False)
        self._repeat_count = saved_repeat_count
        self.status = NodeStatus.RUNNING

    def reset(self, reset_counters: bool = True) -> None:
        """重置节点状态

        Args:
            reset_counters: 是否重置计数器（重复执行时不应重置）
        """
        self.status = NodeStatus.SUCCESS
        self._tick_count = 0
        if reset_counters:
            self._retry_count = 0
            self._repeat_count = 0
        self._start_time = None
        self._child_index = 0
        self._children_running = False
        for child in self.children:
            child.reset()

    def _execute_children(self, context: "ExecutionContext") -> NodeStatus:
        """执行子节点（通用实现）

        Args:
            context: 执行上下文

        Returns:
            执行状态
        """
        while self._child_index < len(self.children):
            child = self.children[self._child_index]
            status = child.tick(context)
            
            if status == NodeStatus.RUNNING:
                self._children_running = True
                return NodeStatus.RUNNING
            
            if status != NodeStatus.SUCCESS:
                self._child_index = 0
                self._children_running = False
                return status
            
            self._child_index += 1
        
        self._child_index = 0
        self._children_running = False
        return NodeStatus.SUCCESS

    def is_protected(self) -> bool:
        """
        检查节点是否受保护(不可删除)
        
        Returns:
            bool: True表示受保护,False表示可删除
        """
        return self._is_protected

    def abort(self, context: "ExecutionContext") -> None:
        """中止节点执行

        当节点被外部中止时调用（如并行节点完成时中止其他RUNNING子节点）。

        Args:
            context: 执行上下文
        """
        self.reset()
        self.status = NodeStatus.ABORTED
        context.notify_node_status(self.node_id, "aborted")
        for child in self.children:
            child.abort(context)

    def add_child(self, child: "Node") -> None:
        """添加子节点

        Args:
            child: 子节点
        """
        child.parent = self
        self.children.append(child)

    def remove_child(self, child: "Node") -> None:
        """移除子节点

        Args:
            child: 子节点
        """
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典

        Returns:
            字典表示
        """
        return {
            "id": self.node_id,
            "type": self.NODE_TYPE,
            "name": self.name,
            "enabled": self.enabled,
            "config": self.config.to_dict(),
            "children": [child.node_id for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        """从字典反序列化

        Args:
            data: 字典数据

        Returns:
            节点实例
        """
        config = NodeConfig.from_dict(data.get("config", {}))
        
        if "name" in data:
            config.name = data["name"]
        if "description" in data:
            config.description = data["description"]
        if "enabled" in data:
            config.enabled = data["enabled"]
        
        node = cls(node_id=data.get("id"), config=config)
        return node


class CompositeNode(Node):
    """组合节点基类

    包含多个子节点的节点，按特定策略执行子节点。
    """
    NODE_TYPE = "CompositeNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.current_index = 0

    def reset(self, reset_counters: bool = True) -> None:
        """重置节点状态"""
        super().reset(reset_counters)
        self.current_index = 0

    def abort(self, context: "ExecutionContext") -> None:
        """中止节点执行，递归中止所有子节点

        Args:
            context: 执行上下文
        """
        for child in self.children:
            child.abort(context)
        super().abort(context)


class SequenceNode(CompositeNode):
    NODE_TYPE = "SequenceNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.continue_on_failure = self.config.get_bool("continue_on_failure", False)
        self.child_interval = self.config.get_int("childinterval", 0)
        self.child_interval_random = self.config.get_int("childinterval_random", 0)
        self._last_child_finish_time: Optional[float] = None

    def tick(self, context: "ExecutionContext") -> NodeStatus:
        return self._execute_with_decorators(context, self._tick_internal)

    def _tick_internal(self, context: "ExecutionContext") -> NodeStatus:
        from bt_utils.log_manager import LogManager

        if not self.children:
            return NodeStatus.SUCCESS

        LogManager.debug_print(
            f"[DEBUG] SequenceNode._tick_internal: '{self.name}' (id={self.node_id}) "
            f"ENTER: current_index={self.current_index}, "
            f"continue_on_failure={self.continue_on_failure}, "
            f"children_count={len(self.children)}"
        )

        has_failure = False

        while self.current_index < len(self.children):
            child = self.children[self.current_index]

            if not child.config.enabled:
                self.current_index += 1
                continue

            if self.child_interval > 0 and self._last_child_finish_time is not None:
                current_time = context.elapsed_time * 1000
                actual_interval = get_random_interval(self.child_interval, self.child_interval_random)
                if current_time - self._last_child_finish_time < actual_interval:
                    return NodeStatus.RUNNING

            LogManager.debug_print(
                f"[DEBUG] SequenceNode._tick_internal: '{self.name}' "
                f"ticking child[{self.current_index}]={child.NODE_TYPE} '{child.name}' "
                f"(id={child.node_id}), child.status={child.status.name}"
            )

            status = child.tick(context)

            LogManager.debug_print(
                f"[DEBUG] SequenceNode._tick_internal: '{self.name}' "
                f"child[{self.current_index}]={child.NODE_TYPE} '{child.name}' "
                f"returned {status.name}"
            )

            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING

            if status == NodeStatus.FAILURE:
                if self.continue_on_failure:
                    has_failure = True
                    self.current_index += 1
                    self._last_child_finish_time = context.elapsed_time * 1000
                    continue
                else:
                    LogManager.debug_print(
                        f"[DEBUG] SequenceNode._tick_internal: '{self.name}' "
                        f"FAILURE branch: setting current_index=0 (was {self.current_index})"
                    )
                    self.current_index = 0
                    LogManager.instance().log_failure(
                        node_type="顺序节点",
                        node_name=self.name,
                        reason=f"子节点 '{child.name}' 执行失败"
                    )
                    return NodeStatus.FAILURE

            self.current_index += 1
            self._last_child_finish_time = context.elapsed_time * 1000

        self.current_index = 0
        
        if has_failure:
            LogManager.instance().log_failure(
                node_type="顺序节点",
                node_name=self.name,
                reason="部分子节点执行失败（继续执行模式）"
            )
        else:
            LogManager.instance().log_success(
                node_type="顺序节点",
                node_name=self.name
            )
        
        return NodeStatus.FAILURE if has_failure else NodeStatus.SUCCESS

    def reset(self, reset_counters: bool = True) -> None:
        super().reset(reset_counters)
        self._last_child_finish_time = None

    def _reset_for_retry(self) -> None:
        super()._reset_for_retry()
        self._last_child_finish_time = None


class SelectorNode(CompositeNode):
    NODE_TYPE = "SelectorNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.child_interval = self.config.get_int("childinterval", 0)
        self.child_interval_random = self.config.get_int("childinterval_random", 0)
        self._last_child_time = 0

    def tick(self, context: "ExecutionContext") -> NodeStatus:
        return self._execute_with_decorators(context, self._tick_internal)

    def _tick_internal(self, context: "ExecutionContext") -> NodeStatus:
        from bt_utils.log_manager import LogManager
        
        if not self.children:
            LogManager.instance().log_failure(
                node_type="选择节点",
                node_name=self.name,
                reason="没有子节点"
            )
            return NodeStatus.FAILURE

        while self.current_index < len(self.children):
            child = self.children[self.current_index]

            if not child.config.enabled:
                self.current_index += 1
                continue

            if self.child_interval > 0:
                current_time = context.elapsed_time * 1000
                actual_interval = get_random_interval(self.child_interval, self.child_interval_random)
                if current_time - self._last_child_time < actual_interval:
                    return NodeStatus.RUNNING
                self._last_child_time = current_time

            status = child.tick(context)

            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING

            if status == NodeStatus.SUCCESS:
                self.current_index = 0
                LogManager.instance().log_success(
                    node_type="选择节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS

            self.current_index += 1

        self.current_index = 0
        LogManager.instance().log_failure(
            node_type="选择节点",
            node_name=self.name,
            reason="所有子节点都执行失败"
        )
        return NodeStatus.FAILURE

    def reset(self, reset_counters: bool = True) -> None:
        super().reset(reset_counters)
        self._last_child_time = 0

    def _reset_for_retry(self) -> None:
        super()._reset_for_retry()
        self._last_child_time = 0


class ParallelNode(CompositeNode):
    """并行节点

    同时执行所有子节点，根据策略决定成功条件。

    Args:
        success_policy: 成功策略，require_all（全部成功）或 require_one（任一成功）
    """
    NODE_TYPE = "ParallelNode"

    SUCCESS_POLICY_ALL = "require_all"
    SUCCESS_POLICY_ONE = "require_one"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.cached_statuses: Dict[int, NodeStatus] = {}
        self.success_policy = self.config.get("success_policy", self.SUCCESS_POLICY_ALL)

    def tick(self, context: "ExecutionContext") -> NodeStatus:
        return self._execute_with_decorators(context, self._tick_internal)

    def _tick_internal(self, context: "ExecutionContext") -> NodeStatus:
        from bt_utils.log_manager import LogManager
        
        if not self.children:
            LogManager.instance().log_success(
                node_type="并行节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS

        success_count = 0
        failure_count = 0
        running_children = []
        enabled_count = 0

        for i, child in enumerate(self.children):
            if not child.config.enabled:
                continue

            enabled_count += 1

            if i in self.cached_statuses:
                status = self.cached_statuses[i]
                if status == NodeStatus.SUCCESS:
                    success_count += 1
                    continue
                elif status == NodeStatus.FAILURE:
                    failure_count += 1
                    continue

            status = child.tick(context)

            if status == NodeStatus.SUCCESS:
                self.cached_statuses[i] = NodeStatus.SUCCESS
                success_count += 1
            elif status == NodeStatus.FAILURE:
                self.cached_statuses[i] = NodeStatus.FAILURE
                failure_count += 1
            elif status == NodeStatus.RUNNING:
                running_children.append(child)

        if self.success_policy == self.SUCCESS_POLICY_ONE and success_count > 0:
            self._abort_running(context, running_children)
            LogManager.instance().log_success(
                node_type="并行节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS

        if running_children:
            return NodeStatus.RUNNING

        if self.success_policy == self.SUCCESS_POLICY_ALL:
            if success_count == enabled_count:
                LogManager.instance().log_success(
                    node_type="并行节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure(
                    node_type="并行节点",
                    node_name=self.name,
                    reason=f"成功 {success_count}/{enabled_count} 个子节点"
                )
                return NodeStatus.FAILURE
        else:
            if success_count > 0:
                LogManager.instance().log_success(
                    node_type="并行节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure(
                    node_type="并行节点",
                    node_name=self.name,
                    reason="所有子节点都执行失败"
                )
                return NodeStatus.FAILURE

    def _abort_running(self, context: "ExecutionContext", children: List[Node]) -> None:
        """中止正在运行的子节点

        Args:
            context: 执行上下文
            children: 正在运行的子节点列表
        """
        for child in children:
            child.abort(context)

    def reset(self, reset_counters: bool = True) -> None:
        """重置节点状态"""
        super().reset(reset_counters)
        self.cached_statuses.clear()
    
    def _reset_for_retry(self) -> None:
        """重试时重置状态（保留重试计数器）"""
        super()._reset_for_retry()
        self.cached_statuses.clear()
    
    def _reset_for_repeat(self) -> None:
        """重复执行时重置状态（保留重复计数器）"""
        super()._reset_for_repeat()
        self.cached_statuses.clear()


class RandomNode(CompositeNode):
    """随机节点

    随机执行子节点，根据策略决定成功条件。

    Args:
        success_policy: 成功策略，require_all（全部成功）或 require_one（任一成功）
        continue_on_failure: 失败后是否继续执行
        fully_random: 是否完全随机（True时已执行的子节点仍可被选中）
    """
    NODE_TYPE = "RandomNode"

    SUCCESS_POLICY_ALL = "require_all"
    SUCCESS_POLICY_ONE = "require_one"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.success_policy = self.config.get("success_policy", self.SUCCESS_POLICY_ALL)
        self.continue_on_failure = self.config.get_bool("continue_on_failure", False)
        self.fully_random = self.config.get_bool("fully_random", False)
        self._executed_indices: set = set()
        self._success_indices: set = set()
        self._failure_indices: set = set()
        self._current_running_index: Optional[int] = None
        self._enabled_indices: List[int] = []

    def tick(self, context: "ExecutionContext") -> NodeStatus:
        return self._execute_with_decorators(context, self._tick_internal)

    def _tick_internal(self, context: "ExecutionContext") -> NodeStatus:
        from bt_utils.log_manager import LogManager
        import random
        
        if not self.children:
            LogManager.instance().log_success(
                node_type="随机节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS

        if not self._enabled_indices:
            self._enabled_indices = [
                i for i, child in enumerate(self.children) 
                if child.config.enabled
            ]
        
        if not self._enabled_indices:
            LogManager.instance().log_success(
                node_type="随机节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS

        if self._current_running_index is not None:
            child = self.children[self._current_running_index]
            status = child.tick(context)
            
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            
            if status == NodeStatus.SUCCESS:
                self._success_indices.add(self._current_running_index)
                if self.success_policy == self.SUCCESS_POLICY_ONE:
                    LogManager.instance().log_success(
                        node_type="随机节点",
                        node_name=self.name
                    )
                    return NodeStatus.SUCCESS
            elif status == NodeStatus.FAILURE:
                self._failure_indices.add(self._current_running_index)
                if not self.continue_on_failure and self.success_policy == self.SUCCESS_POLICY_ALL:
                    LogManager.instance().log_failure(
                        node_type="随机节点",
                        node_name=self.name,
                        reason=f"子节点 '{child.name}' 执行失败"
                    )
                    return NodeStatus.FAILURE
            
            self._current_running_index = None

        available_indices = self._get_available_indices()
        
        if not available_indices:
            return self._determine_final_status()
        
        if self.fully_random and self._executed_indices == set(self._enabled_indices):
            return self._determine_final_status()

        next_index = random.choice(available_indices)
        
        self._executed_indices.add(next_index)
        
        self._current_running_index = next_index
        child = self.children[next_index]
        status = child.tick(context)
        
        if status == NodeStatus.RUNNING:
            return NodeStatus.RUNNING
        
        if status == NodeStatus.SUCCESS:
            self._success_indices.add(next_index)
            if self.success_policy == self.SUCCESS_POLICY_ONE:
                LogManager.instance().log_success(
                    node_type="随机节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
        elif status == NodeStatus.FAILURE:
            self._failure_indices.add(next_index)
            if not self.continue_on_failure and self.success_policy == self.SUCCESS_POLICY_ALL:
                LogManager.instance().log_failure(
                    node_type="随机节点",
                    node_name=self.name,
                    reason=f"子节点 '{child.name}' 执行失败"
                )
                return NodeStatus.FAILURE
        
        self._current_running_index = None
        
        available_indices = self._get_available_indices()
        if not available_indices:
            return self._determine_final_status()
        
        return NodeStatus.RUNNING

    def _get_available_indices(self) -> List[int]:
        """获取可执行的子节点索引列表
        
        Returns:
            可执行的子节点索引列表
        """
        if self.fully_random:
            return self._enabled_indices
        else:
            return [i for i in self._enabled_indices if i not in self._executed_indices]

    def _determine_final_status(self) -> NodeStatus:
        """确定最终状态
        
        Returns:
            最终节点状态
        """
        from bt_utils.log_manager import LogManager
        
        enabled_count = len(self._enabled_indices)
        success_count = len(self._success_indices)
        
        if self.success_policy == self.SUCCESS_POLICY_ALL:
            if success_count == enabled_count:
                LogManager.instance().log_success(
                    node_type="随机节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure(
                    node_type="随机节点",
                    node_name=self.name,
                    reason=f"成功 {success_count}/{enabled_count} 个子节点"
                )
                return NodeStatus.FAILURE
        else:
            if success_count > 0:
                LogManager.instance().log_success(
                    node_type="随机节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure(
                    node_type="随机节点",
                    node_name=self.name,
                    reason="所有子节点都执行失败"
                )
                return NodeStatus.FAILURE

    def reset(self, reset_counters: bool = True) -> None:
        """重置节点状态"""
        super().reset(reset_counters)
        self._executed_indices.clear()
        self._success_indices.clear()
        self._failure_indices.clear()
        self._current_running_index = None
        self._enabled_indices = []
    
    def _reset_for_retry(self) -> None:
        """重试时重置状态（保留重试计数器）"""
        super()._reset_for_retry()
        self._executed_indices.clear()
        self._success_indices.clear()
        self._failure_indices.clear()
        self._current_running_index = None
        self._enabled_indices = []
    
    def _reset_for_repeat(self) -> None:
        """重复执行时重置状态（保留重复计数器）"""
        super()._reset_for_repeat()
        self._executed_indices.clear()
        self._success_indices.clear()
        self._failure_indices.clear()
        self._current_running_index = None
        self._enabled_indices = []


class ConditionNode(Node):
    NODE_TYPE = "ConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.invert = self.config.get_bool("invert", False)
        self.check_interval_ms = self.config.get_int("check_interval_ms", 300)
        self.save_position = self.config.get_bool("save_position", True)
        
        try:
            from config.settings_manager import get_default_position_key
            default_position_key = get_default_position_key()
        except ImportError:
            default_position_key = "last_detection_position"
        
        self.position_key = self.config.get("position_key", default_position_key)
        
        # 坐标偏移参数 (向后兼容：支持旧的 offset_x/offset_y 格式)
        offset = self.config.get("offset", None)
        if offset is not None:
            if isinstance(offset, (list, tuple)) and len(offset) >= 2:
                self.offset = (int(offset[0]), int(offset[1]))
            else:
                self.offset = (0, 0)
        else:
            # 向后兼容：从旧的 offset_x/offset_y 读取
            offset_x = self.config.get_int("offset_x", 0)
            offset_y = self.config.get_int("offset_y", 0)
            self.offset = (offset_x, offset_y)
        
        self._last_check_time = -self.check_interval_ms - 1

    def _parse_region(self, region_config) -> tuple:
        """解析区域配置
        
        Args:
            region_config: 区域配置，支持 None、list、tuple、str 格式
            
        Returns:
            tuple: (x1, y1, x2, y2) 区域坐标
        """
        if region_config is None:
            return None
        elif isinstance(region_config, (list, tuple)):
            if len(region_config) == 4:
                return tuple(int(x) for x in region_config)
            return tuple(region_config)
        elif isinstance(region_config, str):
            try:
                import re
                if region_config.startswith('['):
                    match = re.findall(r'\d+', region_config)
                    if len(match) >= 4:
                        return tuple(int(x) for x in match[:4])
                parts = [int(x.strip()) for x in region_config.split(",")]
                if len(parts) == 4:
                    return tuple(parts)
            except (ValueError, AttributeError):
                pass
        return None

    def _parse_color(self, color_config) -> tuple:
        """解析颜色配置
        
        Args:
            color_config: 颜色配置，支持 None、list、tuple、str 格式
            
        Returns:
            tuple: (r, g, b) 颜色值
        """
        if color_config is None:
            return (255, 0, 0)
        elif isinstance(color_config, (list, tuple)):
            return tuple(int(c) for c in color_config[:3])
        elif isinstance(color_config, str):
            import re
            match = re.search(r'RGB\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color_config, re.IGNORECASE)
            if match:
                return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            try:
                parts = [int(x.strip()) for x in color_config.split(",")]
                if len(parts) >= 3:
                    return tuple(parts[:3])
            except (ValueError, AttributeError):
                pass
        return (255, 0, 0)

    def _apply_offset(self, position: tuple) -> tuple:
        """应用坐标偏移
        
        Args:
            position: 原始位置 (x, y)
            
        Returns:
            tuple: 偏移后的位置
        """
        if position is None:
            return None
        
        return (position[0] + self.offset[0], position[1] + self.offset[1])
    
    def _save_position(self, context, position: tuple):
        """保存位置到黑板（应用偏移）
        
        坐标转换由 ExecutionContext 的 execute_mouse_* 方法自动处理。
        
        Args:
            context: 执行上下文
            position: 原始位置（窗口相对坐标或屏幕绝对坐标）
        """
        if position and self.save_position:
            final_position = self._apply_offset(position)
            context.blackboard.set(self.position_key, final_position)

    def tick(self, context: "ExecutionContext") -> NodeStatus:
        return self._execute_with_decorators(context, self._tick_internal)

    def _tick_internal(self, context: "ExecutionContext") -> NodeStatus:
        from bt_utils.log_manager import LogManager

        if self._children_running and self.children:
            LogManager.debug_print(
                f"[DEBUG] ConditionNode._tick_internal: {self.NODE_TYPE} '{self.name}' "
                f"(id={self.node_id}) _children_running=True, executing children"
            )
            return self._execute_children(context)
        
        current_time = context.elapsed_time * 1000
        time_since_last = current_time - self._last_check_time
        if time_since_last < self.check_interval_ms:
            LogManager.debug_print(
                f"[DEBUG] ConditionNode._tick_internal: {self.NODE_TYPE} '{self.name}' "
                f"(id={self.node_id}) CHECK_INTERVAL_CACHE HIT: "
                f"time_since_last={time_since_last:.1f}ms < check_interval={self.check_interval_ms}ms, "
                f"returning cached status={self.status.name}"
            )
            return self.status

        LogManager.debug_print(
            f"[DEBUG] ConditionNode._tick_internal: {self.NODE_TYPE} '{self.name}' "
            f"(id={self.node_id}) CHECK_INTERVAL_CACHE MISS: "
            f"time_since_last={time_since_last:.1f}ms >= check_interval={self.check_interval_ms}ms, "
            f"current_status={self.status.name}, _last_check_time={self._last_check_time}, "
            f"current_time={current_time:.1f}"
        )

        self._last_check_time = current_time
        result = self._check_condition(context)

        if self.invert:
            result = not result

        status = NodeStatus.SUCCESS if result else NodeStatus.FAILURE
        self.status = status

        LogManager.debug_print(
            f"[DEBUG] ConditionNode._tick_internal: {self.NODE_TYPE} '{self.name}' "
            f"(id={self.node_id}) condition_result={result}, final_status={status.name}"
        )

        if status == NodeStatus.SUCCESS and self.children:
            context.notify_node_status(self.node_id, "success")
            self._children_running = True
            return self._execute_children(context)

        return status

    @abstractmethod
    def _check_condition(self, context: "ExecutionContext") -> bool:
        """检测条件是否满足

        Args:
            context: 执行上下文

        Returns:
            条件是否满足
        """
        pass

    def _validate_region(self, region) -> bool:
        """验证区域配置是否有效

        Args:
            region: 区域配置

        Returns:
            区域是否有效
        """
        if region is None:
            return True
        if isinstance(region, (list, tuple)) and len(region) == 4:
            return all(isinstance(x, int) for x in region)
        return False

    def _get_region_image(self, context):
        """获取区域图像（截图+裁剪）

        Args:
            context: 执行上下文

        Returns:
            PIL.Image 或 None
        """
        try:
            return context.get_screenshot(self.region)
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"{self.NODE_TYPE} '{self.name}' 截图失败")
            return None

    def _log_condition_result(self, success: bool, reason: str = None,
                               extra_info: str = None):
        """记录条件检测结果日志

        Args:
            success: 是否成功
            reason: 失败原因（成功时为None）
            extra_info: 额外信息
        """
        from bt_utils.log_manager import LogManager
        if success:
            LogManager.instance().log_success(
                node_type=self.NODE_TYPE,
                node_name=self.name
            )
        else:
            log_reason = reason or "条件不满足"
            if extra_info:
                log_reason += f"，{extra_info}"
            LogManager.instance().log_failure(
                node_type=self.NODE_TYPE,
                node_name=self.name,
                reason=log_reason
            )

    def reset(self, reset_counters: bool = True) -> None:
        super().reset(reset_counters)
        self._last_check_time = -self.check_interval_ms - 1


class ActionNode(Node):
    """动作节点基类

    执行特定动作，动作成功后可选执行子节点。
    """
    NODE_TYPE = "ActionNode"
    
    SKIP_WINDOW_SWITCH = False

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self._window_switched = False
        self._was_already_foreground = False

    def tick(self, context: "ExecutionContext") -> NodeStatus:
        return self._execute_with_decorators(context, self._tick_internal)

    def _tick_internal(self, context: "ExecutionContext") -> NodeStatus:
        from bt_utils.log_manager import LogManager
        bound_window = context.get_bound_window()

        if bound_window and not self.SKIP_WINDOW_SWITCH:
            if self._children_running:
                return self._execute_children(context)
            
            if not self._window_switched:
                from bt_utils.window_manager import WindowManager
                self._was_already_foreground = WindowManager.is_foreground_window(bound_window)
                
                if self._was_already_foreground:
                    LogManager.debug_print(f"[DEBUG] ActionNode '{self.name}' 绑定窗口已在前台，跳过切换")
                else:
                    LogManager.debug_print(f"[DEBUG] ActionNode '{self.name}' 检测到绑定窗口: hwnd={bound_window}")
                    context.smart_switch_to_bound_window()
                self._window_switched = True
            
            LogManager.debug_print(f"[DEBUG] ActionNode '{self.name}' 执行动作...")
            status = self._execute_action(context)
            
            if status != NodeStatus.RUNNING:
                if not self._was_already_foreground:
                    context.smart_restore_foreground_window()
                self._window_switched = False
                self._was_already_foreground = False
            
            self.status = status

            if status == NodeStatus.SUCCESS and self.children:
                context.notify_node_status(self.node_id, "success")
                self._children_running = True
                return self._execute_children(context)

            return status

        if not self._children_running:
            status = self._execute_action(context)
            self.status = status

            if status == NodeStatus.SUCCESS and self.children:
                context.notify_node_status(self.node_id, "success")
                self._children_running = True
                return self._execute_children(context)

            return status
        else:
            return self._execute_children(context)

    def reset(self, reset_counters: bool = True) -> None:
        super().reset(reset_counters)
        self._window_switched = False
        self._was_already_foreground = False

    @abstractmethod
    def _execute_action(self, context: "ExecutionContext") -> NodeStatus:
        """执行动作

        Args:
            context: 执行上下文

        Returns:
            执行状态
        """
        pass


class StartNode(CompositeNode):
    """
    开始节点 - 行为树的根节点
    
    特性:
    - 继承CompositeNode的组合节点特性
    - 顺序执行子节点，失败后继续执行下一个
    - 支持装饰器参数(重复次数、重复间隔、超时等)
    - 不可删除、不可复制、不可剪切
    """
    NODE_TYPE = "StartNode"
    
    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self._is_protected = True
        self.bind_window = self.config.get_bool("bind_window", False)
        self.window_title = self.config.get("window_title", "")
        self.window_pid = self.config.get_int("window_pid", 0)
        self._window_bound = False
    
    def tick(self, context: "ExecutionContext") -> NodeStatus:
        """顺序执行所有子节点,失败后继续执行
        
        与SequenceNode的区别:
        - SequenceNode: 任一子节点失败立即返回FAILURE
        - StartNode: 子节点失败后继续执行后续子节点
        
        Args:
            context: 执行上下文
            
        Returns:
            NodeStatus: 执行状态
        """
        return self._execute_with_decorators(context, self._tick_internal)
    
    def _tick_internal(self, context: "ExecutionContext") -> NodeStatus:
        from bt_utils.log_manager import LogManager

        if self.bind_window and self.window_title and not self._window_bound:
            self._bind_window_to_context(context)
            self._window_bound = True

        if not self.children:
            LogManager.instance().log_success(
                node_type="开始节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS
        
        LogManager.debug_print(
            f"[DEBUG] StartNode._tick_internal: '{self.name}' (id={self.node_id}) "
            f"ENTER: current_index={self.current_index}, children_count={len(self.children)}"
        )

        while self.current_index < len(self.children):
            child = self.children[self.current_index]
            
            if not child.config.enabled:
                self.current_index += 1
                continue
            
            LogManager.debug_print(
                f"[DEBUG] StartNode._tick_internal: '{self.name}' "
                f"ticking child[{self.current_index}]={child.NODE_TYPE} '{child.name}' "
                f"(id={child.node_id})"
            )

            status = child.tick(context)

            LogManager.debug_print(
                f"[DEBUG] StartNode._tick_internal: '{self.name}' "
                f"child[{self.current_index}]={child.NODE_TYPE} '{child.name}' "
                f"returned {status.name}"
            )
            
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            
            if status == NodeStatus.FAILURE:
                LogManager.instance().log_failure(
                    node_type="开始节点",
                    node_name=self.name,
                    reason=f"子节点 '{child.name}' 执行失败，继续执行后续节点"
                )
            
            self.current_index += 1
        
        self.current_index = 0
        
        LogManager.instance().log_success(
            node_type="开始节点",
            node_name=self.name
        )
        
        return NodeStatus.SUCCESS
    
    def reset(self, reset_counters: bool = True) -> None:
        """重置节点状态"""
        super().reset(reset_counters)
        self._window_bound = False
        for child in self.children:
            child.reset()

    def _bind_window_to_context(self, context: "ExecutionContext") -> None:
        from bt_utils.window_manager import WindowManager
        from bt_utils.log_manager import LogManager
        
        hwnd, find_method = WindowManager.find_window_smart(
            pid=self.window_pid if self.window_pid > 0 else None,
            title_keyword=self.window_title
        )
        
        if hwnd:
            context.bind_window(hwnd)
            rect = WindowManager.get_window_rect(hwnd)
            title = WindowManager.get_window_title(hwnd)
            actual_pid = WindowManager.get_window_pid(hwnd)
            
            if find_method == "pid":
                LogManager.debug_print(f"[DEBUG] StartNode 通过PID绑定窗口: pid={self.window_pid}, hwnd={hwnd}, title='{title}', rect={rect}")
            else:
                LogManager.debug_print(f"[DEBUG] StartNode 通过标题绑定窗口: title='{self.window_title}', hwnd={hwnd}, actual_title='{title}', pid={actual_pid}, rect={rect}")
                if actual_pid and actual_pid != self.window_pid:
                    LogManager.debug_print(f"[DEBUG] StartNode 提示: 窗口PID已变更 ({self.window_pid} -> {actual_pid})，建议重新选择窗口")
        else:
            LogManager.instance().log_failure(
                node_type="开始节点",
                node_name=self.name,
                reason=f"未找到窗口: pid={self.window_pid}, title='{self.window_title}'"
            )
            LogManager.debug_print(f"[DEBUG] StartNode 未找到窗口: pid={self.window_pid}, title='{self.window_title}'")
    
    def _reset_for_retry(self) -> None:
        """重试时重置状态（保留重试计数器）"""
        super()._reset_for_retry()
    
    def _reset_for_repeat(self) -> None:
        """重复执行时重置状态（保留重复计数器）"""
        super()._reset_for_repeat()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        序列化为字典
        
        Returns:
            Dict[str, Any]: 节点数据字典
        """
        data = super().to_dict()
        data["_is_protected"] = self._is_protected
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StartNode":
        """
        从字典反序列化
        
        Args:
            data: 节点数据字典
            
        Returns:
            StartNode: 节点实例
        """
        node = super().from_dict(data)
        node._is_protected = data.get("_is_protected", True)
        return node
