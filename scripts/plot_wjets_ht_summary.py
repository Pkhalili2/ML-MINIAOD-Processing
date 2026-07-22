#!/usr/bin/env python3

import argparse
import csv
import math
import os
import re

import matplotlib.pyplot as plt
import numpy as np


HT_PATTERN = re.compile(r"^WJets_HT(\d+)to(\d+|Inf)$")


def read_csv(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def parse_bins(cutflow_rows, normalization_rows):
    normalization = {row["sample"]: row for row in normalization_rows}
    stages = {}
    for row in cutflow_rows:
        if HT_PATTERN.match(row["sample"]):
            stages.setdefault(row["sample"], {})[row["stage"]] = row

    bins = []
    for sample, sample_stages in stages.items():
        match = HT_PATTERN.match(sample)
        if not match or "processed" not in sample_stages or "selected" not in sample_stages:
            continue
        low = int(match.group(1))
        upper_text = match.group(2)
        high = math.inf if upper_text == "Inf" else int(upper_text)
        processed = float(sample_stages["processed"]["raw_events"])
        selected = float(sample_stages["selected"]["raw_events"])
        normalized_yield = float(sample_stages["selected"]["normalized_yield"])
        norm = normalization[sample]
        bins.append(
            {
                "sample": sample,
                "low_gev": low,
                "high_gev": high,
                "label": "%d-%s" % (low, "inf" if math.isinf(high) else int(high)),
                "xsec_pb": float(norm["xsec_pb"]),
                "sum_genweights": float(norm["sum_genweights"]),
                "event_scale": float(norm["event_scale"]),
                "processed_events": processed,
                "selected_events": selected,
                "selection_efficiency": selected / processed if processed else 0.0,
                "normalized_selected_yield": normalized_yield,
                "normalization_note": norm.get("normalization_note", ""),
            }
        )
    bins.sort(key=lambda row: row["low_gev"])
    total_yield = sum(row["normalized_selected_yield"] for row in bins)
    for row in bins:
        row["selected_yield_fraction"] = (
            row["normalized_selected_yield"] / total_yield if total_yield else 0.0
        )
    return bins


def write_summary(rows, path):
    fields = [
        "sample",
        "ht_bin_gev",
        "xsec_pb",
        "sum_genweights",
        "event_scale",
        "processed_events",
        "selected_events",
        "selection_efficiency",
        "normalized_selected_yield",
        "selected_yield_fraction",
        "normalization_note",
    ]
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "sample": row["sample"],
                    "ht_bin_gev": row["label"],
                    "xsec_pb": "%.10g" % row["xsec_pb"],
                    "sum_genweights": "%.17g" % row["sum_genweights"],
                    "event_scale": "%.17g" % row["event_scale"],
                    "processed_events": "%.17g" % row["processed_events"],
                    "selected_events": "%.17g" % row["selected_events"],
                    "selection_efficiency": "%.17g" % row["selection_efficiency"],
                    "normalized_selected_yield": "%.17g" % row["normalized_selected_yield"],
                    "selected_yield_fraction": "%.17g" % row["selected_yield_fraction"],
                    "normalization_note": row["normalization_note"],
                }
            )


