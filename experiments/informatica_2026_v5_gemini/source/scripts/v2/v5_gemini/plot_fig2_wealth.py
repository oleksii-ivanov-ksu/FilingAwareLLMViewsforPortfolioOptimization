"""Figure 2: small-multiple daily wealth comparisons using saved Gemini returns."""
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/v2/analysis/informatica_v5_gemini/results"
OUT = ROOT / "paper/informatica/v5_ua/figures"
STYLES = {
    "bl_llm_tilt_pos": ("BL-Filing+", "#0072B2", "-", 1.25),
    "bl_llm_tilt": ("BL-Filing", "#D55E00", (0, (5, 2)), 1.25),
    "mvo": ("MVO", "#009E73", "-", 1.25),
    "bl_llm": ("BL-Filing MVO", "#A64D79", (0, (6, 2, 1, 2)), 1.25),
    "random_views": ("Random Views", "#8C6500", "-", 1.25),
    "equal_weight": ("EW", "#333333", (0, (3, 2)), 1.05),
}
PANELS = [("bl_llm_tilt_pos", "bl_llm_tilt"), ("mvo",),
          ("bl_llm", "random_views")]

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": .65, "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5, "pdf.fonttype": 42,
    })
    fig, axes = plt.subplots(3, 2, figsize=(17 / 2.54, 18.5 / 2.54),
                             sharex=True, sharey=True)
    fig.subplots_adjust(left=.095, right=.985, bottom=.075, top=.88,
                        wspace=.17, hspace=.53)
    audit = {"cutoff": "2025-12-31", "frequency": "daily",
             "transform": "cumprod(1 + saved daily return)",
             "smoothing": False, "resampling": False, "inputs": {}}
    for col, split in enumerate(("core", "holdout")):
        path = SRC / split / "daily_returns.csv"
        with path.open() as f:
            rows = [row for row in csv.DictReader(f) if row["date"] <= "2025-12-31"]
        dates = [datetime.fromisoformat(row["date"]) for row in rows]
        curves = {key: np.cumprod([1 + float(row[key]) for row in rows])
                  for key in STYLES}
        audit["inputs"][split] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "observations": len(rows), "first_date": rows[0]["date"],
            "last_date": rows[-1]["date"],
            "final_wealth": {key: float(y[-1]) for key, y in curves.items()},
        }
        for row, names in enumerate(PANELS):
            ax = axes[row, col]
            for key in ("equal_weight",) + names:
                label, color, style, width = STYLES[key]
                ax.plot(dates, curves[key], label=label, color=color,
                        linestyle=style, linewidth=width,
                        zorder=2 if key == "equal_weight" else 3)
            ax.set_yscale("log")
            ax.set_ylim(.35, 23)
            ax.set_xlim(datetime(2006, 1, 1), datetime(2026, 1, 1))
            ax.yaxis.set_major_locator(FixedLocator([.5, 1, 2, 5, 10, 20]))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
            ax.yaxis.set_minor_locator(NullLocator())
            ax.set_xticks([datetime(year, 1, 1) for year in (2008, 2016, 2024)])
            ax.set_xticklabels(["2008", "2016", "2024"])
            ax.tick_params(axis="both", length=3, width=.65, pad=3,
                           labelbottom=True, labelleft=True)
            ax.grid(axis="y", color="#DFE3E6", linewidth=.6)
            ax.grid(axis="x", color="#ECEEEF", linewidth=.5)
            if col == 0:
                ax.set_ylabel("Wealth (log scale)", labelpad=5)
            if row == 2:
                ax.set_xlabel("Year", labelpad=4)
    for col, title in enumerate(("Core", "Holdout")):
        pos = axes[0, col].get_position()
        fig.text((pos.x0 + pos.x1) / 2, .979, title, ha="center",
                 va="top", fontsize=11, fontweight="bold")
    for row, names in enumerate(PANELS):
        handles = []
        for key in names + ("equal_weight",):
            label, color, style, width = STYLES[key]
            handles.append(Line2D([], [], color=color, linestyle=style,
                                  linewidth=width, label=label))
        top = axes[row, 0].get_position().y1
        fig.legend(handles=handles, loc="lower center",
                   bbox_to_anchor=(.54, top + .012), ncol=len(handles),
                   fontsize=9, handlelength=2.8, columnspacing=1.8,
                   handletextpad=.6, frameon=False, borderaxespad=0)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"fig2_wealth.{ext}", dpi=450, facecolor="white")
    (OUT / "fig2_wealth_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    plt.close(fig)
    print(f"Saved 17 x 18.5 cm figure to {OUT}", flush=True)

if __name__ == "__main__":
    main()
