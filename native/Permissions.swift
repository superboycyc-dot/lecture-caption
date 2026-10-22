// Loaded in the main app process: microphone consent belongs to the recording app, not a child helper.
import AVFoundation
import Foundation

@_cdecl("lecture_request_microphone")
public func lectureRequestMicrophone(_ callback: @escaping @convention(c) (Int32) -> Void) {
    switch AVCaptureDevice.authorizationStatus(for: .audio) {
    case .authorized: callback(1)
    case .notDetermined:
        AVCaptureDevice.requestAccess(for: .audio) { granted in callback(granted ? 1 : 0) }
    default: callback(0)
    }
}
