# -*- coding: utf-8 -*-
"""
第 2 步：AI 写大白话摘要 + 中文标题 + 人话版通俗解释
用智谱 GLM-4-Flash（官方免费模型）。

每篇论文产出 6 块：
  中文标题 / 人话版（零术语+比喻）/ 对你有什么用 / 靠谱程度
  专业版四段摘要（一句话、发现了什么、为什么重要、跟纳米医学的关系）

带缓存：同一篇论文只算一次，以后直接复用。
缓存里的旧条目缺哪块就单独补哪块（只翻标题、只写人话版），不整篇重算。
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

PLAIN_VER = 3   # 人话版提示词版本号；改了提示词就 +1，旧缓存会自动重新生成

# 两个提示词共用的人话版规则。已知词 + 对照写法，比单纯下禁令有效得多
_PLAIN_RULES = """【人话版的硬性要求】
① 出现任何专业名词都算失败。下面这些词一个都不许出现：
   - 细胞 / 组织：神经元、小胶质细胞、巨噬细胞、上皮、基质、肿瘤微环境
   - 基因 / 蛋白 / 通路：基因、蛋白、受体、AMPK、mTOR、HIF-1α、Toll样受体、cGAS-STING
   - 材料 / 化学：纳米粒、脂质体、水凝胶、光敏剂、多糖、纳米酶、聚合物
   - 医学 / 实验：血脑屏障、靶向、沉默、转染、凋亡、铁死亡、淀粉样蛋白沉积、
     神经炎症、免疫代谢重编程、体外实验、体内实验
② 必须提及时，一律换成日常说法。照这个尺度改：
     错：体外实验          → 对：实验室培养皿里的实验
     错：体内实验          → 对：在活的老鼠身上做的实验
     错：血脑屏障          → 对：大脑的防护墙
     错：光敏剂            → 对：见光才起效的药
     错：光热治疗          → 对：用光把肿瘤加热
     错：水凝胶            → 对：像果冻一样的胶块
     错：靶向肿瘤          → 对：专门找上肿瘤
     错：基因表达          → 对：让细胞按指令生产东西
     错：细胞表面的受体    → 对：细胞表面的"锁"
     错：淀粉样蛋白沉积    → 对：脑子里堆积的垃圾
③ 必须有一个生活化的比喻（比如快递员、清洁工、生锈、微波炉、钥匙和锁）。
④ 说人话、用短句，不要写"该研究""具有重要意义"这类套话。
⑤ 写完后自己默读一遍：只要读起来还像论文摘要，就重写成大白话再输出。"""

PROMPT = """你是纳米医学领域的资深科研助手，擅长把高深论文讲成人话。
针对下面这篇论文，严格按给定格式输出，不要加任何多余的话。

【中文标题】把标题翻成通顺的中文。专业术语用国内通用译法（如 ferroptosis=铁死亡、
photothermal therapy=光热治疗、lipid nanoparticle=脂质纳米粒）。只输出译文本身。
【人话版】先单独一行写「说白了：」加一句 30 字以内最白的话，再换行用 3-4 句话展开讲
这篇论文干了什么、结果怎么样。
""" + _PLAIN_RULES + """
【对你有什么用】1 句话，读者是纳米医学方向的研究人员：这个思路能给他什么启发、能借鉴什么。
【靠谱程度】1 句话，说清这是细胞实验、动物实验还是人身上做的，离临床大概还有多远、有什么明显局限。
【一句话】用一句最通俗的话说清这篇论文干了什么（不超过40字）。
【发现了什么】1-2 句，说清核心发现或做了什么新东西（可以用专业术语）。
【为什么重要】1-2 句，说清它解决了什么老问题、意义在哪。
【跟纳米医学的关系】1-2 句，说清它跟纳米材料/纳米药物/递送系统有什么关系。

要求：不确定的地方说"可能"，不要编造数字。

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

