# AK15 NanoAOD Extras and Flat-Tree Selection

This project has two connected stages:

1. Produce a normal NanoAOD file from MiniAOD, while adding AK15 jet, PF-constituent, and gen-constituent branches.
2. Read that enriched NanoAOD and make a smaller flat ROOT tree for ML training, selecting only the leading AK15 jet that passes the current analysis cuts.

The standard NanoAOD content is kept. The extra AK15 branches are added alongside it so later training/inference output can be joined back to both reconstructed and generator-level information.

## Environment

Use the CMSSW release area on the cluster, not a local Windows environment.

```bash
ssh login03
cd /nfs_scratch/pkhalili2/AddingAK15/CMSSW_10_6_17/src
source /cvmfs/cms.cern.ch/cmsset_default.sh
cmsenv
```

Build after changing C++ code:

```bash
scram b -j 8
```

`login03` is the intended EL7 machine for this CMSSW release. If running from another host, CMSSW may report missing slc7 libraries such as `libnsl.so.1`.

## Stage 1: MiniAOD to Enriched NanoAOD

Main files:

- `NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py`
- `MyAnalysis/AK15NanoExtras/plugins/AK15ConstituentTableProducer.cc`
- `MyAnalysis/AK15NanoExtras/plugins/BuildFile.xml`
- `run_nano_from_txt.sh`

This stage starts from MiniAOD and runs the standard NanoAOD MC workflow. It also uses JetToolbox to build AK15 CHS PAT jets:

```text
selectedPatJetsAK15PFCHS
```

Then it writes these extra NanoAOD tables:

```text
SuperFatJetAK15
SuperFatJetAK15PFCand
SuperFatJetAK15GenCand
```

### What Comes From JME vs This Project

JME/JetToolbox builds the AK15 jet collection and substructure ingredients.

This project adds the extra NanoAOD tables through:

```text
AK15ConstituentTableProducer.cc
```

That plugin reads `selectedPatJetsAK15PFCHS` and writes:

- an extension onto `SuperFatJetAK15`
- a PF constituent table named `SuperFatJetAK15PFCand`
- a gen constituent table named `SuperFatJetAK15GenCand`

The plugin module label in the config is intentionally singular:

```python
process.ak15ConstituentTable = cms.EDProducer(...)
```

NanoAOD output keeps modules matching:

```text
keep nanoaodFlatTable_*Table_*_*
```

So the module label must end in `Table`; otherwise the branches are produced but dropped from the final NanoAOD output.

### AK15 Jet-Level Branches

`SuperFatJetAK15_*` contains the AK15 jet information. Examples include:

```text
nSuperFatJetAK15
SuperFatJetAK15_pt
SuperFatJetAK15_eta
SuperFatJetAK15_phi
SuperFatJetAK15_mass
SuperFatJetAK15_tau1
SuperFatJetAK15_tau2
SuperFatJetAK15_tau3
SuperFatJetAK15_tau4
SuperFatJetAK15_btag_pfDeepCSVJetTags_probb
SuperFatJetAK15_btag_pfDeepCSVJetTags_probbb
SuperFatJetAK15_btag_pfDeepCSVJetTags_probc
SuperFatJetAK15_btag_pfDeepCSVJetTags_probudsg
```

The custom plugin also appends these jet-level extension branches:

```text
SuperFatJetAK15_nPFConstituents
SuperFatJetAK15_nGenConstituents
SuperFatJetAK15_matchedGenJetExists
SuperFatJetAK15_matchedGenJetPt
SuperFatJetAK15_matchedGenJetEta
SuperFatJetAK15_matchedGenJetPhi
SuperFatJetAK15_matchedGenJetMass
SuperFatJetAK15_hadronFlavor
SuperFatJetAK15_partonFlavor
```

These are produced by `AK15ConstituentTableProducer.cc`, not by JME.

### How Reco to Gen Matching Works

