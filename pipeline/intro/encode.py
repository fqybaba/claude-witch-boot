"""PNG 帧序列（+ 可选 WAV）→ H.264 MP4。用 ComfyUI 自带的 Python（有 PyAV 和 libx264）：
  python.exe -I encode.py 帧目录 输出.mp4 [--audio 音效.wav] [--fps 30] [--crf 17]
"""
import argparse, glob, os, wave
import av
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("frames"); ap.add_argument("out")
ap.add_argument("--audio"); ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--crf", default="17")
a = ap.parse_args()

files = sorted(glob.glob(os.path.join(a.frames, "*.png")))
out = av.open(a.out, "w")
vs = out.add_stream("libx264", rate=a.fps)
vs.width, vs.height = Image.open(files[0]).size   # 跟着帧的尺寸走（1920x1080 或 2560x1440）
vs.pix_fmt = "yuv420p"
vs.options = {"crf": a.crf, "preset": "slow", "tune": "film", "movflags": "+faststart"}
vs.codec_context.color_range = 1  # tv range，播放器兼容性最好

aus = None
if a.audio:
    w = wave.open(a.audio, "rb")
    sr, ch = w.getframerate(), w.getnchannels()
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, ch)
    aus = out.add_stream("aac", rate=sr)
    aus.layout = "stereo"; aus.bit_rate = 192000

for f in files:
    frame = av.VideoFrame.from_image(Image.open(f).convert("RGB"))
    for p in vs.encode(frame):
        out.mux(p)
for p in vs.encode():
    out.mux(p)

if aus is not None:
    step = 1024
    for i in range(0, len(pcm), step):
        chunk = np.ascontiguousarray(pcm[i:i + step].T)
        af = av.AudioFrame.from_ndarray(chunk, format="s16p", layout="stereo")
        af.sample_rate = sr; af.pts = i
        for p in aus.encode(af):
            out.mux(p)
    for p in aus.encode():
        out.mux(p)
out.close()
print(f"写好 {a.out}：{len(files)} 帧，{len(files) / a.fps:.2f}s", "带音轨" if aus else "无音轨")
