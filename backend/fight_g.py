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

        # 生成 JSON 配置
        result_config = {}
        for round_num, actions in round_actions.items():
            # 设置检测回合
            result_config[f"检测回合{round_num}"] = {
                "recognition": "OCR",
                "expected": f"回合{round_num}",
                "roi": [585, 28, 90, 65],
                "next": [f"回合{round_num}行动1"],
                "post_delay": 2000,
            }

            # 处理每个回合中的动作
            current_action_key = None
            for i, action_group in enumerate(actions, start=1):
                # 检查是否是额外操作
                if isinstance(action_group, list) and len(action_group) > 0:
                    action = action_group[0]  # 第一个元素是动作

                    if action.startswith('额外:'):
                        extra_action_type = action.split(':')[1]
                        extra_action_key = f"回合{round_num}行动{i}"
                        if extra_action_type == "左侧目标":
                            result_config[extra_action_key] = {
                                "action": "Swipe",
                                "begin": [207, 745, 1, 1],
                                "end": [406, 745, 1, 1],
                                "post_delay": 2000,
                                "duration": 800
                            }
                        elif extra_action_type == "右侧目标":
                            result_config[extra_action_key] = {
                                "action": "Swipe",
                                "begin": [406, 745, 1, 1],
                                "end": [207, 745, 1, 1],
                                "post_delay": 2000,
                                "duration": 800
                            }
                        elif extra_action_type == "等待":
                            wait_time = int(action.split(':')[2])
                            result_config[extra_action_key] = {
                                "text_doc": "等待",
                                "post_delay": wait_time
                            }
                        # elif extra_action_type == "判断数字":
                        #     result_config[extra_action_key] = {
                        #     }
                        else:
                            # 解析再次行动的位置和动作类型
                            _, action_code = action.split(':')  # 格式为 "额外:1普"
                            action_config = get_action(action_code)
                            if action_config:
                                result_config[extra_action_key] = action_config.copy()
                            result_config[extra_action_key]["text_doc"] = "再动"


                        # 设置前一个动作的next为当前额外操作
                        if current_action_key:
                            result_config[current_action_key]["next"] = [extra_action_key]

                        current_action_key = extra_action_key
                    elif action.startswith('重开:'):
                        # 处理重开操作
                        restart_type = action.split(':')[1]
                        restart_node = f"抄作业{restart_type}重开" if restart_type == "全灭" else f"抄作业点左上角重开"
                        if current_action_key:
                            result_config[current_action_key]["next"] = [restart_node]
                            if i < len(actions):
                                result_config[current_action_key]["next"].append(f"回合{round_num}行动{i + 1}")
                            elif int(round_num) < max_round_num:
                                result_config[current_action_key]["next"].append(f"检测回合{int(round_num)+1}")
                    else:
                        # 处理普通动作
                        action_config = get_action(action)
                        if action_config:
                            action_key = f"回合{round_num}行动{i}"
                            result_config[action_key] = action_config.copy()

                            if current_action_key:
                                result_config[current_action_key]["next"] = [action_key]

                            current_action_key = action_key

                            # 如果是当前回合的最后一个动作，设置next指向下一回合
                            if i == len(actions) and int(round_num) < max_round_num:
                                result_config[action_key]["next"] = [f"检测回合{int(round_num)+1}"]

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
            "timeout": 20000
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
                    "next": ["抄作业战斗开始"],
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
                    "next": ["抄作业战斗开始"],
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
                "roi": [0,249,720,1030],
                "action": "Click",
                "pre_delay": 2000,
                "next": ["抄作业战斗开始"],
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

    # 检测关卡类型和识别名称
    restart_node = config_data.get("抄作业点左上角重开", {})
    next_nodes = restart_node.get("next", [])

    if len(next_nodes) >= 2:  # 确保有第二个节点
        next_node = next_nodes[1]  # 获取第二个节点
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

    # 创建一个临时字典来存储每个回合的动作
    temp_actions = {}

    # 首先按回合号分组处理所有动作
    for key, value in config_data.items():
        # 跳过检测回合配置和其他非动作配置
        if not key.startswith('回合') or '检测' in key:
            continue

        # 从键名中提取回合号和动作序号
        parts = key.split('回合')[1].split('行动')
        round_num = parts[0]  # 基础回合号（如 "2" 或 "2额外2"）
        action_num = int(parts[1]) if len(parts) > 1 else 0

        # 确保回合存在于临时字典中
        if round_num not in temp_actions:
            temp_actions[round_num] = []

        # 解析动作类型
        action_code = None
        # 检查是否是额外操作
        if value.get('text_doc') == "再动":
            # 处理再次行动
            target = value.get('target', [0, 0, 0, 0])
            x = target[0]
            position = '1' if x < 100 else '2' if x < 250 else '3' if x < 400 else '4' if x < 550 else '5'
            # 根据动作类型判断是普攻、大招还是下拉
            if value.get('action') == 'Click':
                action_type = '普'
            else:  # Swipe action
                end_y = value.get('end', [0, 0, 0, 0])[1]
                begin_y = value.get('begin', [0, 0, 0, 0])[1]
                action_type = '大' if end_y < begin_y else '下'
            action_code = f"额外:{position}{action_type}"
        elif value.get('text_doc') == "等待":
            action_code = f"额外:等待:{value.get('post_delay')}"
        elif value.get('action') == 'Swipe':
            begin = value.get('begin', [0, 0, 0, 0])
            end = value.get('end', [0, 0, 0, 0])
            # 检查是否是目标切换操作
            if begin[0] == 207 and end[0] == 406:  # 左侧目标
                action_code = "额外:左侧目标"
            elif begin[0] == 406 and end[0] == 207:  # 右侧目标
                action_code = "额外:右侧目标"
            # 检查是否是大招或下拉
            if value.get('action') == 'Swipe':
                end_y = value.get('end', [0, 0, 0, 0])[1]
                begin_y = value.get('begin', [0, 0, 0, 0])[1]
                action_type = '大' if end_y < begin_y else '下'
                x = value.get('begin', [0, 0, 0, 0])[0]
                position = '1' if x < 100 else '2' if x < 250 else '3' if x < 400 else '4' if x < 550 else '5'
                action_code = f"{position}{action_type}"
        elif value.get('action') == 'Click':
            # 从目标坐标判断位置号
            target = value.get('target', [0, 0, 0, 0])
            x = target[0]
            position = '1' if x < 100 else '2' if x < 250 else '3' if x < 400 else '4' if x < 550 else '5'
            action_code = f"{position}普"

        # 检查下一个动作是否是重开
        if action_code:
            # 将动作和序号一起存储
            temp_actions[round_num].append((action_num, [action_code]))

            # 检查是否有重开配置
            next_actions = value.get('next', [])
            if next_actions:
                if "抄作业全灭重开" in next_actions:
                    temp_actions[round_num].append((action_num + 0.5, ["重开:全灭"]))
                elif "抄作业点左上角重开" in next_actions:
                    temp_actions[round_num].append((action_num + 0.5, ["重开:左上角"]))

    # 处理临时动作列表，按序号排序并合并到最终结果
    for round_num, actions in temp_actions.items():
        # 提取基础回合号（去掉可能的"额外"标记）
        base_round = round_num.split('额外')[0]
        if base_round not in round_actions:
            round_actions[base_round] = []
        # 按动作序号排序并添加到结果中
        sorted_actions = sorted(actions, key=lambda x: x[0])
        for _, action in sorted_actions:
            round_actions[base_round].append(action)

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
