# -*- coding: utf-8 -*-
"""
本地视频理解 —— Qwen2.5-Omni-7B（Thinker-only + bitsandbytes NF4 4bit）

原生视频通道：把视频按 fps 采样成**带时间戳的帧序列**送进模型，不是抽帧当图片看。
默认同时输入视频音轨；音轨链路失败会自动降级为纯画面通道（stderr 有 [warn]）。

依赖：
  torch(cuda) / transformers>=4.57 / bitsandbytes / qwen-omni-utils / torchvision / accelerate
  / audioread（qwen_omni_utils 传递依赖）/ decord（视频解码后端；torchvision>=0.26 已删
  read_video，不装 decord 或 torchcodec 会直接崩）
模型：
  Qwen2.5-Omni-7B 的 fp16 权重（本地目录），只加载 thinker 部分

用法:
  python analyze_omni.py video.mp4
  python analyze_omni.py video.mp4 "只抄录画面里的所有字幕文字" --fps 2 --max-new 384
  python analyze_omni.py video.mp4 "把口播逐字转写"          # 音轨默认已输入，--no-audio 关闭
  python analyze_omni.py audio.wav "这段音频里有人说话吗？"     # 自动走纯音频通道

环境变量:
  OMNI_MODEL_PATH   Qwen2.5-Omni-7B 权重目录（必填，或用 --model）
  OMNI_FPS          采样帧率，默认 1
  OMNI_MAX_NEW      最大生成 token，默认 512
  OMNI_MAX_PIXELS   单帧像素上限，默认 100352（=128×28²，qwen_vl_utils 的硬下限，
                    低于它会断言崩溃；0 = 不传该参数，回到库默认 602112——1080p 帧
                    不缩放会导致 token 爆炸、慢一个数量级，慎用）
  OMNI_REP_PEN      重复惩罚，默认 1.1（greedy 输出尾部会退化，靠它压）
  OMNI_NGRAM_REP    no_repeat_ngram_size，默认 0；输出复读严重时设 4
  OMNI_USE_AUDIO    1 = 输入音轨（脚本默认已开，0 关闭）
  OMNI_SYS          系统提示词

输出可信度：模型约在生成 10s+ 后可能退化复读、编造角色标签；输出未覆盖全时间轴
时必须按 SKILL.md 要求在结果里标注缺口，不要把"没看"当"没有"。
"""
import argparse
import os
import sys
import time

import torch

DEFAULT_PROMPT = (
    "请完整分析这个视频并输出带时间戳的转录、画面文字、时间线、"
    "明确证据、模型归纳和待确认事项。"
)
AUDIO_EXT = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".opus"}


