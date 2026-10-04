#!/usr/bin/env python3
"""站点内容自检。任一项不过退出 10。

1. front matter 必填字段（title / description / kind 等）；
2. 站内相对链接可达（不含外链）；
3. sitemap.xml 与文件树一致（委托 tools/gen_sitemap.py --check）；
4. Liquid 块标签配对、布局 front matter 完整；
5. GitHub Pages（Jekyll 3.10）兼容性——CI 上不跑 Jekyll，这里静态挡一道，
   把「只有推送后才会暴露」的构建失败提前到自检阶段；
6. brands.yml 的品牌都带 order，否则栏目页卡片顺序会在本地/线上之间漂移；
7. robots.txt 的 Sitemap 地址与站点地址一致，且 Disallow 的目录确实不发布。

用法：
    python tools/check_content.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 同目录的生成脚本：站点地址（sitemap 前缀 / robots 的 Sitemap 行）只在它那里定义一次
sys.path.insert(0, str(ROOT / "tools"))
import gen_sitemap  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

EXCLUDE_DIRS = {
    ".git", ".github", "_site", "_data", "_includes", "_layouts", "assets",
    "node_modules", "vendor", "tools", "docs",
}
EXCLUDE_FILES = {"README.md", "CNAME", "robots.txt", "sitemap.xml"}

FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
FENCED_CODE = re.compile(r"```.*?```", re.S)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HTML_LINK = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""")
SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "data:", "//", "#")
# Liquid 输出、raw 块以及会包含模板片段的 JSON-LD，扫描前先剔除
LIQUID_OUTPUT = re.compile(r"\{\{.*?\}\}", re.S)
LIQUID_BLOCK = re.compile(r"\{%.*?%\}", re.S)
LIQUID_RAW = re.compile(r"\{%\s*raw\s*%\}.*?\{%\s*endraw\s*%\}", re.S)
SCRIPT_BLOCK = re.compile(r"<script\b.*?</script>", re.S | re.I)
LIQUID_COMMENT = re.compile(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", re.S)
LIQUID_TAG = re.compile(
    r"\{%-?\s*(if|unless|for|case|capture|raw|endif|endunless|endfor|endcase|endcapture|endraw)\b"
)
LIQUID_OPENERS = {"if", "unless", "for", "case", "capture", "raw"}

# GitHub Pages 线上是 Jekyll 3.10，见 check_jekyll3_compat()
EXP_FILTER = re.compile(
    r"""\b(where_exp|find_exp|group_by_exp)\s*:\s*(?:"[^"]*"|'[^']*')\s*,\s*("[^"]*"|'[^']*')"""
)
BOOLEAN_OP = re.compile(r"\s(?:and|or)\s|&&|\|\|")
JEKYLL4_ONLY_FILTER = re.compile(r"\|\s*(find|find_exp)\s*:")

# _data/brands.yml 的条目边界与 order 字段，见 check_brand_data()
BRAND_ITEM = re.compile(r"^- slug:[ \t]*(\S+)[ \t]*$", re.M)
BRAND_ORDER = re.compile(r"^[ \t]+order:[ \t]*\d+[ \t]*$", re.M)

# robots.txt 与 _config.yml，见 check_robots()
ROBOTS = ROOT / "robots.txt"
CONFIG = ROOT / "_config.yml"
ROBOTS_SITEMAP = re.compile(r"^[ \t]*sitemap[ \t]*:[ \t]*(\S+)[ \t]*$", re.M | re.I)
ROBOTS_DISALLOW = re.compile(r"^[ \t]*disallow[ \t]*:[ \t]*(\S*)[ \t]*$", re.M | re.I)
CONFIG_EXCLUDE_HEAD = re.compile(r"^exclude:[ \t]*$", re.M)
CONFIG_EXCLUDE_ITEM = re.compile(r"^[ \t]+-[ \t]*(\S+)[ \t]*$")


def site_files() -> list[Path]:
    found = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in (".md", ".html"):
            continue
        rel = path.relative_to(ROOT)
        if set(rel.parts) & EXCLUDE_DIRS:
            continue
        if rel.name in EXCLUDE_FILES:
            continue
        if rel.name.startswith((".", "_")):
            continue
        found.append(path)
    return found


def parse_front_matter(text: str) -> dict[str, str]:
    m = FRONT_MATTER.match(text)
    if not m:
        return {}
    fields: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if line.startswith((" ", "\t", "#", "-")):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def strip_code(text: str) -> str:
    """去掉代码块、脚本块与 Liquid 片段，只留下真正的正文链接。"""
    text = LIQUID_RAW.sub("", text)
    text = SCRIPT_BLOCK.sub("", text)
    text = FENCED_CODE.sub("", text)
    text = LIQUID_OUTPUT.sub("", text)
    text = LIQUID_BLOCK.sub("", text)
    return text


def check_liquid(files: list[Path]) -> list[str]:
    """模板与正文里的 Liquid 块标签配对检查。

    没有本地 Ruby/Jekyll 环境时，标签漏写 `endif` 这类错误本来只能在发布后才发现，
    这里先静态挡一道。
    """
    targets: list[Path] = []
    for sub in ("_layouts", "_includes"):
        directory = ROOT / sub
        if directory.exists():
            targets += sorted(directory.glob("*.html"))
    targets += files

    problems: list[str] = []
    for path in dict.fromkeys(targets):
        text = LIQUID_COMMENT.sub("", path.read_text(encoding="utf-8", errors="replace"))
        stack: list[str] = []
        for m in LIQUID_TAG.finditer(text):
            tag = m.group(1)
            if tag in LIQUID_OPENERS:
                stack.append(tag)
            elif not stack:
                problems.append("[liquid] %s 多余的 {%% %s %%}" % (path.relative_to(ROOT), tag))
            else:
                stack.pop()
        for tag in stack:
            problems.append("[liquid] %s 的 {%% %s %%} 未闭合" % (path.relative_to(ROOT), tag))
    return problems


def check_layouts() -> list[str]:
    """检查 _layouts/ 下的模板是否真的能当布局用。

    两个坑，静态检查就能挡住，但踩到时线上表现很隐蔽（页面能打开、只是没有样式）：
      1. 没有 front matter 的文件不会被 Jekyll 当成布局；
      2. front matter 里没有 layout: default 的布局不会套上全站骨架，
         渲染出来是一个裸 HTML 片段——没有 head、CSS、导航、面包屑、页脚。

    第 2 条是实测确认的：把 hub.html 的 `layout: default` 去掉后，
    栏目页立刻退化成 8142 字节的裸片段（对比正常时 14209 字节）。
    default.html 是最底层，不需要指向自己。
    """
    problems: list[str] = []
    directory = ROOT / "_layouts"
    if not directory.exists():
        return problems

    for path in sorted(directory.glob("*.html")):
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="replace")
        # 注意区分「没有 front matter」与「front matter 里只有注释」：
        # 前者 Jekyll 不认它是布局，后者是合法布局（default.html 就是这种）。
        has_front_matter = FRONT_MATTER.match(text) is not None
        if not has_front_matter:
            problems.append("[layout] %s 没有 front matter，Jekyll 不会把它当布局" % rel)
            continue
        if path.stem == "default":
            continue
        fields = parse_front_matter(text)
        if not fields.get("layout"):
            problems.append(
                "[layout] %s 没有声明 layout: default，页面会渲染成裸片段" % rel
            )
    return problems


