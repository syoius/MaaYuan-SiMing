"""
MAA 配置生成器服务
负责将回合动作转换为 MAA 框架可用的 JSON 配置
"""
import json
import os
import re
from typing import Optional

from backend.config import get_template_path
from backend.models.schemas import LevelConfig


class ConfigGenerator:
    """
    MAA 配置文件生成器
    支持正向生成和逆向解析
    """

    def __init__(self, template_path: Optional[str] = None):
        """
        初始化配置生成器

        Args:
            template_path: 动作模板路径
        """
        self.template_path = template_path or get_template_path()
        self._templates: Optional[dict] = None

    def _load_templates(self) -> dict:
        """加载并缓存动作模板"""
        if self._templates is None:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                self._templates = json.load(f)
        return self._templates.copy()

    def _apply_custom_delays(self, templates: dict, config: LevelConfig) -> None:
        """应用自定义延迟到模板"""
        delays = {
            "普攻": config.attack_delay,
            "上拉": config.ult_delay,
            "下拉": config.defense_delay,
        }

        for suffix, delay in delays.items():
            if delay is None:
                continue
            for key, value in templates.items():
                if key.endswith(suffix) and isinstance(value, dict) and "post_delay" in value:
                    value["post_delay"] = delay

    def _get_action_config(self, action_code: str, templates: dict) -> Optional[dict]:
        """
        将动作代码转换为配置

        Args:
            action_code: 如 "1普", "2大", "1sp"
            templates: 动作模板字典

        Returns:
            动作配置字典或 None
        """
        if len(action_code) < 2:
            return None
        position = action_code[0]
        action_type = action_code[1:]
        key_map = {
            "普": "普攻",
            "大": "上拉",
            "下": "下拉",
            "sp": "SP"
        }
        key = f"{position}号位{key_map.get(action_type, action_type)}"
        return templates.get(key)

    def _get_action_focus(self, action_code: str) -> str:
        """将动作代码转换为中文描述"""
        if not action_code or len(action_code) < 2:
            return action_code
        pos = action_code[0]
        act = action_code[1:]
        pos_map = {'1': '1号位', '2': '2号位', '3': '3号位', '4': '4号位', '5': '5号位'}
        act_map = {'普': '普攻', '大': '大招', '下': '防御', 'sp': 'SP'}
        return f"{pos_map.get(pos, pos)}{act_map.get(act, act)}"

    def _parse_detection(self, text: str) -> Optional[dict]:
        """
        解析检测类动作文本，返回 {custom_action, position, text_doc} 或 None

        支持格式：
            - 重开:检测X号位阵亡 → DownRestart
            - 重开:检测X号位退场 → RetreatRestart
            - 重开:检测X号位鹦鹉 → BirdRestart
            - 重开:检测X号位龙气 → DragonRestart
        """
        match = re.search(r'检测(\d+)号位(阵亡|退场|鹦鹉|龙气)', text)
        if not match:
            return None
        position = int(match.group(1))
        condition = match.group(2)
        type_map = {
            "阵亡": ("DownRestart", f"{position}号位阵亡检测"),
            "退场": ("RetreatRestart", f"{position}号位退场检测"),
            "鹦鹉": ("BirdRestart", f"{position}号位鹦鹉检测"),
            "龙气": ("DragonRestart", f"{position}号位龙气检测"),
        }
        custom_action, text_doc = type_map[condition]
        return {
            "custom_action": custom_action,
            "position": position,
            "text_doc": text_doc,
        }

    def _append_to_next(self, node: dict, value: str) -> None:
        """向节点的 next 字段追加值"""
        if "next" not in node:
            node["next"] = []
        if isinstance(node["next"], list) and value not in node["next"]:
            node["next"].append(value)

    def _set_next(self, node: dict, values: list) -> None:
        """设置节点的 next 字段"""
        node["next"] = values.copy()

    def _get_route_key(self, item):
        """获取路由项的标识键（处理字符串和字典类型的节点属性）"""
        if isinstance(item, dict):
            return item.get('name', str(item))
        return item

    def _deduplicate_routes(self, config: dict) -> None:
        """路由去重"""
        for node in config.values():
            if not isinstance(node, dict):
                continue

            routes = {}
            for key in ("next", "on_error"):
                value = node.get(key)
                if isinstance(value, list):
                    seen = set()
                    deduped = []
                    for item in value:
                        route_key = self._get_route_key(item)
                        if route_key not in seen:
                            deduped.append(item)
                            seen.add(route_key)
                    routes[key] = deduped
                else:
                    routes[key] = value

            taken = set()
            for key in ("next", "on_error"):
                value = routes.get(key)
                if isinstance(value, list):
                    filtered = []
                    for item in value:
                        route_key = self._get_route_key(item)
                        if route_key not in taken:
                            filtered.append(item)
                            taken.add(route_key)
                    routes[key] = filtered

            for key, value in routes.items():
                if isinstance(value, list):
                    node[key] = value

    def _get_extra_action_config(self, action: str, action_key: str) -> Optional[dict]:
        """获取额外动作的配置"""
        extra_type = action.split(':')[1]

        configs = {
            "左侧目标": {
                "text_doc": "左侧目标",
                "focus": "切换至左侧目标",
                "action": "Click",
                "target": [154, 648, 1, 1],
                "post_delay": 2000,
                "duration": 800
            },
            "右侧目标": {
                "text_doc": "右侧目标",
                "focus": "切换至右侧目标",
                "action": "Click",
                "target": [603, 413, 18, 21],
                "post_delay": 2000,
                "duration": 800
            },
            "吕布": {
                "text_doc": "吕布",
                "focus": "点击吕布-切换形态",
                "recognition": "TemplateMatch",
                "template": ["copilot/lb_l2h.png", "copilot/lb_h2l.png"],
                "roi": [15, 1072, 690, 95],
                "action": "Click",
                "pre_delay": 500,
                "post_delay": 3000,
            },
            "开自动": {
                "text_doc": "开自动",
                "focus": "开始自动战斗",
                "recognition": "OCR",
                "expected": "手",
                "roi": [635, 610, 85, 95],
                "action": "Click",
                "timeout": 1800000
            },
            "史子眇sp": {
                "text_doc": "额外:史子眇sp",
                "focus": "点击史子眇sp",
                "recognition": "TemplateMatch",
                "template": "copilot/szm_sp_skill.png",
                "roi": [15, 1072, 690, 95],
                "action": "Click",
                "pre_delay": 500,
                "post_delay": 5000
            },
            "关卡内互动": {
                "text_doc": "关卡内互动",
                "pre_delay": 500,
                "action": {
                    "type": "Click",
                    "param": {
                        "target": [662, 398, 18, 22]
                    }
                },
                "post_delay": 1500
            }
        }

        if extra_type in configs:
            return configs[extra_type].copy()

        if extra_type == "等待":
            wait_time = int(action.split(':')[2])
            return {
                "text_doc": "等待",
                "focus": f"等待{wait_time}ms",
                "post_delay": wait_time
            }

        return None

    def generate(self, round_actions: dict, config: LevelConfig) -> dict:
        """
        生成 MAA 配置

        Args:
            round_actions: 回合动作字典
            config: 关卡配置

        Returns:
            MAA 配置字典
        """
        print(f"[DEBUG] ConfigGenerator.generate - config.level_type: '{config.level_type}'")
        templates = self._load_templates()
        self._apply_custom_delays(templates, config)

        if not round_actions:
            raise ValueError("没有找到任何回合动作配置")

        # 找到最后一个有实际行动的回合
        max_round_with_actions = 0
        for rn, acts in round_actions.items():
            if any(isinstance(g, list) and len(g) > 0 for g in acts):
                max_round_with_actions = max(max_round_with_actions, int(rn))

        result_config = {}
        current_action_key = None

        # 先扫描橙星/紫星/蓝星检测回合
        orangestar_rounds = set()
        purplestar_rounds = set()
        bluestar_rounds = set()
        for round_num, actions in round_actions.items():
            for group in actions:
                if isinstance(group, list) and len(group) > 0:
                    if group[0].startswith('重开:无橙星'):
                        orangestar_rounds.add(str(round_num))
                    elif group[0].startswith('重开:无紫星'):
                        purplestar_rounds.add(str(round_num))
                    elif group[0].startswith('重开:无蓝星'):
                        bluestar_rounds.add(str(round_num))

        # 生成回合节点
        for round_num, actions in round_actions.items():
            round_num_str = str(round_num)
            has_actions = any(isinstance(g, list) and len(g) > 0 for g in actions)

            if int(round_num) > max_round_with_actions and not has_actions:
                continue

            # 确定下一个节点
            first_action = actions[0][0] if actions and actions[0] else None
            if round_num_str in orangestar_rounds:
                next_list = [f"第{round_num}回合橙星检测"]
            elif round_num_str in purplestar_rounds:
                next_list = [f"第{round_num}回合紫星检测"]
            elif round_num_str in bluestar_rounds:
                next_list = [f"第{round_num}回合蓝星检测"]
            elif first_action and ('检测' in first_action):
                next_list = [f"回合{round_num}行动1"]
            elif first_action and first_action.startswith('重开:'):
                restart_type = first_action.split(':')[1]
                restart_node = f"抄作业{restart_type}重开" if restart_type == "全灭" else f"抄作业点左上角重开"
                next_list = [restart_node]
            else:
                next_list = [f"回合{round_num}行动1"]

            # 回合检测节点
            result_config[f"检测回合{round_num}"] = {
                "recognition": "Custom",
                "custom_recognition": "PureNum",
                "custom_recognition_param": {
                    "roi": [641, 50, 43, 27],
                    "expected": str(round_num)
                },
                "text_doc": f"回合{round_num}",
                "focus": f"当前：第{round_num}回合",
                "next": next_list,
                "on_error": ["抄作业点左上角重开"],
                "timeout": 3000,
                "post_delay": 4000,
            }

            # 橙星检测节点
            if round_num_str in orangestar_rounds:
                result_config[f"第{round_num}回合橙星检测"] = {
                    "recognition": "ColorMatch",
                    "upper": [255, 255, 120],
                    "lower": [180, 160, 40],
                    "roi": [58, 160, 103, 88],
                    "next": [f"回合{round_num}行动1"],
                    "text_doc": f"第{round_num}回合橙星检测",
                    "focus": f"第{round_num}回合有橙星"
                }
            # 紫星检测节点
            elif round_num_str in purplestar_rounds:
                result_config[f"第{round_num}回合紫星检测"] = {
                    "recognition": "ColorMatch",
                    "upper": [198, 115, 227],
                    "lower": [112, 54, 133],
                    "roi": [58, 160, 103, 88],
                    "next": [f"回合{round_num}行动1"],
                    "text_doc": f"第{round_num}回合紫星检测",
                    "focus": f"第{round_num}回合有紫星"
                }
            # 蓝星检测节点
            elif round_num_str in bluestar_rounds:
                result_config[f"第{round_num}回合蓝星检测"] = {
                    "recognition": "ColorMatch",
                    "upper": [79, 142, 189],
                    "lower": [59, 122, 169],
                    "roi": [58, 160, 103, 88],
                    "next": [f"回合{round_num}行动1"],
                    "text_doc": f"第{round_num}回合蓝星检测",
                    "focus": f"第{round_num}回合有蓝星"
                }

            action_counter = 1
            current_action_key = None

            # 生成动作节点
            for action_group in actions:
                if not (isinstance(action_group, list) and len(action_group) > 0):
                    continue

                action = action_group[0]

                # 处理检测类重开（阵亡/退场/鹦鹉/龙气）
                if '重开:检测' in action:
                    action_key = f"回合{round_num}行动{action_counter}"
                    det = self._parse_detection(action)
                    if det is None:
                        raise ValueError(f"无法解析检测动作: {action}")

                    result_config[action_key] = {
                        "text_doc": det["text_doc"],
                        "action": "Custom",
                        "custom_action": det["custom_action"],
                        "custom_action_param": {"node": action_key, "position": det["position"]}
                    }

                    if current_action_key:
                        self._append_to_next(result_config[current_action_key], action_key)

                    current_action_key = action_key
                    action_counter += 1
                    continue

                # 处理重开指令
                if action.startswith('重开:'):
                    restart_type = action.split(':')[1]

                    if restart_type == "全灭" and current_action_key:
                        original_next = result_config[current_action_key].get("next", [])
                        new_next = ["抄作业全灭重开"] + [n for n in original_next if n != "抄作业全灭重开"]
                        self._set_next(result_config[current_action_key], new_next)

                    elif restart_type == "左上角" and current_action_key:
                        self._set_next(result_config[current_action_key], ["抄作业点左上角重开"])

                    continue

                # 处理正常动作
                action_key = f"回合{round_num}行动{action_counter}"

                if action.startswith('额外:'):
                    extra_config = self._get_extra_action_config(action, action_key)
                    if extra_config:
                        result_config[action_key] = extra_config
                    else:
                        # 再动动作
                        _, action_code = action.split(':')
                        base_config = self._get_action_config(action_code, templates)
                        if base_config:
                            result_config[action_key] = base_config.copy()
                        result_config[action_key]["text_doc"] = f"再动{action_code}"
                        result_config[action_key]["focus"] = f"再次行动:{self._get_action_focus(action_code)}"
                else:
                    base_config = self._get_action_config(action, templates)
                    if base_config:
                        result_config[action_key] = base_config.copy()
                    result_config[action_key]["text_doc"] = action
                    result_config[action_key]["focus"] = f"行动:{self._get_action_focus(action)}"

                if current_action_key:
                    self._append_to_next(result_config[current_action_key], action_key)

                current_action_key = action_key
                action_counter += 1

            # 最后一个动作指向下回合
            if current_action_key:
                if int(round_num) < max_round_with_actions:
                    self._append_to_next(result_config[current_action_key], f"检测回合{int(round_num)+1}")

        # 每个行动结束后都优先检测战斗是否胜利。
        # 只处理行动节点，避免将检测插入回合识别、重开或导航路由。
        action_key_pattern = re.compile(r'^回合\d+行动\d+$')
        for node_name, node in result_config.items():
            if not action_key_pattern.fullmatch(node_name):
                continue
            next_field = node.get("next", [])
            node["next"] = ["抄作业战斗胜利-check"] + [
                route for route in next_field
                if route != "抄作业战斗胜利-check"
            ]

        # 添加导航和辅助节点
        self._add_navigation_nodes(result_config, config)

        # 路由去重
        self._deduplicate_routes(result_config)

        return result_config

    def _add_navigation_nodes(self, config: dict, level_config: LevelConfig) -> None:
        """添加导航节点"""
        # 确定重开后导航节点
        nav_map = {
            '主线': "抄作业找到关卡-主线",
            '洞窟': "抄作业进入关卡-洞窟",
            '活动': "抄作业找到关卡-活动",
            '活动有分级': "抄作业找到关卡-活动分级",
            '白鹄': "抄作业进入关卡-白鹄",
            '兰台': "抄作业找到关卡-兰台",
        }
        next_node = nav_map.get(level_config.level_type, "抄作业找到关卡-OCR")

        # 左上角重开节点
        config["抄作业点左上角重开"] = {
            "recognition": "TemplateMatch",
            "template": "back.png",
            "green_mask": True,
            "threshold": 0.5,
            "roi": [6, 8, 123, 112],
            "action": "Click",
            "pre_delay": 500,
            "post_delay": 2000,
            "next": ["[JumpBack]抄作业确定左上角重开", "抄作业退出兰台木桩", next_node],
            "focus": "正在尝试点左上角重开",
            "timeout": 20000
        }

        # 作业信息
        config["作业信息"] = {
            "focus": "[color:#D48806] [如果版本符合请无视] 该作业由 MaaYuan Share v26.08.01 生成，推荐使用 MaaYuan v2.2.0-beta1 或更高版本运行，以免作业无法使用。如作业中包含以下功能则必须使用最新版本：1️⃣自定义点击偏移量（e.g. 泰山府关卡且使用了重开/自动赌功能）2️⃣退场检测重开 3️⃣未被复制重开（庞统鹦鹉） 4️⃣不足2龙气重开"
        }

        config["抄作业胜利后继续"] = {
            "focus": "战斗胜利，尝试继续",
            "next": [next_node]
        }

        # 自定义延时
        delays = level_config.model_dump()
        config["抄作业自定义延时"] = {
            "attack_delay": str(delays.get('attack_delay', '')),
            "ult_delay": str(delays.get('ult_delay', '')),
            "defense_delay": str(delays.get('defense_delay', ''))
        }

        # 关卡特定导航节点
        print(f"[DEBUG] _add_navigation_nodes - level_config.level_type: '{level_config.level_type}'")
        if level_config.level_type == '洞窟':
            print("[DEBUG] 进入洞窟分支")
            self._add_cave_nodes(config, level_config, next_node)
        elif level_config.level_type == '兰台':
            print("[DEBUG] 进入兰台分支")
            self._add_lantai_nodes(config, level_config, next_node)
        elif level_config.level_type == '活动':
            self._add_simple_event_nodes(config, level_config, next_node)
        elif level_config.level_type == '活动有分级':
            self._add_event_nodes(config, level_config, next_node)
        elif level_config.level_type not in ('主线', '白鹄'):
            self._add_ocr_nodes(config, level_config, next_node)

    def _add_cave_nodes(self, config: dict, level_config: LevelConfig, next_node: str) -> None:
        """添加洞窟导航节点"""
        is_left = level_config.cave_type == '左'
        config["抄作业进入关卡-洞窟"] = {
            "text_doc": "左" if is_left else "右",
            "recognition": "OCR",
            "expected": "前",
            "replace": ["煎", "前"],
            "roi": [237, 810, 82, 89] if is_left else [558, 804, 79, 89],
            "action": "Click",
            "target": [258, 833, 42, 39] if is_left else [581, 832, 41, 41],
            "pre_delay": 1500,
            "next": ["抄作业准备开始战斗"],
            "timeout": 20000
        }

    def _add_lantai_nodes(self, config: dict, level_config: LevelConfig, next_node: str) -> None:
        """添加兰台导航节点"""
        level_name = level_config.level_recognition_name
        print(f"[DEBUG] _add_lantai_nodes - level_name: '{level_name}'")
        simple_levels = {'诛仙阵', '戮魔阵', '奉诏讨伐', '右'}
        other_simple = {'千军阵', '三才阵', '北风演习', '左'}

        if level_name in simple_levels:
            print(f"[DEBUG] 进入简单关卡分支 (诛仙阵/戮魔阵/奉诏讨伐)")
            target = [430, 1197, 28, 30]
        elif level_name in other_simple:
            print(f"[DEBUG] 进入其他简单关卡分支 (千军阵/三才阵/北风演习)")
            target = [244, 1195, 30, 35]
        else:
            print(f"[DEBUG] 进入复杂兰台关卡分支 (生成 jump_back 节点)")
            config["抄作业找到关卡-兰台"] = {
                "level": level_name,
                "recognition": "TemplateMatch",
                "template": "baihu/lantai.png",
                "order_by": "Vertical",
                "roi": [19, 318, 684, 905],
                "action": "Click",
                "pre_delay": 500,
                "post_delay": 500,
                "next": [
                    "抄作业准备开始战斗",
                    "[JumpBack]抄作业-兰台确认进入关卡",
                ],
                "timeout": 4000
            }
            config["抄作业-兰台确认进入关卡"] = {
                "recognition": "OCR",
                "expected": "进入",
                "replace": ["進", "进"],
                "roi": [195, 711, 334, 186],
                "action": "Click",
                "pre_delay": 500,
                "next": ["抄作业找到关卡-兰台"]
            }
            return

        config["抄作业找到关卡-兰台"] = {
            "level": level_name,
            "recognition": "OCR",
            "expected": "切换难度",
            "replace": [["難", "难"], ["換", "换"]],
            "roi": [535, 1208, 180, 70],
            "action": "Click",
            "pre_delay": 500,
            "target": target,
            "next": ["抄作业准备开始战斗"]
        }

    def _add_simple_event_nodes(self, config: dict, level_config: LevelConfig, next_node: str) -> None:
        """添加活动导航节点（无难度分级）"""
        config["抄作业找到关卡-活动"] = {
            "recognition": "OCR",
            "expected": level_config.level_recognition_name,
            "roi": [0, 249, 720, 1030],
            "action": "Click",
            "target_offset": level_config.rec_target_offset,
            "pre_delay": 1500,
            "next": ["抄作业进入关卡"],
            "timeout": 20000
        }

    def _add_event_nodes(self, config: dict, level_config: LevelConfig, next_node: str) -> None:
        """添加活动导航节点"""
        config["抄作业找到关卡-活动分级"] = {
            "recognition": "OCR",
            "expected": level_config.level_recognition_name,
            "roi": [0, 249, 720, 1030],
            "action": "Click",
            "target_offset": level_config.rec_target_offset,
            "pre_delay": 1500,
            "next": ["抄作业选择活动分级"],
            "timeout": 20000
        }
        config["抄作业选择活动分级"] = {
            "recognition": "OCR",
            "expected": level_config.difficulty,
            "roi": [37, 351, 647, 491],
            "pre_delay": 1500,
            "action": "Click",
            "next": ["抄作业进入关卡"],
            "timeout": 20000
        }

    def _add_ocr_nodes(self, config: dict, level_config: LevelConfig, next_node: str) -> None:
        """添加通用 OCR 导航节点"""
        config["抄作业找到关卡-OCR"] = {
            "recognition": "OCR",
            "expected": level_config.level_recognition_name,
            "roi": [0, 297, 720, 1030],
            "action": "Click",
            "target_offset": level_config.rec_target_offset,
            "pre_delay": 2000,
            "next": ["抄作业进入关卡"],
            "timeout": 20000
        }

    @staticmethod
    def _get_rec_target_offset(node: dict) -> list[int]:
        """从 OCR 节点读取合法的点击偏移量，非法或缺失时返回默认值。"""
        if not isinstance(node, dict):
            return [0, 0, 0, 0]

        target_offset = node.get("target_offset")
        if (
            isinstance(target_offset, list)
            and len(target_offset) == 4
            and all(type(item) is int for item in target_offset)
        ):
            return target_offset.copy()
        return [0, 0, 0, 0]

    def reverse(self, config_data: dict) -> dict:
        """
        从 MAA 配置反向解析回合动作

        Args:
            config_data: MAA 配置字典

        Returns:
            dict: {'actions': round_actions, 'config_info': ConfigInfo}
        """
        round_actions = {}
        from backend.models.schemas import ConfigInfo
        config_info = ConfigInfo()

        # 提取延时信息
        delay_info = config_data.get("抄作业自定义延时", {})
        if delay_info:
            config_info.attack_delay = str(delay_info.get('attack_delay', '3000'))
            config_info.ult_delay = str(delay_info.get('ult_delay', '5000'))
            config_info.defense_delay = str(delay_info.get('defense_delay', '3000'))

        # 提取关卡类型
        restart_node = config_data.get("抄作业点左上角重开", {})
        next_nodes = restart_node.get("next", [])
        if len(next_nodes) >= 2:
            next_node = next_nodes[-1]
            type_map = {
                "抄作业找到关卡-主线": ("主线", None),
                "抄作业进入关卡-洞窟": ("洞窟", "cave_type"),
                "抄作业找到关卡-活动": ("活动", "simple_event"),
                "抄作业找到关卡-活动分级": ("活动有分级", "event"),
                "抄作业进入关卡-白鹄": ("白鹄", None),
                "抄作业找到关卡-兰台": ("兰台", "lantai"),
                "抄作业找到关卡-OCR": ("其他", "ocr"),
            }

            if next_node in type_map:
                level_type, extract_type = type_map[next_node]
                config_info.level_type = level_type

                if extract_type == "cave_type":
                    config_info.cave_type = config_data.get("抄作业进入关卡-洞窟", {}).get("text_doc", "")
                elif extract_type == "simple_event":
                    config_info.level_recognition_name = config_data.get("抄作业找到关卡-活动", {}).get("expected", "")
                    config_info.rec_target_offset = self._get_rec_target_offset(
                        config_data.get("抄作业找到关卡-活动", {})
                    )
                elif extract_type == "event":
                    config_info.level_recognition_name = config_data.get("抄作业找到关卡-活动分级", {}).get("expected", "")
                    config_info.rec_target_offset = self._get_rec_target_offset(
                        config_data.get("抄作业找到关卡-活动分级", {})
                    )
                    config_info.difficulty = config_data.get("抄作业选择活动分级", {}).get("expected", "")
                elif extract_type == "lantai":
                    config_info.level_recognition_name = config_data.get("抄作业找到关卡-兰台", {}).get("level", "")
                elif extract_type == "ocr":
                    config_info.level_recognition_name = config_data.get("抄作业找到关卡-OCR", {}).get("expected", "")
                    config_info.rec_target_offset = self._get_rec_target_offset(
                        config_data.get("抄作业找到关卡-OCR", {})
                    )

        # 解析回合动作
        temp_data = {}

        for key, value in config_data.items():
            if key.startswith("检测回合"):
                round_num = key.replace("检测回合", "")
                temp_data.setdefault(round_num, {'prefix': [], 'actions': []})

                # 兼容旧配置：新配置不再生成该节点，导入时仍忽略它。
                next_list = [n for n in value.get("next", []) if n != "史子眇sp"]
                if not next_list:
                    continue

                first_next = next_list[0]
                if first_next == f"第{round_num}回合橙星检测":
                    temp_data[round_num]['prefix'].append(["重开:无橙星"])
                elif first_next == f"第{round_num}回合紫星检测":
                    temp_data[round_num]['prefix'].append(["重开:无紫星"])
                elif first_next == f"第{round_num}回合蓝星检测":
                    temp_data[round_num]['prefix'].append(["重开:无蓝星"])
                elif first_next == "抄作业点左上角重开":
                    temp_data[round_num]['prefix'].append(["重开:左上角"])
                elif first_next == "抄作业全灭重开":
                    temp_data[round_num]['prefix'].append(["重开:全灭"])

            elif key.startswith('回合') and '行动' in key:
                try:
                    parts = key.split('回合')[1].split('行动')
                    round_num, action_num = parts[0], int(parts[1])
                except (IndexError, ValueError):
                    continue

                temp_data.setdefault(round_num, {'prefix': [], 'actions': []})

                action_code = value.get('text_doc', '')
                if not action_code:
                    continue

                # 还原动作代码
                if action_code.startswith('再动'):
                    action_code = f"额外:{action_code[2:]}"
                elif '阵亡检测' in action_code:
                    action_code = f"重开:检测{action_code[0]}号位阵亡"
                elif '退场检测' in action_code:
                    action_code = f"重开:检测{action_code[0]}号位退场"
                elif '鹦鹉检测' in action_code:
                    action_code = f"重开:检测{action_code[0]}号位鹦鹉"
                elif '龙气检测' in action_code:
                    action_code = f"重开:检测{action_code[0]}号位龙气"
                elif action_code in ['左侧目标', '右侧目标', '吕布', '开自动', '关卡内互动']:
                    action_code = f"额外:{action_code}"
                elif action_code == '额外:史子眇sp':
                    action_code = "额外:史子眇sp"
                elif len(action_code) >= 2 and action_code[0] in '12345' and action_code[1:] == 'sp':
                    # 基础 SP 动作，如 "1sp", "2sp"
                    sp_position = action_code[0]
                    action_code = f"额外:{sp_position}SP"
                elif action_code == '等待':
                    action_code = f"额外:等待:{value.get('post_delay', 0)}"

                temp_data[round_num]['actions'].append((action_num, [action_code]))

                # 检查附加重开指令
                next_actions = value.get('next', [])
                if "抄作业全灭重开" in next_actions:
                    temp_data[round_num]['actions'].append((action_num + 0.5, ["重开:全灭"]))
                elif len(next_actions) == 1 and "抄作业点左上角重开" in next_actions:
                    temp_data[round_num]['actions'].append((action_num + 0.5, ["重开:左上角"]))

        # 组装最终结果
        for round_num in sorted(temp_data.keys(), key=int):
            round_info = temp_data[round_num]
            prefix = round_info['prefix']
            actions = round_info['actions']

            final_list = []
            if actions:
                if prefix and prefix[0] in (["重开:无橙星"], ["重开:无紫星"], ["重开:无蓝星"]):
                    final_list.extend(prefix)

                sorted_actions = [action for _, action in sorted(actions, key=lambda x: x[0])]
                final_list.extend(sorted_actions)
            elif prefix:
                final_list.extend(prefix)

            if final_list:
                round_actions[round_num] = final_list

        return {
            'actions': round_actions,
            'config_info': config_info.model_dump()
        }
