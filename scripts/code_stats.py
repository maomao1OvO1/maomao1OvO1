#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════
# 统计「所有仓库」的代码总量 → 写 code-stats.json + 渲染一张总览图
#
#   干什么：① 遍历本账号下的所有仓库 → 调 GitHub 的 /languages 接口
#             （GitHub 自己按 linguist 统计好的各语言字节数）→ 全部加总
#             → 落盘成 code-stats.json（机器读）
#           ② 顺手把同一份数据画成一张 SVG 总览图（人看）→ code-stats.svg
#              —— 这样主页上「既有数字、又有图形」，一眼能看出大小差距
#   为什么：主页那枚「代码总量」徽章读 json，那张总览图读 svg，数字永远最新；
#           而且**不用 clone 任何仓库**，秒级完成（比 tokei / cloc 那套省事）
#   注意 1：**必须排除 fork**（r["fork"]）—— 那是别人的代码，不该算在自己头上
#   注意 2：口径与 shields 的 languages/code-size 一致（只认「被识别成语言」的
#           文件）；如果把 json / 配置 / 文档也算进去，数字会偏大
#   注意 3：raw.githubusercontent.com 有约 5 分钟缓存，徽章/图显示滞后属正常
#   创建：2026-10-07（小鲸）
# ════════════════════════════════════════════════════════════════════
import datetime
import json
import os
import sys
import urllib.request

OWNER = os.environ.get("OWNER") or "maomao1OvO1"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

# 配色：跟主页那套「紫 + 绿、鲜艳」的审美保持一致
C_BG = "#2D1B4E"       # 深紫底
C_CARD = "#3B2A5E"     # 卡片底
C_TEXT = "#F5F3FF"     # 主文字
C_DIM = "#C4B5FD"      # 次要文字
C_BAR = ["#9F7AEA", "#68D391", "#FF6EC7", "#4FD1C5", "#FFD93D", "#F6AD55", "#63B3ED", "#FC8181"]


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


def esc(s):
    """SVG 里出现的文本必须转义，否则 & < > 会把标签搞坏"""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_svg(stats):
    """把统计结果画成一张总览图：左边是各仓库条形，右边是语言占比"""
    repos = stats["repos"][:8]                     # 最多画 8 个仓库，太多会太长
    langs = list(stats["languages"].items())[:6]   # 语言最多列 6 种
    top = max((r["bytes"] for r in repos), default=1)

    W = 900
    head_h = 118          # 顶部大数字区
    row_h = 30            # 每个仓库一行
    body_h = len(repos) * row_h + 16
    lang_h = 96           # 底部语言占比区
    H = head_h + body_h + lang_h

    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">')
    # 背景 + 圆角
    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="16" fill="{C_BG}"/>')
    # 顶部：标题 + 大数字 + 副信息
    s.append(f'<text x="28" y="36" fill="{C_DIM}" font-size="15">🐋 毛毛的代码总览</text>')
    s.append(f'<text x="28" y="80" fill="{C_TEXT}" font-size="34" font-weight="bold">{esc(stats["human"])}</text>')
    s.append(f'<text x="28" y="104" fill="{C_DIM}" font-size="13">'
             f'所有仓库代码总量 · 共 {stats["repo_count"]} 个仓库（已排除 fork） · 更新于 {esc(stats["updated"])}</text>')

    # 中部：各仓库条形（条长按最大值等比缩放）
    y = head_h
    name_w = 250
    bar_w = W - 28 - name_w - 130
    for i, r in enumerate(repos):
        ratio = (r["bytes"] / top) if top else 0
        w = max(4, int(bar_w * ratio))             # 至少给 4px，否则小仓库看不见
        color = C_BAR[i % len(C_BAR)]
        s.append(f'<text x="28" y="{y + 19}" fill="{C_TEXT}" font-size="13">{esc(r["name"])}</text>')
        s.append(f'<rect x="{28 + name_w}" y="{y + 6}" width="{bar_w}" height="16" rx="8" fill="{C_CARD}"/>')
        s.append(f'<rect x="{28 + name_w}" y="{y + 6}" width="{w}" height="16" rx="8" fill="{color}"/>')
        s.append(f'<text x="{28 + name_w + bar_w + 12}" y="{y + 19}" fill="{C_DIM}" font-size="12">{esc(r["human"])}</text>')
        y += row_h

    # 底部：语言占比（一条堆叠条 + 图例）
    y = head_h + body_h
    s.append(f'<text x="28" y="{y + 14}" fill="{C_DIM}" font-size="13">语言占比</text>')
    bar_y = y + 24
    total = sum(v for _, v in langs) or 1
    x = 28
    stack_w = W - 56
    for i, (name, v) in enumerate(langs):
        w = max(2, int(stack_w * v / total))
        if i == len(langs) - 1:
            w = max(2, W - 28 - x)                 # 最后一段补齐，避免累计误差留缝
        s.append(f'<rect x="{x}" y="{bar_y}" width="{w}" height="18" rx="6" fill="{C_BAR[i % len(C_BAR)]}"/>')
        x += w
    # 图例（两行排布，避免超出宽度）
    lx, ly = 28, bar_y + 42
    for i, (name, v) in enumerate(langs):
        pct = v / total * 100
        s.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{C_BAR[i % len(C_BAR)]}"/>')
        s.append(f'<text x="{lx + 16}" y="{ly}" fill="{C_DIM}" font-size="12">'
                 f'{esc(name)} {pct:.1f}%</text>')
        lx += 150
        if lx > W - 160:
            lx, ly = 28, ly + 22
    s.append('</svg>')
    return "\n".join(s)


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
    with open("code-stats.svg", "w", encoding="utf-8") as f:
        f.write(render_svg(out))

    print(f"✅ 合计 {out['human']}（{total} 字节）· 统计 {out['repo_count']} 个仓库"
          f" · 排除 fork {len(skipped)} 个 · 已生成 code-stats.json 与 code-stats.svg")


if __name__ == "__main__":
    main()
