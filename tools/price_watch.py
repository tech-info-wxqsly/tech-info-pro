#!/usr/bin/env python3
"""巡检各线路官方套餐接口，发现资费变动时输出可读的差异报告。

用法：
    python tools/price_watch.py --check           # 与快照比对，有变化则输出报告并以 10 退出
    python tools/price_watch.py --write-snapshot   # 把当前抓到的数据写成新的快照
    python tools/price_watch.py --report          # 输出当前完整资费清单

注意：魔戒的接口是 IP + 自签证书，无法做域名校验，因此这里跳过证书链校验，
改为固定证书指纹（cert_sha256）。指纹对不上就中止，不会把数据写进快照——
抓取结果会被工作流自动提交回仓库，必须挡住中间人替换内容的可能。
对方换证书后指纹会变，报错信息里会给出实际指纹，照着更新常量即可。
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "price-snapshot.json"
UA = "price-watch/1.0 (+https://tech-info.top/)"
# 单套餐价格上限（元），用于挡住明显异常的数据
MAX_PRICE_YUAN = 100000

# Windows 终端默认 GBK，打印 ¥ 之类的字符会直接报错，统一切到 UTF-8
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SOURCES = {
    "mojie": {
        "label": "魔戒",
        "url": "https://74.82.196.10:8000/api/v1/guest/plan/fetch",
        "insecure": True,
        # 自签证书的 SHA-256 指纹，2026-10-04 固定；对方换证书后需同步更新
        "cert_sha256": "c4bb6b977adb0af52bce96db9b5cf4c74bcc72cd05de3aee2bc3622ac83f35ff",
    },
    "ktm": {
        "label": "KTM",
        "url": "https://url.ktm001.vip/api/v1/guest/plan/fetch",
        "insecure": False,
        "cert_sha256": "",
    },
}

# 官方接口里每个周期字段对应的中文名，顺序即展示顺序
PRICE_FIELDS = [
    ("onetime_price", "一次性"),
    ("month_price", "月付"),
    ("quarter_price", "季付"),
    ("half_year_price", "半年付"),
    ("year_price", "年付"),
    ("two_year_price", "两年付"),
    ("three_year_price", "三年付"),
]


def fetch_json(url: str, insecure: bool, cert_sha256: str = "") -> dict:
    """抓取官方接口；insecure 时必须校验固定证书指纹。"""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise SystemExit("只允许抓取 https 地址，当前配置有问题：" + url)

    ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()
    conn = http.client.HTTPSConnection(
        parts.hostname, parts.port or 443, timeout=30, context=ctx
    )
    try:
        conn.connect()
        if insecure:
            der = (conn.sock.getpeercert(binary_form=True) if conn.sock else None) or b""
            actual = hashlib.sha256(der).hexdigest()
            if not cert_sha256 or actual != cert_sha256:
                raise SystemExit(
                    "证书指纹不匹配，已中止（对方可能换了证书，也可能有中间人）：\n"
                    "  期望 %s\n  实际 %s\n"
                    "确认无误后把 SOURCES 里的 cert_sha256 更新为实际值。"
                    % (cert_sha256 or "(未配置)", actual)
                )
        conn.request("GET", parts.path or "/", headers={"User-Agent": UA, "Accept": "application/json"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", "replace")
        if resp.status != 200:
            raise SystemExit("接口返回 HTTP %s：%s" % (resp.status, url))
        return json.loads(body)
    finally:
        conn.close()


def validate(data: dict) -> list[str]:
    """写入快照前的完整性校验：数据来自外部，任何一条可疑都拒绝落盘。"""
    problems: list[str] = []
    for key, src in data.items():
        label = src.get("label", key)
        plans = src.get("plans") or {}
        if not plans:
            problems.append("[%s] 没有解析到任何套餐，接口结构可能已变" % label)
            continue
        for pid, plan in plans.items():
            name = plan.get("name") or pid
            prices = plan.get("prices") or {}
            for cycle, price in prices.items():
                if not isinstance(price, (int, float)) or isinstance(price, bool):
                    problems.append("[%s] 套餐「%s」的 %s 价格不是数字：%r" % (label, name, cycle, price))
                elif price <= 0 or price > MAX_PRICE_YUAN:
                    problems.append("[%s] 套餐「%s」的 %s 价格超出合理范围：%r" % (label, name, cycle, price))
            gb = plan.get("gb")
            gb_ok = isinstance(gb, (int, float)) and not isinstance(gb, bool) and gb > 0
            if gb is not None and not gb_ok:
                problems.append("[%s] 套餐「%s」的流量数值异常：%r" % (label, name, gb))
    return problems


def collect() -> dict:
    result = {}
    for key, src in SOURCES.items():
        payload = fetch_json(src["url"], src["insecure"], src.get("cert_sha256", ""))
        plans = payload.get("data") or []
        entries = {}
        for plan in plans:
            if not plan.get("show", 1):
                continue
            prices = {}
            for field, label in PRICE_FIELDS:
                value = plan.get(field)
                if value:
                    prices[label] = round(value / 100, 2)
            entries[str(plan["id"])] = {
                "name": (plan.get("name") or "").strip(),
                "gb": plan.get("transfer_enable"),
                "prices": prices,
            }
        result[key] = {"label": src["label"], "plans": entries}
    return result


def load_snapshot() -> dict:
    if not SNAPSHOT.exists():
        return {}
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def write_snapshot(data: dict) -> None:
    problems = validate(data)
    if problems:
        raise SystemExit(
            "数据校验未通过，拒绝写入快照：\n" + "\n".join(" - " + p for p in problems)
        )
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": data,
    }
    SNAPSHOT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def diff(old: dict, new: dict) -> list:
    lines = []
    old_sources = old.get("sources", {})
    for key, src in new.items():
        label = src["label"]
        old_plans = old_sources.get(key, {}).get("plans", {})
        new_plans = src["plans"]

        for pid, plan in new_plans.items():
            if pid not in old_plans:
                lines.append("[%s] 新增套餐：%s（%sG）" % (label, plan["name"], plan["gb"]))
                continue
            old_plan = old_plans[pid]
            if old_plan.get("name") != plan.get("name"):
                lines.append(
                    "[%s] 套餐改名：%s → %s" % (label, old_plan.get("name"), plan["name"])
                )
            if old_plan.get("gb") != plan.get("gb"):
                lines.append(
                    "[%s] %s 流量变化：%sG → %sG"
                    % (label, plan["name"], old_plan.get("gb"), plan["gb"])
                )
            old_prices = old_plan.get("prices", {})
            for cycle, price in plan["prices"].items():
                old_price = old_prices.get(cycle)
                if old_price is None:
                    lines.append("[%s] %s 新增 %s：¥%s" % (label, plan["name"], cycle, price))
                elif abs(float(old_price) - float(price)) > 1e-6:
                    lines.append(
                        "[%s] %s %s：¥%s → ¥%s" % (label, plan["name"], cycle, old_price, price)
                    )
            for cycle, old_price in old_prices.items():
                if cycle not in plan["prices"]:
                    lines.append(
                        "[%s] %s 下架 %s（原 ¥%s）" % (label, plan["name"], cycle, old_price)
                    )

        for pid, plan in old_plans.items():
            if pid not in new_plans:
                lines.append(
                    "[%s] 移除套餐：%s（%sG）" % (label, plan.get("name"), plan.get("gb"))
                )
    return lines


def report(data: dict) -> str:
    lines = ["当前资费清单（抓取时间 %s）" % datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")]
    for src in data.values():
        lines.append("")
        lines.append("【%s】" % src["label"])
        plans = sorted(
            src["plans"].items(),
            key=lambda kv: (kv[1]["gb"] is None, kv[1]["gb"] or 0),
        )
        for pid, plan in plans:
            prices = "　".join("%s ¥%s" % (k, v) for k, v in plan["prices"].items())
            lines.append("  %s（%sG）：%s" % (plan["name"], plan["gb"], prices or "无标价"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write-snapshot", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    current = collect()

    problems = validate(current)
    if problems:
        print("抓取结果未通过校验，已中止（不会更新快照）：")
        for line in problems:
            print(" - " + line)
        return 2

    if args.report:
        print(report(current))
        return 0

    if args.write_snapshot:
        write_snapshot(current)
        print("快照已更新：" + str(SNAPSHOT.relative_to(ROOT)))
        return 0

    changes = diff(load_snapshot(), current)
    if not changes:
        print("未发现资费变动。")
        return 0

    print("检测到资费变动：")
    for line in changes:
        print(" - " + line)
    return 10


if __name__ == "__main__":
    sys.exit(main())
