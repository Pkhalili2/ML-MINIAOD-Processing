#!/usr/bin/env python
from __future__ import print_function

import argparse
import csv
import glob
import math
import os
import re
import sys


PLOTS = {
    "ak4_jet_eta_preselection": {
        "source_hist": "ak4_jet_eta_preselection",
        "bins": (60, -5.0, 5.0),
        "title": "AK4 jet pseudorapidity",
        "x_title": "AK4 jet #eta",
    },
    "event_ht": {
        "branches": ["eventHT"],
        "bins": (50, 0.0, 2500.0),
        "title": "Reconstructed event H_{T}",
        "x_title": "AK4-jet H_{T} [GeV]",
    },
    "leading_muon_pt": {
        "branches": ["selectedMuonPt", "selectedLeptonPt"],
        "bins": (40, 0.0, 400.0),
        "title": "Leading selected muon transverse momentum",
        "x_title": "Selected muon p_{T} [GeV]",
    },
    "muon_ak15_delta_r": {
        "branches": ["muonJetDeltaR"],
        "derived": "delta_r",
        "bins": (36, 0.0, 6.0),
        "title": "Muon-leading AK15 angular separation",
        "x_title": "#DeltaR(#mu, AK15 jet)",
    },
    "muon_ak15_delta_phi": {
        "branches": ["muonJetDeltaPhi", "selectedLeptonDeltaPhi"],
        "derived": "delta_phi",
        "bins": (32, 0.0, 3.2),
        "title": "Muon-leading AK15 azimuthal separation",
        "x_title": "|#Delta#phi(#mu, AK15 jet)|",
    },
    "ak15_jet_pt": {
        "branches": ["jet_pt"],
        "bins": (45, 150.0, 1050.0),
        "title": "Selected leading AK15 jet transverse momentum",
        "x_title": "Selected AK15 jet p_{T} [GeV]",
    },
    "ak15_jet_mass": {
        "branches": ["jet_mass"],
        "bins": (40, 0.0, 400.0),
        "title": "Selected leading AK15 jet mass",
        "x_title": "Selected AK15 jet mass [GeV]",
    },
    "ak15_jet_eta": {
        "branches": ["jet_eta"],
        "bins": (30, -3.0, 3.0),
        "title": "Selected leading AK15 jet pseudorapidity",
        "x_title": "Selected AK15 jet #eta",
    },
    "ak15_jet_phi": {
        "branches": ["jet_phi"],
        "bins": (32, -3.2, 3.2),
        "title": "Selected leading AK15 jet azimuth",
        "x_title": "Selected AK15 jet #phi",
    },
    "selected_muon_eta": {
        "branches": ["selectedMuonEta", "selectedLeptonEta"],
        "bins": (30, -2.5, 2.5),
        "title": "Selected muon pseudorapidity",
        "x_title": "Selected muon #eta",
    },
    "selected_muon_phi": {
        "branches": ["selectedMuonPhi", "selectedLeptonPhi"],
        "bins": (32, -3.2, 3.2),
        "title": "Selected muon azimuth",
        "x_title": "Selected muon #phi",
    },
    "selected_muon_iso": {
        "branches": ["selectedMuonIso", "selectedLeptonIso"],
        "bins": (30, 0.0, 0.3),
        "title": "Selected muon relative isolation",
        "x_title": "Selected muon relative isolation",
    },
    "ak15_mass_over_pt": {
        "branches": [],
        "derived": "mass_over_pt",
        "bins": (35, 0.0, 0.7),
        "title": "Selected leading AK15 jet mass-to-momentum ratio",
        "x_title": "AK15 jet mass / p_{T}",
    },
    "n_input_muons": {
        "branches": ["nInputMuon"],
        "bins": (8, -0.5, 7.5),
        "title": "Input muon multiplicity",
        "x_title": "Input muon multiplicity",
    },
    "n_input_ak15": {
        "branches": ["nInputAK15"],
        "bins": (12, -0.5, 11.5),
        "title": "Input AK15 jet multiplicity",
        "x_title": "Input AK15 jet multiplicity",
    },
    "n_ht_jets": {
        "branches": ["nHTJet"],
        "bins": (16, -0.5, 15.5),
        "title": "AK4 jet multiplicity entering H_{T}",
        "x_title": "Number of AK4 jets in H_{T}",
    },
    "event_ht15": {
        "branches": ["eventHT15"],
        "requires": [("eventHT15IsComplete", 1)],
        "bins": (50, 0.0, 2500.0),
        "title": "Reconstructed event H_{T}^{AK15}",
        "x_title": "AK15-jet H_{T} [GeV]",
    },
    "met_pt": {
        "branches": ["met_pt"],
        "bins": (40, 0.0, 400.0),
        "title": "Missing transverse momentum",
        "x_title": "p_{T}^{miss} [GeV]",
    },
    "muon_met_transverse_mass": {
        "branches": ["muonMetTransverseMass"],
        "bins": (40, 0.0, 400.0),
        "title": "Muon-MET transverse mass",
        "x_title": "m_{T}(#mu, p_{T}^{miss}) [GeV]",
    },
    "met_ak15_delta_phi": {
        "branches": ["metJetDeltaPhi"],
        "bins": (32, 0.0, 3.2),
        "title": "MET-leading AK15 azimuthal separation",
        "x_title": "|#Delta#phi(p_{T}^{miss}, AK15)|",
    },
}

