#!/usr/bin/env python
from __future__ import print_function

import argparse
import csv
import os
import re
import sys


FIELDNAMES = [
    "sample",
    "type",
    "year",
    "dataset",
    "input_dir",
    "xsec_pb",
    "sum_genweights",
    "label",
    "color",
]

ALIASES = {
    "sample": ["sample", "process", "name", "sample_name", "dataset_name"],
    "type": ["type", "sample_type", "category", "kind"],
    "year": ["year", "era"],
    "dataset": ["dataset", "das", "das_dataset", "dataset_path"],
    "input_dir": ["input_dir", "input", "path", "glob", "files", "output_dir"],
    "xsec_pb": ["xsec_pb", "xsec", "xs", "xs_pb", "cross_section", "cross section", "cross-section"],
    "sum_genweights": [
        "sum_genweights",
        "sum_genweight",
        "sum genweights",
        "sumgenweights",
        "gen_event_sumw",
        "geneventsumw",
        "total_gen_weight",
        "totgenwt",
        "totalgenweight",
    ],
    "label": ["label", "legend", "legend_label", "plot_label"],
    "color": ["color", "colour", "root_color"],
}


def norm_key(value):
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def parse_float(value, default=""):
    text = str(value or "").strip()
    if not text:
        return default
    text = text.replace(",", "")
    try:
        return "%.17g" % float(text)
    except ValueError:
        return text


def find_column(fieldnames, target):
    normalized = {norm_key(name): name for name in fieldnames or []}
    for alias in ALIASES[target]:
        key = norm_key(alias)
        if key in normalized:
            return normalized[key]
    return None


def normalize_type(value):
    text = str(value or "").strip().lower()
    if text in ("data", "singlemuon", "single_muon"):
        return "data"
    if text in ("signal", "sig"):
        return "signal"
    if text in ("background", "bkg", "mc", "simulation", "sim"):
        return "background"
    return text


def normalize_rows(input_path):
    with open(input_path) as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row")
        columns = {field: find_column(reader.fieldnames, field) for field in FIELDNAMES}
        rows = []
        for raw in reader:
            row = {}
            for field in FIELDNAMES:
                column = columns.get(field)
                row[field] = (raw.get(column, "") if column else "").strip()
            row["type"] = normalize_type(row["type"])
            row["xsec_pb"] = parse_float(row["xsec_pb"])
            row["sum_genweights"] = parse_float(row["sum_genweights"])
            if not row["label"]:
                row["label"] = row["sample"]
            rows.append(row)
    return rows


def single_row_from_args(args):
    return [
        {
            "sample": args.sample or "",
            "type": normalize_type(args.type or ""),
            "year": args.year or "2018",
            "dataset": args.dataset or "",
            "input_dir": args.input_dir or "",
            "xsec_pb": parse_float(args.xsec_pb),
            "sum_genweights": parse_float(args.sum_genweights),
            "label": args.label or args.sample or "",
            "color": args.color or "",
        }
    ]


def validate(rows):
    errors = []
    for index, row in enumerate(rows, 1):
        prefix = "row %d (%s)" % (index, row.get("sample") or "unnamed")
        if not row.get("sample"):
            errors.append(prefix + ": missing sample")
        if row.get("type") not in ("data", "background", "signal"):
            errors.append(prefix + ": type must be data, background, or signal")
        if not row.get("input_dir"):
            errors.append(prefix + ": missing input_dir")

        if row.get("type") == "data":
            row["xsec_pb"] = row.get("xsec_pb") or "1"
            row["sum_genweights"] = row.get("sum_genweights") or "1"
            continue

        for field in ("xsec_pb", "sum_genweights"):
            try:
                value = float(row.get(field, ""))
            except ValueError:
                value = 0.0
            if value == 0.0:
                errors.append(prefix + ": %s must be nonzero for MC/signal" % field)
    return errors


def write_rows(path, rows, append=False):
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    mode = "a" if append else "w"
    with open(path, mode) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if not append or not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def write_template(path):
    rows = [
        {
            "sample": "SingleMuon_Run2018A",
            "type": "data",
            "year": "2018",
            "dataset": "/SingleMuon/Run2018A-15Feb2022_UL2018-v1/MINIAOD",
            "input_dir": "/path/to/analysis_outputs/SingleMuon_Run2018A/*.root",
            "xsec_pb": "1",
            "sum_genweights": "1",
            "label": "SingleMuon 2018A",
            "color": "1",
        },
        {
            "sample": "WJetsToLNu_HT100To200",
            "type": "background",
            "year": "2018",
            "dataset": "/WJetsToLNu_HT-100To200_TuneCP5_13TeV-madgraphMLM-pythia8/RunIISummer20UL18MiniAODv2-106X_upgrade2018_realistic_v16_L1v1-v2/MINIAODSIM",
            "input_dir": "/path/to/analysis_outputs/WJetsToLNu_HT100To200/*.root",
            "xsec_pb": "",
            "sum_genweights": "",
            "label": "W+jets HT100-200",
            "color": "798",
        },
    ]
    write_rows(path, rows)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize professor/sample metadata into the project plotting CSV schema."
    )
    parser.add_argument("--input", help="Professor CSV or another sample table")
    parser.add_argument("--output", default="config/samples_2018.csv")
    parser.add_argument("--template", action="store_true", help="Write a template CSV and exit")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--sample")
    parser.add_argument("--type")
    parser.add_argument("--year", default="2018")
    parser.add_argument("--dataset")
    parser.add_argument("--input-dir")
    parser.add_argument("--xsec-pb")
    parser.add_argument("--sum-genweights")
    parser.add_argument("--label")
    parser.add_argument("--color")
    args = parser.parse_args()

    if args.template:
        write_template(args.output)
        print("Wrote template:", args.output)
        return 0

    if args.input:
        rows = normalize_rows(args.input)
    else:
        rows = single_row_from_args(args)

    errors = validate(rows)
    if errors:
        for error in errors:
            print("ERROR:", error, file=sys.stderr)
        return 1

    if args.validate_only:
        print("Metadata is valid:", args.input or args.output)
        return 0

    out_dir = os.path.dirname(args.output)
    if out_dir:
        try:
            os.makedirs(out_dir)
        except OSError:
            pass
    write_rows(args.output, rows, append=args.append)
    print("Wrote normalized metadata:", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