The plugin does not perform a new matching algorithm. It uses the matching already stored in each `pat::Jet`:

```cpp
jet.genJet()
```

For each reco AK15 jet:

- `matchedGenJetExists` is `1` if `jet.genJet()` is non-null.
- `matchedGenJetPt/Eta/Phi/Mass` are copied from that matched gen jet.
- gen constituents are taken from the matched gen jet daughters:

```cpp
jet.genJet()->daughterPtr(i)
```

PF constituents are taken from the reco AK15 jet daughters:

```cpp
jet.daughterPtr(i)
```

Both PF and gen constituents are sorted by constituent `pt` inside each parent jet before being written.

### Constituent Indexing

For every event:

```text
nSuperFatJetAK15
```

is the number of AK15 jets. Each jet row is indexed from `0` to `nSuperFatJetAK15 - 1`.

PF constituents are stored in:

```text
nSuperFatJetAK15PFCand
SuperFatJetAK15PFCand_jetIdx
SuperFatJetAK15PFCand_candIdx
SuperFatJetAK15PFCand_srcPackedCandIdx
SuperFatJetAK15PFCand_pt
SuperFatJetAK15PFCand_eta
SuperFatJetAK15PFCand_phi
...
```

`SuperFatJetAK15PFCand_jetIdx[i]` points back to the parent AK15 jet row:

```python
jet_index = SuperFatJetAK15PFCand_jetIdx[i]
parent_pt = SuperFatJetAK15_pt[jet_index]
```

Gen constituents work the same way:

```text
nSuperFatJetAK15GenCand
SuperFatJetAK15GenCand_jetIdx
SuperFatJetAK15GenCand_candIdx
SuperFatJetAK15GenCand_srcGenCandIdx
SuperFatJetAK15GenCand_pt
...
```

`SuperFatJetAK15GenCand_jetIdx[i]` points back to the reco AK15 jet row whose matched gen jet supplied that gen constituent.

### Cuts in Stage 1

The custom `SuperFatJetAK15` Nano table currently does not apply an extra AK15 `pt` cut:

```python
cut = cms.string("")
```

This is intentional. The constituent tables index the full `SuperFatJetAK15` table. If a cut is applied to the jet table but not to the constituent producer, `jetIdx` values can stop matching the written jet rows.

Selection cuts for training are applied in Stage 2 instead.

### Running Stage 1 Directly

Example:

```bash
cmsRun NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py \
  inputFiles="file:/afs/hep.wisc.edu/home/pkhalili2/96621423_ExoHiggs_8b_UL18MiniAOD.root" \
  outputFile=test.root \
  maxEvents=5
```

The config applies:

```python
process.maxEvents.input = cms.untracked.int32(options.maxEvents)
```

so `maxEvents=5` really processes 5 events.

Depending on CMSSW `VarParsing`, the output name may receive extra suffixes such as `numEvent5`. Check the actual file name with:

```bash
ls -lh *Nano*.root
```

### Running Stage 1 From a Text File

Put one or more input files in a text file, one per line. Blank lines and lines starting with `#` are ignored. The script currently uses the first valid input line.

Example `one_file.txt`:

```text
file:/afs/hep.wisc.edu/home/pkhalili2/96621423_ExoHiggs_8b_UL18MiniAOD.root
```

Run:

```bash
bash run_nano_from_txt.sh one_file.txt my_output_tag
```

The script expands this into:

```bash
cmsRun NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py \
  inputFiles="$input_file" \
  outputFile="my_output_tag.root"
```

### Enabling Debug Prints

In `NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py`, the producer has:

```python
debug = cms.bool(False)
debugMaxJets = cms.uint32(5)
```

Set `debug = cms.bool(True)` to print, per event:

- number of AK15 jets
- total saved PF constituents
- total saved gen constituents
- for the first `debugMaxJets` jets: `pt`, `eta`, number of daughters, saved PF count, saved gen count, and matched-gen flag

### Stage 1 Validation