DEFAULT_PLOTS = [
    "event_ht",
    "leading_muon_pt",
    "muon_ak15_delta_r",
    "muon_ak15_delta_phi",
    "ak15_jet_pt",
    "ak15_jet_mass",
    "ak15_jet_eta",
    "ak15_jet_phi",
    "selected_muon_eta",
    "selected_muon_phi",
    "selected_muon_iso",
    "ak15_mass_over_pt",
    "n_input_muons",
    "n_input_ak15",
    "n_ht_jets",
    "met_pt",
    "muon_met_transverse_mass",
    "met_ak15_delta_phi",
]

CUTFLOW_STAGES = [
    "processed",
    "certified_lumi",
    "has_muon",
    "muon_pass",
    "has_ak15",
    "ak15_pt_eta",
    "muon_ak15_dphi",
    "ht4_pass",
    "met_pass",
    "mt_pass",
    "met_ak15_dphi",
    "selected",
]

CUTFLOW_DISPLAY = {
    "processed": "Processed",
    "certified_lumi": "Golden JSON",
    "has_muon": "Has muon",
    "muon_pass": "Muon selection",
    "has_ak15": "Has AK15",
    "ak15_pt_eta": "AK15 kinematics",
    "muon_ak15_dphi": "#Delta#phi(#mu, AK15) > 1.5",
    "ht4_pass": "H_{T}^{AK4} > 200",
    "met_pass": "p_{T}^{miss} > 30",
    "mt_pass": "m_{T} > 50",
    "met_ak15_dphi": "#Delta#phi(MET, AK15) > 1.0",
    "selected": "Selected",
}


def load_root():
    import ROOT

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)
    ROOT.gStyle.SetLegendBorderSize(0)
    ROOT.TH1.SetDefaultSumw2(True)
    return ROOT


