# -*- coding: utf-8 -*-
"""
步骤 3 · 数据清洗 + EDA（零依赖备用版 / 纯标准库）
------------------------------------------------------------
用途：当环境里没有 pandas（或装不上）时，用这个版本跑通同样的清洗与统计。
      计算口径与 step3_clean_eda.py 完全一致，结果数字应当对得上。

依赖：只用 Python 自带模块（csv / re / os / sys / statistics / collections）
运行：python scripts/step3_clean_eda_nolib.py
      （放在哪里都能跑：脚本会自动向上/向下查找 data 目录）

输出：
  - data/clean/成都大数据岗位_清洗后.csv
  - data/clean/成都大数据岗位_描述性统计.csv
  - 控制台打印 EDA 结果 + 核对清单

注意：本版不画图（可视化在步骤 4，建议那时再用 pandas/matplotlib）。
"""

import csv
import io
import os
import re
import sys
import statistics
from collections import Counter, OrderedDict, defaultdict

# Windows 控制台中文输出
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SKILL_PH = "（源站详情页触发IP验证码，未获取）"
RAW_NAME = "成都大数据岗位_采集结果.csv"


# =====================================================================
# 0. 自动定位数据文件（避免"脚本挪了位置就找不到数据"的坑）
# =====================================================================
def find_raw():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    # 从脚本目录向上最多 4 级，每级都试 data/ 与同级目录
    d = here
    for _ in range(5):
        candidates.append(os.path.join(d, "data", RAW_NAME))
        candidates.append(os.path.join(d, RAW_NAME))
        d = os.path.dirname(d)
    # 常见固定位置兜底
    candidates.append(os.path.join("D:\\workbuddy测试", "data", RAW_NAME))
    for p in candidates:
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(
        "找不到原始数据文件 %s，请确认它与本脚本在同一项目下。\n已尝试：\n%s"
        % (RAW_NAME, "\n".join(candidates))
    )


RAW = find_raw()
BASE = os.path.dirname(os.path.dirname(RAW))          # …/workbuddy测试
OUT_DIR = os.path.join(BASE, "data", "clean")
os.makedirs(OUT_DIR, exist_ok=True)
CLEAN_CSV = os.path.join(OUT_DIR, "成都大数据岗位_清洗后.csv")
STAT_CSV = os.path.join(OUT_DIR, "成都大数据岗位_描述性统计.csv")


# =====================================================================
# 工具函数
# =====================================================================
def to_num(x):
    """字符串转 float，失败返回 None（对应 pandas 的 NaN）。"""
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def quantile(sorted_vals, q):
    """线性插值分位数，与 numpy/pandas 默认口径一致。"""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def parse_salary(raw):
    """从薪资原文解析区间/单值，返回 (下限, 上限)，单位元。失败 (None, None)。"""
    if not raw:
        return (None, None)
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*k", raw, re.I)  # 12-18k
    if m:
        return float(m.group(1)) * 1000, float(m.group(2)) * 1000
    m = re.search(r"(\d+(?:\.\d+)?)\s*k", raw, re.I)                          # 40k
    if m:
        v = float(m.group(1)) * 1000
        return v, v
    return (None, None)


def parse_exp(s):
    """经验文本 → (下限, 上限) 年。23 种写法统一归一。"""
    s = (s or "").strip()
    if "不限" in s or s == "无":
        return (0.0, None)
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*年", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+)\s*年\s*以上", s)
    if m:
        return float(m.group(1)), None
    m = re.search(r"(\d+)\s*年\s*以下", s)
    if m:
        return 0.0, float(m.group(1))
    m = re.search(r"(\d+)\s*年", s)
    if m:
        return float(m.group(1)), float(m.group(1))
    return (None, None)


def fmt(v, nd=1):
    return "" if v is None else round(v, nd)