def check_jekyll3_compat(files: list[Path]) -> list[str]:
    """挡住 Jekyll 4 能过、线上 Jekyll 3.10 会炸的写法。

    线上 GitHub Pages 用的是 jekyll 3.10.0（github-pages v232）。它的
    parse_condition 只认「单个比较」或「单个真值表达式」，解析完立刻要求
    end_of_string；写成 `where_exp: "p", "p.updated and p.listed != false"`
    会抛 `Liquid syntax error: Expected end_of_string but found id`，
    整个构建直接失败。Jekyll 4 支持这种复合条件，所以只要本机没钉住版本
    （见 Gemfile 里的 github-pages 232），本地构建就是好的、推上去才发现。

    本地钉住版本后这种错已经能复现，但这里仍然保留静态检查：
    CI 上只跑 python（见 .github/workflows/content-check.yml），
    不必装 Ruby/Jekyll 就能在 push 时挡住同类写法。

    具体查两件事：exp 类过滤器里出现 and/or（要求拆成多次过滤），
    以及 Jekyll 4 才有的 find / find_exp（3.10 没有，会报未定义过滤器）。
    """
    targets: list[Path] = []
    for sub in ("_layouts", "_includes"):
        directory = ROOT / sub
        if directory.exists():
            targets += sorted(directory.glob("*.html"))
    targets += files

    problems: list[str] = []
    for path in dict.fromkeys(targets):
        rel = path.relative_to(ROOT)
        text = LIQUID_COMMENT.sub("", path.read_text(encoding="utf-8", errors="replace"))

        for m in EXP_FILTER.finditer(text):
            expr = m.group(2)
            if BOOLEAN_OP.search(expr):
                problems.append(
                    "[jekyll3] %s 的 %s 里用了 and/or：%s"
                    "——线上 Jekyll 3.10 只支持单个条件，请拆成多次 %s"
                    % (rel, m.group(1), expr, m.group(1))
                )

        for m in JEKYLL4_ONLY_FILTER.finditer(text):
            problems.append(
                "[jekyll3] %s 用了 Jekyll 4 才有的 %s 过滤器，线上 Jekyll 3.10 会报未定义过滤器"
                % (rel, m.group(1))
            )
    return problems


