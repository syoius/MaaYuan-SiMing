"""
Flask API 路由层
负责 HTTP 请求处理和响应格式化
所有业务逻辑委托给 Service 层
"""
import os
import uuid

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.config import Constants, get_output_dir, get_frontend_dir
from backend.models.schemas import (
    RoundActionsRequest, GenerateLoopRequest,
    ExportRequest, RestartRequest, OpenFolderRequest,
    SuccessResponse, ErrorResponse, ImportResponse
)
from backend.services.action_service import (
    ActionService, ActionServiceError, RoundLimitError
)

# 创建 Flask 应用
app = Flask(__name__)
CORS(app)

# 初始化服务
action_service = ActionService()


# ==================== 错误处理 ====================

def handle_error(message: str, status_code: int = 400) -> tuple:
    """统一错误响应格式"""
    return jsonify(ErrorResponse(error=message).model_dump()), status_code


def handle_success(message: str = None) -> dict:
    """统一成功响应格式"""
    return jsonify(SuccessResponse(message=message).model_dump())


# ==================== 静态文件服务 ====================

@app.route('/')
def serve_index():
    """首页"""
    return send_from_directory(get_frontend_dir(), 'index.html')


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """前端资源"""
    return send_from_directory(os.path.join(get_frontend_dir(), 'assets'), filename)


@app.route('/static/<path:filename>')
def serve_static(filename):
    """静态文件"""
    return send_from_directory(os.path.join(get_frontend_dir(), 'static'), filename)


# ==================== 动作管理 API ====================

@app.route('/api/actions', methods=['GET'])
def get_actions():
    """获取所有回合动作"""
    actions = action_service.get_all_actions()
    return jsonify(actions)


@app.route('/api/actions/<round_num>', methods=['GET', 'PUT', 'DELETE'])
def handle_round_actions(round_num):
    """处理单个回合的动作（获取/保存/清空）"""
    try:
        round_num = int(round_num)
        if round_num > Constants.MAX_ROUNDS:
            return handle_error(f'超过{Constants.MAX_ROUNDS}回合限制', 400)

        if request.method == 'GET':
            actions = action_service.get_round_actions(round_num)
            return jsonify(actions)

        elif request.method == 'PUT':
            try:
                data = RoundActionsRequest(actions=request.json)
                action_service.save_round_actions(round_num, data.actions)
                return handle_success()
            except Exception as e:
                print(f"保存回合 {round_num} 失败: {str(e)}")
                return handle_error(str(e), 400)

        elif request.method == 'DELETE':
            action_service.clear_round(round_num)
            return handle_success()

    except ValueError:
        return handle_error('无效的回合编号', 400)
    except Exception as e:
        print(f"处理回合 {round_num} 失败: {str(e)}")
        return handle_error(str(e), 500)


@app.route('/api/actions/add/<round_num>', methods=['POST'])
def add_round(round_num):
    """新增回合"""
    try:
        round_num = int(round_num)
        if round_num > Constants.MAX_ROUNDS:
            return handle_error(f'超过{Constants.MAX_ROUNDS}回合限制', 400)

        action_service.add_round(round_num)
        return handle_success()

    except RoundLimitError as e:
        return handle_error(str(e), 400)
    except Exception as e:
        print(f"新增回合 {round_num} 失败: {str(e)}")
        return handle_error(str(e), 500)


@app.route('/api/rounds/<round_num>', methods=['DELETE'])
def delete_round(round_num):
    """删除整个回合"""
    try:
        round_num = int(round_num)
        deleted = action_service.delete_round(round_num)

        if deleted:
            return handle_success()
        return handle_error('回合不存在', 404)

    except Exception as e:
        print(f"删除回合 {round_num} 失败: {str(e)}")
        return handle_error(str(e), 500)


@app.route('/api/actions/clear', methods=['POST'])
def clear_actions():
    """清空所有配置"""
    try:
        action_service.clear_all()
        return handle_success()
    except Exception as e:
        print(f"清空配置失败: {str(e)}")
        return handle_error(str(e), 500)


# ==================== 高级功能 API ====================

@app.route('/api/actions/generate-loop', methods=['POST'])
def generate_loop():
    """生成循环回合"""
    try:
        data = GenerateLoopRequest(**request.json)
        action_service.generate_loop(data)
        return handle_success()

    except RoundLimitError as e:
        return handle_error(str(e), 400)
    except ActionServiceError as e:
        return handle_error(str(e), 400)
    except Exception as e:
        print(f"生成循环失败: {str(e)}")
        return handle_error(str(e), 500)


@app.route('/api/actions/restart', methods=['POST'])
def add_restart():
    """添加重开动作"""
    try:
        data = RestartRequest(**request.json)
        action_service.add_restart(data)
        return handle_success()

    except ActionServiceError as e:
        return handle_error(str(e), 400)
    except Exception as e:
        print(f"添加重开失败: {str(e)}")
        return handle_error(str(e), 500)


@app.route('/api/export', methods=['POST'])
def export_config():
    """导出生成的配置文件"""
    try:
        print(f"[DEBUG] 接收到的原始请求: {request.json}")
        data = ExportRequest(**request.json)
        print(f"[DEBUG] ExportRequest解析后 - level_type: '{data.level_type}'")
        result = action_service.export_config(data)

        # 添加唯一ID到文件名
        unique_id = uuid.uuid4().hex[:8]
        output_filename = f"{data.level_name}_{unique_id}.json"

        # 保存到输出目录
        output_dir = get_output_dir()
        config_path = os.path.join(output_dir, output_filename)

        import json
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(result['content'], f, ensure_ascii=False, indent=4)

        # 返回文件内容和原始文件名
        return jsonify({
            'content': json.dumps(result['content'], ensure_ascii=False, indent=4),
            'filename': result['filename']
        })

    except Exception as e:
        print(f"导出失败: {str(e)}")
        return handle_error(f'导出失败: {str(e)}', 500)


@app.route('/api/actions/import', methods=['POST'])
def import_actions():
    """导入配置文件"""
    try:
        if 'file' not in request.files:
            return handle_error('没有上传文件', 400)

        file = request.files['file']
        if file.filename == '':
            return handle_error('没有选择文件', 400)

        import json
        config_data = json.load(file.stream)

        result = action_service.import_config(config_data)

        return jsonify(ImportResponse(
            actions=result['actions'],
            config_info=result['config_info']
        ).model_dump())

    except json.JSONDecodeError:
        return handle_error('无效的 JSON 文件', 400)
    except Exception as e:
        print(f"导入失败: {str(e)}")
        return handle_error(str(e), 500)


@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    """打开文件夹"""
    try:
        data = OpenFolderRequest(**request.json)
        folder_path = os.path.dirname(data.path)

        if os.path.exists(folder_path):
            # Windows
            if os.name == 'nt':
                os.startfile(folder_path)
            # macOS
            elif os.name == 'posix':
                import subprocess
                subprocess.call(['open', folder_path])
            return jsonify({'message': '已打开文件夹'})

        return handle_error('文件夹不存在', 404)

    except Exception as e:
        return handle_error(str(e), 500)


# ==================== 启动入口 ====================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Constants.DEFAULT_PORT)