Inspect branches:

```bash
root -l output.root
```

Then:

```cpp
Events->Print("*SuperFatJetAK15*")
Events->Print("*PFCand*")
Events->Print("*GenCand*")
Events->Scan("nSuperFatJetAK15")
Events->Scan("nSuperFatJetAK15PFCand")
Events->Scan("nSuperFatJetAK15GenCand")
```

Sanity-check constituent parent indices:

```cpp
Events->Scan("nSuperFatJetAK15:Min$(SuperFatJetAK15PFCand_jetIdx):Max$(SuperFatJetAK15PFCand_jetIdx):Min$(SuperFatJetAK15GenCand_jetIdx):Max$(SuperFatJetAK15GenCand_jetIdx)")
```

For each event, the max PF/gen `jetIdx` should be less than `nSuperFatJetAK15`.

## Stage 2: Enriched NanoAOD to Selected Flat Tree

Main files:

- `AK15NanoFlatTreeProducer.C`
- `run_ak15_nano_flat_tree.sh`

This stage reads the enriched NanoAOD from Stage 1 and produces a smaller flat ROOT tree for ML training.

It is a standalone ROOT C++ macro, not a CMSSW EDAnalyzer. That is intentional because the input is now a flat NanoAOD `TTree`, not MiniAOD EDM collections.

### Running Stage 2

Use the CMSSW environment on `login03`, then run:

```bash
bash run_ak15_nano_flat_tree.sh input_enriched_nano.root ak15_selected.root
```

Full usage:

```bash
bash run_ak15_nano_flat_tree.sh input_nano.root output_selected.root [isSignal=1] [maxEvents=-1] [sourceLabel]
```

Arguments:

| Argument | Meaning | Default |
| --- | --- | --- |
| `input_nano.root` | Enriched NanoAOD from Stage 1 | required |
| `output_selected.root` | Output flat ROOT file | required |
| `isSignal` | Stored as `is_signal_new` | `1` |
| `maxEvents` | Max input entries to process; `-1` means all | `-1` |
| `sourceLabel` | Optional dataset/chunk label stored in the output tree | input file basename |

Example:

```bash
bash run_ak15_nano_flat_tree.sh \
  codex_max5_v2_numEvent5_Nano_numEvent5.root \
  ak15_selected_test.root \
  1 \
  -1
```

The first time it runs, ROOT ACLiC compiles the macro and creates files like:

```text
AK15NanoFlatTreeProducer_C.so
AK15NanoFlatTreeProducer_C.d
AK15NanoFlatTreeProducer_C_ACLiC_dict_rdict.pcm
```

Those are build artifacts and can be regenerated.

The Stage 2 input can also be a text file of enriched NanoAOD ROOT files, one
per line. Blank lines and lines beginning with `#` are ignored:

```bash
bash run_ak15_nano_flat_tree.sh enriched_nano_chunks.txt ak15_selected.root 1 -1 signal_8b_merged
```

### Stage 2 Selection

For each event, the selector loops over `SuperFatJetAK15` jets and requires:

```text
SuperFatJetAK15_pt > 170
abs(SuperFatJetAK15_eta) < 3.0
```

It then requires at least one valid opposite-side lepton.

Muon criteria:

```text
Muon_pt > 30
abs(Muon_eta) < 2.5
Muon_pfRelIso04_chg < 0.3
abs(deltaPhi(AK15 jet, muon)) > 1.5
```

If `Muon_pfRelIso04_chg` is unavailable, the code falls back to `Muon_pfRelIso03_chg`; if needed, it can fall back to the corresponding `_all` branch.

Electron criteria:

```text
Electron_pt > 30
abs(Electron_eta) < 2.5
Electron_pfRelIso03_chg < 0.3
abs(deltaPhi(AK15 jet, electron)) > 1.5
```

The leading passing AK15 jet is selected. Events with no passing AK15 jet are dropped. No `-999` placeholder rows are written for failed events.