def check_brand_data(text: str) -> list[str]:
    """brands.yml 里每个品牌都必须有 order。

    hub.html 用 `sort: "order"` 排品牌卡片。字段缺失时所有 key 都是 nil，
    Ruby 的 sort 不是稳定排序——构建照样成功，但卡片顺序会在本地和线上
    之间漂移（airport 栏目页就这么出现过 KTM 和魔戒对调）。
    这种错构建不会报，只能在这里查。
    """
    problems: list[str] = []
    items = list(BRAND_ITEM.finditer(text))
    for i, m in enumerate(items):
        chunk = text[m.end():items[i + 1].start() if i + 1 < len(items) else len(text)]
        if not BRAND_ORDER.search(chunk):
            problems.append(
                "[brands] _data/brands.yml 的 %s 缺 order 字段，"
                "栏目页品牌卡片顺序会不定" % m.group(1)
            )
    return problems


def check_sitemap() -> list[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_sitemap.py"), "--check"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        return [(result.stdout.strip() or result.stderr.strip()
                 or "sitemap.xml 与文件树不一致")]
    return []


def config_excludes() -> set[str]:
    """_config.yml 里 exclude 列表的首段路径集合。

    只认顶格的 `exclude:` 块，以及它下面缩进的 `- 条目`；遇到下一个顶格键就停。
    """
    if not CONFIG.exists():
        return set()
    text = CONFIG.read_text(encoding="utf-8", errors="replace")
    head = CONFIG_EXCLUDE_HEAD.search(text)
    if not head:
        return set()

    excluded: set[str] = set()
    for line in text[head.end():].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = CONFIG_EXCLUDE_ITEM.match(line)
        if not item:
            break  # 缩进列表结束，后面是别的配置项
        value = item.group(1).strip().strip('"').strip("'").strip("/")
        if value:
            excluded.add(value.split("/")[0])
    return excluded


