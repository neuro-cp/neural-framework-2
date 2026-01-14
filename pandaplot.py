import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------
# Load CSV WITHOUT trusting headers
# ---------------------------------------------
df = pd.read_csv(
    "dominance_trace.csv",
    header=None,
    names=[
        "step",
        "time",
        "channel",
        "raw",
        "instant",
        "smooth",
        "winner",
        "delta",
    ],
)

print("Loaded columns:", df.columns)
print(df.head())

# ---------------------------------------------
# Force numeric types
# ---------------------------------------------
numeric_cols = ["step", "time", "raw", "instant", "smooth", "delta"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Drop only truly invalid rows
df = df.dropna(subset=["step", "channel", "smooth"])

print("\nAfter cleaning:")
print(df.dtypes)
print(df.head())

# ---------------------------------------------
# Split channels
# ---------------------------------------------
d1 = df[df["channel"] == "D1"].sort_values("step")
d2 = df[df["channel"] == "D2"].sort_values("step")

# Safety check
if d1.empty or d2.empty:
    raise RuntimeError("One or both channels are empty — CSV still malformed")

# ---------------------------------------------
# Plot
# ---------------------------------------------
plt.figure(figsize=(10, 5))

plt.plot(d1["step"], d1["smooth"], label="D1", linewidth=2)
plt.plot(d2["step"], d2["smooth"], label="D2", linewidth=2)

plt.xlabel("Step")
plt.ylabel("Smoothed Dominance")
plt.title("Striatal Time Integration (CompetitionKernel)")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
