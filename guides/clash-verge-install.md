---
layout: default
title: "Clash Verge 下载与安装教程：Windows 与 macOS 分别怎么装（2026）"
description: "Clash Verge Rev 去哪里下载、Windows 与 macOS 该选哪个安装包、Apple 芯片和 Intel 怎么区分、首次打开被系统拦截怎么处理，以及安装完成后需要先做哪些初始设置。"
---

# Clash Verge 下载与安装：Windows 与 macOS 分别怎么装

一句话结论：**只从官方仓库的 Release 页面下载，Windows 选 `x64` 安装包，macOS 必须先分清 Apple 芯片和 Intel 芯片。** 装完之后不要急着导入订阅，先把初始设置过一遍。

## 一、去哪里下载

Clash Verge 目前维护得最活跃的版本叫 **Clash Verge Rev**，代码和安装包都发布在 GitHub 的 Releases 页面。判断一个下载渠道是否可靠，看三点：

1. 页面上有完整的版本号、更新时间、更新说明；
2. 每个安装包都标注了平台与架构；
3. 下载链接指向官方仓库的 releases 目录。

**不要用来路不明的"绿色版""加速版"客户端。** 这类软件掌握你的全部流量走向和订阅地址，一旦被植入后门，等于把账号和隐私一起交出去。

## 二、Windows 怎么装

| 文件类型 | 适合场景 |
| --- | --- |
| `*_x64-setup.exe` | 常规安装，推荐大多数人 |
| `*_x64_fixed_webview2-setup.exe` | 系统缺少 WebView2 运行环境时使用 |
| 便携版（zip） | 不想写注册表、放在 U 盘里随身用 |

安装过程中的两个提示不用紧张：

* **Windows SmartScreen 拦截**：点"更多信息 → 仍要运行"。未签名或新发布的程序常会遇到，前提是你从官方页面下载。
* **请求安装服务组件**：只有开启 TUN 模式才需要，用来创建虚拟网卡。暂时用不到可以先跳过，之后开启时再装。

## 三、macOS 怎么装

先确认机型架构：左上角  → 关于本机，看芯片一栏。**Apple 芯片（M1/M2/M3/M4）选 `aarch64`，Intel 芯片选 `x64`**，装错会打不开或运行异常。

步骤：

1. 下载 `.dmg`，打开后把图标拖进「应用程序」；
2. 第一次打开若提示"无法验证开发者"，到「系统设置 → 隐私与安全性」，在下方找到被拦截的提示并选择"仍要打开"；
3. 开启 TUN 模式时会请求授权网络扩展，授权后一般需要重启一次客户端。

## 四、安装完成后的初始设置

装好之后先花两分钟做这几件事，能避免后面一大堆排查：

| 设置项 | 建议 |
| --- | --- |
| 语言 | 切换成中文界面，减少误操作 |
| 混合端口 | 记下端口号（默认 7890），手机共用网络、排查冲突时都要用 |
| 系统代理 | 先用系统代理，遇到不生效的程序再考虑 TUN |
| 开机自启 | 想让网络一直可用就打开，否则保持关闭更省资源 |
| 订阅自动更新 | 导入订阅后设置为 24 小时左右 |

## 五、装不上或打不开怎么办

**双击没反应 / 闪退**：先确认安装包架构与系统匹配，再看系统版本是否过低。Windows 上部分精简版系统缺少运行库，换官方安装包或补装运行库即可。

**安装被安全软件拦截**：把客户端目录加入白名单，而不是直接关闭安全软件。装完再恢复防护。

**提示端口被占用**：7890 被其它程序占用时客户端启动会失败，到设置里换一个端口，例如 7891。

**想彻底卸载**：Windows 在卸载程序里正常卸载，并删除用户目录下的配置文件夹；macOS 拖出应用程序后，顺手删除 `~/Library/Application Support` 下的配置目录，否则重装会沿用旧配置。

装好之后下一步是导入订阅，具体有三种导入方式和对应的排查顺序，见 [Clash Verge 订阅导入与分流教程](clash-verge-subscribe.html)。

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Clash Verge 去哪里下载才安全？",
      "acceptedAnswer": { "@type": "Answer", "text": "只从官方 GitHub 仓库的 Releases 页面下载，页面上应有完整版本号、更新时间和标注架构的安装包；不要使用来源不明的绿色版或加速版，这类客户端可以读取你的全部流量与订阅地址。" }
    },
    {
      "@type": "Question",
      "name": "macOS 上应该选哪个安装包？",
      "acceptedAnswer": { "@type": "Answer", "text": "先确认芯片类型：Apple 芯片（M 系列）选择 aarch64 版本，Intel 芯片选择 x64 版本。装错架构会出现无法打开或运行异常，与客户端本身无关。" }
    },
    {
      "@type": "Question",
      "name": "安装时提示安装服务组件是什么？",
      "acceptedAnswer": { "@type": "Answer", "text": "那是开启 TUN 模式所需的服务组件，用来创建虚拟网卡接管全局流量；如果暂时只用系统代理，可以跳过安装，之后需要开启 TUN 时再安装即可。" }
    }
  ]
}
</script>

## 相关阅读

* [Clash Verge 订阅导入与分流教程](clash-verge-subscribe.html)
* [电脑端科学上网客户端对比：Windows 与 macOS](desktop-client-windows-mac.html)
* [机场订阅链接怎么获取与备份](subscription-link-guide.html)
* [返回首页：线路资费与实测记录](../index.html)
