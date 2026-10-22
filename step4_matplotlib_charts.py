# -*- coding: utf-8 -*-
"""
步骤4 · matplotlib 版可视化（4 张图）
数据：data/clean/成都大数据岗位_清洗后.csv  (n=373)
产出：docs/figures/ 下 4 张 PNG
说明：纯教学脚本，逐行中文注释，学生可改、可讲、可面试。
"""
import os
import csv
import statistics
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")  # 无界面环境也能存图
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

# ---------- 0. 中文显示设置（面试/作业都要中文标签） ----------
# Windows 常见中文字体：SimHei(黑体)、Microsoft YaHei(微软雅黑)。
# 自动探测，找不到就列出系统可用字体，避免乱码。
def setup_cn_font():
    for name in ["SimHei", "Microsoft YaHei", "SimSun"]:
        try:
            fm.findfont(name, fallback_to_default=False)
            plt.rcParams["font.sans-serif"] = [name]
            return name
        except Exception:
            continue
    # 兜底：列出可用字体供排错
    print("未找到常见中文字体，系统可用字体前5：",
          [f.name for f in fm.fontManager.ttflist][:5])
    return None

CNF = setup_cn_font()
plt.rcParams["axes.unicode_minus"] = False   # 修复负号显示为方块的问题
plt.rcParams["figure.dpi"] = 130            # 导出清晰度，适合放网页/简历

# ---------- 1. 读取清洗后的 CSV（零依赖 csv 模块，稳定可读） ----------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "clean", "成都大数据岗位_清洗后.csv")
OUTDIR = os.path.join(ROOT, "docs", "figures")
os.makedirs(OUTDIR, exist_ok=True)

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig", newline="")))

def num(x):
    """把薪资/经验文本转成数字；空或异常返回 None。"""
    try:
        x = str(x).strip().replace(",", "")
        return float(x) if x else None
    except Exception:
        return None

# ---------- 2. 预聚合（EDA 的核心：先算数，再画图） ----------
# 图1：学历 × 薪资中位
edu_order = ["大专", "本科", "硕士", "学历不限"]
sal_by_edu = defaultdict(list)
for r in rows:
    v = num(r["月薪中位_元"])
    if v:
        sal_by_edu[r["学历要求"]].append(v)
edu_med = {e: statistics.median(sal_by_edu[e]) for e in edu_order if sal_by_edu.get(e)}

# 图2：可达性分层占比
reach = Counter(r["可达性"] for r in rows)

# 图3：岗位族招聘量
fam = Counter(r["岗位族"] for r in rows)

# 图4：薪资分布（整体直方图用中位薪资）
sal_all = [num(r["月薪中位_元"]) for r in rows if num(r["月薪中位_元"])]
SAL_MED = statistics.median(sal_all)
SAL_MEAN = statistics.mean(sal_all)

# 配色（统一观感）
C_MAIN, C_SUB, C_ACC = "#2563eb", "#94a3b8", "#f59e0b"

# ====================== 图1：学历 × 薪资中位（条形图） ======================
fig, ax = plt.subplots(figsize=(7, 4.2))
xs = list(edu_med.keys())
ys = [edu_med[k] for k in xs]
bars = ax.bar(xs, ys, color=[C_MAIN, C_MAIN, C_MAIN, C_ACC])
ax.set_title("不同学历要求的薪资中位数对比", fontsize=13, weight="bold")
ax.set_ylabel("月薪中位数（元）")
ax.set_xlabel("学历要求")
for b, y in zip(bars, ys):
    ax.text(b.get_x() + b.get_width()/2, y + 300, f"{int(y):,}",
            ha="center", fontsize=10, weight="bold")
ax.axhline(SAL_MED, color=C_SUB, ls="--", lw=1)
ax.text(0, SAL_MED + 300, f"整体中位 {int(SAL_MED):,}", color=C_SUB, fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(OUTDIR, "fig1_edu_salary.png"))
plt.close(fig)

# ====================== 图2：可达性分层（环形图） ======================
fig, ax = plt.subplots(figsize=(5.4, 5))
order = ["L1", "L2", "L3"]
vals = [reach.get(k, 0) for k in order]
colors = ["#16a34a", "#2563eb", "#cbd5e1"]
w, _, at = ax.pie(vals, labels=order, colors=colors, autopct=lambda p: f"{p:.1f}%",
                  startangle=90, pctdistance=0.78,
                  wedgeprops=dict(width=0.42, edgecolor="white"))
ax.set_title("专科生可达性分层（L1/L2/L3）", fontsize=13, weight="bold")
# 圆心注释：可投面合计
l12 = reach.get("L1", 0) + reach.get("L2", 0)
ax.text(0, 0, f"可投面\n{l12}/{len(rows)}\n({l12*100//len(rows)}%)",
        ha="center", va="center", fontsize=12, weight="bold")
ax.axis("equal")
fig.tight_layout()
fig.savefig(os.path.join(OUTDIR, "fig2_reachability.png"))
plt.close(fig)

# ====================== 图3：岗位族招聘量（水平条形图） ======================
fig, ax = plt.subplots(figsize=(7.5, 5))
items = fam.most_common()
labels = [k for k, _ in items][::-1]
counts = [v for _, v in items][::-1]
bars = ax.barh(labels, counts, color=C_MAIN)
ax.set_title("各岗位族招聘需求量", fontsize=13, weight="bold")
ax.set_xlabel("岗位数")
for b, c in zip(bars, counts):
    ax.text(c + 1, b.get_y() + b.get_height()/2, str(c), va="center", fontsize=9)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(OUTDIR, "fig3_job_family.png"))
plt.close(fig)

# ====================== 图4：薪资分布（直方图 + 中位/均值线） ======================
fig, ax = plt.subplots(figsize=(7.5, 4.2))
ax.hist(sal_all, bins=20, color=C_MAIN, alpha=0.85, edgecolor="white")
ax.axvline(SAL_MED, color=C_ACC, ls="--", lw=2, label=f"中位数 {int(SAL_MED):,}")
ax.axvline(SAL_MEAN, color="#dc2626", ls=":", lw=2, label=f"均值 {int(SAL_MEAN):,}")
ax.set_title("月薪中位数分布（右偏）", fontsize=13, weight="bold")
ax.set_xlabel("月薪中位数（元）")
ax.set_ylabel("岗位数")
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(OUTDIR, "fig4_salary_dist.png"))
plt.close(fig)

print("字体:", CNF)
print("图1 学历中位:", {k: int(v) for k, v in edu_med.items()})
print("图2 可达性:", dict(reach), "可投面 L1+L2 =", l12)
print("图3 岗位族Top3:", items[:3])
print("图4 中位/均值:", int(SAL_MED), int(SAL_MEAN))
print("PNG 已保存到:", OUTDIR)
