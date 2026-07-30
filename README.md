# AK15 NanoAOD and Analysis Workflow

This repository produces constituent-enriched AK15 NanoAOD files from 2018
MiniAOD, reduces them to compact jet-level or analysis-level ROOT files, and
runs the corresponding HTCondor workflows.

The supported runtime is:

- `CMSSW_10_6_17`
- `SCRAM_ARCH=slc7_amd64_gcc700`
- an EL7-compatible CMS worker environment
- Python 3 for input discovery and metadata tools
- ROOT from the CMSSW release for the C++ reducers and plotting

## Repository Layout

```text
MyAnalysis/AK15NanoExtras/       CMSSW plugins for AK15 tables and leading-jet selection
JMEAnalysis/JetToolbox/          JetToolbox package used to build the AK15 collection
config/                          Event selection, luminosity mask, and sample metadata
condor/                          Dataset discovery, packaging, worker wrappers, and submit files
scripts/                         Luminosity, normalization, event-count, and plotting utilities
NanoIncludingAK15_*.py           Data and MC NanoAOD configurations
AK15NanoFlatTreeProducer.C       Phase-2 ML-oriented reducer
PhysicsAnalysisTreeProducer.C    Compact muon-plus-AK15 analysis reducer
```

Generated Condor state, ROOT files, compiled ROOT macros, caches, and returned
tarballs are excluded from version control.

## CMSSW Setup

Run the workflow on an EL7-compatible CMS machine.

```bash
export SCRAM_ARCH=slc7_amd64_gcc700
source /cvmfs/cms.cern.ch/cmsset_default.sh
cmsrel CMSSW_10_6_17
cd CMSSW_10_6_17/src
git clone <repository-url> .
cmsenv
scram b -j8
```

For an existing checkout:

```bash
cd /path/to/CMSSW_10_6_17/src
source /cvmfs/cms.cern.ch/cmsset_default.sh
cmsenv
scram b -j8
```

Remote CMS inputs require a valid proxy:

```bash
voms-proxy-init --voms cms --valid 144:00
voms-proxy-info -timeleft
```

## Stage 1: AK15 NanoAOD

The data and MC configurations recluster CHS AK15 jets, write the standard
NanoAOD tables, and add custom AK15 jet and constituent tables.

Run a short local data test:

```bash
cmsRun NanoIncludingAK15_UL18NanoAODv2_OnlyNano_data_cfg.py \
  inputFiles=file:/path/to/input_miniaod.root \
  outputFile=output.root \
  maxEvents=100 \
  ak15LeadingOnly=True
```

Run an MC test:

```bash
cmsRun NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py \
  inputFiles=root://cms-xrd-global.cern.ch//store/path/input.root \
  outputFile=output.root \
  maxEvents=100 \
  ak15LeadingOnly=True
```

`ak15LeadingOnly=True` keeps the globally highest-\(p_T\) AK15 jet in each
event and stores its PF and generator-level constituents. It does not apply
analysis kinematic or lepton cuts. The original row in the unreduced AK15
collection is recorded as `SuperFatJetAK15_leadingAK15SourceJetIdx`, and the
original jet multiplicity is recorded as
`SuperFatJetAK15_originalAK15Multiplicity`. The soft-drop subjet table is
restricted to subjets referenced by the leading jet and records both the
parent row and original subjet row.

The standard NanoAOD tables are unchanged by this option. Only the custom AK15
jet, soft-drop subjet, PF-constituent, and generator-constituent tables are
reduced.

`ak15LeadingOnly=False` retains the full custom AK15 jet and constituent
collections.

### Reducing Existing Full-AK15 NanoAOD

Existing constituent-rich NanoAOD files can be converted without rerunning the
MiniAOD production step. The reducer writes a new file and never modifies the
input:

```bash
bash run_reduce_ak15_nano_to_leading.sh \
  full_ak15_nano.root \
  leading_only_nano.root
```

The output has the same event count and retains the ordinary NanoAOD trees and
branches. It keeps the global highest-`pT` custom AK15 row and its PF and
generator constituents. The original jet index and multiplicity are recorded
in the same metadata branches used by native leading-only Stage 1 production.

Legacy full-AK15 files produced by this repository used the default output of
`selectedPatJetsAK15PFCHSSoftDropPacked` for `SuperFat_SubJetAK8`, rather than
its `SubJets` product. Those rows have no recoverable parent-jet association.
The reducer therefore preserves that small legacy table unchanged instead of
inventing an association. Newly produced leading-only files use the corrected
packed fat-jet source and contain the true associated SoftDrop subjets.

The optional third argument limits events for smoke tests; production
conversions should use the default `-1`.

