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

"""Seedance API 配置节点（V3）"""
from comfy_api.latest import io

from .client import DEFAULT_BASE_URL
from ._types import SeedanceConfigType

_DESC = (
    "配置火山方舟(Volcengine Ark) Seedance 视频生成的接入信息：API Key、模型 ID、接入点地址、"
    "轮询与超时参数，输出『配置』接到生成节点。\n"
    "API Key 在火山方舟控制台获取；模型 ID 填你开通的 Seedance 接入点ID或模型名。"
)


class SeedanceConfig(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="SeedanceConfig",
            display_name="Seedance 2.0 配置（API）",
            category="Seedance 2.0",
            description=_DESC,
            inputs=[
                io.String.Input("api_key", display_name="api_key", default="",
                    tooltip="火山方舟 API Key(控制台→API Key 管理获取)，仅本地使用不上传第三方"),
                io.String.Input("model", display_name="model", default="doubao-seedance-2-0-260128",
                    tooltip="Seedance 模型 ID 或接入点ID。2.0: doubao-seedance-2-0-260128 / doubao-seedance-2-0-fast-260128"),
                io.String.Input("base_url", display_name="base_url", default=DEFAULT_BASE_URL,
                    tooltip="方舟 API 基址，默认华北(cn-beijing)。其它区域改这里，末尾到 /api/v3"),
                io.Int.Input("timeout", display_name="timeout", default=60, min=5, max=600, step=5,
                    tooltip="单次 HTTP 请求超时(秒)，不是总等待时间"),
                io.Float.Input("poll_interval", display_name="poll_interval", default=3.0, min=1.0, max=30.0, step=0.5,
                    tooltip="轮询任务状态的间隔(秒)"),
                io.Int.Input("max_wait", display_name="max_wait", default=600, min=30, max=3600, step=30,
                    tooltip="等待一个视频生成完成的最长时间(秒)，超时报错"),
            ],
            outputs=[SeedanceConfigType.Output(display_name="配置")],
        )

    @classmethod
    def execute(cls, api_key, model, base_url, timeout, poll_interval, max_wait) -> io.NodeOutput:
        return io.NodeOutput({
            "api_key": (api_key or "").strip(),
            "model": (model or "").strip(),
            "base_url": ((base_url or "").strip() or DEFAULT_BASE_URL),
            "timeout": int(timeout),
            "poll_interval": float(poll_interval),
            "max_wait": int(max_wait),
        })
