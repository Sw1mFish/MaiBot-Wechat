# MaiBot — WeChat AI Bot

An intelligent WeChat assistant powered by large language models, integrated with DeepSeek, supporting image recognition, emoji management, and group chat interaction.

[![Download ZIP](https://img.shields.io/badge/Download-ZIP-green)](https://github.com/Sw1mFish/MaiBot-Wechat/archive/refs/heads/master.zip)

> 📥 **Don't have a GitHub account?** Download the full project as ZIP, extract, and double-click `setup_gui.bat` to start.

---

## Features

- 💬 **Smart Chat** — Powered by DeepSeek LLM, natural conversations
- 🖼️ **Image Recognition** — Understands images and emojis sent in chat
- 👥 **Group Chat** — Auto-replies when @mentioned, learns group chat atmosphere
- 🧠 **Long-term Memory** — Remembers user preferences and chat history
- 🔌 **Plugin System** — Extensible functionality
- For basic features, see the [original MaiBot docs](https://docs.mai-mai.org)

## Requirements

| Requirement | Description |
|-------------|-------------|
| **Windows 10/11** | Windows only |
| **Python 3.12+** | [Download](https://www.python.org/downloads/) |
| **WeChat 3.9.x** | [Download WeChat versions](https://github.com/tom-snow/wechat-windows-versions) |
| **DeepSeek API Key** | [Free registration](https://platform.deepseek.com/) |

## Quick Start

### One-click Setup (Recommended)

Double-click `setup_gui.bat` (graphical interface) or `quick_start.bat`, follow the prompts to enter your API Key and WeChat nickname.

### Manual Setup

**1. Install dependencies**

```cmd
pip install -r requirements.txt
pip install wxauto
```

**2. Get a DeepSeek API Key**

1. Visit [https://platform.deepseek.com](https://platform.deepseek.com)
2. Register → "API Keys" → Create a new Key
3. Copy the Key (starts with `sk-`)

**3. Configure API Key**

Copy `config/example.model_config.toml` to `config/model_config.toml`, then edit:

```toml
[[api_providers]]
name = "DeepSeek"
api_key = "sk-your-key"              # ← Replace with your key
base_url = "https://api.deepseek.com"
```

**4. Configure WeChat nickname**

Copy `config/example.bot_config.toml` to `config/bot_config.toml`, then edit:

```toml
[bot]
platforms = ["wx:your_wechat_name"]  # ← Replace with your WeChat display name
nickname = "your_wechat_name"         # ← Replace with your WeChat display name

[wechat]
enabled = true                        # ← Set to true
```

**5. Start**

Double-click `start.bat`

## First Use

1. Make sure WeChat is logged in and the window is visible (don't minimize to tray)
2. Run `start.bat`
3. Wait for "successfully awakened" message
4. Send a message to "File Transfer" to test

## WebUI Control Panel

MaiBot comes with a web management panel. Visit after starting:

> **URL**: [http://localhost:8001](http://localhost:8001)
> **Login Token**: Printed in the console on startup (`WebUI Token loaded: xxxx...`),
> or check `data/webui.json` for the full token.

Configure the bot, manage emojis, and view logs from your browser.

## WeChat Version Bypass Tool

If your WeChat version is blocked with "version too old" error, use the included patcher:

```cmd
pip install pymem
python tools\wechat_patcher.py
```

**Steps:**
1. Open WeChat, stay on the QR code login screen
2. Run `python tools\wechat_patcher.py`
3. Press Enter to apply the patch
4. Scan QR code with your phone (**don't confirm**) → scan again → confirm login

> ⚠️ The patch modifies memory only, restarting WeChat requires re-application.

## Project Structure

```
MaiBot/
├── bot.py                  # Entry point
├── start.bat               # Start script
├── quick_start.bat         # Setup wizard
├── setup_gui.bat           # GUI setup (double-click friendly)
├── config/                 # Configuration files
│   ├── bot_config.toml     # Bot config
│   └── model_config.toml   # Model config
├── src/                    # Source code
├── plugins/                # Plugin directory
├── data/                   # Data directory (auto-generated)
│   ├── emoji/              # Emoji storage
│   └── images/             # Image cache
└── logs/                   # Logs
```

## Known Limitations

- WeChat window must remain visible (don't minimize to tray)
- Uses display names instead of IDs; changing nicknames may break continuity
- Animated emoji content cannot be viewed (WeChat UI limitation)
- Emojis cannot be automatically saved due to WeChat API limitations

## ❤️ Credits

This project is based on [MaiBot](https://github.com/MaiM-with-u/MaiBot) with added WeChat adapter layer.

- Original: [MaiM-with-u/MaiBot](https://github.com/MaiM-with-u/MaiBot)
- This repo only adds WeChat adaptation and deployment tools; core functionality belongs to the original project.
