---
title: "AI API 接入实测：大模型接口的选型、配置与成本"
description: "大模型 API 聚合服务的实测记录：Claude Code、Codex CLI、Cursor 等工具怎么接入，模型怎么选、成本怎么算、报错怎么排查，以及聚合服务相对官方直连的取舍。"
updated: 2026-10-04
---

这一栏解决的问题和机场那一栏不一样：**机场解决「网络通不通」，这里解决「模型调不调得到」。**

能稳定访问境外服务之后，下一个卡点通常是账号与支付：官方 API 要境外信用卡、要分别开号、要按各家不同的协议写代码。API 聚合服务就是冲这个来的——一个 Key、一套协议，调通 100+ 个模型，覆盖 Claude、GPT、Gemini、DeepSeek、通义千问、豆包、智谱 GLM、Kimi、MiniMax 等十余家厂商。

## 先想清楚要不要用聚合服务

不是所有人都需要。先看这张对照表：

| 你的情况 | 建议 |
| --- | --- |
| 只用一家模型，已经有官方账号和支付方式 | 直接用官方，少一跳链路，延迟和可用性都更可控 |
| 要在 Claude、GPT、Gemini 之间来回对比 | 聚合最省事，不用维护三套 Key 和三套 SDK 配置 |
| 用 Claude Code / Codex CLI 这类工具，但官方账号不好搞 | 聚合是最快的通路，通常只改一个 `base_url` |
| 关键业务、对可用性和延迟有硬要求 | 先小额实测。中转链路比官方直连多一跳，这一点要有心理预期 |

聚合服务的价值在「省事」和「多模型」，不在「更便宜」。 如果你的场景不需要这两点，官方直连更简单。

## 这里写了什么

* **[Ofox 实测：大模型 API 聚合服务怎么用](ofox/index.html)** —— 当前在用的服务，三种协议兼容性、100+ 模型覆盖哪些厂商、接入方式、适合谁与不适合谁。
* **[OpenRouter 和 Ofox 怎么选](ofox/openrouter-vs-ofox.html)** —— 两家聚合服务的差别在哪，国内场景为什么更推荐 Ofox。
* **[DeepSeek Harness 接入 Ofox](ofox/deepseek-harness-setup.html)** —— 国内网络用 `api.ofox.io`、国际网络用 `api.ofox.ai`，以及 profile 里 provider 路由怎么填。
* **[Claude Code 接入配置指南](ofox/claude-code-setup.html)** —— 从环境变量到 `settings.json`，以及最常见的三个配置错误。
* **[聚合 API 的成本怎么算](ofox/pricing-guide.html)** —— Token 计费与机场流量计费的区别，怎么估自己的月成本。

## 网络前提

用 Claude Code、Codex CLI 这类**本地客户端**时，客户端本身要能访问境外接口。如果你所在网络连不上，先解决这一层：[机场实测与线路选择](../airport/index.html)。

这一点经常被忽略：接口配好了却一直超时，八成不是 API 的问题，而是本地网络出不去。
