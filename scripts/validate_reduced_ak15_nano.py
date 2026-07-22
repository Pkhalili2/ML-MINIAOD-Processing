#!/usr/bin/env python
from __future__ import print_function

import argparse
import math

import ROOT


CUSTOM_PREFIXES = (
    "nSuperFatJetAK15",
    "SuperFatJetAK15_",
    "nSuperFatJetAK15PFCand",
    "SuperFatJetAK15PFCand_",
    "nSuperFatJetAK15GenCand",
    "SuperFatJetAK15GenCand_",
    "nSuperFat_SubJetAK8",
    "SuperFat_SubJetAK8_",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def branches(tree):
    return {branch.GetName() for branch in tree.GetListOfBranches()}


def values(tree, name):
    return list(getattr(tree, name))


def close(first, second):
    return abs(first - second) <= max(1e-6, 1e-6 * abs(first), 1e-6 * abs(second))


def sampled_entries(total, limit):
    if limit < 0 or limit >= total:
        return list(range(total))
    if limit == 0:
        return []
    if limit == 1:
        return [0]
    return sorted({int(round(index * (total - 1.0) / (limit - 1))) for index in range(limit)})


def compare_values(left, right, message):
    require(len(left) == len(right), message + " multiplicity changed")
    require(all(close(float(a), float(b)) for a, b in zip(left, right)), message + " values changed")


def main():
    parser = argparse.ArgumentParser(
        description="Validate a non-destructive full-AK15 to leading-only NanoAOD reduction."
    )
    parser.add_argument("input")
    parser.add_argument("reduced")
    parser.add_argument("--reference-leading")
    parser.add_argument("--max-events", type=int, default=-1)
    parser.add_argument(
        "--check-events",
        type=int,
        default=-1,
        help="Check this many evenly spaced events while still requiring the full event count.",
    )
    args = parser.parse_args()

    source_file = ROOT.TFile.Open(args.input)
    reduced_file = ROOT.TFile.Open(args.reduced)
    require(source_file and not source_file.IsZombie(), "input ROOT file is unreadable")
    require(reduced_file and not reduced_file.IsZombie(), "reduced ROOT file is unreadable")
    source = source_file.Get("Events")
    reduced = reduced_file.Get("Events")
    require(source and reduced, "Events tree is missing")

    expected = source.GetEntries()
    if args.max_events >= 0:
        expected = min(expected, args.max_events)
    require(reduced.GetEntries() == expected, "event count changed")

    source_branches = branches(source)
    reduced_branches = branches(reduced)
    ordinary_missing = sorted(
        name for name in source_branches - reduced_branches
        if not name.startswith(CUSTOM_PREFIXES)
    )
    require(not ordinary_missing, "ordinary NanoAOD branches are missing: " + ", ".join(ordinary_missing))
    required = {
        "SuperFatJetAK15_leadingAK15SourceJetIdx",
        "SuperFatJetAK15_originalAK15Multiplicity",
        "SuperFatJetAK15PFCand_jetIdx",
    }
    require(required.issubset(reduced_branches), "leading-only metadata is incomplete")

    reference_file = ROOT.TFile.Open(args.reference_leading) if args.reference_leading else None
    reference = reference_file.Get("Events") if reference_file else None
    if reference:
        require(reference.GetEntries() >= expected, "reference leading file has too few events")

    ordinary_checks = ("run", "luminosityBlock", "event", "nMuon", "Muon_pt", "MET_pt")
    collection_prefixes = (
        "SuperFatJetAK15_",
        "SuperFatJetAK15PFCand_",
        "SuperFatJetAK15GenCand_",
        "SuperFat_SubJetAK8_",
    )
    enabled = set(ordinary_checks)
    for name in source_branches | reduced_branches:
        if name.startswith(collection_prefixes):
            enabled.add(name)
    for tree in (source, reduced, reference):
        if not tree:
            continue
        tree.SetBranchStatus("*", 0)
        tree_branches = branches(tree)
        for name in enabled & tree_branches:
            tree.SetBranchStatus(name, 1)

    pf_total = 0
    gen_total = 0
    subjet_total = 0
    entries = sampled_entries(expected, args.check_events)
    for entry in entries:
        require(source.GetEntry(entry) > 0, "failed to read input event %d" % entry)
        require(reduced.GetEntry(entry) > 0, "failed to read reduced event %d" % entry)
        if reference:
            require(reference.GetEntry(entry) > 0, "failed to read reference event %d" % entry)

        for name in ordinary_checks:
            if name not in source_branches:
                continue
            left = getattr(source, name)
            right = getattr(reduced, name)
            if hasattr(left, "__len__") and not isinstance(left, (str, bytes)):
                require(len(left) == len(right), "%s multiplicity changed at event %d" % (name, entry))
                require(all(close(float(a), float(b)) for a, b in zip(left, right)),
                        "%s changed at event %d" % (name, entry))
            else:
                require(left == right or close(float(left), float(right)),
                        "%s changed at event %d" % (name, entry))

        source_pt = values(source, "SuperFatJetAK15_pt")
        reduced_pt = values(reduced, "SuperFatJetAK15_pt")
        require(len(reduced_pt) <= 1, "more than one AK15 jet remains")
        require(len(reduced_pt) == min(len(source_pt), 1), "AK15 multiplicity is inconsistent")
        if source_pt:
            leading = max(range(len(source_pt)), key=source_pt.__getitem__)
            require(close(reduced_pt[0], source_pt[leading]), "leading AK15 pT is incorrect")
            require(values(reduced, "SuperFatJetAK15_leadingAK15SourceJetIdx")[0] == leading,
                    "source jet index is incorrect")
            require(values(reduced, "SuperFatJetAK15_originalAK15Multiplicity")[0] == len(source_pt),
                    "original AK15 multiplicity is incorrect")

            for name in sorted(source_branches & reduced_branches):
                if not name.startswith("SuperFatJetAK15_"):
                    continue
                if name in {
                    "SuperFatJetAK15_leadingAK15SourceJetIdx",
                    "SuperFatJetAK15_originalAK15Multiplicity",
                }:
                    continue
                source_values = values(source, name)
                output_values = values(reduced, name)
                compare_values([source_values[leading]], output_values,
                               "%s at event %d" % (name, entry))

            source_pf = values(source, "SuperFatJetAK15PFCand_jetIdx")
            pf_indices = [index for index, jet_index in enumerate(source_pf) if jet_index == leading]
            output_pf = values(reduced, "SuperFatJetAK15PFCand_jetIdx")
            require(len(output_pf) == len(pf_indices) and all(index == 0 for index in output_pf),
                    "PF-constituent association is incorrect")
            for name in sorted(source_branches & reduced_branches):
                if not name.startswith("SuperFatJetAK15PFCand_") or name.endswith("_jetIdx"):
                    continue
                source_values = values(source, name)
                output_values = values(reduced, name)
                compare_values([source_values[index] for index in pf_indices], output_values,
                               "%s at event %d" % (name, entry))
            output_gen = []
            if "SuperFatJetAK15GenCand_jetIdx" in source_branches:
                source_gen = values(source, "SuperFatJetAK15GenCand_jetIdx")
                gen_indices = [index for index, jet_index in enumerate(source_gen) if jet_index == leading]
                output_gen = values(reduced, "SuperFatJetAK15GenCand_jetIdx")
                require(len(output_gen) == len(gen_indices) and all(index == 0 for index in output_gen),
                        "generator-constituent association is incorrect")
                for name in sorted(source_branches & reduced_branches):
                    if not name.startswith("SuperFatJetAK15GenCand_") or name.endswith("_jetIdx"):
                        continue
                    source_values = values(source, name)
                    output_values = values(reduced, name)
                    compare_values([source_values[index] for index in gen_indices], output_values,
                                   "%s at event %d" % (name, entry))
            pf_total += len(output_pf)
            gen_total += len(output_gen)

        source_subjet_pt = values(source, "SuperFat_SubJetAK8_pt")
        for name in sorted(source_branches & reduced_branches):
            if not name.startswith("SuperFat_SubJetAK8_"):
                continue
            compare_values(values(source, name), values(reduced, name),
                           "%s at event %d" % (name, entry))
        subjet_total += len(source_subjet_pt)

        if reference:
            for name in (
                "SuperFatJetAK15_pt",
                "SuperFatJetAK15PFCand_pt",
                "SuperFatJetAK15PFCand_srcPackedCandIdx",
                "SuperFatJetAK15GenCand_pt",
                "SuperFatJetAK15GenCand_srcGenCandIdx",
            ):
                if name not in branches(reference):
                    continue
                left = values(reduced, name)
                right = values(reference, name)
                require(len(left) == len(right), "%s differs from reference" % name)
                require(all(close(float(a), float(b)) for a, b in zip(left, right)),
                        "%s differs from reference" % name)

    print("events=%d" % expected)
    print("checked_events=%d" % len(entries))
    print("ordinary_branches_preserved=1")
    print("leading_ak15_valid=1")
    print("pf_candidates=%d" % pf_total)
    print("gen_candidates=%d" % gen_total)
    print("legacy_subjet_rows_preserved=%d" % subjet_total)
    print("reference_match=%d" % (1 if reference else 0))


if __name__ == "__main__":
    main()
