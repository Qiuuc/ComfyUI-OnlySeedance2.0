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
ComfyUI-Seedance —— 火山方舟(Volcengine Ark) Doubao Seedance 视频生成

节点(V3，经 comfy_entrypoint 注册，以启用原生 autogrow 动态输入)：
- Seedance 配置(API)   : 填 API Key / 模型 ID / 接入点
- Seedance 输入        : 提示词 + 首/尾帧 + 参考素材(图/视频/音频，连一个长一个)
- Seedance 视频生成    : 素材包 + 参数 → VIDEO
"""
import logging
import sys

from comfy_api.latest import ComfyExtension

# 统一控制台输出：logging.getLogger("seedance") 的消息自动加 [Seedance] 前缀。
_log = logging.getLogger("seedance")
if not getattr(_log, "_seedance_configured", False):
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("[Seedance] %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)
    _log.propagate = False
    _log._seedance_configured = True

from .seedance import NODES

__version__ = "1.0.0"


class SeedanceExtension(ComfyExtension):
    async def get_node_list(self):
        return NODES


async def comfy_entrypoint() -> ComfyExtension:
    return SeedanceExtension()


print(f"\033[36m[Seedance]\033[0m v{__version__} \033[92m已加载\033[0m {len(NODES)} 个节点")
