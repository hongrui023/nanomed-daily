# -*- coding: utf-8 -*-
"""
第 2 步：AI 写大白话摘要
用智谱 GLM-4-Flash（官方免费模型）把每篇论文总结成三句话。
带缓存：同一篇论文只算一次，以后直接复用，不重复花额度。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash-250414"
CACHE = os.path.join(BASE, "cache", "ai_cache.json")

PROMPT = """你是纳米医学领域的资深科研助手，擅长把高深论文讲成人话。
请用大白话总结下面这篇论文，严格按这个格式输出，不要加多余的话：

【一句话】用一句最通俗的话说清这篇论文干了什么（不超过40字）。
【发现了什么】1-2 句，说清核心发现或做了什么新东西。
【为什么重要】1-2 句，说清它解决了什么老问题、意义在哪。
【跟纳米医学的关系】1-2 句，说清它跟纳米材料/纳米药物/递送系统有什么关系。

要求：说人话，避免堆砌术语；不确定的地方说"可能"，不要编造数字。

标题：{title}
期刊：{journal}
摘要：{abstract}
"""


def log(m):
    print(m, flush=True)


def load_cache():
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(c):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(c, open(CACHE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def call_ai(key, prompt):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"], d.get("usage", {})


def main(date_str=None):
    key = os.environ.get("ZHIPU_KEY", "").strip()
    if not key:
        log("!! 没有拿到智谱密钥（环境变量 ZHIPU_KEY），跳过 AI 摘要。")
        return False

    if date_str is None:
        ds = sorted(os.listdir(os.path.join(BASE, "data")))
        ds = [d for d in ds if d.endswith(".json") and d != "index.json"]
        if not ds:
            log("!! 没有数据文件，请先运行 fetch_papers.py")
            return False
        date_str = ds[-1].replace(".json", "")

    path = os.path.join(BASE, "data", date_str + ".json")
    data = json.load(open(path, encoding="utf-8"))
    papers = data["papers"]
    cache = load_cache()

    todo = [p for p in papers if p["pmid"] not in cache]
    log(f"共 {len(papers)} 篇，其中 {len(todo)} 篇需要新写摘要，"
        f"{len(papers) - len(todo)} 篇用缓存。")

    used = 0
    for i, p in enumerate(todo, 1):
        prompt = PROMPT.format(
            title=p.get("title", ""),
            journal=p.get("journal_display") or p.get("journal", ""),
            abstract=(p.get("abstract", "") or "（无摘要）")[:3000])
        try:
            txt, usage = call_ai(key, prompt)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            log(f"  [{i}/{len(todo)}] 失败 HTTP {e.code}: {detail}")
            if e.code in (401, 403):
                log("!! 密钥无效或没权限，停止。")
                break
            time.sleep(3)
            continue
        except Exception as e:
            log(f"  [{i}/{len(todo)}] 失败 {type(e).__name__}: {str(e)[:200]}")
            time.sleep(3)
            continue

        cache[p["pmid"]] = txt
        used += usage.get("total_tokens", 0)
        log(f"  [{i}/{len(todo)}] OK  {p.get('title', '')[:48]}...")
        time.sleep(1.2)

    for p in papers:
        p["ai"] = cache.get(p["pmid"], "")

    data["ai_tokens_used"] = used
    json.dump(data, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    save_cache(cache)
    log("=" * 60)
    log(f"完成。本次新消耗约 {used} tokens。缓存累计 {len(cache)} 篇。")
    return True


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
