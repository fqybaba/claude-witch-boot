# NOTICE

`player/` 基于 [wynneceles/ai-boot-animations](https://github.com/wynneceles/ai-boot-animations)（commit `b624d2a`，`claude/windows/`）修改，原作品以 GPL-3.0 发布。本仓库沿用 GPL-3.0。

## 对 `player/src/ClaudeBootAnimation.cs` 的修改（2026-11）

- 默认配置适配本项目的开屏：`fadeStartSeconds` = 13.4；`showSubtitles` = false（字幕已做进视频）。
- **开屏全屏**（`introFullscreen`）：开屏阶段盖满整块屏幕（含任务栏）并置顶，透出界面时缩回 Claude 窗口、取消置顶。
- **去掉「跳过」按钮**（`showSkipButton`，默认 false，可在设置文件里打开）。
- 背景不透明度上限从 80% 提到 100%。
- **Claude 窗口右上角 ✨ 按钮**（`showAdjustButton`、`adjustButtonRight`、`adjustButtonTop`）：循环背景时显示，点开一个下拉菜单（Claude 同款黑底 + 暗金花体线装饰），可调开关、背景不透明度、开屏音量，播放一次开屏，关掉背景。
- 修复：有开屏时先隐藏循环层，避免打开 Claude 时先闪一下循环背景。
- 程序启动时如果 Claude 已经开着，直接挂上循环背景（不补播开屏）。
- 新增开发参数 `--render-menu 路径`：把 ✨ 菜单画成 PNG。

`install.ps1`、`build.ps1`、`uninstall.ps1` 未改动；去掉了从原仓库 Releases 下载的 `web-install.ps1`。

## 第三方模型（不随仓库分发，需自行下载）

- Real-ESRGAN `realesr-animevideov3`（BSD-3-Clause）：https://github.com/xinntao/Real-ESRGAN
- RIFE 4.7（MIT）：https://github.com/hzwer/Practical-RIFE ；PyTorch 结构代码取自 https://github.com/Fannovel16/ComfyUI-Frame-Interpolation

## 素材来源

- 首帧图由 ChatGPT 生成；三段视频由火山方舟 Seedance 2.5 生成；循环背景由魔女首帧图放大而成。
- 字体：Old English Text MT、Vivaldi、Garamond 为 Windows 自带字体，仅在渲染时使用，不随仓库分发。
