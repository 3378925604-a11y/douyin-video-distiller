# -*- coding: utf-8 -*-
"""
本地视频理解 —— Qwen2.5-Omni-7B（Thinker-only + bitsandbytes NF4 4bit）

原生视频通道：把视频按 fps 采样成**带时间戳的帧序列**送进模型，不是抽帧当图片看。
可选同时输入视频音轨（--audio）。

依赖：
  torch / transformers>=4.57 / bitsandbytes / qwen-omni-utils / torchvision>=0.19
模型：
  Qwen2.5-Omni-7B 的 fp16 权重（本地目录），只加载 thinker 部分

用法:
  python analyze_omni.py video.mp4
  python analyze_omni.py video.mp4 "只抄录画面里的所有字幕文字" --fps 2 --max-new 384
  python analyze_omni.py video.mp4 "把口播逐字转写" --audio
  python analyze_omni.py audio.wav "这段音频里有人说话吗？"     # 自动走纯音频通道

环境变量:
  OMNI_MODEL_PATH   Qwen2.5-Omni-7B 权重目录（必填，或用 --model）
  OMNI_FPS          采样帧率，默认 1
  OMNI_MAX_NEW      最大生成 token，默认 512
  OMNI_MAX_PIXELS   单帧像素上限，用于压显存（如 100000）
  OMNI_REP_PEN      重复惩罚，默认 1.1（greedy 输出尾部会退化，靠它压）
  OMNI_USE_AUDIO    1 = 同时输入音轨，默认 0
  OMNI_SYS          系统提示词
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
    ap.add_argument("--max-pixels", type=int, default=None)
    ap.add_argument("--rep-pen", type=float, default=float(os.environ.get("OMNI_REP_PEN", "1.1")))
    ap.add_argument("--sys", default=os.environ.get("OMNI_SYS", "You are a helpful assistant."))
    ap.add_argument("--audio", action="store_true",
                    default=os.environ.get("OMNI_USE_AUDIO", "0") == "1",
                    help="视频以外的音轨也一并输入")
    args = ap.parse_args()

    if not args.model:
        sys.exit("缺少模型目录：请设置 OMNI_MODEL_PATH 或用 --model 指定 Qwen2.5-Omni-7B 权重路径。")
    if not os.path.exists(args.media):
        sys.exit("文件不存在: %s" % args.media)

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
    audios, images, videos = process_mm_info(messages, use_audio_in_video=args.audio)
    inputs = processor(text=text, audio=audios, images=images, videos=videos,
                       return_tensors="pt", padding=True).to("cuda")

    n_tok = inputs["input_ids"].shape[-1]
    print("[input] tokens=%d  vram=%.2fGB" % (
        n_tok, torch.cuda.memory_allocated() / 1024 ** 3), file=sys.stderr, flush=True)

    torch.cuda.reset_peak_memory_stats()
    t1 = time.time()
    with torch.no_grad():
        # 注意：thinker 模型不接受 return_audio（那是 talker 的参数）
        out = model.generate(**inputs, use_audio_in_video=args.audio,
                             max_new_tokens=args.max_new, do_sample=False,
                             repetition_penalty=args.rep_pen)
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
