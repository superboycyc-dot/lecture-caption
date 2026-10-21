<p align="center"><img src="assets/AppIcon.png" width="128" alt="Lecture Caption 图标"></p>
<h1 align="center">Lecture Caption</h1>
<p align="center">听懂每一句，记住每个关键点。<br>macOS 双语课堂字幕与实时 Markdown 笔记</p>

[English](README.md) · 简体中文 · [使用指南](docs/USER_GUIDE.zh-CN.md)

面向英语 CS / 数学课的免费开源 Mac 应用。麦克风收听教室，电脑音频接入线上会议或视频；一个窗口左侧整理笔记、右侧保留双语翻译历史。可选择 Apple 本地识别和翻译，或继续使用 Groq；逻辑笔记由 Groq 整理。

[![CI](https://github.com/superboycyc-dot/lecture-caption/actions/workflows/ci.yml/badge.svg)](https://github.com/superboycyc-dot/lecture-caption/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/superboycyc-dot/lecture-caption)](https://github.com/superboycyc-dot/lecture-caption/releases/latest) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 下载与开始

1. 在本仓库 **Releases** 下载 `macOS-arm64.zip`。
2. 解压，把 **Lecture Caption.app** 拖入“应用程序”。应用内置运行环境，不需要终端或单独安装 Python。
3. 当前版本为本地签名、尚未 Apple 公证；如系统阻止打开，核对来源和校验和后，在“系统设置 → 隐私与安全性”使用系统提供的打开流程。
4. 在 [Groq API Keys](https://console.groq.com/keys) 注册并创建自己的 key。
5. 打开“设置”，粘贴 key，点“测试 API”。默认验证成功后保存到 macOS 钥匙串，下次自动读取。
6. 选麦克风或电脑内部音频，点“开始收音”，按 macOS 提示授权。

![蓝白控制面板](docs/workspace-blue.png)

## 当前功能

- 源语言默认英语，翻译为简体中文。
- 单窗口左右分栏，可拖动分隔线；主窗口支持 Pin 置顶与30%–100%不透明度。
- 翻译保留历史、当前句高亮、平滑跟随；上翻阅读后点击“回到最新”继续跟随。界面保留最近300段，完整原文/翻译保存在本机。
- 开始、停止、输入来源、音量条与本机语音 API 用量直接显示在主界面。
- 设置按需弹出；字号、后端、置顶与透明度等偏好自动保存。
- 可选 Apple 本地英文识别（实验）与英中翻译（macOS 15+），不自动回退到云端。
- 字幕默认最多8秒一段，加上网络/推理延迟；不是逐字同传。
- 笔记约每45秒整理，支持手动立即整理，保存为 Markdown。
- 可填课程术语，提示模型保留英文术语、不确定符号标【待核对】。
- 使用钥匙串加密保存 key；不写入普通配置、日志或命令参数。
- 不保存原始录音，原文和翻译作为事件保存在 `transcript.jsonl`。
- 接口落后时丢弃过时音频并标记缺失，避免字幕延迟无限积累。
- 自定义兼容接口可用于后续家用服务器；当前不是香橙派部署工具。

## Apple 本地模式

在“设置”里将语音识别和翻译方式都选为 Apple，点击“准备 Apple 英中翻译语言包”，在系统弹窗中完成下载。首次识别需允许语音识别权限；缺少英文资源时，请在 macOS 键盘设置中开启英文听写并完成下载。

关闭“自动整理并保存 Markdown 笔记”后，本地双语字幕不需要 key。开启笔记仍需要 Groq key，且原文会发往 Groq。本地识别大约2–3秒分段，加上系统处理时间；仍非逐字同传。Apple 服务也使用本地机器学习模型，会耗电，但无需自行部署大模型。Apple 识别目前使用通用英文听写，课程术语提示仅作用于云端识别。

## 限制与费用

应用免费，**第三方 API 有自己的额度、规则与计费**。建议先用 Groq Free Plan，查看自己的 Limits；不能保证无限时长、无限请求或付费账号绝不产生费用。默认不会自动切换到其他付费服务。

数学识别和整理可能出错。老师没有念出的板书、符号和图示不能从音频还原。内置预览不排版 LaTeX，可用 Typora / Obsidian 等打开笔记。暂停会停止上传，丢弃尚未识别的音频并标记；保留最后一句时，等字幕出现再暂停。

早期版本 `v0.4.0` 支持 Apple Silicon、macOS 14+。用户已在 M5 上确认原始管线能生成英文、中文和笔记；长课时、不同设备及会议软件仍需更多测试。蓝白界面为 Qt 定制主题与半透明效果，不是原生 Liquid Glass 控件。

笔记与日志位于 `~/Library/Application Support/Lecture Caption/`；笔记窗口可直接打开文件夹。云端模式的音频与转写会发送至你配置的 API；Apple 识别/翻译在本机完成，但开启自动笔记仍会把原文发送给 Groq，详见 [隐私说明](docs/PRIVACY.md)。

开发、测试、构建及许可证见 [英文 README](README.md)。欢迎通过 Issues 提交可复现问题；不要上传密钥或私人课堂录音。

Groq 请求返回限额响应头时，主界面还会显示最近一次服务端剩余请求/Token 快照，标明模型和时间；它不是费用余额，也不代表所有模型的实时总额度。
