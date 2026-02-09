"""
Pydantic 数据模型定义
用于请求验证、响应序列化和类型提示
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ==================== 基础模型 ====================

class ActionItem(BaseModel):
    """单个动作项"""
    code: str = Field(..., description="动作代码，如 '1普', '2大', '重开:全灭'")


class RoundData(BaseModel):
    """单个回合的数据"""
    round_num: int = Field(..., ge=1, le=50, description="回合编号 1-50")
    actions: list[list[str]] = Field(default_factory=list, description="动作列表")


# ==================== 请求模型 ====================

class RoundActionsRequest(BaseModel):
    """保存回合动作请求体"""
    actions: list[list[str]] = Field(default_factory=list, description="动作组列表")

    @field_validator('actions')
    @classmethod
    def validate_actions(cls, v):
        """验证动作格式"""
        for group in v:
            if not isinstance(group, list):
                raise ValueError('动作组必须是列表')
            for action in group:
                if not isinstance(action, str):
                    raise ValueError('动作必须是字符串')
        return v


class GenerateLoopRequest(BaseModel):
    """生成循环回合请求"""
    start: int = Field(..., ge=1, le=50, description="模板起始回合")
    end: int = Field(..., ge=1, le=50, description="模板结束回合")

    @field_validator('end')
    @classmethod
    def validate_end(cls, v, info):
        """验证结束回合不小于起始回合"""
        if 'start' in info.data and v < info.data['start']:
            raise ValueError('结束回合不能小于起始回合')
        return v


class ExportRequest(BaseModel):
    """导出配置请求"""
    level_name: str = Field(default='generated_config', description="关卡名称")
    level_type: Literal['', '主线', '洞窟', '活动有分级', '白鹄', '兰台'] = Field(default='', description="关卡类型")
    level_recognition_name: str = Field(default='', description="关卡识别名称")
    difficulty: str = Field(default='', description="难度等级")
    cave_type: Literal['', '左', '右'] = Field(default='', description="洞窟类型")
    lantai_nav: str = Field(default='true', description="兰台导航设置")
    attack_delay: str = Field(default='', description="普攻延迟(ms)")
    ult_delay: str = Field(default='', description="大招延迟(ms)")
    defense_delay: str = Field(default='', description="防御延迟(ms)")
    actions: dict = Field(default_factory=dict, description="回合动作数据")


class RestartRequest(BaseModel):
    """添加重开动作请求"""
    roundNum: int = Field(..., ge=1, le=50, description="回合编号")
    restartType: Literal['全灭重开', '左上角'] = Field(..., description="重开类型")
    isExtended: bool = Field(default=False, description="是否添加到扩展行")


class OpenFolderRequest(BaseModel):
    """打开文件夹请求"""
    path: str = Field(..., description="文件或文件夹路径")


# ==================== 响应模型 ====================

class SuccessResponse(BaseModel):
    """成功响应"""
    status: str = "success"
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    details: Optional[str] = None


class ActionsResponse(BaseModel):
    """动作配置响应"""
    actions: dict = Field(default_factory=dict, description="所有回合动作")


class ConfigInfo(BaseModel):
    """关卡配置信息"""
    level_type: str = Field(default='')
    level_recognition_name: str = Field(default='')
    difficulty: str = Field(default='')
    cave_type: str = Field(default='')
    lantai_nav: str = Field(default='')
    attack_delay: str = Field(default='3000')
    ult_delay: str = Field(default='5000')
    defense_delay: str = Field(default='3000')


class ImportResponse(BaseModel):
    """导入配置响应"""
    message: str = "导入成功"
    actions: dict = Field(default_factory=dict)
    config_info: ConfigInfo = Field(default_factory=ConfigInfo)


class ExportResponse(BaseModel):
    """导出配置响应"""
    content: str = Field(..., description="配置文件内容")
    filename: str = Field(..., description="文件名")


# ==================== 领域模型 ====================

class LevelConfig(BaseModel):
    """关卡配置领域模型"""
    level_type: str = ''
    level_recognition_name: str = ''
    difficulty: str = ''
    cave_type: str = ''
    lantai_nav: str = 'true'
    attack_delay: int = 3000
    ult_delay: int = 5000
    defense_delay: int = 3000

    @field_validator('attack_delay', 'ult_delay', 'defense_delay', mode='before')
    @classmethod
    def parse_delay(cls, v):
        """将字符串延迟转换为整数"""
        if v is None or v == '':
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class ActionConfig(BaseModel):
    """动作配置领域模型"""
    round_actions: dict[str, list[list[str]]] = Field(default_factory=dict)

    def get_max_round(self) -> int:
        """获取当前最大回合数"""
        if not self.round_actions:
            return 0
        return max(int(k) for k in self.round_actions.keys())

    def get_max_round_with_actions(self) -> int:
        """获取包含实际行动的最大回合数"""
        max_round = 0
        for rn, acts in self.round_actions.items():
            if any(isinstance(g, list) and len(g) > 0 for g in acts):
                max_round = max(max_round, int(rn))
        return max_round