# =====================================================================
# 1. 读取原始数据（全部当字符串读，保留中文/空串原貌）
# =====================================================================
with open(RAW, "r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
cols = list(rows[0].keys()) if rows else []
print("[读取] 原始行数 = %d" % len(rows))
print("[读取] 字段(%d) = %s" % (len(cols), cols))


# =====================================================================
# 2. 去重：主键（岗位ID）+ 业务（岗位名/企业/薪资/学历/经验 全同）
# =====================================================================
def dup_count(keys):
    seen = Counter()
    for r in rows:
        seen[tuple(r.get(k, "") for k in keys)] += 1
    return sum(c - 1 for c in seen.values() if c > 1)


dup_id = dup_count(["岗位ID"])
dup_full = dup_count(["岗位名称", "企业名称", "薪资原文", "学历要求", "经验要求"])

seen_id = set()
uniq = []
for r in rows:
    pid = r.get("岗位ID", "")
    if pid in seen_id:
        continue
    seen_id.add(pid)
    uniq.append(r)
rows = uniq
print("[去重] 主键重复=%d 业务重复=%d → 去重后行数=%d" % (dup_id, dup_full, len(rows)))


# =====================================================================
# 3. 缺失值：薪资用"薪资原文"回补并打存疑标记；技能占位符 → 空
# =====================================================================
n_fill = 0
for r in rows:
    lo = to_num(r.get("月薪下限_元"))
    hi = to_num(r.get("月薪上限_元"))
    mid = to_num(r.get("月薪中位_元"))
    if lo is None or hi is None:
        plo, phi = parse_salary(r.get("薪资原文", ""))
        if plo is not None and phi is not None:
            lo, hi = plo, phi
            mid = (plo + phi) / 2
            r["薪资口径标记"] = "存疑(原文回补)"
            n_fill += 1
    r["_lo"], r["_hi"], r["_mid"] = lo, hi, mid

    # 技能字段：占位符视为未获取
    if r.get("技能要求") == SKILL_PH:
        r["技能要求"] = ""

skill_ok = sum(1 for r in rows if r.get("技能要求"))
print("[缺失] 薪资回补行数=%d；技能可用行数=%d" % (n_fill, skill_ok))

# 是否复合岗位（岗位名含 / 或 、）
for r in rows:
    r["是否复合岗位"] = "是" if re.search(r"[/、]", r.get("岗位名称", "")) else "否"


# =====================================================================
# 4. 异常值：只标记、不删行
# =====================================================================
mids = sorted([r["_mid"] for r in rows if r["_mid"] is not None])
hi_thr = quantile(mids, 0.995)
lo_thr = quantile(mids, 0.005)

n_mid_out = n_rev = n_ext = 0
for r in rows:
    flags = []
    lo, hi, mid = r["_lo"], r["_hi"], r["_mid"]
    if mid is not None and lo is not None and hi is not None:
        if mid < lo * 0.9 or mid > hi * 1.1:
            flags.append("中位越界")
            n_mid_out += 1
        if lo > hi:
            flags.append("上下限颠倒")
            n_rev += 1
    if mid is not None and hi_thr is not None and lo_thr is not None:
        if mid > hi_thr or mid < lo_thr:
            if not flags:
                flags.append("极端值(保留)")
            n_ext += 1
    r["薪资异常"] = ";".join(flags)
print("[异常] 中位越界=%d 上下限颠倒=%d 极端值=%d" % (n_mid_out, n_rev, n_ext))


# =====================================================================
# 5. 类型转换：经验 → 数值；学历/可达性 → 有序类别（此处用排序权重表达）
# =====================================================================
EDU_ORDER = {"大专": 1, "学历不限": 2, "本科": 3, "硕士": 4, "博士": 5}
REACH_ORDER = {"L1": 1, "L2": 2, "L3": 3}

n_exp_missing = 0
for r in rows:
    elo, ehi = parse_exp(r.get("经验要求", ""))
    r["_elo"], r["_ehi"] = elo, ehi
    if elo is None:
        n_exp_missing += 1
print("[转换] 经验解析成功=%d，缺失=%d" % (len(rows) - n_exp_missing, n_exp_missing))


# =====================================================================
# 6. 落盘清洗后数据集
# =====================================================================
extra = ["是否复合岗位", "薪资异常"]
out_cols = [c for c in cols if c not in extra] + [c for c in extra if c not in cols]
for c in ("经验下限_年", "经验上限_年", "经验缺失"):
    if c not in out_cols:
        out_cols.append(c)

with open(CLEAN_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        rec = {c: r.get(c, "") for c in out_cols}
        # 关键：把"解析/回补"后的薪资写回三个数值列，否则下游读不到回补值
        for col, key in (("月薪下限_元", "_lo"), ("月薪上限_元", "_hi"), ("月薪中位_元", "_mid")):
            if col in out_cols:
                v = r[key]
                rec[col] = "" if v is None else ("%g" % v)
        rec["是否复合岗位"] = r["是否复合岗位"]
        rec["薪资异常"] = r["薪资异常"]
        rec["经验下限_年"] = fmt(r["_elo"])
        rec["经验上限_年"] = fmt(r["_ehi"])
        rec["经验缺失"] = "TRUE" if r["_elo"] is None else "FALSE"
        w.writerow(rec)
print("[落盘] 清洗后数据集 → %s（%d 行）" % (CLEAN_CSV, len(rows)))


# =====================================================================
# 7. EDA · 描述性统计（薪资用中位数更稳健）
# =====================================================================
sal = [r["_mid"] for r in rows if r["_mid"] is not None]
sal_sorted = sorted(sal)

print("\n========== 描述性统计（月薪中位_元）==========")
stat_items = [
    ("样本数", len(sal)),
    ("均值", round(statistics.mean(sal), 1)),
    ("中位数", round(statistics.median(sal), 1)),
    ("标准差", round(statistics.stdev(sal), 1) if len(sal) > 1 else 0),
    ("最小值", round(sal_sorted[0], 1)),
    ("25%分位", round(quantile(sal_sorted, 0.25), 1)),
    ("75%分位", round(quantile(sal_sorted, 0.75), 1)),
    ("最大值", round(sal_sorted[-1], 1)),
]
for k, v in stat_items:
    print("%-8s %s" % (k, v))

# 稳健性检验：剔除 存疑 + 极端值
robust = [
    r["_mid"]
    for r in rows
    if r["_mid"] is not None
    and "极端值" not in r["薪资异常"]
    and r.get("薪资口径标记") != "存疑(原文回补)"
]
if robust:
    print("剔除存疑+极端值后 n=%d，中位数=%s，均值=%s"
          % (len(robust), round(statistics.median(robust), 1), round(statistics.mean(robust), 1)))


# =====================================================================
# 8. EDA · 分组统计
# =====================================================================
def group_stat(keyfn, label, sort_by="count"):
    buckets = defaultdict(list)
    for r in rows:
        buckets[keyfn(r)].append(r)
    out = []
    for k, rs in buckets.items():
        vs = [x["_mid"] for x in rs if x["_mid"] is not None]
        out.append((k, len(rs), statistics.median(vs) if vs else None,
                    statistics.mean(vs) if vs else None))
    if sort_by == "count":
        out.sort(key=lambda t: -t[1])
    return out


print("\n========== 分组统计 ==========")

print("\n[岗位族] 招聘量 & 薪资中位：")
print("%-16s %8s %10s" % ("岗位族", "招聘量", "薪资中位"))
for k, n, med, _ in group_stat(lambda r: r.get("岗位族", "") or "(空)", "岗位族"):
    print("%-16s %8d %10s" % (k, n, fmt(med, 0)))

print("\n[学历] 溢价：")
edu_rows = group_stat(lambda r: r.get("学历要求", "") or "(空)", "学历要求")
edu_rows.sort(key=lambda t: EDU_ORDER.get(t[0], 99))
print("%-10s %8s %10s %10s" % ("学历", "招聘量", "薪资中位", "薪资均值"))
for k, n, med, mean in edu_rows:
    print("%-10s %8d %10s %10s" % (k, n, fmt(med, 0), fmt(mean, 0)))

print("\n[经验下限] 溢价：")
exp_buckets = defaultdict(list)
for r in rows:
    k = "缺失" if r["_elo"] is None else ("%g年" % r["_elo"])
    exp_buckets[k].append(r)


def exp_key(k):
    return (1, 0) if k == "缺失" else (0, float(k.replace("年", "")))


for k in sorted(exp_buckets, key=exp_key):
    rs = exp_buckets[k]
    vs = [x["_mid"] for x in rs if x["_mid"] is not None]
    print("%-8s %8d %10s" % (k, len(rs), fmt(statistics.median(vs) if vs else None, 0)))

print("\n[可达性] 分布：")
reach = Counter(r.get("可达性", "") or "(空)" for r in rows)
for k in sorted(reach, key=lambda x: REACH_ORDER.get(x, 99)):
    print("%-6s %d" % (k, reach[k]))

print("\n[解锁路径] 分布：")
for k, c in Counter(r.get("解锁路径", "") or "(空)" for r in rows).most_common():
    print("%-16s %d" % (k, c))

print("\n[区县] Top10：")
for k, c in Counter(r.get("区县", "") or "(空)" for r in rows).most_common(10):
    print("%-12s %d" % (k, c))

print("\n[岗位族 × 可达性] 交叉表：")
fams = [k for k, _, _, _ in group_stat(lambda r: r.get("岗位族", "") or "(空)", "岗位族")]
reach_levels = [k for k in sorted(reach, key=lambda x: REACH_ORDER.get(x, 99))]
ct = defaultdict(Counter)
for r in rows:
    ct[r.get("岗位族", "") or "(空)"][r.get("可达性", "") or "(空)"] += 1
header = "%-18s" % "岗位族" + "".join("%8s" % lv for lv in reach_levels)
print(header)
for fam in fams:
    print("%-18s" % fam + "".join("%8d" % ct[fam][lv] for lv in reach_levels))


# =====================================================================
# 9. 保存统计结果 + 核对清单
# =====================================================================
l1 = reach.get("L1", 0)
l2 = reach.get("L2", 0)
l3 = reach.get("L3", 0)
zhuan = sum(1 for r in rows if r.get("解锁路径") == "专升本")

stat_rows = [
    ("原始行数", len(rows) + dup_id),
    ("清洗后行数", len(rows)),
    ("薪资样本数", len(sal)),
    ("薪资中位数", round(statistics.median(sal), 1)),
    ("薪资均值", round(statistics.mean(sal), 1)),
    ("薪资25%~75%", "%s~%s" % (round(quantile(sal_sorted, .25), 1), round(quantile(sal_sorted, .75), 1))),
    ("L1可达数", l1),
    ("L2跳一跳数", l2),
    ("L3暂不可达数", l3),
    ("专升本解锁数", zhuan),
]
with open(STAT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["指标", "值"])
    w.writerows(stat_rows)
print("\n[落盘] 描述性统计 → %s" % STAT_CSV)

print("\n========== 你本机运行后请核对以下数字 ==========")
print("清洗后行数 = %d（预期 373）" % len(rows))
print("薪资中位数 = %s（预期 18000）" % round(statistics.median(sal), 1))
print("薪资均值   = %s（预期约 22097）" % round(statistics.mean(sal), 1))
print("可达性 L1/L2/L3 = %d/%d/%d（预期 12/226/135）" % (l1, l2, l3))
print("若以上数字接近，说明清洗逻辑与你的数据一致，可放心进入步骤4可视化。")