PLAIN_PROMPT = """你是科普作家，专门给"完全不懂纳米医学的聪明人"讲解论文。
严格按下面的格式输出，不要加任何多余的话。

第一行（必须单独一行）：说白了：<30 字以内，最白的一句总结>
第二行起：用 3-4 句话展开讲这篇论文干了什么、结果怎么样。
""" + _PLAIN_RULES + """

另外再输出两个小标题（各 1 句话）：
【对你有什么用】读者是纳米医学方向的研究人员：这个思路能给他什么启发、能借鉴什么。
【靠谱程度】说清这是细胞实验、动物实验还是人身上做的，离临床大概还有多远、有什么明显局限。

标题：{title}
期刊：{journal}
摘要：{abstract}
"""

# 由「人话版扩充调用」负责的字段（整篇调用时也一起出）
EXTRA_LABELS = ["人话版", "对你有什么用", "靠谱程度"]
ALL_LABELS = ["中文标题"] + EXTRA_LABELS + ["一句话", "发现了什么", "为什么重要", "跟纳米医学的关系"]


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


def call_ai(key, prompt, max_tokens=1100):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["choices"][0]["message"]["content"], d.get("usage", {})


def take(txt, label):
    """取出【label】后面的内容（到下一个小标题或结尾为止）。
    保留换行，人话版的「说白了」才能单独成行、不跟正文糊在一起。"""
    m = re.search(r"【" + label + r"】[ \t]*([\s\S]*?)(?=\n*【|\Z)", txt or "")
    if not m:
        return ""
    return "\n".join(x.strip() for x in m.group(1).split("\n") if x.strip())


def strip_labels(txt, labels):
    out = txt or ""
    for lb in labels:
        out = re.sub(r"【" + lb + r"】[ \t]*[\s\S]*?(?=\n*【|\Z)", "", out)
    return out.strip()


def clean_plain(s):
    """去掉模型自作主张加的「生活化比喻：」之类小标签，只留句子本身。"""
    out = []
    for ln in (s or "").split("\n"):
        ln = re.sub(r"^(生活化比喻|比喻|打个比方)\s*[：:]\s*", "", ln.strip())
        ln = re.sub(r"^【人话版】\s*", "", ln)
        if ln:
            out.append(ln)
    return "\n".join(out)


def norm_entry(v):
    """兼容旧缓存（值是纯字符串 / 只有 ai、zh 两种字段）。pv = 人话版提示词版本。"""
    base = {"ai": "", "zh": "", "plain": "", "use": "", "conf": "", "pv": 0}
    if isinstance(v, dict):
        for k in ("ai", "zh", "plain", "use", "conf"):
            base[k] = (v.get(k) or "").strip()
        try:
            base["pv"] = int(v.get("pv") or 0)
        except Exception:
            base["pv"] = 0
    else:
        base["ai"] = (v or "").strip()
    return base


def parse_full(txt):
    e = {"zh": take(txt, "中文标题"),
         "plain": clean_plain(take(txt, "人话版")),
         "use": take(txt, "对你有什么用"),
         "conf": take(txt, "靠谱程度"),
         "pv": PLAIN_VER}
    e["ai"] = strip_labels(txt, ALL_LABELS)
    return e


def parse_plain(txt):
    """只补人话版时的解析（这种返回里没有【人话版】标题，前几行就是正文）。"""
    use = take(txt, "对你有什么用")
    conf = take(txt, "靠谱程度")
    body = strip_labels(txt, ["对你有什么用", "靠谱程度"])
    return clean_plain(body), use, conf


