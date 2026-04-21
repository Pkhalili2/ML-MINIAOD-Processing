This repository extends the standard CMS NanoAOD workflow to include **particle-level (constituent-level) information for AK15 jets**, while preserving the full NanoAOD content.

The output is a single ROOT file containing:
- Standard NanoAOD branches (electrons, muons, jets, MET, etc.)
- AK15 jet collection (via JetToolbox)
- Additional flat tables for:
  - PF (reco-level) jet constituents
  - Gen-level jet constituents

---

## Overview of Method

The workflow consists of three main components:

1. **Standard NanoAOD production**
   - Runs the official NanoAOD sequence on MiniAOD input
   - Produces all default Nano branches

2. **AK15 jet reconstruction**
   - Uses JetToolbox to build AK15 jets:
     ```
     selectedPatJetsAK15PFCHS
     ```
   - These are included in the Nano output

3. **Custom FlatTable producer**
   - A custom CMSSW plugin (`AK15ConstituentTableProducer`)
   - Reads AK15 jets event-by-event
   - Writes additional Nano-style flat tables:
     - Jet-level extensions
     - PF constituent table (reco-level)
     - Gen constituent table (truth-level)

All data are stored in the same NanoAOD ROOT file and aligned per event.

---

## Output Structure

### AK15 Jet Table

```
SuperFatJetAK15_pt
SuperFatJetAK15_eta
SuperFatJetAK15_phi
SuperFatJetAK15_mass
SuperFatJetAK15_hadronFlavor
SuperFatJetAK15_partonFlavor

SuperFatJetAK15_nPFConstituents
SuperFatJetAK15_nGenConstituents
SuperFatJetAK15_matchedGenJetExists
SuperFatJetAK15_matchedGenJetPt
```

---

### PF Candidate Table (Reco-Level)

```
nSuperFatJetAK15PFCand

SuperFatJetAK15PFCand_pt
SuperFatJetAK15PFCand_eta
SuperFatJetAK15PFCand_phi
SuperFatJetAK15PFCand_mass
SuperFatJetAK15PFCand_energy
SuperFatJetAK15PFCand_px
SuperFatJetAK15PFCand_py
SuperFatJetAK15PFCand_pz

SuperFatJetAK15PFCand_pdgId
SuperFatJetAK15PFCand_charge
SuperFatJetAK15PFCand_fromPV

SuperFatJetAK15PFCand_dz
SuperFatJetAK15PFCand_dxy

SuperFatJetAK15PFCand_puppiWeight
SuperFatJetAK15PFCand_puppiWeightNoLep

SuperFatJetAK15PFCand_isElectron
SuperFatJetAK15PFCand_isMuon
SuperFatJetAK15PFCand_isPhoton
SuperFatJetAK15PFCand_isChargedHadron
SuperFatJetAK15PFCand_isNeutralHadron

SuperFatJetAK15PFCand_jetIdx
SuperFatJetAK15PFCand_candIdx
SuperFatJetAK15PFCand_srcPackedCandIdx
```

These represent the **reco-level particle cloud** used for ML.

---

### Gen Candidate Table (Truth-Level)

```
nSuperFatJetAK15GenCand

SuperFatJetAK15GenCand_pt
SuperFatJetAK15GenCand_eta
SuperFatJetAK15GenCand_phi
SuperFatJetAK15GenCand_mass
SuperFatJetAK15GenCand_energy

SuperFatJetAK15GenCand_pdgId
SuperFatJetAK15GenCand_charge
SuperFatJetAK15GenCand_status

SuperFatJetAK15GenCand_jetIdx
SuperFatJetAK15GenCand_candIdx
SuperFatJetAK15GenCand_srcGenCandIdx
```

These provide **truth-level supervision**.

---

## Matching Scheme

Each table is linked via indices:

- `jetIdx` → index of AK15 jet
- `candIdx` → local index within jet (sorted by pt)
- `srcPackedCandIdx` → original PF candidate index
- `srcGenCandIdx` → original gen particle index

Example:

To get PF constituents of jet `j`:
```
select rows where SuperFatJetAK15PFCand_jetIdx == j
```

---

## CMSSW Requirements

- CMSSW_10_6_17
- NanoAODv2 UL18 setup
- JetToolbox (JMEAnalysis)

---

## Running

Inside CMSSW:

```
cmsRun NanoIncludingAK15_UL18NanoAODv2_OnlyNano_mc_cfg.py \
  inputFiles="file:your_input.root" \
  outputFile=output.root \
  maxEvents=100
```

---

- full CMS event information
- reco-level particle clouds
- truth-level labels

in a single, analysis-ready ROOT file.