### Stage 2 Output Tree

The output file contains one tree:

```text
Events
```

Important event-level bridge branches:

```text
run
luminosityBlock
event
sourceLabel
inputEntry
selectedJetIdx
nInputAK15
nInputPFCand
nInputGenCand
ttv
is_signal_new
```

`inputEntry` is the entry number in the enriched NanoAOD input tree.

`sourceLabel` is useful for Condor chunk outputs. After hadding many flat files,
use `sourceLabel` together with `inputEntry`, `selectedJetIdx`, and the
constituent row bridge branches to identify which enriched NanoAOD chunk the
flat row came from.

`selectedJetIdx` is the selected AK15 jet row in the original `SuperFatJetAK15_*` arrays.

`ttv` is the deterministic train/validation/test split:

```text
0 = train
1 = validation
2 = test
```

The split is based on the selected-event counter:

```text
every 10th selected event -> test
every 9th selected event -> validation
all others -> train
```

### Selected Jet Branches

The selected AK15 jet is stored as scalar branches:

```text
jet_pt
jet_eta
jet_phi
jet_mass
jet_energy
jet_px
jet_py
jet_pz
jet_p
jet_tau1
jet_tau2
jet_tau3
jet_tau4
jet_btagDeepCSV_probb
jet_btagDeepCSV_probbb
jet_btagDeepCSV_probc
jet_btagDeepCSV_probudsg
matchedGenJetExists
matchedGenJetPt
matchedGenJetEta
matchedGenJetPhi
matchedGenJetMass
jetNPFConstituents
jetNGenConstituents
jetHadronFlavor
jetPartonFlavor
```

Legacy-compatible aliases are also written:

```text
truthPX
truthPY
truthPZ
truthE
E_tot
PX_tot
PY_tot
PZ_tot
P_tot
Eta_tot
Phi_tot
idx
origIdx
```

### Selected Lepton Branches

The lepton that satisfied the opposite-side requirement is stored as:

```text
selectedLeptonPdgId
selectedLeptonIdx
selectedLeptonPt
selectedLeptonEta
selectedLeptonPhi
selectedLeptonIso
selectedLeptonDeltaPhi
```

`selectedLeptonPdgId` is `13` for muons and `11` for electrons.

### PF Constituent Branches

Only PF constituents belonging to the selected leading AK15 jet are written:

```text
nPart
Part_E
Part_PX
Part_PY
Part_PZ
Part_E_log
Part_P
Part_P_log
Part_Etarel
Part_Phirel
Part_pt
Part_eta
Part_phi
Part_mass
Part_pdgId
Part_charge
Part_fromPV
Part_candIdx
Part_srcPackedCandIdx
Part_inputRow
```

`Part_inputRow[k]` is the row index in the original enriched NanoAOD constituent table:

```text
SuperFatJetAK15PFCand_*
```

This means a selected flat-tree particle can be joined back to the original NanoAOD row using:

```text
run/luminosityBlock/event/inputEntry
selectedJetIdx
Part_inputRow
```

The code only includes rows where:

```text
SuperFatJetAK15PFCand_jetIdx == selectedJetIdx
```

### Gen Constituent Branches

Only gen constituents associated with the selected AK15 jet are written:

```text
nGenPart
GenPart_pt
GenPart_eta
GenPart_phi
GenPart_mass
GenPart_energy
GenPart_px
GenPart_py
GenPart_pz
GenPart_pdgId
GenPart_charge
GenPart_status
GenPart_candIdx
GenPart_srcGenCandIdx
GenPart_inputRow
```

`GenPart_inputRow[k]` is the row index in:

```text
SuperFatJetAK15GenCand_*
```

The code only includes rows where:

```text
SuperFatJetAK15GenCand_jetIdx == selectedJetIdx
```

### Stage 2 Validation

Run:

```bash
root -l ak15_selected.root
```

Inspect the tree:

```cpp
Events->Print()
Events->Scan("run:luminosityBlock:event:inputEntry:selectedJetIdx:nInputAK15:jet_pt:selectedLeptonPdgId:selectedLeptonDeltaPhi:nPart:nGenPart:ttv")
```

The selected jets should satisfy:

```text
jet_pt > 170
selectedJetIdx >= 0
selectedJetIdx < nInputAK15
nPart > 0
```

To verify the bridge arrays:

```cpp
std::vector<int>* pfRows = 0;
std::vector<int>* genRows = 0;
Events->SetBranchAddress("Part_inputRow", &pfRows);
Events->SetBranchAddress("GenPart_inputRow", &genRows);
Events->GetEntry(0);
pfRows->size();
genRows->size();
```

## Example End-to-End Workflow

From the CMSSW `src` directory on `login03`:

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
cmsenv
scram b -j 8
```

Produce enriched NanoAOD:

```bash
cmsRun NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py \
  inputFiles="file:/afs/hep.wisc.edu/home/pkhalili2/96621423_ExoHiggs_8b_UL18MiniAOD.root" \
  outputFile=ak15_enriched.root \
  maxEvents=5
```

Find the actual output:

```bash
ls -lh *Nano*.root
```

Make the selected flat tree:

```bash
bash run_ak15_nano_flat_tree.sh \
  ak15_enriched_Nano.root \
  ak15_selected.root \
  1 \
  -1
```

Inspect:

```bash
root -l ak15_selected.root
```

```cpp
Events->Print()
Events->Scan("event:selectedJetIdx:jet_pt:nPart:nGenPart:ttv")
```

## Condor Mass Processing

The `condor/` directory contains a batch workflow for large MiniAOD or enriched
NanoAOD datasets. It generates one non-overlapping file list per job, packages
the needed CMSSW source code, runs in a fresh worker-node CMSSW area, and copies
ROOT outputs to the requested output directory. Condor only transfers the small
job report and an output tarball back; direct copies to remote storage are
attempted only when that path is writable from the worker.

`CMSSW_10_6_17` is an EL7-era release. The worker script therefore tries to
re-exec itself inside the standard CMSSW RHEL7 Singularity/Apptainer image:

```text
/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel7
```

Set `USE_SINGULARITY=0` only if you deliberately want to require a native EL7
worker environment.

Main files:

- `condor/submit_all.sh` - user-facing driver
- `condor/make_filelists.py` - creates chunk lists and `job_table.txt`
- `condor/package_project.sh` - packages `MyAnalysis`, `JMEAnalysis`, the Stage 1 config, and the Stage 2 macro
- `condor/submit.sub` - HTCondor submit description
- `condor/run.sh` - worker-node executable
- `condor/unpack_outputs.sh` - unpacks returned tarballs and organizes ROOT files
- `condor/hadd_by_size.sh` - hadds ROOT files into size-capped consolidated outputs

### Test on Two Small Jobs

From the CMSSW `src` directory on `login03`:

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
cmsenv
scram b -j 8

bash condor/submit_all.sh \
  --tag signal_8b_test \
  --input /hdfs/store/user/abdollah/ExoHiggs/MiniAOD_8bjets \
  --mode both \
  --is-signal 1 \
  --files-per-job 1 \
  --limit-jobs 2 \
  --max-events 5 \
  --output-dir /nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b_test
```

This submits only two jobs, each with one input file and `maxEvents=5`. To
prepare everything without submitting:

```bash
bash condor/submit_all.sh ... --no-submit
```

To ask Condor to parse the submit file without queueing jobs:

```bash
bash condor/submit_all.sh ... --dry-run
```

Monitor jobs:

```bash
condor_q
condor_q -better-analyze <cluster.id>
```

### Production HDFS Example

For the signal MiniAOD directory, 20 files per job, up to 100 jobs:

```bash
bash condor/submit_all.sh \
  --tag signal_8b \
  --input /hdfs/store/user/abdollah/ExoHiggs/MiniAOD_8bjets \
  --mode both \
  --is-signal 1 \
  --files-per-job 20 \
  --limit-jobs 100 \
  --max-events -1 \
  --output-dir /hdfs/store/user/pkhalili2/ML-MINIAOD-Processing/signal_8b
```

HDFS inputs are written to the chunk files as `file:/hdfs/...`, and the submit
file automatically requires worker nodes advertising `HAS_CMS_HDFS`. The job
writes ROOT files in its local scratch directory first, then copies them to the
output directory.

If HDFS-mounted worker slots are scarce, the same `/hdfs/store/...` directory
can be discovered on the login node but written to chunk lists as Wisconsin
xrootd URLs instead:

```bash
bash condor/submit_all.sh \
  --tag signal_8b_xrd \
  --input /hdfs/store/user/abdollah/ExoHiggs/MiniAOD_8bjets \
  --input-prefix xrootd-wisc \
  --require-hdfs 0 \
  --mode both \
  --is-signal 1 \
  --files-per-job 20 \
  --limit-jobs 100 \
  --output-dir davs://cmsxrootd.hep.wisc.edu:1094/store/user/pkhalili2/ML-MINIAOD-Processing/signal_8b_xrd \
  --use-x509
```

If xrootd reports `Auth failed`, refresh a CMS proxy with `voms-proxy-init` and
add `--use-x509`. Direct `file:/hdfs/...` input does not need xrootd auth, but
it does need an HDFS-mounted worker slot. Likewise, direct `/hdfs/...` output
needs an HDFS-mounted worker; use a `davs://...` output directory plus
`--use-x509` when running without `--require-hdfs`.

### Official CMS DAS or xrootd Inputs

For official CMS MiniAOD datasets, create or refresh a proxy first:

```bash
voms-proxy-init --voms cms --valid 192:00
```

Then submit with `--use-x509`. A DAS dataset name is resolved with
`dasgoclient`, and `/store/...` file names are prefixed with
`root://cms-xrd-global.cern.ch/` by default:

```bash
bash condor/submit_all.sh \
  --tag TTToSemiLeptonic \
  --input /TTToSemiLeptonic_TuneCP5_13TeV-powheg-pythia8/RunIISummer20UL18MiniAODv2-106X_upgrade2018_realistic_v16_L1v1-v2/MINIAODSIM \
  --mode both \
  --is-signal 0 \
  --files-per-job 20 \
  --limit-jobs 100 \
  --output-dir /hdfs/store/user/pkhalili2/ML-MINIAOD-Processing/TTToSemiLeptonic \
  --use-x509
```

### Condor Modes

`--mode phase1` reads MiniAOD and writes enriched NanoAOD only.

`--mode phase2` reads enriched NanoAOD files and writes selected flat trees only.

`--mode both` runs Stage 1 and then Stage 2 inside each job. In this mode
`--max-events` applies to Stage 1; Stage 2 processes the produced NanoAOD file.

The chunk lists and manifest are written under:

```text
condor/.generated/<tag>/
```

### Returned Outputs

Each Condor job returns:

```text
root_outputs_<tag>_<chunk>.tgz
```

For example, a dataset with 1115 files and `--files-per-job 20` produces 56
jobs and therefore 56 returned tarballs. Each tarball contains the ROOT files
for that chunk:

- `nano_<tag>_<chunk>.root` for Stage 1 output when `--save-nano 1`
- `flat_<tag>_<chunk>.root` for Stage 2 output

Unpack and organize all tarballs from one output directory:

```bash
bash condor/unpack_outputs.sh /nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b
```

This creates:

```text
/nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b/nano_ntuples/
/nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b/flat_ntuples/
```

Files with unexpected names are moved to `other_root/`.

For jobs that run on CHTC-style workers, `/nfs_scratch` is not mounted inside
the job. In that case the job logs a warning for direct copies and relies on
Condor's output transfer tarball. This is expected.

