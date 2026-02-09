"""
全局配置模块
统一处理环境判断、路径配置和常量定义
"""
import os
import sys


def is_frozen() -> bool:
    """判断是否为 PyInstaller 打包后的环境"""
    return getattr(sys, 'frozen', False)


def get_base_dir() -> str:
    """获取应用基础目录"""
    if is_frozen():
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


def get_data_dir() -> str:
    """获取数据存储目录"""
    data_dir = os.path.join(get_base_dir(), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_output_dir() -> str:
    """获取配置输出目录"""
    output_dir = os.path.join(get_base_dir(), 'output')
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def get_template_dir() -> str:
    """获取模板文件目录"""
    if is_frozen():
        return os.path.join(sys._MEIPASS, 'backend', 'templates')
    else:
        return os.path.join(get_base_dir(), 'templates')


def get_template_path(filename: str = 'fight_action.json') -> str:
    """获取指定模板文件的完整路径"""
    return os.path.join(get_template_dir(), filename)


def get_frontend_dir() -> str:
    """获取前端资源目录"""
    base = sys._MEIPASS if is_frozen() else os.path.dirname(get_base_dir())
    return os.path.join(base, 'frontend')


# 应用常量
class Constants:
    """应用常量定义"""
    MAX_ROUNDS = 50
    DEFAULT_PORT = 49481
    CONFIG_FILENAME = 'round_actions.json'


# 导出常用路径函数
__all__ = [
    'is_frozen',
    'get_base_dir',
    'get_data_dir',
    'get_output_dir',
    'get_template_dir',
    'get_template_path',
    'get_frontend_dir',
    'Constants',
]
