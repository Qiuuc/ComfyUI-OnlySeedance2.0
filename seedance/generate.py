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
Seedance 2.0 视频生成节点（V3，火山方舟 API）

只负责"生成参数 + 调用"：提示词与素材都从『Seedance 输入』节点的『素材』来。
参数走请求体顶层；素材按 role 进 content。输出原生 VIDEO(含音频) + 尾帧 IMAGE。
"""
import logging

import torch
import folder_paths
from comfy_api.latest import io

from . import client
from ._types import SeedanceConfigType, SeedanceMediaType

logger = logging.getLogger("seedance")

_PLACEHOLDER = torch.zeros((1, 1, 1, 3), dtype=torch.float32)

_DESC = (
    "调用火山方舟 Seedance 2.0 生成视频。提示词与素材(首/尾帧、参考图/视频/音频)全部来自"
    "『Seedance 输入』节点，这里只设生成参数。\n"
    "约束：尾帧需配首帧；『首/尾帧』与『参考素材』二选一；参考音频须搭配图像或视频。\n"
    "输出 视频(含音轨) + 尾帧(可当下一段首帧续写)。"
)

_RATIOS = ["16:9", "9:16", "4:3", "3:4", "21:9", "1:1", "adaptive"]


def _video_from_file(path):
    try:
        from comfy_api.latest import InputImpl
        return InputImpl.VideoFromFile(path)
    except Exception:
        from comfy_api.input_impl import VideoFromFile
        return VideoFromFile(path)


def _has_img(t):
    return t is not None and len(t) > 0


def _build_content(prompt, first_frame, last_frame, ref_images, ref_videos, ref_audios):
    content = [{"type": "text", "text": prompt}] if prompt else []

    def _img(t, role):
        return {"type": "image_url", "image_url": {"url": client.image_to_data_url(t[0])}, "role": role}

    if _has_img(first_frame):
        content.append(_img(first_frame, "first_frame"))
    if _has_img(last_frame):
        content.append(_img(last_frame, "last_frame"))
    for t in ref_images:
        content.append(_img(t, "reference_image"))
    for idx, v in enumerate(ref_videos):
        content.append({"type": "video_url", "video_url": {"url": client.video_to_data_url(v, idx)}, "role": "reference_video"})
    for au in ref_audios:
        content.append({"type": "audio_url", "audio_url": {"url": client.audio_to_data_url(au)}, "role": "reference_audio"})
    return content


class SeedanceVideoGenerator(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SeedanceVideoGenerator",
            display_name="Seedance 2.0 视频生成",
            category="Seedance 2.0",
            description=_DESC,
            inputs=[
                SeedanceConfigType.Input("config", display_name="配置", tooltip="来自『Seedance 配置（API）』节点"),
                SeedanceMediaType.Input("media", display_name="内容", tooltip="来自『Seedance 输入』节点(首尾帧/参考素材)的提示词+素材打包"),
                io.Combo.Input("resolution", display_name="分辨率", options=["480p", "720p", "1080p"], default="1080p",
                    tooltip="输出分辨率(resolution)"),
                io.Combo.Input("ratio", display_name="比例", options=_RATIOS, default="adaptive",
                    tooltip="画面宽高比(ratio)。adaptive=按输入图自适应；纯文生且选 adaptive 时自动按 16:9"),
                io.Boolean.Input("auto_duration", display_name="智能时长", default=False,
                    tooltip="由模型按内容自动决定时长(duration=-1)，开启后忽略下方时长秒"),
                io.Int.Input("duration", display_name="时长秒", default=5, min=4, max=15,
                    tooltip="视频时长秒数(duration)，2.0 支持 4~15；『智能时长』开启时无效"),
                io.Boolean.Input("generate_audio", display_name="生成音频", default=True,
                    tooltip="是否生成原生音频(generate_audio)。Seedance 2.0 招牌能力"),
                io.Boolean.Input("web_search", display_name="联网搜索", default=False,
                    tooltip="允许模型联网检索辅助生成(web_search)"),
                io.Boolean.Input("watermark", display_name="平台水印", default=False,
                    tooltip="是否让平台在视频上加水印(watermark)，一般关"),
                io.Int.Input("seed", display_name="seed", default=-1, min=-1, max=2147483647,
                    tooltip="随机种子(seed)，-1=不固定。固定可复现"),
            ],
            outputs=[
                io.Video.Output(display_name="视频"),
                io.Image.Output(display_name="尾帧"),
            ],
        )

    @classmethod
    def execute(cls, config, media, resolution, ratio, auto_duration, duration,
                generate_audio, web_search, watermark, seed) -> io.NodeOutput:
        bundle = media or {}
        prompt = (bundle.get("prompt") or "").strip()
        first_frame = bundle.get("first_frame")
        last_frame = bundle.get("last_frame")
        ref_images = [t for t in (bundle.get("images") or []) if _has_img(t)]
        ref_videos = [v for v in (bundle.get("videos") or []) if v is not None]
        ref_audios = [a for a in (bundle.get("audios") or []) if a is not None]

        has_first_last = _has_img(first_frame) or _has_img(last_frame)
        has_img_ref = bool(ref_images)
        has_vid_ref = bool(ref_videos)
        has_aud_ref = bool(ref_audios)
        has_any_ref = has_img_ref or has_vid_ref or has_aud_ref

        # —— 约束校验（对齐火山方舟 Seedance 2.0）——
        if _has_img(last_frame) and not _has_img(first_frame):
            raise RuntimeError("连了『尾帧图』但没连『首帧图』；首尾帧模式需同时提供首帧。")
        if has_first_last and has_any_ref:
            raise RuntimeError("『首/尾帧』与『参考素材(参考图/视频/音频)』互斥，请二选一种工作流。")
        if has_aud_ref and not (has_img_ref or has_vid_ref):
            raise RuntimeError("『参考音频』必须搭配『参考图』或『参考视频』使用。")
        if not prompt and not (has_first_last or has_any_ref):
            raise RuntimeError("『Seedance 输入』里至少要填提示词，或连入首帧/参考素材。")

        if ratio == "adaptive" and not (has_first_last or has_img_ref or has_vid_ref):
            ratio = "16:9"

        content = _build_content(prompt, first_frame, last_frame, ref_images, ref_videos, ref_audios)
        params = {
            "resolution": resolution,
            "ratio": ratio,
            "duration": -1 if auto_duration else int(duration),
            "generate_audio": bool(generate_audio),
            "watermark": bool(watermark),
            "return_last_frame": True,
            "seed": int(seed) if seed is not None and seed >= 0 else None,
        }
        if web_search:
            params["tools"] = [{"type": "web_search"}]

        logger.info(f"生成: res={resolution} ratio={ratio} dur={'auto' if auto_duration else duration} "
                    f"audio={generate_audio} 参考[图{len(ref_images)}/视频{len(ref_videos)}/音频{len(ref_audios)}] "
                    f"prompt={prompt[:50]}")

        task_id = client.submit_task(config, content, params)
        video_url, data = client.poll_task(config, task_id)
        path = client.download_video(config, video_url, folder_paths.get_temp_directory(), task_id)
        video = _video_from_file(path)

        last_frame_out = _PLACEHOLDER
        lf_url = (data.get("content") or {}).get("last_frame_url")
        if lf_url:
            try:
                last_frame_out = client.download_image_tensor(config, lf_url)
            except Exception as e:
                logger.warning(f"尾帧下载失败(忽略): {e}")
        return io.NodeOutput(video, last_frame_out)
