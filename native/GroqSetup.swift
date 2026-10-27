// Embedded official Groq account page. No script injection, DOM/clipboard inspection or credential logging.
import AppKit
import WebKit

final class Browser: NSObject, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate {
    let url = URL(string: "https://console.groq.com/keys")!
    var window: NSWindow!
    var web: WKWebView!
    func show() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1000, height: 880), styleMask: [.titled, .closable, .resizable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Lecture Caption · Groq 官方注册与 API Key"
        window.delegate = self
        window.isReleasedWhenClosed = false
        let root = NSStackView()
        root.orientation = .vertical
        root.spacing = 10
        root.edgeInsets = NSEdgeInsets(top: 12, left: 12, bottom: 12, right: 12)
        let heading = NSTextField(labelWithString: "请按下面 4 步操作，再返回应用")
        heading.font = .boldSystemFont(ofSize: 22)
        heading.textColor = .systemBlue
        root.addArrangedSubview(heading)
        let hint = NSTextField(wrappingLabelWithString: "① 登录或注册 Groq → 点击 Create API Key\n② Display Name 填：Lecture Caption　｜　Expiration 保持：No expiration\n③ 点击 Submit / Create API Key，生成后一定要复制完整 key\n④ 点击下方‘已复制 key，返回应用’，在应用点‘下一步：验证并保存’")
        hint.font = .systemFont(ofSize: 18, weight: .medium)
        root.addArrangedSubview(hint)
        let note = NSTextField(wrappingLabelWithString: "请先复制再关闭：完整 key 之后可能无法再次查看。第三方登录受限时，点击‘在默认浏览器继续’。")
        note.textColor = .secondaryLabelColor
        root.addArrangedSubview(note)
        let row = NSStackView()
        row.addArrangedSubview(NSButton(title: "在默认浏览器继续", target: self, action: #selector(external)))
        row.addArrangedSubview(NSButton(title: "已复制 key，返回应用", target: self, action: #selector(back)))
        root.addArrangedSubview(row)
        let configuration = WKWebViewConfiguration()
        web = WKWebView(frame: .zero, configuration: configuration)
        web.navigationDelegate = self
        web.uiDelegate = self
        root.addArrangedSubview(web)
        window.contentView = root
        web.widthAnchor.constraint(equalTo: root.widthAnchor, constant: -24).isActive = true
        web.load(URLRequest(url: url))
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    @objc func external() { NSWorkspace.shared.open(url) }
    @objc func back() { NSApp.terminate(nil) }
    func windowWillClose(_ notification: Notification) { NSApp.terminate(nil) }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let scheme = action.request.url?.scheme, scheme == "https" || scheme == "about" else {
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        // OAuth providers may reject embedded user agents. Continue in a real browser instead of bypassing provider rules.
        NSWorkspace.shared.open(url)
        return nil
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        window.title = "页面未加载 · 可点击“在默认浏览器继续”"
    }
}
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let browser = Browser()
browser.show()
app.run()
