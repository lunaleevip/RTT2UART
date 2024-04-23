echo off
python .\cx_exe.py build
rem nuitka --standalone .\main_window.py --enable-plugin=pyside6 --windows-icon-from-ico=Jlink_ICON.ico --disable-console --output-filename=xexunrtt.exe --company-name=Xexun --product-name=XexunRTT --file-version=1.0.4 --onefile 