# -*- coding: utf-8 -*-
"""
第 2 步：AI 写大白话摘要 + 中文标题
用智谱 GLM-4-Flash（官方免费模型）把每篇论文总结成几句话，并把标题翻成中文。
带缓存：同一篇论文只算一次，以后直接复用，不重复花额度。
缓存里已有旧版摘要、但还没中文标题的，会单独补一次翻译（只翻标题，很快）。
"""
import json
import os
import re
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

【中文标题】把标题翻成通顺的中文。专业术语用国内通用译法（如 ferroptosis=铁死亡、
photothermal therapy=光热治疗、lipid nanoparticle=脂质纳米粒）。
只输出译文本身，不要加书名号、引号或英文。
【一句话】用一句最通俗的话说清这篇论文干了什么（不超过40字）。
【发现了什么】1-2 句，说清核心发现或做了什么新东西。
【为什么重要】1-2 句，说清它解决了什么老问题、意义在哪。
【跟纳米医学的关系】1-2 句，说清它跟纳米材料/纳米药物/递送系统有什么关系。

要求：说人话，避免堆砌术语；不确定的地方说"可能"，不要编造数字。

标题：{title}
期刊：{journal}
摘要：{abstract}
"""

ZH_PROMPT = """只做一件事：把下面这篇论文的标题翻成通顺的中文。
专业术语用国内通用译法（如 ferroptosis=铁死亡、photothermal therapy=光热治疗、
lipid nanoparticle=脂质纳米粒）。不要加书名号、引号或英文，不要解释。
严格按这个格式输出一行，不要输出别的内容：
【中文标题】译文

标题：{title}
"""

RE_ZH = re.compile(r"【中文标题】\s*(.*)")


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


def call_ai(key, prompt, max_tokens=700):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"], d.get("usage", {})


def split_zh(txt):
    """从 AI 返回里摘出【中文标题】，并从摘要正文里去掉这一行。"""
    zh = ""
    m = RE_ZH.search(txt or "")
    if m:
        zh = m.group(1).strip().strip("《》\"'")
    body = RE_ZH.sub("", txt or "").strip()
    return body, zh


def norm_entry(v):
    """兼容旧缓存（值是纯字符串），统一成 {ai, zh} 字典。"""
    if isinstance(v, dict):
        return {"ai": v.get("ai", ""), "zh": v.get("zh", "")}
    return {"ai": v or "", "zh": ""}


def translate_only(key, title):
    txt, usage = call_ai(key, ZH_PROMPT.format(title=title), max_tokens=120)
    _, zh = split_zh(txt)
    return zh, usage


def run_one(key, date_str, cache):
    path = os.path.join(BASE, "data", date_str + ".json")
    data = json.load(open(path, encoding="utf-8"))
    papers = data.get("papers", [])

    need_sum = []    # 连摘要都没有，要整篇总结
    need_zh = []     # 摘要有了，只缺中文标题
    for p in papers:
        e = norm_entry(cache.get(p["pmid"]))
        if not e["ai"]:
            need_sum.append(p)
        elif not e["zh"]:
            need_zh.append(p)

    log(f"[{date_str}] 共 {len(papers)} 篇｜新写摘要 {len(need_sum)} 篇｜"
        f"仅补中文标题 {len(need_zh)} 篇｜完全命中缓存 "
        f"{len(papers) - len(need_sum) - len(need_zh)} 篇")

    used = 0
    for i, p in enumerate(need_sum, 1):
        prompt = PROMPT.format(
            title=p.get("title", ""),
            journal=p.get("journal_display") or p.get("journal", ""),
            abstract=(p.get("abstract", "") or "（无摘要）")[:3000])
        try:
            txt, usage = call_ai(key, prompt)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            log(f"  [{i}/{len(need_sum)}] 失败 HTTP {e.code}: {detail}")
            if e.code in (401, 403):
                log("!! 密钥无效或没权限，停止。")
                return False
            time.sleep(3)
            continue
        except Exception as e:
            log(f"  [{i}/{len(need_sum)}] 失败 {type(e).__name__}: {str(e)[:200]}")
            time.sleep(3)
            continue

        body, zh = split_zh(txt)
        cache[p["pmid"]] = {"ai": body, "zh": zh}
        used += usage.get("total_tokens", 0)
        log(f"  [{i}/{len(need_sum)}] OK  {zh or p.get('title', '')[:40]}")
        time.sleep(1.2)

    for i, p in enumerate(need_zh, 1):
        try:
            zh, usage = translate_only(key, p.get("title", ""))
        except Exception as e:
            log(f"  [补标题 {i}/{len(need_zh)}] 跳过 {type(e).__name__}: {str(e)[:120]}")
            time.sleep(2)
            continue
        if zh:
            e = norm_entry(cache.get(p["pmid"]))
            e["zh"] = zh
            cache[p["pmid"]] = e
            used += usage.get("total_tokens", 0)
            log(f"  [补标题 {i}/{len(need_zh)}] OK  {zh}")
        time.sleep(1.0)

    filled = 0
    for p in papers:
        e = norm_entry(cache.get(p["pmid"]))
        if e["ai"]:
            p["ai"] = e["ai"]
        if e["zh"]:
            p["title_zh"] = e["zh"]
            filled += 1

    data["ai_tokens_used"] = used
    json.dump(data, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log(f"[{date_str}] 完成，有中文标题的 {filled}/{len(papers)} 篇，"
        f"本次约 {used} tokens。")
    return True


def main(date_str=None):
    key = os.environ.get("ZHIPU_KEY", "").strip()
    if not key:
        log("!! 没有拿到智谱密钥（环境变量 ZHIPU_KEY），跳过 AI 摘要。")
        return False

    cache = load_cache()

    if date_str:
        targets = [date_str]
    else:
        ddir = os.path.join(BASE, "data")
        if not os.path.isdir(ddir):
            log("!! 没有 data 目录，请先运行 fetch_papers.py")
            return False
        targets = sorted(f[:-5] for f in os.listdir(ddir)
                         if f.endswith(".json") and f != "index.json")
        if not targets:
            log("!! 没有数据文件，请先运行 fetch_papers.py")
            return False

    ok = True
    for ds in targets:
        if not run_one(key, ds, cache):
            ok = False
            break

    save_cache(cache)
    log("=" * 60)
    log(f"全部完成。缓存累计 {len(cache)} 篇。")
    return ok


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
