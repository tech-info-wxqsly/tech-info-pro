# tech-info.top · 站点源码

长期自用的两条线实测记录，发布在 [tech-info.top](https://tech-info.top)：

* **机场实测**（`/airport/`）——线路资费、晚高峰表现与避坑记录；
* **AI API**（`/ai-api/`）——大模型接口接入、客户端配置与成本核算；
* **公共教程**（`/guides/`）——平台无关的客户端、协议与排障教程，被上面两条线共用。

> 首页是**门户页**，只做分流；具体价格写在品牌页里。这份 README 是仓库说明，
> 不再是站点首页的内容源（历史上首页用 `include_relative README.md` 实现，
> 导致「改首页 = 改仓库门面」，现已解开）。

## 目录结构

```
_config.yml              Jekyll 配置；front matter 默认值集中在这里
_data/
  verticals.yml          业务线（栏目）定义
  brands.yml             品牌单一事实来源：推广链接、价格、卖点、适合谁
  nav.yml                顶部导航与首页「按场景找答案」
  faq-airport.yml        机场栏目 FAQ（正文与结构化数据同源）
_layouts/
  default.html           全站骨架：导航 + 面包屑 + 页脚
  index.html             门户首页
  hub.html               L1 栏目页
  brand.html             L2 品牌落地页
  brand-article.html     L3 品牌文章（末尾自动带出同品牌其它文章）
  article.html           公共教程
_includes/               导航、面包屑、品牌卡、推广区块、FAQ、相关阅读
airport/                 机场栏目与品牌页
ai-api/                  AI API 栏目与品牌页
guides/                  公共教程（URL 保持不变，已收录）
tools/                   巡检与自检脚本（不随站点发布）
```

站点用 GitHub Pages 默认构建（仓库里没有 `Gemfile`，不依赖任何插件），
所以新增页面不需要改动构建配置。

## 加内容怎么加

### 加一个品牌

1. 在 `_data/brands.yml` 加一段（`slug` / `vertical` / `aff` / `price_rows` / …）；
2. 建品牌页 `<vertical>/<slug>/index.md`，`layout` 与 `brand` 由 `_config.yml`
   的 front matter 默认值自动套上，正文只写实测内容；
3. 需要的话在 `_data/verticals.yml` 里加新栏目。

首页卡片、栏目页品牌列表、顶部导航、面包屑、sitemap 都会自动跟上，
**不需要改任何模板**。

### 加一篇文章

在对应品牌目录下新建 `.md`，front matter 写 `title` / `description` /
`nav_weight` / `updated` 即可——`layout`、`vertical`、`brand` 由
`_config.yml` 的默认值提供。写完运行：

```bash
python tools/gen_sitemap.py --write   # 更新 sitemap（否则新页面不会被 IndexNow 提交）
python tools/check_content.py         # 自检：front matter、站内链接、sitemap 一致性
```

### 改价格

只改 `_data/brands.yml` 里的 `price_rows` 与 `updated`。
所有引用价格的位置都从这里取数据。

## 工具脚本

以下脚本均无第三方依赖（只用标准库），与仓库现有的零依赖风格一致：

| 脚本 | 作用 | 退出码 |
| --- | --- | --- |
| `tools/gen_sitemap.py` | 从文件树生成 `sitemap.xml` | `--check` 不一致时 10 |
| `tools/check_content.py` | front matter / 站内链接 / sitemap 三项自检 | 不过时 10 |
| `tools/link_watch.py` | 巡检外部推广链接（含 `_data/brands.yml`） | 有失效时 10 |
| `tools/price_watch.py` | 抓取各家官方套餐接口，与快照比对资费变动 | 有变动时 10 |
| `tools/notify.py` | 多通道提醒（企业微信 / 钉钉 / 飞书 / Telegram / ntfy / 短信） | — |

## 自动化

| 工作流 | 触发 | 做什么 |
| --- | --- | --- |
| `content-check.yml` | push / PR | 内容自检，挡住死链、漏字段、sitemap 漂移 |
| `link-watch.yml` | 每周一 | 推广链接有效性 + 内容自检，失效时开 issue 并推送提醒 |
| `price-watch.yml` | 每天 | 资费变动检测，有变化就更新快照并提醒 |
| `seo-ping.yml` | 每天 | 按 sitemap 的 `lastmod` 用 IndexNow 提交有更新的页面 |
| `site-health.yml` | 每 30 分钟 | HTTP/HTTPS 与证书巡检，恢复后自动关闭提醒 issue |

> `seo-ping.yml` 依赖 sitemap 的 `lastmod`，只提交最近 1 天内有更新的条目。
> 这就是新增文章必须跑 `gen_sitemap.py --write` 的原因。

## 本地预览

```bash
# 需要 Ruby 与 jekyll（GitHub Pages 官方用 github-pages gem）
gem install github-pages
jekyll serve
```

Windows 上如果没装 Ruby，也可以只跑上面几个 Python 脚本做内容自检，
发布交给 GitHub Pages 构建。

## 内容口径

* 标价整理自各家官方套餐页，核对日期写在品牌页里，**以官网为准**；
* 推广入口统一走 `_includes/aff-cta.html`，只在这一处维护披露语与
  `rel="sponsored nofollow"`；
* 不写「哪家最好」这类结论，写「适合谁、不适合谁」。
