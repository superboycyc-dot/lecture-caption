<p align="center"><img src="assets/AppIcon.png" width="128" alt="Lecture Caption 图标"></p>
<h1 align="center">Lecture Caption</h1>
<p align="center">听懂每一句，记住每个关键点。<br>macOS 双语课堂字幕与实时 Markdown 笔记</p>

[English](README.md) · 简体中文 · [使用指南](docs/USER_GUIDE.zh-CN.md)

面向英语 CS / 数学课的免费开源 Mac 应用。麦克风收听教室，电脑音频接入线上会议或视频；英文与中文浮窗同步显示，独立笔记窗口定时提炼定义、前提、推导与算法思路。Mac 只负责收音和界面，模型运行在你选择的 API 服务。

[![CI](https://github.com/superboycyc-dot/lecture-caption/actions/workflows/ci.yml/badge.svg)](https://github.com/superboycyc-dot/lecture-caption/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/superboycyc-dot/lecture-caption)](https://github.com/superboycyc-dot/lecture-caption/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 下载与开始

1. 在本仓库 **Releases** 下载 `macOS-arm64.zip`。
2. 解压，把 **Lecture Caption.app** 拖入“应用程序”。应用内置运行环境，不需要终端或单独安装 Python。
3. 当前版本为本地签名、尚未 Apple 公证；如系统阻止打开，核对来源和校验和后，在“系统设置 → 隐私与安全性”使用系统提供的打开流程。
4. 在 [Groq API Keys](https://console.groq.com/keys) 注册并创建自己的 key。
5. 粘贴到应用，点“测试 API”。默认验证成功后保存到 macOS 钥匙串，下次自动读取。
6. 选麦克风或电脑内部音频，点“开始收音”，按 macOS 提示授权。

![蓝白控制面板](docs/controls-blue.png)

## 当前功能

- 源语言默认英语，翻译为简体中文。
- 字幕与笔记窗口可独立 Pin 置顶、调整不透明度30%–100%。
- 字幕默认最多8秒一段，加上网络/推理延迟；不是逐字同传。
- 笔记约每45秒整理，支持手动立即整理，保存为 Markdown。
- 可填课程术语，提示模型保留英文术语、不确定符号标【待核对】。
- 使用钥匙串加密保存 key；不写入普通配置、日志或命令参数。
- 不保存原始录音，原文和翻译作为事件保存在 `transcript.jsonl`。
- 接口落后时丢弃过时音频并标记缺失，避免字幕延迟无限积累。
- 自定义兼容接口可用于后续家用服务器；当前不是香橙派部署工具。

## 限制与费用

应用免费，**第三方 API 有自己的额度、规则与计费**。建议先用 Groq Free Plan，查看自己的 Limits；不能保证无限时长、无限请求或付费账号绝不产生费用。默认不会自动切换到其他付费服务。

数学识别和整理可能出错。老师没有念出的板书、符号和图示不能从音频还原。内置预览不排版 LaTeX，可用 Typora / Obsidian 等打开笔记。暂停会停止上传，丢弃尚未识别的音频并标记；保留最后一句时，等字幕出现再暂停。

早期版本 `v0.3.0` 支持 Apple Silicon、macOS 14+。用户已在 M5 上确认原始管线能生成英文、中文和笔记；长课时、不同设备及会议软件仍需更多测试。蓝白界面为 Qt 定制主题与半透明效果，不是原生 Liquid Glass 控件。

笔记与日志位于 `~/Library/Application Support/Lecture Caption/`；笔记窗口可直接打开文件夹。音频与转写会发送至你配置的 API，详见 [隐私说明](docs/PRIVACY.md)。

开发、测试、构建及许可证见 [英文 README](README.md)。欢迎通过 Issues 提交可复现问题；不要上传密钥或私人课堂录音。
