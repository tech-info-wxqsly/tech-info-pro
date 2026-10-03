#!/usr/bin/env python3
"""把告警文本推送到手机。按"先配置先用"的顺序自动选择渠道。

用法：
    python tools/notify.py --text "要发送的内容"
    python tools/notify.py --text-file link-summary.txt

支持的渠道（按下面的顺序尝试，找到第一个配置完整的就发送）：
    1. 短信宝        SMSBAO_USER + SMSBAO_PASS + ALERT_PHONE     真实短信
    2. 企业微信机器人  WECHAT_WORK_WEBHOOK                        机器人 Webhook
    3. 钉钉机器人      DINGTALK_WEBHOOK（+ 可选 DINGTALK_SECRET）
    4. 飞书机器人      FEISHU_WEBHOOK
    5. Telegram      TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
    6. ntfy          NTFY_TOPIC（+ 可选 NTFY_SERVER、NTFY_TOKEN）
    7. 通用 Webhook   SMS_WEBHOOK_URL                             POST {title, body}

所有凭证都从环境变量读取，工作流里通过仓库 Secrets 注入。

安全约定：仓库是公开的，Actions 日志任何人都能看，因此出错时只输出渠道名
与 HTTP 状态码，绝不把请求 URL、请求参数或响应体写进日志——这些位置会带上
webhook key、bot token 与短信接口的密码哈希。新增渠道时请沿用同样的写法。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TITLE = "站点链接告警"
UA = "notify/1.0 (+https://tech-info.top/)"
CTX = ssl.create_default_context()
# 公共 ntfy.sh 上 topic 名就是唯一的凭证，太短等于把告警内容公开
NTFY_PUBLIC_MIN_TOPIC = 20

# Windows 终端默认 GBK，中文日志会报错，统一切到 UTF-8
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def safe_reason(exc: BaseException) -> str:
    """把异常压成不含 URL 与请求参数的短描述，供日志输出。"""
    if isinstance(exc, urllib.error.HTTPError):
        return "HTTP %s" % exc.code
    if isinstance(exc, urllib.error.URLError):
        return "URLError（网络不可达或被拦截）"
    return type(exc).__name__


def post(url: str, payload: dict, headers: dict | None = None) -> tuple[bool, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "User-Agent": UA}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as resp:
            body = resp.read().decode("utf-8", "replace")
            return 200 <= resp.getcode() < 300, body[:400]
    except Exception as exc:
        return False, safe_reason(exc)


def get(url: str) -> tuple[bool, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as resp:
            return 200 <= resp.getcode() < 300, resp.read().decode("utf-8", "replace")[:400]
    except Exception as exc:
        return False, safe_reason(exc)


def send_smsbao(text: str) -> tuple[bool, str]:
    user = os.environ["SMSBAO_USER"]
    password = hashlib.md5(os.environ["SMSBAO_PASS"].encode("utf-8")).hexdigest()
    phone = os.environ["ALERT_PHONE"]
    query = urllib.parse.urlencode({"u": user, "p": password, "m": phone, "c": text})
    ok, body = get("https://api.smsbao.com/sms?" + query)
    # 短信宝返回 "0" 表示提交成功，其它为错误码
    return (ok and body.strip() == "0"), body.strip()


def send_wechat_work(text: str) -> tuple[bool, str]:
    url = os.environ["WECHAT_WORK_WEBHOOK"]
    ok, body = post(url, {"msgtype": "text", "text": {"content": text}})
    if not ok:
        return ok, body
    try:
        data = json.loads(body)
    except Exception:
        return True, body
    # 企业微信即使出错也返回 HTTP 200，必须看 errcode
    return data.get("errcode") == 0, body


def send_dingtalk(text: str) -> tuple[bool, str]:
    url = os.environ["DINGTALK_WEBHOOK"]
    secret = os.environ.get("DINGTALK_SECRET", "")
    if secret:
        stamp = str(round(time.time() * 1000))
        string_to_sign = "%s\n%s" % (stamp, secret)
        digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(digest).decode("utf-8"))
        joiner = "&" if "?" in url else "?"
        url = "%s%stimestamp=%s&sign=%s" % (url, joiner, stamp, sign)
    ok, body = post(url, {"msgtype": "text", "text": {"content": text}})
    if not ok:
        return ok, body
    try:
        data = json.loads(body)
    except Exception:
        return True, body
    # 钉钉同样用 errcode 表示结果
    return data.get("errcode") == 0, body


def send_feishu(text: str) -> tuple[bool, str]:
    ok, body = post(os.environ["FEISHU_WEBHOOK"], {"msg_type": "text", "content": {"text": text}})
    if not ok:
        return ok, body
    try:
        data = json.loads(body)
    except Exception:
        return True, body
    code = data.get("code", data.get("StatusCode", 0))
    return code in (0, None), body


def send_telegram(text: str) -> tuple[bool, str]:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    ok, body = post(url, {"chat_id": chat, "text": text, "disable_web_page_preview": True})
    if not ok:
        return ok, body
    try:
        return bool(json.loads(body).get("ok")), body
    except Exception:
        return True, body


def send_ntfy(text: str) -> tuple[bool, str]:
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    topic = os.environ["NTFY_TOPIC"]
    headers = {"Title": TITLE.encode("utf-8").decode("latin-1"), "User-Agent": UA}
    token = os.environ.get("NTFY_TOKEN", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        "%s/%s" % (server, topic),
        data=text.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25, context=CTX) as resp:
            return 200 <= resp.getcode() < 300, resp.read().decode("utf-8", "replace")[:200]
    except Exception as exc:
        return False, safe_reason(exc)


def ntfy_topic_too_weak() -> bool:
    """公共 ntfy.sh 上 topic 名就是凭证，短串会被猜到并读取全部告警。"""
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    if server != "https://ntfy.sh":
        return False
    return len(os.environ.get("NTFY_TOPIC", "")) < NTFY_PUBLIC_MIN_TOPIC


def send_generic_webhook(text: str) -> tuple[bool, str]:
    return post(os.environ["SMS_WEBHOOK_URL"], {"title": TITLE, "body": text})


# (渠道名, 必需的环境变量, 发送函数)
CHANNELS = [
    ("短信宝", ["SMSBAO_USER", "SMSBAO_PASS", "ALERT_PHONE"], send_smsbao),
    ("企业微信机器人", ["WECHAT_WORK_WEBHOOK"], send_wechat_work),
    ("钉钉机器人", ["DINGTALK_WEBHOOK"], send_dingtalk),
    ("飞书机器人", ["FEISHU_WEBHOOK"], send_feishu),
    ("Telegram", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"], send_telegram),
    ("ntfy", ["NTFY_TOPIC"], send_ntfy),
    ("通用 Webhook", ["SMS_WEBHOOK_URL"], send_generic_webhook),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default="")
    parser.add_argument("--text-file", default="")
    args = parser.parse_args()

    text = args.text
    if args.text_file and os.path.exists(args.text_file):
        text = open(args.text_file, encoding="utf-8").read().strip()
    if not text:
        text = "站点巡检发现异常，详情见仓库 issue。"
    # 短信通道对长度敏感，统一截断
    text = text[:300]

    for name, required, sender in CHANNELS:
        if not all(os.environ.get(key) for key in required):
            continue
        if name == "ntfy" and ntfy_topic_too_weak():
            print(
                "::warning::ntfy topic 不足 %d 位，公共 ntfy.sh 上任何人猜到就能订阅全部告警，"
                "本次跳过该渠道。请换成长随机串，或改用自建服务端并配置 NTFY_TOKEN。"
                % NTFY_PUBLIC_MIN_TOPIC
            )
            continue
        ok, detail = sender(text)
        if ok:
            print("已通过「%s」发送提醒。" % name)
            return 0
        print("「%s」发送失败：%s" % (name, detail))
        return 1

    print("::warning::尚未配置任何提醒渠道，本次仅记录到 issue。")
    print("可选：短信宝 / 企业微信机器人 / 钉钉机器人 / 飞书机器人 / Telegram / ntfy / 通用 Webhook")
    return 0


if __name__ == "__main__":
    sys.exit(main())
