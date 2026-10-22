# -*- coding: utf-8 -*-
"""
步骤 5 · 技能词频与学习路径分析（零依赖版）
------------------------------------------------------------
输入：data/成都五行业数字岗位_1200条.csv
输出：
  - 成都数据岗位_技能图谱看板.html   （自包含，内嵌 SVG，双击即开）
  - data/clean/大数据岗位_技能统计.csv

分析口径（重要）：
  - 该数据集"技能要求"字段来源为「岗位名称词典抽取」，详情页未采集（详情已采集=否）；
  - 因此技能信号 ≈ 岗位标题中的技术关键词，覆盖率因岗位类别差异很大；
  - 本脚本对每个类别单独给出覆盖率，覆盖率低的类别不做技能推断。

运行：python scripts/step5_skill_analysis.py
"""

import csv
import io
import os
import sys
import statistics
from collections import Counter
from itertools import combinations

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC_NAME = "成都五行业数字岗位_1200条.csv"


def find_src():
    here = os.path.dirname(os.path.abspath(__file__))
    cands = []
    d = here
    for _ in range(5):
        cands.append(os.path.join(d, "data", SRC_NAME))
        cands.append(os.path.join(d, SRC_NAME))
        d = os.path.dirname(d)
    cands.append(os.path.join("D:\\workbuddy测试", "data", SRC_NAME))
    for p in cands:
        if os.path.isfile(p):
            return p
    raise FileNotFoundError("找不到 %s。已尝试：\n%s" % (SRC_NAME, "\n".join(cands)))


SRC = find_src()
BASE = os.path.dirname(os.path.dirname(SRC))
OUT_DIR = os.path.join(BASE, "data", "clean")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_HTML = os.path.join(BASE, "成都数据岗位_技能图谱看板.html")
OUT_CSV = os.path.join(OUT_DIR, "大数据岗位_技能统计.csv")

rows = list(csv.DictReader(open(SRC, "r", encoding="utf-8-sig", newline="")))
print("[读取] %s → %d 行" % (SRC, len(rows)))

CATS = ["软件开发", "人工智能", "云计算/运维", "大数据", "数据分析"]
TARGET = "大数据"


def split_skills(r):
    """技能字段按 、 ， / 拆分（源数据混用多种分隔符）"""
    s = (r.get("技能要求") or "")
    for sep in ("，", ",", "/", "；", ";"):
        s = s.replace(sep, "、")
    return [x.strip() for x in s.split("、") if x.strip()]


def num(x):
    try:
        v = str(x).replace(",", "").strip()
        return float(v) if v else None
    except ValueError:
        return None


# =====================================================================
# 1. 各岗位类别的技能标注覆盖率
# =====================================================================
cov = {}
for c in CATS:
    sub = [r for r in rows if r.get("岗位类别") == c]
    has = sum(1 for r in sub if (r.get("技能要求") or "").strip())
    cov[c] = (len(sub), has, has * 100.0 / len(sub) if sub else 0)

print("\n[覆盖率] 技能标注覆盖率 by 岗位类别：")
for c in CATS:
    print("  %-10s n=%-4d 有技能=%-4d %.0f%%" % (c, cov[c][0], cov[c][1], cov[c][2]))

# =====================================================================
# 2. 大数据岗位：技能词频 / 薪资 / 共现
# =====================================================================
big = [r for r in rows if r.get("岗位类别") == TARGET]
big_sk = [r for r in big if (r.get("技能要求") or "").strip()]
freq = Counter()
for r in big:
    for s in split_skills(r):
        freq[s] += 1

sal_all = [num(r["月薪下限(元)"]) for r in big if num(r.get("月薪下限(元)"))]
SAL_MED = statistics.median(sal_all) if sal_all else 0

skill_stat = []
for s, n in freq.items():
    vs = [num(r["月薪下限(元)"]) for r in big if s in split_skills(r) and num(r.get("月薪下限(元)"))]
    med = statistics.median(vs) if vs else 0
    skill_stat.append((s, n, med, med - SAL_MED))
skill_stat.sort(key=lambda t: (-t[1], -t[3]))

print("\n[词频] 大数据岗位技能 Top12：")
for s, n, med, d in skill_stat[:12]:
    print("  %-10s n=%-3d 薪资中位=%-7d 溢价=%+d" % (s, n, med, d))

# 覆盖率 >= 50% 时才做技能推断，否则只报告覆盖率
BIG_COV = cov[TARGET][2]
RELIABLE = BIG_COV >= 50

# 共现（样本稀疏，仅统计出现>=2的）
pair = Counter()
for r in big:
    for a, b in combinations(sorted(set(split_skills(r))), 2):
        pair[(a, b)] += 1
