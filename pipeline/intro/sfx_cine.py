"""电影感版开屏音效（由 make_sfx_cine.py 从 sfx_magic.py 生成，别手改；要改时间线改 make_sfx_cine.py）。
时间点和 intro_cine.html 对齐（INTRO_LEN = 13.5 秒）：
  0–3.6 抽书（书震动、锁链响、滑出书架、落灰）→ 4.7 锁链崩断、紫光碎掉 → 5.8 书翻开、翻页
  → 6.6 法阵升起 → 7.0 Claude 字标 → 7.9 倒吸 → 8.4 炸开 → 魔女现身的冷和弦 → 11.6 欢迎处一声冷钟。
"""
import sys, wave
import numpy as np

SR = 48000
LEN = 13.5
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
# 底噪（0–8.6）：极低的 D 与 A，缓慢起伏；加一层很暗的风噪
d = t_of(int(8.6 * SR))
drone = (np.sin(2 * np.pi * 36.71 * d) + 0.6 * np.sin(2 * np.pi * 55.0 * d + 1) + 0.25 * np.sin(2 * np.pi * 73.42 * d)) \
    * (1 + 0.25 * np.sin(2 * np.pi * 0.23 * d)) * fade_env(len(d), 1.6, 0.5)
add(drone, 0, 0.21)
air = lp2(rng.standard_normal(len(d)), 380) * fade_env(len(d), 2.0, 0.5)
add(air, 0, 0.10, -0.2)
# 远处的烛火
fire_len = 8.0
add(crackle(fire_len, 4, seed=1, bright=2500) * fade_env(int(fire_len * SR), 1.0, 0.4), 0.2, 0.05, 0.5)

# ① 抽书（0–3.6）：书在书架里震动，锁链轻响；1.0 起皮面蹭着木头滑出来；2.4 离开书架，落灰
for k, at in enumerate([0.45, 0.8, 1.1, 1.35]):
    add(thump(48 + 3 * k, 0.7), at, 0.14 + 0.05 * k)
add(chain_jingle(0.9, 6, seed=20) * 0.6, 0.5, 0.08, -0.3)
add(chain_jingle(1.4, 9, seed=21) * 0.7, 1.2, 0.10, 0.2)
sl = t_of(int(1.5 * SR))
add(lp2(rng.standard_normal(len(sl)), 700 + 500 * sl / 1.5) * fade_env(len(sl), 0.5, 0.25) * (1 + 0.4 * np.sin(2 * np.pi * 9 * sl)), 1.0, 0.16, -0.15)
add(whoosh(1.2, 0.6, 200, 1800), 1.8, 0.12, -0.1)
add(thump(44, 1.0), 2.45, 0.20)
add(lowpass(rng.standard_normal(int(1.0 * SR)), 1400) * np.exp(-t_of(int(1.0 * SR)) * 4), 2.45, 0.07, -0.3)   # 落灰
add(chain_jingle(1.0, 7, seed=22) * 0.6, 2.5, 0.08, 0.3)
add(overtones(1.6, nfreq('D2'), (8, 12, 15), attack=0.8, release=0.5), 2.4, 0.05, 0.2)                        # 悬在半空的紫光

# ② 蓄力（3.6–4.7）：书越晃越厉害，锁链绷紧
add(crackle(1.1, lambda s: 20 + 200 * (s / 1.1) ** 2, seed=3, bright=1800) * np.linspace(0.3, 1, int(1.1 * SR)), 3.6, 0.20, 0.1)
ten = t_of(int(1.1 * SR))
add(np.sin(2 * np.pi * np.cumsum(60 * (1 + 0.5 * (ten / 1.1) ** 2)) / SR) * (ten / 1.1) ** 2, 3.6, 0.17)
for k, at in enumerate([3.7, 4.0, 4.25, 4.45, 4.6]):
    add(chain_jingle(0.5, 5, seed=30 + k), at, 0.07 + 0.03 * k, (-1) ** k * 0.4)
    add(thump(52 + 4 * k, 0.6), at, 0.16 + 0.05 * k)

# 崩断（4.7）：金属断裂 + 锁链碎裂 + 低闷的冲击；紫光像玻璃一样碎掉
add(clank(1.8, 290), 4.70, 0.42, -0.1)
add(clank(1.4, 410), 4.71, 0.22, 0.25)
add(chain_jingle(1.3, 16, seed=4), 4.72, 0.20, -0.4)
add(chain_jingle(1.3, 14, seed=5), 4.74, 0.18, 0.4)
add(impact(2.0), 4.70, 0.36)
for k, nm in enumerate(['A6', 'F6', 'D6', 'Bb5', 'E6', 'C#6']):
    add(glass(nfreq(nm), 0.8), 4.72 + k * 0.045, 0.06, -0.5 + k * 0.2)
