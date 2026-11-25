"""魔女版开屏音效（暗黑魔法调性），用 numpy 合成，不用任何外部素材，输出 48kHz 立体声 WAV。
时间点和 intro_magic.html 的分镜对齐（INTRO_LEN = 12.4 秒）。用 ComfyUI 自带的 Python 跑：
  python.exe -I sfx_magic.py 输出.wav
调性：D 小调。底噪 + 烛火 → 封印脉动越来越急 → 裂纹 → 崩断的金属声和锁链 → 光缝的细高音
→ 法阵升起的低吟和泛音 → 定形的低锣 → 字母翻面的玻璃轻响 → 坍缩的倒吸 → 炸开的低频冲击
→ 魔女现身的冷和弦（Dm add9 → Gm add9/D → C#dim7）+ 竖琴分解 → 烧穿的火声 → 欢迎处一声冷钟。
"""
import sys, wave
import numpy as np

SR = 48000
LEN = 12.4
N = int(SR * LEN)
rng = np.random.default_rng(11)
L = np.zeros(N); R = np.zeros(N)


def t_of(n):
    return np.arange(n) / SR


def add(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N:
        return
    s = sig[: N - i] * gain
    L[i:i + len(s)] += s * np.sqrt((1 - pan) / 2) * np.sqrt(2)
    R[i:i + len(s)] += s * np.sqrt((1 + pan) / 2) * np.sqrt(2)


def lowpass(x, cutoff):
    """一阶低通，cutoff 可以是数组（随时间变化）。"""
    a = np.exp(-2 * np.pi * np.broadcast_to(cutoff, x.shape) / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = a[i] * acc + (1 - a[i]) * x[i]
        y[i] = acc
    return y


def lp2(x, cutoff):
    return lowpass(lowpass(x, cutoff), cutoff)


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def fade_env(n, a, r):
    t = t_of(n); d = n / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.clip((d - t) / max(r, 1e-4), 0, 1)


def nfreq(name):
    """音名 → 频率，如 'D3'、'Bb4'、'C#5'。"""
    names = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    k = names[name[0]]; rest = name[1:]
    if rest[0] == '#': k += 1; rest = rest[1:]
    elif rest[0] == 'b': k -= 1; rest = rest[1:]
    midi = 12 * (int(rest) + 1) + k
    return 440 * 2 ** ((midi - 69) / 12)


# ---------- 音色 ----------
def bell(freq, dur, bright=1.0, decay=1.0):
    """钟：非谐泛音，长衰减。"""
    t = t_of(int(dur * SR))
    partials = [(0.5, 0.35), (1, 1), (1.19, 0.3 * bright), (1.56, 0.25 * bright), (2.0, 0.2 * bright), (2.74, 0.12 * bright), (3.76, 0.06 * bright)]
    s = sum(a * np.sin(2 * np.pi * freq * m * t + m) * np.exp(-t * (0.9 + m * 0.7) / decay) for m, a in partials)
    return s * np.minimum(1, t / 0.003)


def glass(freq, dur=0.9):
    t = t_of(int(dur * SR))
    s = np.sin(2 * np.pi * freq * t) * np.exp(-t * 6) + 0.35 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 11)
    return s * np.minimum(1, t / 0.002)


def thump(f=58, dur=0.9):
    t = t_of(int(dur * SR))
    ff = f * (1 + 0.6 * np.exp(-t * 30))
    return np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-t * 6) * np.minimum(1, t / 0.004)


def clank(dur=1.6, base=310):
    """金属断裂：一组非谐的金属泛音 + 很短的噪声冲击。"""
    t = t_of(int(dur * SR))
    ratios = [1, 1.47, 2.09, 2.56, 3.31, 4.17, 5.43]
    s = sum(np.sin(2 * np.pi * base * r * t + r * 3) * np.exp(-t * (3 + r * 1.6)) / (1 + 0.4 * r) for r in ratios)
    hit = highpass(rng.standard_normal(len(t)), 1500) * np.exp(-t * 60)
    return 0.8 * s + 0.7 * hit


def chain_jingle(dur=1.2, n=14, seed=0):
    """锁链碎裂：一串高低不一的小金属声，越来越稀。"""
    r = np.random.default_rng(seed)
    out = np.zeros(int(dur * SR))
    for k in range(n):
        at = (r.uniform(0, 1) ** 1.8) * dur * 0.85
        f = r.uniform(1800, 4200)
        tt = t_of(int(0.35 * SR))
        s = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.53 * tt)) * np.exp(-tt * r.uniform(18, 35))
        i = int(at * SR); out[i:i + len(s)] += s[: len(out) - i] * r.uniform(0.25, 0.7)
    return out


