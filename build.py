import os
import shutil
import subprocess
import sys

# 清理目录
for dir_name in ['build', 'dist']:
    if os.path.exists(dir_name):
        print(f'正在清理 {dir_name} 目录...')
        shutil.rmtree(dir_name)
        print(f'{dir_name} 目录已清理完成')

# 获取 PyInstaller 可执行文件的完整路径
pyinstaller_path = os.path.join(sys.prefix, 'Scripts', 'pyinstaller.exe')

# 运行 PyInstaller
print('开始构建...')
try:
    subprocess.run([pyinstaller_path, 'build.spec'], check=True)
    print('构建完成！')
except subprocess.CalledProcessError as e:
    print(f'构建失败: {e}')
    sys.exit(1) 