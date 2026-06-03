# ComfyUI-OnlySeedance2.0

火山方舟 Doubao **Seedance 2.0** 视频生成节点：文生 / 图生（首尾帧）/ 多模态参考（图·视频·音频），原生音频，输出 ComfyUI 原生 `VIDEO`。素材全部 base64 内联直传火山，不经任何第三方云、不走代理。

**节点**（菜单 `Seedance 2.0`）：
`配置(API)` → `输入(首尾帧 或 参考素材)` → `视频生成`

**用法**：在[火山方舟](https://console.volcengine.com/ark)开通 Seedance、拿 API Key 填进配置节点；按工作流选一个输入节点写提示词、接素材（参考类连一个自动长一个，上限 图9/视频3/音频3）；接到生成节点设分辨率、时长即可。输出 `VIDEO` 接 Save Video 保存。

许可证：GPL-3.0
