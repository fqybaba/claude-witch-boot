"""高清化：AI 放大（Real-ESRGAN animevideov3）+ AI 补帧（RIFE 4.7）。
用 ComfyUI 的虚拟环境跑（有 torch / spandrel），模型在 tools_dl/ 里：
  python.exe hd.py up  输入(视频或图片或帧目录)  输出目录  --w 2560 --h 1440      # 每帧放大 4 倍再缩到目标尺寸（cover 裁切）
  python.exe hd.py vfi 帧目录  输出目录  --mul 5                                  # 每两帧之间补 mul-1 帧（24fps × 5 = 120fps）
输出都是 JPG（质量 96），文件名 0001.jpg 起。
"""

import argparse, glob, os, sys, time
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESRGAN = os.path.join(ROOT, "tools_dl", "esrgan", "realesr-animevideov3.pth")
RIFE = os.path.join(ROOT, "tools_dl", "rife", "rife47.pth")
dev = torch.device("cuda")


def load_frames(src):
    if os.path.isdir(src):
        fs = sorted(
            glob.glob(os.path.join(src, "*.png"))
            + glob.glob(os.path.join(src, "*.jpg"))
        )
        for f in fs:
            yield Image.open(f).convert("RGB")
    elif src.lower().endswith((".mp4", ".mov", ".webm")):
        import av

        for fr in av.open(src).decode(video=0):
            yield fr.to_image()
    else:
        yield Image.open(src).convert("RGB")


def to_t(im):
    return (
        torch.from_numpy(np.asarray(im)).permute(2, 0, 1).unsqueeze(0).float().div(255)
    )


def to_im(t):
    a = t.squeeze(0).clamp(0, 1).mul(255).round().byte().permute(1, 2, 0).cpu().numpy()
    return Image.fromarray(a)


def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def cmd_up(a):
    from spandrel import ModelLoader

    m = ModelLoader().load_from_file(ESRGAN).model.to(dev).eval().half()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    n = 0
    with torch.inference_mode():
        for im in load_frames(a.src):
            y = m(to_t(im).to(dev).half()).float()
            big = to_im(y)
            out = cover(big, a.w, a.h) if a.w else big
            if a.blend < 1:   # 写实镜头：放大结果和普通放大按比例混合，保留皮革、木纹这类细纹理
                plain = cover(im, out.width, out.height)
                out = Image.blend(plain, out, a.blend)
            n += 1
            out.save(os.path.join(a.out, f"{n:04d}.jpg"), quality=96)
            if n % 20 == 0:
                print(f"  放大 {n} 帧 {time.time() - t0:.0f}s", flush=True)
    print(f"放大完成 {n} 帧 → {a.out}  {time.time() - t0:.0f}s")


def load_rife():
    sys.path.insert(0, os.path.join(ROOT, "tools_dl", "rife"))
    import rife_arch

    m = rife_arch.IFNet(arch_ver="4.7")
    m.load_state_dict(torch.load(RIFE, map_location="cpu", weights_only=False))
    return m.eval().to(dev).half()


def cmd_vfi(a):
    m = load_rife()
    fs = sorted(
        glob.glob(os.path.join(a.src, "*.jpg"))
        + glob.glob(os.path.join(a.src, "*.png"))
    )
    os.makedirs(a.out, exist_ok=True)
    scale = [8 / a.scale, 4 / a.scale, 2 / a.scale, 1 / a.scale]
    t0 = time.time()
    n = 0
    prev = None
    with torch.inference_mode():
        for i, f in enumerate(fs):
            im = Image.open(f).convert("RGB")
            cur = to_t(im).to(dev).half()
            if prev is not None:
                for k in range(1, a.mul):
                    ts = torch.full(
                        (1, 1, 1, 1), k / a.mul, device=dev, dtype=torch.half
                    )
                    mid = m(prev, cur, ts, scale, False, True, False)
                    mid = mid[:, :, : im.height, : im.width]
                    n += 1
                    to_im(mid.float()).save(
                        os.path.join(a.out, f"{n:04d}.jpg"), quality=96
                    )
            n += 1
            im.save(os.path.join(a.out, f"{n:04d}.jpg"), quality=96)
            prev = cur
            if i % 10 == 0:
                print(f"  补帧 {i}/{len(fs)} {time.time() - t0:.0f}s", flush=True)
    print(f"补帧完成 {len(fs)} → {n} 帧 → {a.out}  {time.time() - t0:.0f}s")


ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["up", "vfi"])
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--w", type=int, default=0)
ap.add_argument("--h", type=int, default=0)
ap.add_argument("--blend", type=float, default=1.0); ap.add_argument("--mul", type=int, default=5)
ap.add_argument("--scale", type=float, default=1.0)   # 0.5 会让补出的帧整体偏 0.8 像素，画面抖
a = ap.parse_args()
{"up": cmd_up, "vfi": cmd_vfi}[a.cmd](a)
