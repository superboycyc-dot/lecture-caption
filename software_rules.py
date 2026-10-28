"""Versioned in-app use rules; explicit first-run agreement includes disclosed usage consent."""

RULES_VERSION = "2026-10-27.1"
RULES_TEXT = """# 软件使用规则

版本：2026-10-27.1

## 1. 软件用途与录音权限
Lecture Caption 用于课堂、会议或视频的语音识别、翻译和学习笔记。请确认你有权收听、录制及处理相应内容，并遵守课堂、会议或内容提供方的要求。系统权限准备不会自动开始录音；只有你点击“开始”后才收音，暂停或结束会释放输入。

## 2. 内容如何处理
选择 Groq 识别时，音频片段发送至已配置的语音服务；选择云端翻译或笔记时，相关原文、现有笔记（包括导入内容）发送至对应服务。选择 Apple 本地识别/翻译时，相应处理使用本地系统能力，不会静默改用云端。自动笔记使用你配置的文本模型服务，默认是 Groq。第三方服务的隐私政策及额度规则分别适用。

软件不保存原始录音，但会在本机保存原文、译文和笔记等记录供继续整理和导出。这些本机记录与下面的用量统计是不同的数据。

## 3. 用量分享：首次协议包含的授权
首次设置必须勾选“同意《软件使用规则》并分享用量统计”才能继续。勾选同时授权下述用量统计，用于帮助开发者了解使用规模并改进软件；无需另行勾选。未勾选前不会启用统计。之后可随时在设置中撤回分享授权，关闭后不影响字幕、翻译或笔记。

开启后，只向开发者后台发送：录音次数、实际收音时长、原文和译文的词数/字数，以及随机的每课事件编号、快照版本和 UTC 日期；每次上传还由接收服务器记录该次连接的 IP 地址。不会发送录音、原文、译文、笔记、API key、账号或稳定设备标识。实时识别与重译的修正会替换原统计，不重复累加。

连接 IP 用于了解统计来源和排查异常上传，仅供开发者后台管理使用，不在公开统计中展示，不用于广告画像；保留 30 天后清除。使用 VPN 或代理时，记录的可能是出口 IP，不能用于确认个人身份或精确位置。软件不访问第三方查 IP 服务。

这属于包含 IP 地址的用量统计，不保证整条链路匿名：网络服务与 Tailscale Funnel 上游可能处理或保留连接 IP 等诊断信息。统计后台由开发者运营，公开数字可能被伪造，不用于计费或可靠的独立用户统计。

## 4. 离线保存与撤回选择
分享开启后，统计先保存在本机队列；断网、超时或未收到有效确认时会保留，联网或下次打开软件时重试。软件关闭后不会另启常驻进程。

你可以随时在“设置”里关闭用量分享。关闭会停止后续收集和上传，并清除本机统计队列；已在途的请求可能已到达后台，关闭并不自动删除服务端已收到的记录。再次开启不会回扫之前的录音文本或笔记。

## 5. API key、密码与更新
你自己的 API key 可保存到 macOS 钥匙串。Mac 登录密码只在 macOS 系统弹窗中输入，由系统验证；不要把它填到 API key 栏或发给开发者。软件和辅助程序不会接收这个 Mac 密码。

自动更新默认开启，通过本项目官方 GitHub 检查和下载新版，可在设置中关闭。更新请求不附带课堂内容或 API key；录音、待保存内容和首次配置会暂缓自动安装。

## 6. 结果核对与费用
识别、翻译和 AI 笔记可能出错或遗漏，尤其是公式、代码、专业术语和板书，请结合课件核对。Groq 免费额度、模型和第三方条款可能变化；软件无法保证所有账号使用情况都免费，请自行核对供应商的额度及账单。

## 7. 许可证与联系
软件采用 MIT 许可证，打包组件保留各自许可证。本规则说明应用内服务和数据处理，不变更 MIT 或第三方许可证已经赋予的权利。

开发者：Yichen Chen
项目与反馈：https://github.com/superboycyc-dot/lecture-caption
联系邮箱：superboycyc@gmail.com

首次勾选“同意《软件使用规则》并分享用量统计”表示你接受以上使用与数据处理说明并授权上述用量及连接 IP 分享；可在首次设置的链接或“关于”中重新查看规则。
"""


def make_rules_dialog(controls, parent=None):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton

    dialog = QDialog(parent or controls)
    dialog.setWindowTitle("软件使用规则")
    dialog.setWindowModality(Qt.WindowModal)
    dialog.resize(660, 640)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(20, 20, 20, 20)
    text = QTextBrowser()
    text.setMarkdown(RULES_TEXT)
    text.setOpenExternalLinks(True)
    text.setStyleSheet(
        "QTextBrowser {background:white;border:1px solid #D9E4F2;border-radius:8px;padding:14px;color:#233956;}"
    )
    layout.addWidget(text, 1)
    close = QPushButton("返回")
    close.clicked.connect(dialog.accept)
    layout.addWidget(close)
    # Owning widgets keep the dialog available for tests and repeated viewing.
    dialog.rules_view = text
    return dialog
