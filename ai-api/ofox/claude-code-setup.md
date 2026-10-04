---
title: "Claude Code 接入 Ofox 配置指南：环境变量怎么设、报错怎么查"
description: "把 Claude Code 接到 Ofox 聚合 API 的完整配置步骤：ANTHROPIC_BASE_URL 与 ANTHROPIC_AUTH_TOKEN 怎么设、写进 settings.json 还是 shell 配置、401/404/超时分别是什么原因，以及怎么切回官方。"
nav_weight: 10
updated: 2026-10-04
---

# Claude Code 接入 Ofox：环境变量怎么设、报错怎么查

Claude Code 接第三方接口，本质上就是设两个环境变量：`ANTHROPIC_BASE_URL` 和 `ANTHROPIC_AUTH_TOKEN`。 大部分「接不上」的问题不是接口坏了，而是变量没生效、URL 多了一个斜杠、或者两套凭证同时存在互相打架。

## 一、原理：Claude Code 是怎么找到接口的

Claude Code 默认连 Anthropic 官方接口。它认这几个环境变量：

| 变量 | 作用 |
| --- | --- |
| `ANTHROPIC_BASE_URL` | 接口地址。改这个就把请求指向聚合服务 |
| `ANTHROPIC_AUTH_TOKEN` | 第三方接口的凭证，直接作为 Bearer Token 使用 |
| `ANTHROPIC_API_KEY` | 官方 Key。**接第三方时不要同时设**，容易互相覆盖 |
| `ANTHROPIC_MODEL` / `ANTHROPIC_SMALL_FAST_MODEL` | 指定主模型与轻量模型，按服务商支持的模型名填 |

> 变量名和取值以 [Ofox 官方接入文档](https://ofox.ai/zh/docs/integrations/claude-code) 为准。这类服务偶尔会调整地址和模型名，下面讲的是方法，不是会过期的常量。

## 二、两种配置方式，选一种

### 方式 A：写进 Claude Code 的配置文件（推荐）

Claude Code 支持在 `~/.claude/settings.json` 里通过 `env` 段注入环境变量。好处是**跟着工具有效，不依赖你从哪个终端启动**：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "<官方文档给出的接口地址>",
    "ANTHROPIC_AUTH_TOKEN": "<你的 Ofox API Key>"
  }
}
```

注意这是 JSON，**不能有注释、不能有尾逗号**。文件放错位置或语法错一个字符，配置就会静默失效——Claude Code 不会报「配置文件解析失败」，只会继续连官方接口，于是你看到的是认证错误，而不是配置错误。

### 方式 B：写进 shell 配置

临时验证用 `export`，长期使用写进 `~/.zshrc`（macOS 默认）或 `~/.bashrc`：

```bash
export ANTHROPIC_BASE_URL="<官方文档给出的接口地址>"
export ANTHROPIC_AUTH_TOKEN="<你的 Ofox API Key>"
```

改完要重开终端或 `source` 一次才生效。**Windows 上用 `setx` 设置的是用户级环境变量，需要重启终端**，在同一个窗口里测是测不出来的。

### 方式 C：用 CC Switch 之类的切换工具

如果你同时要在官方和聚合服务之间来回切，手改环境变量会很烦。CC Switch 这类工具把多套配置存成 profile，切换时改写 Claude Code 与 Codex CLI 的配置文件。

用这类工具要注意一点：**它改写的是同一份配置文件**，所以切换后如果行为不对，先打开 `settings.json` 看看里面到底写的是哪一套，而不是怀疑接口。

## 三、验证是否接上了

配完先做一次最小验证，别直接开工：

1. 新开一个终端窗口（确保变量生效）；
2. 启动 `claude`，问一句最简单的问题，例如「回复 ok」；
3. 能正常回复，说明链路通了；报错就进下一节。

想确认请求真的走了聚合服务，看客户端的用量或日志页面有没有新增调用记录——**这是唯一可靠的判断方式**，凭感觉「好像变快了/变慢了」都不算。

## 四、三个最常见的坑

### 1. base_url 末尾多了一个斜杠

`https://xxx.com` 和 `https://xxx.com/` 在字符串层面不一样。有些客户端会拼成 `//v1/messages`，直接 404。

**处理：严格照官方文档抄，别自己补斜杠，也别自己加 `/v1`。** 路径前缀该不该带，文档会写清楚。

### 2. 两套凭证同时存在

`ANTHROPIC_API_KEY` 和 `ANTHROPIC_AUTH_TOKEN` 同时设置时，优先级容易搞混，表现是间歇性 401。

**处理：接第三方时把官方 Key 清掉**（`unset ANTHROPIC_API_KEY`，并检查 shell 配置里有没有残留的 `export`）。

### 3. 换了接口但模型名没换

聚合服务的模型标识不一定和官方同名。填了一个它不认识的模型名，通常报 404 或 400。

**处理：模型名从服务商的模型列表页复制，不要凭记忆写。** 先用一个确定存在的模型验证链路，再换你要用的那个。

## 五、报错对照表

| 现象 | 大概率原因 | 先查什么 |
| --- | --- | --- |
| 401 Unauthorized | Key 错、Key 被禁用、两套凭证打架 | 检查 Key 有没有多余空格；确认官方 Key 已清除 |
| 403 Forbidden | Key 权限不足或额度耗尽 | 到服务商后台看余额与权限 |
| 404 Not Found | base_url 路径错、多了斜杠、模型名不存在 | 逐字符比对官方文档 |
| 400 Bad Request | 模型名或参数不被支持 | 换一个已知存在的模型试 |
| 429 Too Many Requests | 触发限流 | 降并发；确认套餐的速率限制 |
| 一直超时、无响应 | **本地网络出不去**，不是 API 的问题 | 见下方 |

最后一行是最容易被误判的：接口配得再对，本地连不上境外服务也调不通。这类情况先解决网络层，再回来查配置——判断方法和处理顺序见 [机场突然用不了怎么排查](../../guides/proxy-down-diagnosis.html)。

## 六、怎么切回官方

三条路，按彻底程度排序：

* 删掉 `settings.json` 里的 `env` 段，恢复官方直连；
* 或把 `ANTHROPIC_BASE_URL` 换回官方地址，`ANTHROPIC_AUTH_TOKEN` 换成 `ANTHROPIC_API_KEY`；
* 用 CC Switch 切 profile（最省事，但要确认它确实改对了文件）。

**建议保留一份配置备份。** 环境变量这类东西一旦被覆盖，回溯起来很费时间。

## 七、下一步

* 还没决定要不要用聚合服务：先看 [Ofox 实测](index.html) 里的「适合谁、不适合谁」；
* 想算清楚成本：见 [聚合 API 的成本怎么算](pricing-guide.html)；
* 网络层还没解决：见 [机场实测与线路选择](../../airport/index.html)。
