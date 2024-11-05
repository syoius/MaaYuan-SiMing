import json
import os
import sys

def get_data_dir():
    """获取数据目录"""
    if getattr(sys, 'frozen', False):
        # 打包环境
        base_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    data_dir = os.path.join(base_dir, 'data')
    print(f"数据目录: {data_dir}")
    return data_dir

def get_template_path():
    """获取模板文件路径"""
    if getattr(sys, 'frozen', False):
        # 打包环境
        return os.path.join(sys._MEIPASS, 'backend', 'templates', 'fight_action.json')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'fight_action.json')

def get_output_dir():
    """获取输出目录"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    output_dir = os.path.join(base_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

# 获取各种路径
DATA_DIR = get_data_dir()
CONFIG_FILE = os.path.join(DATA_DIR, 'round_actions.json')
TEMPLATE_FILE = get_template_path()
output_file = os.path.join(get_output_dir(), 'generated_config.json')

try:
    print(f"正在加载模板文件: {TEMPLATE_FILE}")
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        action_templates = json.load(f)

    print(f"正在加载配置文件: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        round_actions = json.load(f)

    if not round_actions:
        raise ValueError("没有找到任何回合动作配置")

    max_round_num = max(int(round_num) for round_num in round_actions.keys())

    # 将操作指令转换为行动配置
    def get_action(action_code):
        position = action_code[0]  # 获取位置编号，例如 "1"
        action_type = action_code[1]  # 获取动作类型，例如 "普"
        key = f"{position}号位" + ("普攻" if action_type == "普" else "上拉" if action_type == "上" else "下拉")
        return action_templates.get(key)

    # 生成 JSON 配置
    config = {}
    for round_num, actions in round_actions.items():
        # 设置检测回合
        config[f"检测回合{round_num}"] = {
            "recognition": "OCR",
            "expected": f"回合{round_num}",
            "roi": [585, 28, 90, 65],
            "next": [f"回合{round_num}行动1"],
            "post_delay": 1000,
        }   
        
        # 设置每个回合中的行动
        for i, action_code in enumerate(actions, start=1):
            action_config = get_action(action_code)
            if action_config:
                action_key = f"回合{round_num}行动{i}"
                config[action_key] = action_config.copy()
                if i == 5:
                    config[action_key]["on_error"] = [f"检测回合{round_num}"]
                if int(round_num) == max_round_num and i == len(actions):
                    config[action_key]["next"] = []
                else:
                    next_action = f"回合{round_num}行动{i + 1}" if i < len(actions) else f"检测回合{int(round_num)+1}"
                    config[action_key]["next"] = [next_action]

    print(f"正在保存配置到: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

    print("配置文件生成成功")

except Exception as e:
    print(f"生成配置文件时出错: {str(e)}")
    raise

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
            for i, action_code in enumerate(actions, start=1):
                action_config = get_action(action_code)
                if action_config:
                    action_key = f"回合{round_num}行动{i}"
                    result_config[action_key] = action_config.copy()
                    if i == 5:
                        result_config[action_key]["on_error"] = [f"检测回合{round_num}"]
                    if int(round_num) == max_round_num and i == len(actions):
                        result_config[action_key]["next"] = []
                    else:
                        next_action = f"回合{round_num}行动{i + 1}" if i < len(actions) else f"检测回合{int(round_num)+1}"
                        result_config[action_key]["next"] = [next_action]

        # 保存输出配置
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_config, f, ensure_ascii=False, indent=4)

        return result_config

    except Exception as e:
        print(f"生成配置失败: {str(e)}")
        raise

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python fight_g.py input_path output_path")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    generate_config(input_path, output_path)