def check_robots() -> list[str]:
    """robots.txt 与站点配置的一致性。

    两个会静默漂移的点，构建和 Pages 都不会报错：

      1. `Sitemap:` 是硬编码的绝对地址。换域名时如果只改了 _config.yml，
         这里会继续指向旧域名，而 sitemap 本身是好的，谁都不会发现；
         所以它必须等于 gen_sitemap 实际使用的站点地址。
      2. `Disallow:` 的目录如果没同时写进 _config.yml 的 exclude，
         那只是「请求搜索引擎别抓」，文件本身仍然发布在站点上公开可取——
         想藏东西却忘了排除，是这个文件最容易骗到人的地方。
    """
    problems: list[str] = []
    if not ROBOTS.exists():
        return ["[robots] 缺少 robots.txt"]

    text = ROBOTS.read_text(encoding="utf-8", errors="replace")

    expected = gen_sitemap.site_url() + "/sitemap.xml"
    found = ROBOTS_SITEMAP.findall(text)
    if not found:
        problems.append("[robots] 没有 Sitemap 行，搜索引擎不会主动来取 sitemap.xml")
    for url in found:
        if not url.startswith(("http://", "https://")):
            problems.append("[robots] Sitemap 必须写绝对地址，当前是 %s" % url)
        elif url != expected:
            problems.append(
                "[robots] Sitemap 指向 %s，与站点地址不一致，应为 %s" % (url, expected)
            )

    excluded = config_excludes()
    for path in ROBOTS_DISALLOW.findall(text):
        segment = path.strip().strip("/").split("/")[0]
        if not segment:
            continue  # `Disallow:` 留空表示不屏蔽任何路径，是合法写法
        if segment not in excluded:
            problems.append(
                "[robots] Disallow: %s 的 %s/ 不在 _config.yml 的 exclude 里，"
                "该目录会被发布到站点上（robots 只劝不挡）" % (path, segment)
            )
    return problems


def build_available(files: list[Path]) -> set[str]:
    """站点上真实可达的目标集合。

    Jekyll 会把 .md 发布成同名 .html，所以两种写法都得算可达；
    目录形式（foo/）在站点上等价于 foo/index.html。
    """
    available: set[str] = {"index.html"}  # 根目录首页
    for path in files:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        available.add(rel)
        if path.suffix == ".md":
            html = rel[: -len(".md")] + ".html"
            available.add(html)
            if rel.endswith("/index.md"):
                available.add(rel[: -len("index.md")])
    return available


def main() -> int:
    problems: list[str] = []
    files = site_files()
    available = build_available(files)

    for path in files:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        text = path.read_text(encoding="utf-8", errors="replace")
        fields = parse_front_matter(text)

        # ---- 1. front matter ----
        if path.suffix == ".md" and not fields:
            problems.append("[front matter] %s 缺少 front matter" % rel)
        else:
            kind = fields.get("kind", "")
            required = ["title", "description"]
            if kind:
                required += ["kind"]
            for key in required:
                if not fields.get(key):
                    problems.append("[front matter] %s 缺少 %s" % (rel, key))
            desc = fields.get("description", "")
            # layout: null 的页面自带 head 与 meta，不参与这里的规定
            if desc and fields.get("layout") != "null" and not (20 <= len(desc) <= 200):
                problems.append(
                    "[front matter] %s 的 description 长度为 %d，建议 20–200 字" % (rel, len(desc))
                )

        # ---- 2. 站内链接 ----
        body = strip_code(text)
        candidates = MD_LINK.findall(body) + HTML_LINK.findall(body)
        for raw in candidates:
            link = raw.strip()
            if not link or link.startswith(SKIP_SCHEMES):
                continue
            link = link.split("#", 1)[0].split("?", 1)[0]
            if not link:
                continue

            if link.startswith("/"):
                target = link.lstrip("/")
            else:
                target = str((Path(rel).parent / link)).replace("\\", "/")
            target = re.sub(r"/\./", "/", target)
            # 归一化 ../ 与 ./
            parts: list[str] = []
            for seg in target.split("/"):
                if seg in ("", "."):
                    continue
                if seg == "..":
                    if parts:
                        parts.pop()
                    continue
                parts.append(seg)
            target = "/".join(parts)

            if target not in available:
                problems.append("[dead link] %s -> %s" % (rel, raw))

    problems += ["[sitemap] " + line for line in check_sitemap()]
    problems += check_liquid(files)
    problems += check_layouts()
    problems += check_jekyll3_compat(files)
    brands_file = ROOT / "_data" / "brands.yml"
    if brands_file.exists():
        problems += check_brand_data(brands_file.read_text(encoding="utf-8", errors="replace"))
    try:
        problems += check_robots()
    except gen_sitemap.ConfigError as exc:
        problems.append("[robots] " + str(exc))

    if problems:
        print("内容自检未通过：")
        for line in problems:
            print(" - " + line)
        return 10

    print(
        "内容自检通过：%d 个页面，front matter、站内链接、模板标签、"
        "Jekyll 3.10 兼容性、品牌数据、sitemap、robots 均正常。" % len(files)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
