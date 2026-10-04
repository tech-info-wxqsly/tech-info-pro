#!/usr/bin/env python3
"""站点内容自检。三项检查，任一不过退出 10。

1. front matter 必填字段（title / description / kind 等）；
2. 站内相对链接可达（不含外链）；
3. sitemap.xml 与文件树一致（委托 tools/gen_sitemap.py --check）。

用法：
    python tools/check_content.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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


def check_sitemap() -> list[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "gen_sitemap.py"), "--check"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        return [result.stdout.strip() or "sitemap.xml 与文件树不一致"]
    return []


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

    if problems:
        print("内容自检未通过：")
        for line in problems:
            print(" - " + line)
        return 10

    print(
        "内容自检通过：%d 个页面，front matter、站内链接、模板标签、sitemap 均正常。" % len(files)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
