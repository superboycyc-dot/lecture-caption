// Receives mono float32 PCM at 16kHz on stdin. Never writes audio to disk.
import Foundation
import Speech
import AVFoundation

func finish(_ object: [String: String], _ code: Int32 = 0) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: object)
    FileHandle.standardOutput.write(data)
    exit(code)
}
@available(macOS 26.0, *)
func modernSpeech() async {
    guard SpeechTranscriber.isAvailable,
          let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: "en-US")) else {
        finish(["error": "这台 Mac 不支持 Apple SpeechAnalyzer 英文识别，请手动选择 Groq。"], 1)
    }
    let transcriber = SpeechTranscriber(locale: locale, preset: .transcription)
    do {
        try await AssetInventory.reserve(locale: locale)
        if CommandLine.arguments.contains("--prepare") {
            if let installation = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
                try await installation.downloadAndInstall()
            }
            finish(["text": "Apple 英文语音资源已准备好。"])
        }
        let status = await AssetInventory.status(forModules: [transcriber])
        if CommandLine.arguments.contains("--check") {
            finish(["text": status == .installed ? "ready: SpeechAnalyzer en-US" : "needs-assets: SpeechAnalyzer en-US"])
        }
        guard status == .installed else {
            finish(["error": "Apple 英文识别模型尚未准备好。请在应用设置中点击“准备 Apple 英文语音资源”，不必反复调整系统听写。"], 1)
        }
        let data = FileHandle.standardInput.readDataToEndOfFile()
        guard data.count > 0, data.count % 4 == 0 else { finish(["error": "本地语音输入无效。"], 1) }
        let inputFormat = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16000, channels: 1, interleaved: false)!
        let frames = AVAudioFrameCount(data.count / 4)
        let input = AVAudioPCMBuffer(pcmFormat: inputFormat, frameCapacity: frames)!
        input.frameLength = frames
        data.withUnsafeBytes { raw in
            input.floatChannelData![0].update(from: raw.bindMemory(to: Float.self).baseAddress!, count: Int(frames))
        }
        guard let format = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber]),
              let converter = AVAudioConverter(from: inputFormat, to: format) else {
            finish(["error": "无法配置 Apple 识别音频格式。"], 1)
        }
        let capacity = AVAudioFrameCount(ceil(Double(frames) * format.sampleRate / 16000)) + 1024
        let converted = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: capacity)!
        var supplied = false
        var conversionError: NSError?
        let convertedStatus = converter.convert(to: converted, error: &conversionError) { _, status in
            if supplied { status.pointee = .endOfStream; return nil }
            supplied = true
            status.pointee = .haveData
            return input
        }
        guard convertedStatus != .error, converted.frameLength > 0 else {
            finish(["error": "Apple 识别音频转换失败。"], 1)
        }
        let analyzer = SpeechAnalyzer(modules: [transcriber])
        let resultsTask = Task { () throws -> String in
            var text = ""
            for try await result in transcriber.results {
                text += String(result.text.characters)
            }
            return text
        }
        let (sequence, continuation) = AsyncStream<AnalyzerInput>.makeStream()
        continuation.yield(AnalyzerInput(buffer: converted))
        continuation.finish()
        try await analyzer.start(inputSequence: sequence)
        try await analyzer.finalizeAndFinishThroughEndOfInput()
        let text = try await resultsTask.value
        finish(["text": text.trimmingCharacters(in: .whitespacesAndNewlines)])
    } catch {
        let error = error as NSError
        // Numeric diagnostics only: never expose recognized content in error text.
        let domain = error.domain.filter { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "." || $0 == "_") }
        finish(["error": "Apple 本地识别未完成（\(domain.prefix(70)) / \(error.code)）。请在应用设置中准备英文语音资源后重试。"], 1)
    }
}
if CommandLine.arguments.contains("--authorize") {
    if #available(macOS 26.0, *) { finish(["text": "本地 SpeechAnalyzer 无需旧版听写授权。"] ) }
    SFSpeechRecognizer.requestAuthorization { status in
        finish(status == .authorized ? ["text": "语音识别权限已就绪。"] : ["error": "请在系统设置 → 隐私与安全性 → 语音识别中允许 Lecture Caption。"], status == .authorized ? 0 : 1)
    }
    RunLoop.main.run()
    exit(0)
}
if #available(macOS 26.0, *) {
    Task { await modernSpeech() }
    if !CommandLine.arguments.contains("--prepare") {
        DispatchQueue.global().asyncAfter(deadline: .now() + 40) {
            finish(["error": "Apple 本地识别超时，请在应用中重新准备英文语音资源。"], 1)
        }
    }
    RunLoop.main.run()
    exit(0)
}
if CommandLine.arguments.contains("--check") {
    let supported = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))?.supportsOnDeviceRecognition ?? false
    finish(["text": supported ? "supported" : "unavailable"])
}
let data = FileHandle.standardInput.readDataToEndOfFile()
guard data.count > 0, data.count % 4 == 0 else { finish(["error": "本地语音输入无效。"], 1) }
var speechRecognizer: SFSpeechRecognizer?
var task: SFSpeechRecognitionTask?
var request: SFSpeechAudioBufferRecognitionRequest?
SFSpeechRecognizer.requestAuthorization { status in
    DispatchQueue.main.async {
        guard status == .authorized else {
            finish(["error": "请在系统设置 → 隐私与安全性 → 语音识别中允许 Lecture Caption。"], 1)
        }
        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")), recognizer.supportsOnDeviceRecognition else {
            finish(["error": "Apple 英文本地语音资源不可用。请开启英文听写并下载语言资源，或手动选择 Groq 识别。"], 1)
        }
        speechRecognizer = recognizer
        let req = SFSpeechAudioBufferRecognitionRequest()
        request = req
        req.requiresOnDeviceRecognition = true
        req.shouldReportPartialResults = false
        req.taskHint = .dictation
        let format = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 16000, channels: 1, interleaved: false)!
        let frames = AVAudioFrameCount(data.count / 4)
        let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames)!
        buffer.frameLength = frames
        data.withUnsafeBytes { raw in
            buffer.floatChannelData![0].update(from: raw.bindMemory(to: Float.self).baseAddress!, count: Int(frames))
        }
        task = recognizer.recognitionTask(with: req) { result, error in
            if let result = result, result.isFinal {
                finish(["text": result.bestTranscription.formattedString])
            }
            if let error = error as NSError? {
                if error.code == 1110 { finish(["text": ""]) }
                finish(["error": "Apple 旧版语音识别失败（代码 \(error.code)）。macOS 26+ 可使用新的本地语音引擎。"], 1)
            }
        }
        req.append(buffer)
        req.endAudio()
    }
}
DispatchQueue.main.asyncAfter(deadline: .now() + 22) {
    task?.cancel()
    finish(["error": "Apple 本地语音识别超时，请检查英文听写资源。"], 1)
}
RunLoop.main.run()