def crackle(dur, density=40, seed=0, bright=3000):
    """火的噼啪：随机小脉冲。density 可以是随时间变化的函数 f(秒)。"""
    r = np.random.default_rng(seed)
    n = int(dur * SR); out = np.zeros(n)
    t = 0.0
    while True:
        rate = density(t) if callable(density) else density
        t += r.exponential(1 / max(rate, 1e-3))
        if t >= dur: break
        i = int(t * SR); ln = int(r.uniform(0.002, 0.012) * SR)
        burst = r.standard_normal(ln) * np.exp(-np.arange(ln) / (ln / 4)) * r.uniform(0.2, 1.0)
        out[i:i + ln] += burst[: n - i]
    return highpass(out, bright)


def whoosh(dur, peak=0.5, lo=300, hi=4000):
    t = t_of(int(dur * SR))
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    cut = lo + hi * np.exp(-((t / dur - peak) ** 2) / 0.05)
    return lowpass(rng.standard_normal(len(t)), cut) * e


def inhale(dur):
    """坍缩的倒吸：噪声越来越亮越来越响，最后猛地停住。"""
    t = t_of(int(dur * SR)); u = t / dur
    noise = lp2(rng.standard_normal(len(t)), 150 + 5200 * u ** 2.5)
    f = 70 * (1 + 3 * u ** 3)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.4 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    e = u ** 2.4 * np.clip((dur - t) / 0.012, 0, 1)
    return (0.9 * noise + 0.35 * tone) * e


def impact(dur=3.0):
    t = t_of(int(dur * SR))
    f = 28 + 70 * np.exp(-t * 7)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.3)
    body = lp2(rng.standard_normal(len(t)), 900) * np.exp(-t * 3.2)
    crack = highpass(rng.standard_normal(len(t)), 1200) * np.exp(-t * 22)
    return 1.0 * sub + 0.5 * body + 0.3 * crack


def choir(dur, root, attack=0.8, release=1.0, vowel=(700, 1150), vib=5.2, seed=0):
    """低吟：带元音共振峰的谐波合成，轻微颤音和合唱式失谐。"""
    t = t_of(int(dur * SR))
    out = np.zeros(len(t))
    for d, det in enumerate([-0.004, 0.0, 0.005]):
        f0 = root * (1 + det) * (1 + 0.004 * np.sin(2 * np.pi * vib * t + d * 2))
        ph = 2 * np.pi * np.cumsum(f0) / SR
        for h in range(1, 28):
            fh = root * h
            if fh > 5000: break
            w = sum(np.exp(-((fh - F) / (F * 0.18)) ** 2) for F in vowel) + 0.5 / h
            out += w * np.sin(h * ph + h * d) / 3
    return out / np.max(np.abs(out)) * fade_env(len(t), attack, release)


def overtones(dur, root, partials=(8, 10, 12, 16), attack=1.2, release=0.8):
    """泛音：同一根音的高次谐波，慢慢闪烁。"""
    t = t_of(int(dur * SR)); out = np.zeros(len(t))
    for k, p in enumerate(partials):
        am = 0.5 + 0.5 * np.sin(2 * np.pi * (0.7 + 0.37 * k) * t + k)
        out += np.sin(2 * np.pi * root * p * t + k) * am / (1 + 0.3 * k)
    return out / len(partials) * fade_env(len(t), attack, release)


def pad(dur, notes, attack=0.9, release=1.0, cut=1800):
    t = t_of(int(dur * SR)); s = np.zeros(len(t))
    for i, nm in enumerate(notes):
        f = nfreq(nm)
        for det in (-0.003, 0.003):
            ph = 2 * np.pi * f * (1 + det) * t + i
            s += np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
    s *= 1 + 0.12 * np.sin(2 * np.pi * 0.3 * t)
    return lowpass(s, cut) / (2 * len(notes)) * fade_env(len(t), attack, release)


def pluck(freq, dur=1.6):
    """竖琴式拨弦。"""
    t = t_of(int(dur * SR))
    s = sum(np.sin(2 * np.pi * freq * h * t) * np.exp(-t * (2.5 + h * 1.4)) / h for h in range(1, 6))
    return s * np.minimum(1, t / 0.002)


# ---------- 时间线 ----------
# 底噪（0–6.4）：极低的 D 与 A，缓慢起伏；加一层很暗的风噪
d = t_of(int(6.6 * SR))
drone = (np.sin(2 * np.pi * 36.71 * d) + 0.6 * np.sin(2 * np.pi * 55.0 * d + 1) + 0.25 * np.sin(2 * np.pi * 73.42 * d)) \
    * (1 + 0.25 * np.sin(2 * np.pi * 0.23 * d)) * fade_env(len(d), 1.6, 0.5)
