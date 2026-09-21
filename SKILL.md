---
name: douyin-video-distiller
description: '抖音视频蒸馏 Skill。用户提供抖音链接、视频文件或要求把短视频提炼成知识卡片、摘要、时间线、证据、行动项、Wiki 内容或第二大脑资料时使用；也适用于"帮我把这个视频真正变成可检索知识"等未明确说蒸馏的请求。'
disable-model-invocation: false
user-invocable: true
compatibility: '需要本地 Qwen2.5-Omni-7B 权重（约 22GB，4bit 量化后 8G 显存可跑）；下载依赖 douyin-video-download skill；视频分析脚本为本 skill 自带的 scripts/analyze_omni.py。Python 依赖：torch / transformers>=4.57 / bitsandbytes / qwen-omni-utils / torchvision>=0.19 / accelerate（device_map 必需）/ audioread（qwen_omni_utils 传递依赖，国内镜像常缺、需走官方 PyPI）/ decord（视频解码后端：torchvision>=0.26 已删除 read_video，不装 decord 或 torchcodec 会直接崩）'
---

# 抖音视频蒸馏

## 核心原则

把视频处理成可复用知识，而不是只生成泛泛摘要。必须区分视频明确说出/展示的内容、模型归纳、用户可能需要确认的推测，并尽量保留时间戳。下载失败、视频不可访问或视觉模型不支持完整视频时，要如实报告并停止冒充已完成。

## 输入与权限

支持抖音链接、本地视频和用户提供的转录文本。链接下载需要用户已有访问权限；不绕过验证码、登录墙、访问控制或平台限制。Cookie、API Key 和账号信息只从本机安全配置读取，不显示、不写入输出、不上传到 Wiki。

## 第 0 步：环境自检与分析通道选择（必做，别直接开跑）

按顺序探测，走第一个能跑的通道；全部不通就向用户要转录文本，**不得凭链接内容瞎编蒸馏结果**：

1. **通道 A · 本地模型**：检查环境变量 `OMNI_MODEL_PATH` 指向的目录里有没有 `config.json` + safetensors 权重，且本机有 ≥8GB 显存（`nvidia-smi`）。三者齐备 → 用 `scripts/analyze_omni.py`。缺权重/缺显存 → 不要试图现场下载 22GB 模型，直接下一通道。
2. **通道 B · NVIDIA 云端**：检查 `NVIDIA_API_KEY` 环境变量。未设置 → 告知用户去 https://build.nvidia.com 免费注册获取 key 并 `$env:NVIDIA_API_KEY="nvapi-…"`（PowerShell），然后改用 `scripts/analyze.rb`。**云端单次请求体上限 25MB（base64 后）**，必须先用 FFmpeg 压段：每段 ≤150 秒、`scale=720:-2`、CRF 32、AAC 64k，逐段分析后合并。
3. **通道 C · 用户提供文本**：A/B 都不通时，请用户粘贴抖音自带的图文转录或第三方转文字结果，走纯文本蒸馏流程（质量降级，需在输出里注明"仅基于文本，无画面证据"）。

下载同理：链接一律按 `douyin-video-download` skill 里的「CDP 登录态提取法」执行（该 skill 唯一路径）；不要尝试 yt-dlp/纯 HTTP 解析/cookie 导出等已被抖音反爬淘汰的做法，用户手动给来本地视频路径则直接进分析。

## 执行流程

1. 判断输入类型。链接先解析并保存原始链接信息；本地视频记录文件路径、大小、时长和格式；文本直接进入转录蒸馏流程。
2. 处理抖音链接时，调用已安装的 `douyin-video-download` skill（CDP 登录态提取法），按其文档步骤下载视频到临时目录。不要复制下载器源码，也不要输出视频签名直链、Cookie 或凭据。
3. 本地模型没有请求体大小上限，但耗时随视频长度和采样帧率线性增长。先记录视频时长：超长视频（>3 分钟）先降低采样帧率（`--fps 0.5`），必要时再用 FFmpeg 切段（每段 ≤150 秒、`scale=720:-2`、CRF 32、AAC 64k），逐段分析后合并结果。
4. 调用本 skill 自带的本地视觉分析脚本处理视频（默认 fps=1；口播类视频加 `--audio` 可一并听音轨）：
   ```bash
   python "<本 skill 目录>/scripts/analyze_omni.py" "<视频文件>" "请完整分析视频并输出带时间戳的转录、画面文字、时间线、明确证据、模型归纳和待确认事项。"
   ```
   脚本通过 `OMNI_MODEL_PATH` 读取本地 Qwen2.5-Omni-7B 权重目录。分析结果保存为临时分析文本或 JSON，不自动写入 Wiki、Index、graph.json 或知识蛛网。
