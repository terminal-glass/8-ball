# Installing the 8-Ball console (Linux)

Tested on Ubuntu with Python 3.11+ and Ollama on the same machine. Run as root where noted.

```bash
# 1. user, folders, code (pin a commit)
useradd --system --home /var/lib/8ball --shell /usr/sbin/nologin eightball
install -d -o root -g root -m 0755 /opt/8ball /etc/8ball
install -d -o eightball -g eightball -m 0750 /var/lib/8ball /var/lib/8ball/console
git clone --filter=blob:none --sparse https://github.com/terminal-glass/8-ball /opt/8ball/catalog
git -C /opt/8ball/catalog sparse-checkout set app profiles install/shared config schemas data/normalized
git -C /opt/8ball/catalog checkout <commit>
git -C /opt/8ball/catalog rev-parse HEAD > /opt/8ball/catalog/CATALOG_COMMIT
ln -sfn /opt/8ball/catalog/app /opt/8ball/app

# 2. Python environment with pinned, hashed dependencies
python3 -m venv /opt/8ball/venv
/opt/8ball/venv/bin/pip install --require-hashes -r /opt/8ball/app/requirements.txt

# 3. config
cp /opt/8ball/app/examples/console.example.toml /etc/8ball/console.toml   # edit as needed

# 4. profile (scan, then build). Re-run after hardware changes; the console never scans on its own.
cd /opt/8ball/app
/opt/8ball/venv/bin/python -m eightball_console scan --out /var/lib/8ball/scan.v1.json
/opt/8ball/venv/bin/python -m eightball_console build --scan /var/lib/8ball/scan.v1.json --out /var/lib/8ball/profile.v1.json
/opt/8ball/venv/bin/python -m eightball_console check

# 5. a login (basic mode). The password is read from a file and is never printed.
umask 077; openssl rand -base64 24 > /root/8ball-admin.txt
/opt/8ball/venv/bin/python -m eightball_console user-add admin --role admin --password-file /root/8ball-admin.txt
chown eightball /etc/8ball/users.json

# 6. service
cp /opt/8ball/app/examples/8ball-console.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now 8ball-console
curl -s http://127.0.0.1:8788/api/health
```

Then publish it through your reverse proxy (see `examples/nginx-location.conf`). Keep it behind TLS
and a login on any machine reachable from outside your LAN.

## Optional: read-only terminal view

Download ttyd 1.7.7 from its GitHub release and check the hash before installing:

| file | sha256 |
|---|---|
| `ttyd.x86_64` | `8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55` |
| `ttyd.aarch64` | `b38acadd89d1d396a0f5649aa52c539edbad07f4bc7348b27b4f4b7219dd4165` |

```bash
install -m 0755 ttyd.x86_64 /opt/8ball/bin/ttyd
cp /opt/8ball/app/examples/8ball-console-tty.service /etc/systemd/system/
echo 'console_path = "tty/"' >> /etc/8ball/console.toml
systemctl daemon-reload && systemctl enable --now 8ball-console-tty && systemctl restart 8ball-console
```

ttyd runs without `-W` (no keyboard input) and only starts the log viewer, which needs a short-lived
token for one job. Without ttyd the Console page still streams the same log over server-sent events.

## Uninstall

`systemctl disable --now 8ball-console 8ball-console-tty`, remove the units, `/opt/8ball`,
`/etc/8ball` and `/var/lib/8ball`. Ollama and its models are left untouched.
