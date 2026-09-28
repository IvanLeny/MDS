"""Figures du chapitre 4 : PNG 300 dpi, lisibles en noir et blanc (gris + hachures),
un seul axe par figure, étiquettes directes ; chaque figure a son CSV."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GRIS = ["#222222", "#777777", "#bbbbbb", "#dddddd"]
HACH = ["", "///", "...", "xx"]


def _style(ax, titre, ylabel):
    ax.set_title(titre, fontsize=10, loc="left")
    ax.set_ylabel(ylabel, fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8)


def _csv(chemin: Path, lignes: list[dict]):
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]), delimiter=";")
        w.writeheader()
        w.writerows(lignes)


def barres_groupees(chemin: Path, categories: list[str], series: dict[str, list[float | None]],
                    titre: str, ylabel: str, ymax: float | None = 1.0, note: str = ""):
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    n = len(series)
    larg = 0.8 / max(n, 1)
    for i, (nom, vals) in enumerate(series.items()):
        xs = [k + (i - (n - 1) / 2) * larg for k in range(len(categories))]
        v = [x if x is not None else 0 for x in vals]
        barres = ax.bar(xs, v, larg * 0.92, label=nom, color=GRIS[i % 4], hatch=HACH[i % 4],
                        edgecolor="#222222", linewidth=0.5)
        for b, x in zip(barres, vals):
            ax.annotate("n.m." if x is None else f"{x:.2f}".replace(".", ","),
                        (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom",
                        fontsize=6.5, xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=15, ha="right")
    if ymax:
        ax.set_ylim(0, ymax * 1.12)
    _style(ax, titre, ylabel)
    if n > 1:
        ax.legend(fontsize=8, frameon=False, ncol=n, loc="upper left", bbox_to_anchor=(0, -0.28))
    if note:
        fig.text(0.01, 0.01, note, fontsize=6.5, color="#555555")
    fig.tight_layout()
    fig.savefig(chemin, dpi=300)
    plt.close(fig)
    _csv(chemin.with_suffix(".csv"), [{"categorie": c, **{s: v[i] for s, v in series.items()}}
                                      for i, c in enumerate(categories)])


def distribution_temps(chemin: Path, durees: dict[str, list[float]], titre: str):
    noms = [k for k, v in durees.items() if v]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.boxplot([durees[k] for k in noms], tick_labels=noms, widths=0.45, showfliers=True,
               medianprops={"color": "#000000", "linewidth": 1.5},
               boxprops={"color": "#444444"}, whiskerprops={"color": "#444444"},
               flierprops={"marker": "o", "markersize": 3, "markerfacecolor": "#888888", "markeredgewidth": 0})
    ax.set_yscale("log")
    _style(ax, titre, "secondes (échelle log)")
    fig.tight_layout()
    fig.savefig(chemin, dpi=300)
    plt.close(fig)
    _csv(chemin.with_suffix(".csv"), [{"service": k, "duree_s": round(x, 4)} for k in noms for x in durees[k]])
