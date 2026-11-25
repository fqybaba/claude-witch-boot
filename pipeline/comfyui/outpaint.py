"""把图往外扩（外延补画）：原图缩小放进 1920x1080 画布的指定位置，空出来的地方让 ComfyUI 补画，再把原图贴回去。
用法（ComfyUI 自带的 Python）：
  python.exe -I outpaint.py 原图 输出.png --scale 0.92 --left 196 --top 0 --prompt-file 提示词 [--seed 5] [--lora 文件:强度]
"""

import argparse, io, json, sys, time, urllib.request
from PIL import Image, ImageFilter, ImageOps
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from gen import NEG, CKPT, upload, call, add_loras

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--scale", type=float, default=0.92)
ap.add_argument("--left", type=int, default=196)
ap.add_argument("--top", type=int, default=0)
ap.add_argument("--prompt-file", required=True)
ap.add_argument("--seed", type=int, default=5)
ap.add_argument("--port", type=int, default=8188)
ap.add_argument("--lora", action="append", default=[])
ap.add_argument("--neg-extra", default="")
a = ap.parse_args()

W, H = 1920, 1080
src = Image.open(a.src).convert("RGB")
sw, sh = (
    round(src.width * a.scale * W / src.width),
    round(src.height * a.scale * H / src.height),
)
small = src.resize((sw, sh), Image.LANCZOS)

# 初始画面：空白处先用镜像 + 模糊垫底，补画时颜色更容易接上
canvas = Image.new("RGB", (W, H))
big = ImageOps.mirror(src.resize((W, H), Image.LANCZOS)).filter(
    ImageFilter.GaussianBlur(18)
)
canvas.paste(big, (0, 0))
canvas.paste(small, (a.left, a.top))
# 遮罩：原图以外的地方要补画（往原图里多吃 24 像素，接缝更自然）
keep = Image.new("L", (W, H), 0)
keep.paste(
    255,
    (
        a.left + 24,
        a.top + (24 if a.top > 0 else 0),
        a.left + sw - (24 if a.left + sw < W else 0),
        a.top + sh - 24,
    ),
)
rgba = canvas.copy()
rgba.putalpha(keep)  # LoadImage 把透明的地方当成要补画的遮罩
tmp = a.out + ".in.png"
rgba.save(tmp)
name = upload(a.port, tmp)

pos = open(a.prompt_file, encoding="utf-8").read().strip()
neg = NEG + (", " + a.neg_extra if a.neg_extra else "")
wf = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["1", 1]}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
    "30": {"class_type": "LoadImage", "inputs": {"image": name}},
    "40": {
        "class_type": "VAEEncodeForInpaint",
        "inputs": {
            "pixels": ["30", 0],
            "vae": ["1", 2],
            "mask": ["30", 1],
            "grow_mask_by": 16,
        },
    },
    "5": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["40", 0],
            "seed": a.seed,
            "steps": 30,
            "cfg": 5.5,
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "denoise": 1.0,
        },
    },
    "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
    "7": {
        "class_type": "SaveImage",
        "inputs": {"images": ["6", 0], "filename_prefix": "outpaint"},
    },
}
wf = add_loras(wf, a.lora)
pid = call(a.port, "/prompt", {"prompt": wf})["prompt_id"]
print("queued", pid, flush=True)
while True:
    h = call(a.port, f"/history/{pid}")
    if pid in h:
        st = h[pid]["status"]["status_str"]
        print("status:", st)
        im = [i for o in h[pid]["outputs"].values() for i in o.get("images", [])][0]
        q = f"/view?filename={im['filename']}&subfolder={im['subfolder']}&type=output"
        with urllib.request.urlopen(f"http://127.0.0.1:{a.port}{q}", timeout=60) as r:
            gen = (
                Image.open(io.BytesIO(r.read()))
                .convert("RGB")
                .resize((W, H), Image.LANCZOS)
            )
        break
    time.sleep(3)
# 原图贴回去（边缘羽化 24 像素）
feather = keep.filter(ImageFilter.GaussianBlur(10))
out = Image.composite(canvas, gen, feather)
out.save(a.out)
print("写好", a.out)
