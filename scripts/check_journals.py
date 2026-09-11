# -*- coding: utf-8 -*-
"""
连通性 + 期刊名核验脚本（第 1 阶段用）
作用：逐个问 PubMed —— 这 46 本期刊能不能搜到？最近 N 天有几篇新论文？
只用 Python 自带功能，不需要安装任何东西。
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

# (你的期刊名, PubMed 里要用的写法)
JOURNALS = [
    ("ACS Nano", "ACS Nano"),
    ("ACS Applied Materials & Interfaces", "ACS Appl Mater Interfaces"),
    ("Acta Biomaterialia", "Acta Biomater"),
    ("Advanced Drug Delivery Reviews", "Adv Drug Deliv Rev"),
    ("Advanced Healthcare Materials", "Adv Healthc Mater"),
    ("Advanced Materials", "Adv Mater"),
    ("Advanced Therapeutics", "Adv Ther (Weinh)"),
    ("Beilstein Journal of Nanotechnology", "Beilstein J Nanotechnol"),
    ("Biomaterials", "Biomaterials"),
    ("Biomaterials Science", "Biomater Sci"),
    ("Bioconjugate Chemistry", "Bioconjug Chem"),
    ("BioNanoScience", "Bionanoscience"),
    ("Colloids and Surfaces B: Biointerfaces", "Colloids Surf B Biointerfaces"),
    ("Drug Delivery", "Drug Deliv"),
    ("Drug Delivery and Translational Research", "Drug Deliv Transl Res"),
    ("European Journal of Pharmaceutics and Biopharmaceutics", "Eur J Pharm Biopharm"),
    ("Expert Opinion on Drug Delivery", "Expert Opin Drug Deliv"),
    ("International Journal of Nanomedicine", "Int J Nanomedicine"),
    ("International Journal of Pharmaceutics", "Int J Pharm"),
    ("Journal of Biomedical Nanotechnology", "J Biomed Nanotechnol"),
    ("Journal of Controlled Release", "J Control Release"),
    ("Journal of Drug Targeting", "J Drug Target"),
    ("Journal of Nanobiotechnology", "J Nanobiotechnology"),
    ("Journal of Nanoparticle Research", "J Nanopart Res"),
    ("Materials Today Bio", "Mater Today Bio"),
    ("Molecular Pharmaceutics", "Mol Pharm"),
    ("Nano Convergence", "Nano Converg"),
    ("Nano Letters", "Nano Lett"),
    ("Nano Research", "Nano Res"),
    ("Nano Today", "Nano Today"),
    ("Nano-Micro Letters", "Nanomicro Lett"),
    ("Nanomedicine (UK)", "Nanomedicine (Lond)"),
    ("Nanomedicine: NBM", "Nanomedicine"),
    ("Nanoscale", "Nanoscale"),
    ("Nanoscale Advances", "Nanoscale Adv"),
    ("Nanotheranostics", "Nanotheranostics"),
    ("Nanotoxicology", "Nanotoxicology"),
    ("Nanotechnology", "Nanotechnology"),
    ("Nature Biomedical Engineering", "Nat Biomed Eng"),
    ("Nature Materials", "Nat Mater"),
    ("Nature Nanotechnology", "Nat Nanotechnol"),
    ("Particle and Fibre Toxicology", "Part Fibre Toxicol"),
    ("Precision Nanomedicine", "Precis Nanomed"),
    ("Small", "Small"),
    ("Theranostics", "Theranostics"),
    ("WIREs Nanomedicine and Nanobiotechnology",
     "Wiley Interdiscip Rev Nanomed Nanobiotechnol"),
]


def esearch(term, retmax=0):
    params = {"db": "pubmed", "term": term, "retmax": str(retmax), "retmode": "json"}
    url = EUTILS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "nanomed-tracker/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    return int(data["esearchresult"]["count"])


def main(days=7):
    today = date.today()
    start = today - timedelta(days=days)
    span = f'{start.strftime("%Y/%m/%d")}:{today.strftime("%Y/%m/%d")}'

    print(f"今天: {today}   统计区间: 最近 {days} 天 ({span})")
    print("=" * 78)
    print(f'{"期刊":<48}{"写法":<42}{"总篇数":>10}{"近7天":>8}')
    print("-" * 78)

    ok, bad, recent_total = [], [], 0
    for name, pm in JOURNALS:
        term_all = f'"{pm}"[Journal]'
        term_recent = f'"{pm}"[Journal] AND {span}[Date - Entrez]'
        try:
            total = esearch(term_all)
            time.sleep(0.4)
            recent = esearch(term_recent)
            time.sleep(0.4)
        except Exception as e:
            print(f"{name:<48}{pm:<42}{'错误':>10}  {e}")
            bad.append((name, pm, str(e)))
            continue

        flag = "" if total > 0 else "  <-- 搜不到！"
        print(f"{name:<48}{pm:<42}{total:>10}{recent:>8}{flag}")
        recent_total += recent
        if total > 0:
            ok.append((name, pm))
        else:
            bad.append((name, pm, "PubMed 查无此刊名"))

    print("=" * 78)
    print(f"能搜到: {len(ok)} / {len(JOURNALS)}    最近 {days} 天新论文合计: {recent_total} 篇")
    if bad:
        print("\n需要处理的期刊：")
        for b in bad:
            print("  -", b)


if __name__ == "__main__":
    import sys
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    main(d)
