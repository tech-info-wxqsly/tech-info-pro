# 站点维护手册

本站是一个纯静态的 GitHub Pages 站点：没有服务器、没有数据库、也没有需要你运维的构建流程。所有内容都是仓库里的文本文件，提交之后几分钟内线上自动更新。

## 一、基础信息

| 项目 | 值 |
| --- | --- |
| 仓库 | https://github.com/tech-info-wxqsly/tech-info-pro |
| 正式域名 | https://tech-info.top/ |
| 备用地址 | https://tech-info-wxqsly.github.io/tech-info-pro/ （会 301 跳转到正式域名） |
| 托管方式 | GitHub Pages，`main` 分支根目录，legacy 构建 |
| 收录提交 | `.github/workflows/seo-ping.yml`，每天北京时间 07:00 自动运行 |

## 二、目录结构与用途

| 路径 | 用途 | 改动频率 |
| --- | --- | --- |
| `index.md` | 站点首页，用 `include_relative` 引入 `README.md`，本身不含正文 | 极低 |
| `README.md` | 正文唯一来源，同时是站点首页内容与仓库首页展示内容 | 高 |
| `guides/ios-proxy-setup.html` | iOS 上手教程，独立 HTML 页 | 低 |
| `404.html` | 访问不存在路径时的提示页 | 极低 |
| `_config.yml` | 站点标题、SEO 描述、站点地址 | 发布时改一次 |
| `CNAME` | 自定义域名声明文件，内容固定为域名本身 | 换域名时改 |
| `sitemap.xml` | 站点地图，供搜索引擎与收录工作流读取 | 加页面时改 |
| `.github/workflows/seo-ping.yml` | 定时提交收录的工作流 | 换域名时改 |
| `.github/workflows/price-watch.yml` | 每天巡检各线路官方资费，有变动就提醒 | 极低 |
| `.github/workflows/site-health.yml` | 每 30 分钟巡检证书与站点可用性 | 极低 |
| `tools/price_watch.py` | 资费抓取与比对的脚本 | 加线路时改 |
| `data/price-snapshot.json` | 上一次抓到的资费快照，用于比对 | 由工作流自动更新 |

## 三、日常改动怎么做

在 GitHub 网页上直接编辑最省事：打开仓库 → 点开对应文件 → 右上角铅笔图标 → 改完写一句提交说明 → 提交。也可以用命令行：

```powershell
cd D:\project\tech-info\jichang
git add .
git commit -m "update content"
git push
```

内容类改动集中在两处：

* **调整线路信息**：改 `README.md` 里的表格，名称、链接、资费、适用人群都在表格行里。站点首页会通过 `index.md` 自动引用同一份内容，不需要改两遍。
* **新增一条线路**：复制一整段 `## ✈️ ...` 及其表格，粘在后面改内容即可。暂时不想上线的线路，可以整段包在 `<!-- -->` 注释里，页面不会显示。

改完内容之后，把 `sitemap.xml` 里对应条目的 `lastmod` 改成当天日期——收录工作流只提交 `lastmod` 在最近 24 小时内的页面，不改日期就不会被提交。

## 四、域名与 DNS

域名 `tech-info.top` 注册在 Spaceship，NS 是 `launch1.spaceship.net` 与 `launch2.spaceship.net`，解析在 Spaceship 后台的 DNS 管理页维护。

需要存在的记录：

| 类型 | 主机 | 值 |
| --- | --- | --- |
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `tech-info-wxqsly.github.io` |

注意两点：注册商自带的停靠页 A 记录必须删掉，否则会与上面四条冲突；也不要拿"URL 转发"功能代替 A 记录，那个不参与 HTTPS 证书校验。