### Hadding Outputs

The flat outputs can be hadded normally:

```bash
bash condor/unpack_outputs.sh /nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b
hadd -f flat_signal_8b.root /nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b/flat_ntuples/*.root
```

To keep training inputs bounded in size, use the size-capped hadd helper. This
groups input ROOT files by their summed input size and writes as many
consolidated files as needed:

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
cmsenv

bash condor/hadd_by_size.sh \
  /nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b/flat_ntuples \
  /nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b/hadd_flat \
  flat_signal_8b \
  6G

bash condor/hadd_by_size.sh \
  /nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b/nano_ntuples \
  /nfs_scratch/pkhalili2/ak15_condor_outputs/signal_8b/hadd_nano \
  nano_signal_8b \
  6G
```

The `6G` limit controls the approximate input bytes per `hadd` group. The
final output size can differ because ROOT compression changes during hadding.

`hadd` preserves the tree branches. Since `inputEntry` is local to the enriched
NanoAOD file processed by one Condor chunk, keep `sourceLabel` in the flat tree
when joining hadded flat outputs back to enriched NanoAOD chunks.

### Count Events

Count entries in phase 1 or phase 2 outputs:

```bash
python scripts/count_events.py /hdfs/store/user/pkhalili2/ML-MINIAOD-Processing/signal_8b/*.root
```

The script prints per-file entries, a total, and a simple phase classification
based on the branches present in the `Events` tree.

## Customization Guide

### Change the AK15 Production Input

In `NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py`, the custom producer reads:

```python
jets = cms.InputTag("selectedPatJetsAK15PFCHS")
```

Only change this if the AK15 collection label changes.

### Change the Stage 2 Jet Cuts

Edit `AK15NanoFlatTreeProducer.C` in the jet-selection loop:

```cpp
if (jet_pt[j] <= 170.0f || std::abs(jet_eta[j]) >= 3.0f) {
  continue;
}
```

### Change the Stage 2 Lepton Cuts

Edit the muon/electron requirements in `AK15NanoFlatTreeProducer.C`:

```cpp
pt > 30
abs(eta) < 2.5
iso < 0.3
abs(deltaPhi) > 1.5
```

### Change the Train/Validation/Test Split

Edit:

```cpp
int splitLabel(long long selectedCount)
```

Current behavior:

```text
mod 10 == 0 -> test
mod 10 == 9 -> validation
otherwise -> train
```

### Run on Background Samples

Pass `isSignal=0` to Stage 2:

```bash
bash run_ak15_nano_flat_tree.sh input.root selected_background.root 0 -1
```

This writes:

```text
is_signal_new = 0
```

### Limit the Number of Events

Stage 1:

```bash
cmsRun ... maxEvents=100
```

Stage 2:

```bash
bash run_ak15_nano_flat_tree.sh input.root output.root 1 100
```

## Notes for Future ParticleNet Inference

This project does not yet run ParticleNet inference. It prepares the input features and preserves enough indexing to join inference output later.

For event-level model scores, join using:

```text
run
luminosityBlock
event
inputEntry
selectedJetIdx
```

For particle-level model scores, also keep the particle row bridge:

```text
Part_inputRow
GenPart_inputRow
Part_candIdx
GenPart_candIdx
```

That makes it possible to answer:

- which input NanoAOD event produced this training row
- which AK15 jet was selected
- which PF constituents were fed to the model
- which gen constituents/matched gen jet were associated with that reco AK15 jet

## Generated Files

Common generated files include:

```text
*_Nano*.root
ak15_selected*.root
AK15NanoFlatTreeProducer_C.so
AK15NanoFlatTreeProducer_C.d
AK15NanoFlatTreeProducer_C_ACLiC_dict_rdict.pcm
```

The ROOT files are analysis outputs. The `AK15NanoFlatTreeProducer_C.*` files are ROOT ACLiC build products and can be regenerated.
