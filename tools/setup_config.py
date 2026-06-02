"""quick_start.bat / setup_gui.ps1 调用的配置生成脚本"""
import sys, os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

wechat_name = sys.argv[1]
api_key = sys.argv[2]

# bot_config
with open("config/example.bot_config.toml", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("你的微信昵称", wechat_name)
c = c.replace("enabled = false", "enabled = true")
# 加上 inner 版本信息
c = '[inner]\nversion = "8.12.24"\n\n' + c
with open("config/bot_config.toml", "w", encoding="utf-8") as f:
    f.write(c)
print("bot_config.toml generated")

# model_config
with open("config/example.model_config.toml", "r", encoding="utf-8") as f:
    c = f.read()
c = c.replace("sk-你的DeepSeekKey", api_key)
c = '[inner]\nversion = "1.17.2"\n\n' + c
with open("config/model_config.toml", "w", encoding="utf-8") as f:
    f.write(c)
print("model_config.toml generated")