def mkdir_p(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")


def parse_float(row, key, default=None):
    value = str(row.get(key, "")).strip()
    if not value:
        if default is None:
            raise ValueError("missing %s for sample %s" % (key, row.get("sample", "")))
        return default
    return float(value.replace(",", ""))


def parse_bool(row, key, default=True):
    value = str(row.get(key, "")).strip().lower()
    if not value:
        return default
    if value in ("1", "true", "yes", "y"):
        return True
    if value in ("0", "false", "no", "n"):
        return False
    raise ValueError("invalid %s=%s for sample %s" % (key, value, row.get("sample", "")))


def expand_files(spec):
    specs = [item.strip() for item in (spec or "").split(";") if item.strip()]
    files = []
    for item in specs:
        if item.startswith(("root://", "davs://", "https://")):
            matches = [item]
        elif os.path.isfile(item) and item.endswith((".txt", ".list")):
            with open(item) as handle:
                matches = [
                    raw.strip()
                    for raw in handle
                    if raw.strip() and not raw.lstrip().startswith("#")
                ]
        elif os.path.isdir(item):
            matches = sorted(glob.glob(os.path.join(item, "*.root")))
        else:
            matches = sorted(glob.glob(item))
            if not matches and os.path.isfile(item):
                matches = [item]
        files.extend(
            path
            for path in matches
            if path.startswith(("root://", "davs://", "https://"))
            or (os.path.isfile(path) and os.path.getsize(path) > 0)
        )
    return sorted(set(files))


def read_samples(path):
    required = set(["sample", "type", "input_dir", "xsec_pb", "sum_genweights"])
    with open(path) as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise SystemExit("Metadata CSV is missing required columns: " + ", ".join(missing))
        rows = []
        for row in reader:
            if not row.get("sample"):
                continue
            row["type"] = row.get("type", "").strip().lower()
            if row["type"] not in ("data", "background", "signal"):
                raise SystemExit("Sample %s has invalid type %s" % (row.get("sample"), row["type"]))
            row["_files"] = expand_files(row.get("input_dir", ""))
            if not row["_files"]:
                raise SystemExit(
                    "Sample %s has no nonempty ROOT files from input_dir=%s"
                    % (row["sample"], row.get("input_dir", ""))
                )
            row["_plot_scale"] = parse_float(row, "plot_scale", 1.0)
            row["_cutflow_valid"] = parse_bool(row, "cutflow_valid", True)
            rows.append(row)
    return rows


def has_branch(chain, name):
    return bool(name and chain.GetBranch(name))


def wrapped_delta_phi(phi1, phi2):
    value = math.fmod(phi1 - phi2, 2.0 * math.pi)
    if value > math.pi:
        value -= 2.0 * math.pi
    elif value <= -math.pi:
        value += 2.0 * math.pi
    return value


def event_value(event, chain, plot_name):
    plot = PLOTS[plot_name]
    for branch in plot.get("branches", []):
        if has_branch(chain, branch):
            return float(getattr(event, branch))
    derived = plot.get("derived", "")
    if derived in ("delta_r", "delta_phi"):
        mu_eta_name = "selectedMuonEta" if has_branch(chain, "selectedMuonEta") else "selectedLeptonEta"
        mu_phi_name = "selectedMuonPhi" if has_branch(chain, "selectedMuonPhi") else "selectedLeptonPhi"
        deta = float(getattr(event, mu_eta_name)) - float(getattr(event, "jet_eta"))
        dphi = wrapped_delta_phi(float(getattr(event, mu_phi_name)), float(getattr(event, "jet_phi")))
        if derived == "delta_phi":
            return abs(dphi)
        return math.sqrt(deta * deta + dphi * dphi)
    if derived == "mass_over_pt":
        pt = float(getattr(event, "jet_pt"))
        return float(getattr(event, "jet_mass")) / pt if pt > 0.0 else -1.0
    raise AttributeError("No available branch or derivation for plot %s" % plot_name)


def passes_plot_requirements(event, chain, plot_name):
    for branch, expected in PLOTS[plot_name].get("requires", []):
        if not has_branch(chain, branch) or int(getattr(event, branch)) != expected:
            return False
    return True


def sample_color(ROOT, row, index):
    raw = str(row.get("color", "")).strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    palette = [
        ROOT.kAzure - 9,
        ROOT.kOrange - 2,
        ROOT.kGreen + 2,
        ROOT.kViolet - 5,
        ROOT.kTeal - 5,
        ROOT.kPink + 7,
        ROOT.kSpring + 5,
    ]
    return palette[index % len(palette)]


def make_hist(ROOT, name, plot_name):
    nbins, xmin, xmax = PLOTS[plot_name]["bins"]
    hist = ROOT.TH1D(name, "", nbins, xmin, xmax)
    hist.SetDirectory(0)
    return hist


def aggregate_source_hist(ROOT, row, plot_name):
    source_name = PLOTS[plot_name]["source_hist"]
    combined = None
    missing = []
    for path in row["_files"]:
        root_file = ROOT.TFile.Open(path)
        source = root_file.Get(source_name) if root_file and not root_file.IsZombie() else None
        if not source:
            missing.append(path)
        elif combined is None:
            combined = source.Clone(safe_name(row["sample"]) + "_" + safe_name(plot_name))
            combined.SetDirectory(0)
        else:
            combined.Add(source)
        if root_file:
            root_file.Close()
    if missing:
        raise SystemExit(
            "Sample %s is missing histogram %s in %d file(s): %s"
            % (row["sample"], source_name, len(missing), ", ".join(missing[:5]))
        )
    if not combined:
        raise SystemExit("Sample %s has no histogram %s" % (row["sample"], source_name))
    return combined


def fold_flow_bins(hist):
    first = 1
    last = hist.GetNbinsX()
    for source, target in ((0, first), (last + 1, last)):
        content = hist.GetBinContent(target) + hist.GetBinContent(source)
        error = math.sqrt(hist.GetBinError(target) ** 2 + hist.GetBinError(source) ** 2)
        hist.SetBinContent(target, content)
        hist.SetBinError(target, error)
        hist.SetBinContent(source, 0.0)
        hist.SetBinError(source, 0.0)


def hist_values(hist):
    labels = []
    values = []
    for index in range(1, hist.GetNbinsX() + 1):
        labels.append(hist.GetXaxis().GetBinLabel(index) or str(index))
        values.append(float(hist.GetBinContent(index)))
    return labels, values


def canonical_cutflow(labels, values):
    mapped = dict(zip(labels, values))
    if "certified_lumi" not in mapped and "processed" in mapped:
        mapped["certified_lumi"] = mapped["processed"]
    if "muon_ak15_dphi" not in mapped and "dphi_pass" in mapped:
        mapped["muon_ak15_dphi"] = mapped["dphi_pass"]
    return [float(mapped.get(stage, 0.0)) for stage in CUTFLOW_STAGES]


def collect_file_metadata(ROOT, row):
    raw = [0.0] * len(CUTFLOW_STAGES)
    weighted = [0.0] * len(CUTFLOW_STAGES)
    normalization = {}
    cutflow_files = 0
    weighted_files = 0
    normalization_files = 0
    bad_files = []

    for path in row["_files"]:
        root_file = ROOT.TFile.Open(path)
        if not root_file or root_file.IsZombie():
            bad_files.append(path)
            continue
        raw_hist = root_file.Get("cutflow")
        if raw_hist:
            labels, values = hist_values(raw_hist)
            values = canonical_cutflow(labels, values)
            raw = [left + right for left, right in zip(raw, values)]
            cutflow_files += 1
        weighted_hist = root_file.Get("cutflow_weighted")
        if weighted_hist:
            labels, values = hist_values(weighted_hist)
            values = canonical_cutflow(labels, values)
            weighted = [left + right for left, right in zip(weighted, values)]
            weighted_files += 1
        norm_hist = root_file.Get("normalization")
        if norm_hist:
            labels, values = hist_values(norm_hist)
            for label, value in zip(labels, values):
                normalization[label] = normalization.get(label, 0.0) + value
            normalization_files += 1
        root_file.Close()

    if bad_files:
        raise SystemExit("Sample %s has unreadable ROOT files: %s" % (row["sample"], ", ".join(bad_files[:5])))
    if cutflow_files == 0:
        raise SystemExit("Sample %s has no cutflow histograms" % row["sample"])
    return {
        "raw": raw,
        "weighted": weighted,
        "cutflow_files": cutflow_files,
        "weighted_files": weighted_files,
        "normalization": normalization,
        "normalization_files": normalization_files,
    }


def style_hist(ROOT, row, hist, color):
    if row["type"] == "signal":
        hist.SetLineColor(color)
        hist.SetLineWidth(3)
        hist.SetFillStyle(0)
    elif row["type"] == "background":
        hist.SetFillColorAlpha(color, 0.82)
        hist.SetLineColor(ROOT.kBlack)
        hist.SetLineWidth(1)


def combined_data_hist(ROOT, plot_name, sample_hists):
    combined = None
    for row, hist in sample_hists:
        if row["type"] != "data":
            continue
        if combined is None:
            combined = hist.Clone("data_" + safe_name(plot_name))
            combined.SetDirectory(0)
        else:
            combined.Add(hist)
    if combined:
        combined.SetMarkerStyle(20)
        combined.SetMarkerSize(0.85)
        combined.SetLineColor(ROOT.kBlack)
    return combined


def cms_labels(ROOT, lumi_pb, note, title=""):
    labels = []
    cms = ROOT.TLatex()
    cms.SetNDC(True)
    cms.SetTextFont(62)
    cms.SetTextSize(0.052)
    cms.DrawLatex(0.14, 0.92, "CMS")
    labels.append(cms)

    status = ROOT.TLatex()
    status.SetNDC(True)
    status.SetTextFont(52)
    status.SetTextSize(0.040)
    status.DrawLatex(0.235, 0.92, "Work in progress")
    labels.append(status)

    lumi = ROOT.TLatex()
    lumi.SetNDC(True)
    lumi.SetTextFont(42)
    lumi.SetTextAlign(31)
    lumi.SetTextSize(0.040)
    if lumi_pb is None:
        lumi_text = "13 TeV"
    else:
        lumi_text = "%.2f fb^{-1} (13 TeV)" % (lumi_pb / 1000.0)
    lumi.DrawLatex(0.94, 0.92, lumi_text)
    labels.append(lumi)

    if title:
        plot_title = ROOT.TLatex()
        plot_title.SetNDC(True)
        plot_title.SetTextFont(62)
        plot_title.SetTextSize(0.031)
        plot_title.DrawLatex(0.14, 0.855, title)
        labels.append(plot_title)

    if note:
        for index, line in enumerate(part.strip() for part in note.split(";") if part.strip()):
            qualifier = ROOT.TLatex()
            qualifier.SetNDC(True)
            qualifier.SetTextFont(42)
            qualifier.SetTextSize(0.025)
            qualifier.DrawLatex(0.14, 0.805 - 0.040 * index, line)
            labels.append(qualifier)
    return labels


def build_total_background(backgrounds, name):
    total = None
    for _, hist in backgrounds:
        if total is None:
            total = hist.Clone(name)
            total.SetDirectory(0)
        else:
            total.Add(hist)
    return total


def group_backgrounds(backgrounds, name):
    grouped = {}
    order = []
    for row, hist in backgrounds:
        group = str(row.get("stack_group", "")).strip() or row["sample"]
        if group not in grouped:
            display_row = dict(row)
            display_row["label"] = str(row.get("stack_label", "")).strip() or row.get("label") or row["sample"]
            combined = hist.Clone("%s_%s" % (name, safe_name(group)))
            combined.SetDirectory(0)
            grouped[group] = (display_row, combined)
            order.append(group)
        else:
            grouped[group][1].Add(hist)
    return [grouped[group] for group in order]


def draw_stack_plot(
    ROOT, key, plot_title, x_title, data_hist, backgrounds, signals, output_dir, lumi_pb, note, log_y
):
    suffix = "" if log_y else "_linear"
    is_cutflow = key.startswith("cutflow")
    canvas_height = 920 if is_cutflow else 850
    canvas = ROOT.TCanvas("c_%s%s" % (safe_name(key), suffix), "", 900, canvas_height)
    has_data = bool(data_hist and data_hist.Integral(0, data_hist.GetNbinsX() + 1) > 0)
    total_bkg = build_total_background(backgrounds, "total_bkg_" + safe_name(key) + suffix)
    has_bkg = bool(total_bkg and total_bkg.Integral(0, total_bkg.GetNbinsX() + 1) != 0)
    has_ratio = has_data and has_bkg

    if has_ratio:
        split = 0.38 if is_cutflow else 0.30
        top = ROOT.TPad("top_%s%s" % (safe_name(key), suffix), "", 0.0, split, 1.0, 1.0)
        bottom = ROOT.TPad("bottom_%s%s" % (safe_name(key), suffix), "", 0.0, 0.0, 1.0, split)
        top.SetLeftMargin(0.12)
        top.SetRightMargin(0.04)
        top.SetBottomMargin(0.02)
        top.SetTopMargin(0.10)
        bottom.SetLeftMargin(0.12)
        bottom.SetRightMargin(0.04)
        bottom.SetTopMargin(0.03)
        bottom.SetBottomMargin(0.48 if is_cutflow else 0.34)
        top.Draw()
        bottom.Draw()
        top.cd()
    else:
        top = canvas
        bottom = None
        canvas.SetLeftMargin(0.12)
        canvas.SetRightMargin(0.04)
        canvas.SetBottomMargin(0.12)
        canvas.SetTopMargin(0.10)

    if log_y:
        top.SetLogy(True)

    stack = ROOT.THStack("stack_%s%s" % (safe_name(key), suffix), "")
    legend = ROOT.TLegend(0.57, 0.52, 0.94, 0.86)
    legend.SetFillColor(ROOT.kWhite)
    legend.SetFillStyle(1001)
    legend.SetBorderSize(0)
    legend.SetTextSize(0.027)
    for row, hist in backgrounds:
        stack.Add(hist)
        legend.AddEntry(hist, row.get("label") or row["sample"], "f")

    frame = None
    if backgrounds:
        stack.Draw("HIST")
        frame = stack.GetHistogram()
    elif has_data:
        data_hist.Draw("E1")
        frame = data_hist
    elif signals:
        signals[0][1].Draw("HIST")
        frame = signals[0][1]
    if frame is None:
        return

    frame.SetTitle("")
    frame.GetYaxis().SetTitle("Events" if is_cutflow else "Events / bin")
    frame.GetYaxis().SetTitleOffset(1.25)
    if has_ratio:
        frame.GetXaxis().SetLabelSize(0)
        frame.GetXaxis().SetTitle("")
    else:
        frame.GetXaxis().SetTitle(x_title)

    maxima = [frame.GetMaximum()]
    if has_data:
        maxima.append(data_hist.GetMaximum())
    maxima.extend(hist.GetMaximum() for _, hist in signals)
    max_y = max(maxima) if maxima else 1.0
    if log_y:
        minimum = 0.3
        maximum = max(10.0, max_y * 20.0)
    else:
        minimum = 0.0
        maximum = max(1.0, max_y * 1.55)
    if backgrounds:
        stack.SetMinimum(minimum)
        stack.SetMaximum(maximum)
    else:
        frame.SetMinimum(minimum)
        frame.SetMaximum(maximum)

    uncertainty = None
    if total_bkg:
        uncertainty = total_bkg.Clone("uncertainty_" + safe_name(key) + suffix)
        uncertainty.SetDirectory(0)
        uncertainty.SetFillColor(ROOT.kGray + 2)
        uncertainty.SetFillStyle(3344)
        uncertainty.SetMarkerSize(0)
        uncertainty.SetLineColor(ROOT.kGray + 2)
        uncertainty.Draw("E2 SAME")
        legend.AddEntry(uncertainty, "MC stat. unc.", "f")

    for row, hist in signals:
        hist.Draw("HIST SAME")
        legend.AddEntry(hist, row.get("label") or row["sample"], "l")
    if has_data:
        data_hist.Draw("E1 SAME")
        legend.AddEntry(data_hist, "Data", "lep")
    legend.Draw()
    labels = cms_labels(ROOT, lumi_pb, note, plot_title)

    ratio = None
    ratio_band = None
    unity = None
    if has_ratio:
        canvas.cd()
        bottom.cd()
        ratio = data_hist.Clone("ratio_" + safe_name(key) + suffix)
        ratio.SetDirectory(0)
        ratio_band = total_bkg.Clone("ratio_band_" + safe_name(key) + suffix)
        ratio_band.SetDirectory(0)
        ratio_points = []
        for index in range(1, ratio.GetNbinsX() + 1):
            observed = data_hist.GetBinContent(index)
            observed_error = data_hist.GetBinError(index)
            expected = total_bkg.GetBinContent(index)
            expected_error = total_bkg.GetBinError(index)
            if expected > 0.0:
                value = observed / expected
                error = observed_error / expected
                ratio.SetBinContent(index, value)
                ratio.SetBinError(index, error)
                ratio_band.SetBinContent(index, 1.0)
                ratio_band.SetBinError(index, expected_error / expected)
                if not math.isnan(value) and not math.isinf(value):
                    ratio_points.append((value, error))
            else:
                ratio.SetBinContent(index, 0.0)
                ratio.SetBinError(index, 0.0)
                ratio_band.SetBinContent(index, 0.0)
                ratio_band.SetBinError(index, 0.0)
        ratio.SetTitle("")
        ratio.SetMarkerStyle(20)
        ratio.SetMarkerSize(0.75)
        ratio.GetYaxis().SetTitle("Data/MC")
        largest = max([2.0] + [value + error for value, error in ratio_points])
        positive = [value for value, _ in ratio_points if value > 0.0]
        if largest > 5.0:
            bottom.SetLogy(True)
            smallest = min(positive) if positive else 1.0
            lower = max(0.05, min(0.5, smallest * 0.5))
            upper = 10.0 ** math.ceil(math.log10(largest * 1.2))
            ratio.GetYaxis().SetRangeUser(lower, upper)
        else:
            ratio.GetYaxis().SetRangeUser(0.0, max(2.0, largest * 1.15))
        ratio.GetYaxis().SetNdivisions(505)
        ratio.GetYaxis().SetTitleSize(0.105)
        ratio.GetYaxis().SetTitleOffset(0.52)
        ratio.GetYaxis().SetLabelSize(0.085)
        ratio.GetXaxis().SetTitle("" if is_cutflow else x_title)
        ratio.GetXaxis().SetTitleSize(0.085 if is_cutflow else 0.115)
        ratio.GetXaxis().SetTitleOffset(1.55 if is_cutflow else 1.15)
        ratio.GetXaxis().SetLabelSize(0.060 if is_cutflow else 0.095)
        ratio.GetXaxis().CenterTitle(True)
        if is_cutflow:
            ratio.GetXaxis().LabelsOption("v")
        ratio_band.SetFillColor(ROOT.kGray + 2)
        ratio_band.SetFillStyle(3344)
        ratio_band.SetMarkerSize(0)
        ratio_band.SetLineColor(ROOT.kGray + 2)
        ratio.Draw("E1")
        ratio_band.Draw("E2 SAME")
        ratio.Draw("E1 SAME")
        unity = ROOT.TLine(ratio.GetXaxis().GetXmin(), 1.0, ratio.GetXaxis().GetXmax(), 1.0)
        unity.SetLineStyle(2)
        unity.Draw()

    canvas.SaveAs(os.path.join(output_dir, key + suffix + ".png"))
    canvas.SaveAs(os.path.join(output_dir, key + suffix + ".pdf"))
    canvas.Close()


def cutflow_hist(ROOT, name, values):
    hist = ROOT.TH1D(name, "", len(CUTFLOW_STAGES), 0.5, len(CUTFLOW_STAGES) + 0.5)
    hist.SetDirectory(0)
    for index, stage in enumerate(CUTFLOW_STAGES, 1):
        hist.GetXaxis().SetBinLabel(index, CUTFLOW_DISPLAY[stage])
        hist.SetBinContent(index, values[index - 1])
    return hist


def draw_efficiency_plot(ROOT, rows, output_dir):
    canvas = ROOT.TCanvas("c_cutflow_efficiency", "", 1050, 650)
    canvas.SetLeftMargin(0.10)
    canvas.SetRightMargin(0.04)
    canvas.SetBottomMargin(0.24)
    canvas.SetTopMargin(0.10)
    legend = ROOT.TLegend(0.67, 0.55, 0.94, 0.87)
    legend.SetFillStyle(0)
    legend.SetTextSize(0.030)
    drawn = []
    grouped_rows = {}
    group_order = []
    for row in rows:
        if not row["_cutflow_valid"]:
            continue
        group = str(row.get("stack_group", "")).strip() or row["sample"]
        if group not in grouped_rows:
            combined = dict(row)
            combined["label"] = str(row.get("stack_label", "")).strip() or row.get("label") or row["sample"]
            combined["_cutflow_raw"] = list(row["_cutflow_raw"])
            grouped_rows[group] = combined
            group_order.append(group)
        else:
            grouped_rows[group]["_cutflow_raw"] = [
                left + right for left, right in zip(grouped_rows[group]["_cutflow_raw"], row["_cutflow_raw"])
            ]

    for index, group in enumerate(group_order):
        row = grouped_rows[group]
        values = row["_cutflow_raw"]
        baseline_index = 1 if row["type"] == "data" else 0
        baseline = values[baseline_index]
        efficiency = [value / baseline if baseline > 0.0 else 0.0 for value in values]
        hist = cutflow_hist(ROOT, "eff_" + safe_name(row["sample"]), efficiency)
        color = row["_color"]
        hist.SetLineColor(color)
        hist.SetMarkerColor(color)
        hist.SetLineWidth(2)
        hist.SetMarkerStyle(20 + (index % 10))
        hist.GetYaxis().SetTitle("Cumulative efficiency")
        hist.GetYaxis().SetRangeUser(0.0, 1.25)
        hist.GetXaxis().LabelsOption("v")
        hist.GetXaxis().SetLabelSize(0.050)
        hist.Draw("LP" if index == 0 else "LP SAME")
        legend.AddEntry(hist, row.get("label") or row["sample"], "lp")
        drawn.append(hist)
    legend.Draw()
    labels = cms_labels(
        ROOT,
        None,
        "Normalization independent",
        "Cumulative selection efficiency",
    )
    canvas.SaveAs(os.path.join(output_dir, "cutflow_efficiency.png"))
    canvas.SaveAs(os.path.join(output_dir, "cutflow_efficiency.pdf"))
    canvas.Close()


def main():
    parser = argparse.ArgumentParser(
        description="Make luminosity-weighted CMS-style data/MC plots from compact analysis trees."
    )
    parser.add_argument("--metadata", default="config/samples_2018.csv")
    parser.add_argument("--output-dir", default="plots/physics_analysis")
    parser.add_argument("--tree", default="Events")
    parser.add_argument("--lumi-pb", type=float, required=True)
    parser.add_argument("--plots", default=",".join(DEFAULT_PLOTS))
    parser.add_argument("--note", default="Available 2018 samples only")
    args = parser.parse_args()

    ROOT = load_root()
    mkdir_p(args.output_dir)
    samples = read_samples(args.metadata)
    plots = [item.strip() for item in args.plots.split(",") if item.strip()]
    unknown = sorted(set(plots) - set(PLOTS))
    if unknown:
        raise SystemExit("Unknown plots: " + ", ".join(unknown))

    yield_rows = []
    normalization_rows = []
    cutflow_rows = []
    plot_hists = dict((plot, []) for plot in plots)

    for sample_index, row in enumerate(samples):
        row["_color"] = sample_color(ROOT, row, sample_index)
        metadata = collect_file_metadata(ROOT, row)
        row["_cutflow_raw"] = metadata["raw"]

        sumw_text = str(row.get("sum_genweights", "")).strip().lower()
        if row["type"] == "data":
            sumw = 1.0
            xsec = 1.0
            event_scale = 1.0
        else:
            xsec = parse_float(row, "xsec_pb")
            if sumw_text in ("", "auto"):
                sumw = float(metadata["normalization"].get("sum_genweights", 0.0))
                if metadata["normalization_files"] != len(row["_files"]):
                    raise SystemExit(
                        "Sample %s requested automatic sum_genweights but only %d/%d files contain normalization metadata"
                        % (row["sample"], metadata["normalization_files"], len(row["_files"]))
                    )
            else:
                sumw = float(sumw_text.replace(",", ""))
            if sumw == 0.0:
                raise SystemExit("Sample %s has sum_genweights=0" % row["sample"])
            event_scale = args.lumi_pb * xsec * row["_plot_scale"] / sumw
        row["_sumw"] = sumw
        row["_event_scale"] = event_scale

        needs_event_loop = any(
            not PLOTS[plot].get("source_hist") for plot in plots
        )
        chain = None
        if needs_event_loop:
            chain = ROOT.TChain(args.tree)
            for path in row["_files"]:
                chain.Add(path)
            entries = int(chain.GetEntries())
        else:
            entries = int(
                round(metadata["normalization"].get("selected_events", 0.0))
            )
        if entries == 0:
            sys.stderr.write(
                "WARNING: sample %s has zero selected entries in tree %s; "
                "retaining it as a zero-yield sample\n"
                % (row["sample"], args.tree)
            )

        sample_hists = {}
        for plot in plots:
            if PLOTS[plot].get("source_hist"):
                hist = aggregate_source_hist(ROOT, row, plot)
                if row["type"] != "data":
                    hist.Scale(event_scale)
                sample_hists[plot] = hist
            else:
                sample_hists[plot] = make_hist(
                    ROOT, safe_name(row["sample"]) + "_" + safe_name(plot), plot
                )
        for hist in sample_hists.values():
            style_hist(ROOT, row, hist, row["_color"])

        selected_sumw = float(
            metadata["normalization"].get("selected_sum_genweights", 0.0)
        )
        if needs_event_loop:
            selected_sumw = 0.0
            for event in chain:
                if row["type"] == "data":
                    gen_weight = 1.0
                    weight = 1.0
                else:
                    if not has_branch(chain, "genWeight"):
                        raise SystemExit("MC sample %s is missing genWeight" % row["sample"])
                    gen_weight = float(getattr(event, "genWeight"))
                    weight = gen_weight * event_scale
                selected_sumw += gen_weight
                for plot in plots:
                    if PLOTS[plot].get("source_hist"):
                        continue
                    if not passes_plot_requirements(event, chain, plot):
                        continue
                    sample_hists[plot].Fill(event_value(event, chain, plot), weight)

        for hist in sample_hists.values():
            fold_flow_bins(hist)

        if metadata["weighted_files"] == len(row["_files"]):
            cutflow_genweights = metadata["weighted"]
            cutflow_method = "cutflow_weighted"
        elif row["type"] == "data":
            cutflow_genweights = list(metadata["raw"])
            cutflow_method = "raw_data"
        else:
            processed = metadata["raw"][0]
            average = sumw / processed if processed > 0.0 else 0.0
            cutflow_genweights = [value * average for value in metadata["raw"]]
            cutflow_genweights[-1] = selected_sumw
            cutflow_method = "raw_times_average_genweight"
        row["_cutflow_genweights"] = cutflow_genweights
        row["_cutflow_yields"] = (
            list(metadata["raw"])
            if row["type"] == "data"
            else [value * event_scale for value in cutflow_genweights]
        )

        normalization_rows.append(
            {
                "sample": row["sample"],
                "type": row["type"],
                "files": len(row["_files"]),
                "tree_entries": entries,
                "xsec_pb": "%.17g" % xsec,
                "sum_genweights": "%.17g" % sumw,
                "lumi_pb": "%.17g" % args.lumi_pb,
                "plot_scale": "%.17g" % row["_plot_scale"],
                "event_scale": "%.17g" % event_scale,
                "cutflow_weight_method": cutflow_method,
                "xsec_source": row.get("xsec_source", ""),
                "normalization_note": row.get("normalization_note", ""),
                "cutflow_valid": int(row["_cutflow_valid"]),
            }
        )
        for stage_index, stage in enumerate(CUTFLOW_STAGES):
            cutflow_rows.append(
                {
                    "sample": row["sample"],
                    "type": row["type"],
                    "stage": stage,
                    "raw_events": "%.17g" % metadata["raw"][stage_index],
                    "sum_genweights": "%.17g" % cutflow_genweights[stage_index],
                    "normalized_yield": "%.17g" % row["_cutflow_yields"][stage_index],
                    "cutflow_valid": int(row["_cutflow_valid"]),
                }
            )
        for plot in plots:
            hist = sample_hists[plot]
            plot_hists[plot].append((row, hist))
            yield_rows.append(
                {
                    "sample": row["sample"],
                    "type": row["type"],
                    "plot": plot,
                    "files": len(row["_files"]),
                    "tree_entries": entries,
                    "yield": "%.17g" % hist.Integral(0, hist.GetNbinsX() + 1),
                }
            )

    root_out = ROOT.TFile.Open(os.path.join(args.output_dir, "histograms.root"), "RECREATE")
    for plot in plots:
        for _, hist in plot_hists[plot]:
            hist.Write()
    root_out.Close()

    with open(os.path.join(args.output_dir, "yields.csv"), "w") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample", "type", "plot", "files", "tree_entries", "yield"])
        writer.writeheader()
        writer.writerows(yield_rows)
    with open(os.path.join(args.output_dir, "normalization.csv"), "w") as handle:
        fields = [
            "sample",
            "type",
            "files",
            "tree_entries",
            "xsec_pb",
            "sum_genweights",
            "lumi_pb",
            "plot_scale",
            "event_scale",
            "cutflow_weight_method",
            "xsec_source",
            "normalization_note",
            "cutflow_valid",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(normalization_rows)
    with open(os.path.join(args.output_dir, "cutflow.csv"), "w") as handle:
        fields = [
            "sample",
            "type",
            "stage",
            "raw_events",
            "sum_genweights",
            "normalized_yield",
            "cutflow_valid",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(cutflow_rows)

    for plot in plots:
        sample_hists = plot_hists[plot]
        data_hist = combined_data_hist(ROOT, plot, sample_hists)
        backgrounds = group_backgrounds(
            [(row, hist) for row, hist in sample_hists if row["type"] == "background"],
            "grouped_%s" % safe_name(plot),
        )
        signals = [(row, hist) for row, hist in sample_hists if row["type"] == "signal"]
        draw_stack_plot(
            ROOT,
            plot,
            PLOTS[plot]["title"],
            PLOTS[plot]["x_title"],
            data_hist,
            backgrounds,
            signals,
            args.output_dir,
            args.lumi_pb,
            args.note,
            True,
        )
        draw_stack_plot(
            ROOT,
            plot,
            PLOTS[plot]["title"],
            PLOTS[plot]["x_title"],
            data_hist,
            backgrounds,
            signals,
            args.output_dir,
            args.lumi_pb,
            args.note,
            False,
        )

    cutflow_hists = []
    for row in samples:
        if not row["_cutflow_valid"]:
            continue
        hist = cutflow_hist(ROOT, "cutflow_" + safe_name(row["sample"]), row["_cutflow_yields"])
        style_hist(ROOT, row, hist, row["_color"])
        cutflow_hists.append((row, hist))
    data_cutflow = combined_data_hist(ROOT, "cutflow_weighted", cutflow_hists)
    background_cutflow = group_backgrounds(
        [(row, hist) for row, hist in cutflow_hists if row["type"] == "background"],
        "grouped_cutflow",
    )
    signal_cutflow = [(row, hist) for row, hist in cutflow_hists if row["type"] == "signal"]
    for log_y in (True, False):
        draw_stack_plot(
            ROOT,
            "cutflow_weighted",
            "Cumulative weighted event selection",
            "Selection stage",
            data_cutflow,
            background_cutflow,
            signal_cutflow,
            args.output_dir,
            args.lumi_pb,
            args.note,
            log_y,
        )
    draw_efficiency_plot(ROOT, samples, args.output_dir)

    print("Wrote weighted plots, cutflows, and normalization audit to", args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
