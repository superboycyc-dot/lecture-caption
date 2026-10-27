# Mac 安装与首次打开图解

> 🔴 **首次打开容易被 macOS 拦截。请根据下面的步骤逐步完成设置。系统拦截弹窗无法由本应用添加按钮或自动确认；请手动打开“系统设置 → 隐私与安全性”，下滑到“安全性”后点击“仍要打开”。**

先[下载 Mac 版](https://github.com/superboycyc-dot/lecture-caption/releases/latest)，解压后双击 **Lecture Caption.app**。完成下方系统安全确认后，点击“安装到应用程序并打开”，无需手动拖动；手动拖入仍可作为备用方法。

## 首次打开被 macOS 拦截？按图操作

当前版本尚未 Apple 公证。确认从本项目的官方 GitHub 发布页下载后，按下面四步打开 **Lecture Caption**。

**① 打开“系统设置”**

点击屏幕左上角的  菜单，选择“系统设置”；图标长这样：

<img src="install/system-settings.png" width="110" alt="系统设置的齿轮图标">

**② 点击左侧“隐私与安全性”**

在左边列表中找到红框标出的“隐私与安全性”。找不到时向下滚动左侧列表。

<img src="install/privacy-security.png" width="680" alt="在系统设置左侧点击红框中的隐私与安全性">

**③ 在右侧找到 Lecture Caption，点击“仍要打开”**

向下滚动右侧页面到“安全性”，在“已阻止 Lecture Caption”旁边点击红框按钮。若没有这个按钮，先到“应用程序”尝试打开一次 Lecture Caption，再回到此页面。

<img src="install/open-anyway.png" width="680" alt="在隐私与安全性页面的安全性区域，点击 Lecture Caption 旁的仍要打开">

**④ 在弹出的确认窗口中，再点一次“仍要打开”**

点击下图红框中的“仍要打开”；如果系统要求验证身份，按提示使用触控 ID 或 Mac 登录密码。完成后应用会打开，跟随首次使用指南继续配置即可。

<img src="install/confirm-open.png" width="420" alt="在打开 Lecture Caption 的确认弹窗中点击红框内的仍要打开">

## 看到“Keychain 想要使用机密信息”怎么办？

这是 macOS 的钥匙串授权窗口：软件想读取你之前保存的 **Lecture Caption API Key**，这样下次打开就不用重新输入 Groq key。这里的“机密信息”指这个已保存的 key。

<img src="install/keychain-prompt.png" width="680" alt="macOS 钥匙串弹窗：Keychain 请求读取 Lecture Caption API Key，可选择始终允许、拒绝或允许">

**先核对条目名称是“Lecture Caption API Key”**，且你正在打开官方版本的 Lecture Caption。弹窗中的 **Keychain** 是本软件随附的钥匙串辅助程序名称。

1. 密码框要求的是 **“登录”钥匙串的密码**，通常就是你解锁这台 Mac 的登录密码，**不是 Groq API key，也不是 Apple ID 密码**。如果你曾单独修改钥匙串密码，请使用对应密码。
2. 想先授权这一次，点 **“允许”**；下次读取时可能再次询问。
3. 确认来源可信、希望以后少弹窗，可以选择 **“始终允许”**，让这个辅助程序以后读取该条目时不再逐次确认。更新程序后，系统仍可能要求重新授权。
4. 不想授权，可以点 **“拒绝”**。本次无法自动读取已保存的 key，仍可在软件设置中手动填写；不使用 Groq 时也可选择本地字幕，但无法自动整理笔记。

密码仅在 **macOS 系统弹窗** 中输入，由系统验证；本软件不会接收这个 Mac 密码。授权后软件会取得该 API key 来调用接口。不要把 Mac 密码填到软件的 API key 栏、Groq 网页或发给任何人。这个操作是在授权读取上述条目，不是要求你关闭钥匙串保护。

按钮含义可参阅 [Apple 官方说明：允许 App 访问钥匙串](https://support.apple.com/guide/mac-help/kychn002/mac)。


### 2.4.3 一键安装
下载 ZIP 后解压、打开应用。完成 macOS 首次安全确认后，点“安装到应用程序并打开”，软件自动复制并验证，退出下载副本后打开已安装版本。权限不足时由 macOS 请求管理员授权；原下载文件不删除。若已有安装，点击“打开已安装版本”后在关于窗口检查更新。也可“稍后（继续使用）”。下载中的文件不能自行运行或移动，系统安全拦截不能自动绕过。
