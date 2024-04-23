from cx_Freeze import setup, Executable

# 要打包的 Python 脚本
script = 'main_window.py'


# 打包配置
exe = Executable(
    script,
    base='Win32GUI',  # 设置为 'Win32GUI' 表示创建 GUI 应用程序
    icon='Jlink_ICON.ico',  # 添加图标
)

setup(
    name='XexunRTT',
    version='1.0.4',
    description='a Jlink RTT Viewer app',
    executables=[exe],
    options={
        'build_exe': {
            'include_files': ['JLinkCommandFile.jlink', 'cmd.txt'],  # 需要包含的其他文件（如果有）
            'packages': [],       # 需要包含的其他包（如果有）
            'zip_include_packages':['*'],
            'zip_exclude_packages':[],
        }
    }
)