5. 只有在分析成功且分析结果已保存后，才删除本次下载的临时视频文件及其临时下载目录；删除前确认路径位于本次任务临时目录内。分析失败、超时、结果为空或无法验证完整视频时，保留视频以便重试，并明确报告原因。不得删除用户原本已有的本地视频，除非用户在当前请求中明确要求删除。
6. 获取转录和视觉证据。视频明确展示/说出的信息标为"原视频证据"；模型归纳标为"蒸馏结论"；无法核实的信息标为"待确认"。
7. 输出时间线、关键概念、因果链、例子、反例、行动步骤和关键词。不要把单条视频观点自动升级成客观事实。
8. 若用户明确要求写入知识库，先读取相关 Schema 和 Wiki 文件，优先更新同主题文件；来源写相对路径或原始链接，状态默认为 `draft`，等待审核。分析、下载、删除、写 Wiki 是不同动作，不能自动串联未被请求的 Wiki 写入。
9. 完成后给出处理状态：下载、分析和清理分别是否成功；列出实际使用的输入和未完成原因。

## 标准输出

```markdown
---
title: ""
type: learning
topic: ""
source:
  - "原始抖音链接或相对文件路径"
confidence: high | medium | low
status: draft
---

# 标题

## 一句话结论

## 原视频证据
按时间戳列出明确说出或展示的内容。

## 蒸馏结论
模型归纳出的框架、因果关系和可迁移方法。

## 关键概念与关键词

## 可执行行动

## 待确认事项

## 关联主题
```

## 失败处理

- 下载失败：返回"未取得视频"，说明错误类别和下一步，不生成虚假的视频内容；不要删除任何文件。
- 抖音反爬（只返回壳页/无视频数据）：如实报告，建议用户改用浏览器登录态方式手动获取视频后走本地视频流程。
- 只有标题或短链接元数据：只能整理元数据，不能声称完成视频蒸馏。
- 视频过长导致推理超时或显存不足：按执行流程第 3 步降低采样帧率或切段压缩（也可用 `--max-pixels` 压单帧像素），或如实报告未完成。
- **生成慢约 10 倍（<1 tok/s）时先查 GPU 频率，别怀疑模型**：`nvidia-smi --query-gpu=clocks.sm,clocks.max.sm,power.draw,utilization.gpu --format=csv -l 2` 连续采样；若 SM 频率钉在 300MHz 档不动、无节流标记（clocks_event_reasons.active=0x0），是驱动功耗策略没让 dGPU 升频——NVIDIA 控制面板给 python.exe 设「最高性能优先」，或管理员 `nvidia-smi -lgc 1500,3090`（跑完 `-rgc` 解锁）；笔记本还要查混合显卡/MUX（2026-09-21 同学机 RTX 5060 Laptop 实测案例）。
- transformers 5.x 提示 "does not apply the per-frame pixel cap"：输入 token 会远超预期，加 `--max-pixels 100000` 收敛。
- 解码报 `torchvision.io has no attribute 'read_video'`：torchvision≥0.26 已删除该函数，`pip install decord` 即可（qwen_omni_utils 自动优选，无需改代码）。
- 分析失败、超时、返回空结果或拒绝视频：保留本次下载的视频，明确说明分析未完成，不执行自动删除；如用户允许，可改为"转录 + 抽帧"并明确这不是完整视频理解。
- 清理失败：如实报告残留文件路径，不重复删除用户原有文件。
- 内容含个人隐私、健康、财务、密码、Cookie、API Key 或身份凭据：不上传、不输出、不写入公开 Wiki。
