# Claude 魔女开机动画 · claude-witch-boot

给 Windows 版 Claude 桌面端加一段电影感的开机动画：打开 Claude 时，哥特图书馆里一本缠着锁链的禁书从书架上滑出、震断锁链、翻开，书页上燃起法阵和 **Claude** 字样，一道光之后，橘发魔女现身——最后画面慢慢透出真正的 Claude 界面，留下一层半透明的魔女背景。

- 🎬 **开屏动画**：13.5 秒，2560×1440、120 帧，带合成音效
- 🌙 **循环背景**：开屏结束后半透明循环播放，点击直接穿透到 Claude，不影响使用
- ✨ **右上角按钮**：Claude 标题栏右上角有一个 ✨，点开可以调背景不透明度、开屏音量、开关
- 🧼 **不改 Claude 本体**：独立的小程序，盖在 Claude 窗口上播放；卸载后什么都不留

> 非官方同人项目，与 Anthropic 无关。Claude 是 Anthropic 的商标。

## 安装（Windows 10 / 11）

1. 下载本仓库（Code → Download ZIP，解压），或者 `git clone`。
2. 打开 PowerShell，进入 `player` 文件夹，运行：

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

不需要装任何 SDK：用 Windows 自带的 C# 编译器现场编译。程序装到剩余空间最大的非系统盘（例如 `D:\AIBootAnimations\ClaudeBootAnimation`），并设为开机自启。有的安全软件会提示「powershell 试图开机启动」，选允许即可。

装好后下次打开 Claude 就会播放；想马上看，点 Claude 右上角的 ✨ →「现在播放一次开屏」，或右键托盘的 ✨ 图标。

**如果播放卡顿**：到 [Releases](../../releases) 下载 60 帧版的 `intro.mp4`、`loop.mp4`，替换 `player/assets/` 里的同名文件，再运行一次 `install.ps1`。

卸载：✨ 菜单 →「更多设置…」→「卸载…」，或运行 `player/uninstall.ps1`。

设置文件 `%APPDATA%\ClaudeBootAnimation\config.json`，日志 `%LOCALAPPDATA%\ClaudeBootAnimation\log.txt`。

## 仓库里有什么

```
player/                 播放器（基于 wynneceles/ai-boot-animations 的 Windows 版修改，GPL-3.0）
  src/ClaudeBootAnimation.cs
  assets/intro.mp4      开屏（2560x1440, 120fps）
  assets/loop.mp4       循环背景（2560x1440, 120fps）
  install.ps1 / build.ps1 / uninstall.ps1
pipeline/               整套制作流程（想自己做一版可以参考）
  keyframes/            首帧图：抽书镜头、魔女定妆图（ChatGPT 生成）
  seedance/             火山方舟 Seedance 2.5 图生视频脚本 + 三段提示词
  footage/              Seedance 生成的三段原始视频（1080p, 24fps）
  comfyui/              ComfyUI 出图 / 局部重绘 / 外扩补画脚本和提示词；hd.py：AI 放大 + 补帧
  intro/                剪辑与合成：intro_cine.html（Canvas 叠字标、闪光、字幕）、render.mjs（逐帧渲染）、
                        sfx_cine.py（numpy 合成音效）、encode.py（H.264 编码）
```

## 制作流程

1. **首帧**：用 ChatGPT 出两张首帧图（`pipeline/keyframes/`）。
2. **AI 视频**：`pipeline/seedance/ark_video.py` 调火山方舟 Seedance 2.5 生成三段 5 秒 1080p 视频：
   ① 抽书（首帧 `first_frame_book.png`）→ ② 断链、翻开、法阵（首帧是 ① 的最后一帧）→ ③ 魔女（首帧和尾帧都是 `witch.png`，尾帧回到原图，正好接循环背景）。
   需要自己的方舟 API Key：`$env:ARK_API_KEY = "你的Key"`。
3. **高清化**：`pipeline/comfyui/hd.py`（用 ComfyUI 的 Python 环境，有 torch）
   - `up`：Real-ESRGAN `realesr-animevideov3` 放大到 2560x1440（写实镜头 `--blend 0.55`、动漫镜头 `--blend 0.4`，纯 AI 放大会抹掉纹理、改脸）
   - `vfi`：RIFE 4.7 补帧 24 → 120fps（`--scale` 一定要用 1，0.5 会让补出的帧整体错位、画面发抖）
   - 模型需要自己下载放到 `pipeline/tools_dl/`：
     - `tools_dl/esrgan/realesr-animevideov3.pth`：[Real-ESRGAN Releases v0.2.5.0](https://github.com/xinntao/Real-ESRGAN/releases)
     - `tools_dl/rife/rife47.pth`：[ComfyUI-Frame-Interpolation Releases](https://github.com/Fannovel16/ComfyUI-Frame-Interpolation/releases)
     - `tools_dl/rife/rife_arch.py`：从 [ComfyUI-Frame-Interpolation](https://github.com/Fannovel16/ComfyUI-Frame-Interpolation) 的 `vfi_models/rife/rife_arch.py` 拷贝，把 `from comfy.model_management import get_torch_device` 换成返回 `torch.device("cuda")` 的小函数
4. **剪辑合成**（`pipeline/intro/`）：
   - `build_cine_base.py`：把三段视频按时间线排成 120fps 底片帧（抽书 1.4 倍速、断链前段 2 倍速、法阵定格）
   - `render.mjs`：用 Playwright 自带的 headless Chromium 逐帧渲染 `intro_cine.html`（叠 Claude 哥特字标、拉丁文副标题、闪光转场、台词、Welcome back），`loop` 模式渲染循环背景
   - `sfx_cine.py`：numpy 合成全部音效（不用外部素材）；`encode.py`：PyAV 编码 H.264 + AAC
   - 开屏最后一帧和循环背景第一帧逐像素一致，交接无缝

```powershell
python build_cine_base.py frames_base --fps 120 --s1 ..\hd\s1_120 --s2 ..\hd\s2_120 --witch ..\hd\w2_120 --src-fps 120
node render.mjs intro frames_intro --page intro_cine.html --fps 120 --char frames_base --char-start 0 --char-fps 120
node render.mjs loop frames_loop --page intro_cine.html --fps 120
python sfx_cine.py sfx.wav
python encode.py frames_intro intro.mp4 --audio sfx.wav --fps 120 --crf 16
python encode.py frames_loop loop.mp4 --fps 120 --crf 16
```

## 相对原播放器的改动

见 [NOTICE.md](NOTICE.md)。

## 许可证

- 播放器代码基于 [wynneceles/ai-boot-animations](https://github.com/wynneceles/ai-boot-animations)（GPL-3.0），本仓库整体以 **GPL-3.0** 发布，见 [LICENSE](LICENSE)。
- `player/assets/LibreBodoni-*`：SIL Open Font License，见 `LibreBodoni-OFL.txt`。
- 本仓库**不包含**原项目自带的动画视频（原作者以 CC BY-NC-ND 发布，不可修改转发）；`player/assets/intro.mp4`、`loop.mp4` 和 `pipeline/` 里的图片视频都是本项目新做的。
