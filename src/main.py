import sys
import os

from flask import send_from_directory
import webview
from threading import Thread

def get_backend_path():
    """获取后端模块路径"""
    if getattr(sys, 'frozen', False):
        # 打包环境
        return os.path.join(sys._MEIPASS, 'backend')
    else:
        # 开发环境
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 添加后端模块路径
sys.path.append(get_backend_path())

# 导入后端应用
from backend.app import app

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)

@app.route('/')
def serve_index():
    return send_from_directory(resource_path('frontend'), 'index.html')

def run_server():
    app.run(port=5000)

def create_window():
    # 启动 Flask 服务
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

    # 创建窗口
    webview.create_window(
        'MAA鸢/司命 - 勘天篆命',
        'http://127.0.0.1:5000',
        width=800,
        height=600,
        resizable=True,
        min_size=(1600, 900)
    )
    webview.start()

if __name__ == '__main__':
    # 设置工作目录
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))

    create_window()