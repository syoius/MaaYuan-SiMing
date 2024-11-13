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

def generate_config(input_path, output_path, level_type='', level_recognition_name='', difficulty=''):
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
                "post_delay": 1000,
            }

            # 处理每个回合中的动作
            current_action_key = None
            for i, action_group in enumerate(actions, start=1):
                # 检查是否是额外操作
                if isinstance(action_group, list) and len(action_group) > 0:
                    action = action_group[0]  # 第一个元素是动作
                    
                    if action.startswith('额外:'):
                        extra_action_type = action.split(':')[1]
                        extra_action_key = f"回合{round_num}额外{i}"
                        
                        # 配置额外操作
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
                        # elif extra_action_type == "判断数字":
                        #     result_config[extra_action_key] = {
                        #     }
                        
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

        # 根据关卡类别设置重开后的导航节点
        if level_type == '主线':
            next_node = "抄作业找到关卡-主线"
        elif level_type == '洞窟':
            next_node = "抄作业找到关卡-洞窟"
        elif level_type == '活动有分级':
            next_node = "抄作业找到关卡-活动分级"
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
            result_config["抄作业找到关卡-洞窟"] = {
                "recognition": "OCR",
                "expected": level_recognition_name,  # 使用传入的识别名称
                "roi": [0,249,720,1030],
                "action": "Click",
                "target_offset": [-27, 443, -22, -69],
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
        elif level_type != '主线':  # 非主线且非洞窟的情况
            result_config["抄作业找到关卡-OCR"] = {
                "recognition": "OCR",
                "expected": level_recognition_name,  # 使用传入的识别名称
                "roi": [0,249,720,1030],
                "action": "Click",
                "pre_delay": 2000,
                "next": ["抄作业战斗开始"],
                "timeout": 20000
            }

        # 加载必要动作
        result_config["抄作业全灭重开"] = {
            "recognition": "OCR",
            "expected": "再次挑战",
            "roi": [402, 1099, 218, 59],
            "pre_wait_freezes": 500,
            "post_delay": 2000,
            "action": "Click",
            "next": ["抄作业战斗开始"],
            "timeout": 20000
        }

        result_config["抄作业找到关卡-主线"] = {
            "recognition": "ColorMatch",
            "roi": [98, 527, 519, 43],
            "method": 4,
            "upper": [225, 131, 131],
            "lower": [170, 50, 50],
            "count": 4500,
            "order_by": "Score",
            "connected": True,
            "action": "Click",
            "pre_delay": 2000,
            "next": ["抄作业战斗开始"],
            "timeout": 20000
        }

        # todo 需要根据活动调整
        result_config["抄作业进入关卡"] = {
            "next": ["抄作业进入关卡-首通","抄作业进入关卡-多刷"],
            "timeout": 20000
        }

        result_config["抄作业进入关卡-首通"] = {
            "recognition": "OCR",
            "expected": "挑战",
            "roi" : [253,874,202,77],
            "action": "Click",
            "pre_delay": 1500,
            "next": ["抄作业战斗开始"],
            "timeout": 20000
        }       

        result_config["抄作业进入关卡-多刷"] = {
            "recognition": "OCR",
            "expected": "体验",
            "roi": [82,707,561,470],
            "action": "Click",
            "pre_delay": 1500,
            "next": ["抄作业战斗开始"],
            "timeout": 20000
        }

        result_config["抄作业战斗开始"] = {
            "recognition": "OCR",
            "expected": "开始战斗",
            "roi": [264, 1158, 201, 51],
            "action": "Click",
            "pre_wait_freezes": 500,
            "next": ["抄作业切一下手动","检测回合1"],
            "timeout": 20000
        }

        result_config["抄作业切一下手动"] = {
            "is_sub": True,
            "recognition": "OCR",
            "expected": "自动",
            "roi": [635, 610, 85, 95],
            "action": "Click"
        }

        result_config["抄作业确定左上角重开"] = {
            "is_sub": True,
            "recognition": "OCR",
            "expected": "确定",
            "roi": [434,737,129,61],
            "pre_wait_freezes": 500,
            "post_delay": 2000,
            "action": "Click"
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
        'difficulty': ''
    }

    # 检测关卡类型和识别名称
    restart_node = config_data.get("抄作业点左上角重开", {})
    next_nodes = restart_node.get("next", [])
    
    if len(next_nodes) >= 2:  # 确保有第二个节点
        next_node = next_nodes[1]  # 获取第二个节点
        if next_node == "抄作业找到关卡-主线":
            config_info['level_type'] = '主线'
        elif next_node == "抄作业找到关卡-洞窟":
            config_info['level_type'] = '洞窟'
            config_info['level_recognition_name'] = config_data.get("抄作业找到关卡-洞窟", {}).get("expected", "")
        elif next_node == "抄作业找到关卡-活动分级":
            config_info['level_type'] = '活动有分级'
            config_info['level_recognition_name'] = config_data.get("抄作业找到关卡-活动分级", {}).get("expected", "")
            # 获取难度信息
            config_info['difficulty'] = config_data.get("抄作业选择活动分级", {}).get("expected", "")
        elif next_node == "抄作业找到关卡-OCR":
            config_info['level_type'] = '其他'
            config_info['level_recognition_name'] = config_data.get("抄作业找到关卡-OCR", {}).get("expected", "")

    # 首先按回合号分组处理所有动作
    for key, value in config_data.items():
        # 跳过检测回合配置
        if not key.startswith('回合') or '检测' in key:
            continue

        # 从键名中提取回合号
        # 例如: "回合1行动1" -> round_num = "1"
        round_num = key.split('回合')[1].split('行动')[0]

        # 初始化该回合的动作列表
        if round_num not in round_actions:
            round_actions[round_num] = []

        # 解析普通动作
        action_code = None
        if value.get('action') == 'Click':
            # 从目标坐标判断位置号
            target = value.get('target', [0, 0, 0, 0])
            x = target[0]
            if x < 100:
                position = '1'
            elif x < 250:
                position = '2'
            elif x < 400:
                position = '3'
            elif x < 550:
                position = '4'
            else:
                position = '5'
            action_code = f"{position}普"

        elif value.get('action') == 'Swipe':
            # 从起点坐标判断位置号
            begin = value.get('begin', [0, 0, 0, 0])
            end = value.get('end', [0, 0, 0, 0])
            x = begin[0]
            if x < 100:
                position = '1'
            elif x < 250:
                position = '2'
            elif x < 400:
                position = '3'
            elif x < 550:
                position = '4'
            else:
                position = '5'

            # 通过终点y坐标判断是上拉还是下拉
            if end[1] < begin[1]:
                action_code = f"{position}上"
            else:
                action_code = f"{position}下"

        if action_code:
            action_group = [action_code]
            round_actions[round_num].append(action_group)

            # 检查是否有重开配置，如果有则添加为单独的动作组
            if value.get('next'):
                if "抄作业全灭重开" in value['next']:
                    round_actions[round_num].append(["重开:全灭"])
                elif "抄作业点左上角重开" in value['next']:
                    round_actions[round_num].append(["重开:左上角"])

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

    generate_config(input_path, output_path, level_type, level_recognition_name, difficulty)
