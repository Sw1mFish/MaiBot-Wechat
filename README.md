<div align="right">
  [🇨🇳 中文] | [🇬🇧 [English](README_EN.md)]
</div>


# MaiBot 麦麦 — 微信 AI 机器人

[![Download ZIP](https://img.shields.io/badge/Download-ZIP-green)](https://github.com/Sw1mFish/MaiBot-Wechat/archive/refs/heads/master.zip)

基于大语言模型的微信智能助手，接入 DeepSeek，支持图片识别、群聊互动。

## 功能

- 💬 **智能对话** — 接入 DeepSeek 大模型，自然聊天
- 🖼️ **图片识别** — 能看懂发的图片（需免费注册 SiliconFlow）
- 👥 **群聊互动** — 群聊被 @ 时自动回复，会观察学习群聊氛围
- 🧠 **长期记忆** — 记住用户偏好和聊天历史
- 🔌 **插件系统** — 支持功能扩展

> 基本特性可查看[原版 MaiBot 文档](https://docs.mai-mai.org)

## 前置要求

| 需求 | 说明 |
|------|------|
| **Windows 10/11** | 仅限 Windows |
| **Python 3.12+** | [下载地址](https://www.python.org/downloads/) |
| **微信 3.9.x** | [点此下载微信各版本](https://github.com/tom-snow/wechat-windows-versions) |
| **DeepSeek API Key** | [免费注册](https://platform.deepseek.com/) |

## 快速部署

> 📥 **不想注册 GitHub？** 点此直接下载全部文件:
> [MaiBot-Wechat-master.zip](https://github.com/Sw1mFish/MaiBot-Wechat/archive/refs/heads/master.zip)
> 解压后双击 `quick_start.bat` 即可开始部署。


### 方法一：一键部署（推荐）

双击 `quick_start.bat`（或 `setup_gui.bat` 图形界面版），按提示输入 API Key 和微信昵称即可。

或者直接双击 `setup_gui.bat` 使用图形界面。

### 方法二：手动部署

**1. 安装依赖**

```cmd
pip install -r requirements.txt
pip install wxauto
```

**2. 获取 DeepSeek API Key**

1. 打开 [https://platform.deepseek.com](https://platform.deepseek.com)
2. 注册账号 → 进入"API Keys" → 创建新的 Key
3. 复制 Key（以 `sk-` 开头）

**3. 配置 API Key**

编辑 `config/model_config.toml`，找到 `[api_providers]` 下的 `api_key`，填入你的 Key：

```toml
[[api_providers]]
name = "DeepSeek"
api_key = "sk-你的Key"              # ← 改成你的 Key
base_url = "https://api.deepseek.com"
```

**4. 配置微信昵称**

编辑 `config/bot_config.toml`，修改以下字段：

```toml
[bot]
platforms = ["wx:你的微信昵称"]      # ← 改成你的微信显示名
nickname = "你的微信昵称"            # ← 改成你的微信显示名

[wechat]
enabled = true                       # ← 改为 true 启用微信连接
```

**5. 启动**

双击 `start.bat`

## 第一次使用

1. 确保微信已登录，窗口保持打开（不要最小化到托盘）
2. 运行 `start.bat`
3. 看到 `麦麦 已成功唤醒` 说明启动成功
4. 在微信中给"文件传输助手"发消息测试

## 配置说明

所有配置都在 `config/` 目录下：

| 文件 | 用途 |
|------|------|
| `bot_config.toml` | 机器人基础配置（昵称、微信账号、聊天风格等） |
| `model_config.toml` | AI 模型配置（API Key、模型选择等） |

### 常用调整

**修改聊天风格**

编辑 `config/bot_config.toml` 中的：

```toml
[personality]
personality = "你是一个大二女大学生..."
reply_style = "你的风格平淡简短..."
```

**开启图片识别（可选）**

图片识别需要免费注册 [SiliconFlow](https://cloud.siliconflow.cn)，获取 API Key 后在 `config/model_config.toml` 中添加：

```toml
[[api_providers]]
name = "SiliconFlow"
api_key = "你的SiliconFlow Key"
base_url = "https://api.siliconflow.cn/v1"
client_type = "openai"
```

## 项目结构

```
MaiBot/
├── bot.py                  # 入口文件
├── start.bat               # 启动脚本
├── quick_start.bat         # 部署向导
├── config/                 # 配置文件
│   ├── bot_config.toml     # 机器人配置
│   └── model_config.toml   # 模型配置
├── src/                    # 源码
├── plugins/                # 插件目录
├── data/                   # 数据目录（自动生成）
│   ├── emoji/              # 表情包存放
│   └── images/             # 图片缓存
└── logs/                   # 日志
```

## 微信版本绕过工具

如果你的微信版本被提示"版本过低"无法登录，可使用附带的补丁工具临时绕过：

```cmd
pip install pymem
python tools/wechat_patcher.py
```

**使用步骤：**

1. 打开微信，停留在扫码登录界面
2. 运行 `python tools/wechat_patcher.py`
3. 按 Enter 执行补丁
4. 手机扫码（**不要点确认**）→ 再扫一次 → 点确认登录

> ⚠️ 补丁仅临时修改内存，重启微信后需重新执行。仅供学习研究。
> 📥 此文件已包含在主项目 [ZIP 包](https://github.com/Sw1mFish/MaiBot-Wechat/archive/refs/heads/master.zip) 中（`tools/wechat_patcher.py`）
> 作者：B站 [@山山official](https://space.bilibili.com/695805824)


## 已知限制
- 由于微信接口限制，无法主动保存聊天中的表情包


- 需保持微信窗口可见（不要最小化到托盘）
- 使用微信显示名称而非 ID，改名后可能影响会话连续性
- 动画表情无法查看具体内容（微信 UI 限制）

## ❤️ 致谢

本项目基于 [MaiBot](https://github.com/MaiM-with-u/MaiBot) 修改，增加了微信适配层。

- 原项目: [MaiM-with-u/MaiBot](https://github.com/MaiM-with-u/MaiBot)
- 本仓库仅添加微信适配层及部署工具，核心功能归原项目所有
