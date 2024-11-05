from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
import sys
import subprocess

app = Flask(__name__)
CORS(app)

def get_data_dir():
    """获取数据目录"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的环境，使用可执行文件所在目录
        base_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境使用当前文件所在目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_dir, 'data')

# 配置文件路径
DATA_DIR = get_data_dir()
CONFIG_FILE = os.path.join(DATA_DIR, 'round_actions.json')

def load_actions():
    """加载动作配置"""
    try:
        # 确保数据目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"加载配置失败: {str(e)}")
        return {}

def save_actions(actions):
    """保存动作配置"""
    try:
        # 确保数据目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(actions, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"保存配置失败: {str(e)}")
        raise

@app.route('/api/actions', methods=['GET'])
def get_actions():
    """获取所有回合动作"""
    return jsonify(load_actions())

@app.route('/api/actions/<round_num>', methods=['GET', 'PUT', 'DELETE'])
def handle_round_actions(round_num):
    """处理单个回合的动作"""
    if int(round_num) > 50:
        return jsonify({'error': '超过50回合限制'}), 400
        
    actions = load_actions()
    print(f"当前操作: {request.method}, 回合: {round_num}")
    
    if request.method == 'GET':
        return jsonify(actions.get(round_num, []))
    
    elif request.method == 'PUT':
        try:
            print(f"收到的数据: {request.json}")
            round_actions = request.json
            if not isinstance(round_actions, list):
                print(f"无效的动作数据类型: {type(round_actions)}")
                return jsonify({'error': '无效的动作数据'}), 400
            actions[round_num] = round_actions
            save_actions(actions)
            print(f"保存回合 {round_num} 成功")
            return jsonify({'status': 'success'})
        except Exception as e:
            print(f"保存回合 {round_num} 失败: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        try:
            if round_num in actions:
                actions[round_num] = []
                save_actions(actions)
                print(f"清空回合 {round_num} 的动作成功")
            return jsonify({'status': 'success'})
        except Exception as e:
            print(f"清空回合 {round_num} 的动作失败: {str(e)}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/actions/generate-loop', methods=['POST'])
def generate_loop():
    """生成循环回合"""
    data = request.json
    start_round = str(data['start'])  # 循环模板的起始回合
    end_round = str(data['end'])      # 循环模板的结束回合
    
    actions = load_actions()
    
    # 验证起始回合和结束回合都存在
    if start_round not in actions or end_round not in actions:
        return jsonify({'error': '起始回合或结束回合未设置'}), 400
    
    # 确保起始回合小于等于结束回合
    if int(start_round) > int(end_round):
        return jsonify({'error': '起始回合不能大于结束回合'}), 400
    
    # 获取模板长度（包含起始和结束回合）
    template_length = int(end_round) - int(start_round) + 1
    
    # 找到当前最大回合数
    max_round = max(map(int, actions.keys())) if actions else 0
    next_start = max_round + 1
    
    # 检查是否超过50回合限制
    if next_start + template_length - 1 > 50:
        return jsonify({'error': '超过50回合限制'}), 400
    
    # 复制模板一次
    for offset in range(template_length):
        src_round = str(int(start_round) + offset)  # 模板中的回合
        target_round = str(next_start + offset)     # 要生成的回合
        
        # 如果模板回合有动作，复制到目标回合
        if src_round in actions:
            actions[target_round] = actions[src_round].copy()
    
    save_actions(actions)
    return jsonify({'status': 'success'})

# 添加一个新的路由来处理新增回合（虽然可以用 PUT 处理，但为了清晰可以单独处理）
@app.route('/api/actions/add/<round_num>', methods=['POST'])
def add_round(round_num):
    """新增回合"""
    try:
        if int(round_num) > 50:
            return jsonify({'error': '超过50回合限制'}), 400
            
        actions = load_actions()
        if round_num not in actions:
            actions[round_num] = []  # 新回合默认为空列表
            save_actions(actions)
            print(f"新增回合 {round_num} 成功")
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"新回合 {round_num} 失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rounds/<round_num>', methods=['DELETE'])
def delete_round(round_num):
    """删除整个回合"""
    try:
        actions = load_actions()
        if round_num in actions:
            del actions[round_num]
            save_actions(actions)
            print(f"删除回合 {round_num} 成功")  # 添加日志
            return jsonify({'status': 'success'})
        return jsonify({'status': 'not_found'}), 404
    except Exception as e:
        print(f"删除回合 {round_num} 失败: {str(e)}")  # 添加错误日志
        return jsonify({'error': str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_config():
    """导出生成的配置文件"""
    try:
        level_name = request.args.get('level_name', 'generated_config')
        
        if getattr(sys, 'frozen', False):
            # 打包环境
            from backend import fight_g
            output_dir = os.path.join(os.path.dirname(sys.executable), 'output')
        else:
            # 开发环境
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fight_g.py')
            output_dir = os.path.join(os.path.dirname(script_path), 'output')
            
        os.makedirs(output_dir, exist_ok=True)
        config_path = os.path.join(output_dir, f'{level_name}.json')
        
        # 首先将当前的动作配置保存到临时文件
        actions = load_actions()
        temp_config_path = os.path.join(DATA_DIR, 'temp_config.json')
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            json.dump(actions, f, ensure_ascii=False, indent=4)
            
        if getattr(sys, 'frozen', False):
            # 打包环境的处理逻辑
            fight_g.generate_config(temp_config_path, config_path)
        else:
            # 开发环境下运行脚本
            python_executable = sys.executable
            result = subprocess.run(
                [python_executable, script_path, temp_config_path, config_path],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(script_path)
            )
            
            if result.returncode != 0:
                print(f"脚本执行失败: {result.stderr}")
                return jsonify({'error': f'生成配置文件失败: {result.stderr}'}), 500
        
        # 检查文件是否生成成功
        if not os.path.exists(config_path):
            return jsonify({'error': '配置文件生成失败'}), 500
            
        # 读取生成的配置文件
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # 清理临时文件
        if os.path.exists(temp_config_path):
            os.remove(temp_config_path)
            
        return jsonify({
            'config': config,
            'path': config_path,
            'message': f'配置文件已生成：{config_path}'
        })
            
    except Exception as e:
        print(f"导出失败: {str(e)}")
        return jsonify({'error': f'导出失败: {str(e)}'}), 500

@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    try:
        path = request.json.get('path')
        folder_path = os.path.dirname(path)
        if os.path.exists(folder_path):
            os.startfile(folder_path)  # Windows
            return jsonify({'message': '已打开文件夹'})
        return jsonify({'error': '文件夹不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/actions/clear', methods=['POST'])
def clear_actions():
    """清空所有配置"""
    try:
        save_actions({})  # 保存空字典来清空配置
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"清空配置失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
