# 第三方许可声明 / Third-Party Notices

music3 音乐工作室 使用以下第三方软件与模型。本文件随软件分发的每一份副本一同提供。

---

## 1. MiniMax-Music3（音乐生成模型）

本软件生成的音频由 **MiniMax-Music3** 模型产生。

- 许可协议：**MiniMax-Music3 Community License**（完整文本见 `LICENSE-MINIMAX-MUSIC3.txt`）
- 版权归 MiniMax 所有
- 获取地址：https://huggingface.co/MiniMaxAI/MiniMax-Music3
  （国内镜像：https://hf-mirror.com/MiniMaxAI/MiniMax-Music3）
- 界面署名：本软件在界面中显著标注 "MiniMax-Music3"，以满足该许可的 Commercial Terms 第 1 条。

MiniMax-Music3 的上游组件：

| 组件 | 来源 | 许可 |
|---|---|---|
| Qwen3-8B（文本编码器基础） | https://huggingface.co/Qwen/Qwen3-8B | Apache License 2.0 |
| Stable Audio Tools（DiT-2B 基础） | https://github.com/Stability-AI/stable-audio-tools | MIT License |
| DAC（音频编解码器 / VAE 基础） | https://github.com/descriptinc/descript-audio-codec | MIT License |

---

## 2. ComfyUI（本地推理运行时）

- 主页：https://github.com/comfyanonymous/ComfyUI
- 许可：GPL-3.0

> **重要**：music3 通过 HTTP API **调用**用户本机已安装的 ComfyUI，不包含、不分发、不链接 ComfyUI 的任何代码。
> ComfyUI 与其模型权重由用户自行获取与安装。music3 与 ComfyUI 之间的交互仅为 HTTP 协议调用。

---

## 3. Python 软件基金会 / 其他 Python 包

本软件使用了标准库之外的以下第三方 Python 包：

| 包 | 用途 | 许可 |
|---|---|---|
| PyInstaller | 打包为可执行文件 | GPL-2.0-or-later（打包工具，不随运行时分发） |

其余功能全部基于 Python 标准库实现（http.server、urllib、json、tkinter 等）。

---

## 4. 字体

界面使用操作系统自带字体（Windows: Microsoft YaHei UI；macOS: 系统 UI 字体），不随软件分发字体文件。

---

## 5. MiniMax 文本 API（可选功能）

「AI 写词 / AI 写编曲说明」功能会调用 MiniMax 文本接口。此为可选功能，用户需自行提供 API Key。
使用该功能时，请求内容会发送至 MiniMax 服务器。请查阅 MiniMax 的隐私政策与服务条款。

**不启用该功能时，全部推理在本机完成，提示词与音频不会离开用户设备。**
