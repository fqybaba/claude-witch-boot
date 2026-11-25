"""用火山方舟 API 生成 Seedance 视频（首帧图生视频）。Key 从环境变量 ARK_API_KEY 读，不写进文件。
用法（ComfyUI 自带的 Python）：
  python.exe -I ark_video.py --image 首帧.png --prompt-file 提示词.txt --out 输出.mp4
      [--model doubao-seedance-2-5-260628] [--resolution 720p] [--duration 5] [--ratio 16:9] [--last 尾帧.png]
  python.exe -I ark_video.py --poll 任务id --out 输出.mp4     # 只查询、下载已有任务
"""
import argparse, base64, io, json, os, sys, time, urllib.request, urllib.error
from PIL import Image

BASE = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
KEY = os.environ.get("ARK_API_KEY") or sys.exit("先设置环境变量 ARK_API_KEY")


def call(url, data=None, tries=5):
    """网络不稳时自动重试。GET 直接重试；POST 失败后先看任务列表里有没有新任务，避免重复提交。"""
    before = None
    if data is not None:
        before = {t["id"] for t in call(BASE + "?page_size=10").get("items", [])}
    for k in range(tries):
        req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            sys.exit(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:1500]}")
        except Exception as e:
            print("网络错误，重试：", type(e).__name__, flush=True)
            time.sleep(5)
            if before is not None:
                new = [t for t in call(BASE + "?page_size=10").get("items", []) if t["id"] not in before]
                if new:
                    return new[0]
    sys.exit("连续网络错误，放弃")


def download(url, out, tries=8):
    done = 0
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={done}-"} if done else {})
            with urllib.request.urlopen(req, timeout=120) as r, open(out, "ab" if done else "wb") as f:
                while True:
                    b = r.read(1 << 16)
                    if not b:
                        return
                    f.write(b); done += len(b)
        except Exception as e:
            print("下载中断，续传：", type(e).__name__, done, flush=True)
            time.sleep(3)
    sys.exit("下载失败")


def data_url(path):
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, "JPEG", quality=95)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


ap = argparse.ArgumentParser()
ap.add_argument("--image"); ap.add_argument("--last"); ap.add_argument("--prompt-file")
ap.add_argument("--out", required=True)
ap.add_argument("--model", default="doubao-seedance-2-5-260628")
ap.add_argument("--resolution", default="720p"); ap.add_argument("--duration", type=int, default=5)
ap.add_argument("--ratio", default="16:9"); ap.add_argument("--poll")
ap.add_argument("--audio", action="store_true", help="让模型同时生成声音（默认不要）")
a = ap.parse_args()

tid = a.poll
if not tid:
    content = [{"type": "text", "text": open(a.prompt_file, encoding="utf-8").read().strip()},
               {"type": "image_url", "image_url": {"url": data_url(a.image)}, "role": "first_frame"}]
    if a.last:
        content.append({"type": "image_url", "image_url": {"url": data_url(a.last)}, "role": "last_frame"})
    # 有首帧时不能传 ratio（比例跟着首帧图走）
    body = {"model": a.model, "content": content, "resolution": a.resolution,
            "duration": a.duration, "watermark": False, "generate_audio": bool(a.audio)}
    tid = call(BASE, body)["id"]
    print("task", tid, flush=True)

t0 = time.time()
while True:
    r = call(f"{BASE}/{tid}")
    st = r.get("status")
    if st in ("succeeded", "failed", "cancelled", "expired"):
        slim = {k: v for k, v in r.items() if k != "content"}
        print(json.dumps(slim, ensure_ascii=False))
        if st != "succeeded":
            sys.exit(1)
        url = r["content"]["video_url"]
        download(url, a.out)
        print("saved", a.out, f"{time.time() - t0:.0f}s")
        break
    print(st, f"{time.time() - t0:.0f}s", flush=True)
    time.sleep(8)
