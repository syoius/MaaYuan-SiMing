"""
动作配置存储层
封装 JSON 文件的读写操作
"""
import json
import os
from typing import Optional

from backend.config import get_data_dir, Constants
from backend.models.schemas import ActionConfig


class ActionRepository:
    """
    回合动作配置的存储仓库
    使用 JSON 文件作为持久化存储
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化仓库

        Args:
            data_dir: 数据目录，默认使用 config.get_data_dir()
        """
        self.data_dir = data_dir or get_data_dir()
        self.config_file = os.path.join(self.data_dir, Constants.CONFIG_FILENAME)

    def load_all(self) -> dict:
        """
        加载所有回合动作配置

        Returns:
            dict: 回合动作字典，键为回合号字符串，值为动作列表
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except json.JSONDecodeError as e:
            print(f"配置文件解析失败: {str(e)}")
            return {}
        except Exception as e:
            print(f"加载配置失败: {str(e)}")
            return {}

    def load_round(self, round_num: str) -> list:
        """
        加载指定回合的动作

        Args:
            round_num: 回合号（字符串）

        Returns:
            list: 该回合的动作列表
        """
        actions = self.load_all()
        return actions.get(round_num, [])

    def save_all(self, actions: dict) -> None:
        """
        保存所有回合动作配置

        Args:
            actions: 回合动作字典

        Raises:
            IOError: 文件写入失败时抛出
        """
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(actions, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置失败: {str(e)}")
            raise IOError(f"保存配置失败: {str(e)}") from e

    def save_round(self, round_num: str, actions: list) -> None:
        """
        保存单个回合的动作

        Args:
            round_num: 回合号（字符串）
            actions: 动作列表
        """
        all_actions = self.load_all()
        all_actions[round_num] = actions
        self.save_all(all_actions)

    def delete_round(self, round_num: str) -> bool:
        """
        删除指定回合

        Args:
            round_num: 回合号（字符串）

        Returns:
            bool: 是否成功删除（回合存在则返回True）
        """
        all_actions = self.load_all()
        if round_num in all_actions:
            del all_actions[round_num]
            self.save_all(all_actions)
            return True
        return False

    def clear_round(self, round_num: str) -> None:
        """
        清空指定回合的动作（保留回合，清空动作列表）

        Args:
            round_num: 回合号（字符串）
        """
        all_actions = self.load_all()
        if round_num in all_actions:
            all_actions[round_num] = []
            self.save_all(all_actions)

    def clear_all(self) -> None:
        """清空所有配置"""
        self.save_all({})

    def get_action_config(self) -> ActionConfig:
        """
        获取 ActionConfig 领域模型

        Returns:
            ActionConfig: 动作配置领域模型
        """
        return ActionConfig(round_actions=self.load_all())


class TemplateRepository:
    """
    模板文件存储仓库
    """

    def __init__(self, template_path: Optional[str] = None):
        """
        初始化模板仓库

        Args:
            template_path: 模板文件路径，默认使用 config.get_template_path()
        """
        from backend.config import get_template_path
        self.template_path = template_path or get_template_path()

    def load_action_templates(self) -> dict:
        """
        加载动作模板

        Returns:
            dict: 动作模板字典

        Raises:
            FileNotFoundError: 模板文件不存在
            json.JSONDecodeError: 模板文件解析失败
        """
        with open(self.template_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_action_templates(self, templates: dict) -> None:
        """
        保存动作模板（通常用于修改延迟等配置）

        Args:
            templates: 动作模板字典
        """
        with open(self.template_path, 'w', encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=4)
