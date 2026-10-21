// Receives mono float32 PCM at 16kHz on stdin. Never writes audio to disk.
import Foundation
import Speech
import AVFoundation

func finish(_ object: [String: String], _ code: Int32 = 0) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: object)
    FileHandle.standardOutput.write(data)
    exit(code)
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
            if error != nil { finish(["error": "Apple 本地语音识别失败，请检查英文听写资源后重试。"], 1) }
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
