# douyin-video-distiller — 抖音视频蒸馏 Skill

把抖音短视频**一步到位**蒸馏成可检索的知识卡片：带时间戳的原视频证据、模型归纳、关键概念、行动项，直接落盘为 Markdown/Wiki 格式。

支持 Claude Code / OpenCode 等任何读取 `SKILL.md` 规范的 agent。

## 致谢与来源

本 skill 的下载环节基于 **[aehyok/douyin-video-download](https://github.com/aehyok/douyin-video-download)**（无水印视频/图集解析下载）。本仓库**不包含**该下载器的任何源码，仅作为上游依赖调用它——请先自行安装。

在此基础上的新增/改动：

1. **一步到位的正确流程**：链接 → 下载 → 视频理解 → 证据分级 → 知识卡片 → 临时文件清理，失败即如实报告、保留现场，不产生"假摘要"。
2. **本地多模态模型直接吃完整视频**：调用本地 **Qwen2.5-Omni-7B**，视频以带时间戳的帧序列原生送入模型（不是抽帧当图片看），还可加 `--audio` 连音轨一起理解；不联网、无额度限制、无请求体大小上限。自带 `scripts/analyze_omni.py`。
3. **长视频的正确处理**：靠采样帧率（`--fps`）和 `--max-pixels` 控制耗时与显存，脚本给出 FFmpeg 切段压缩命令（150s/段、720p、CRF32），长视频也能稳定跑通。
4. **证据分级输出规范**：`原视频证据 / 蒸馏结论 / 待确认` 三层分离 + 时间戳，防止模型把单条视频观点升级成客观事实。

## 前置条件

| 依赖 | 必需 | 说明 |
|---|---|---|
| [Qwen2.5-Omni-7B](https://huggingface.co/Qwen/Qwen2.5-Omni-7B) 权重 | ✅ | 本地推理；4bit 量化后权重常驻约 6GB 显存，8G 显卡实测可跑 |
| Python 3.10+ | ✅ | 需 `torch` / `transformers>=4.57` / `bitsandbytes` / `qwen-omni-utils` / `torchvision>=0.19` |
| [douyin-video-download](https://github.com/aehyok/douyin-video-download) | ✅ | 链接下载环节的上游 skill |
| FFmpeg | 建议 | 长视频切段压缩用 |

设置模型路径：

```bash
export OMNI_MODEL_PATH="/path/to/Qwen2.5-Omni-7B"     # Linux / macOS
$env:OMNI_MODEL_PATH="D:\Models\Qwen2.5-Omni-7B"      # Windows PowerShell
```

## 安装

把本目录整个放进你的 skills 目录：

```
# Claude Code
~/.claude/skills/douyin-video-distiller/

# OpenCode
~/.config/opencode/skills/douyin-video-distiller/
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

## 已知限制

- 抖音反爬持续升级：上游下载器失效时本 skill 无法下载，此时如实报告；可用浏览器登录态方式手动取视频后走本地视频流程。
- 推理速度取决于显卡：RTX 4060 Laptop（8G）下 fps=1、输出 512 token 约需 2 分钟；纯音频约 30 秒。
- 模型**会幻觉**：长输出尾部可能自续对话轮次、编造不存在的时间点。脚本已加 `repetition_penalty` 压制，但仍应只采信前半段，重要内容回看原视频核对（skill 已强制标注"待确认事项"）。
- 画面硬字幕识别可靠；**时间轴不可信**，不要把模型给的分段时间当证据。

## 可选：云端后端

仓库里保留了 `scripts/analyze.rb` —— 走 NVIDIA 免费 API（`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`）的旧版实现，
没有本地显卡时可用（需 `NVIDIA_API_KEY`，仅依赖 Ruby 标准库，注意其 25MB 请求体上限）。
默认流程走本地 `scripts/analyze_omni.py`。

## License

MIT（仅覆盖本仓库内容；上游下载器版权归其原作者）