Validate a conversion before expanding it:

```bash
python scripts/validate_reduced_ak15_nano.py \
  full_ak15_nano.root \
  leading_only_nano.root
```

For multi-gigabyte files, submit one source file per Condor job:

```bash
bash condor/submit_reduce_existing.sh \
  --tag wjets_ht100to200_leading_test \
  --input-list config/full_ak15_inputs.txt \
  --return-dir /nfs_scratch/$USER/wjets_ht100to200_leading_test \
  --limit-files 3
```

Each returned tarball contains one new reduced ROOT file. Inputs are opened
read-only and are never overwritten.

## Stage 2: ML-Oriented Reduction

`AK15NanoFlatTreeProducer.C` applies the jet selection used by the ML
preprocessing and writes a compact ROOT tree with one selected jet and its
constituent features.

```bash
bash run_ak15_nano_flat_tree.sh \
  input_nano.root \
  output_flat.root \
  0 \
  -1 \
  sample_label
```

The positional arguments after the output are `isSignal`, `maxEvents`, and
`sourceLabel`. Input can also be a text list prefixed with `@`.

For leading-only NanoAOD, the selected jet row is normally zero.
`selectedSourceJetIdx` preserves the original AK15 row before Stage-1
reduction.

## Compact Physics Analysis

`PhysicsAnalysisTreeProducer.C` creates small ROOT products for cutflows and
data/MC plots. The default cumulative selection is:

1. readable event;
2. certified run and luminosity section for data;
3. at least one input muon;
4. highest-\(p_T\) muon with \(p_T>30\) GeV, \(|\eta|<2.5\), and relative
   isolation below 0.3;
5. at least one AK15 jet and identify the global highest-\(p_T\) AK15 jet;
6. require that leading jet to have \(p_T>200\) GeV and \(|\eta|<3.0\);
7. require \(|\Delta\phi(\mu,\mathrm{leading\ AK15})|>1.5\);
8. write the selected event.

The tighter selection in `config/analysis_muon_2018_final_selection.json`
uses a tight muon with `pT > 55 GeV` and relative isolation below 0.15, then
adds these cumulative requirements:

1. reconstructed AK4 `HT > 200 GeV`, where HT is the scalar sum of `Jet_pt`
   for jets with `pT > 30 GeV`, `abs(eta) < 3.0`, and `Jet_jetId >= 2`;
2. `MET_pt > 30 GeV`;
3. muon-MET transverse mass above 50 GeV;
4. `abs(DeltaPhi(MET, leading AK15)) > 1.0`.

The existing leading-AK15 kinematic stage already requires the global leading
AK15 jet to have `pT > 200 GeV`. This also guarantees that the scalar sum of
AK15-jet transverse momenta exceeds 200 GeV, without requiring nonleading
AK15 candidates in leading-only NanoAOD.

The defaults are in `config/analysis_muon_2018.json` and can be overridden on
the command line:

```bash
bash run_physics_analysis_tree.sh \
  input_nano.root \
  analysis.root \
  --config config/analysis_muon_2018.json \
  --sample WJets_HT100to200 \
  --is-data 0 \
  --max-events -1
```

Use `--is-data 1` for collision data. The configured CMS Golden JSON is
applied only to data.

## Stage-1 Condor Submission

The submitter accepts a DAS dataset, directory, glob, text list, ROOT file, or
xrootd URL. Always prepare a one-job smoke test before a production campaign.

```bash
bash condor/submit_all.sh \
  --tag wjets_ht200to400_smoke \
  --input /WJetsToLNu_HT-200To400_TuneCP5_13TeV-madgraphMLM-pythia8/RunIISummer20UL18MiniAODv2-106X_upgrade2018_realistic_v16_L1v1-v1/MINIAODSIM \
  --mode phase1 \
  --config-type mc \
  --is-signal 0 \
  --files-per-job 1 \
  --limit-jobs 1 \
  --max-events 100 \
  --ak15-leading-only 1 \
  --use-x509 \
  --output-dir /hdfs/store/user/$USER/AK15/WJets_HT200to400 \
  --return-dir /nfs_scratch/$USER/ak15_returns/WJets_HT200to400 \
  --no-submit
```

Remove `--no-submit` after inspecting the generated table under
`condor/.generated/<tag>/`. Use `--dry-run` to render the final ClassAd without
submitting it.

Important settings:

