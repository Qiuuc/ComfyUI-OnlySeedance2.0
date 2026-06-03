# ComfyUI-Seedance
# GPL-3.0 (见仓库 LICENSE)
"""共享的自定义连线类型(V3 io.Custom)。两端引用同一 io_type 字符串即可连通。"""
from comfy_api.latest import io

SeedanceConfigType = io.Custom("SEEDANCE_CONFIG")
SeedanceMediaType = io.Custom("SEEDANCE_MEDIA")
