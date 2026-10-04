---
title: "DeepSeek Harness 接入 Ofox 配置指南：国内用 api.ofox.io，国际用 api.ofox.ai"
description: "把 DeepSeek Harness 接到 Ofox 网关的完整配置：为什么国内网络必须用 api.ofox.io、国际网络用 api.ofox.ai，providers 配置字段怎么填、API Key 放在哪里，以及只配一个域名会导致的典型超时现象。"
nav_weight: 5
updated: 2026-10-04
---

# DeepSeek Harness 接入 Ofox：国内用 api.ofox.io，国际用 api.ofox.ai

> ## ⚠️ 先记住这一条，再往下看
>
> | 你所在的网络 | 用哪个接口地址 |
> | --- | --- |
> | **国内网络（大陆直连）** | **`https://api.ofox.io/v1`** |
> | **国际网络（海外 VPS / 海外家宽）** | **`https://api.ofox.ai/v1`** |
>
> **只有一个域名是对的那个。** 在国内把 `baseURL` 填成 `api.ofox.ai`，请求会直接超时，
> 而报错信息通常不会告诉你「域名错了」——它更像 Key 失效或额度用完。
> 这是接 Ofox 时最常见、也最浪费时间的一个坑，所以放在最前面。

DeepSeek Harness 接 Ofox，本质是在 profile 里加一条 provider 路由；难点不在配置本身，而在选对域名。 国内网络的直连域名是 `api.ofox.io`，走的是大陆可达的通道；`api.ofox.ai` 面向国际网络，在大陆直连基本连不上。两个域名只差一个字母，配错了症状却像「Key 挂了」。

## 一、为什么会有两个域名

Ofox 是聚合网关，入口按网络位置分成了两条通道：

| | `api.ofox.io` | `api.ofox.ai` |
| --- | --- | --- |
| 面向网络 | 中国大陆直连 | 国际网络 |
| 国内直连是否可达 | ✅ 可以 | ❌ 通常不通 |
| 典型使用者 | 国内开发机、国内服务器 | 海外 VPS、海外办公网络 |
| 协议路径 | `/v1`、`/anthropic`、`/gemini` | 同左 |

**判断方法很简单：你的机器访问境外服务需不需要代理？**

* 不需要代理就能正常访问境外接口 → 用 `api.ofox.ai`
* 需要先解决网络才能访问境外服务 → 用 `api.ofox.io`

> 实测口径：在国内网络环境下，`api.ofox.io/v1/models` 可以直接返回模型列表；
> `api.ofox.ai/v1/models` 则连接失败。反过来，海外机器直连 `.io` 也能用，
> 只是绕了远路——**所以国内用户不要想着「两个都试试」，先按上表选对。**

## 二、准备 API Key

1. 在 Ofox 控制台创建一个 API Key；
2. **把 Key 存进 DSH 的凭据系统，不要写进配置文件。**

这一点是硬要求：DSH 的 provider 配置里只有 `apiKeyEnv`，它保存的是**凭据引用名**，不是 Key 本身。配置解析时通过 Harness 凭据 seam 按请求取值。

本机凭据记录在 `~/.dsh/.credentials.yaml` 的 `refs` 段（Windows 是 `C:\Users\<你>\.dsh\.credentials.yaml`）：

```yaml
refs:
  OFOX_API_KEY: sk-of-****************
```

引用名要和配置里的 `apiKeyEnv` 完全一致。**名字对不上、或这条记录不存在，请求会以 `MISSING_CREDENTIAL` 失败**——这个错误码的意思是「找不到凭据引用」，不是「Key 无效」。
（注意别把两件事混了：第 4 节用来验域名的 `/v1/models` 列表是公开的，不带 Key 也能通，
但这不代表不带 Key 能正常调用模型——没有 Key 就无法计量与计费，模型请求必然失败。）

## 三、配置：两种方式

### 方式 A：GUI 里填写（推荐先试这个）

DSH 的设置界面可以新增模型端点，填四项：**端点名称、URL、协议、API Key**。URL 填 `https://api.ofox.io/v1`，协议选 OpenAI Responses（或 OpenAI Completions，见下方说明），Key 填你的 Ofox Key。

界面上还有「模型拉取」功能：它会请求 `{baseURL}/models` 把 Ofox 的模型目录列出来，让你直接勾选，不用手抄模型 ID。对 100+ 模型的服务来说这个功能很实用。

### 方式 B：写 `cordis.patch.yml`

手动配置的落点是 profile 的 patch 文件：

* Windows：`C:\Users\<你>\.dsh\profiles\desktop\cordis.patch.yml`
* macOS / Linux：`~/.dsh/profiles/desktop/cordis.patch.yml`

在顶层数组里加一条：

```yaml
- id: llm-pi-ai
  name: "@deepseek-ai/dsh-llm-pi-ai"
  config:
    providers:
      ofox:
        displayName: Ofox
        apiKeyEnv: OFOX_API_KEY
        api: openai-responses
        baseURL: https://api.ofox.io/v1     # 国内网络；国际网络改成 https://api.ofox.ai/v1
        models:
          - id: deepseek/deepseek-v4-pro-0423
            name: "DeepSeek: V4 Pro"
            contextWindow: 1000000
            maxTokens: 128000
          - id: anthropic/claude-sonnet-5
            name: "Anthropic: Claude Sonnet 5"
            contextWindow: 1000000
            maxTokens: 128000
```

改完保存即生效。DSH 在每个请求前解析 profile 与凭据，所以**新增或修改 provider 不需要重启**。

### 关于 `api` 这个字段

它决定用哪套协议发请求：`openai-responses`、`openai-completions`、`anthropic-messages`。对接网关选前两个都行：

