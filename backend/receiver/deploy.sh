#!/bin/sh
# Run as root on the inspected Ubuntu/aarch64 device. No package or OS upgrades.
set -eu
[ "$(id -u)" = 0 ] || { echo 'root_required'; exit 1; }
release=${1:?usage: deploy.sh RELEASE_NAME}
case "$release" in *[!a-zA-Z0-9_-]*|'') echo 'invalid_release'; exit 1;; esac
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
base=/opt/lecture-usage
target=$base/releases/$release
[ ! -e "$target" ] || { echo 'release_already_exists'; exit 1; }
python3 -c 'import venv,sqlite3' || { echo 'python_venv_required'; exit 1; }
[ -f "$source_dir/requirements-lock.txt" ] || { echo 'lock_required'; exit 1; }
if [ -L "$base/current" ]; then
  systemctl start lecture-usage-backup.service
else
  python3 - <<'PY'
import socket
s=socket.socket();s.bind(('127.0.0.1',18765));s.close()
PY
fi
id lecture-usage >/dev/null 2>&1 || useradd --system --home-dir /var/lib/lecture-usage --shell /usr/sbin/nologin lecture-usage
install -d -m 0755 "$target"
for file in app.py server.py ops.py test_backend.py requirements.in requirements-lock.txt request.schema.json response.schema.json openapi.json example-request.json example-response.json README.md; do
  install -m 0644 "$source_dir/$file" "$target/$file"
done
python3 -m venv "$target/venv"
if [ -d "$source_dir/wheelhouse" ]; then
  (cd "$source_dir/wheelhouse" && sha256sum -c SHA256SUMS)
  "$target/venv/bin/pip" install --no-index --find-links "$source_dir/wheelhouse" -r "$target/requirements-lock.txt"
else
  "$target/venv/bin/pip" install --index-url https://pypi.org/simple -r "$target/requirements-lock.txt"
fi
(cd "$target" && venv/bin/python -m unittest -v test_backend)
install -d -m 0700 -o lecture-usage -g lecture-usage /var/lib/lecture-usage /var/backups/lecture-usage
install -m 0644 "$source_dir"/lecture-usage*.service "$source_dir"/lecture-usage*.timer /etc/systemd/system/
ln -s "releases/$release" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
systemctl daemon-reload
systemctl enable lecture-usage.service lecture-usage-backup.timer lecture-usage-capacity.timer
systemctl restart lecture-usage.service
systemctl start lecture-usage-backup.timer lecture-usage-capacity.timer
printf '%s\n' 'deployed; verify http://127.0.0.1:18765/healthz; Funnel configuration is a separate explicit operation'
