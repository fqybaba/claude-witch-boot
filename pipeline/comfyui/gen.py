"""通过 ComfyUI 本地 API 出定妆图（两遍：1344x768 底图 -> 放大 1.5 倍 -> 重绘 denoise 0.4）。

用法：python gen.py [--prompt-file 文件] [--seed N] [--batch N] [--prefix 名字] [--port 8188]
参数和提示词来自 docs/角色设定与提示词.md。结果保存在 ComfyUI-Shared\\output。
"""

import argparse, json, random, sys, time, urllib.request

CKPT = "WAI-Nsfw-Illustrious-17.safetensors"

POS = (
    "masterpiece, best quality, amazing quality, 1girl, solo, orange hair, very long hair, straight hair, "
    "hair between eyes, sidelocks, orange eyes, hair flower, orange flower, hair ribbon, black ribbon, white ribbon, "
    "earrings, white capelet, gold embroidery, lace trim, white shirt, frilled shirt, frills, black ascot, orange brooch, "
    "puffy long sleeves, frilled sleeves, black corset, underbust, gold chain, tassel, black skirt, long skirt, "
    "layered skirt, frilled skirt, holding book, open book, glowing book, looking down, closed mouth, calm, upper body, "
    "indoors, library, bookshelf, gothic architecture, arched window, stained glass, moonlight, light rays, candle, "
    "candlelight, light particles, floating paper, night, dark, rim light, backlighting, depth of field, "
    "blurry background, cinematic lighting, muted colors"
)
NEG = "bad quality, worst quality, worst detail, sketch, censor, nsfw, lowres, bad hands, extra fingers, text, watermark, signature, wide-eyed, glowing eyes, constricted pupils, large pupils, red eyes, open mouth, smile, saturated, high contrast"


def build(pos, neg, seed, batch, prefix):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": pos, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": neg, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 1344, "height": 768, "batch_size": batch},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": 28,
                "cfg": 5.5,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "ImageScaleBy",
            "inputs": {"image": ["6", 0], "upscale_method": "lanczos", "scale_by": 1.5},
        },
        "8": {
            "class_type": "VAEEncodeTiled",
            "inputs": {
                "pixels": ["7", 0],
                "vae": ["1", 2],
                "tile_size": 1024,
                "overlap": 64,
                "temporal_size": 64,
                "temporal_overlap": 8,
            },
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["8", 0],
                "seed": seed,
                "steps": 20,
                "cfg": 5.5,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 0.4,
            },
        },
        "10": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": ["9", 0],
                "vae": ["1", 2],
                "tile_size": 1024,
                "overlap": 64,
                "temporal_size": 64,
                "temporal_overlap": 8,
            },
        },
        "11": {
            "class_type": "SaveImage",
            "inputs": {"images": ["10", 0], "filename_prefix": prefix},
        },
    }


def add_loras(wf, loras):
    """在模型后面串上 LoRA（每个是 "文件名:强度"），再把用到模型和 CLIP 的节点改接到最后一个 LoRA。"""
    model, clip = ["1", 0], ["1", 1]
    for i, spec in enumerate(loras):
        name, w = spec.rsplit(":", 1)
        nid = str(20 + i)
        wf[nid] = {
            "class_type": "LoraLoader",
            "inputs": {"model": model, "clip": clip, "lora_name": name,
                       "strength_model": float(w), "strength_clip": float(w)},
        }
        model, clip = [nid, 0], [nid, 1]
    for nid in ("2", "3"):
        wf[nid]["inputs"]["clip"] = clip
    for nid in ("5", "9"):
        if nid in wf:
            wf[nid]["inputs"]["model"] = model
    return wf


def use_init(wf, image_name, denoise):
    """图生图：不从空白开始，直接把上传的图编码成潜空间，单遍重绘。"""
    for nid in ("4", "5", "6", "7"):
        del wf[nid]
    wf["30"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    wf["8"]["inputs"]["pixels"] = ["30", 0]
    wf["9"]["inputs"]["denoise"] = denoise
    wf["9"]["inputs"]["steps"] = 28
    return wf


def upload(port, path):
    import uuid
    b = uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="image"; filename="init_{b[:8]}.png"\r\n'
            f"Content-Type: image/png\r\n\r\n").encode() + open(path, "rb").read() + \
        f'\r\n--{b}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n--{b}--\r\n'.encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/upload/image", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["name"]


def call(port, path, data=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:2000]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file")
    ap.add_argument("--seed", type=int, default=random.randrange(2**32))
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--prefix", default="claude_dzt")
    ap.add_argument("--port", type=int, default=8188)
    ap.add_argument("--lora", action="append", default=[], help="文件名:强度，可以写多次")
    ap.add_argument("--neg-extra", default="", help="追加到反向提示词后面")
    ap.add_argument("--init", help="图生图：底图路径（尺寸要能被 8 整除）")
    ap.add_argument("--denoise", type=float, default=0.5, help="图生图的重绘强度")
    a = ap.parse_args()
    pos = open(a.prompt_file, encoding="utf-8").read().strip() if a.prompt_file else POS
    neg = NEG + (", " + a.neg_extra if a.neg_extra else "")
    wf = build(pos, neg, a.seed, a.batch, a.prefix)
    if a.init:
        wf = use_init(wf, upload(a.port, a.init), a.denoise)
    wf = add_loras(wf, a.lora)
    pid = call(a.port, "/prompt", {"prompt": wf})["prompt_id"]
    print(f"queued {pid} seed={a.seed} batch={a.batch}", flush=True)
    t0 = time.time()
    while True:
        h = call(a.port, f"/history/{pid}")
        if pid in h:
            st = h[pid]["status"]
            print("status:", st["status_str"], f"{time.time() - t0:.0f}s")
            if st["status_str"] != "success":
                print(json.dumps(st["messages"], ensure_ascii=False)[:2000])
            for out in h[pid]["outputs"].values():
                for im in out.get("images", []):
                    print("image:", im["subfolder"], im["filename"])
            return
        time.sleep(3)


if __name__ == "__main__":
    main()
