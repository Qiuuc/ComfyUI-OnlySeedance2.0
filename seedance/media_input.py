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
Seedance 输入节点（V3）—— 两种工作流各一个，互斥所以分开：

- SeedanceInputFrames   : 首尾帧工作流（提示词 + 首帧/尾帧）
- SeedanceInputReference: 多模态参考工作流（提示词 + autogrow 参考图/视频/音频）

两者都输出『素材』(SEEDANCE_MEDIA)，接同一个生成节点；用哪条工作流就放哪个节点。
参考素材上限对齐火山方舟：参考图 9 / 参考视频 3 / 参考音频 3。
"""
from comfy_api.latest import io
from comfy_api.latest import _io

from ._types import SeedanceMediaType

MAX_IMAGES = 9
MAX_VIDEOS = 3
MAX_AUDIOS = 3

_PROMPT_INPUT = io.String.Input(
    "prompt", display_name="提示词", multiline=True, default="",
    tooltip="视频提示词，直接在此编辑。多镜头可分句描述，可用中英文",
)


def _grow(input_id, display_name, template_input, prefix, max_n):
    return _io.Autogrow.Input(
        input_id, display_name=display_name, optional=True,
        template=_io.Autogrow.TemplatePrefix(input=template_input, prefix=prefix, min=1, max=max_n),
    )


def _vals(d):
    if isinstance(d, dict):
        return [v for _, v in sorted(d.items()) if v is not None]
    if d is None:
        return []
    return [d]


def _empty_bundle(prompt):
    return {
        "prompt": (prompt or "").strip(),
        "first_frame": None, "last_frame": None,
        "images": [], "videos": [], "audios": [],
    }


class SeedanceInputFrames(io.ComfyNode):
    """首尾帧工作流输入：提示词 + 首帧/尾帧。"""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SeedanceInputFrames",
            display_name="Seedance 2.0 输入（首尾帧）",
            category="Seedance 2.0",
            description=(
                "首尾帧工作流的输入：提示词 + 可选首帧/尾帧 → 打包『素材』接生成节点。\n"
                "都不连=纯文生；只连首帧=图生视频；首+尾帧=从首帧到尾帧补全。尾帧需配首帧。\n"
                "本工作流与『参考素材』互斥，要用参考素材请改用另一个输入节点。"
            ),
            inputs=[
                _PROMPT_INPUT,
                io.Image.Input("first_frame", display_name="首帧图", optional=True,
                    tooltip="图生视频首帧(role=first_frame)。不连=纯文生"),
                io.Image.Input("last_frame", display_name="尾帧图", optional=True,
                    tooltip="首尾帧的尾帧(role=last_frame，需同时连首帧图)"),
            ],
            outputs=[SeedanceMediaType.Output(display_name="内容")],
        )

    @classmethod
    def execute(cls, prompt="", first_frame=None, last_frame=None) -> io.NodeOutput:
        bundle = _empty_bundle(prompt)
        bundle["first_frame"] = first_frame
        bundle["last_frame"] = last_frame
        return io.NodeOutput(bundle)


class SeedanceInputReference(io.ComfyNode):
    """多模态参考工作流输入：提示词 + autogrow 参考图/视频/音频。"""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SeedanceInputReference",
            display_name="Seedance 2.0 输入（参考素材）",
            category="Seedance 2.0",
            description=(
                "多模态参考工作流的输入：提示词 + 参考图/视频/音频(连一个自动长一个) → 打包『素材』。\n"
                "上限 图9/视频3/音频3；参考音频须搭配参考图或参考视频。\n"
                "本工作流与『首尾帧』互斥，要用首尾帧请改用另一个输入节点。"
            ),
            inputs=[
                _PROMPT_INPUT,
                _grow("ref_images", "参考图", io.Image.Input("ref_image", display_name="参考图", optional=True), "ref_image", MAX_IMAGES),
                _grow("ref_videos", "参考视频", io.Video.Input("ref_video", display_name="参考视频", optional=True), "ref_video", MAX_VIDEOS),
                _grow("ref_audios", "参考音频", io.Audio.Input("ref_audio", display_name="参考音频", optional=True), "ref_audio", MAX_AUDIOS),
            ],
            outputs=[SeedanceMediaType.Output(display_name="内容")],
        )

    @classmethod
    def execute(cls, prompt="", ref_images=None, ref_videos=None, ref_audios=None) -> io.NodeOutput:
        # 参考图：每个连接可能是批量，拆成单张 (1,H,W,C)
        images = []
        for t in _vals(ref_images):
            for i in range(len(t)):
                images.append(t[i:i + 1])
        bundle = _empty_bundle(prompt)
        bundle["images"] = images[:MAX_IMAGES]
        bundle["videos"] = _vals(ref_videos)[:MAX_VIDEOS]
        bundle["audios"] = _vals(ref_audios)[:MAX_AUDIOS]
        return io.NodeOutput(bundle)
