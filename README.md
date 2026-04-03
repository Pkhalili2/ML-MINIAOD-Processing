# MINIAOD-Processing

This repository provides a CMSSW-based workflow for processing CMS MiniAOD files into a single ROOT output file containing two TTrees:

- `NanoTree`: high-level AK15 jet and event information
- `ParticleTree`: particle-level AK15 jet constituent information for later machine learning preprocessing

The workflow is split into two stages:

1. **CMSSW production stage**
   Read MiniAOD, cluster/build AK15 jets, extract jet- and particle-level information, and write one ROOT file.

2. **External preprocessing stage**
   Read the ROOT file produced by CMSSW and convert it into the final ML-ready format for training, validation, and testing (not in this repo).

---

## Repository purpose

This pipeline is intended to:

- Start from MiniAOD
- Build AK15 jets using JetToolbox
- Create one output ROOT file per job
- Write both a Nano-like summary tree and a particle-level tree into the same ROOT file
- Keep later ML preprocessing outside CMSSW

The output file is meant to be the source input for later ML preprocessing and model training.

---

## Output structure

Each successful run produces one ROOT file containing:

### `NanoTree`

A Nano-like tree with high-level event and AK15 jet information.

Branches include:

- `run`
- `lumi`
- `event`
- `hasAK15`
- `nAK15`
- `SuperFatJetAK15_pt`
- `SuperFatJetAK15_eta`
- `SuperFatJetAK15_phi`
- `SuperFatJetAK15_mass`
- `SuperFatJetAK15_tau1`
- `SuperFatJetAK15_tau2`
- `SuperFatJetAK15_tau3`
- `SuperFatJetAK15_tau4`
- `SuperFatJetAK15_area`
- `SuperFatJetAK15_btag_probb`
- `SuperFatJetAK15_btag_probbb`
- `SuperFatJetAK15_btag_probc`
- `SuperFatJetAK15_btag_probudsg`

### `ParticleTree`

A particle-level tree with constituent information from the leading AK15 jet.

Branches include:

- `run`
- `lumi`
- `event`
- `nPart`
- `Part_E`
- `Part_PX`
- `Part_PY`
- `Part_PZ`
- `Part_E_log`
- `Part_P`
- `Part_P_log`
- `Part_Etarel`
- `Part_Phirel`
- `truthPX`
- `truthPY`
- `truthPZ`
- `truthE`
- `E_tot`
- `PX_tot`
- `PY_tot`
- `PZ_tot`
- `P_tot`
- `Eta_tot`
- `Phi_tot`
- `is_signal_new`
- `idx`
- `origIdx`
- `ttv`

### `cutflow`

A histogram for basic event bookkeeping:

- Processed events
- Events with AK15 jets
- Events passing the reference AK15 jet `pT` threshold

---

## Overall what happens

```text
MiniAOD
  -> AK15 jet clustering/building inside CMSSW
  -> Nano-like high-level tree writing
  -> particle-level tree writing
  -> one ROOT file with NanoTree + ParticleTree
  -> separate preprocessing outside CMSSW
  -> ML-ready files
```

---

## Required environment

This is intended to run in:

- `CMSSW_10_6_17` or another CMSSW release compatible with the provided AK15/Nano configuration
- An EL7-compatible runtime environment for this CMSSW release

---

## Required packages and files

You need the following inside your CMSSW release area:

```text
CMSSW_10_6_17/src/
├── MyAnalysis/
│   └── AK8FlatTreeProducer/
│       ├── BuildFile.xml
│       └── plugins/
│           ├── BuildFile.xml
│           └── AK15FlatTreeProducer.cc
├── JMEAnalysis/
│   └── JetToolbox/
│       ├── python/
│       │   └── jetToolbox_cff.py
│       ├── plugins/
│       └── ...
└── condor/
    ├── AK15JetProducer_cfg.py
    ├── NanoIncludingAK15_plusFlatTree_cfg.py
    ├── run_cmssw_ak15.sh
    ├── submit_ak15.sub
    ├── submit_all.sh
    ├── make_filelists.sh
    ├── make_job_table.sh
    └── datasets.txt
```

---

## What each major file does

### `condor/AK15JetProducer_cfg.py`


- Load the Nano-era CMSSW process
- Run JetToolbox
- Create the AK15 PAT jet collection
- Add AK15-related Nano-era modules to the process


### `condor/NanoIncludingAK15_plusFlatTree_cfg.py`

