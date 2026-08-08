#!/usr/bin/env python
from __future__ import print_function

import argparse
import csv
import math
import os
import sys

from make_weighted_plots import (
    DEFAULT_PLOTS,
    PLOTS,
    collect_file_metadata,
    cms_labels,
    draw_stack_plot,
    event_value,
    fold_flow_bins,
    group_backgrounds,
    has_branch,
    load_root,
    make_hist,
    mkdir_p,
    parse_float,
    passes_plot_requirements,
    read_samples,
    safe_name,
    sample_color,
    style_hist,
)


REGIONS = ("A", "B", "C", "D")
ABCD_AXIS_PLOTS = ("selected_muon_iso", "muon_met_transverse_mass")
ABCD_DEFAULT_PLOTS = [name for name in DEFAULT_PLOTS if name not in ABCD_AXIS_PLOTS]


def hist_integral_and_error(ROOT, hist):
    error = ROOT.Double(0.0)
    value = hist.IntegralAndError(0, hist.GetNbinsX() + 1, error)
    return float(value), float(error)


def clone_empty(hist, name):
    result = hist.Clone(name)
    result.SetDirectory(0)
    result.Reset("ICES")
    return result


def add_hist(target, source):
    if target is None:
        target = source.Clone(source.GetName() + "_sum")
        target.SetDirectory(0)
    else:
        target.Add(source)
    return target


def subtract_hist(data_hist, background_hist, name):
    result = data_hist.Clone(name)
    result.SetDirectory(0)
    if background_hist:
        result.Add(background_hist, -1.0)
    return result


def positive_shape(source, name):
    result = source.Clone(name)
    result.SetDirectory(0)
    negative_bins = 0
    negative_yield = 0.0
    for index in range(0, result.GetNbinsX() + 2):
        content = result.GetBinContent(index)
        if content < 0.0:
            negative_bins += 1
            negative_yield += content
            result.SetBinContent(index, 0.0)
    return result, negative_bins, negative_yield


def propagated_product_ratio(b, c, d):
    if b[0] <= 0.0 or c[0] <= 0.0 or d[0] <= 0.0:
        raise SystemExit(
            "ABCD residual yields must be positive; got B=%.6g C=%.6g D=%.6g"
            % (b[0], c[0], d[0])
        )
    value = b[0] * c[0] / d[0]
    relative_variance = (b[1] / b[0]) ** 2 + (c[1] / c[0]) ** 2 + (d[1] / d[0]) ** 2
    return value, abs(value) * math.sqrt(relative_variance)


def optional_product_ratio(b, c, d):
    if b[0] <= 0.0 or c[0] <= 0.0 or d[0] <= 0.0:
        return (float("nan"), float("nan"))
    return propagated_product_ratio(b, c, d)


