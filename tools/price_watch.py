#!/usr/bin/env python3
"""巡检各线路官方套餐接口，发现资费变动时输出可读的差异报告。

用法：
    python tools/price_watch.py --check           # 与快照比对，有变化则输出报告并以 10 退出
    python tools/price_watch.py --write-snapshot   # 把当前抓到的数据写成新的快照
    python tools/price_watch.py --report          # 输出当前完整资费清单

注意：魔戒的接口是 IP + 自签证书，因此这里显式跳过证书校验，只读取公开的价目数据。
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "price-snapshot.json"

SOURCES = {
    "mojie": {
        "label": "魔戒",
        "url": "https://74.82.196.10:8000/api/v1/guest/plan/fetch",
        "insecure": True,
    },
    "ktm": {
        "label": "KTM",
        "url": "https://url.ktm001.vip/api/v1/guest/plan/fetch",
        "insecure": False,
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


def fetch_json(url: str, insecure: bool) -> dict:
    ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "price-watch/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect() -> dict:
    result = {}
    for key, src in SOURCES.items():
        payload = fetch_json(src["url"], src["insecure"])
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
