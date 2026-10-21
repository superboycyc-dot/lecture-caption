import Foundation
import ScreenCaptureKit
import CoreMedia
import AudioToolbox
import CoreGraphics

// Permission preparation does not create a stream or read audio/screens.
if CommandLine.arguments.contains("--permissions") {
    let allowed = CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess()
    let response = ["text": allowed ? "系统音频权限已就绪。" : "请在系统设置 → 隐私与安全性 → 屏幕与系统音频录制中允许 Lecture Caption；系统可能要求重新打开应用。"]
    FileHandle.standardOutput.write(try! JSONSerialization.data(withJSONObject: response))
    exit(allowed ? 0 : 1)
}

final class AudioSink: NSObject, SCStreamOutput, SCStreamDelegate {
    func stream(_ stream: SCStream, didStopWithError error: Error) {
        FileHandle.standardError.write(Data("系统音频中断：\(error.localizedDescription)\n".utf8))
        exit(2)
    }
    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of outputType: SCStreamOutputType) {
        guard outputType == .audio, sampleBuffer.isValid else { return }
        var list = AudioBufferList()
        var retained: CMBlockBuffer?
        let result = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(sampleBuffer, bufferListSizeNeededOut: nil, bufferListOut: &list, bufferListSize: MemoryLayout<AudioBufferList>.size, blockBufferAllocator: nil, blockBufferMemoryAllocator: nil, flags: kCMSampleBufferFlag_AudioBufferList_Assure16ByteAlignment, blockBufferOut: &retained)
        guard result == noErr, list.mNumberBuffers == 1, let data = list.mBuffers.mData else { return }
        guard let format = CMSampleBufferGetFormatDescription(sampleBuffer), let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(format), asbd.pointee.mBitsPerChannel == 32, asbd.pointee.mFormatFlags & kAudioFormatFlagIsFloat != 0, asbd.pointee.mSampleRate == 16000 else { return }
        FileHandle.standardOutput.write(Data(bytes: data, count: Int(list.mBuffers.mDataByteSize)))
    }
}
let sink = AudioSink()
var capture: SCStream?
Task { @MainActor in
    do {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)
        guard let display = content.displays.first else { throw NSError(domain: "LectureCaption", code: 1, userInfo: [NSLocalizedDescriptionKey:"未找到屏幕"]) }
        let filter = SCContentFilter(display: display, excludingWindows: [])
        let config = SCStreamConfiguration()
        config.width = 2; config.height = 2
        config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
        config.capturesAudio = true; config.sampleRate = 16000; config.channelCount = 1
        config.excludesCurrentProcessAudio = true
        let stream = SCStream(filter: filter, configuration: config, delegate: sink)
        try stream.addStreamOutput(sink, type: .audio, sampleHandlerQueue: DispatchQueue(label: "lecture.audio"))
        capture = stream
        try await stream.startCapture()
        FileHandle.standardError.write(Data("READY\n".utf8))
    } catch {
        FileHandle.standardError.write(Data("需要系统音频/屏幕录制权限：\(error.localizedDescription)\n".utf8))
        exit(1)
    }
}
RunLoop.main.run()
