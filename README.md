# douyin-video-distiller — 抖音视频蒸馏 Skill

把抖音短视频**一步到位**蒸馏成可检索的知识卡片：带时间戳的原视频证据、模型归纳、关键概念、行动项，直接落盘为 Markdown/Wiki 格式。

支持 Claude Code / OpenCode 等任何读取 `SKILL.md` 规范的 agent。

## 致谢与来源

本 skill 的下载环节基于 **[aehyok/douyin-video-download](https://github.com/aehyok/douyin-video-download)**（无水印视频/图集解析下载）。本仓库**不包含**该下载器的任何源码，仅作为上游依赖调用它——请先自行安装。

在此基础上的新增/改动：

1. **一步到位的正确流程**：链接 → 下载 → 视频理解 → 证据分级 → 知识卡片 → 临时文件清理，失败即如实报告、保留现场，不产生"假摘要"。
2. **NVIDIA 免费多模态模型直接吃完整视频**：调用 `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`（原生视频输入），不再需要本地 whisper / 抽帧拼凑；自带 `scripts/analyze.rb`（纯 Ruby 标准库，零 gem 依赖）。
3. **25MB 载荷上限的正确处理**：脚本内置大小检查并给出 FFmpeg 切段压缩命令（150s/段、720p、CRF32），长视频也能稳定跑通。
4. **证据分级输出规范**：`原视频证据 / 蒸馏结论 / 待确认` 三层分离 + 时间戳，防止模型把单条视频观点升级成客观事实。

## 前置条件

| 依赖 | 必需 | 说明 |
|---|---|---|
| NVIDIA API Key | ✅ | 到 https://build.nvidia.com 免费注册获取（`nvapi-` 开头，含免费额度） |
| Ruby 3.x | ✅ | 仅用标准库，无需装 gem（WSL 内即可） |
| [douyin-video-download](https://github.com/aehyok/douyin-video-download) | ✅ | 链接下载环节的上游 skill |
| FFmpeg | 建议 | 视频超过 ~18MB 时切段压缩用 |

设置 Key：

```bash
export NVIDIA_API_KEY="nvapi-你的key"        # Linux / macOS / WSL
$env:NVIDIA_API_KEY="nvapi-你的key"          # Windows PowerShell
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
ruby scripts/analyze.rb video.mp4 "请完整分析视频并输出带时间戳的转录、画面文字、时间线、明确证据、模型归纳和待确认事项。"
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
- NVIDIA 免费账户有速率/额度限制，长视频分段多时注意。
- 模型输出为归纳而非逐字转录，重要内容请回看原视频核对（skill 已强制标注"待确认事项"）。

## License

MIT（仅覆盖本仓库内容；上游下载器版权归其原作者）
