---
layout: brand
kind: brand
title: "Ofox 实测：大模型 API 聚合服务怎么用"
description: "Ofox 的实测记录：一个 Key 调用 100+ 个模型、十余家厂商（远不止 OpenAI、Anthropic、Gemini 三家，还覆盖 Claude、GPT、Gemini、DeepSeek、通义千问、豆包、智谱 GLM、Kimi、MiniMax、Grok 等），兼容三种接口协议，Claude Code 与 Codex CLI 的接入方式、适用场景，以及聚合服务相对官方直连的取舍。"
heading: "Ofox 实测"
aff_top: false
updated: 2026-10-04
---

它解决的是「我不想为每一家模型单独开号、单独配协议」这个问题。一个 API Key、一套协议，覆盖 100+ 个模型、十余家厂商——Claude、GPT、Gemini、DeepSeek、通义千问、豆包、智谱 GLM、Kimi、MiniMax 等都在里面。**「三种协议」说的是接口格式，不是只有三种模型**；Claude Code、Cursor 这类工具基本只改一个 `base_url` 就能接上。代价是多一跳中转链路，关键业务建议先小额实测。

## 模型目录里都有谁

「兼容三种协议」最容易被误读成「只有三家模型」。实际目录里是 **100+ 个模型、十余家厂商**，挑一部分列在这儿（完整清单看官方模型页，或直接请求 `https://api.ofox.io/v1/models`）：

| 厂商 | 代表模型 |
| --- | --- |
| Anthropic | Claude Opus 5.5 / Sonnet 5 / Haiku 4.5 |
| OpenAI | GPT-5.5、GPT-5.4、GPT-5.3 Codex、GPT-4.1 |
| Google | Gemini 3.1 / 2.5 Pro、Nano Banana（图像生成） |
| DeepSeek | DeepSeek V4 Pro / V4 Flash、V4.1 |
| 阿里通义 | Qwen Max / Plus / Turbo、Qwen3 Coder、万相 Wan 3.0（视频生成） |
| 字节豆包 | Doubao Seed 2.1 Pro / Turbo / Code、Seedance 2.5（视频生成） |
| 智谱 GLM | GLM-5.3、GLM-5、GLM-4.7 |
| 月之暗面 Kimi | Kimi K3、Kimi K2.7 Code |
| MiniMax | MiniMax M2.5、M2.1 |
| xAI | Grok 4.7、Grok 4.5 |
| 微软 | MAI Image 2.5 |

> 上表只是挑了一部分有代表性的；模型版本更新很快，具体以官方模型页为准。

## 网络前提与付款方式

**注册和充值需要先能访问境外网络。** 官网 `ofox.ai` 在大陆打不开，注册入口、价目页、充值都在这个域名下，所以开号这一步绕不开科学上网。

**但配好之后，日常调用不需要科学上网。** 模型接口走的是 `api.ofox.io`，国内网络可以直接连上；Claude Code、Cursor 这类本地工具只要把 `base_url` 指向它就能用，不需要一直挂着代理。

**付款支持支付宝和微信。** 不用为它单独办境外信用卡，扫码就能充值——同类服务里，卡住很多人的其实不是技术，而是支付这一步。

还没解决网络问题的话，先看[机场实测与线路选择](../../airport/index.html)。

## 它在工作流里的位置

```
本地工具（Claude Code / Codex CLI / Cursor）
        │
        │  一个 Key；3 种协议格式，100+ 个模型
        ▼
      Ofox 聚合层
        │
   ┌────┼─────┬──────────┐
   ▼    ▼     ▼          ▼
 Claude  GPT  Gemini   …100+ 模型 / 十余家厂商
```

和直连官方相比，多了中间这一层。换来的是：不用给每家官方单独开号、单独维护 Key，不用为不同协议写不同的调用代码，也不必自己处理境外支付。

## 接入方式：基本只改一个变量

它同时兼容 **OpenAI、Anthropic、Gemini** 三种协议。这里要说清楚的是：**「三种协议」指接口格式，不是模型种类**——目录里是 **100+ 个模型、十余家厂商**（详见上一节），换模型通常只改模型名，协议不用动。接入的通用套路是：

1. 在官方控制台拿到 API Key；
2. 把客户端的接口地址（`base_url` / `ANTHROPIC_BASE_URL` 之类）指向 Ofox；
3. 填上 Key，把模型名换成对应的模型标识。

**接入地址要按网络位置选，这一步选错后面全是无效排查：**

| 你的网络 | 接口地址 |
| --- | --- |
| 国内网络（大陆直连） | `https://api.ofox.io/v1` |
| 国际网络（海外 VPS / 海外网络） | `https://api.ofox.ai/v1` |

两个域名只差一个字母，但在大陆直连 `api.ofox.ai` 会直接超时，症状像 Key 失效。完整说明和各客户端的配置见：

* **[DeepSeek Harness 接入 Ofox](deepseek-harness-setup.html)** —— profile 里 provider 路由怎么填；
* **[Claude Code 接入 Ofox](claude-code-setup.html)** —— 环境变量与 `settings.json`，以及三个最常见的配置错误。

> 接入域名以官方文档为准。站内给的是当前可用的取值，若官方调整，以上面两个入口文档里的说明为准。

## 适合谁，不适合谁

**适合：**

* 用 AI 编程工具，但官方账号或支付方式不好搞；
* 需要在多个模型之间来回对比，不想维护多套配置；
* 小团队想统一一个 Key、统一看账单。

**不适合：**

* 只用一家模型、已经有官方账号和境外支付——直连更简单；
* 对延迟和可用性有硬要求的关键业务。中转链路比直连多一跳，这个差别在高峰期是能感知到的；
* 需要模型原生特有能力（某些私有参数、区域端点）的场景，聚合层不一定透传。

## 实测口径说明

本站写的是**能验证的部分**：怎么接、接不上怎么查、成本怎么估。至于「哪个模型更强」这种随时会变、且强依赖具体任务的问题，我不给结论——建议你自己用真实任务跑一遍对比。

## 成本

聚合服务按 Token 计费，和机场按流量计费是两套完全不同的账。很多人第一次用会把这两个概念混起来，估算方式见 [聚合 API 的成本怎么算](pricing-guide.html)。

先看[Ofox 官方模型与价目页](https://ofox.ai/zh/models)确认当前单价，再决定充多少。
