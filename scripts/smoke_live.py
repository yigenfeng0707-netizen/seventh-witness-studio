# -*- coding: utf-8 -*-
"""部署后公网冒烟：等待容器就绪 → 开新局/提问/出示证据/第二章/指认/成绩卡。

只依赖标准库，GitHub Actions 部署后直接运行。
失败时以非 0 退出，避免“部署成功但线上不可玩”。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = "https://gsym236998-seventh-witness.ms.show"
BASE = ROOT + "/gradio_api"
SESSION = "ci-smoke-%d" % int(time.time())
EXPECTED = os.environ.get("GITHUB_SHA", "")[:12]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131"
HEADERS = {"Content-Type": "application/json", "User-Agent": UA}


def _req(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=timeout)


def wait_ready(max_wait=900):
    """等到新容器就绪：/config 里出现本次 commit 的 build 标记。"""
    start = time.time()
    last = None
    while time.time() - start < max_wait:
        try:
            with _req(ROOT + "/config", timeout=20) as r:
                cfg = r.read().decode("utf-8", "ignore")
            if r.status == 200:
                if not EXPECTED or EXPECTED in cfg:
                    print("[smoke] 新容器就绪 build=%s（%.0fs）"
                          % (EXPECTED or "dev", time.time() - start))
                    return
                last = "旧版本仍在运行"
        except Exception as e:
            last = e
        time.sleep(15)
    raise RuntimeError("新容器 15 分钟内未就绪：%s" % last)


def _text(msg):
    """Gradio 6 的 content 可能是字符串，也可能是 [{'text': ...}] 块列表。"""
    content = (msg or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(x.get("text", "") if isinstance(x, dict) else str(x)
                       for x in content)
    return str(content or "")


def call(name, data):
    payload = json.dumps({"data": data, "session_hash": SESSION}).encode("utf-8")
    with _req(BASE + "/call/" + name, data=payload, timeout=30) as r:
        event_id = json.loads(r.read().decode("utf-8"))["event_id"]
    with _req(BASE + "/call/" + name + "/" + event_id, timeout=120) as r:
        text = r.read().decode("utf-8")
    event, data_line = None, None
    for line in text.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_line = line.split(":", 1)[1].strip()
    if event != "complete":
        raise RuntimeError("%s 失败：%s %s" % (name, event, (data_line or "")[:300]))
    return json.loads(data_line)


def main():
    wait_ready()

    out = call("do_restart", ["第一章 · 自鸣钟机芯失窃案", "普通", ""])
    assert len(out) == 21, "do_restart 输出槽位异常：%d" % len(out)
    assert "卷宗" in _text(out[0][0]), "开局缺少卷宗"
    assert "data:image/jpeg;base64" in str(out[2]), "状态卡缺少立绘"
    print("[smoke] 第一章开局 / 卷宗 / 立绘 OK")

    out = call("do_ask", ["案发当晚你在哪里？", []])
    assert any("侦探" in _text(m) for m in out[0]), "提问无回复"
    assert "线索" in out[1], "HUD 缺少线索计数"
    print("[smoke] 在线提问 OK")

    out = call("do_present", [
        "📄 账本残页 — 酒馆记账簿残页，有一笔三倍工钱的定制记录", []])
    assert "线索 1/4" in out[1], "有效证据未解锁线索"
    print("[smoke] 证据坦白 OK")

    out = call("do_confront", ["王大锤 × 苏眉 · 案发当晚", []])
    assert len(out) == 10, "do_confront 输出槽位异常：%d" % len(out)
    raw = out[8].get("choices") or []
    flat = [c[0] if isinstance(c, (list, tuple)) else c for c in raw]
    assert flat == ["王大锤", "苏眉"], "对质选项异常：%s" % flat
    out = call("do_resolve", ["王大锤", []])
    assert "谎言被揭穿" in _text(out[0][-1]), "对质结算失败"
    print("[smoke] 当面对质 OK")

    out = call("do_restart", ["第二章 · 狱中忏悔信失踪案", "普通", "0:1:1:0"])
    assert "第二章" in out[9]["value"], "第二章未切换"
    choices = out[13].get("choices") or []
    assert any("贾万通" in str(c) for c in choices), "第二章指认名单未切换"
    assert out[14]["value"] == "忏悔信里写了什么？", "第二章快捷问题未切换"
    print("[smoke] 第二章指认/快捷问题 OK")

    call("do_accuse", ["🏪 贾万通（当铺老板）", []])
    out = call("do_card", ["0:1:1:0"])
    assert out[0].get("visible") is True, "成绩卡未显示"
    assert out[0].get("value", {}).get("url"), "成绩卡无图片 URL"
    print("[smoke] 成绩卡生成 OK")

    out = call("do_restart", ["终章 · 第七位证人", "普通", "0:1:1:1"])
    assert "终章" in out[9]["value"], "终章未切换"
    assert any("严崇山" in str(c) for c in (out[13].get("choices") or [])), "终章指认名单异常"
    assert len(out[19].get("choices") or []) == 2, "终章对质点数量异常"
    out = call("do_confront", ["严崇山 × 温书仪 · 煤油壶从哪来", []])
    assert len(out) == 10, "终章对质输出槽位异常"
    out = call("do_resolve", ["严崇山", []])
    assert "谎言被揭穿" in _text(out[0][-1]), "终章对质结算失败"
    print("[smoke] 终章/对质 OK")

    print("[smoke] 全部通过")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("[smoke] FAILED:", e)
        sys.exit(1)
