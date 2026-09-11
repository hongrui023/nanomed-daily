# -*- coding: utf-8 -*-
"""
第 1 步：抓论文
从 PubMed（免费，无需注册）抓取指定期刊在最近 N 天的新论文，
用关键词筛选后，存成 data/日期.json
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
UA = {"User-Agent": "nanomed-tracker/0.1"}
SLEEP = 0.4


def log(msg):
    print(msg, flush=True)


# ---------- 读配置 ----------
def read_config():
    cfg = {"days": 3, "max_papers": 50}
    p = os.path.join(BASE, "config.txt")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            try:
                cfg[k.strip()] = int(v.strip())
            except ValueError:
                cfg[k.strip()] = v.strip()
    return cfg


def read_journals():
    """每行：显示名 | PubMed写法   （没有 | 就两个都用同一个）"""
    out, p = [], os.path.join(BASE, "journals.txt")
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            disp, pm = line.split("|", 1)
        else:
            disp = pm = line
        out.append((disp.strip(), pm.strip()))
    return out


def read_keywords():
    """返回 (must, opt)。

    一行一个关键词。以 + 开头的表示「必须命中」（AND）：
        必须词：每一篇论文都得含有它，否则不要 —— 用来锁死研究方向。
        可选词：命中任意一个就算（OR），用来扩大覆盖面。
    例：
        +nanoparticle     ← 必须是纳米相关
        +neuromodulation  ← 而且还必须跟神经调控有关
        tumor therapy     ← 可选：肿瘤治疗也一起看
    """
    must, opt, p = [], [], os.path.join(BASE, "keywords.txt")
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("+"):
            v = line[1:].strip().lower()
            if v:
                must.append(v)
        else:
            opt.append(line.lower())
    return must, opt


def read_gate():
    """门槛词：至少命中一个才认为是纳米医学相关"""
    out, p = [], os.path.join(BASE, "gate.txt")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip().lower()
            if line and not line.startswith("#"):
                out.append(line)
    return out


# ---------- PubMed 接口 ----------
def http_get(endpoint, **params):
    params.setdefault("db", "pubmed")
    url = EUTILS + endpoint + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def esearch(term, retmax=100):
    raw = http_get("esearch.fcgi", term=term, retmax=str(retmax),
                   retmode="json", sort="date")
    d = json.loads(raw.decode("utf-8"))
    return int(d["esearchresult"]["count"]), d["esearchresult"].get("idlist", [])


def txt(node):
    return "".join(node.itertext()).strip() if node is not None else ""


def efetch(ids):
    """批量取论文详情（标题/摘要/期刊/日期/DOI）"""
    if not ids:
        return {}
    out = {}
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        raw = http_get("efetch.fcgi", id=",".join(chunk), retmode="xml")
        root = ET.fromstring(raw)
        for art in root.iter("PubmedArticle"):
            pmid = txt(art.find(".//MedlineCitation/PMID"))
            if not pmid:
                continue
            a = art.find(".//MedlineCitation/Article")
            if a is None:
                continue
            title = txt(a.find("ArticleTitle"))
            jr = txt(a.find(".//Journal/Title")) or txt(a.find(".//Journal/ISOAbbreviation"))
            abstract = " ".join(
                txt(x) for x in a.findall(".//Abstract/AbstractText")).strip()
            doi = ""
            for e in a.findall("ELocationID"):
                if e.get("EIdType") == "doi":
                    doi = txt(e)
            if not doi:
                for aid in art.findall(".//ArticleIdList/ArticleId"):
                    if aid.get("IdType") == "doi":
                        doi = txt(aid)

            # 日期
            pd = a.find(".//Journal/JournalIssue/PubDate")
            y = m = d = ""
            if pd is not None:
                y = txt(pd.find("Year"))
                m = txt(pd.find("Month"))
                d = txt(pd.find("Day"))
                if not y:
                    md = txt(pd.find("MedlineDate"))
                    mm = re.match(r"(\d{4})", md)
                    if mm:
                        y = mm.group(1)
            mon = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                   "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
            try:
                mi = int(m) if m.isdigit() else mon.get(m[:3], 1)
            except Exception:
                mi = 1
            try:
                di = int(d) if d.isdigit() else 1
            except Exception:
                di = 1
            pub = f"{y or '0000'}-{mi:02d}-{di:02d}" if y else ""

            authors = []
            for au in a.findall(".//AuthorList/Author")[:4]:
                ln = txt(au.find("LastName"))
                if ln:
                    authors.append(ln)

            out[pmid] = {
                "pmid": pmid,
                "title": title,
                "journal": jr,
                "pubdate": pub,
                "doi": doi,
                "authors": authors,
                "abstract": abstract,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        time.sleep(SLEEP)
    return out


# ---------- 主流程 ----------
def main():
    cfg = read_config()
    days = int(cfg.get("days", 3))
    max_papers = int(cfg.get("max_papers", 50))
    journals = read_journals()
    kw_must, kw_opt = read_keywords()
    keywords = kw_must + kw_opt

    today = date.today()
    start = today - timedelta(days=days)
    span = f'{start.strftime("%Y/%m/%d")}:{today.strftime("%Y/%m/%d")}'

    log("=" * 70)
    log(f"抓取区间：最近 {days} 天（{span}）")
    log(f"期刊：{len(journals)} 本　关键词：{len(keywords)} 个　上限：{max_papers} 篇")
    if kw_must:
        log(f"必须命中：{'、'.join(kw_must)}（缺一个就不要）")
    if kw_opt:
        log(f"可选命中：{'、'.join(kw_opt)}（命中任一即可）")
    log("=" * 70)

    # 关键词拆成单词
    STOP = {"the", "and", "for", "with", "via", "based", "using", "of", "in",
            "on", "a", "an", "to", "by"}
    kw_tokens = {}
    for k in keywords:
        if re.search(r"[\u4e00-\u9fff]", k):
            toks = [k]
        else:
            toks = [t for t in re.split(r"[^a-z0-9]+", k)
                    if len(t) >= 3 and t not in STOP]
        kw_tokens[k] = toks or [k]

    id_map = {}            # pmid -> 期刊显示名
    per_journal = {}       # 期刊 -> 篇数
    failed = []
    for disp, pm in journals:
        term = f'"{pm}"[Journal] AND {span}[Date - Entrez]'
        try:
            cnt, ids = esearch(term, retmax=100)
        except Exception as e:
            log(f"  [错误] {disp}: {e}")
            failed.append(disp)
            time.sleep(SLEEP)
            continue
        time.sleep(SLEEP)
        per_journal[disp] = cnt
        for i in ids:
            id_map.setdefault(i, disp)
        if cnt == 0 and ids:
            pass
        if cnt > 0:
            log(f"  {disp:<52} {cnt:>4} 篇")

    all_ids = list(id_map.keys())
    log("-" * 70)
    log(f"抓到 {len(all_ids)} 篇（未去重）")

    if not all_ids:
        log("!! 一篇都没抓到。可能原因：日期太近 PubMed 还没收录，或期刊名不对。")
        return None

    log("正在取标题和摘要 ...")
    papers = efetch(all_ids)
    log(f"取到详情 {len(papers)} 篇")

    # 期刊归属（用搜索时的结果兜底）
    for pmid, p in papers.items():
        p["journal_display"] = id_map.get(pmid, p.get("journal", ""))

    items = list(papers.values())

    # 关键词筛选（拆词匹配：一个关键词里的词全部出现才算命中）
    kw_hits = {k: 0 for k in keywords}
    if keywords:
        kept = []
        for p in items:
            blob = (p.get("title", "") + " " + p.get("abstract", "")).lower()
            must_hits = [k for k in kw_must if all(t in blob for t in kw_tokens[k])]
            if kw_must:
                # 必须词必须全部命中
                if len(must_hits) < len(kw_must):
                    continue
            opt_hits = [k for k in kw_opt if all(t in blob for t in kw_tokens[k])]
            if kw_must:
                # 写了可选词，还得至少命中一个，避免只有必须词时把范围放太开
                if kw_opt and not opt_hits:
                    continue
            else:
                if not opt_hits:
                    continue
            hits = must_hits + opt_hits
            p["matched"] = hits
            p["matched_n"] = len(hits)
            p["must_n"] = len(must_hits)
            for k in hits:
                kw_hits[k] += 1
            kept.append(p)
        log(f"关键词命中 {len(kept)} 篇（总 {len(items)} 篇）")
        if kw_must and not kept:
            log("  ⚠ 一篇都没命中：必须词可能太严，或这几个词组合起来在最近这几天没有论文。")
            log("    建议：把最核心的那个词留成必须，其他改成不带 + 的可选词。")
        items = kept
    else:
        log("没有关键词，保留全部")

    # 门槛筛选：必须跟医学沾边
    gate = read_gate()
    if gate:
        before = len(items)
        items = [p for p in items
                 if any(g in (p.get("title", "") + " " + p.get("abstract", "")).lower()
                        for g in gate)]
        log(f"门槛筛选后剩 {len(items)} 篇（拦掉 {before - len(items)} 篇非医学论文）")

    # 门槛之后再统计一次每个关键词真正带来多少「对口」论文（截断前）
    kw_final = {k: 0 for k in keywords}
    for p in items:
        for k in p.get("matched", []):
            kw_final[k] += 1

    if keywords:
        log("-" * 70)
        log("关键词体检（门槛后实际带来多少篇）：")
        for k, n in sorted(kw_final.items(), key=lambda x: -x[1]):
            tag = " [必须]" if k in kw_must else ""
            if n == 0:
                log(f"  {k:<38}{tag} {n:>4} 篇   ← 一个都没抓到，建议换掉或删掉")
            else:
                log(f"  {k:<38}{tag} {n:>4} 篇")
        if not kw_must:
            wide = [k for k, n in kw_final.items()
                    if n > len(items) * 0.8 and len(items) > 10]
            if wide:
                log("  ⚠ 这些词几乎命中所有论文，会盖住别的词的效果：" + "、".join(wide))
                log("    想让研究方向更聚焦？在最关键的那个词前面加一个 +（必须命中）。")

    # 排序：先按「命中关键词个数」多的在前（越对口越靠前），同分再按日期新的在前
    items.sort(key=lambda x: x.get("pubdate", ""), reverse=True)
    items.sort(key=lambda x: x.get("matched_n", 0), reverse=True)
    items = items[:max_papers]

    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    out = {
        "date": today.strftime("%Y-%m-%d"),
        "range": f'{start.strftime("%Y-%m-%d")} ~ {today.strftime("%Y-%m-%d")}',
        "days": days,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "journal_count": len(journals),
        "keyword_count": len(keywords),
        "keywords_used": keywords,
        "keywords_must": kw_must,
        "keywords_opt": kw_opt,
        "keyword_stats": kw_final,
        "total_found": len(all_ids),
        "matched": len(items),
        "per_journal": per_journal,
        "failed_journals": failed,
        "papers": items,
    }
    path = os.path.join(BASE, "data", today.strftime("%Y-%m-%d") + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log("=" * 70)
    log(f"已保存 {len(items)} 篇 → data/{today.strftime('%Y-%m-%d')}.json")
    if failed:
        log("以下期刊抓取失败（检查名字）：" + "、".join(failed))
    return path


if __name__ == "__main__":
    main()
