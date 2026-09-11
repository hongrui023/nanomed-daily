# -*- coding: utf-8 -*-
"""
第 1 阶段 · 连通性测试
用途：在 Gitee Go 的构建机上跑一次，看看能不能连上 4 个免费论文数据源。
只测网络连通 + 能否取到数据，不做任何抓取任务。耗时约 20 秒。
"""
import json
import socket
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "nanomed-tracker/0.1"}
TIMEOUT = 25


def probe(name, url, parser):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8", "ignore")
        ms = int((time.time() - t0) * 1000)
        info = parser(body)
        print(f"  [OK]   {name:<14} 耗时 {ms:>5} ms   {info}")
        return True
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        print(f"  [失败] {name:<14} 耗时 {ms:>5} ms   {type(e).__name__}: {e}")
        return False


def p_pubmed(b):
    d = json.loads(b)
    return f'命中 {d["esearchresult"]["count"]} 篇'


def p_eupmc(b):
    d = json.loads(b)
    return f'命中 {d.get("hitCount", "?")} 篇'


def p_openalex(b):
    d = json.loads(b)
    return f'命中 {d.get("meta", {}).get("count", "?")} 条'


def p_crossref(b):
    d = json.loads(b)
    return f'命中 {d.get("message", {}).get("total-results", "?")} 条'


def main():
    print("=" * 66)
    print("连通性测试开始（4 个免费数据源）")
    print("=" * 66)

    # 先做一次纯 DNS/连接测试，看网络本身通不通
    for host in ("eutils.ncbi.nlm.nih.gov", "www.ebi.ac.uk", "api.openalex.org",
                 "api.crossref.org", "gitee.com"):
        t0 = time.time()
        try:
            socket.setdefaulttimeout(8)
            socket.create_connection((host, 443), timeout=8).close()
            print(f"  [OK]   域名可达 {host:<32} {int((time.time()-t0)*1000):>5} ms")
        except Exception as e:
            print(f"  [失败] 域名不可达 {host:<32} {type(e).__name__}")

    print("-" * 66)

    results = []
    results.append(probe(
        "PubMed",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        "?db=pubmed&term=%22ACS+Nano%22[Journal]&retmax=1&retmode=json",
        p_pubmed))
    results.append(probe(
        "Europe PMC",
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        "?query=JOURNAL:%22ACS%20Nano%22&format=json&pageSize=1",
        p_eupmc))
    results.append(probe(
        "OpenAlex",
        "https://api.openalex.org/works?filter=title.search:nanoparticle&per-page=1",
        p_openalex))
    results.append(probe(
        "Crossref",
        "https://api.crossref.org/works?query=nanoparticle&rows=1",
        p_crossref))

    print("=" * 66)
    ok = sum(results)
    print(f"结果：{ok} / {len(results)} 个数据源可用")
    if results[0]:
        print(">>> 结论：PubMed 可用，主方案直接成立。")
    elif ok > 0:
        print(">>> 结论：PubMed 不通，但有备用源可用，需要改走兜底源。")
    else:
        print(">>> 结论：全部不通。这台机器无法访问国外数据源，必须换方案。")
    print("=" * 66)


if __name__ == "__main__":
    main()
