@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title MaiBot 快速部署向导

cd /d "%~dp0"

echo ============================================
echo   MaiBot - 微信 AI 机器人 快速部署
echo ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.12+
    pause
    exit /b 1
)

echo [1/4] 安装依赖...
python -m pip install -r requirements.txt -q
python -m pip install wxauto -q
echo       OK
echo.

:ask_key
echo --------------------------------------------
echo  配置 AI 模型 (DeepSeek)
echo --------------------------------------------
echo 1. 打开 https://platform.deepseek.com 注册
echo 2. 进入 API Keys - 创建新 Key
echo.
set /p DEEPSEEK_KEY=DeepSeek API Key (sk-...):
if "%DEEPSEEK_KEY%"=="" goto ask_key
echo.

:ask_name
echo --------------------------------------------
echo  配置微信账号
echo --------------------------------------------
echo 请输入你的微信显示名称（微信窗口顶部的名字）
echo.
set /p WECHAT_NAME=微信昵称:
if "%WECHAT_NAME%"=="" goto ask_name
echo.

echo [2/4] 生成配置文件...
python tools/setup_config.py "%WECHAT_NAME%" "%DEEPSEEK_KEY%"
echo       OK
echo.

echo [3/4] 创建数据目录...
if not exist data\emoji mkdir data\emoji
if not exist data\images mkdir data\images
echo       OK
echo.

echo [4/4] 部署完成!
echo ============================================
echo.
echo  下一步：
echo  1. 确认微信已登录（窗口保持打开）
echo  2. 双击 start.bat 启动
echo  3. 给文件传输助手发消息测试
echo.
echo  配置摘要:
echo     API Key:      %DEEPSEEK_KEY:~0,10%...
echo     微信昵称:     %WECHAT_NAME%
echo     微信连接:     已启用
echo.
echo  如需修改配置，编辑 config/ 目录下的 toml 文件
echo  或重新运行此向导
echo ============================================
echo.
pause
