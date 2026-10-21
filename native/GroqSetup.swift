// Embedded official Groq account page. No script injection, DOM/clipboard inspection or credential logging.
import AppKit
import WebKit

final class Browser: NSObject, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate {
    let url = URL(string: "https://console.groq.com/keys")!
    var window: NSWindow!
    var web: WKWebView!
    func show() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1000, height: 730), styleMask: [.titled, .closable, .resizable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Lecture Caption · Groq 官方注册与 API Key"
        window.delegate = self
        window.isReleasedWhenClosed = false
        let root = NSStackView()
        root.orientation = .vertical
        root.spacing = 10
        root.edgeInsets = NSEdgeInsets(top: 12, left: 12, bottom: 12, right: 12)
        let hint = NSTextField(wrappingLabelWithString: "登录/注册 → Create API Key → 复制 key → 返回应用粘贴。账号和验证步骤由 Groq 提供；第三方登录受限时请在浏览器继续。")
        root.addArrangedSubview(hint)
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
