---
name: douyin-video-download
description: 解析抖音分享链接，下载无水印视频和图集。当用户提供抖音分享链接（v.douyin.com、www.iesdouyin.com、www.douyin.com）时，通过本机浏览器已登录会话（CDP）提取真实视频地址并下载。支持视频和图集两种内容类型。
---

# 抖音视频下载

解析抖音分享链接 → 下载无水印视频 / 图集。**唯一可行路径是下面的 CDP 登录态提取法**——抖音 2025 年中起对纯 HTTP 解析全面上反爬，任何"直接请求页面拿 `_ROUTER_DATA`"或"yt-dlp + cookie"的做法都会失败或拿到壳页，不要浪费时间尝试。

## 前置条件

- 用户电脑上 Edge 或 Chrome **网页版抖音（www.douyin.com）处于登录状态**
- 本机有 Python（含 `websockets` 库）、curl、ffmpeg（图集/Live Photo 不需要 ffmpeg）
- 需要关闭现有浏览器进程（会向用户说明后再执行）；不绕过验证码、登录墙或风控，只使用用户自己的已登录会话

## 执行流程（CDP 登录态提取法，已验证）

1. **解析短链**：`https://v.douyin.com/xxx/` 用 **GET**（HEAD 会 404）跟随重定向，拿到 `www.douyin.com/video/<id>` 或图集地址。
2. **强杀浏览器进程**（Edge 为例：`Stop-Process -Name msedge -Force`），否则调试参数不生效。
3. **带调试端口重启并打开目标页**（端口避开常被屏蔽的 9222，用 9333；参数含空格时不要带 `--user-data-dir`）：
   ```
   msedge.exe --remote-debugging-port=9333 --remote-allow-origins=* "https://www.douyin.com/video/<id>"
   ```
   ⚠️ **Chromium/Edge 136+ 起禁止在默认 user-data-dir 上开调试端口**（参数会被静默忽略）。绕过法（2026-09-21 同学机 Edge 153 验证）：`mklink /J C:\edgeprof "%LOCALAPPDATA%\Microsoft\Edge\User Data"` 建一个**无空格 junction** 指向真实 profile，再带 `--user-data-dir=C:\edgeprof` 启动即可保留登录态；**收尾必须 `rmdir C:\edgeprof` 只删联接**，原 profile 完好。
4. 等 14~20 秒，访问 `http://127.0.0.1:9333/json` 拿 page target 的 `webSocketDebuggerUrl`。
5. CDP `Runtime.evaluate` 执行 `document.querySelector('video').currentSrc` → 得到 `douyinvod.com` 真实流地址。
6. 若 `currentSrc` 是 `blob:`（MSE 分段流）：改用 CDP **Network 域**监听收集 `douyinvod.com` 的 media 请求（视频、音频是分离的两条流），分别下载后 `ffmpeg -c copy` 合并。
7. 下载时带浏览器 UA + `Referer: https://www.douyin.com/`；下完用 ffprobe 核对分辨率/时长/编码。
8. **收尾**：关闭调试实例并正常重启浏览器；把保存路径告知用户；不输出、不留存签名直链和 Cookie。**用了 junction 的，收尾必须 `rmdir C:\edgeprof` 删掉联接本身——删前用 `fsutil reparsepoint query C:\edgeprof` 或 `Get-Item C:\edgeprof` 确认 Attributes 含 ReparsePoint；严禁 `rm -rf` / `Remove-Item -Recurse`（那会顺着联接删掉用户真实的 Edge 配置，等于毁掉他所有浏览器 profile）。**

## 输出

- 视频：`<视频ID>.mp4`（下载到任务临时目录或用户指定目录）
- 图集链接：页面内逐张图片走同一 CDP 会话提取 `img` 资源地址下载

## 失败处理

- 拿不到 `currentSrc` 且 Network 无 media 请求：多半是页面没加载完或登录态失效 → 让用户在浏览器里手动打开该视频确认能播，再重试一次；仍失败如实报告
- 9333 端口无响应：确认浏览器进程真的被杀干净、调试参数生效（`netstat -ano | findstr 9333`）
- 私密/已删除/付费内容：如实报告，不尝试绕过
- 用户手动下载了视频给来路径：直接当本地文件进入后续流程，不必走 CDP

## 已失效路径（保留说明防止 AI 重蹈覆辙）

`scripts/download_douyin_video.py`（纯 HTTP 解析 `_ROUTER_DATA`）已被抖音反爬淘汰，通常只返回无数据的壳页；`scripts/` 目录仅作历史存档，**不要执行、不要在其上调试**。
