"""生成发给同事的安装包：exe + 使用说明 + 一键安装脚本 → zip"""
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST = HERE / "dist"
PKG = DIST / "番茄桌宠_v1.0"
EXE = DIST / "PomodoroPet.exe"

README = """番茄桌宠  使用说明
==================================================

一个桌面番茄钟：屏幕右下角放一颗小番茄，专注 25 分钟、休息 5 分钟。
到点它跳三下、响三声、弹一张提醒卡片，不点就不消失。


一、怎么装
--------------------------------------------------
方法 A（最简单）
  1. 把 PomodoroPet.exe 复制到桌面（或者任何你找得到的地方）
  2. 双击运行
     第一次 Windows 可能弹一个蓝色的框说"Windows 已保护你的电脑"，
     点「更多信息」→「仍要运行」就行（这是没买数字签名的程序都会遇到的）
  3. 屏幕右下角出现一颗小番茄，装好了

方法 B（装到本机，桌面留个图标）
  1. 双击「安装到本机.bat」
  2. 按提示按回车
  3. 桌面会多一个「番茄桌宠」图标，以后双击它启动


二、怎么用
--------------------------------------------------
  双击番茄         展开面板：今日番茄数、专注时长、改时长
  拖动番茄         换位置（会记住。接了两块屏幕可以拖到另一块）
  右键番茄         开始 / 重置 / 展开 / 退出
  右键右下角小图标   同上
  到点             番茄跳三下 + 三声提示音 + 右下角弹提醒卡片

  提醒卡片右上角是「提醒发出的时刻」，下面一行实时显示
  「现在几点 · 已经过了多久」，超过 5 分钟会变成橙色。
  你走开回来一眼就知道自己错过了多长时间。

  结束后是停住的，不会自己跳下一轮，等你点按钮才开始。


三、电脑重启后不会自己出现
--------------------------------------------------
  想开机自动有：按 Win+R，输入  shell:startup  回车，
  把「番茄桌宠」的快捷方式复制进那个文件夹就行。


四、设置和统计存在哪
--------------------------------------------------
  C:\\Users\\<你的用户名>\\AppData\\Roaming\\PomodoroPet\\pomodoro_state.json
  删掉这个文件 = 恢复默认设置 + 清空统计。
  换电脑想带走记录，把这个文件复制过去就行。


五、怎么卸载
--------------------------------------------------
  1. 右键托盘里的小番茄 → 退出
  2. 删掉安装目录（默认是 %LOCALAPPDATA%\\Programs\\PomodoroPet）
     没安装过就删掉那个 exe
  3. 删掉上面的 PomodoroPet 文件夹
  完成。它不写注册表，不需要卸载程序。


六、双击没反应 / 被杀毒软件拦了
--------------------------------------------------
  1. 360、火绒、Defender 偶尔会把这种"单文件程序"当成可疑。
     选择「允许」「信任」「加入白名单」即可，它不联网、不读你的文件。
  2. 双击后右下角没看到番茄：检查右下角托盘区（可能被折叠进 ^ 箭头里），
     或者在屏幕右下角找找（拖到边缘会自己贴住）。
  3. 已经开着一个时再双击，第二个会安静退出，不会开两个。
  4. 还不行：把 %APPDATA%\\PomodoroPet\\pomodoro_error.log 发给我。
"""

BAT = r"""@echo off
chcp 936 >nul
title 番茄桌宠 安装
set "TARGET=%LOCALAPPDATA%\Programs\PomodoroPet"
cls
echo.
echo    番茄桌宠  安装程序
echo    ----------------------------------------
echo.
echo    会安装到：
echo    %TARGET%
echo.
echo    并在桌面创建一个「番茄桌宠」图标。
echo.
pause
echo.
if not exist "%TARGET%" mkdir "%TARGET%"
if not exist "%~dp0PomodoroPet.exe" goto NOFILE
copy /y "%~dp0PomodoroPet.exe" "%TARGET%\PomodoroPet.exe" >nul
if not exist "%TARGET%\PomodoroPet.exe" goto FAIL
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $exe=Join-Path $env:LOCALAPPDATA 'Programs\PomodoroPet\PomodoroPet.exe'; $lnk=$ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) '番茄桌宠.lnk')); $lnk.TargetPath=$exe; $lnk.IconLocation=$exe+',0'; $lnk.WorkingDirectory=(Split-Path $exe); $lnk.Save()"
echo    装好了！桌面应该多了「番茄桌宠」图标。
echo    现在启动一次，看看右下角有没有出现小番茄...
start "" "%TARGET%\PomodoroPet.exe"
ping -n 6 127.0.0.1 >nul
echo.
echo    如果右下角出现了小番茄，就成功了。
echo    以后双击桌面图标启动，或者把它拖到任务栏。
echo.
pause
exit /b 0

:NOFILE
echo    安装失败：这个文件夹里没找到 PomodoroPet.exe
echo    请把压缩包完整解压后再运行本文件（不要在压缩包里直接双击）。
echo.
pause
exit /b 1

:FAIL
echo    安装失败：复制文件出错，可能是磁盘或权限问题。
echo.
pause
exit /b 1
"""

if not EXE.exists():
    raise SystemExit("先打包 exe：dist/PomodoroPet.exe 不存在")

if PKG.exists():
    shutil.rmtree(PKG)
PKG.mkdir(parents=True)

shutil.copy2(EXE, PKG / "PomodoroPet.exe")
(PKG / "使用说明.txt").write_text(README, encoding="utf-8-sig")
(PKG / "安装到本机.bat").write_text(BAT, encoding="gbk", newline="\r\n")

zip_path = DIST / "番茄桌宠_v1.0.zip"
if zip_path.exists():
    zip_path.unlink()
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in sorted(PKG.iterdir()):
        z.write(f, arcname=f"番茄桌宠_v1.0/{f.name}")

print("安装包:", zip_path, f"{zip_path.stat().st_size/1048576:.1f} MB")
print("目录:")
for f in sorted(PKG.iterdir()):
    print(f"  {f.name}  ({f.stat().st_size/1048576:.1f} MB)")