def run_one(key, date_str, cache):
    path = os.path.join(BASE, "data", date_str + ".json")
    data = json.load(open(path, encoding="utf-8"))
    papers = data.get("papers", [])

    need_full, need_zh, need_plain = [], [], []
    for p in papers:
        e = norm_entry(cache.get(p["pmid"]))
        if not e["ai"]:
            need_full.append(p)
        else:
            if not e["zh"]:
                need_zh.append(p)
            if not e["plain"] or e["pv"] != PLAIN_VER:
                need_plain.append(p)

    log(f"[{date_str}] 共 {len(papers)} 篇｜整篇新写 {len(need_full)} 篇｜"
        f"只补中文标题 {len(need_zh)} 篇｜只补人话版 {len(need_plain)} 篇｜"
        f"完全命中缓存 {len(papers) - len(need_full) - len(need_zh) - len(need_plain)} 篇")

    used = 0

    for i, p in enumerate(need_full, 1):
        prompt = PROMPT.format(
            title=p.get("title", ""),
            journal=p.get("journal_display") or p.get("journal", ""),
            abstract=(p.get("abstract", "") or "（无摘要）")[:3000])
        try:
            txt, usage = call_ai(key, prompt)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            log(f"  [{i}/{len(need_full)}] 失败 HTTP {e.code}: {detail}")
            if e.code in (401, 403):
                log("!! 密钥无效或没权限，停止。")
                return False
            time.sleep(3)
            continue
        except Exception as e:
            log(f"  [{i}/{len(need_full)}] 失败 {type(e).__name__}: {str(e)[:200]}")
            time.sleep(3)
            continue

        cache[p["pmid"]] = parse_full(txt)
        used += usage.get("total_tokens", 0)
        log(f"  [{i}/{len(need_full)}] OK  {cache[p['pmid']]['zh'] or p.get('title', '')[:40]}")
        time.sleep(1.2)

    for i, p in enumerate(need_plain, 1):
        try:
            txt, usage = call_ai(key, PLAIN_PROMPT.format(
                title=p.get("title", ""),
                journal=p.get("journal_display") or p.get("journal", ""),
                abstract=(p.get("abstract", "") or "（无摘要）")[:3000]))
        except Exception as e:
            log(f"  [补人话版 {i}/{len(need_plain)}] 跳过 {type(e).__name__}: {str(e)[:120]}")
            time.sleep(2)
            continue
        e = norm_entry(cache.get(p["pmid"]))
        pl, us, cf = parse_plain(txt)
        e["plain"], e["use"], e["conf"] = pl, us, cf
        e["pv"] = PLAIN_VER
        if e["plain"]:
            cache[p["pmid"]] = e
            used += usage.get("total_tokens", 0)
            log(f"  [补人话版 {i}/{len(need_plain)}] OK  {e['plain'][:52]}…")
        else:
            log(f"  [补人话版 {i}/{len(need_plain)}] 返回内容没解析出来，跳过")
        time.sleep(1.0)

    for i, p in enumerate(need_zh, 1):
        try:
            txt, usage = call_ai(key, ZH_PROMPT.format(title=p.get("title", "")),
                                 max_tokens=120)
        except Exception as e:
            log(f"  [补标题 {i}/{len(need_zh)}] 跳过 {type(e).__name__}: {str(e)[:120]}")
            time.sleep(2)
            continue
        zh = take(txt, "中文标题").strip("《》\"'")
        if zh:
            e = norm_entry(cache.get(p["pmid"]))
            e["zh"] = zh
            cache[p["pmid"]] = e
            used += usage.get("total_tokens", 0)
            log(f"  [补标题 {i}/{len(need_zh)}] OK  {zh}")
        time.sleep(1.0)

    n_ai = n_zh = n_pl = 0
    for p in papers:
        e = norm_entry(cache.get(p["pmid"]))
        if e["ai"]:
            p["ai"] = e["ai"]
            n_ai += 1
        if e["zh"]:
            p["title_zh"] = e["zh"]
            n_zh += 1
        if e["plain"]:
            p["plain"] = e["plain"]
            n_pl += 1
        if e["use"]:
            p["use"] = e["use"]
        if e["conf"]:
            p["conf"] = e["conf"]

    data["ai_tokens_used"] = used
    json.dump(data, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log(f"[{date_str}] 完成：摘要 {n_ai}/{len(papers)}，中文标题 {n_zh}/{len(papers)}，"
        f"人话版 {n_pl}/{len(papers)}，本次约 {used} tokens。")
    return True


def main(date_str=None):
    key = os.environ.get("ZHIPU_KEY", "").strip()
    if not key:
        log("!! 没有拿到智谱密钥（环境变量 ZHIPU_KEY），跳过 AI 生成。")
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
