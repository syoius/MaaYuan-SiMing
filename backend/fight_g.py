import json
import os
import sys

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

def generate_config(input_path, output_path, level_type='', level_recognition_name='', difficulty='', cave_type=''):
    """生成配置文件"""
    try:
        # 读取输入配置
        with open(input_path, 'r', encoding='utf-8') as f:
            round_actions = json.load(f)

        if not round_actions:
            raise ValueError("没有找到任何回合动作配置")

        max_round_num = max(int(round_num) for round_num in round_actions.keys())

        # 读取模板文件
        template_path = get_template_path()
        with open(template_path, "r", encoding="utf-8") as f:
            action_templates = json.load(f)

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
            # 修正：重开:无橙星优先走橙星检测分支
            first_action = actions[0][0] if actions and actions[0] else None
            if str(round_num) in rounds_with_orangestar_restart:
                next_list = [f"第{round_num}回合橙星检测"]
            elif first_action and first_action.startswith('重开:'):
                restart_type = first_action.split(':')[1]
                restart_node = f"抄作业{restart_type}重开" if restart_type == "全灭" else f"抄作业点左上角重开"
                next_list = [restart_node]
            else:
                next_list = [f"回合{round_num}行动1"]
            
            result_config[f"检测回合{round_num}"] = {
                "recognition": "OCR",
                "expected": f"{round_num}",
                "roi": [641, 43, 43, 37],
                "text_doc": f"回合{round_num}",
                "model": "en",
                "only_rec": True,
                "focus": f"当前：第{round_num}回合",
                "next": next_list,
                "on_error": ["抄作业点左上角重开"],
                "timeout": 7000,
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
                
                # 处理重开指令 - 不创建新节点，只修改前一个动作的next
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
                if int(round_num) < max_round_num:
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
        else:
            next_node = "抄作业找到关卡-OCR"

        result_config["抄作业点左上角重开"] = {
            "recognition": "TemplateMatch",
            "template": "back.png",
            "green_mask": True,
            "threshold": 0.5,
            "roi" : [6,8,123,112],
            "action": "Click",
            "pre_delay": 2000,
            "post_delay": 2000,
            "next": ["抄作业确定左上角重开", next_node],
            "focus": "正在尝试点左上角重开",
            "timeout": 20000
        }

        result_config["抄作业胜利后继续"] = {
            "focus": "战斗胜利，尝试继续",
            "next": [next_node]
        }

        # 根据关卡类别和识别名称设置对应的导航节点
        if level_type == '洞窟':
            if cave_type == '左':
                result_config["抄作业进入关卡-洞窟"] = {
                    "text_doc": "左",
                    "recognition": "OCR",
                    "expected": "前往",
                    "roi" : [237,810,82,89],
                    "action": "Click",
                    "target": [258,833,42,39],
                    "pre_delay": 1500,
                    "next": ["指定抄作业战斗队伍", "抄作业战斗开始"],
                    "timeout": 20000
                }
            else:
                result_config["抄作业进入关卡-洞窟"] = {
                    "text_doc": "右",
                    "recognition": "OCR",
                    "expected": "前往",
                    "roi" : [558,804,79,89],
                    "action": "Click",
                    "target": [581,832,41,41],
                    "pre_delay": 1500,
                    "next": ["指定抄作业战斗队伍", "抄作业战斗开始"],
                    "timeout": 20000
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


        # 保存输出配置
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_config, f, ensure_ascii=False, indent=4)

        return result_config

    except Exception as e:
        print(f"生成配置失败: {str(e)}")
        raise

def reverse_config(config_data):
    """从生成的配置文件反向生成回合动作配置"""
    round_actions = {}
    config_info = {
        'level_type': '',
        'level_recognition_name': '',
        'difficulty': '',
        'cave_type': ''
    }

    # 1. 提取关卡元信息 (逻辑不变)
    restart_node = config_data.get("抄作业点左上角重开", {})
    next_nodes = restart_node.get("next", [])
    if len(next_nodes) >= 2:
        next_node = next_nodes[1]
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
        elif next_node == "抄作业找到关卡-OCR":
            config_info['level_type'] = '其他'
            config_info['level_recognition_name'] = config_data.get("抄作业找到关卡-OCR", {}).get("expected", "")

    # 2. 创建临时字典，用于存储所有解析到的动作
    # 结构: { "round_num": [(sort_key, action_list), ...], ... }
    # sort_key 用于保证动作顺序正确 (例如 action_num 和 action_num + 0.5)
    temp_actions = {}

    # 3. 第一遍：解析所有实际的“回合X行动Y”节点
    for key, value in config_data.items():
        if not key.startswith('回合') or '检测' in key:
            continue

        parts = key.split('回合')[1].split('行动')
        round_num = parts[0]
        action_num = int(parts[1])

        temp_actions.setdefault(round_num, [])

        action_code = None
        # 根据 value['text_doc'] 或 value['action'] 等信息反推 action_code
        if value.get('text_doc', '').startswith("再动"):
            action_code = value['text_doc'].replace("再动", "额外:")
        elif value.get('text_doc') == "左侧目标":
            action_code = "额外:左侧目标"
        elif value.get('text_doc') == "右侧目标":
            action_code = "额外:右侧目标"
        elif value.get('text_doc') == "等待":
            action_code = f"额外:等待:{value.get('post_delay')}"
        else: # 普通攻击或技能
            position_code = value.get('text_doc', '')[0]
            action_type_code = ''
            if value.get('action') == 'Click':
                action_type_code = '普'
            elif value.get('action') == 'Swipe':
                begin_y = value.get('begin', [0, 0])[1]
                end_y = value.get('end', [0, 0])[1]
                action_type_code = '大' if end_y < begin_y else '下'
            if position_code and action_type_code:
                action_code = f"{position_code}{action_type_code}"

        if action_code:
            temp_actions[round_num].append((action_num, [action_code]))

            # 检查此动作后是否紧跟着重开指令
            next_actions = value.get('next', [])
            if "抄作业全灭重开" in next_actions:
                # 使用小数排序键，确保它紧跟在当前动作之后
                temp_actions[round_num].append((action_num + 0.5, ["重开:全灭"]))
            elif "抄作业点左上角重开" in next_actions:
                temp_actions[round_num].append((action_num + 0.5, ["重开:左上角"]))

    # 4. 第二遍：解析“检测回合”节点，还原“无橙星重开”和“仅重开的回合”
    for key, value in config_data.items():
        if not key.startswith("检测回合"):
            continue

        round_num = key.replace("检测回合", "")
        next_list = value.get("next", [])
        if not next_list:
            continue

        first_next_node = next_list[0]

        # 检查是否是“无橙星重开”逻辑
        if first_next_node == f"第{round_num}回合橙星检测":
            temp_actions.setdefault(round_num, [])
            # 使用-1作为排序键，确保它在最前面
            temp_actions[round_num].append((-1, ["重开:无橙星"]))

        # 检查是否是“仅重开的回合”
        # 条件：该回合在第一遍解析中没有任何动作 (temp_actions.get(round_num) 为空)
        elif not temp_actions.get(round_num):
            if first_next_node == "抄作业点左上角重开":
                temp_actions.setdefault(round_num, [])
                temp_actions[round_num].append((-1, ["重开:左上角"]))
            elif first_next_node == "抄作业全灭重开": # 虽然少见，但逻辑上支持
                temp_actions.setdefault(round_num, [])
                temp_actions[round_num].append((-1, ["重开:全灭"]))

    # 5. 最后，整理 temp_actions 到最终的 round_actions 格式
    for round_num, actions_with_sort_key in sorted(temp_actions.items(), key=lambda item: int(item[0])):
        if not actions_with_sort_key:
            continue

        # 按排序键排序，然后提取出干净的动作列表
        sorted_actions = sorted(actions_with_sort_key, key=lambda x: x[0])
        final_action_list = [action_list for sort_key, action_list in sorted_actions]

        # 去除可能因逻辑重复产生的重复项（例如，无橙星被多次添加）
        unique_actions = []
        for action in final_action_list:
            if action not in unique_actions:
                unique_actions.append(action)

        round_actions[round_num] = unique_actions

    return {
        'actions': round_actions,
        'config_info': config_info
    }

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python fight_g.py input_path output_path [level_type] [level_recognition_name]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    level_type = sys.argv[3] if len(sys.argv) > 3 else ''
    level_recognition_name = sys.argv[4] if len(sys.argv) > 4 else ''
    difficulty = sys.argv[5] if len(sys.argv) > 5 else ''
    cave_type = sys.argv[6] if len(sys.argv) > 6 else ''

    generate_config(input_path, output_path, level_type, level_recognition_name, difficulty, cave_type)