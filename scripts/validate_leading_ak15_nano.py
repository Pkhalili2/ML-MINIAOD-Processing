#!/usr/bin/env python
from __future__ import print_function

import argparse
import math

import ROOT


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def branch_names(tree):
    return {branch.GetName() for branch in tree.GetListOfBranches()}


def sampled_entries(total, limit):
    if limit < 0 or limit >= total:
        return list(range(total))
    if limit == 0:
        return []
    if limit == 1:
        return [0]
    return sorted({int(round(index * (total - 1.0) / (limit - 1))) for index in range(limit)})


def main():
    parser = argparse.ArgumentParser(
        description="Validate a leading-only AK15 NanoAOD without requiring its MiniAOD source."
    )
    parser.add_argument("input")
    parser.add_argument("--expected-events", type=int)
    parser.add_argument("--check-events", type=int, default=1000)
    parser.add_argument("--require-original-ht", action="store_true")
    parser.add_argument("--require-branch", action="append", default=[])
    args = parser.parse_args()

    source = ROOT.TFile.Open(args.input)
    require(source and not source.IsZombie(), "input ROOT file is unreadable")
    tree = source.Get("Events")
    require(tree, "Events tree is missing")

    entries = tree.GetEntries()
    if args.expected_events is not None:
        require(entries == args.expected_events, "event count does not match DAS metadata")

    branches = branch_names(tree)
    ordinary = {
        "run",
        "luminosityBlock",
        "event",
        "nMuon",
        "Muon_pt",
        "nJet",
        "Jet_pt",
        "MET_pt",
    }
    metadata = {
        "nSuperFatJetAK15",
        "SuperFatJetAK15_pt",
        "SuperFatJetAK15_leadingAK15SourceJetIdx",
        "SuperFatJetAK15_originalAK15Multiplicity",
        "SuperFatJetAK15PFCand_jetIdx",
    }
    if args.require_original_ht:
        metadata.add("SuperFatJetAK15_originalAK15HT")
    require(ordinary.issubset(branches), "ordinary NanoAOD or muon branches are missing")
    require(metadata.issubset(branches), "leading-only AK15 metadata is incomplete")
    require(
        set(args.require_branch).issubset(branches),
        "required branches are missing: %s"
        % ", ".join(sorted(set(args.require_branch) - branches)),
    )

    enabled = ordinary | metadata
    if "SuperFatJetAK15GenCand_jetIdx" in branches:
        enabled.add("SuperFatJetAK15GenCand_jetIdx")
    tree.SetBranchStatus("*", 0)
    for name in enabled:
        tree.SetBranchStatus(name, 1)

    checked = sampled_entries(entries, args.check_events)
    jets = 0
    pf_candidates = 0
    gen_candidates = 0
    for entry in checked:
        require(tree.GetEntry(entry) > 0, "failed to read event %d" % entry)
        multiplicity = int(tree.nSuperFatJetAK15)
        require(multiplicity <= 1, "event %d contains more than one AK15 jet" % entry)

        source_indices = list(tree.SuperFatJetAK15_leadingAK15SourceJetIdx)
        original_multiplicities = list(tree.SuperFatJetAK15_originalAK15Multiplicity)
        require(len(source_indices) == multiplicity, "source-index multiplicity is inconsistent")
        require(
            len(original_multiplicities) == multiplicity,
            "original-multiplicity metadata is inconsistent",
        )
        if multiplicity:
            require(original_multiplicities[0] >= 1, "original AK15 multiplicity is invalid")
            require(
                0 <= source_indices[0] < original_multiplicities[0],
                "leading AK15 source index is invalid",
            )
            jets += 1
            if args.require_original_ht:
                original_ht = list(tree.SuperFatJetAK15_originalAK15HT)
                require(len(original_ht) == 1, "original AK15 HT metadata is inconsistent")
                require(
                    not math.isnan(original_ht[0]) and not math.isinf(original_ht[0]),
                    "original AK15 HT is not finite",
                )
                require(
                    original_ht[0] + 1.0e-3 >= list(tree.SuperFatJetAK15_pt)[0],
                    "original AK15 HT is smaller than the retained leading-jet pT",
                )

        pf_indices = list(tree.SuperFatJetAK15PFCand_jetIdx)
        require(
            not pf_indices or multiplicity == 1,
            "PF constituents are present without a retained AK15 jet",
        )
        require(all(index == 0 for index in pf_indices), "PF constituent jet index is not remapped")
        pf_candidates += len(pf_indices)

        if "SuperFatJetAK15GenCand_jetIdx" in branches:
            gen_indices = list(tree.SuperFatJetAK15GenCand_jetIdx)
            require(
                not gen_indices or multiplicity == 1,
                "generator constituents are present without a retained AK15 jet",
            )
            require(
                all(index == 0 for index in gen_indices),
                "generator constituent jet index is not remapped",
            )
            gen_candidates += len(gen_indices)

    print("events=%d" % entries)
    print("checked_events=%d" % len(checked))
    print("ordinary_nanoaod_branches_present=1")
    print("events_with_ak15=%d" % jets)
    print("pf_candidates=%d" % pf_candidates)
    print("gen_candidates=%d" % gen_candidates)
    print("leading_only_metadata_valid=1")
    if args.require_branch:
        print("required_branches_present=%s" % ",".join(args.require_branch))


if __name__ == "__main__":
    main()