| Option | Purpose |
| --- | --- |
| `--mode phase1\|phase2\|both` | Select Nano production, flat reduction, or both |
| `--config-type mc\|data` | Select the MC or data Nano configuration |
| `--files-per-job N` | Number of source files assigned to each process |
| `--limit-files N` | Restrict the campaign to the first `N` discovered files |
| `--limit-jobs N` | Restrict the number of generated processes |
| `--max-events N` | Event limit per job; `-1` processes all events |
| `--ak15-leading-only 0\|1` | Keep all AK15 jets or only the leading jet |
| `--save-nano 0\|1` | Persist the Stage-1 Nano output |
| `--use-x509` | Transfer the current CMS VOMS proxy |
| `--require-hdfs 0\|1\|auto` | Require a worker with the HDFS mount |
| `--input-prefix` | Control local, HDFS-xrootd, or unmodified input paths |
| `--prefetch-xrootd` | Copy xrootd Nano inputs on the worker host before entering EL7 |
| `--direct-output-files 0\|1` | Copy ROOT outputs to an xrootd output URL and return only an audit tarball |
| `--transfer-output-tarball 0\|1` | Disable Condor return transfer when all durable outputs are copied directly |
| `--log-dir` | Set the Condor stdout, stderr, and event-log directory; use `/dev/null` for direct-output campaigns |
| `--request-disk` | Condor scratch request in KB for Stage 1 |
| `--max-retries` | Automatic retries after nonzero payload exits |

Physics outputs should normally be written to HDFS. Condor logs and compact
return tarballs can be kept under NFS.

For Stage 2 on existing HDFS Nano files, use `--mode phase2`, one input file
per job, `--input-prefix xrootd-wisc`, `--prefetch-xrootd`, and
`--require-hdfs 0`. Only the compact flat ROOT products are returned.
When the flat products are too large for the Condor return filesystem, set an
xrootd `--output-dir` and add `--direct-output-files 1`; the ROOT file is then
written directly to that URL and Condor returns a small audit tarball.

## Analysis Condor Submission

The compact analysis submitter can read HDFS files through xrootd and prefetch
each source file with the worker host before entering the EL7 CMSSW runtime.

```bash
bash condor/submit_analysis_all.sh \
  --tag wjets_ht100to200_analysis \
  --input '/hdfs/store/user/'"$USER"'/AK15/WJets_HT100to200/nano_*.root' \
  --output-dir /nfs_scratch/$USER/ak15_analysis/WJets_HT100to200 \
  --files-per-job 1 \
  --is-data 0 \
  --input-prefix xrootd-wisc \
  --prefetch-xrootd \
  --use-x509 \
  --require-hdfs 0 \
  --limit-jobs 1 \
  --max-events 100
```

Use one source file per job when prefetching multi-GB Nano files so the worker
scratch request remains predictable.

For the tighter muon control-region selection and reconstructed event HT:

```bash
bash condor/submit_analysis_all.sh \
  --tag wjets_ht_analysis_tightid \
  --input '/hdfs/store/user/'"$USER"'/AK15/WJets_HT*/nano_*.root' \
  --output-dir root://cmsxrootd.hep.wisc.edu//store/user/$USER/AK15/analysis_tightid \
  --log-dir /hdfs/store/user/$USER/AK15/analysis_tightid/logs \
  --config config/analysis_muon_2018_tightid_ht.json \
  --files-per-job 1 \
  --is-data 0 \
  --muon-pt-min 55 \
  --muon-iso-max 0.15 \
  --muon-iso-branch Muon_pfRelIso04_all \
  --muon-id tight \
  --ht-jet-pt-min 30 \
  --ht-jet-eta-max 2.4 \
  --ht-jet-id-min 2 \
  --input-prefix xrootd-wisc \
  --prefetch-xrootd \
  --direct-output-files 1 \
  --use-x509 \
  --require-hdfs 0
```

The compact output stores `eventHT` and `eventHT4` as the scalar pT sum of ordinary AK4 jets
passing the configured pT, eta, and `Jet_jetId` requirements. It also stores
the selected muon's medium/tight ID decisions and an `AnalysisMetadata` tree
containing the exact selection configuration. The data and MC definitions of
`eventHT` are identical; generator HT is used only to label and normalize the
W+jets source samples.

New leading-only Nano files also store `SuperFatJetAK15_originalAK15HT`, the
scalar sum of all reconstructed AK15 jet transverse momenta before non-leading
rows are removed. The compact reducer writes this value as `eventHT15` and sets
`eventHT15IsComplete=1`. Full-AK15 inputs are summed directly. Older
leading-only files without this metadata are marked incomplete instead of
silently treating the retained leading jet as the full event sum.

