# douyin-video-distiller — 抖音视频蒸馏 Skill

**本地离线跑：抖音链接 → 无水印下载 → 本地 Qwen 视频理解 → 带时间戳知识卡片。Douyin video distiller: link → watermark-free download → on-device Qwen2.5-Omni video understanding → timestamped, citable knowledge cards.** 全程不调第三方云端模型、无额度限制、无请求体上限。

把抖音短视频**一步到位**蒸馏成可检索的知识卡片：带时间戳的原视频证据、模型归纳、关键概念、行动项，直接落盘为 Markdown/Wiki 格式。

支持 Claude Code / OpenCode 等任何读取 `SKILL.md` 规范的 agent。

## 下载环节：CDP 登录态提取法（本仓库自带）

抖音 2025 年中起对纯 HTTP 解析全面上反爬——早期基于 `_ROUTER_DATA` 解析的下载器（包括本仓库曾引用的上游 `aehyok/douyin-video-download`）**已失效，只会拿到无数据的壳页，请勿再安装使用**。

现在链接下载走本仓库自带的 `douyin-video-download/SKILL.md`：借用你本机浏览器（Edge/Chrome）里已登录的抖音会话，通过 Chrome DevTools Protocol 提取真实视频流地址下载。零第三方下载器、无水印、支持视频和图集。

## 特性

1. **一步到位的正确流程**：链接 → 下载 → 视频理解 → 证据分级 → 知识卡片 → 临时文件清理，失败即如实报告、保留现场，不产生"假摘要"。
2. **本地多模态模型直接吃完整视频**：调用本地 **Qwen2.5-Omni-7B**，视频以带时间戳的帧序列原生送入模型（不是抽帧当图片看），音轨默认一起输入（缺依赖自动降级纯画面，stderr 有 `[warn]`）；不联网、无额度限制、无请求体大小上限。自带 `scripts/analyze_omni.py`。
3. **长视频的正确处理**：靠采样帧率（`--fps`）和 `--max-pixels`（默认 100352）控制耗时与显存，脚本给出 FFmpeg 切段压缩命令（150s/段、720p、CRF32），长视频也能稳定跑通。
4. **证据分级输出规范**：`原视频证据 / 蒸馏结论 / 待确认` 三层分离 + 时间戳，防止模型把单条视频观点升级成客观事实。

## 前置条件

| 依赖 | 必需 | 说明 |
|---|---|---|
| [Qwen2.5-Omni-7B](https://huggingface.co/Qwen/Qwen2.5-Omni-7B) 权重 | ✅ | 本地推理；4bit 量化后权重常驻约 6GB 显存，8G 显卡实测可跑 |
| Python 3.10+ | ✅ | 需 `torch` / `transformers>=4.57` / `bitsandbytes` / `qwen-omni-utils` / `torchvision>=0.19` / `accelerate`（device_map 必需）/ `audioread`（qwen-omni-utils 传递依赖，国内镜像常缺、需走官方 PyPI）/ `decord`（视频解码后端：**torchvision>=0.26 已删除 `read_video`，不装 decord 或 torchcodec 会直接崩**） |
| 浏览器 + 抖音网页版登录态 | ✅（仅链接下载） | Edge/Chrome 里 www.douyin.com 已登录；本地视频文件不需要 |
| FFmpeg、curl、Python `websockets` | ✅（仅链接下载） | CDP 提取与流合并用 |

### 获取模型权重（约 22GB，四种方式任选，手动自动都行）

```bash
# 方式1 · huggingface 官方（需可访问 huggingface.co）
hf download Qwen/Qwen2.5-Omni-7B --local-dir ./Qwen2.5-Omni-7B

# 方式2 · aifasthub 国内直链（快，支持断点续传，-C - 即续传）
HF_ENDPOINT=https://aifasthub.com hf download Qwen/Qwen2.5-Omni-7B --local-dir ./Qwen2.5-Omni-7B
# 单文件直链格式（浏览器/curl/wget 均可）：
#   https://aifasthub.com/Qwen/Qwen2.5-Omni-7B/resolve/main/<文件名>
curl -L -C - -O https://aifasthub.com/Qwen/Qwen2.5-Omni-7B/resolve/main/config.json

# 方式3 · hf-mirror 镜像
HF_ENDPOINT=https://hf-mirror.com hf download Qwen/Qwen2.5-Omni-7B --local-dir ./Qwen2.5-Omni-7B

# 方式4 · ModelScope（需 `pip install modelscope`）
modelscope download --model Qwen/Qwen2.5-Omni-7B --local_dir ./Qwen2.5-Omni-7B
```

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

# 音轨默认已输入（口播转写开箱即用）；纯画面任务加 --no-audio 关闭
python scripts/analyze_omni.py video.mp4 "把口播逐字转写"

# 输出复读严重时加 --ngram-rep 4（硬禁 4-gram 复读）

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

- **生成慢约 10 倍（<1 tok/s）**：**先查输入 token 数**（脚本 stderr 的 `[input] tokens=` 行），不是先看视频时长，也不是先怀疑显卡。缺省不压像素时 1080p 帧可喂进 5000+ token，慢一个数量级且 GPU 频率看着"异常低"（其实是超大输入的表象）。脚本已默认 `--max-pixels 100352`（=128×28²，qwen_vl_utils 硬下限，**传低于它的值如 100000 会直接断言崩溃**）；token 仍超预算就降 `--fps`。确认 token 正常后才查驱动：`nvidia-smi -l 2` 采样 SM 频率钉死低频且无节流标记时，给 python.exe 设「最高性能优先」或 `nvidia-smi -lgc`（跑完 `-rgc` 解锁），笔记本另查混合显卡/MUX。
- **每段循环重启 python 进程**：模型加载要 1–2 分钟，一个进程里加载一次、循环推理多段。
- **transformers 5.x 警告 pixel cap**：输入 token 会远超预期——确认 `--max-pixels` 生效（脚本默认 100352），不要传低于 100352 的值。

## 已知限制

- 抖音反爬持续升级：CDP 法依赖浏览器登录态；Chromium/Edge 136+ 禁止在默认 profile 上开调试端口，绕过法见 `douyin-video-download/SKILL.md` 第 3 步。仍拿不到视频时如实报告，可手动保存视频后走本地文件流程。
- 推理速度取决于显卡：RTX 4060 Laptop（8G）下 fps=1、输出 512 token 约需 2 分钟；纯音频约 30 秒。
- 模型**会幻觉**：约第 10 秒输出起可能退化复读、吐 `Human:` 之类角色标签。脚本已默认 `repetition_penalty=1.1`，仍严重时加 `--ngram-rep 4`；采信前先截断复读段。**覆盖校验**：输出时间戳没到视频末尾的，缺口必须标"未分析"——短视频卡死多半是输入 token 超预算（看 `[input] tokens=` 行），先确认 `--max-pixels` 没被关掉，不是降 fps。
- **音轨链路依赖因机器而异**（ffmpeg/audioread/decord）：缺依赖时脚本不会挂掉，会自动降级为纯画面通道并在 stderr 打 `[warn]`——但这次输出就不含任何语音信息，补齐依赖后重跑才是完整蒸馏。
- 画面硬字幕识别可靠；**模型自报的分段时间戳不可信**（实测偏差可达 30s），精确时间轴要用 ffmpeg 按画面字幕实测校正。

## License

MIT