* 选 `openai-responses`：能覆盖 Ofox 上那批 **responses-only 的模型**（截至 2026-10，`openai/gpt-5.3-codex`、`openai/gpt-5.4-pro` 这类只提供 `/v1/responses` 端点）。如果你要用 Codex 系列，必须选这个。
* 选 `openai-completions`：兼容面最广，但不支持上面那批模型，而且 `responses-only` 的模型用它会在请求阶段被拒。

**不确定就选 `openai-responses`。** 对 Ofox 来说它是更完整的那个。

### 关于 `models` 的硬性规则

这条很关键，配错了会被直接拒绝保存：

* **手工声明的路由，`models` 不能为空**。`api`、`baseURL`、非空 `models` 三者缺一，profile 在写入处就会被拒。
* **`models` 是整体替换，不是追加**。写两个就只服务两个——不会跟内置目录合并。
* **`models` 和 `modelOverrides` 不能同时用**。想「只改内置目录里的某一个模型、其余保留」，用 `modelOverrides`，但它只对内置目录路由有效，自定义网关不能用。

对多数人来说，选「只服务我常用的两三个模型」就够了——路由越窄，模型选择器越干净。

## 四、验证接上了没有

按顺序做三步，能一次分清是网络问题、凭据问题还是模型问题：

1. **先单独验域名连通性**（不经过 DSH，也不消耗额度）：

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://api.ofox.io/v1/models
   ```

   返回 `200` 就说明这个域名在国内网络下可达；**卡住不动或报连接失败，就是域名选错了**。
   换成 `https://api.ofox.ai/v1/models` 对比一次，两个域名的差别会非常直观。

   > 这个模型列表接口是公开的，不带 Key 也能返回 200，所以它验证的是**网络与域名**，
   > 不验证 Key。Key 有没有问题要在第 3 步才会体现。

2. **再看 DSH 的模型选择器里有没有出现 Ofox**。没出现说明 profile 没生效或被拒。
3. **发一句话试跑**。跑不通时看错误码：`MISSING_CREDENTIAL` 是凭据引用没解析到，`UNKNOWN_MODEL` 是模型 ID 不在该路由目录里，`INVALID_CREDENTIAL` 才是 Key 本身有问题。

## 五、报错对照表

| 现象 | 大概率原因 | 先查什么 |
| --- | --- | --- |
| 请求一直挂起、最终超时，没有明确 HTTP 错误 | **域名选错**（国内用了 `api.ofox.ai`） | 按第一节的表换成 `api.ofox.io`；用第四节的 curl 单独验一次连通性 |
| `MISSING_CREDENTIAL` | `apiKeyEnv` 指向的引用名不存在或解析为空 | 核对 `~/.dsh/.credentials.yaml` 里 `refs` 的键名是否与配置完全一致 |
| `INVALID_CREDENTIAL` | 引用解析到了，但 Key 被服务端拒绝 | 到 Ofox 控制台确认 Key 是否被禁用、是否有多余空格 |
| `UNKNOWN_MODEL` | 模型 ID 不在该路由的 `models` 列表里 | 用模型拉取功能核对 ID；注意 ID 带 provider 前缀 |
| 配置保存被拒绝 | `models` 为空，或 `models` 与 `modelOverrides` 并用 | 补上至少一个模型条目，二选一 |
| `QUOTA` / `RATE_LIMIT` | 额度用尽或触发限流 | 看控制台余额；降低并发 |

**「一直超时且没有明确错误」这一行值得单独记住**：pi-ai 的错误事件不跨 provider 暴露稳定的 HTTP 状态，所以连接层面的问题往往表现得很难判断，第一反应应该是回去检查域名，而不是怀疑 Key。

## 六、切换模型与推理强度

模型选择器里的名字来自你写的 `models` 列表。要换模型：

* 加一个新条目（`id`、`name`、`contextWindow`、`maxTokens`），或用界面上的拉取功能勾选；
* ID 一定从模型目录复制，别凭记忆写——**ID 带 provider 前缀**（如 `anthropic/claude-sonnet-5`），少一段就是 `UNKNOWN_MODEL`。

推理强度（`reasoningEffort`）有两层：agent 的默认值在 profile 的 `agent-default-model` 里，单个模型的能力则在 provider 或模型条目上声明。需要给某个模型单独开放等级时才写 `reasoningEfforts`；**自定义模型不写就没有推理能力**，因为 `models` 是整体替换，不会继承内置目录的推理档位。

## 七、快速对照表

| 配置项 | 值 |
| --- | --- |
| `id`（路由名） | `ofox` |
| `apiKeyEnv` | `OFOX_API_KEY`（与 `~/.dsh/.credentials.yaml` 的 `refs` 键名一致） |
| `api` | `openai-responses` |
| `baseURL`（国内） | `https://api.ofox.io/v1` |
| `baseURL`（国际） | `https://api.ofox.ai/v1` |
| `models` | 至少一条，`id` 带 provider 前缀 |

## 八、下一步

* 还不确定要不要用网关：见 [Ofox 实测](index.html) 的「适合谁、不适合谁」；
* 想算清楚花多少钱：见 [聚合 API 的成本怎么算](pricing-guide.html)；
* 用 Claude Code 而不是 DSH：见 [Claude Code 接入配置指南](claude-code-setup.html)；
* 本地网络本身就出不去：先解决网络层，见 [机场实测与线路选择](../../airport/index.html)。

## 参考

* [DSH llm-pi-ai 参数参考（官方 README）](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-pi-ai/README.zh.md)
* [llm-pi-ai 参数速查（社区整理）](https://github.com/MarvekG/deepseek-harness-model-config/blob/main/docs/llm-pi-ai-parameters.md)
* [Ofox 官方接入文档](https://ofox.ai/zh/docs/integrations/deepseek-harness)
