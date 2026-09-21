# douyin-video-distiller — 抖音视频蒸馏 Skill

把抖音短视频**一步到位**蒸馏成可检索的知识卡片：带时间戳的原视频证据、模型归纳、关键概念、行动项，直接落盘为 Markdown/Wiki 格式。

支持 Claude Code / OpenCode 等任何读取 `SKILL.md` 规范的 agent。

## 下载环节：CDP 登录态提取法（本仓库自带）

抖音 2025 年中起对纯 HTTP 解析全面上反爬——早期基于 `_ROUTER_DATA` 解析的下载器（包括本仓库曾引用的上游 `aehyok/douyin-video-download`）**已失效，只会拿到无数据的壳页，请勿再安装使用**。

现在链接下载走本仓库自带的 `douyin-video-download/SKILL.md`：借用你本机浏览器（Edge/Chrome）里已登录的抖音会话，通过 Chrome DevTools Protocol 提取真实视频流地址下载。零第三方下载器、无水印、支持视频和图集。

## 特性

1. **一步到位的正确流程**：链接 → 下载 → 视频理解 → 证据分级 → 知识卡片 → 临时文件清理，失败即如实报告、保留现场，不产生"假摘要"。
2. **本地多模态模型直接吃完整视频**：调用本地 **Qwen2.5-Omni-7B**，视频以带时间戳的帧序列原生送入模型（不是抽帧当图片看），还可加 `--audio` 连音轨一起理解；不联网、无额度限制、无请求体大小上限。自带 `scripts/analyze_omni.py`。
3. **长视频的正确处理**：靠采样帧率（`--fps`）和 `--max-pixels` 控制耗时与显存，脚本给出 FFmpeg 切段压缩命令（150s/段、720p、CRF32），长视频也能稳定跑通。
4. **证据分级输出规范**：`原视频证据 / 蒸馏结论 / 待确认` 三层分离 + 时间戳，防止模型把单条视频观点升级成客观事实。

## 前置条件

| 依赖 | 必需 | 说明 |
|---|---|---|
| [Qwen2.5-Omni-7B](https://huggingface.co/Qwen/Qwen2.5-Omni-7B) 权重 | ✅ | 本地推理；4bit 量化后权重常驻约 6GB 显存，8G 显卡实测可跑 |
| Python 3.10+ | ✅ | 需 `torch` / `transformers>=4.57` / `bitsandbytes` / `qwen-omni-utils` / `torchvision>=0.19` / `accelerate`（device_map 必需）/ `audioread`（qwen-omni-utils 传递依赖，国内镜像常缺、需走官方 PyPI）/ `decord`（视频解码后端：**torchvision>=0.26 已删除 `read_video`，不装 decord 或 torchcodec 会直接崩**） |
| 浏览器 + 抖音网页版登录态 | ✅（仅链接下载） | Edge/Chrome 里 www.douyin.com 已登录；本地视频文件不需要 |
| FFmpeg、curl、Python `websockets` | ✅（仅链接下载） | CDP 提取与流合并用 |
| 可选：`NVIDIA_API_KEY` | ❌ | 没有本地显卡时走 `scripts/analyze.rb` 云端后端（注意 25MB 请求体上限） |

设置模型路径：

```bash
export OMNI_MODEL_PATH="/path/to/Qwen2.5-Omni-7B"     # Linux / macOS
$env:OMNI_MODEL_PATH="D:\Models\Qwen2.5-Omni-7B"      # Windows PowerShell
```

## 安装

把两个 skill 目录放进你的 skills 目录（下载 skill 是蒸馏流程的依赖，两个都要）：

```
# Claude Code
~/.claude/skills/douyin-video-distiller/
~/.claude/skills/douyin-video-download/

# OpenCode
~/.config/opencode/skills/douyin-video-distiller/
~/.config/opencode/skills/douyin-video-download/
```

## 使用

对 agent 说：

> 把这个抖音视频蒸馏成知识卡片：https://v.douyin.com/xxxxx/

或直接处理本地视频：

```bash
python scripts/analyze_omni.py video.mp4 "请完整分析视频并输出带时间戳的转录、画面文字、时间线、明确证据、模型归纳和待确认事项。"

# 口播类视频：连音轨一起听
python scripts/analyze_omni.py video.mp4 "把口播逐字转写" --audio

# 纯音频文件会自动走音频通道
python scripts/analyze_omni.py audio.wav "这段音频里有人说话吗？"
```

## 输出格式

```markdown
---
title: ""
type: learning
source: ["原始链接"]
confidence: high | medium | low
status: draft
---
## 一句话结论 / 原视频证据 / 蒸馏结论 / 关键概念 / 可执行行动 / 待确认事项
```

## 性能排障（跑得太慢先看这里）

- **生成慢约 10 倍（<1 tok/s）**：先查 GPU 频率，别怀疑模型。`nvidia-smi --query-gpu=clocks.sm,clocks.max.sm,power.draw,utilization.gpu --format=csv -l 2` 连续采样；若 SM 频率钉在 300MHz 档、无节流标记（`clocks_event_reasons.active=0x0`），是驱动功耗策略没让 dGPU 升频——NVIDIA 控制面板给 python.exe 设「最高性能优先」，或管理员 `nvidia-smi -lgc 1500,3090`（跑完 `-rgc` 解锁）。笔记本另查混合显卡/MUX。
- **每段循环重启 python 进程**：模型加载要 1–2 分钟，一个进程里加载一次、循环推理多段。
- **transformers 5.x 警告 pixel cap**：输入 token 会远超预期，加 `--max-pixels 100000` 收敛。

## 已知限制

- 抖音反爬持续升级：CDP 法依赖浏览器登录态；Chromium/Edge 136+ 禁止在默认 profile 上开调试端口，绕过法见 `douyin-video-download/SKILL.md` 第 3 步。仍拿不到视频时如实报告，可手动保存视频后走本地文件流程。
- 推理速度取决于显卡：RTX 4060 Laptop（8G）下 fps=1、输出 512 token 约需 2 分钟；纯音频约 30 秒。
- 模型**会幻觉**：长输出尾部可能自续对话轮次、编造不存在的时间点。脚本已加 `repetition_penalty` 压制，但仍应只采信前半段，重要内容回看原视频核对（skill 已强制标注"待确认事项"）。
- 画面硬字幕识别可靠；**模型自报的分段时间戳不可信**（实测偏差可达 30s），精确时间轴要用 ffmpeg 按画面字幕实测校正。

## 可选：云端后端

仓库里保留了 `scripts/analyze.rb` —— 走 NVIDIA 免费 API（`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`）的旧版实现，
没有本地显卡时可用（需 `NVIDIA_API_KEY`，仅依赖 Ruby 标准库，注意其 25MB 请求体上限）。
默认流程走本地 `scripts/analyze_omni.py`。

## License

MIT