def plot(rows, output_stem, lumi_fb, status_label):
    labels = [row["label"] for row in rows]
    yields = np.array([row["normalized_selected_yield"] for row in rows])
    efficiencies = np.array([row["selection_efficiency"] for row in rows])
    positions = np.arange(len(rows))

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.linewidth": 1.0,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
        }
    )
    fig = plt.figure(figsize=(10.5, 8.2))
    grid = fig.add_gridspec(2, 1, height_ratios=[2.2, 1.0], hspace=0.06)
    upper = fig.add_subplot(grid[0])
    lower = fig.add_subplot(grid[1], sharex=upper)

    colors = plt.cm.viridis(np.linspace(0.12, 0.88, len(rows)))
    bars = upper.bar(positions, yields, color=colors, edgecolor="black", linewidth=0.8)
    upper.set_yscale("log")
    upper.set_ylabel("Expected selected events")
    upper.set_ylim(max(1.0, yields.min() * 0.35), yields.max() * 8.0)
    upper.grid(axis="y", which="both", linestyle=":", linewidth=0.6, alpha=0.55)
    upper.tick_params(labelbottom=False)

    for bar, value in zip(bars, yields):
        upper.text(
            bar.get_x() + bar.get_width() / 2.0,
            value * 1.18,
            "%.3g" % value,
            ha="center",
            va="bottom",
            fontsize=9,
            rotation=0,
        )

    upper.text(0.02, 0.96, "CMS", transform=upper.transAxes, fontsize=20, fontweight="bold", va="top")
    upper.text(0.13, 0.96, status_label, transform=upper.transAxes, fontsize=14, style="italic", va="top")
    upper.text(
        0.98,
        0.96,
        "%.2f fb$^{-1}$ (13 TeV)" % lumi_fb,
        transform=upper.transAxes,
        fontsize=13,
        ha="right",
        va="top",
    )
    upper.text(
        0.02,
        0.82,
        r"W+jets: $w_i=\mathcal{L}\,\sigma_{H_T}/\sum w_{\mathrm{gen}}$",
        transform=upper.transAxes,
        fontsize=11,
        va="top",
    )

    lower.plot(positions, efficiencies * 100.0, marker="o", color="#b31b1b", linewidth=1.8, markersize=6)
    lower.set_yscale("log")
    lower.set_ylabel("Selected / processed [%]")
    lower.set_xlabel(r"Generator $H_T$ bin [GeV]")
    lower.set_xticks(positions)
    lower.set_xticklabels(labels, rotation=35, ha="right")
    positive = efficiencies[efficiencies > 0.0] * 100.0
    lower.set_ylim(max(1e-5, positive.min() * 0.35), max(1.0, positive.max() * 5.0))
    lower.grid(axis="y", which="both", linestyle=":", linewidth=0.6, alpha=0.55)

    for x, value in zip(positions, efficiencies * 100.0):
        lower.annotate("%.3g%%" % value, (x, value), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8)

    fig.text(
        0.5,
        0.012,
        "Available UL2018 samples; each bin normalized to its process cross section. HT 70-100 cross section is provisional.",
        ha="center",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.11, right=0.97, top=0.96, bottom=0.18)
    fig.savefig(output_stem + ".png", dpi=180)
    fig.savefig(output_stem + ".pdf")
    plt.close(fig)


def selected_yield_totals(cutflow_rows):
    selected = {
        row["sample"]: float(row["normalized_yield"])
        for row in cutflow_rows
        if row["stage"] == "selected"
    }
    data = sum(value for sample, value in selected.items() if sample.startswith("SingleMuon_"))
    ttbar = sum(value for sample, value in selected.items() if sample.startswith("TTTo"))
    return selected, data, ttbar


def write_composition_summary(rows, data, ttbar, path):
    wjets = sum(row["normalized_selected_yield"] for row in rows)
    mc = wjets + ttbar
    records = [
        {
            "category": row["sample"],
            "kind": "WJets HT bin",
            "normalized_selected_yield": row["normalized_selected_yield"],
            "fraction_of_mc": row["normalized_selected_yield"] / mc if mc else 0.0,
        }
        for row in rows
    ]
    records.extend(
        [
            {"category": "ttbar_total", "kind": "background", "normalized_selected_yield": ttbar, "fraction_of_mc": ttbar / mc if mc else 0.0},
            {"category": "WJets_total", "kind": "subtotal", "normalized_selected_yield": wjets, "fraction_of_mc": wjets / mc if mc else 0.0},
            {"category": "MC_total", "kind": "total", "normalized_selected_yield": mc, "fraction_of_mc": 1.0 if mc else 0.0},
            {"category": "Data", "kind": "data", "normalized_selected_yield": data, "fraction_of_mc": data / mc if mc else 0.0},
        ]
    )
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["category", "kind", "normalized_selected_yield", "fraction_of_mc"],
        )
        writer.writeheader()
        for record in records:
            record = dict(record)
            record["normalized_selected_yield"] = "%.17g" % record["normalized_selected_yield"]
            record["fraction_of_mc"] = "%.17g" % record["fraction_of_mc"]
            writer.writerow(record)