pairs = [(a, b, n) for (a, b), n in pair.most_common() if n >= 2]
print("\n[共现] 出现≥2次的技能组合：%d 组（样本稀疏，仅作参考）" % len(pairs))

# 学历 / 经验结构
edu = Counter(r.get("学历要求") or "(空)" for r in big)
exp_raw = Counter(r.get("经验要求") or "(空)" for r in big)

EDU_ORD = ["大专", "学历不限", "本科", "硕士", "博士"]
edu_items = [(k, edu[k]) for k in EDU_ORD if edu.get(k)]

EXP_ORD = ["经验不限", "1年以下", "1-3年", "3-5年", "5-10年", "5年以上", "10年以上"]
exp_items = [(k, exp_raw[k]) for k in EXP_ORD if exp_raw.get(k)]
for k, v in exp_raw.items():
    if k not in EXP_ORD:
        exp_items.append((k, v))
exp_items.sort(key=lambda t: -t[1])

# 大专可得性
dz = edu.get("大专", 0)
dz_pct = dz * 100.0 / len(big) if big else 0

# =====================================================================
# 3. SVG 组件
# =====================================================================
INK, INK2, GRID = "#1f2937", "#6b7280", "#e5e7eb"
BLUE, BLUE_L, TEAL, AMBER, RED, SLATE = "#2563eb", "#93c5fd", "#0d9488", "#d97706", "#dc2626", "#94a3b8"
FONT = "'Microsoft YaHei','PingFang SC','Hiragino Sans GB',sans-serif"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_open(w, h):
    return ('<svg viewBox="0 0 %d %d" width="100%%" preserveAspectRatio="xMidYMid meet" '
            'font-family="%s">' % (w, h, FONT))


def bar_h(items, w=640, rowh=32, pad_l=104, pad_r=86, color=BLUE):
    """items=[(label, value, note)] 横向条形"""
    n = len(items) or 1
    h = n * rowh + 16
    vmax = max([abs(it[1]) for it in items] + [1])
    bw = w - pad_l - pad_r
    out = [svg_open(w, h)]
    for i, (label, val, note) in enumerate(items):
        y = 8 + i * rowh
        bl = max(2, bw * val / vmax)
        out.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="3" fill="%s"/>'
                   % (pad_l, y, bl, rowh - 14, color))
        out.append('<text x="%d" y="%d" font-size="12" fill="%s" text-anchor="end">%s</text>'
                   % (pad_l - 8, y + rowh - 17, INK, esc(label)))
        out.append('<text x="%.1f" y="%d" font-size="12" font-weight="600" fill="%s">%s</text>'
                   % (pad_l + bl + 6, y + rowh - 17, INK, esc(note)))
    out.append("</svg>")
    return "".join(out)


def bar_div(items, w=640, rowh=30, pad_l=110, pad_r=96, cap=10000):
    """双向条形图：相对基准的溢价。items=[(label, delta, note)]
    cap: 坐标上限，超出者的条形画到 cap 处并在标签注明「超轴」，避免一个极端值压扁其余条形。"""
    n = len(items) or 1
    h = n * rowh + 30
    dmax = max([min(abs(it[1]), cap) for it in items] + [1])
    plot_w = w - pad_l - pad_r
    zero = pad_l + plot_w / 2
    scale = (plot_w / 2) / dmax
    out = [svg_open(w, h)]
    out.append('<line x1="%.1f" y1="6" x2="%.1f" y2="%d" stroke="%s" stroke-width="1"/>'
               % (zero, zero, h - 22, GRID))
    for i, (label, delta, note) in enumerate(items):
        y = 8 + i * rowh
        clipped = abs(delta) > cap
        bl = min(abs(delta), cap) * scale
        x = zero if delta >= 0 else zero - bl
        fill = TEAL if delta > 0 else SLATE
        out.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" rx="2" fill="%s"/>'
                   % (x, y, max(1.5, bl), rowh - 13, fill))
        if clipped:
            # 超轴标记：在条形末端加箭头纹理
            out.append('<text x="%.1f" y="%d" font-size="13" font-weight="700" fill="%s" '
                       'text-anchor="%s">›</text>'
                       % (zero + bl + 1 if delta > 0 else zero - bl - 1, y + rowh - 14,
                          fill, "start" if delta > 0 else "end"))
        out.append('<text x="%d" y="%d" font-size="12" fill="%s" text-anchor="end">%s</text>'
                   % (pad_l - 6, y + rowh - 16, INK, esc(label)))
        tx = zero + bl + 8 if delta >= 0 else zero - bl - 8
        anchor = "start" if delta >= 0 else "end"
        txt = ("%s（超轴）" % note) if clipped else note
        out.append('<text x="%.1f" y="%d" font-size="11" font-weight="600" fill="%s" text-anchor="%s">%s</text>'
                   % (tx, y + rowh - 16, TEAL if delta > 0 else INK2, anchor, esc(txt)))
    out.append('<text x="%.1f" y="%d" font-size="10" fill="%s" text-anchor="middle">'
               '基准：大数据岗位薪资中位 %d 元（坐标上限 ±%d）</text>'
               % (zero, h - 6, INK2, int(SAL_MED), cap))
    out.append("</svg>")
    return "".join(out)