- Load `AK15JetProducer_cfg.py`
- Override the input file list
- Set the output ROOT filename through `TFileService`
- Disable the separate official Nano EDM output file
- Add `AK15FlatTreeProducer`
- Ensure both `NanoTree` and `ParticleTree` are written into one ROOT file

### `MyAnalysis/AK8FlatTreeProducer/plugins/AK15FlatTreeProducer.cc`

This is the producer that writes the two TTrees and the cutflow histogram. Its role is to:

- Read the AK15 jet collection
- Choose the leading AK15 jet
- Write high-level AK15 variables into `NanoTree`
- Write particle-level constituent arrays into `ParticleTree`
- Write basic bookkeeping into `cutflow`

### `condor/run_cmssw_ak15.sh`

This is the Condor job wrapper. Its role is to:

- Create a CMSSW area inside the job
- Unpack the required code packages
- Compile
- Run `cmsRun`
- Produce one ROOT output file for that job

### `condor/submit_ak15.sub`

This is the HTCondor submit description. Its role is to:

- Define the executable
- Transfer the necessary input files
- Request resources
- Queue one job per file chunk

### `condor/make_filelists.sh`

This generates full file lists from DAS and splits them into chunk files.

### `condor/make_job_table.sh`

This creates `condor/job_table.txt`, which lists one Condor job per chunk.

### `condor/submit_all.sh`

This is the top-level submission script. Its role is to:

- Create needed tarballs
- Generate chunked file lists
- Generate the job table
- Submit all jobs

---

## Setup from scratch

### 1. Create the CMSSW area

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
source /afs/hep.wisc.edu/cms/setup/bashrc

export SCRAM_ARCH=slc7_amd64_gcc700

mkdir -p /nfs_scratch/$USER/AddingAK15
cd /nfs_scratch/$USER/AddingAK15
scramv1 project CMSSW CMSSW_10_6_17
cd CMSSW_10_6_17/src
```

If your host OS is newer than EL7, use the corresponding EL7-compatible CMSSW container before building and running.

### 2. Initialize the environment

```bash
cmsenv
```

### 3. Clone this repository into the CMSSW area

```bash
git clone https://github.com/Pkhalili2/P-Net-MINIAOD-Pre-Processing.git MyAnalysis
```

This should create:

```text
CMSSW_10_6_17/src/MyAnalysis/AK8FlatTreeProducer/...
```

### 4. Add JetToolbox

Unpack `JMEAnalysis.tar.xz` into `src` so that this exists:

```text
CMSSW_10_6_17/src/JMEAnalysis/JetToolbox/python/jetToolbox_cff.py
```

Example:

```bash
tar -xJf /path/to/JMEAnalysis.tar.xz
```

Then verify:

```bash
ls JMEAnalysis/JetToolbox/python/jetToolbox_cff.py
```

### 5. Create the `condor` helper directory if needed

```bash
mkdir -p condor
```

Place the required config and Condor helper files inside `src/condor/`.

### 6. Compile

```bash
scram b clean
scram b -j8
```

### 7. Verify the plugin is visible

```bash
edmPluginDump | grep -i AK15FlatTreeProducer
```

You should see `AK15FlatTreeProducer`.

---

## Local test run

### 1. Create a one-file input list

For example:

```bash
cat > one_file.txt <<'EOF'
/store/...
EOF
```

or, for a visible local path:

```bash
cat > one_file.txt <<'EOF'
/hdfs/store/user/.../somefile.root
EOF
```

The wrapper config will convert:

- `/store/...` to global xrootd paths
- `/hdfs/...` to `file:/hdfs/...`

### 2. Run `cmsRun`

```bash
cmsRun condor/NanoIncludingAK15_plusFlatTree_cfg.py \
    inputList=one_file.txt \
    flatOut=test.root \
    maxEvents=50 \
    isSignal=1 \
    fillAllEvents=1