add(drone, 0, 0.21)
air = lp2(rng.standard_normal(len(d)), 380) * fade_env(len(d), 2.0, 0.5)
add(air, 0, 0.10, -0.2)

# 烛火：轻微的噼啪 + 低低的火焰气声（① 和 ②③，坍缩时收掉）
fire_len = 6.2
add(crackle(fire_len, 6, seed=1, bright=2500) * fade_env(int(fire_len * SR), 1.0, 0.4), 0.2, 0.09, -0.5)
add(crackle(fire_len, 5, seed=2, bright=2500) * fade_env(int(fire_len * SR), 1.0, 0.4), 0.2, 0.08, 0.5)
fh = t_of(int(fire_len * SR))
add(lp2(rng.standard_normal(len(fh)), 900) * (0.6 + 0.4 * np.sin(2 * np.pi * 1.3 * fh)) * fade_env(len(fh), 1.2, 0.5), 0.2, 0.025)

# 封印脉动：每次封面符文最亮时一下低沉的“心跳”，越来越急、越来越响
tt = np.arange(0.4, 2.3, 1 / 2000)
ph = 0.42 * tt + 0.85 * np.maximum(0, tt - 1.3) ** 2      # 和画面里的相位一样（单位：周）
peaks = tt[1:][np.floor(ph[1:] - 0.5) > np.floor(ph[:-1] - 0.5)]
for k, at in enumerate(peaks):
    g_ = 0.18 + 0.32 * ((at - 0.4) / 1.9) ** 1.5
    add(thump(52 + 4 * k, 0.9), at, g_)
    add(lowpass(rng.standard_normal(int(0.4 * SR)), 500) * np.exp(-t_of(int(0.4 * SR)) * 9), at, g_ * 0.25)

# 裂纹：1.55–2.3 越来越密的细碎裂声 + 低低的上扬张力
add(crackle(0.75, lambda s: 20 + 180 * (s / 0.75) ** 2, seed=3, bright=1800) * np.linspace(0.3, 1, int(0.75 * SR)), 1.55, 0.22, 0.1)
ten = t_of(int(0.75 * SR))
add(np.sin(2 * np.pi * np.cumsum(60 * (1 + 0.5 * (ten / 0.75) ** 2)) / SR) * (ten / 0.75) ** 2, 1.55, 0.16)
# 锁扣冒电弧：1.8–2.3 几下很短的高频滋滋
for k in range(7):
    at = 1.82 + k * 0.066
    add(highpass(rng.standard_normal(int(0.03 * SR)), 3500) * np.exp(-t_of(int(0.03 * SR)) * 120), at, 0.05, 0.3 if k % 2 else -0.3)

# ② 封印崩断（2.3）：金属断裂 + 锁链碎裂 + 一记低闷的冲击
add(clank(1.8, 290), 2.30, 0.42, -0.1)
add(clank(1.4, 410), 2.31, 0.22, 0.25)
add(chain_jingle(1.3, 16, seed=4), 2.32, 0.20, -0.4)
add(chain_jingle(1.3, 14, seed=5), 2.34, 0.18, 0.4)
add(impact(2.0), 2.30, 0.34)
# 光缝：一条极细的高音，在黑里亮着（2.35–3.1）
sl = t_of(int(0.8 * SR))
add((np.sin(2 * np.pi * 1174.7 * sl) + 0.3 * np.sin(2 * np.pi * 1760 * sl)) * fade_env(len(sl), 0.08, 0.35) * (1 + 0.3 * np.sin(2 * np.pi * 7 * sl)), 2.35, 0.035)
# 碎片落地：几下暗的小金属声
for k, at in enumerate([2.78, 2.9, 3.02, 3.2]):
    add(clank(0.4, 700 + 150 * k) * 0.5, at, 0.05, (-1) ** k * 0.5)

# 书页上的印记亮起（2.72）：一声很低的钟，和根音成小二度，阴冷
add(bell(nfreq('D3'), 3.5, 0.6, 1.4), 2.72, 0.16, -0.15)
add(bell(nfreq('Eb3'), 3.0, 0.4, 1.2), 2.80, 0.06, 0.15)

# 法阵升起（2.85–6.0）：低吟（D2 上的 “啊”）+ 泛音，越来越满，Claude 段收一点
ch = choir(3.4, nfreq('D2'), attack=1.0, release=0.5, vowel=(650, 1080), seed=0)
add(ch * np.minimum(1, 0.55 + 0.45 * t_of(len(ch)) / 1.3), 2.85, 0.30, -0.1)
ch2 = choir(3.2, nfreq('A2'), attack=1.4, release=0.5, vowel=(500, 900), vib=4.6, seed=1)
add(ch2, 3.05, 0.16, 0.15)
add(overtones(3.2, nfreq('D2'), (8, 12, 15, 16, 20), attack=1.3, release=0.5), 2.95, 0.06, 0.2)
add(whoosh(1.4, 0.55, 200, 2200), 2.85, 0.10)                    # 升起的气流
# 法阵定形（4.0）：一记低锣
add(bell(nfreq('D2'), 4.0, 0.9, 2.2), 4.0, 0.32)
add(lowpass(rng.standard_normal(int(1.2 * SR)), 300) * np.exp(-t_of(int(1.2 * SR)) * 3), 4.0, 0.10)