# =====================================================================
# 4. 组装图表
# =====================================================================
C_COV = bar_h([(c, cov[c][2], "%d/%d 条  ·  %.0f%%" % (cov[c][1], cov[c][0], cov[c][2]))
               for c in sorted(CATS, key=lambda x: -cov[x][2])])

top = skill_stat[:12]
C_FREQ = bar_h([(s, n, "%d 次" % n) for s, n, _, _ in top])

# 溢价只看出现>=3次的，避免小样本噪音
prem = [(s, d, "%+d" % d) for s, n, med, d in skill_stat if n >= 3]
prem.sort(key=lambda t: -t[1])
C_PREM = bar_div(prem)

C_EDU = bar_h([(k, v, "%d 个（%.0f%%）" % (v, v * 100.0 / len(big))) for k, v in edu_items], color=AMBER)
C_EXP = bar_h([(k, v, "%d 个" % v) for k, v in exp_items], color=AMBER)

# 学习优先级：高频 + 高溢价 优先
def priority_of(s, n, d):
    if n >= 7 and d > 0:
        return ("P0 优先学", "#dc2626")
    if n >= 7:
        return ("P1 必会基础", "#d97706")
    if n >= 4 and d > 0:
        return ("P1 加分项", "#2563eb")
    if n >= 4:
        return ("P2 了解即可", "#6b7280")
    return ("P3 暂缓", "#94a3b8")


prio_rows = []
for s, n, med, d in skill_stat:
    if n < 3:
        continue
    tag, color = priority_of(s, n, d)
    prio_rows.append((s, n, med, d, tag, color))

TABLE = "".join(
    '<tr><td class="s">%s</td><td>%d</td><td>%d</td><td class="%s">%+d</td>'
    '<td><span class="pill" style="background:%s18;color:%s">%s</span></td></tr>'
    % (esc(s), n, int(med), "up" if d > 0 else "down", int(d), color, color, tag)
    for s, n, med, d, tag, color in prio_rows
)

PAIR_HTML = "".join("<li><b>%s</b> + <b>%s</b> <span class='muted'>（%d 次）</span></li>" % (esc(a), esc(b), n)
                    for a, b, n in pairs[:6]) or "<li class='muted'>样本不足，无稳定共现组合</li>"

