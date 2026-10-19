import Foundation
import Security

struct Request: Decodable { let operation: String; let account: String; let secret: String? }
func respond(_ status: String, secret: String? = nil) -> Never {
    var body = ["status": status]
    if let secret = secret { body["secret"] = secret }
    if let data = try? JSONSerialization.data(withJSONObject: body) { FileHandle.standardOutput.write(data) }
    exit(status == "ok" || status == "missing" ? 0 : 1)
}
let bytes = FileHandle.standardInput.readDataToEndOfFile()
guard bytes.count < 16384, let request = try? JSONDecoder().decode(Request.self, from: bytes), request.account.count == 64, request.account.allSatisfy({ $0.isHexDigit }) else { respond("invalid_request") }
let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "local.lecturecaption.api", kSecAttrAccount as String: request.account, kSecAttrSynchronizable as String: false]
switch request.operation {
case "load":
    var lookup = query
    lookup[kSecReturnData as String] = true
    lookup[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    let status = SecItemCopyMatching(lookup as CFDictionary, &result)
    if status == errSecItemNotFound { respond("missing") }
    guard status == errSecSuccess, let data = result as? Data, let secret = String(data: data, encoding: .utf8) else { respond("keychain_read_failed") }
    respond("ok", secret: secret)
case "save":
    guard let secret = request.secret, !secret.isEmpty, secret.utf8.count <= 8192 else { respond("invalid_secret") }
    let data = Data(secret.utf8)
    var status = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
    if status == errSecItemNotFound {
        var item = query
        item[kSecValueData as String] = data
        item[kSecAttrLabel as String] = "Lecture Caption API Key"
        item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        status = SecItemAdd(item as CFDictionary, nil)
    }
    guard status == errSecSuccess else { respond("keychain_save_failed") }
    respond("ok")
case "delete":
    let status = SecItemDelete(query as CFDictionary)
    guard status == errSecSuccess || status == errSecItemNotFound else { respond("keychain_delete_failed") }
    respond("ok")
default: respond("invalid_operation")
}
