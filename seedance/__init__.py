# ComfyUI-Seedance — Seedance 节点子包
# GPL-3.0 (见仓库 LICENSE)
"""
- config      : Seedance 配置(API Key / 模型 / 接入点)
- media_input : 两个输入节点 —— 首尾帧工作流 / 参考素材工作流(互斥，故分开) → 素材
- generate    : Seedance 视频生成(素材包 + 参数 → 视频)
节点用 V3 io.ComfyNode 定义，经顶层 comfy_entrypoint 注册(autogrow 需要)。
"""
from .config import SeedanceConfig
from .media_input import SeedanceInputFrames, SeedanceInputReference
from .generate import SeedanceVideoGenerator

NODES = [SeedanceConfig, SeedanceInputFrames, SeedanceInputReference, SeedanceVideoGenerator]