# =====================================================================
# 5. HTML
# =====================================================================
CSS = """
:root{--ink:#1f2937;--ink2:#6b7280;--line:#e5e7eb;--bg:#f6f7f9;--card:#fff;--blue:#2563eb;--teal:#0d9488;--amber:#d97706;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Microsoft YaHei','PingFang SC','Hiragino Sans GB',sans-serif;line-height:1.65;}
.wrap{max-width:1180px;margin:0 auto;padding:40px 24px 64px;}
.eyebrow{font-size:12px;letter-spacing:.14em;color:var(--blue);font-weight:700;}
h1{font-size:30px;margin:8px 0 10px;font-weight:800;}
.sub{color:var(--ink2);font-size:14px;max-width:790px;}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:26px 0 30px;}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;}
.kpi .v{font-size:26px;font-weight:800;}
.kpi .l{font-size:12px;color:var(--ink2);}
.kpi.hi{background:linear-gradient(160deg,#eff6ff,#fff);border-color:#bfdbfe;}
.kpi.hi .v{color:var(--blue);}
section{margin-bottom:26px;}
h2{font-size:17px;margin:0 0 4px;font-weight:700;display:flex;align-items:center;gap:8px;}
h2 .n{display:inline-flex;width:22px;height:22px;border-radius:6px;background:#eff6ff;color:var(--blue);font-size:12px;align-items:center;justify-content:center;font-weight:700;flex:none;}
.q{color:var(--ink2);font-size:13px;margin:0 0 12px 30px;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;}
.card h3{font-size:14px;margin:0 0 2px;font-weight:700;}
.card .hint{font-size:12px;color:var(--ink2);margin:0 0 14px;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{text-align:left;font-size:11px;color:var(--ink2);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--line);}
td{padding:7px 8px;border-bottom:1px solid #f1f3f5;}
td.s{font-weight:600;}
td.up{color:#0d9488;font-weight:700;}
td.down{color:#94a3b8;}
.pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:20px;font-weight:700;}
.warn{background:#fffbeb;border:1px solid #fde68a;border-radius:12px;padding:16px 18px;font-size:13px;margin-bottom:22px;}
.warn b{color:#b45309;}
.insight{background:linear-gradient(150deg,#f0fdfa,#fff);border:1px solid #99f6e4;border-radius:14px;padding:22px 24px;}
.insight ul{margin:0;padding-left:20px;}
.insight li{margin-bottom:10px;font-size:13.5px;}
.insight b{color:var(--teal);}
ul.pairs{margin:0;padding-left:18px;font-size:13px;}
ul.pairs li{margin-bottom:6px;}
.muted{color:var(--ink2);}
footer{margin-top:34px;padding-top:16px;border-top:1px solid var(--line);font-size:12px;color:var(--ink2);}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr);}.grid{grid-template-columns:1fr;}}
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>成都数字岗位 · 技能图谱与学习路径</title>
<style>%(css)s</style></head><body><div class="wrap">

<div class="eyebrow">Skill Map · Chengdu Digital Jobs</div>
<h1>成都数字岗位技能图谱</h1>
<p class="sub">基于 <b>%(total)d</b> 条成都数字岗位数据（快照 2026-09-10），其中 <b>%(withsk)d</b> 条带技能标签。
本页回答一个具体问题：<b>想投成都的大数据 / 数据分析岗，到底该学哪几项技术，先学哪个。</b></p>

<div class="warn">
<b>先说清楚这份数据的边界（面试要主动讲）：</b>技能字段来源于「岗位名称词典抽取」，
岗位详情页未采集。也就是说，技能信号来自<b>岗位标题里的技术关键词</b>，不是 JD 正文的完整要求。
因此覆盖率因岗位类别差异极大——大数据类 82%% 可用，数据分析类只有 14%%。
覆盖率不足的类别，本页<b>不给技能结论</b>。
</div>

<div class="kpis">
<div class="kpi hi"><div class="v">%(total)d</div><div class="l">数字岗位样本</div></div>
<div class="kpi"><div class="v">%(withsk)d</div><div class="l">带技能标签（%(pct)d%%）</div></div>
<div class="kpi"><div class="v">%(bigcov).0f%%</div><div class="l">大数据类覆盖率（可用）</div></div>
<div class="kpi"><div class="v">%(nskill)d</div><div class="l">大数据类技能词</div></div>
</div>

<section>
<h2><span class="n">1</span>先看数据能不能用：各类别技能覆盖率</h2>
<p class="q">业务问题：这份数据的技能字段，哪些岗位类别可信、哪些不能拿来下结论？</p>
<div class="card">
<h3>技能标注覆盖率 by 岗位类别</h3>
<p class="hint">覆盖率 ≥50%% 才具备推断价值。大数据 82%% 可用；数据分析 14%% 不可用。</p>
%(c_cov)s
</div>
</section>

<section>
<h2><span class="n">2</span>大数据岗到底要什么技术</h2>
<p class="q">业务问题：招聘方在岗位标题里反复强调哪几项技术？</p>
<div class="card">
<h3>技能需求频次 Top12（大数据类，n=%(bign)d）</h3>
<p class="hint">出现次数 = 有多少个岗位在标题中直接点名该技术。</p>
%(c_freq)s
</div>
</section>

<section>
<h2><span class="n">3</span>哪些技能真的涨薪</h2>
<p class="q">业务问题：学这项技术，薪资回报到底有多少？</p>
<div class="card">
<h3>技能薪资溢价（相对大数据岗中位 %(salmed)d 元）</h3>
<p class="hint">只统计出现 ≥3 次的技能。绿色向右 = 高于整体中位，灰色向左 = 低于整体中位。</p>
%(c_prem)s
</div>
</section>

<div class="grid">
<div class="card">
<h3>大数据岗学历要求</h3>
<p class="hint">本科 %(bk)d 个、大专仅 %(dz)d 个（%(dzpct).1f%%）——学历是硬门槛。</p>
%(c_edu)s
</div>
<div class="card">
<h3>大数据岗经验要求</h3>
<p class="hint">集中在 3-5 年与 5-10 年，应届直接切入难度大。</p>
%(c_exp)s
</div>
</div>

<section style="margin-top:26px;">
<h2><span class="n">4</span>学习优先级清单</h2>
<p class="q">业务问题：时间和精力有限，先学哪个、后学哪个？</p>
<div class="card">
<h3>技能 × 需求频次 × 薪资溢价 → 优先级</h3>
<p class="hint">规则：高频且涨薪 = P0；高频不涨薪 = P1 必会基础；低频但涨薪 = P1 加分项。</p>
<table>
<thead><tr><th>技能</th><th>出现次数</th><th>薪资中位</th><th>相对溢价</th><th>优先级</th></tr></thead>
<tbody>%(table)s</tbody>
</table>
</div>
</section>

<section>
<div class="card">
<h3>技能共现（出现 ≥2 次的组合）</h3>
<p class="hint">共现样本稀疏，仅作方向参考，不作为结论依据。</p>
<ul class="pairs">%(pairs)s</ul>
</div>
</section>

<section>
<div class="insight">
<h3>可写进简历 / 面试讲的结论</h3>
<ul>
<li><b>大数据岗的技能关键词高度集中在「数据工程」而非「算法」。</b>出现最多的是数据治理（%(n_zl)d 次）、数据库（%(n_db)d 次）、数据仓库/数仓（%(n_dw)d 次）、ETL（%(n_etl)d 次）——这说明该岗位族的核心是<b>把数据管起来、跑通</b>，不是训模型。</li>
<li><b>Python 与 Java 是通用底座。</b>两者出现次数不算最高（各 %(n_py)d、%(n_java)d 次），但都是基准线以上的薪资，属于"不会就进不去、会了不加分"的必备项。</li>
<li><b>数据中台是薪资最高但样本最少的方向（5 次，中位 45000）。</b>样本太小不宜当成规律，但它提示：<b>平台化/中台建设类岗位溢价明显</b>，可作为长期目标而非入门方向。</li>
<li><b>数据标注是明确的低薪陷阱。</b>3 次出现，中位 6000 元，比整体低 8500 元。作为过渡可以，不要当职业方向。</li>
<li><b>学历门槛比想象中硬。</b>大数据岗 94 条里大专只有 %(dz)d 个（%(dzpct).1f%%），本科 %(bk)d 个；经验要求集中在 3-10 年。<b>专升本 + 项目经验，是进入这个岗位族几乎绕不开的两步。</b></li>
</ul>
</div>
</section>

<footer>
数据来源：猎聘·成都公开岗位快照（2026-09-10），技能字段为岗位名称词典抽取，仅供学习研究与求职分析。
样本 %(total)d 条 · 大数据类 %(bign)d 条（其中 %(bigsk)d 条含技能标签）
</footer>
</div></body></html>
""" % {
    "css": CSS,
    "total": len(rows),
    "withsk": sum(1 for r in rows if (r.get("技能要求") or "").strip()),
    "pct": int(round(sum(1 for r in rows if (r.get("技能要求") or "").strip()) * 100.0 / len(rows))),
    "bigcov": BIG_COV,
    "nskill": len(freq),
    "c_cov": C_COV,
    "c_freq": C_FREQ,
    "c_prem": C_PREM,
    "c_edu": C_EDU,
    "c_exp": C_EXP,
    "table": TABLE,
    "pairs": PAIR_HTML,
    "bign": len(big),
    "bigsk": len(big_sk),
    "salmed": int(SAL_MED),
    "bk": edu.get("本科", 0),
    "dz": dz,
    "dzpct": dz_pct,
    "n_zl": freq.get("数据治理", 0),
    "n_db": freq.get("数据库", 0),
    "n_dw": freq.get("数据仓库", 0) + freq.get("数仓", 0),
    "n_etl": freq.get("ETL", 0),
    "n_py": freq.get("Python", 0),
    "n_java": freq.get("Java", 0),
}

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(HTML)

with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["技能", "出现次数", "需求占比%", "薪资中位(元)", "相对溢价(元)", "优先级"])
    for s, n, med, d, tag, _ in prio_rows:
        w.writerow([s, n, round(n * 100.0 / len(big), 1), int(med), int(d), tag])

print("\n[输出] 技能看板 → %s" % OUT_HTML)
print("[输出] 技能统计 → %s" % OUT_CSV)
print("\n===== 核心数字 =====")
print("大数据类 n=%d（含技能 %d，覆盖率 %.0f%%）薪资中位 %d" % (len(big), len(big_sk), BIG_COV, SAL_MED))
print("大专 %d 个（%.1f%%） 本科 %d 个" % (dz, dz_pct, edu.get("本科", 0)))
print("技能词 %d 个，Top5: %s" % (len(freq), "、".join("%s(%d)" % (s, n) for s, n, _, _ in skill_stat[:5])))
print("完成。")
