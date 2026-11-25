"""从 sfx_magic.py 生成 sfx_cine.py：音色函数和混响原样沿用，只把时间线换成电影感版（intro_cine.html，13.5 秒）的。
python.exe -I make_sfx_cine.py     # 写出 sfx_cine.py
"""

src = open("sfx_magic.py", encoding="utf-8").read()
A, B = "# ---------- 时间线 ----------", "# ---------- 混响 + 收尾 ----------"
head, tail = src[: src.index(A)], src[src.index(B) :]
head = head.replace("LEN = 12.4", "LEN = 13.5")
head = head[head.index('"""', 3) + 3 :]
doc = '''"""电影感版开屏音效（由 make_sfx_cine.py 从 sfx_magic.py 生成，别手改；要改时间线改 make_sfx_cine.py）。
时间点和 intro_cine.html 对齐（INTRO_LEN = 13.5 秒）：
  0–3.6 抽书（书震动、锁链响、滑出书架、落灰）→ 4.7 锁链崩断、紫光碎掉 → 5.8 书翻开、翻页
  → 6.6 法阵升起 → 7.0 Claude 字标 → 7.9 倒吸 → 8.4 炸开 → 魔女现身的冷和弦 → 11.6 欢迎处一声冷钟。
"""'''
timeline = r"""# ---------- 时间线 ----------
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

"""
open("sfx_cine.py", "w", encoding="utf-8").write(doc + head + timeline + tail)
print("写好 sfx_cine.py")
