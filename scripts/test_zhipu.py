# -*- coding: utf-8 -*-
"""测试智谱 API 是否可用、GLM-4-Flash 是否免费。"""
import json
import os
import urllib.request

KEY = os.environ.get("ZHIPU_KEY", "")
URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def call(model, messages, max_tokens=300):
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body,
        headers={"Authorization": "Bearer " + KEY,
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d["choices"][0]["message"]["content"], d.get("usage", {})
    except urllib.error.HTTPError as e:
        return None, {"error": e.code, "detail": e.read().decode("utf-8", "ignore")[:600]}
    except Exception as e:
        return None, {"error": type(e).__name__, "detail": str(e)[:400]}


PROMPT = """你是纳米医学领域的资深科研助手。请用大白话总结这篇论文，分三点：
1）发现了什么
2）为什么重要
3）跟纳米医学有什么关系
要求：每点 1-2 句，说人话，不要堆术语。

标题：A lipid nanoparticle platform for mRNA delivery to solid tumours
摘要：We developed a novel ionizable lipid nanoparticle (LNP) formulation that delivers mRNA to solid tumours with high efficiency after intravenous injection. The formulation showed a 10-fold increase in tumour accumulation compared with standard LNPs and induced complete regression in a mouse model of colorectal cancer.
"""

for model in ("glm-4-flash", "glm-4-flash-250414", "glm-4.5-flash"):
    print("=" * 70)
    print("模型:", model)
    out, usage = call(model, [{"role": "user", "content": PROMPT}])
    if out:
        print(out)
        print("用量:", usage)
    else:
        print("失败:", usage)