```

### 3. Inspect the output

```bash
ls -lh test.root
root -l -q -e 'TFile f("test.root"); f.ls();'
```

Check entries:

```bash
root -l -q -e 'TFile f("test.root"); auto t=(TTree*)f.Get("NanoTree"); if(t) printf("NanoTree entries = %lld\n", t->GetEntries()); else printf("No NanoTree\n");'
root -l -q -e 'TFile f("test.root"); auto t=(TTree*)f.Get("ParticleTree"); if(t) printf("ParticleTree entries = %lld\n", t->GetEntries()); else printf("No ParticleTree\n");'
```

Check cutflow:

```bash
root -l -q -e 'TFile f("test.root"); auto h=(TH1I*)f.Get("cutflow"); if(h) h->Print("all"); else printf("No cutflow\n");'
```

---

## What happens when `cmsRun` is executed

When you run:

```bash
cmsRun condor/NanoIncludingAK15_plusFlatTree_cfg.py ...
```

the following happens:

1. The wrapper config parses the command-line options.
2. The wrapper loads the base AK15-building config `AK15JetProducer_cfg.py`.
3. The base config:
   - Creates the CMSSW process
   - Loads Nano-era services and conditions
   - Runs JetToolbox
   - Creates `selectedPatJetsAK15PFCHS`
   - Adds AK15-related modules to the process
4. The wrapper overrides:
   - `process.source.fileNames`
   - `process.maxEvents`
5. The wrapper disables the separate official Nano EDM output file.
6. The wrapper defines `TFileService` with your chosen output ROOT filename.
7. The wrapper adds `AK15FlatTreeProducer` to the AK15/Nano sequence.
8. During the event loop:
   - AK15 jets are built
   - The producer reads the AK15 collection
   - `NanoTree` is filled with high-level AK15 variables
   - `ParticleTree` is filled with constituent-level arrays
   - `cutflow` is updated
9. One ROOT file is written containing:
   - `NanoTree`
   - `ParticleTree`
   - `cutflow`

---

## Condor workflow (this is untested thus far)

### 1. Prepare the repository top level

At the top level of your repository, you should have:

```text
MyAnalysis/
condor/
JMEAnalysis.tar.xz
```

### 2. Generate DAS file lists and chunk them

```bash
FILES_PER_JOB=10 bash condor/make_filelists.sh
```

### 3. Build the Condor job table

```bash
bash condor/make_job_table.sh
```

This creates:

```text
condor/job_table.txt
```

### 4. Submit all jobs

```bash
bash condor/submit_all.sh
```

### 5. Monitor jobs

```bash
condor_q $USER
```

### 6. Inspect logs

```bash
tail -f logs/<dataset>_<chunk>.out
tail -f logs/<dataset>_<chunk>.err
```

---

## Expected Condor output

Each Condor job should produce:

```text
flat_<DATASET_TAG>_<CHUNK_ID>.root
```

Each such file should contain:

- `NanoTree`
- `ParticleTree`
- `cutflow`

These files can later be merged or preprocessed.

---

## What the later preprocessing stage should do

After CMSSW production, a separate preprocessing script should:

- Open the produced ROOT files
- Read `ParticleTree`
- Optionally use `NanoTree` for selection or bookkeeping
- Perform any ML-specific transformations:
  - Fixed-length padding or truncation
  - Normalization
  - Labeling
  - Train/validation/test split
- Write the final ML-ready files

This repository does not perform that preprocessing inside CMSSW.

---

## Common problems and checks

### `AK15FlatTreeProducer` not found

Check:

```bash
edmPluginDump | grep -i AK15FlatTreeProducer
```

If missing:

- Confirm both `BuildFile.xml` files exist
- Re-run `scram b clean && scram b -j8`

### `No module named JMEAnalysis`

JetToolbox is not in the correct place. Confirm:

```bash
ls JMEAnalysis/JetToolbox/python/jetToolbox_cff.py
```

### Zero processed events

The input file is empty. Check:

```bash
edmFileUtil file:/path/to/file.root
edmEventSize -a file:/path/to/file.root
```

---

## Minimal file summary

| File | Purpose |
|------|---------|
| `MyAnalysis/AK8FlatTreeProducer/plugins/AK15FlatTreeProducer.cc` | Writes `NanoTree`, `ParticleTree`, `cutflow` |
| `condor/AK15JetProducer_cfg.py` | Builds AK15 jets using JetToolbox |
| `condor/NanoIncludingAK15_plusFlatTree_cfg.py` | Wrapper that loads base cfg, overrides inputs, and attaches the producer |
| `condor/run_cmssw_ak15.sh` | Condor-side CMSSW build and run wrapper |
| `condor/submit_ak15.sub` | Condor submit description |
| `condor/make_filelists.sh` | DAS query and chunk generation |
| `condor/make_job_table.sh` | Builds `condor/job_table.txt` |
| `condor/submit_all.sh` | Top-level submission helper |

---

## Recommended first test

Use one known non-empty MiniAOD file and run:

```bash
cmsRun condor/NanoIncludingAK15_plusFlatTree_cfg.py \
    inputList=one_file.txt \
    flatOut=test.root \
    maxEvents=50 \
    isSignal=1 \
    fillAllEvents=1
```

Then verify:

- `test.root` exists
- `NanoTree` exists
- `ParticleTree` exists
- `cutflow` exists
