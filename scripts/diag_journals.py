# -*- coding: utf-8 -*-
"""诊断可疑期刊：对比 [Journal] / [ta] / 全称 三种写法的命中数，
并抽查实际返回的论文到底属于哪本期刊。"""
import json
import time
import urllib.parse
import urllib.request

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
UA = {"User-Agent": "nanomed-tracker/0.1"}


def get(endpoint, **params):
    params.setdefault("retmode", "json")
    url = EUTILS + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def count(term):
    d = get("esearch.fcgi", db="pubmed", term=term, retmax="0")
    return int(d["esearchresult"]["count"])


def sample_journals(term, n=5):
    d = get("esearch.fcgi", db="pubmed", term=term, retmax=str(n), sort="date")
    ids = d["esearchresult"].get("idlist", [])
    if not ids:
        return []
    s = get("esummary.fcgi", db="pubmed", id=",".join(ids))
    out = []
    for i in ids:
        out.append(s["result"][i].get("source", "?"))
    return out


CASES = [
    ("Nano Research", ["Nano Res", "Nano Research"]),
    ("Nano Today", ["Nano Today"]),
    ("Precision Nanomedicine", ["Precis Nanomed", "Precision Nanomed"]),
    ("Nanotoxicology", ["Nanotoxicology"]),
    ("J Nanopart Res", ["J Nanopart Res"]),
    ("J Biomed Nanotechnol", ["J Biomed Nanotechnol"]),
    ("Adv Ther (Weinh)", ["Adv Ther (Weinh)"]),
    ("Bionanoscience", ["Bionanoscience"]),
]

for label, names in CASES:
    print("=" * 70)
    print(f"【{label}】")
    for nm in names:
        for field in ("Journal", "ta"):
            t = f'"{nm}"[{field}]'
            try:
                c = count(t)
            except Exception as e:
                print(f"  {t:<46} 错误 {e}")
                continue
            time.sleep(0.4)
            print(f"  {t:<46} {c:>8} 篇", end="")
            if c:
                try:
                    print("   实际来自:", sample_journals(t, 4))
                except Exception as e:
                    print("   (取样失败", e, ")")
                time.sleep(0.4)
            else:
                print()

print("=" * 70)
print("【两本 Nanomedicine 会不会混淆】")
for t in ['"Nanomedicine"[Journal]',
          '"Nanomedicine (Lond)"[Journal]',
          '"Nanomedicine"[Journal] NOT "Nanomedicine (Lond)"[Journal]',
          '"Nanomedicine: Nanotechnology, Biology, and Medicine"[Journal]']:
    try:
        c = count(t)
    except Exception as e:
        print(f"  {t}  错误 {e}")
        continue
    time.sleep(0.4)
    print(f"  {t:<72} {c:>7} 篇", end="")
    if c:
        try:
            print("   实际来自:", sample_journals(t, 4))
        except Exception:
            print()
        time.sleep(0.4)
    else:
        print()