# ③ 字母翻面（4.25 + k*0.08 + 0.62）：六声玻璃轻响，D 小调分解（D F A D F A）
for k, nm in enumerate(['D5', 'F5', 'A5', 'D6', 'F6', 'A6']):
    add(glass(nfreq(nm), 1.0), 4.25 + k * 0.08 + 0.62, 0.07, -0.5 + k * 0.2)
# 副标题（5.3）：一层极轻的高泛音
add(overtones(1.0, nfreq('D3'), (12, 16, 20), attack=0.3, release=0.6), 5.3, 0.03)

# ④ 坍缩的倒吸（5.85–6.36），6.36 炸开的低频冲击 + 火星
add(inhale(0.51), 5.85, 0.42)
add(impact(3.2), 6.36, 0.85)
add(crackle(1.0, lambda s: 400 * np.exp(-s * 4), seed=6, bright=2500), 6.37, 0.18, -0.3)
add(crackle(1.0, lambda s: 400 * np.exp(-s * 4), seed=7, bright=2500), 6.38, 0.18, 0.3)
add(whoosh(0.9, 0.15, 200, 3000), 6.36, 0.14)

# ⑤ 魔女现身（6.5–9.95）：冷而华丽的和弦，Dm add9 → Gm add9/D → C#dim7（不解决，等欢迎处）
add(pad(2.1, ['D2', 'A2', 'D3', 'F3', 'A3', 'E4']), 6.5, 0.85)
add(pad(1.6, ['D2', 'G2', 'Bb2', 'D3', 'A3', 'D4']), 8.3, 1.0)
add(pad(1.45, ['C#3', 'E3', 'G3', 'Bb3', 'E4']), 9.6, 0.9)
add(overtones(3.4, nfreq('D2'), (12, 16, 18, 24), attack=1.0, release=1.0), 6.6, 0.035, 0.3)
# 竖琴式分解（Dm：D A D F A D E），冷亮
for k, nm in enumerate(['D3', 'A3', 'D4', 'F4', 'A4', 'D5', 'E5']):
    add(pluck(nfreq(nm), 2.0), 6.62 + k * 0.11, 0.16, -0.4 + k * 0.13)
# 台词进来时（7.3）一下很轻的低钟
add(bell(nfreq('A2'), 3.0, 0.5, 1.5), 7.3, 0.09)
# 第二个和弦处再拨一串（G D G B♭）
for k, nm in enumerate(['G3', 'D4', 'G4', 'Bb4']):
    add(pluck(nfreq(nm), 1.8), 8.32 + k * 0.12, 0.13, 0.4 - k * 0.2)

# ⑥ 烧穿（9.95–10.8）：火焰吞纸的噼啪和气流
add(crackle(1.0, lambda s: 60 + 500 * np.sin(np.pi * min(1, s / 0.9)), seed=8, bright=1500), 9.92, 0.24, 0.2)
add(whoosh(1.0, 0.45, 300, 2600), 9.92, 0.14, 0.3)

# 欢迎（10.4）：一声冷钟（D5，非谐泛音），垫一个 Dm 的低音
add(bell(nfreq('D5'), 3.0, 1.0, 1.3), 10.42, 0.26)
add(bell(nfreq('A4'), 2.6, 0.6, 1.1), 10.44, 0.07, 0.3)
add(pad(1.95, ['D2', 'A2', 'D3', 'F3']), 10.45, 0.45)

# ---------- 混响 + 收尾 ----------
def reverb(x, secs=2.4, mix=0.3):
    n = int(secs * SR)
    ir = rng.standard_normal(n) * np.exp(-t_of(n) * 5.0 / secs)
    ir = lowpass(ir, 3800); ir /= np.sqrt((ir ** 2).sum())
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
    return x * (1 - mix) + wet * mix * 3


L = reverb(L); R = reverb(R)
fade = np.clip((LEN - t_of(N)) / 0.8, 0, 1)   # 最后 0.8 秒淡出，接循环背景（静音）
L *= fade; R *= fade
peak = max(np.abs(L).max(), np.abs(R).max())
L /= peak / 0.89; R /= peak / 0.89

out = (np.stack([L, R], 1) * 32767).astype('<i2')
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
print('写好', sys.argv[1], f'{LEN}s')
