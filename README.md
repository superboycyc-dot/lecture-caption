<p align="center"><img src="assets/AppIcon.png" width="112" alt="Lecture Caption 图标"></p>
<h1 align="center">Lecture Caption</h1>
<p align="center">听懂每一句，记住每个关键点。<br>Mac 英中双语字幕 · 实时课堂笔记 · 本地原文归档</p>

<p align="center"><a href="https://github.com/superboycyc-dot/lecture-caption/releases/download/v3.0.0/LectureCaption-3.0.0-macOS-arm64.dmg"><img src="https://img.shields.io/badge/下载正式版_3.0.0-DMG_·_Apple_Silicon-2877E1?style=for-the-badge&logo=apple&logoColor=white" alt="下载 DMG 安装包"></a></p>

[English](README.en.md) · [详细中文说明](README.zh-CN.md) · [使用指南](docs/USER_GUIDE.zh-CN.md) · [隐私说明](docs/PRIVACY.md) · [更新记录](CHANGELOG.md)

Lecture Caption 是面向英语课堂、在线课程和会议学习的免费开源 macOS 应用。收听麦克风或电脑播放的音频，在同一窗口查看英文原文、中文翻译和持续整理的 Markdown 笔记，课后导出 PDF 与转录原文。尤其适合 CS、数学等需要保留英文术语和推导过程的课程。

![软件界面：左侧课堂笔记，右侧英文原文与中文翻译](docs/workspace-blue.png)

## 可以做什么

| 功能 | 使用体验 |
| --- | --- |
| 麦克风与电脑音频 | 教室收音，或转录电脑播放的线上课程、会议和视频；一次选择一种音源。 |
| 英中双语字幕 | 英文原文与中文翻译对照，支持纯英文/纯中文；历史可回看，当前段落高亮。 |
| 持续课堂笔记 | 约每 30 秒追加新增笔记，每 5 分钟整合此前全部内容，保留已有知识点。 |
| 原文与笔记导出 | 自动保存 PDF 和转录 Markdown；“另存转录”单独导出已识别原文，笔记支持 Markdown/PDF。 |
| 笔记编辑与公式 | 编辑 Markdown、添加高亮和批注，支持公式预览与 PDF 导出。 |
| Apple 本地或 Groq | 可选 Apple 本地英文识别/英中翻译，或使用配置的云端接口；结构化笔记需要文本 API。 |
| 清楚的故障反馈 | 显示超时、限流、密钥/权限等原因，临时错误退避重试，未整理原文保留。 |
| Mac 使用习惯 | DMG 拖拽安装、钥匙串保存密钥、应用内更新；开始前不收音，不保存原始录音。 |

## 三步安装

1. [下载 3.0.0 DMG](https://github.com/superboycyc-dot/lecture-caption/releases/download/v3.0.0/LectureCaption-3.0.0-macOS-arm64.dmg)，双击打开。
2. 在安装窗口把 **Lecture Caption** 拖到右侧 **Applications（应用程序）** 文件夹。升级时先退出旧应用，再按 Finder 提示替换。
3. 推出安装磁盘，从“应用程序”打开 Lecture Caption，按首次指南设置权限与所需模型，再点击开始。

适用于 **Apple Silicon（M1/M2/M3/M4/M5 等）和 macOS 14+**；Apple 本地翻译要求 macOS 15+。DMG 与内部应用均使用 Developer ID 签名并通过 Apple 公证，仍可能出现正常的下载来源确认和权限弹窗。无需安装 Python 或输入终端命令。

## 模型、费用与数据

应用本身免费开源。Groq 等第三方接口有自己的账号额度、服务规则和计费；不会自动切换到其他付费服务。Apple 本地字幕可在关闭自动笔记后不使用 API key；开启笔记会把识别原文发送至配置的文本 API。

原文和笔记保存在本机；云端模式会发送所需音频/文字到所选接口。密钥保存在 macOS 钥匙串。数字用量分享需首次明确同意，可在设置中关闭；详见[隐私说明](docs/PRIVACY.md)。转录和笔记可能出错，未念出的板书内容不能从音频还原。

## 获取帮助与参与开发

- [详细功能与设置](README.zh-CN.md) · [英文开发与构建说明](README.en.md)
- [安装帮助](docs/INSTALL.zh-CN.md) · [提交问题](https://github.com/superboycyc-dot/lecture-caption/issues)（请勿上传密钥或私人课堂录音）
- [正式版本与校验和](https://github.com/superboycyc-dot/lecture-caption/releases/latest) · [MIT 许可证](LICENSE)

[![CI](https://github.com/superboycyc-dot/lecture-caption/actions/workflows/ci.yml/badge.svg)](https://github.com/superboycyc-dot/lecture-caption/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/superboycyc-dot/lecture-caption)](https://github.com/superboycyc-dot/lecture-caption/releases/latest)
