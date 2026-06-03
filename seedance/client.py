# ComfyUI-Seedance
# Copyright (C) 2026 Qiuuc
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
火山方舟(Volcengine Ark) Seedance 视频生成 API 客户端

异步任务式接口：
  1. POST {base_url}/contents/generations/tasks         → 返回 {"id": "cgt-..."}
  2. GET  {base_url}/contents/generations/tasks/{id}     → 轮询 status，成功后取 content.video_url
鉴权：Authorization: Bearer <ARK_API_KEY>

参数(分辨率/比例/时长/帧率/种子等)以 `--key value` 命令的形式拼在 text 提示词里，
图像(首帧/尾帧/参考图)作为 content 数组里的 image_url 条目、用 role 区分用途。
注：role 取值与可用 `--` 参数随模型版本而变，请对照所用 Seedance 模型的官方文档核对。
"""
import base64
import logging
import os
import time
from io import BytesIO

import numpy as np
import requests
from PIL import Image

logger = logging.getLogger("seedance")

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# 复用 HTTP 连接。trust_env=False：忽略系统/环境代理，直连火山方舟，
# 不让任何代理中间方经手数据，也避免占用代理流量。
_session = requests.Session()
_session.trust_env = False


def image_to_data_url(img_tensor, fmt="JPEG", quality=92):
    """ComfyUI IMAGE 单帧张量 (H,W,C) 0~1 → base64 data URL，直接塞进 image_url。"""
    arr = (img_tensor.cpu().numpy().clip(0.0, 1.0) * 255.0).astype(np.uint8)
    if arr.ndim == 3 and arr.shape[-1] == 4:
        arr = arr[..., :3]
    pil = Image.fromarray(arr)
    if fmt == "JPEG" and pil.mode != "RGB":
        pil = pil.convert("RGB")
    buf = BytesIO()
    pil.save(buf, format=fmt, **({"quality": quality} if fmt == "JPEG" else {}))
    mime = "jpeg" if fmt == "JPEG" else "png"
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/{mime};base64,{b64}"


def audio_to_data_url(audio):
    """ComfyUI AUDIO({waveform:(B,C,T), sample_rate}) → wav base64 data URL。"""
    import io
    import wave
    waveform = audio.get("waveform") if isinstance(audio, dict) else None
    sr = int((audio.get("sample_rate") if isinstance(audio, dict) else 0) or 0)
    if waveform is None or sr <= 0:
        raise RuntimeError("无效的音频输入(缺 waveform / sample_rate)。")
    wf = waveform.detach().cpu().numpy() if hasattr(waveform, "detach") else np.asarray(waveform)
    if wf.ndim == 3:
        wf = wf[0]            # (C,T) 取第一条
    if wf.ndim == 1:
        wf = wf[None, :]
    data = np.clip(wf.T, -1.0, 1.0)          # (T,C)
    pcm = (data * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:audio/wav;base64,{b64}"


def video_to_data_url(video, index=0):
    """ComfyUI VIDEO → base64 data URL，直接内联给火山方舟，不经任何外部托管/上传。"""
    import os
    import folder_paths
    from comfy_api.util import VideoContainer
    tmp_dir = folder_paths.get_temp_directory()
    os.makedirs(tmp_dir, exist_ok=True)
    tmp = os.path.join(tmp_dir, f"seedance_refvid_{index}.mp4")
    video.save_to(tmp, format=VideoContainer("mp4"), codec="auto", metadata=None)
    try:
        with open(tmp, "rb") as f:
            raw = f.read()
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
    mb = len(raw) / (1024.0 * 1024.0)
    if mb > 8:
        logger.warning(f"参考视频较大({mb:.1f}MB)内联编码，可能超出接口请求体上限；如失败请改用更短/更低清的片段。")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:video/mp4;base64,{b64}"


def _headers(cfg, json_body=False):
    h = {"Authorization": f"Bearer {cfg['api_key']}"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def submit_task(cfg, content, params=None):
    """创建视频生成任务，返回 task_id。

    params: Seedance 2.0 的顶层请求体参数(resolution/ratio/duration/seed/
    watermark/generate_audio/return_last_frame 等)，None 值会被剔除。
    """
    if not cfg.get("api_key"):
        raise RuntimeError("未配置 API Key，请在『Seedance 配置』节点填入火山方舟 API Key。")
    url = cfg["base_url"].rstrip("/") + "/contents/generations/tasks"
    body = {"model": cfg["model"], "content": content}
    for k, v in (params or {}).items():
        if v is not None:
            body[k] = v
    resp = _session.post(url, headers=_headers(cfg, json_body=True), json=body, timeout=cfg["timeout"])
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"创建任务失败 HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    task_id = data.get("id")
    if not task_id:
        raise RuntimeError(f"接口未返回任务 ID: {data}")
    logger.info(f"已提交任务 {task_id} (model={cfg['model']})")
    return task_id


def _interrupted():
    """ComfyUI 取消执行时返回 True（best-effort）。"""
    try:
        import comfy.model_management as mm
        return mm.processing_interrupted()
    except Exception:
        return False


def poll_task(cfg, task_id):
    """轮询任务直到完成，返回 (video_url, 完整响应)。失败/超时/取消抛异常。"""
    url = cfg["base_url"].rstrip("/") + f"/contents/generations/tasks/{task_id}"
    interval = max(1.0, float(cfg["poll_interval"]))
    max_wait = int(cfg["max_wait"])
    waited = 0.0
    last_status = None
    while True:
        if _interrupted():
            raise RuntimeError("已被用户取消。")
        resp = _session.get(url, headers=_headers(cfg), timeout=cfg["timeout"])
        if resp.status_code != 200:
            raise RuntimeError(f"查询任务失败 HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        status = data.get("status")
        if status != last_status:
            logger.info(f"任务 {task_id} 状态: {status}")
            last_status = status
        if status == "succeeded":
            video_url = (data.get("content") or {}).get("video_url")
            if not video_url:
                raise RuntimeError(f"任务成功但无 video_url: {data}")
            return video_url, data
        if status in ("failed", "cancelled"):
            raise RuntimeError(f"任务{status}: {data.get('error') or data}")
        # queued / running → 继续等
        if waited >= max_wait:
            raise RuntimeError(f"等待超时({max_wait}s)，最后状态={status}。可在配置节点调大『最大等待』。")
        time.sleep(interval)
        waited += interval


def download_image_tensor(cfg, image_url):
    """下载一张图片(如返回的尾帧 PNG)，转成 ComfyUI IMAGE 张量 (1,H,W,3)。"""
    import torch
    resp = _session.get(image_url, timeout=cfg["timeout"])
    resp.raise_for_status()
    pil = Image.open(BytesIO(resp.content)).convert("RGB")
    arr = np.asarray(pil).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]


def download_video(cfg, video_url, dest_dir, basename):
    """流式下载视频到 dest_dir，返回本地路径。"""
    os.makedirs(dest_dir, exist_ok=True)
    safe = "".join(c for c in str(basename) if c.isalnum() or c in "-_") or "seedance"
    path = os.path.join(dest_dir, f"{safe}.mp4")
    with _session.get(video_url, stream=True, timeout=cfg["timeout"]) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    logger.info(f"视频已下载: {path}")
    return path