for k, at in enumerate([5.15, 5.3, 5.42, 5.6]):                                   # 链环落地
    add(clank(0.4, 700 + 150 * k) * 0.5, at, 0.05, (-1) ** k * 0.5)

# 书翻开（5.8）：一下气流，然后纸页哗哗翻动、飞出去
add(whoosh(0.7, 0.3, 300, 3000), 5.7, 0.14)
add(thump(60, 0.6), 5.8, 0.16)
add(crackle(1.2, lambda s: 90 * np.exp(-s * 1.2) + 12, seed=40, bright=900) * fade_env(int(1.2 * SR), 0.05, 0.5), 5.85, 0.16, 0.2)
add(bell(nfreq('D3'), 3.5, 0.6, 1.4), 5.95, 0.14, -0.15)                          # 书里的火光亮起
add(crackle(2.4, 14, seed=41, bright=2200) * fade_env(int(2.4 * SR), 0.6, 0.3), 6.0, 0.10, -0.4)

# 法阵升起（6.5–8.3）：低吟 + 泛音 + 上升的气流
ch = choir(2.0, nfreq('D2'), attack=0.7, release=0.3, vowel=(650, 1080), seed=0)
add(ch, 6.45, 0.30, -0.1)
ch2 = choir(1.8, nfreq('A2'), attack=0.9, release=0.3, vowel=(500, 900), vib=4.6, seed=1)
add(ch2, 6.6, 0.16, 0.15)
add(overtones(1.9, nfreq('D2'), (8, 12, 15, 16, 20), attack=0.9, release=0.3), 6.5, 0.06, 0.2)
add(whoosh(1.2, 0.55, 200, 2200), 6.45, 0.10)

# Claude 字标（7.0）：一声低锣，上面两下玻璃轻响
add(bell(nfreq('D2'), 3.0, 0.9, 2.2), 7.0, 0.26)
add(glass(nfreq('D5'), 1.2), 7.05, 0.08, -0.2)
add(glass(nfreq('A5'), 1.2), 7.2, 0.06, 0.2)
add(overtones(0.9, nfreq('D3'), (12, 16, 20), attack=0.3, release=0.5), 7.35, 0.03)

# 倒吸（7.89–8.4），8.4 炸开的低频冲击 + 余烬
add(inhale(0.51), 7.89, 0.42)
add(impact(3.2), 8.40, 0.85)
add(crackle(1.0, lambda s: 400 * np.exp(-s * 4), seed=6, bright=2500), 8.41, 0.18, -0.3)
add(crackle(1.0, lambda s: 400 * np.exp(-s * 4), seed=7, bright=2500), 8.42, 0.18, 0.3)
add(whoosh(0.9, 0.15, 200, 3000), 8.40, 0.14)

# 魔女现身：冷和弦 Dm add9（8.55）→ Gm add9/D（10.3）→ C#dim7（11.0，不解决），竖琴式分解
add(pad(2.0, ['D2', 'A2', 'D3', 'F3', 'A3', 'E4']), 8.55, 0.85)
add(pad(1.3, ['D2', 'G2', 'Bb2', 'D3', 'A3', 'D4']), 10.2, 1.0)
add(pad(1.0, ['C#3', 'E3', 'G3', 'Bb3', 'E4']), 11.0, 0.8)
add(overtones(3.4, nfreq('D2'), (12, 16, 18, 24), attack=1.0, release=1.0), 8.6, 0.035, 0.3)
for k, nm in enumerate(['D3', 'A3', 'D4', 'F4', 'A4', 'D5', 'E5']):
    add(pluck(nfreq(nm), 2.0), 8.67 + k * 0.11, 0.16, -0.4 + k * 0.13)
add(bell(nfreq('A2'), 3.0, 0.5, 1.5), 9.2, 0.09)                                  # 台词进来
for k, nm in enumerate(['G3', 'D4', 'G4', 'Bb4']):
    add(pluck(nfreq(nm), 1.8), 10.22 + k * 0.12, 0.13, 0.4 - k * 0.2)
# 魔女手里的火
add(crackle(4.6, 9, seed=8, bright=2000) * fade_env(int(4.6 * SR), 0.8, 0.8), 8.7, 0.07, 0.4)

# 欢迎（11.6）：一声冷钟（D5），垫一个 Dm 的低音
add(bell(nfreq('D5'), 3.0, 1.0, 1.3), 11.62, 0.26)
add(bell(nfreq('A4'), 2.6, 0.6, 1.1), 11.64, 0.07, 0.3)
add(pad(1.85, ['D2', 'A2', 'D3', 'F3']), 11.65, 0.45)

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