For an AK4 eta-acceptance study, use
`config/analysis_muon_2018_eta_diagnostic.json`. After the tight-muon and
strict-leading-AK15 baseline (at least one AK15 jet is required, and the
global highest-pT jet is tested), the reducer fills
`ak4_jet_eta_preselection` for every reconstructed AK4 jet with
`pT > 30 GeV` and `Jet_jetId >= 2` before applying an AK4 eta requirement.
The same compact output includes MET and
`mT(mu,MET) = sqrt(2 pT(mu) MET [1-cos(DeltaPhi(mu,MET))])`. These are
diagnostic observables; the configuration does not impose HT, MET, or
transverse-mass cuts.

## Luminosity and Weighted Plots

Collect unique data run/luminosity sections:

```bash
python scripts/collect_analysis_lumis.py \
  /path/to/data/analysis_*.root \
  --output processed_lumis.json
```

Evaluate the recorded luminosity with the official CMS luminosity tools and
normtag, then pass the resulting value in inverse picobarns to the plotter.

Prepare a metadata table from the example:

```bash
cp config/samples_2018.example.csv config/samples_2018.csv
```

The current UL2018 W+jets, ttbar, and QCD normalization inputs are recorded in
`config/cross_sections_ul2018.csv`, including the provisional status of the
W+jets HT70-100 value. The active QCD entries cover HT200-300, 300-500,
500-700, 700-1000, 1000-1500, 1500-2000, and 2000-Inf.

For a reproducible file-complete MC subset, select files by event count rather
than taking the first fraction of a DAS file list:

```bash
python scripts/select_das_event_fraction.py \
  --dataset /QCD_HT300to500_TuneCP5_13TeV-madgraphMLM-pythia8/RunIISummer20UL18MiniAODv2-106X_upgrade2018_realistic_v16_L1v1-v2/MINIAODSIM \
  --fraction 0.10 \
  --seed qcd-ul18 \
  --cache campaign/das_qcd_ht300to500.json \
  --output campaign/qcd_ht300to500_10pct.txt \
  --metadata campaign/qcd_ht300to500_10pct.json
```

Use `--allowed-files` with a newline-delimited LFN list when the campaign must
be restricted to files verified at a particular disk RSE. The fraction target
is still calculated from the full DAS dataset event count.

Use `stack_group` and `stack_label` to combine separately normalized samples
into one displayed stack category. Set `cutflow_valid=0` for a sample whose
kinematic tree is usable but whose stored cutflow does not follow the current
cumulative convention; it will remain in distribution overlays and be omitted
from cutflow figures. A campaign-specific example is provided in
`config/samples_strictleading_2018_20260722.csv`.

Update each input path, cross section, and generator-weight sum, then run:

```bash
python scripts/make_weighted_plots.py \
  --metadata config/samples_2018.csv \
  --output-dir plots/physics_analysis \
  --lumi-pb <recorded-luminosity-pb>
```

Data events use unit weight. Simulated events use

```text
event weight = genWeight * luminosity * cross section / sumGenWeights
```

The plotting script stacks backgrounds, overlays data and signal, draws the MC
statistical uncertainty, writes cumulative cutflow and normalization CSV
files, and adds a `Data / sum(MC)` lower panel.

`config/samples_tightid_ht_with_qcd_2018_20260726.csv` is the tight-muon HT
configuration with the six QCD bins displayed as one `QCD multijet` stack
component. Each bin is normalized independently with its own cross section and
processed `sumGenWeights` before grouping. The QCD subset fraction does not
multiply the event weights; its smaller processed `sumGenWeights` supplies the
corresponding normalization to the inclusive process cross section.

Audit compact analysis outputs before plotting:

```bash
python scripts/audit_analysis_outputs.py \
  /path/to/analysis_outputs \
  --expected-files <count> \
  --require-lumis \
  --output-csv analysis_audit.csv
```

Omit `--require-lumis` for simulated samples.

## Validation

Before expanding a campaign:

1. compile the CMSSW plugins;
2. run 10-100 events locally;
3. confirm the output ROOT file opens and contains the expected tables;
4. submit one Condor process;
5. inspect its event log, stdout, stderr, exit code, and returned tarball;
6. verify the requested HDFS and NFS destinations;
7. estimate logical and replicated storage before increasing the job count.

For leading-only Stage-1 Nano outputs, run:

```bash
python scripts/validate_leading_ak15_nano.py \
  root://cmsxrootd.hep.wisc.edu//store/user/$USER/AK15/nano_sample.root \
  --expected-events <source-file-events> \
  --check-events 1000
```

This verifies the event count, ordinary NanoAOD and muon branches, at most one
custom AK15 row, leading-only metadata, and remapped PF/generator constituent
indices.

Do not treat a completed Condor process as successful until its returned ROOT
content has been validated.
