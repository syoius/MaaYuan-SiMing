"""
动作配置业务服务层
处理回合动作的增删改查和业务规则验证
"""
from typing import Optional

from backend.config import Constants
from backend.models.schemas import (
    ActionConfig, ConfigInfo, LevelConfig,
    GenerateLoopRequest, ExportRequest, RestartRequest
)
from backend.repositories.action_repo import ActionRepository
from backend.services.config_generator import ConfigGenerator


class ActionServiceError(Exception):
    """动作服务异常基类"""
    pass


class RoundLimitError(ActionServiceError):
    """回合数限制错误"""
    pass


class InvalidActionError(ActionServiceError):
    """无效动作错误"""
    pass


class ActionService:
    """
    回合动作业务服务
    封装所有业务逻辑，协调 Repository 和 ConfigGenerator
    """

    def __init__(self, repository: Optional[ActionRepository] = None):
        """
        初始化服务

        Args:
            repository: 存储仓库实例，默认创建新的
        """
        self.repository = repository or ActionRepository()
        self.config_generator = ConfigGenerator()

    def get_all_actions(self) -> dict:
        """
        获取所有回合动作

        Returns:
            dict: 回合动作字典
        """
        return self.repository.load_all()

    def get_round_actions(self, round_num: int) -> list:
        """
        获取指定回合的动作

        Args:
            round_num: 回合编号

        Returns:
            list: 动作列表
        """
        return self.repository.load_round(str(round_num))

    def save_round_actions(self, round_num: int, actions: list) -> None:
        """
        保存回合动作

        Args:
            round_num: 回合编号
            actions: 动作列表

        Raises:
            RoundLimitError: 超过最大回合限制
        """
        if round_num > Constants.MAX_ROUNDS:
            raise RoundLimitError(f"超过{Constants.MAX_ROUNDS}回合限制")

        self.repository.save_round(str(round_num), actions)

    def add_round(self, round_num: int) -> bool:
        """
        添加新回合

        Args:
            round_num: 回合编号

        Returns:
            bool: 是否成功添加（已存在则返回False）

        Raises:
            RoundLimitError: 超过最大回合限制
        """
        if round_num > Constants.MAX_ROUNDS:
            raise RoundLimitError(f"超过{Constants.MAX_ROUNDS}回合限制")

        actions = self.repository.load_all()
        round_key = str(round_num)

        if round_key not in actions:
            actions[round_key] = []
            self.repository.save_all(actions)
            return True
        return False

    def delete_round(self, round_num: int) -> bool:
        """
        删除回合

        Args:
            round_num: 回合编号

        Returns:
            bool: 是否成功删除
        """
        return self.repository.delete_round(str(round_num))

    def clear_round(self, round_num: int) -> None:
        """
        清空回合动作

        Args:
            round_num: 回合编号
        """
        self.repository.clear_round(str(round_num))

    def clear_all(self) -> None:
        """清空所有配置"""
        self.repository.clear_all()

    def generate_loop(self, request: GenerateLoopRequest) -> None:
        """
        生成循环回合

        Args:
            request: 循环生成请求

        Raises:
            RoundLimitError: 超过最大回合限制或无效模板范围
        """
        actions = self.repository.load_all()
        start_key, end_key = str(request.start), str(request.end)

        if start_key not in actions or end_key not in actions:
            raise ActionServiceError("起始回合或结束回合未设置")

        if request.start > request.end:
            raise ActionServiceError("起始回合不能大于结束回合")

        template_length = request.end - request.start + 1
        max_round = max(int(k) for k in actions.keys()) if actions else 0
        next_start = max_round + 1

        if next_start + template_length - 1 > Constants.MAX_ROUNDS:
            raise RoundLimitError(f"超过{Constants.MAX_ROUNDS}回合限制")

        # 复制模板
        for offset in range(template_length):
            src_round = str(request.start + offset)
            target_round = str(next_start + offset)
            if src_round in actions:
                actions[target_round] = actions[src_round].copy()

        self.repository.save_all(actions)

    def export_config(self, request: ExportRequest) -> dict:
        """
        导出 MAA 配置

        Args:
            request: 导出请求

        Returns:
            dict: 包含 content 和 filename 的字典
        """
        print(f"[DEBUG] ActionService.export_config - request.level_type: '{request.level_type}'")
        # 构建 LevelConfig
        level_config = LevelConfig(
            level_type=request.level_type,
            level_recognition_name=request.level_recognition_name,
            rec_target_offset=request.rec_target_offset,
            difficulty=request.difficulty,
            cave_type=request.cave_type,
            lantai_nav=request.lantai_nav,
            attack_delay=request.attack_delay or None,
            ult_delay=request.ult_delay or None,
            defense_delay=request.defense_delay or None,
        )
        print(f"[DEBUG] ActionService.export_config - level_config.level_type: '{level_config.level_type}'")

        # 生成配置
        config = self.config_generator.generate(request.actions, level_config)

        return {
            'content': config,
            'filename': f"{request.level_name}.json"
        }

    def import_config(self, config_data: dict) -> dict:
        """
        导入 MAA 配置

        Args:
            config_data: MAA 配置字典

        Returns:
            dict: {'actions': round_actions, 'config_info': config_info_dict}
        """
        result = self.config_generator.reverse(config_data)
        self.repository.save_all(result['actions'])
        return result

    def add_restart(self, request: RestartRequest) -> None:
        """
        添加重开动作

        Args:
            request: 重开请求

        Raises:
            ActionServiceError: 回合不存在或无动作
        """
        actions = self.repository.load_all()
        round_key = str(request.roundNum)

        if round_key not in actions:
            raise ActionServiceError("回合不存在")

        current_actions = actions[round_key]
        if not current_actions:
            raise ActionServiceError("请先添加动作再设置重开")

        restart_text = "全灭" if request.restartType == "全灭重开" else "左上角"
        restart_action = [f"重开:{restart_text}"]

        # 获取 firstLineActions
        first_line_actions = current_actions.get('firstLineActions', len(current_actions))

        if request.isExtended:
            current_actions.append(restart_action)
        else:
            current_actions.insert(first_line_actions, restart_action)
            current_actions['firstLineActions'] = first_line_actions + 1

        actions[round_key] = current_actions
        self.repository.save_all(actions)

    def get_action_config(self) -> ActionConfig:
        """
        获取动作配置领域模型

        Returns:
            ActionConfig: 动作配置
        """
        return self.repository.get_action_config()
