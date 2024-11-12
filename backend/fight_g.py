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

def generate_config(input_path, output_path):
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
            key = f"{position}号位" + ("普攻" if action_type == "普" else "上拉" if action_type == "上" else "下拉")
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

            # 设置每个回合中的行动
            for i, action_group in enumerate(actions, start=1):
                action = action_group[0]  # 第一个元素是动作
                action_config = get_action(action)
                if action_config:
                    action_key = f"回合{round_num}行动{i}"
                    result_config[action_key] = action_config.copy()

                    # 检查是否有重开设置
                    restart_type = None
                    if len(action_group) > 1 and action_group[1].startswith("重:"):
                        restart_type = action_group[1].split(":")[1]

                    # 设置next
                    if int(round_num) == max_round_num and i == len(actions):
                        result_config[action_key]["next"] = []
                        if restart_type:
                            restart_node = f"抄作业{restart_type}重开" if restart_type == "全灭" else f"抄作业点左上角重开"
                            result_config[action_key]["next"].append(restart_node)
                    else:
                        next_action = f"回合{round_num}行动{i + 1}" if i < len(actions) else f"检测回合{int(round_num)+1}"
                        result_config[action_key]["next"] = []
                        if restart_type:
                            restart_node = f"抄作业{restart_type}重开" if restart_type == "全灭" else f"抄作业点左上角重开"
                            result_config[action_key]["next"].append(restart_node)
                        result_config[action_key]["next"].append(next_action)

                    # 设置错误处理
                    if i == 9:
                        result_config[action_key]["on_error"] = [f"检测回合{round_num}"]

        # 加载必要动作
        result_config["抄作业全灭重开"] = {
            "recognition": "OCR",
            "expected": "再次挑战",
            "roi": [402, 1099, 218, 59],
            "pre_wait_freezes": 500,
            "post_delay": 2000,
            "action": "Click",
            "next": ["抄作业战斗开始"]
        }

        result_config["抄作业点左上角重开"] = {
            "action": "Click",
            "target": [34, 21, 41, 41],
            "pre_delay": 2000,
            "post_delay": 2000,
            "next": ["抄作业确定左上角重开"]
        }

        result_config["抄作业确定左上角重开"] = {
            "recognition": "OCR",
            "expected": "确定",
            "roi": [434,737,129,61],
            "pre_wait_freezes": 500,
            "post_delay": 2000,
            "action": "Click"
        }

        result_config["抄作业战斗开始"] = {
            "recognition": "OCR",
            "expected": "开始战斗",
            "roi": [264, 1158, 201, 51],
            "action": "Click",
            "pre_wait_freezes": 500,
            "next": ["检测回合1"]
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
            
            # 检查是否有重开配置
            if value.get('next'):
                if "抄作业全灭重开" in value['next']:
                    action_group.append("重:全灭")
                elif "抄作业点左上角重开" in value['next']:
                    action_group.append("重:左上角")
            
            round_actions[round_num].append(action_group)
    
    return round_actions

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python fight_g.py input_path output_path")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    generate_config(input_path, output_path)
