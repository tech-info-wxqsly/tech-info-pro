#!/usr/bin/env python3
"""检查站点正文里引用的外部推广链接是否还能正常访问。

链接来源是 README.md（站点首页与仓库首页共用同一份内容源），
因此只要页面上挂了新链接，这里就会自动纳入检查，不需要单独维护清单。

用法：
    python tools/link_watch.py            # 检查并输出报告，全部正常退出 0，有异常退出 10
    python tools/link_watch.py --summary-file out.txt   # 额外写出适合短信推送的短摘要

判定口径：
    2xx / 3xx        -> 正常
    401 / 403 / 429  -> 警告（多为机房 IP 被防护拦截，不代表链接失效）
    其它 4xx / 5xx   -> 失效
    连接失败 / 证书错误 -> 失效
"""

from __future__ import annotations

import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import argparse
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [ROOT / "README.md"]
SKIP_HOSTS = {"tech-info.top", "www.tech-info.top"}
UA = "Mozilla/5.0 (compatible; link-watch/1.0; +https://tech-info.top/)"
WARN_STATUS = {401, 403, 429}
RETRIES = 2


def extract_links() -> list[str]:
    found: list[str] = []
    md_link = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
    bare_link = re.compile(r"<(https?://[^>\s]+)>")
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for url in md_link.findall(text) + bare_link.findall(text):
            host = (urlparse(url).hostname or "").lower()
            if not host or host in SKIP_HOSTS:
                continue
            if url not in found:
                found.append(url)
    return found


def probe(url: str) -> tuple[str, str]:
    """返回 (状态, 说明)，状态取 ok / warn / fail。"""
    host = (urlparse(url).hostname or "").lower()
    # 部分机场面板用 IP + 自签证书，这里对 IP 直连的地址放行证书校验
    ctx = ssl._create_unverified_context() if re.match(r"^[\d.]+$", host) else ssl.create_default_context()
    last = ""
    for attempt in range(RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
                code = resp.getcode()
                final = resp.geturl()
                if code in WARN_STATUS:
                    return "warn", "HTTP %s（可能被防护拦截，不代表失效）" % code
                if 200 <= code < 400:
                    extra = "" if final == url else "（跳转到 %s）" % final
                    return "ok", "HTTP %s%s" % (code, extra)
                return "fail", "HTTP %s" % code
        except urllib.error.HTTPError as exc:
            code = exc.code
            if code in WARN_STATUS:
                return "warn", "HTTP %s（可能被防护拦截）" % code
            return "fail", "HTTP %s" % code
        except Exception as exc:  # 连接失败、超时、证书错误等
            last = "%s: %s" % (type(exc).__name__, exc)
        if attempt < RETRIES:
            time.sleep(5)
    return "fail", "无法访问（%s）" % last


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-file", default="")
    args = parser.parse_args()

    links = extract_links()
    if not links:
        print("未在正文中找到需要检查的外部链接。")
        return 0

    print("开始检查正文中的 %d 个外部链接：" % len(links))
    print("")
    failures: list[str] = []
    warnings: list[str] = []
    for url in links:
        status, detail = probe(url)
        mark = {"ok": "正常", "warn": "警告", "fail": "失效"}[status]
        print("[%s] %s -> %s" % (mark, url, detail))
        if status == "fail":
            failures.append("%s（%s）" % (url, detail))
        elif status == "warn":
            warnings.append("%s（%s）" % (url, detail))

    print("")
    if warnings:
        print("需要注意（未判定为失效）：")
        for item in warnings:
            print(" - " + item)
    if failures:
        print("确认失效的链接：")
        for item in failures:
            print(" - " + item)
        if args.summary_file:
            first = failures[0].split("（")[0]
            summary = "站点链接告警：共 %d 个推广链接异常，首个是 %s。详情见仓库 issue。" % (
                len(failures),
                first,
            )
            Path(args.summary_file).write_text(summary, encoding="utf-8")
        return 10

    print("结论：所有链接均可正常访问。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
