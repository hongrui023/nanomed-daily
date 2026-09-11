# -*- coding: utf-8 -*-
"""
把用户的一句大白话（可能口语化、有错别字、不完整）变成高质量的 PubMed 检索关键词。
用法：
  ZHIPU_KEY=xxx python scripts/ai_keywords.py "我做纳米材料治肿瘤，主要看LNP递送和铁死亡"
输出 JSON：{"intent": "...", "corrected": "...", "keywords": [...], "text": "...", "ts": ...}
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = os.environ.get("ZHIPU_MODEL", "glm-4-flash-250414")
MIN_KEYWORDS = 8


def load_system():
    """提示词统一放在 prompts/keywords_system.txt，网页与服务器共用同一份。"""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "prompts", "keywords_system.txt")
    if os.path.exists(p):
        return io.open(p, encoding="utf-8").read().strip()
    return ("你是纳米医学文献检索专家。把用户的一句话变成 10 个左右英文检索关键词，"
            "每个 1-3 个单词，用领域标准术语（如铁死亡=ferroptosis）。只输出 JSON："
            '{"intent":"...","corrected":"...","keywords":["..."]}')


def chat(messages, key):
    payload = {"model": MODEL, "temperature": 0.3, "max_tokens": 1000,
               "messages": messages}
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        raise SystemExit("智谱 API 报错 %s\n%s" % (e.code, e.read().decode("utf-8", "ignore")[:400]))


def extract_json(s):
    s = (s or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*", "", s).strip().rstrip("`").strip()
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def clean_keywords(raw):
    out = []
    for k in raw or []:
        k = (k or "").strip().strip("-*•·").strip().strip('"').strip()
        if not k:
            continue
        if len(k.split()) > 4:          # 太长的直接丢掉，避免长句
            continue
        if k.lower() in [x.lower() for x in out]:
            continue
        out.append(k)
    return out


def main():
    key = os.environ.get("ZHIPU_KEY", "").strip()
    if not key:
        raise SystemExit("缺少 ZHIPU_KEY")
    text = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not text:
        raise SystemExit('请给一句话，例如：python scripts/ai_keywords.py "我做纳米材料治肿瘤"')

    sysmsg = load_system()
    messages = [
        {"role": "system", "content": sysmsg},
        {"role": "user", "content": "我想追踪的方向是：" + text},
    ]

    first = chat(messages, key)
    data = extract_json(first) or {}
    kws = clean_keywords(data.get("keywords"))

    # 兜底：关键词太少会让召回面变窄，再追问一次
    if len(kws) < MIN_KEYWORDS:
        messages.append({"role": "assistant", "content": first})
        messages.append({"role": "user", "content":
                         "你只给了 %d 个关键词，太少。请补充到 10-12 个："
                         "除了我提到的方向，再补上同领域常见的技术、材料、机制类术语。"
                         "同样只输出 JSON。" % len(kws)})
        second = chat(messages, key)
        d2 = extract_json(second) or {}
        if clean_keywords(d2.get("keywords")):
            data, kws = d2, clean_keywords(d2.get("keywords"))

    corrected = (data.get("corrected") or "").strip()
    if corrected in ("无", "没有", "none", "None", "...", "。"):
        corrected = ""

    print(json.dumps({
        "intent": (data.get("intent") or "").strip(),
        "corrected": corrected,
        "keywords": kws,
        "text": text,
        "ts": int(time.time()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
