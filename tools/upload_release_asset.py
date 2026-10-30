"""用 REST 接口上传 release 附件，文件名走 URL 参数以保住中文名

gh CLI 在 Windows 下从 bash 拿中文参数会丢字（番茄桌宠_v1.0.zip → _v1.0.zip），
所以这里不用命令行传名，改成 ?name= 传 UTF-8。
"""
import subprocess
import sys
from pathlib import Path

import requests

GH = Path.home() / "bin" / "gh-tool" / "bin" / "gh.exe"
OWNER, REPO, TAG = "Lin123Feng", "pomodoro-pet", "v1.0.0"
SRC = Path(r"D:\Users\python\learn\dist\番茄桌宠_v1.0.zip")
ASSET_NAME = "番茄桌宠_v1.0.zip"

token = subprocess.run([str(GH), "auth", "token"], capture_output=True, text=True).stdout.strip()
if not token:
    raise SystemExit("拿不到 token，先 gh auth login")
h = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

rel = requests.get(
    f"https://api.github.com/repos/{OWNER}/{REPO}/releases/tags/{TAG}",
    headers=h, timeout=60,
).json()
rid = rel["id"]
print("release id:", rid)

for a in rel.get("assets", []):
    print("已有附件:", a["name"])

print(f"上传 {SRC.name}  {SRC.stat().st_size / 1048576:.1f} MB ...")
with SRC.open("rb") as f:
    r = requests.post(
        f"https://uploads.github.com/repos/{OWNER}/{REPO}/releases/{rid}/assets",
        params={"name": ASSET_NAME},
        headers={**h, "Content-Type": "application/zip"},
        data=f,
        timeout=1800,
    )

print("HTTP", r.status_code)
if r.status_code not in (200, 201):
    print(r.text[:600])
    sys.exit(1)

d = r.json()
print(f"asset: {d['name']}  {d['size']} 字节  state={d['state']}")
print("下载地址:", d["browser_download_url"])
