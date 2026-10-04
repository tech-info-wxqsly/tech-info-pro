#!/usr/bin/env python3
"""从站点文件树生成 sitemap.xml。

为什么需要这个脚本：sitemap 原来是手写的静态文件，而
.github/workflows/seo-ping.yml 用 IndexNow 按 sitemap 的 lastmod 提交页面，
只提交「lastmod 在 1 天内」的条目。手写意味着新增文章如果忘了加条目，
就永远不会被主动提交给搜索引擎。这里改成从文件树生成，并在 CI 里校验
「生成结果与仓库里的文件一致」，让它不可能再漂移。

用法：
    python tools/gen_sitemap.py            # 打印当前应有的 sitemap 内容
    python tools/gen_sitemap.py --write    # 写入 sitemap.xml
    python tools/gen_sitemap.py --check    # 与仓库里的 sitemap.xml 比对，不一致退出 10
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = ROOT / "sitemap.xml"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# 不参与发布的目录（与 _config.yml 的 exclude 保持一致）
EXCLUDE_DIRS = {
    ".git", ".github", "_site", "_data", "_includes", "_layouts", "assets",
    "node_modules", "vendor", "tools", "docs",
}
# 不参与发布的根文件
EXCLUDE_FILES = {"README.md", "CNAME", "robots.txt", "sitemap.xml", "404.html"}

FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)

# 首页 > 栏目页 > 品牌页 > 文章
PRIORITY = [
    ("index.md", "1.0", "weekly"),
    ("index.html", "1.0", "weekly"),
]


def parse_front_matter(text: str) -> dict[str, str]:
    """只取需要的那几个顶层字段，不引入 YAML 依赖。"""
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


def git_date(path: Path) -> str:
    """取文件最后一次提交日期；未提交或不适用时退回文件修改时间。"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path.relative_to(ROOT))],
            cwd=str(ROOT), capture_output=True, text=True, timeout=20, check=False,
            encoding="utf-8", errors="replace",
        )
        value = out.stdout.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
    except Exception:  # 没有 git、超时等，都不应该让生成失败
        pass
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def collect() -> list[tuple[str, str, str, str]]:
    """返回 [(url_path, lastmod, changefreq, priority)]。"""
    entries: list[tuple[str, str, str, str]] = []

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in (".md", ".html"):
            continue
        rel = path.relative_to(ROOT)
        parts = rel.parts
        if set(parts) & EXCLUDE_DIRS:
            continue
        if rel.name in EXCLUDE_FILES:
            continue
        if rel.name.startswith(".") or rel.name.startswith("_"):
            continue

        fields = parse_front_matter(path.read_text(encoding="utf-8", errors="replace"))
        lastmod = fields.get("updated") or git_date(path)

        if rel.name in ("index.md", "index.html") and len(parts) == 1:
            url = ""
            priority, changefreq = "1.0", "weekly"
        else:
            url = str(rel.with_suffix(".html")).replace("\\", "/")
            if rel.name.startswith("index."):
                # 栏目页（一层）> 品牌页（两层）
                if len(parts) == 2:
                    priority, changefreq = "0.9", "weekly"
                else:
                    priority, changefreq = "0.8", "monthly"
            else:
                # 公共教程与品牌文章
                priority, changefreq = ("0.6", "monthly") if len(parts) >= 4 else ("0.7", "monthly")

        entries.append((url, lastmod, changefreq, priority))

    # 首页排最前，其余按 URL 排序，保证输出稳定（CI 比对才有意义）
    entries.sort(key=lambda e: (e[0] != "", e[0]))
    return entries


def render(entries: list[tuple[str, str, str, str]]) -> str:
    base = "https://tech-info.top"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!-- 本文件由 tools/gen_sitemap.py 生成，请勿手工编辑。 -->",
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url, lastmod, changefreq, priority in entries:
        loc = base + "/" + url if url else base + "/"
        lines += [
            "  <url>",
            "    <loc>%s</loc>" % loc,
            "    <lastmod>%s</lastmod>" % lastmod,
            "    <changefreq>%s</changefreq>" % changefreq,
            "    <priority>%s</priority>" % priority,
            "  </url>",
        ]
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    content = render(collect())

    if args.write:
        SITEMAP.write_text(content, encoding="utf-8")
        print("已写入 " + str(SITEMAP.relative_to(ROOT)) + "（%d 条）" % content.count("<loc>"))
        return 0

    if args.check:
        current = SITEMAP.read_text(encoding="utf-8") if SITEMAP.exists() else ""
        if current.strip() != content.strip():
            print("sitemap.xml 与当前文件树不一致，请运行：python tools/gen_sitemap.py --write")
            print("---- 应该是 ----")
            print(content)
            return 10
        print("sitemap 与文件树一致（%d 条）。" % content.count("<loc>"))
        return 0

    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
