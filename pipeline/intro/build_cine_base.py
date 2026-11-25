"""把三段 AI 视频按剪辑时间线排成一条 30fps 的底片帧序列（1920x1080 JPG），给 intro_cine.html 当人物图层。
用 ComfyUI 自带的 Python 跑（在 src/intro 目录下）：
  python.exe -I build_cine_base.py 输出目录 [--fps 48] [--w 2560 --h 1440] [--s1 帧目录 --s2 帧目录 --witch 帧目录]
  （--s1/--s2/--witch：换成 AI 放大过的帧，帧文件按顺序排）
时间线（秒，和 intro_cine.html、sfx_cine.py 对齐）：
  0.00–3.60   S1 抽书，1.4 倍速
  3.60–7.94   S2 断链：前 1.4 秒（只是晃动）2 倍速，之后原速
  7.94–8.40   S2 最后一帧定格（页面里做轻微推近，叠 Claude 字标）
  8.40–13.50  魔女视频，原速；播完停在最后一帧
"""
import argparse, glob, os, sys
import av
from PIL import Image

ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--fps", type=int, default=48)
ap.add_argument("--w", type=int, default=2560); ap.add_argument("--h", type=int, default=1440)
ap.add_argument("--s1"); ap.add_argument("--s2"); ap.add_argument("--witch")
ap.add_argument("--src-fps", type=float, default=24, help="--s1/--s2/--witch 帧目录的帧率（补过帧就是 120）")
A = ap.parse_args(); out = A.out
os.makedirs(out, exist_ok=True)
ROOT = "../footage/"
T_S2, T_HOLD, T_WITCH, LEN, FPS = 3.60, 7.94, 8.40, 13.5, A.fps
OW, OH = A.w, A.h


def frames(path, folder=None):
    if folder:   # 帧目录只记路径，用到再读（高清帧全读进内存会爆）
        return sorted(glob.glob(os.path.join(folder, "*.png")) + glob.glob(os.path.join(folder, "*.jpg")))
    return [f.to_image() for f in av.open(path).decode(video=0)]


def fit(im):
    """铺满 OWxOH（cover）。"""
    w, h = im.size
    if (w, h) == (OW, OH):
        return im
    s = max(OW / w, OH / h)
    im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    x, y = (im.width - OW) // 2, (im.height - OH) // 2
    return im.crop((x, y, x + OW, y + OH))


s1 = frames(ROOT + "S1_book_pull.mp4", A.s1)
s2 = frames(ROOT + "S2_chain_break.mp4", A.s2)
witch = sorted(glob.glob(os.path.join(A.witch, "*.png")) + glob.glob(os.path.join(A.witch, "*.jpg"))) if A.witch else sys.exit("需要 --witch 帧目录（先用 comfyui/hd.py 把 footage/W2_witch.mp4 放大、补帧）")
SF1 = A.src_fps if A.s1 else 24
SF2 = A.src_fps if A.s2 else 24
SFW = A.src_fps if A.witch else 24
cache = {}
n = round(LEN * FPS)
for i in range(n):
    t = i / FPS
    if t < T_S2:
        key = ("s1", min(len(s1) - 1, round(t * 1.4 * (SF1))))
    elif t < T_HOLD:
        u = t - T_S2
        src = u * 2 if u < 0.7 else 1.4 + (u - 0.7)
        key = ("s2", min(len(s2) - 1, round(src * (SF2))))
    elif t < T_WITCH:
        key = ("s2", len(s2) - 1)
    else:
        key = ("w", min(len(witch) - 1, int((t - T_WITCH) * (SFW) + 1e-6)))
    if key not in cache:
        cache.clear()
        src = {"s1": s1, "s2": s2}.get(key[0])
        item = src[key[1]] if src else witch[key[1]]
        cache[key] = fit(Image.open(item).convert("RGB") if isinstance(item, str) else item)
    cache[key].save(os.path.join(out, f"{i + 1:04d}.jpg"), quality=95)
print("写好", n, "帧 →", out)
