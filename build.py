import os
import shutil
import subprocess

# 清理目录
for dir_name in ['build', 'dist']:
    if os.path.exists(dir_name):
        print(f'正在清理 {dir_name} 目录...')
        shutil.rmtree(dir_name)
        print(f'{dir_name} 目录已清理完成')

# 运行 PyInstaller
print('开始构建...')
subprocess.run(['pyinstaller', 'build.spec'], check=True)
print('构建完成！')