DNS 生效后，GitHub 会自动签发并续期 Let's Encrypt 证书。证书签发完成之前，仓库 `Settings → Pages` 里的 `Enforce HTTPS` 可能点不动，属正常现象。换域名时，需要同步修改 `_config.yml` 的 `url`、`sitemap.xml`、`guides/ios-proxy-setup.html` 的 `canonical`、`CNAME`、工作流里的 `sitemap-location`，以及 `INDEXNOW_KEY_LOCATION` 这个 Secret。

## 五、收录提交是怎么工作的

工作流调用 `bojieyang/indexnow-action`，把 `sitemap.xml` 里最近更新过的页面提交给 Bing（IndexNow 协议），让搜索引擎更快发现改动，不需要自己去后台提交。

* 仓库根目录的 `32ac67f880e38583d5136a1e85f6584f.txt` 是 key 文件，内容就是这串 key。
* 仓库 Secrets 里有两个值：`INDEXNOW_KEY` 与 `INDEXNOW_KEY_LOCATION`。
* 手动验证：仓库 Actions 页面选「搜索引擎收录提交」→ Run workflow，跑完在日志里看到 `URLs submitted successfully` 即为成功。

## 六、后台巡检任务

两个巡检都跑在 GitHub 的服务器上，不需要你开机，也不占用这台电脑：

| 任务 | 频率 | 做什么 | 什么时候打扰你 |
| --- | --- | --- | --- |
| 资费巡检 | 每天 09:00 | 抓取魔戒与 KTM 的官方套餐接口，和 `data/price-snapshot.json` 比对 | 只有出现调价、改名、上下架时才开 issue 提醒；无变化完全静默 |
| 站点与证书巡检 | 每 30 分钟 | 探测 `http://` 与 `https://tech-info.top/`，证书就绪后自动尝试开启 Enforce HTTPS | 证书就绪时提醒一次；站点连续不可访问时开 issue，恢复后自动关闭 |

提醒以仓库 issue 的形式发出，GitHub 会按你的通知设置推送邮件。资费巡检在提醒的同时会把快照更新掉，所以同一次调价只会提醒一次，不会天天刷。

想手动跑一次、或者想看当前完整资费清单：Actions → 资费巡检 → Run workflow，勾上 `force_report`，跑完在 issue 里就能看到各家当前的全部套餐与标价。

想在本机手动查：

```powershell
cd D:\project\tech-info\jichang
python tools\price_watch.py --report        # 打印当前完整资费
python tools\price_watch.py --check         # 只比对，有变动时退出码为 10
python tools\price_watch.py --write-snapshot # 把当前资费记为新的比对基准
```

## 七、本机开发环境备注

* 代码仓库位于 `D:\project\tech-info\jichang`。
* 本机装有 GitHub CLI，已登录 `tech-info-wxqsly`，因此推送不需要额外配置 Token。
* GitHub Pages 的 Jekyll 渲染由 GitHub 服务端完成，本机没有 Ruby 环境也能正常改内容；想本地预览可以直接用浏览器打开 HTML 文件。
* 如果哪天推送出现连接超时，多半是网络环境问题：确认代理软件在运行（FlClash 的本地端口默认是 `127.0.0.1:7890`），必要时给 git 单独配上代理：

```powershell
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
# 不需要时撤销
# git config --global --unset http.proxy
# git config --global --unset https.proxy
```

## 八、容易踩的坑

* 改完 `_config.yml` 需要重新触发一次 Pages 构建才会生效，最简单的办法是随便提交一个文件。
* 页面内的链接一律用相对路径。项目仓库或自定义域名切换时，相对路径不会失效，根路径写法容易出问题。
* GitHub Pages 在大陆的访问质量受线路影响，偶发打不开属于网络波动，可以用备用域名或备用解析缓解。
* 仓库是公开的，所有人都能看到里面的推广链接与文案。别把私密信息、后台地址、账号密码写进仓库。
* 站点每隔一段时间要体检：首页与教程页能否打开、推广链接是否还能跳转、资费是否已经变化。失效信息挂着比不写更伤信任。