def main():
    ap = argparse.ArgumentParser(
        description="Qwen2.5-Omni-7B 本地视频/音频理解（4bit, thinker-only）")
    ap.add_argument("media", help="本地视频或音频文件路径")
    ap.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT, help="提问")
    ap.add_argument("--model", default=os.environ.get("OMNI_MODEL_PATH"),
                    help="Qwen2.5-Omni-7B 权重目录（也可用 OMNI_MODEL_PATH）")
    ap.add_argument("--fps", type=float, default=float(os.environ.get("OMNI_FPS", "1")))
    ap.add_argument("--max-new", type=int, default=int(os.environ.get("OMNI_MAX_NEW", "512")))
    ap.add_argument("--max-pixels", type=int,
                    default=int(os.environ.get("OMNI_MAX_PIXELS", "100352")),
                    help="单帧像素上限，默认 100352（128×28² 硬下限，同时也是有效的压缩值；0=不传）")
    ap.add_argument("--rep-pen", type=float, default=float(os.environ.get("OMNI_REP_PEN", "1.1")))
    ap.add_argument("--ngram-rep", type=int, default=int(os.environ.get("OMNI_NGRAM_REP", "0")),
                    help="no_repeat_ngram_size，>0 可硬禁 n-gram 复读（如 4），0=关闭")
    ap.add_argument("--sys", default=os.environ.get("OMNI_SYS", "You are a helpful assistant."))
    ap.add_argument("--audio", action="store_true",
                    default=os.environ.get("OMNI_USE_AUDIO", "1") == "1",
                    help="视频以外的音轨也一并输入（默认开：口播类视频不加等于主动放弃全部语音信息；--no-audio 关闭）")
    ap.add_argument("--no-audio", dest="audio", action="store_false")
    args = ap.parse_args()

    if not args.model:
        sys.exit("缺少模型目录：请设置 OMNI_MODEL_PATH 或用 --model 指定 Qwen2.5-Omni-7B 权重路径。")
    if not os.path.exists(args.media):
        sys.exit("文件不存在: %s" % args.media)
    if not torch.cuda.is_available():
        sys.exit("torch 看不到 CUDA 设备：本脚本无 CPU 回退，请检查驱动/装对 cuda 版 torch，不要硬跑。")

    from transformers import (
        BitsAndBytesConfig,
        Qwen2_5OmniConfig,
        Qwen2_5OmniProcessor,
        Qwen2_5OmniThinkerForConditionalGeneration,
    )
    from qwen_omni_utils import process_mm_info

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    # 顶层 config.json 是 Qwen2_5OmniConfig（thinker/talker/token2wav 嵌套三层），
    # Qwen2_5OmniThinkerConfig 无法直接反序列化它 —— 必须显式取出 thinker_config 子配置传入，
    # 否则模型会按默认值构造出错误结构。
    full_cfg = Qwen2_5OmniConfig.from_pretrained(args.model)
    thinker_cfg = full_cfg.thinker_config

    t0 = time.time()
    model = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(
        args.model,
        config=thinker_cfg,
        quantization_config=bnb,
        torch_dtype=torch.float16,
        device_map="cuda",
        attn_implementation="sdpa",
    )
    model.eval()
    print("[model] %.1fs  vram=%.2fGB" % (
        time.time() - t0, torch.cuda.memory_allocated() / 1024 ** 3),
        file=sys.stderr, flush=True)

    processor = Qwen2_5OmniProcessor.from_pretrained(args.model)

    if os.path.splitext(args.media)[1].lower() in AUDIO_EXT:
        media_ele = {"type": "audio", "audio": args.media}
    else:
        media_ele = {"type": "video", "video": args.media, "fps": args.fps}
        if args.max_pixels:
            media_ele["max_pixels"] = args.max_pixels

    messages = [
        {"role": "system", "content": [{"type": "text", "text": args.sys}]},
        {"role": "user", "content": [media_ele, {"type": "text", "text": args.prompt}]},
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    use_audio = args.audio
    try:
        audios, images, videos = process_mm_info(messages, use_audio_in_video=use_audio)
        inputs = processor(text=text, audio=audios, images=images, videos=videos,
                           return_tensors="pt", padding=True).to("cuda")
    except Exception as e:
        # 音轨链路依赖（ffmpeg/audioread/decord 等）在部分机器上不全：降级为纯画面通道，
        # 不让整轮分析挂掉。降级是信息损失，必须在 stderr 里说清楚并在输出中注明无语音证据。
        if not use_audio:
            raise
        print("[warn] 音轨处理失败（%s），自动降级为 --no-audio 纯画面通道；"
              "本次输出不含任何语音信息。彻底修请补齐 ffmpeg/audioread/decord 后重跑。"
              % e.__class__.__name__, file=sys.stderr, flush=True)
        use_audio = False
        audios, images, videos = process_mm_info(messages, use_audio_in_video=False)
        inputs = processor(text=text, audio=audios, images=images, videos=videos,
                           return_tensors="pt", padding=True).to("cuda")

    n_tok = inputs["input_ids"].shape[-1]
    print("[input] tokens=%d  vram=%.2fGB" % (
        n_tok, torch.cuda.memory_allocated() / 1024 ** 3), file=sys.stderr, flush=True)
    if n_tok > 3000:
        print("[warn] 输入 token 偏大（%d），生成会慢一个数量级；可加大 --max-pixels 压缩力度"
              "（不得低于 100352 下限）或降低 --fps。" % n_tok, file=sys.stderr, flush=True)

    torch.cuda.reset_peak_memory_stats()
    t1 = time.time()
    with torch.no_grad():
        # 注意：thinker 模型不接受 return_audio（那是 talker 的参数）
        gen_kw = dict(use_audio_in_video=use_audio,
                      max_new_tokens=args.max_new, do_sample=False,
                      repetition_penalty=args.rep_pen)
        if args.ngram_rep > 0:
            gen_kw["no_repeat_ngram_size"] = args.ngram_rep
        out = model.generate(**inputs, **gen_kw)
    dt = time.time() - t1
    n_new = out.shape[-1] - n_tok
    print("[gen] %.1fs  new_tokens=%d  %.1ftok/s  peak=%.2fGB" % (
        dt, n_new, n_new / dt if dt else 0,
        torch.cuda.max_memory_allocated() / 1024 ** 3), file=sys.stderr, flush=True)

    # 必须裁掉输入部分，否则会把 prompt 一并 decode 出来
    print(processor.batch_decode(out[:, n_tok:], skip_special_tokens=True,
                                 clean_up_tokenization_spaces=False)[0].strip())


if __name__ == "__main__":
    main()