def plot_composition(rows, data, ttbar, output_stem, lumi_fb, status_label):
    colors = plt.cm.viridis(np.linspace(0.12, 0.88, len(rows)))
    fig, axis = plt.subplots(figsize=(11.5, 7.2))
    axis.bar(0, data, width=0.62, color="white", edgecolor="black", linewidth=1.4, label="Data")

    bottom = 0.0
    for row, color in zip(rows, colors):
        value = row["normalized_selected_yield"]
        axis.bar(
            1,
            value,
            width=0.62,
            bottom=bottom,
            color=color,
            edgecolor="black",
            linewidth=0.5,
            label="W+jets HT %s GeV" % row["label"],
        )
        bottom += value
    axis.bar(
        1,
        ttbar,
        width=0.62,
        bottom=bottom,
        color="#d1495b",
        edgecolor="black",
        linewidth=0.7,
        label=r"$t\bar{t}$ (three channels)",
    )

    mc = bottom + ttbar
    axis.set_xlim(-0.65, 1.65)
    axis.set_ylim(0.0, data * 1.23)
    axis.set_xticks([0, 1])
    axis.set_xticklabels(["Data", "Available MC"])
    axis.set_ylabel("Expected selected events")
    axis.grid(axis="y", linestyle=":", linewidth=0.7, alpha=0.6)
    axis.set_axisbelow(True)
    axis.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    axis.text(0, data * 1.025, "%.3g" % data, ha="center", va="bottom", fontsize=11)
    axis.text(1, mc * 1.035, "%.3g" % mc, ha="center", va="bottom", fontsize=11)
    axis.text(
        0.5,
        0.73,
        "Data / MC = %.2f\nW+jets = %.1f%% of available MC" % (data / mc, 100.0 * bottom / mc),
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=13,
        bbox={"facecolor": "white", "edgecolor": "#666666", "boxstyle": "square,pad=0.45"},
    )
    axis.text(0.02, 0.97, "CMS", transform=axis.transAxes, fontsize=20, fontweight="bold", va="top")
    axis.text(0.13, 0.97, status_label, transform=axis.transAxes, fontsize=14, style="italic", va="top")
    axis.text(
        0.98,
        0.97,
        "%.2f fb$^{-1}$ (13 TeV)" % lumi_fb,
        transform=axis.transAxes,
        fontsize=13,
        ha="right",
        va="top",
    )
    axis.legend(loc="center left", bbox_to_anchor=(1.01, 0.48), frameon=False, fontsize=9)
    fig.text(
        0.5,
        0.02,
        "Exploratory normalization: available W+jets and ttbar only; trigger, muon, pileup, and theory corrections remain incomplete.",
        ha="center",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.11, right=0.73, top=0.95, bottom=0.13)
    fig.savefig(output_stem + ".png", dpi=180)
    fig.savefig(output_stem + ".pdf")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Plot W+jets yields and efficiency by generator HT bin.")
    parser.add_argument("--cutflow", required=True)
    parser.add_argument("--normalization", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--lumi-fb", type=float, default=37.997277757686)
    parser.add_argument("--status-label", default="Work in progress")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    cutflow_rows = read_csv(args.cutflow)
    rows = parse_bins(cutflow_rows, read_csv(args.normalization))
    if not rows:
        raise SystemExit("No WJets_HT samples found in the supplied audit tables")
    write_summary(rows, os.path.join(args.output_dir, "wjets_ht_bin_summary.csv"))
    plot(rows, os.path.join(args.output_dir, "wjets_ht_bin_summary"), args.lumi_fb, args.status_label)
    _, data, ttbar = selected_yield_totals(cutflow_rows)
    write_composition_summary(
        rows,
        data,
        ttbar,
        os.path.join(args.output_dir, "selected_yield_wjets_ht_composition.csv"),
    )
    plot_composition(
        rows,
        data,
        ttbar,
        os.path.join(args.output_dir, "selected_yield_wjets_ht_composition"),
        args.lumi_fb,
        args.status_label,
    )


if __name__ == "__main__":
    main()