def write_csv(path, fieldnames, rows):
    with open(path, "w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def draw_abcd_plane(ROOT, hist, output_dir, key, title, note, lumi_pb, log_z):
    canvas = ROOT.TCanvas("c_" + safe_name(key), "", 900, 760)
    canvas.SetLeftMargin(0.12)
    canvas.SetRightMargin(0.14)
    canvas.SetBottomMargin(0.12)
    canvas.SetTopMargin(0.10)
    if log_z:
        canvas.SetLogz(True)
        hist.SetMinimum(0.5)
    hist.SetTitle("")
    hist.GetXaxis().SetTitle("Selected muon relative isolation")
    hist.GetYaxis().SetTitle("m_{T}(#mu, p_{T}^{miss}) [GeV]")
    hist.GetZaxis().SetTitle("Events / bin")
    hist.Draw("COLZ")
    vertical = ROOT.TLine(0.15, 0.0, 0.15, 400.0)
    horizontal = ROOT.TLine(0.0, 50.0, 0.5, 50.0)
    for line in (vertical, horizontal):
        line.SetLineColor(ROOT.kBlack)
        line.SetLineWidth(2)
        line.SetLineStyle(2)
        line.Draw()
    region_labels = []
    for label, x, y in (("A", 0.07, 220.0), ("B", 0.07, 20.0), ("C", 0.32, 220.0), ("D", 0.32, 20.0)):
        text = ROOT.TLatex(x, y, label)
        text.SetTextFont(62)
        text.SetTextSize(0.045)
        text.Draw()
        region_labels.append(text)
    labels = cms_labels(ROOT, lumi_pb, note, title)
    canvas.SaveAs(os.path.join(output_dir, key + ".png"))
    canvas.SaveAs(os.path.join(output_dir, key + ".pdf"))
    canvas.Close()


def main():
    parser = argparse.ArgumentParser(
        description="Build a data-driven QCD estimate from muon isolation and transverse-mass ABCD regions."
    )
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--lumi-pb", type=float, required=True)
    parser.add_argument("--plots", default=",".join(ABCD_DEFAULT_PLOTS))
    parser.add_argument("--tree", default="ABCDEvents")
    parser.add_argument("--qcd-group", default="QCD")
    parser.add_argument("--note", default="Data-driven QCD estimate; work in progress")
    args = parser.parse_args()

    ROOT = load_root()
    mkdir_p(args.output_dir)
    PLOTS["selected_muon_iso"]["bins"] = (50, 0.0, 0.5)
    samples = read_samples(args.metadata)
    plots = [item.strip() for item in args.plots.split(",") if item.strip()]
    unknown = sorted(set(plots) - set(PLOTS))
    if unknown:
        raise SystemExit("Unknown plots: " + ", ".join(unknown))
    invalid_axes = sorted(set(plots) & set(ABCD_AXIS_PLOTS))
    if invalid_axes:
        raise SystemExit(
            "ABCD-axis variables require control-region plots and cannot use the region-D shape transfer: "
            + ", ".join(invalid_axes)
        )
    source_hist_plots = [name for name in plots if PLOTS[name].get("source_hist")]
    if source_hist_plots:
        raise SystemExit(
            "ABCD plots require event-level branches, not source histograms: "
            + ", ".join(source_hist_plots)
        )

    sample_region_hists = {}
    sample_region_yields = {}
    sample_planes = {}
    normalization_rows = []

    for sample_index, row in enumerate(samples):
        row["_color"] = sample_color(ROOT, row, sample_index)
        metadata = collect_file_metadata(ROOT, row)
        if row["type"] == "data":
            xsec = 1.0
            sumw = 1.0
            scale = 1.0
        else:
            xsec = parse_float(row, "xsec_pb")
            sumw_text = str(row.get("sum_genweights", "")).strip().lower()
            if sumw_text in ("", "auto"):
                sumw = float(metadata["normalization"].get("sum_genweights", 0.0))
                if metadata["normalization_files"] != len(row["_files"]):
                    raise SystemExit(
                        "Sample %s has normalization metadata in only %d/%d files"
                        % (row["sample"], metadata["normalization_files"], len(row["_files"]))
                    )
            else:
                sumw = float(sumw_text.replace(",", ""))
            if sumw == 0.0:
                raise SystemExit("Sample %s has sum_genweights=0" % row["sample"])
            scale = args.lumi_pb * xsec * row["_plot_scale"] / sumw
        row["_event_scale"] = scale

        chain = ROOT.TChain(args.tree)
        for path in row["_files"]:
            chain.Add(path)
        if not chain.GetBranch("abcdRegion"):
            raise SystemExit("Sample %s is missing abcdRegion in %s" % (row["sample"], args.tree))

        region_hists = dict(
            (
                region,
                dict(
                    (plot, make_hist(ROOT, "%s_%s_%s" % (safe_name(row["sample"]), region, plot), plot))
                    for plot in plots
                ),
            )
            for region in REGIONS
        )
        region_yields = dict((region, [0.0, 0.0]) for region in REGIONS)
        plane = ROOT.TH2D(
            safe_name(row["sample"]) + "_abcd_plane",
            "",
            25,
            0.0,
            0.5,
            40,
            0.0,
            400.0,
        )
        plane.SetDirectory(0)
        plane.Sumw2()
        for event in chain:
            region_index = int(event.abcdRegion)
            if region_index < 1 or region_index > 4:
                raise SystemExit("Sample %s has invalid ABCD region %d" % (row["sample"], region_index))
            region = REGIONS[region_index - 1]
            if row["type"] == "data":
                weight = 1.0
            else:
                if not has_branch(chain, "genWeight"):
                    raise SystemExit("MC sample %s is missing genWeight" % row["sample"])
                weight = float(event.genWeight) * scale
            region_yields[region][0] += weight
            region_yields[region][1] += weight * weight
            plane.Fill(float(event.selectedMuonIso), float(event.muonMetTransverseMass), weight)
            for plot in plots:
                if passes_plot_requirements(event, chain, plot):
                    region_hists[region][plot].Fill(event_value(event, chain, plot), weight)

        for region in REGIONS:
            region_yields[region][1] = math.sqrt(region_yields[region][1])
            for hist in region_hists[region].values():
                fold_flow_bins(hist)
                style_hist(ROOT, row, hist, row["_color"])
        sample_region_hists[row["sample"]] = region_hists
        sample_region_yields[row["sample"]] = region_yields
        sample_planes[row["sample"]] = plane
        normalization_rows.append(
            {
                "sample": row["sample"],
                "type": row["type"],
                "files": len(row["_files"]),
                "tree_entries": int(chain.GetEntries()),
                "xsec_pb": "%.17g" % xsec,
                "sum_genweights": "%.17g" % sumw,
                "lumi_pb": "%.17g" % args.lumi_pb,
                "event_scale": "%.17g" % scale,
                "stack_group": row.get("stack_group", ""),
                "xsec_source": row.get("xsec_source", ""),
            }
        )

    data_rows = [row for row in samples if row["type"] == "data"]
    qcd_rows = [
        row
        for row in samples
        if row["type"] == "background"
        and (str(row.get("stack_group", "")).strip() or row["sample"]) == args.qcd_group
    ]
    nonqcd_rows = [row for row in samples if row["type"] == "background" and row not in qcd_rows]
    signal_rows = [row for row in samples if row["type"] == "signal"]

    yield_rows = []
    residual_yields = {}
    qcd_mc_yields = {}
    for region in REGIONS:
        data_value = sum(sample_region_yields[row["sample"]][region][0] for row in data_rows)
        data_error = math.sqrt(
            sum(sample_region_yields[row["sample"]][region][1] ** 2 for row in data_rows)
        )
        nonqcd_value = sum(sample_region_yields[row["sample"]][region][0] for row in nonqcd_rows)
        nonqcd_error = math.sqrt(
            sum(sample_region_yields[row["sample"]][region][1] ** 2 for row in nonqcd_rows)
        )
        qcd_value = sum(sample_region_yields[row["sample"]][region][0] for row in qcd_rows)
        qcd_error = math.sqrt(
            sum(sample_region_yields[row["sample"]][region][1] ** 2 for row in qcd_rows)
        )
        residual = data_value - nonqcd_value
        residual_error = math.sqrt(data_error * data_error + nonqcd_error * nonqcd_error)
        residual_yields[region] = (residual, residual_error)
        qcd_mc_yields[region] = (qcd_value, qcd_error)
        yield_rows.append(
            {
                "region": region,
                "data": "%.17g" % data_value,
                "data_stat": "%.17g" % data_error,
                "nonqcd_mc": "%.17g" % nonqcd_value,
                "nonqcd_mc_stat": "%.17g" % nonqcd_error,
                "data_minus_nonqcd": "%.17g" % residual,
                "residual_stat": "%.17g" % residual_error,
                "qcd_mc": "%.17g" % qcd_value,
                "qcd_mc_stat": "%.17g" % qcd_error,
            }
        )

    prediction = propagated_product_ratio(
        residual_yields["B"], residual_yields["C"], residual_yields["D"]
    )
    qcd_mc_prediction = optional_product_ratio(
        qcd_mc_yields["B"], qcd_mc_yields["C"], qcd_mc_yields["D"]
    )
    qcd_mc_a = qcd_mc_yields["A"]
    closure_ratio = (
        qcd_mc_prediction[0] / qcd_mc_a[0]
        if qcd_mc_a[0] > 0.0 and not math.isnan(qcd_mc_prediction[0])
        else float("nan")
    )
    kappa = (
        qcd_mc_a[0] * qcd_mc_yields["D"][0]
        / (qcd_mc_yields["B"][0] * qcd_mc_yields["C"][0])
        if qcd_mc_yields["B"][0] and qcd_mc_yields["C"][0]
        else float("nan")
    )
    summary_rows = [
        {"quantity": "qcd_A_prediction_BxC_over_D", "value": "%.17g" % prediction[0], "stat_error": "%.17g" % prediction[1]},
        {"quantity": "qcd_MC_A_observed", "value": "%.17g" % qcd_mc_a[0], "stat_error": "%.17g" % qcd_mc_a[1]},
        {"quantity": "qcd_MC_A_prediction_BxC_over_D", "value": "%.17g" % qcd_mc_prediction[0], "stat_error": "%.17g" % qcd_mc_prediction[1]},
        {"quantity": "qcd_MC_closure_prediction_over_observed", "value": "%.17g" % closure_ratio, "stat_error": ""},
        {"quantity": "qcd_MC_kappa_AxD_over_BxC", "value": "%.17g" % kappa, "stat_error": ""},
    ]

    shape_rows = []
    root_out = ROOT.TFile.Open(os.path.join(args.output_dir, "abcd_histograms.root"), "RECREATE")
    data_plane = None
    nonqcd_plane = None
    qcd_mc_plane = None
    for row in data_rows:
        data_plane = add_hist(data_plane, sample_planes[row["sample"]])
    for row in nonqcd_rows:
        nonqcd_plane = add_hist(nonqcd_plane, sample_planes[row["sample"]])
    for row in qcd_rows:
        qcd_mc_plane = add_hist(qcd_mc_plane, sample_planes[row["sample"]])
    residual_plane = subtract_hist(data_plane, nonqcd_plane, "abcd_plane_data_minus_nonqcd")
    draw_abcd_plane(
        ROOT,
        data_plane,
        args.output_dir,
        "abcd_plane_data",
        "ABCD control plane: data",
        args.note,
        args.lumi_pb,
        True,
    )
    draw_abcd_plane(
        ROOT,
        residual_plane,
        args.output_dir,
        "abcd_plane_data_minus_nonqcd",
        "ABCD control plane: data minus non-QCD",
        args.note,
        args.lumi_pb,
        False,
    )
    data_plane.Write("abcd_plane_data")
    nonqcd_plane.Write("abcd_plane_nonqcd")
    residual_plane.Write()
    if qcd_mc_plane:
        qcd_mc_plane.Write("abcd_plane_qcd_mc")
    for plot in plots:
        data_by_region = {}
        nonqcd_by_region = {}
        for region in REGIONS:
            data_hist = None
            for row in data_rows:
                data_hist = add_hist(data_hist, sample_region_hists[row["sample"]][region][plot])
            nonqcd_hist = None
            for row in nonqcd_rows:
                nonqcd_hist = add_hist(nonqcd_hist, sample_region_hists[row["sample"]][region][plot])
            data_by_region[region] = data_hist
            nonqcd_by_region[region] = nonqcd_hist

        d_residual = subtract_hist(
            data_by_region["D"], nonqcd_by_region["D"], "qcd_D_residual_%s" % safe_name(plot)
        )
        qcd_prediction, negative_bins, negative_yield = positive_shape(
            d_residual, "qcd_A_prediction_%s" % safe_name(plot)
        )
        positive_integral = qcd_prediction.Integral(0, qcd_prediction.GetNbinsX() + 1)
        if positive_integral <= 0.0:
            raise SystemExit("Region-D residual shape is nonpositive for %s" % plot)
        qcd_prediction.Scale(prediction[0] / positive_integral)
        relative_norm_error = prediction[1] / prediction[0] if prediction[0] > 0.0 else 0.0
        for index in range(0, qcd_prediction.GetNbinsX() + 2):
            content = qcd_prediction.GetBinContent(index)
            shape_error = qcd_prediction.GetBinError(index)
            qcd_prediction.SetBinError(
                index, math.sqrt(shape_error * shape_error + (content * relative_norm_error) ** 2)
            )
        qcd_row = {
            "sample": "QCD_data_driven",
            "type": "background",
            "label": "QCD multijet (data-driven)",
            "stack_group": "QCDDataDriven",
            "stack_label": "QCD multijet (data-driven)",
        }
        style_hist(ROOT, qcd_row, qcd_prediction, ROOT.kMagenta - 7)

        backgrounds = [(qcd_row, qcd_prediction)]
        for row in nonqcd_rows:
            backgrounds.append((row, sample_region_hists[row["sample"]]["A"][plot]))
        backgrounds = group_backgrounds(backgrounds, "abcd_grouped_%s" % safe_name(plot))
        signals = [(row, sample_region_hists[row["sample"]]["A"][plot]) for row in signal_rows]
        data_a = data_by_region["A"]
        data_a.SetMarkerStyle(20)
        data_a.SetMarkerSize(0.85)
        data_a.SetLineColor(ROOT.kBlack)
        for log_y in (True, False):
            draw_stack_plot(
                ROOT,
                plot,
                PLOTS[plot]["title"],
                PLOTS[plot]["x_title"],
                data_a,
                backgrounds,
                signals,
                args.output_dir,
                args.lumi_pb,
                args.note,
                log_y,
                "Pred. stat. + ABCD norm. unc.",
                "Data/Pred.",
            )
        data_a.Write("data_A_%s" % safe_name(plot))
        d_residual.Write()
        qcd_prediction.Write()
        shape_rows.append(
            {
                "plot": plot,
                "region_d_residual_integral": "%.17g" % d_residual.Integral(0, d_residual.GetNbinsX() + 1),
                "positive_shape_integral_before_norm": "%.17g" % positive_integral,
                "negative_bins_clipped": negative_bins,
                "negative_yield_clipped": "%.17g" % negative_yield,
                "qcd_A_prediction": "%.17g" % prediction[0],
                "qcd_A_prediction_stat": "%.17g" % prediction[1],
            }
        )
    root_out.Close()

    write_csv(
        os.path.join(args.output_dir, "abcd_yields.csv"),
        ["region", "data", "data_stat", "nonqcd_mc", "nonqcd_mc_stat", "data_minus_nonqcd", "residual_stat", "qcd_mc", "qcd_mc_stat"],
        yield_rows,
    )
    write_csv(
        os.path.join(args.output_dir, "abcd_summary.csv"),
        ["quantity", "value", "stat_error"],
        summary_rows,
    )
    write_csv(
        os.path.join(args.output_dir, "qcd_shape_audit.csv"),
        ["plot", "region_d_residual_integral", "positive_shape_integral_before_norm", "negative_bins_clipped", "negative_yield_clipped", "qcd_A_prediction", "qcd_A_prediction_stat"],
        shape_rows,
    )
    write_csv(
        os.path.join(args.output_dir, "normalization.csv"),
        ["sample", "type", "files", "tree_entries", "xsec_pb", "sum_genweights", "lumi_pb", "event_scale", "stack_group", "xsec_source"],
        normalization_rows,
    )
    print("QCD region-A prediction: %.6g +/- %.6g" % prediction)
    print("QCD MC closure prediction/observed: %.6g" % closure_ratio)
    print("QCD MC kappa: %.6g" % kappa)
    print("Wrote ABCD plots and audits to", args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
