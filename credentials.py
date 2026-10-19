"""macOS Keychain wrapper: key material uses stdin/stdout, never command args."""

import hashlib
import json
import subprocess
from pathlib import Path


class CredentialStore:
    def __init__(self, root, config):
        self.helper = Path(root) / "native" / "bin" / "Keychain"
        # Hash identifies the destinations, not the secret: changing API servers
        # cannot silently load a credential saved for a different destination.
        endpoints = [config[k].rstrip("/") for k in ("stt_base_url", "text_base_url")]
        self.account = hashlib.sha256(json.dumps(endpoints).encode()).hexdigest()

    def execute(self, operation, secret=None):
        body = {"operation": operation, "account": self.account}
        if secret is not None:
            body["secret"] = secret
        try:
            result = subprocess.run(
                [str(self.helper)], input=json.dumps(body), text=True, capture_output=True, timeout=60
            )
            response = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise RuntimeError("无法访问 macOS 钥匙串；请解锁登录钥匙串或手动输入 key。") from None
        if result.returncode or response.get("status") not in ("ok", "missing"):
            raise RuntimeError("钥匙串操作未完成；请检查系统授权。密钥未写入普通文件。")
        return response.get("secret", "")

    def load(self):
        return self.execute("load")

    def save(self, key):
        self.execute("save", key)

    def delete(self):
        self.execute("delete")
