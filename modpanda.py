from pathlib import Path
import re
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# CONFIG
# ============================================================

BASE = Path(r"C:\Users\Admin\Desktop\neural framework")

TRUE_DIR  = BASE / "z true latch"
FALSE_DIR = BASE / "z false latch"

ROLL = 5  # light smoothing

# ============================================================
# ZLOG PARSER
# ============================================================

LINE_RE = re.compile(
    r"^(?P<region>\w+)\s+(?P<pop>\w+)\s+\d+\s+(?P<mass>[0-9.]+)",
    re.I
)

def parse_zlog(path: Path) -> pd.DataFrame:
    rows = []
    t = -1

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("t="):
                t += 1
                continue

            m = LINE_RE.match(line)
            if not m:
                continue

            rows.append({
                "t": t,
                "region": m.group("region").lower(),
                "pop": m.group("pop").lower(),
                "mass": float(m.group("mass")),
            })

    df = pd.DataFrame(rows)
    return df

def collapse_regions(df: pd.DataFrame) -> pd.DataFrame:
    out = []

    for t, g in df.groupby("t"):
        pfc = g[g.region == "pfc"].mass.mean()
        md  = g[(g.region == "md")  & (g.pop == "relay_cells")].mass.mean()
        trn = g[(g.region == "trn") & (g.pop == "trn_gaba")].mass.mean()

        out.append({
            "t": t,
            "pfc": pfc,
            "md": md,
            "trn": trn,
        })

    return pd.DataFrame(out)

# ============================================================
# LOAD BOTH RUNS
# ============================================================

true_df  = collapse_regions(parse_zlog(TRUE_DIR  / "zlog.txt"))
false_df = collapse_regions(parse_zlog(FALSE_DIR / "zlog.txt"))

for c in ["pfc", "md", "trn"]:
    true_df[c]  = true_df[c].rolling(ROLL, min_periods=1).mean()
    false_df[c] = false_df[c].rolling(ROLL, min_periods=1).mean()

diff_df = true_df.copy()
diff_df[["pfc","md","trn"]] -= false_df[["pfc","md","trn"]]

# ============================================================
# DECISION TIME
# ============================================================

dec = pd.read_csv(TRUE_DIR / "decision_latch_trace.csv")
t_dec = dec.iloc[0]["step"] if not dec.empty else None

# ============================================================
# PLOT
# ============================================================

fig, axs = plt.subplots(4, 1, figsize=(12, 10), sharex=True)

axs[0].plot(true_df.t,  true_df.pfc,  label="PFC TRUE")
axs[0].plot(false_df.t, false_df.pfc, "--", label="PFC FALSE")
axs[0].set_ylabel("PFC")

axs[1].plot(true_df.t,  true_df.md,  label="MD TRUE")
axs[1].plot(false_df.t, false_df.md, "--", label="MD FALSE")
axs[1].set_ylabel("MD")

axs[2].plot(true_df.t,  true_df.trn,  label="TRN TRUE")
axs[2].plot(false_df.t, false_df.trn, "--", label="TRN FALSE")
axs[2].set_ylabel("TRN")

axs[3].plot(diff_df.t, diff_df.pfc, label="ΔPFC")
axs[3].plot(diff_df.t, diff_df.md,  label="ΔMD")
axs[3].plot(diff_df.t, diff_df.trn, label="ΔTRN")
axs[3].set_ylabel("TRUE − FALSE")
axs[3].set_xlabel("Step")

if t_dec is not None:
    for ax in axs:
        ax.axvline(t_dec, color="k", alpha=0.3)

for ax in axs:
    ax.legend()
    ax.grid(alpha=0.3)

plt.tight_layout()
plt.show()
