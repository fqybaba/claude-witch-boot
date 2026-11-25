"""只重画一张图的脸部：裁出脸 -> 放大到 1024 -> 低 denoise 重绘 -> 缩回原尺寸，用羽化椭圆贴回去。

用 ComfyUI 自带的 Python 运行（需要 PIL）：
  standalone-env\\python.exe -I face_fix.py 原图.png 输出.png --box x0 y0 x1 y1 [--denoise 0.45] [--seed N]
"""

import argparse, io, json, sys, time, urllib.request, uuid
from PIL import Image, ImageDraw, ImageFilter

CKPT = "WAI-Nsfw-Illustrious-17.safetensors"
POS = (
    "masterpiece, best quality, amazing quality, 1girl, solo, face, close-up, orange hair, swept bangs, hair between eyes, "
    "half-closed eyes, light brown eyes, amber eyes, small pupils, beautiful detailed eyes, long eyelashes, "
    "looking at viewer, closed mouth, calm, aloof, expressionless, pale skin, small face, "
    "night, dark, moonlight, rim light, candlelight, muted colors"
)
NEG = (
    "bad quality, worst quality, worst detail, sketch, lowres, text, watermark, wide-eyed, glowing eyes, "
    "constricted pupils, large pupils, red eyes, open mouth, smile, saturated, high contrast"
)
PORT = 8188


def api(path, data=None, raw=None, ctype="application/json"):
    body = (
        raw
        if raw is not None
        else (json.dumps(data).encode() if data is not None else None)
    )
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", data=body, headers={"Content-Type": ctype}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def upload(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    b = uuid.uuid4().hex
    name = f"facefix_{b[:8]}.png"
    body = (
        (
            f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode()
        + buf.getvalue()
        + f'\r\n--{b}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{b}--\r\n'.encode()
    )
    return json.loads(
        api("/upload/image", raw=body, ctype=f"multipart/form-data; boundary={b}")
    )["name"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--box", type=int, nargs=4, required=True)
    ap.add_argument("--denoise", type=float, default=0.45)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--pos-file", help="换一套正向提示词（比如重画花饰时）")
    ap.add_argument("--lora", help="文件名:强度")
    ap.add_argument("--neg-extra", default="")
    ap.add_argument("--rect", action="store_true", help="用羽化矩形蒙版；贴着图片边缘的那几边不羽化")
    a = ap.parse_args()
    pos = open(a.pos_file, encoding="utf-8").read().strip() if a.pos_file else POS
    src = Image.open(a.src).convert("RGB")
    x0, y0, x1, y1 = a.box
    crop = src.crop(a.box)
    side = 1024
    big = crop.resize(
        (side, round(side * crop.height / crop.width / 8) * 8), Image.LANCZOS
    )
    name = upload(big)
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": pos, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": NEG + (", " + a.neg_extra if a.neg_extra else ""), "clip": ["1", 1]},
        },
        "4": {"class_type": "LoadImage", "inputs": {"image": name}},
        "5": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["4", 0], "vae": ["1", 2]},
        },
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["5", 0],
                "seed": a.seed,
                "steps": 24,
                "cfg": 5.5,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": a.denoise,
            },
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["6", 0], "vae": ["1", 2]},
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {"images": ["7", 0], "filename_prefix": "facefix_tmp"},
        },
    }
    if a.lora:
        name_, w = a.lora.rsplit(":", 1)
        wf["9"] = {
            "class_type": "LoraLoader",
            "inputs": {"model": ["1", 0], "clip": ["1", 1], "lora_name": name_,
                       "strength_model": float(w), "strength_clip": float(w)},
        }
        wf["2"]["inputs"]["clip"] = wf["3"]["inputs"]["clip"] = ["9", 1]
        wf["6"]["inputs"]["model"] = ["9", 0]
    pid = json.loads(api("/prompt", {"prompt": wf}))["prompt_id"]
    while True:
        h = json.loads(api(f"/history/{pid}"))
        if pid in h:
            break
        time.sleep(2)
    if h[pid]["status"]["status_str"] != "success":
        sys.exit(json.dumps(h[pid]["status"]["messages"])[:2000])
    im = h[pid]["outputs"]["8"]["images"][0]
    q = urllib.parse.urlencode(
        {"filename": im["filename"], "subfolder": im["subfolder"], "type": "output"}
    )
    fixed = (
        Image.open(io.BytesIO(api(f"/view?{q}")))
        .convert("RGB")
        .resize(crop.size, Image.LANCZOS)
    )
    # 羽化椭圆蒙版，只换中间，边缘和原图自然过渡
    m = int(min(crop.size) * 0.12)
    if a.rect:
        # 先画大一圈的蒙版再羽化，贴着原图边缘的那几边往外延伸，羽化就落在图外
        pad = 2 * m
        big_mask = Image.new("L", (crop.width + 2 * pad, crop.height + 2 * pad), 0)
        l = 0 if x0 == 0 else pad + m
        t = 0 if y0 == 0 else pad + m
        r = big_mask.width if x1 >= src.width else pad + crop.width - m
        b = big_mask.height if y1 >= src.height else pad + crop.height - m
        ImageDraw.Draw(big_mask).rectangle((l, t, r, b), fill=255)
        mask = big_mask.filter(ImageFilter.GaussianBlur(m * 0.6)).crop(
            (pad, pad, pad + crop.width, pad + crop.height))
    else:
        mask = Image.new("L", crop.size, 0)
        ImageDraw.Draw(mask).ellipse((m, m, crop.width - m, crop.height - m), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(m * 0.8))
    out = src.copy()
    out.paste(fixed, (x0, y0), mask)
    out.save(a.out)
    print("saved", a.out)


if __name__ == "__main__":
    import urllib.parse

    main()
