#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════
# 统计「所有仓库」的代码总量，写进仓库根目录的 code-stats.json
#
#   干什么：遍历本账号下的所有仓库 → 调 GitHub 的 /languages 接口
#           （GitHub 自己按 linguist 统计好的各语言字节数）→ 全部加总
#           → 落盘成 code-stats.json
#   为什么：主页那枚「代码总量」徽章读的就是这个 json，所以数字永远是最新的；
#           而且**不用 clone 任何仓库**，秒级完成（比 tokei / cloc 那套省事）
#   注意 1：**必须排除 fork**（r["fork"]）—— 那是别人的代码，不该算在自己头上
#   注意 2：口径与 shields 的 languages/code-size 一致（只认「被识别成语言」的
#           文件）；如果把 json / 配置 / 文档也算进去，数字会偏大
#   注意 3：raw.githubusercontent.com 有约 5 分钟缓存，徽章显示滞后属正常
#   创建：2026-10-07（小鲸）
# ════════════════════════════════════════════════════════════════════
import datetime
import json
import os
import sys
import urllib.request

OWNER = os.environ.get("OWNER") or "maomao1OvO1"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def api(url):
    """带认证地 GET 一个 GitHub API（本地跑没 token 也能用，只是限额低）"""
    headers = {"User-Agent": "code-stats", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def human(n):
    """把字节数变好看：9493842 → 9.05 MiB"""
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def main():
    repos, page = [], 1
    while True:  # 分页把账号下的仓库全部拉下来
        batch = api(
            f"https://api.github.com/users/{OWNER}/repos"
            f"?per_page=100&page={page}&type=owner"
        )
        if not batch:
            break
        repos += batch
        page += 1

    total, langs, per_repo, skipped = 0, {}, [], []
    for r in repos:
        if r.get("fork"):  # 注意 1：fork 是别人的代码，跳过
            skipped.append(r["name"])
            continue
        try:
            d = api(r["languages_url"])  # 该仓库各语言的字节数
        except Exception as e:  # 单个仓库失败不影响整体
            print(f"  跳过 {r['name']}：{e}", file=sys.stderr)
            continue
        s = sum(d.values())
        total += s
        per_repo.append({"name": r["name"], "bytes": s, "human": human(s)})
        for k, v in d.items():
            langs[k] = langs.get(k, 0) + v

    out = {
        "bytes": total,                                          # 机器读这个
        "human": human(total),                                   # 徽章显示这个
        "repos": sorted(per_repo, key=lambda x: -x["bytes"]),     # 各仓库明细
        "languages": dict(sorted(langs.items(), key=lambda x: -x[1])),
        "repo_count": len(per_repo),
        "excluded_forks": skipped,
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    with open("code-stats.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"✅ 合计 {out['human']}（{total} 字节）· 统计 {out['repo_count']} 个仓库"
          f" · 排除 fork {len(skipped)} 个")


if __name__ == "__main__":
    main()
