// macOS 15 Translation.framework. Only --prepare may download language assets.
import Foundation
import AppKit
import SwiftUI
import Translation
import ObjectiveC

func output(_ object: [String: String], _ code: Int32 = 0) -> Never {
    FileHandle.standardOutput.write(try! JSONSerialization.data(withJSONObject: object))
    exit(code)
}
@available(macOS 15.0, *)
struct TranslateView: View {
    let source: String
    let prepare: Bool
    @State private var status = "正在准备英文 → 简体中文翻译…"
    var body: some View {
        VStack(spacing: 18) {
            Text("Apple 本地翻译").font(.title2.bold())
            Text(status).multilineTextAlignment(.center)
            Text("语言包准备后，课堂字幕在本机翻译。完成后可关闭此窗口。")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(28).frame(width: 440, height: 200)
        .translationTask(source: Locale.Language(identifier: "en"), target: Locale.Language(identifier: "zh-Hans")) { session in
            do {
                if prepare {
                    try await session.prepareTranslation()
                    if CommandLine.arguments.contains("--prepare-and-exit") { output(["text": "Apple 英中翻译资源已准备好。"] ) }
                    status = "英文和中文翻译语言包已准备好。"
                } else {
                    let result = try await session.translate(source)
                    output(["text": result.targetText])
                }
            } catch {
                if CommandLine.arguments.contains("--prepare-and-exit") { output(["error": "Apple 翻译资源准备未完成，请重试或检查网络。"], 1) }
                if prepare { status = "准备未完成，请重试或检查网络。" }
                else { output(["error": "Apple 本地翻译失败，请在设置中准备英中翻译语言包。"], 1) }
            }
        }
    }
}
class ClosingDelegate: NSObject, NSWindowDelegate {
    func windowWillClose(_ notification: Notification) { exit(0) }
}
let closingDelegate = ClosingDelegate()
let prepare = CommandLine.arguments.contains("--prepare") || CommandLine.arguments.contains("--prepare-and-exit")
if #available(macOS 15.0, *) {
    let application = NSApplication.shared
    application.setActivationPolicy(.accessory)
    var source = ""
    if !prepare {
        let data = FileHandle.standardInput.readDataToEndOfFile()
        guard let input = try? JSONSerialization.jsonObject(with: data) as? [String: String], let text = input["text"] else {
            output(["error": "本地翻译输入无效。"], 1)
        }
        source = text
    }
    let capturedSource = source
    Task { @MainActor in
        if !prepare {
            let availability = LanguageAvailability()
            let status = await availability.status(from: Locale.Language(identifier: "en"), to: Locale.Language(identifier: "zh-Hans"))
            guard status == .installed else {
                output(["error": "尚未安装 Apple 英中翻译语言包，请先在设置中点击“准备 Apple 英中翻译语言包”。"], 1)
            }
        }
        let window = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 500, height: 250), styleMask: [.titled, .closable, .nonactivatingPanel], backing: .buffered, defer: false)
        window.delegate = closingDelegate
        window.title = "Lecture Caption · Apple 语言包"
        window.isReleasedWhenClosed = false
        window.contentView = NSHostingView(rootView: TranslateView(source: capturedSource, prepare: prepare))
        if !prepare { window.alphaValue = 0; window.ignoresMouseEvents = true }
        window.center()
        window.orderFrontRegardless()
        if prepare { application.activate(ignoringOtherApps: true) }
        // Keep the host/window alive throughout the asynchronous translation task.
        objc_setAssociatedObject(application, Unmanaged.passUnretained(application).toOpaque(), window, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
    }
    if !prepare {
        DispatchQueue.main.asyncAfter(deadline: .now() + 30) {
            output(["error": "Apple 本地翻译超时，请检查语言包。"], 1)
        }
    }
    application.run()
} else {
    output(["error": "Apple 翻译需要 macOS 15 或更新版本。"], 1)
}
