"""
Purchase-to-pay analysis on real data (BPI Challenge 2019).

Questions:
  1. Is the data clean enough to use?
  2. How long from the vendor's invoice to payment, and where does the time go?
  3. Do payment blocks and order changes (rework) slow payment down?
  4. Which matching types and vendors cause the most delay?
  5. How much of the work is already automated?

Run from the project root (after src/convert_xes.py):
    python src/analyse.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

EVENTS = Path("data/events.csv")
VALID_FROM, VALID_TO = "2017-01-01", "2020-01-01"   # almost all events are from 2018
Path("images").mkdir(exist_ok=True)
Path("results").mkdir(exist_ok=True)

out_lines = []
def say(text=""):
    print(text)
    out_lines.append(str(text))

# ---------------- 1. load ----------------
print("Loading events ...")
df = pd.read_csv(
    EVENTS,
    usecols=["case_id", "activity", "timestamp", "resource", "item_category", "vendor"],
    dtype={"activity": "category", "resource": "category",
           "item_category": "category", "vendor": "category"},
)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601")

# ---------------- 2. data quality ----------------
bad = (df["timestamp"] < pd.Timestamp(VALID_FROM, tz="UTC")) | \
      (df["timestamp"] >= pd.Timestamp(VALID_TO, tz="UTC"))
bad_cases = df.loc[bad, "case_id"].unique()
say("=== 1. DATA QUALITY ===")
say(f"Events loaded:                  {len(df):,}")
say(f"Cases (order items):            {df['case_id'].nunique():,}")
say(f"Events with impossible dates:   {bad.sum():,} (earliest: {df['timestamp'].min().date()})")
say(f"Cases removed because of them:  {len(bad_cases):,}")
df = df[~df["case_id"].isin(bad_cases)]
say(f"Cases kept for analysis:        {df['case_id'].nunique():,}")

# ---------------- 3. automation level ----------------
df["is_batch"] = df["resource"].astype(str).str.startswith("batch")
say("\n=== 2. HOW MUCH IS ALREADY AUTOMATED? (share of events done by batch users) ===")
say(f"Overall: {df['is_batch'].mean():.0%} of all events")
key_acts = ["Create Purchase Order Item", "Record Goods Receipt", "Vendor creates invoice",
            "Record Invoice Receipt", "Remove Payment Block", "Clear Invoice",
            "Change Price", "Change Quantity"]
auto = (df[df["activity"].isin(key_acts)]
        .groupby("activity", observed=True)["is_batch"].agg(["size", "mean"])
        .reindex(key_acts))
for act, r in auto.iterrows():
    say(f"  {act:30s} {int(r['size']):>9,} events   {r['mean']:>5.0%} automated")

# ---------------- 4. one row per case ----------------
def first(act):
    return df[df["activity"] == act].groupby("case_id", observed=True)["timestamp"].min()

def last(act):
    return df[df["activity"] == act].groupby("case_id", observed=True)["timestamp"].max()

def has(act):
    return df.loc[df["activity"] == act, "case_id"].unique()

cases = df.groupby("case_id", observed=True)[["item_category", "vendor"]].first()
cases["po_created"] = first("Create Purchase Order Item")
cases["invoice_created"] = first("Vendor creates invoice")
cases["invoice_recorded"] = first("Record Invoice Receipt")
cases["paid"] = last("Clear Invoice")
cases["payment_block"] = cases.index.isin(has("Remove Payment Block"))
cases["price_change"] = cases.index.isin(has("Change Price"))
cases["quantity_change"] = cases.index.isin(has("Change Quantity"))
cases["invoice_cancelled"] = cases.index.isin(has("Cancel Invoice Receipt"))
cases["rework"] = cases["price_change"] | cases["quantity_change"]

def days(a, b):
    return (cases[b] - cases[a]).dt.total_seconds() / 86400

cases["invoice_to_pay"] = days("invoice_created", "paid")
cases["invoice_to_record"] = days("invoice_created", "invoice_recorded")
cases["record_to_pay"] = days("invoice_recorded", "paid")
cases["po_to_pay"] = days("po_created", "paid")

paid = cases[cases["invoice_to_pay"].ge(0)].copy()

# ---------------- 5. cycle times ----------------
say(f"\n=== 3. HOW LONG DOES PAYMENT TAKE? ({len(paid):,} cases with invoice and payment) ===")
say(f"Median days order created -> paid:        {paid['po_to_pay'].median():.0f}")
say(f"Median days vendor invoice -> paid:       {paid['invoice_to_pay'].median():.0f}")
say(f"  of which invoice -> recorded in ERP:    {paid.loc[paid['invoice_to_record'] >= 0, 'invoice_to_record'].median():.0f}")
say(f"  of which recorded -> paid:              {paid.loc[paid['record_to_pay'] >= 0, 'record_to_pay'].median():.0f}")
say(f"Paid within 10 days of invoice (Skonto):  {(paid['invoice_to_pay'] <= 10).mean():.0%}")
say(f"Paid within 30 days of invoice:           {(paid['invoice_to_pay'] <= 30).mean():.0%}")
say(f"Paid after 60+ days:                      {(paid['invoice_to_pay'] > 60).mean():.0%}")

# ---------------- 6. impact of problems ----------------
rows = []
for flag, label in [("payment_block", "Payment block"),
                    ("rework", "Price/quantity change"),
                    ("invoice_cancelled", "Invoice cancelled")]:
    yes, no = paid[paid[flag]], paid[~paid[flag]]
    rows.append({"issue": label, "cases": len(yes), "share": len(yes) / len(paid),
                 "with_issue": yes["invoice_to_pay"].median(),
                 "without_issue": no["invoice_to_pay"].median()})
impact = pd.DataFrame(rows)
impact["extra_days"] = impact["with_issue"] - impact["without_issue"]
say("\n=== 4. DO PROBLEMS SLOW PAYMENT DOWN? (median days invoice -> paid) ===")
say(impact.to_string(index=False, formatters={
    "cases": "{:,}".format, "share": "{:.1%}".format, "with_issue": "{:.0f}".format,
    "without_issue": "{:.0f}".format, "extra_days": "{:+.0f}".format}))

# ---------------- 7. by matching type ----------------
by_cat = (paid.groupby("item_category", observed=True)
          .agg(cases=("invoice_to_pay", "size"),
               median_days=("invoice_to_pay", "median"),
               payment_block_rate=("payment_block", "mean"),
               rework_rate=("rework", "mean"))
          .sort_values("cases", ascending=False))
say("\n=== 5. BY MATCHING TYPE ===")
say(by_cat.to_string(formatters={"cases": "{:,}".format, "median_days": "{:.0f}".format,
                                 "payment_block_rate": "{:.1%}".format,
                                 "rework_rate": "{:.1%}".format}))

# ---------------- 8. vendors ----------------
by_vendor = (paid.groupby("vendor", observed=True)
             .agg(cases=("invoice_to_pay", "size"),
                  median_days=("invoice_to_pay", "median"),
                  payment_block_rate=("payment_block", "mean"))
             .sort_values("cases", ascending=False))
top10 = by_vendor.head(10)
say("\n=== 6. TOP 10 VENDORS BY VOLUME ===")
say(f"Top 10 vendors = {top10['cases'].sum() / len(paid):.0%} of all paid cases "
    f"(out of {len(by_vendor):,} vendors)")
say(top10.to_string(formatters={"cases": "{:,}".format, "median_days": "{:.0f}".format,
                                "payment_block_rate": "{:.1%}".format}))

# ---------------- 9. charts ----------------
plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})

ax = impact.set_index("issue")[["without_issue", "with_issue"]].plot(
    kind="barh", color=["#8C8C8C", "#C44E52"], figsize=(7, 3.5))
ax.set_xlabel("Median days from vendor invoice to payment"); ax.set_ylabel("")
ax.set_xlim(0, impact["with_issue"].max() * 1.35)
ax.legend(["Without issue", "With issue"], frameon=False, loc="lower right")
ax.set_title("Problems that slow down payment")
plt.tight_layout(); plt.savefig("images/issue_impact.png"); plt.close()

ax = by_cat["median_days"].sort_values().plot(kind="barh", color="#4C72B0", figsize=(7, 3.2))
ax.set_xlabel("Median days from vendor invoice to payment"); ax.set_ylabel("")
ax.set_title("Payment time by matching type")
plt.tight_layout(); plt.savefig("images/days_by_category.png"); plt.close()

ax = paid["invoice_to_pay"].clip(upper=180).plot(kind="hist", bins=36, color="#4C72B0",
                                                  figsize=(7, 3.5))
for d, ha in [(10, "right"), (30, "left"), (60, "left")]:
    ax.axvline(d, ls="--", color="grey", lw=1)
    ax.text(d + (2 if ha == "left" else -2), ax.get_ylim()[1] * 0.93, f"{d} days",
            color="grey", ha=ha, fontsize=9)
ax.set_ylabel("Invoices")
ax.set_xlabel("Days from vendor invoice to payment (capped at 180)")
ax.set_title("How long invoices wait to be paid")
plt.tight_layout(); plt.savefig("images/payment_time_distribution.png"); plt.close()

auto_plot = auto["mean"].drop("Vendor creates invoice").sort_values()  # vendor step, not ours
ax = auto_plot.plot(kind="barh", color="#55A868", figsize=(7, 3.5))
ax.set_xlabel("Share of events done automatically (batch)"); ax.set_ylabel("")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
ax.set_title("Automation level per process step")
plt.tight_layout(); plt.savefig("images/automation_level.png"); plt.close()

# ---------------- 10. save ----------------
cases.to_csv("data/cases.csv")
Path("results/summary.txt").write_text("\n".join(out_lines), encoding="utf-8")
print("\nSaved: results/summary.txt, images/*.png, data/cases.csv")
