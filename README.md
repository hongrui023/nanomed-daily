# 纳米医学 · 今日速览

一个完全免费的论文追踪工具：从 46 本纳米医学/药物递送期刊抓最新论文，
用免费 AI 写成中文大白话，生成手机网页。

- 论文来源：PubMed（免费公开接口，无需注册）
- AI 摘要：智谱 GLM-4-Flash（官方免费模型）
- 运行：Gitee Go 流水线（免费额度）
- 展示：Gitee Pages（免费静态托管）

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `journals.txt` | 期刊列表，一行一本。格式 `显示名 \| PubMed写法` |
| `keywords.txt` | 关键词，一行一个，中英文都行 |
| `gate.txt` | 门槛词：至少命中一个才认为是医学相关（拦掉材料学噪音） |
| `config.txt` | 抓取天数、最多总结篇数 |
| `scripts/fetch_papers.py` | 抓 PubMed + 关键词/门槛筛选 |
| `scripts/summarize.py` | 调 AI 写大白话摘要（带缓存，不重复花钱） |
| `scripts/build_site.py` | 生成 index.html |
| `data/*.json` | 每天的结果数据 |
| `cache/ai_cache.json` | AI 摘要缓存，同一篇论文只算一次 |
| `index.html` | 手机网页（页面本体） |
| `trigger.txt` | 写入一次即触发流水线运行 |

## 手动运行

```bash
export ZHIPU_KEY=你的智谱密钥
python3 scripts/fetch_papers.py
python3 scripts/summarize.py
python3 scripts/build_site.py
```

## 安全说明

仓库是**公开**的（Gitee Pages 免费版要求），但里面**没有任何密钥**。
智谱密钥存在 Gitee Go 的「全局参数」里，令牌存在你自己手机浏览器里。
