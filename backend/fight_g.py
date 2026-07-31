import json
import os
import sys
import re

def get_data_dir():
    """获取数据目录"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    data_dir = os.path.join(base_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_template_path():
    """获取模板文件路径"""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'backend', 'templates', 'fight_action.json')
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'fight_action.json')

def get_action_focus(action_code):
    """将action code转换为中文描述"""
    if not action_code or len(action_code) < 2:
        return action_code
    pos = action_code[0]
    act = action_code[1]
    pos_map = {
        '1': '1号位',
        '2': '2号位',
        '3': '3号位',
        '4': '4号位',
        '5': '5号位'
    }
    act_map = {
        '普': '普攻',
        '大': '大招',
        '下': '防御'
    }
    return f"{pos_map.get(pos, pos)}{act_map.get(act, act)}"

def parse_detection(text):
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

def apply_custom_delays(action_templates, attack_delay, ult_delay, defense_delay):
    def update_delay(keyword, delay_value):
        if not delay_value:
            return
        try:
            delay = int(delay_value)
        except (TypeError, ValueError):
            return
        for key, value in action_templates.items():
            if key.endswith(keyword) and isinstance(value, dict) and "post_delay" in value:
                value["post_delay"] = delay

    update_delay("普攻", attack_delay)
    update_delay("上拉", ult_delay)
    update_delay("下拉", defense_delay)

def _get_route_key(item):
    """获取路由项的标识键（处理字符串和字典类型的节点属性）"""
    if isinstance(item, dict):
        return item.get('name', str(item))
    return item

def deduplicate_routes(config):
    """去重 next/on_error，避免重复路由"""
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
                    route_key = _get_route_key(item)
                    if route_key not in seen:
                        deduped.append(item)
                        seen.add(route_key)
                routes[key] = deduped
            else:
                routes[key] = value

        taken = set()
        for key in ("next", "on_error"):
            value = routes.get(key)
            if not isinstance(value, list):
                continue
            filtered = []
            for item in value:
                route_key = _get_route_key(item)
                if route_key in taken:
                    continue
                filtered.append(item)
                taken.add(route_key)
            routes[key] = filtered

        for key, value in routes.items():
            if isinstance(value, list):
                node[key] = value
def generate_config(input_path, output_path, level_type='', level_recognition_name='', difficulty='', cave_type='', lantai_nav='true', attack_delay='',ult_delay='',defense_delay=''):
    """生成配置文件"""
    try:
        # 读取输入配置
        with open(input_path, 'r', encoding='utf-8') as f:
            round_actions = json.load(f)

        if not round_actions:
            raise ValueError("没有找到任何回合动作配置")

        max_round_num = max(int(round_num) for round_num in round_actions.keys())

        # 找到最后一个包含实际行动的回合，避免空回合导致的多余检测
        max_round_with_actions = 0
        for rn, acts in round_actions.items():
            if any(isinstance(g, list) and len(g) > 0 for g in acts):
                max_round_with_actions = max(max_round_with_actions, int(rn))

        # 读取模板文件
        template_path = get_template_path()
        with open(template_path, "r", encoding="utf-8") as f:
            action_templates = json.load(f)
        apply_custom_delays(action_templates, attack_delay, ult_delay, defense_delay)

        # 将操作指令转换为行动配置
        def get_action(action_code):
            position = action_code[0]  # 获取位置编号，例如 "1"
            action_type = action_code[1]  # 获取动作类型，例如 "普"
            key = f"{position}号位" + ("普攻" if action_type == "普" else "上拉" if action_type == "大" else "下拉")
            return action_templates.get(key)

        # 新增：为动作的next字段追加内容的子函数
        def append_to_next(node, value):
            if "next" not in node:
                node["next"] = []
            if value not in node["next"]:
                node["next"].append(value)

        # 新增：为动作的next字段设置内容的子函数（会覆盖原有内容）
        def set_next(node, values):
            node["next"] = values if isinstance(values, list) else [values]

        # 1. 先扫描所有回合，找出有"重开:无橙星"的回合
        rounds_with_orangestar_restart = set()
        for round_num, actions in round_actions.items():
            for action_group in actions:
                if isinstance(action_group, list) and len(action_group) > 0:
                    action = action_group[0]
                    if action.startswith('重开:无橙星'):
                        rounds_with_orangestar_restart.add(str(round_num))

        # 生成 JSON 配置
        result_config = {}
        for round_num, actions in round_actions.items():
            round_has_actions = any(
                isinstance(action_group, list) and len(action_group) > 0
                for action_group in actions
            )

            # 如果该回合在最后一个有效回合之后且没有行动，跳过生成
            if int(round_num) > max_round_with_actions and not round_has_actions:
                continue
            # 修正：重开:无橙星优先走橙星检测分支
            first_action = actions[0][0] if actions and actions[0] else None
            if str(round_num) in rounds_with_orangestar_restart:
                next_list = [f"第{round_num}回合橙星检测"]
            elif first_action and ('检测' in first_action):
                next_list = [f"回合{round_num}行动1"]
            elif first_action and first_action.startswith('重开:'):
                restart_type = first_action.split(':')[1]
                restart_node = f"抄作业{restart_type}重开" if restart_type == "全灭" else f"抄作业点左上角重开"
                next_list = [restart_node]
            else:
                next_list = [f"回合{round_num}行动1"]

            result_config[f"检测回合{round_num}"] = {
                "recognition": "Custom",
                "custom_recognition": "PureNum",
                "custom_recognition_param": {
                "roi": [641, 50, 43, 27],
                "expected": f"{round_num}"
                },
                "text_doc": f"回合{round_num}",
                "focus": f"当前：第{round_num}回合",
                "next": next_list,
                "on_error": ["抄作业点左上角重开"],
                "timeout": 3000,
                "post_delay": 2000,
            }

            # 如果需要橙星检测，插入橙星检测节点
            if str(round_num) in rounds_with_orangestar_restart:
                # 修正问题2：橙星检测成功后，应固定跳转到该回合的“行动1”，因为它是第一个被创建的实际动作节点。
                result_config[f"第{round_num}回合橙星检测"] = {
                    "recognition": "ColorMatch",
                    "upper": [255, 255, 120],
                    "lower": [180, 160, 40],
                    "roi": [58, 160, 103, 88],
                    "next": [f"回合{round_num}行动1"], # 固定指向第一个实际行动
                    "text_doc": f"第{round_num}回合橙星检测",
                    "focus": f"第{round_num}回合有橙星"
                }

            current_action_key = None
            action_keys = []

            # 用于跟踪实际创建的动作节点
            actual_action_counter = 1

            for i, action_group in enumerate(actions, start=1):
                if not (isinstance(action_group, list) and len(action_group) > 0):
                    continue
                action = action_group[0]

                # 拦截检测类重开（阵亡/退场/鹦鹉/龙气）
                if '重开:检测' in action:
                    # 视为正常动作
                    action_key = f"回合{round_num}行动{actual_action_counter}"
                    action_keys.append(action_key)

                    det = parse_detection(action)
                    if det is None:
                        raise ValueError(f"无法解析检测动作: {action}")

                    result_config[action_key] = {
                        "text_doc": det["text_doc"],
                        "action": "Custom",
                        "custom_action": det["custom_action"],
                        "custom_action_param": {
                            "node": action_key,
                            "position": det["position"]
                        }
                    }
                    # 提前处理next关系
                    if current_action_key:
                        append_to_next(result_config[current_action_key], action_key)

                    # 更新current_action_key
                    current_action_key = action_key
                    actual_action_counter += 1
                    # 避开常规重开指令的处理
                    continue

                # 处理重开指令 - 不创建新节点，只修改前一个动作的next
                # todo：重开都改为由agent去做pipeline override，框架规范为正常/额外动作
                if action.startswith('重开:'):
                    restart_type = action.split(':')[1]

                    # 修正问题1：重开指令应修改上一个“已创建”的动作节点，即current_action_key
                    if restart_type == "全灭":
                        # 重开:全灭：令上一个非重开动作的next内容变为["抄作业全灭重开","原内容"（如果有的话）]
                        if current_action_key and current_action_key in result_config:
                            original_next = result_config[current_action_key].get("next", [])
                            new_next = ["抄作业全灭重开"]
                            for item in original_next:
                                if item not in new_next:
                                    new_next.append(item)
                            set_next(result_config[current_action_key], new_next)

                    elif restart_type == "左上角":
                        # 重开:左上角：令上一个非重开动作的next内容变为["抄作业点左上角重开"]
                        if current_action_key and current_action_key in result_config:
                            set_next(result_config[current_action_key], ["抄作业点左上角重开"])

                    elif restart_type == "无橙星":
                        # 这个逻辑已在上面的橙星检测节点创建时处理，此处跳过
                        pass
                    else:
                        pass

                    # 重开指令不更新action counter和action keys，继续下一个循环
                    continue

                # 处理正常动作 - 使用实际的动作计数器
                action_key = f"回合{round_num}行动{actual_action_counter}"
                action_keys.append(action_key)

                # 统一处理所有动作类型
                if action.startswith('额外:'):
                    extra_action_type = action.split(':')[1]
                    if extra_action_type == "左侧目标":
                        result_config[action_key] = {
                            "text_doc": "左侧目标",
                            "focus": "切换至左侧目标",
                            "action": "Click",
                            "target": [154, 648, 1, 1],
                            "post_delay": 2000,
                            "duration": 800
                        }
                    elif extra_action_type == "右侧目标":
                        result_config[action_key] = {
                            "text_doc": "右侧目标",
                            "focus": "切换至右侧目标",
                            "action": "Click",
                            "target": [603,413,18,21],
                            "post_delay": 2000,
                            "duration": 800
                        }
                    elif extra_action_type == "等待":
                        wait_time = int(action.split(':')[2])
                        result_config[action_key] = {
                            "text_doc": "等待",
                            "focus": "等待"+str(wait_time)+"ms",
                            "post_delay": wait_time
                        }
                    elif extra_action_type == "开自动":
                        result_config[action_key] = {
                            "text_doc": "开自动",
                            "focus": "开始自动战斗",
                            "recognition": "OCR",
                            "expected": "手",
                            "roi": [635, 610, 85, 95],
                            "action": "Click",
                            "timeout": 1800000
                        }
                    elif extra_action_type == "1SP":
                        result_config[action_key] = {
                            "text_doc": "1号位SP",
                            "focus": "点击1号位SP技能",
                            "action": "Click",
                            "target": [76, 1114, 17, 18],
                            "pre_delay": 500,
                            "post_delay": 3000
                        }
                    elif extra_action_type == "2SP":
                        result_config[action_key] = {
                            "text_doc": "2号位SP",
                            "focus": "点击2号位SP技能",
                            "action": "Click",
                            "target": [214, 1116, 23, 13],
                            "pre_delay": 500,
                            "post_delay": 3000
                        }
                    elif extra_action_type == "3SP":
                        result_config[action_key] = {
                            "text_doc": "3号位SP",
                            "focus": "点击3号位SP技能",
                            "action": "Click",
                            "target": [355, 1118, 17, 10],
                            "pre_delay": 500,
                            "post_delay": 3000
                        }
                    elif extra_action_type == "4SP":
                        result_config[action_key] = {
                            "text_doc": "4号位SP",
                            "focus": "点击4号位SP技能",
                            "action": "Click",
                            "target": [498, 1115, 13, 16],
                            "pre_delay": 500,
                            "post_delay": 3000
                        }
                    elif extra_action_type == "5SP":
                        result_config[action_key] = {
                            "text_doc": "5号位SP",
                            "focus": "点击5号位SP技能",
                            "action": "Click",
                            "target": [634, 1118, 16, 11],
                            "pre_delay": 500,
                            "post_delay": 3000
                        }
                    else:
                        # 解析再次行动的位置和动作类型
                        _, action_code = action.split(':')  # 格式为 "额外:1普"
                        action_config = get_action(action_code)
                        if action_config:
                            result_config[action_key] = action_config.copy()
                        result_config[action_key]["text_doc"] = "再动"+action_code
                        result_config[action_key]["focus"] = "再次行动:"+get_action_focus(action_code)
                else:
                    action_config = get_action(action)
                    if action_config:
                        result_config[action_key] = action_config.copy()
                    result_config[action_key]["text_doc"] = action
                    result_config[action_key]["focus"] = "行动:"+get_action_focus(action)

                # 统一处理next关系
                if current_action_key:
                    append_to_next(result_config[current_action_key], action_key)

                # 更新current_action_key（只有非重开动作才更新）
                current_action_key = action_key
                actual_action_counter += 1  # 只有非重开动作才增加计数器

            # 最后一个动作的next指向胜利或下回合检测
            if current_action_key:
                if int(round_num) < max_round_with_actions:
                    append_to_next(result_config[current_action_key], "抄作业战斗胜利")
                    append_to_next(result_config[current_action_key], f"检测回合{int(round_num)+1}")
                else:
                    append_to_next(result_config[current_action_key], "抄作业战斗胜利")

        # 根据关卡类别设置重开后的导航节点
        if level_type == '主线':
            next_node = "抄作业找到关卡-主线"
        elif level_type == '洞窟':
            next_node = "抄作业进入关卡-洞窟"
        elif level_type == '活动有分级':
            next_node = "抄作业找到关卡-活动分级"
        elif level_type == '白鹄':
            next_node = "抄作业进入关卡-白鹄"
        elif level_type == '兰台':
            next_node = "抄作业找到关卡-兰台"
        else:
            next_node = "抄作业找到关卡-OCR"

        result_config["抄作业点左上角重开"] = {
            "recognition": "TemplateMatch",
            "template": "back.png",
            "green_mask": True,
            "threshold": 0.5,
            "roi" : [6,8,123,112],
            "action": "Click",
            "pre_delay": 500,
            "post_delay": 2000,
            "next": ["抄作业确定左上角重开", "抄作业退出兰台木桩", next_node],
            "focus": "正在尝试点左上角重开",
            "timeout": 20000
        }

        result_config["作业信息"] = {
            "focus": "[color:#D48806]作业信息：由 MaaYuan Share v26.02.09 生成，需 MaaYuan v2.0.0-beta5 以上运行。[/color]"
        }

        result_config["抄作业胜利后继续"] = {
            "focus": "战斗胜利，尝试继续",
            "next": [next_node]
        }

        result_config["抄作业自定义延时"] = {
            "attack_delay": attack_delay,
            "ult_delay": ult_delay,
            "defense_delay": defense_delay
        }

        # 根据关卡类别和识别名称设置对应的导航节点
        if level_type == '洞窟':
            if cave_type == '左':
                result_config["抄作业进入关卡-洞窟"] = {
                    "text_doc": "左",
                    "recognition": "OCR",
                    "expected": "前",
                    "replace": ["煎", "前"],
                    "roi" : [237,810,82,89],
                    "action": "Click",
                    "target": [258,833,42,39],
                    "pre_delay": 1500,
                    "next": ["抄作业准备开始战斗"],
                    "timeout": 20000
                }
            else:
                result_config["抄作业进入关卡-洞窟"] = {
                    "text_doc": "右",
                    "recognition": "OCR",
                    "expected": "前",
                    "replace": ["煎", "前"],
                    "roi" : [558,804,79,89],
                    "action": "Click",
                    "target": [581,832,41,41],
                    "pre_delay": 1500,
                    "next": ["抄作业准备开始战斗"],
                    "timeout": 20000
                }
        elif level_type == '兰台':
            if level_recognition_name in ('诛仙阵', '戮魔阵', '奉诏讨伐'):
                result_config["抄作业找到关卡-兰台"] = {
                    "level": level_recognition_name,
                    "recognition": "OCR",
                    "expected": "切换难度",
                    "replace": [
                      ["難", "难"],
                      ["換", "换"]
                    ],
                    "roi": [535, 1208, 180, 70],
                    "action": "Click",
                    "pre_delay": 500,
                    "target": [430,1197,28,30],
                    "next": ["抄作业准备开始战斗"]
                }
            elif level_recognition_name in ('千军阵', '三才阵', '北风演习'):
                result_config["抄作业找到关卡-兰台"] = {
                    "level": level_recognition_name,
                    "recognition": "OCR",
                    "expected": "切换难度",
                    "replace": [
                      ["難", "难"],
                      ["換", "换"]
                    ],
                    "roi": [535, 1208, 180, 70],
                    "action": "Click",
                    "pre_delay": 500,
                    "target": [244,1195,30,35],
                    "next": ["抄作业准备开始战斗"]
                }
            else:
                result_config["抄作业找到关卡-兰台"] = {
                    "level": level_recognition_name,
                    "recognition": "TemplateMatch",
                    "template": "baihu/lantai.png",
                    "order_by": "Vertical",
                    "roi": [19, 318, 684, 905],
                    "action": "Click",
                    "pre_delay": 500,
                    "post_delay": 500,
                    "next": [
                        "抄作业准备开始战斗",
                        {
                            "name": "抄作业-兰台确认进入关卡",
                            "jump_back": True
                        }
                    ],
                    "timeout": 4000
                }
                result_config["抄作业-兰台确认进入关卡"] = {
                    "recognition": "OCR",
                    "expected": "进入",
                    "replace": ["進", "进"],
                    "roi": [195, 711, 334, 186],
                    "action": "Click",
                    "pre_delay": 500,
                    "next": ["抄作业找到关卡-兰台"]
                }
        elif level_type == '活动有分级':
            result_config["抄作业找到关卡-活动分级"] = {
                "recognition": "OCR",
                "expected": level_recognition_name,  # 使用传入的识别名称
                "roi": [0,249,720,1030],
                "action": "Click",
                "pre_delay": 1500,
                "next": ["抄作业选择活动分级"],
                "timeout": 20000
            }
            result_config["抄作业选择活动分级"] = {
                "recognition": "OCR",
                "expected": difficulty, # 使用传入的难度等级
                "roi": [37,351,647,491], # todo 需要根据活动调整
                "pre_delay": 1500,
                "action": "Click",
                "next": ["抄作业进入关卡"],
                "timeout": 20000
            }
        elif level_type != '主线' and level_type != '白鹄':  # 其他的情况
            result_config["抄作业找到关卡-OCR"] = {
                "recognition": "OCR",
                "expected": level_recognition_name,  # 使用传入的识别名称
                "roi": [0,297,720,1030],
                "action": "Click",
                "pre_delay": 2000,
                "next": ["抄作业进入关卡"],
                "timeout": 20000
            }

        # 路由去重，防止 next/interrupt/on_error 目标重复
        deduplicate_routes(result_config)

        # 为检测节点回填 restore_next：不触发重开时恢复的正常流程
        DETECTION_ACTIONS = ("DownRestart", "RetreatRestart", "BirdRestart", "DragonRestart")
        for node in result_config.values():
            if isinstance(node, dict) and node.get("custom_action") in DETECTION_ACTIONS:
                param = node.get("custom_action_param", {})
                if isinstance(param, dict):
                    param["restore_next"] = list(node.get("next", []))
                    node["custom_action_param"] = param

        # 保存输出配置
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_config, f, ensure_ascii=False, indent=4)

        return result_config

    except Exception as e:
        print(f"生成配置失败: {str(e)}")
        raise

def reverse_config(config_data):
    """
    从生成的配置文件反向生成回合动作配置 (最终版)。
    采用“构建-填充”模式，确保逻辑清晰，覆盖所有边缘情况。
    """
    round_actions = {}
    config_info = {
        'level_type': '',
        'level_recognition_name': '',
        'difficulty': '',
        'cave_type': '',
        'lantai_nav': '',
        'attack_delay': '',
        'ult_delay': '',
        'defense_delay':''
    }

    if config_data.get("抄作业自定义延时",{}):
        delay_info = config_data.get("抄作业自定义延时",{})
        config_info['attack_delay'] = delay_info['attack_delay']
        config_info['ult_delay'] = delay_info['ult_delay']
        config_info['defense_delay'] = delay_info['defense_delay']
    else:
        config_info['attack_delay'] = '3000'
        config_info['ult_delay'] = '5000'
        config_info['defense_delay'] = '3000'

    # 1. 提取关卡元信息 (此部分逻辑正确，保持不变)
    restart_node = config_data.get("抄作业点左上角重开", {})
    next_nodes = restart_node.get("next", [])
    if len(next_nodes) >= 2:
        next_node = next_nodes[-1]
        if next_node == "抄作业找到关卡-主线":
            config_info['level_type'] = '主线'
        elif next_node == "抄作业进入关卡-洞窟":
            config_info['level_type'] = '洞窟'
            config_info['cave_type'] = config_data.get("抄作业进入关卡-洞窟", {}).get("text_doc", "")
        elif next_node == "抄作业找到关卡-活动分级":
            config_info['level_type'] = '活动有分级'
            config_info['level_recognition_name'] = config_data.get("抄作业找到关卡-活动分级", {}).get("expected", "")
            config_info['difficulty'] = config_data.get("抄作业选择活动分级", {}).get("expected", "")
        elif next_node == "抄作业进入关卡-白鹄":
            config_info['level_type'] = '白鹄'
        elif next_node == "抄作业找到关卡-兰台":
            config_info['level_type'] = '兰台'
            config_info['level_recognition_name'] = config_data.get("抄作业找到关卡-兰台", {}).get("level", "")
        elif next_node == "抄作业找到关卡-OCR":
            config_info['level_type'] = '其他'
            config_info['level_recognition_name'] = config_data.get("抄作业找到关卡-OCR", {}).get("expected", "")

    # 2. 构建阶段：扫描所有节点，填充一个临时的、多维度的信息字典
    # 结构: { round_num: {'prefix': [], 'actions': []} }
    temp_data = {}

    # Pass 1: 扫描所有节点，分类填充信息
    for key, value in config_data.items():
        # Case A: 找到回合的起始指令
        if key.startswith("检测回合"):
            round_num = key.replace("检测回合", "")
            temp_data.setdefault(round_num, {'prefix': [], 'actions': []})

            next_list = value.get("next", [])
            if not next_list:
                continue

            first_next = next_list[0]
            if first_next == f"第{round_num}回合橙星检测":
                temp_data[round_num]['prefix'].append(["重开:无橙星"])
            elif first_next == "抄作业点左上角重开":
                temp_data[round_num]['prefix'].append(["重开:左上角"])
            elif first_next == "抄作业全灭重开":
                temp_data[round_num]['prefix'].append(["重开:全灭"])

        # Case B: 找到常规动作
        elif key.startswith('回合') and '行动' in key:
            try:
                parts = key.split('回合')[1].split('行动')
                round_num, action_num = parts[0], int(parts[1])
            except (IndexError, ValueError):
                continue

            temp_data.setdefault(round_num, {'prefix': [], 'actions': []})

            # 从 text_doc 还原动作码，这是最可靠的方式
            action_code = value.get('text_doc', '')
            if not action_code: continue

            # 还原 "额外" 前缀
            if action_code.startswith('再动'):
                action_code = f"额外:{action_code[2:]}"  # 去掉"再动"前缀
            elif '阵亡检测' in action_code:
                action_code = f"重开:检测{action_code[0]}号位阵亡"
            elif '退场检测' in action_code:
                action_code = f"重开:检测{action_code[0]}号位退场"
            elif '鹦鹉检测' in action_code:
                action_code = f"重开:检测{action_code[0]}号位鹦鹉"
            elif '龙气检测' in action_code:
                action_code = f"重开:检测{action_code[0]}号位龙气"
            elif action_code in ['左侧目标', '右侧目标', '开自动']:
                action_code = f"额外:{action_code}"
            elif action_code in ['1号位SP', '2号位SP', '3号位SP', '4号位SP', '5号位SP']:
                sp_position = action_code[0]  # 提取数字
                action_code = f"额外:{sp_position}SP"
            elif action_code == '等待':
                action_code = f"额外:等待:{value.get('post_delay')}"

            # 存储动作及其排序键
            temp_data[round_num]['actions'].append((action_num, [action_code]))

            # 检查并存储附加的重开指令
            next_actions = value.get('next', [])
            if "抄作业全灭重开" in next_actions:
                temp_data[round_num]['actions'].append((action_num + 0.5, ["重开:全灭"]))
            elif len(next_actions) == 1 and "抄作业点左上角重开" in next_actions:
                temp_data[round_num]['actions'].append((action_num + 0.5, ["重开:左上角"]))

    # 3. 组装阶段：根据收集到的信息，生成最终的 round_actions
    sorted_round_nums = sorted(temp_data.keys(), key=int)

    for round_num in sorted_round_nums:
        round_info = temp_data[round_num]
        prefix = round_info['prefix']
        actions = round_info['actions']

        # 关键逻辑判断：
        # 如果一个回合有常规动作(actions不为空)，那么它的前缀只可能是 "无橙星"。
        # 如果它的前缀是 "左上角重开" 或 "全灭重开"，那么它一定没有常规动作。

        final_action_list = []
        if actions: # 如果存在常规动作
            # 只有 "无橙星" 前缀可以和常规动作共存
            if prefix and prefix[0] == ["重开:无橙星"]:
                final_action_list.extend(prefix)

            # 排序并添加常规动作
            sorted_actions = [action for sort_key, action in sorted(actions, key=lambda x: x[0])]
            final_action_list.extend(sorted_actions)

        elif prefix: # 如果没有常规动作，但有前缀
            # 这就是 "仅重开" 的情况
            final_action_list.extend(prefix)

        if final_action_list:
            round_actions[round_num] = final_action_list

    return {
        'actions': round_actions,
        'config_info': config_info
    }

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python fight_g.py input_path output_path [level_type] [level_recognition_name] [difficulty] [cave_type] [lantai_nav] [attack_delay] [ult_delay] [defense_delay]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    level_type = sys.argv[3] if len(sys.argv) > 3 else ''
    level_recognition_name = sys.argv[4] if len(sys.argv) > 4 else ''
    difficulty = sys.argv[5] if len(sys.argv) > 5 else ''
    cave_type = sys.argv[6] if len(sys.argv) > 6 else ''
    lantai_nav = sys.argv[7] if len(sys.argv) > 7 else ''
    attack_delay = sys.argv[8] if len(sys.argv) > 8 else ''
    ult_delay = sys.argv[9] if len(sys.argv) >9 else ''
    defense_delay = sys.argv[10] if len(sys.argv) > 10 else ''

    generate_config(input_path, output_path, level_type, level_recognition_name, difficulty, cave_type, lantai_nav, attack_delay, ult_delay, defense_delay)
