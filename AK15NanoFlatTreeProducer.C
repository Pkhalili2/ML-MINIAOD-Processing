#include "TBranch.h"
#include "TChain.h"
#include "TFile.h"
#include "TLorentzVector.h"
#include "TTree.h"
#include "TTreeReader.h"
#include "TTreeReaderArray.h"
#include "TTreeReaderValue.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr double kMissing = -999.0;
constexpr double kLogEps = 1e-6;

bool hasBranch(TTree* tree, const char* name) {
  return tree != nullptr && tree->GetBranch(name) != nullptr;
}

std::string trim(const std::string& value) {
  const std::string whitespace = " \t\r\n";
  const std::string::size_type begin = value.find_first_not_of(whitespace);
  if (begin == std::string::npos) {
    return "";
  }
  const std::string::size_type end = value.find_last_not_of(whitespace);
  return value.substr(begin, end - begin + 1);
}

bool endsWith(const std::string& value, const std::string& suffix) {
  return value.size() >= suffix.size() &&
         value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
}

std::string baseName(const std::string& path) {
  const std::string::size_type pos = path.find_last_of("/\\");
  if (pos == std::string::npos) {
    return path;
  }
  return path.substr(pos + 1);
}

int addInputs(TChain& chain, const char* inputSpec) {
  std::string spec = inputSpec ? inputSpec : "";
  if (spec.empty()) {
    return 0;
  }

  bool readList = false;
  if (spec[0] == '@') {
    spec = spec.substr(1);
    readList = true;
  } else if (endsWith(spec, ".txt") || endsWith(spec, ".list")) {
    readList = true;
  }

  if (!readList) {
    return chain.Add(spec.c_str());
  }

  std::ifstream inputs(spec.c_str());
  if (!inputs.is_open()) {
    std::cerr << "ERROR: could not open input list '" << spec << "'" << std::endl;
    return 0;
  }

  int added = 0;
  std::string line;
  while (std::getline(inputs, line)) {
    line = trim(line);
    if (line.empty() || line[0] == '#') {
      continue;
    }
    added += chain.Add(line.c_str());
  }
  return added;
}

void requireBranch(TTree* tree, const char* name) {
  if (!hasBranch(tree, name)) {
    throw std::runtime_error(std::string("Missing required branch: ") + name);
  }
}

template <typename T>
std::unique_ptr<TTreeReaderArray<T>> optionalArray(TTreeReader& reader, TTree* tree, const char* name) {
  if (!hasBranch(tree, name)) {
    return std::unique_ptr<TTreeReaderArray<T>>();
  }
  return std::unique_ptr<TTreeReaderArray<T>>(new TTreeReaderArray<T>(reader, name));
}

double deltaPhi(double phi1, double phi2) {
  double dphi = std::fmod(phi1 - phi2, 2.0 * M_PI);
  if (dphi > M_PI) {
    dphi -= 2.0 * M_PI;
  } else if (dphi <= -M_PI) {
    dphi += 2.0 * M_PI;
  }
  return dphi;
}

int safeInt(unsigned long long value) {
  if (value > static_cast<unsigned long long>(std::numeric_limits<int>::max())) {
    return -1;
  }
  return static_cast<int>(value);
}

int splitLabel(long long selectedCount) {
  const long long mod = selectedCount % 10;
  if (mod == 0) {
    return 2;  // test
  }
  if (mod == 9) {
    return 1;  // validation
  }
  return 0;  // train
}

double leptonIso(const std::unique_ptr<TTreeReaderArray<Float_t>>& preferred,
                 const std::unique_ptr<TTreeReaderArray<Float_t>>& fallback,
                 unsigned int idx) {
  if (preferred) {
    return (*preferred)[idx];
  }
  if (fallback) {
    return (*fallback)[idx];
  }
  return std::numeric_limits<double>::infinity();
}

}  // namespace

int AK15NanoFlatTreeProducer(const char* inputFile = "codex_max5_v2_numEvent5_Nano_numEvent5.root",
                             const char* outputFile = "ak15_selected.root",
                             int isSignal = 1,
                             Long64_t maxEvents = -1,
                             const char* sourceLabelArg = "") {
  TChain chain("Events");
  const int added = addInputs(chain, inputFile);
  if (added == 0) {
    std::cerr << "ERROR: no input files matched '" << inputFile << "'" << std::endl;
    return 1;
  }
  const std::string sourceLabel =
      (sourceLabelArg != nullptr && sourceLabelArg[0] != '\0') ? sourceLabelArg : baseName(inputFile);

  TTree* tree = &chain;

  const char* requiredBranches[] = {
      "run",
      "luminosityBlock",
      "event",
      "nMuon",
      "Muon_pt",
      "Muon_eta",
      "Muon_phi",
      "nElectron",
      "Electron_pt",
      "Electron_eta",
      "Electron_phi",
      "nSuperFatJetAK15",
      "SuperFatJetAK15_pt",
      "SuperFatJetAK15_eta",
      "SuperFatJetAK15_phi",
      "SuperFatJetAK15_mass",
      "SuperFatJetAK15_tau1",
      "SuperFatJetAK15_tau2",
      "SuperFatJetAK15_tau3",
      "SuperFatJetAK15_tau4",
      "SuperFatJetAK15_btag_pfDeepCSVJetTags_probb",
      "SuperFatJetAK15_btag_pfDeepCSVJetTags_probbb",
      "SuperFatJetAK15_btag_pfDeepCSVJetTags_probc",
      "SuperFatJetAK15_btag_pfDeepCSVJetTags_probudsg",
      "SuperFatJetAK15_matchedGenJetExists",
      "SuperFatJetAK15_matchedGenJetPt",
      "SuperFatJetAK15_matchedGenJetEta",
      "SuperFatJetAK15_matchedGenJetPhi",
      "SuperFatJetAK15_matchedGenJetMass",
      "SuperFatJetAK15_nPFConstituents",
      "SuperFatJetAK15_nGenConstituents",
      "SuperFatJetAK15_hadronFlavor",
      "SuperFatJetAK15_partonFlavor",
      "nSuperFatJetAK15PFCand",
      "SuperFatJetAK15PFCand_pt",
      "SuperFatJetAK15PFCand_eta",
      "SuperFatJetAK15PFCand_phi",
      "SuperFatJetAK15PFCand_mass",
      "SuperFatJetAK15PFCand_energy",
      "SuperFatJetAK15PFCand_px",
      "SuperFatJetAK15PFCand_py",
      "SuperFatJetAK15PFCand_pz",
      "SuperFatJetAK15PFCand_jetIdx",
      "SuperFatJetAK15PFCand_candIdx",
      "SuperFatJetAK15PFCand_srcPackedCandIdx",
      "SuperFatJetAK15PFCand_pdgId",
      "SuperFatJetAK15PFCand_charge",
      "SuperFatJetAK15PFCand_fromPV",
      "nSuperFatJetAK15GenCand",
      "SuperFatJetAK15GenCand_pt",
      "SuperFatJetAK15GenCand_eta",
      "SuperFatJetAK15GenCand_phi",
      "SuperFatJetAK15GenCand_mass",
      "SuperFatJetAK15GenCand_energy",
      "SuperFatJetAK15GenCand_px",
      "SuperFatJetAK15GenCand_py",
      "SuperFatJetAK15GenCand_pz",
      "SuperFatJetAK15GenCand_jetIdx",
      "SuperFatJetAK15GenCand_candIdx",
      "SuperFatJetAK15GenCand_srcGenCandIdx",
      "SuperFatJetAK15GenCand_pdgId",
      "SuperFatJetAK15GenCand_charge",
      "SuperFatJetAK15GenCand_status",
  };

  try {
    for (const char* branch : requiredBranches) {
      requireBranch(tree, branch);
    }
  } catch (const std::exception& err) {
    std::cerr << "ERROR: " << err.what() << std::endl;
    return 2;
  }

  TTreeReader reader(tree);

  TTreeReaderValue<UInt_t> run(reader, "run");
  TTreeReaderValue<UInt_t> luminosityBlock(reader, "luminosityBlock");
  TTreeReaderValue<ULong64_t> event(reader, "event");

  TTreeReaderValue<UInt_t> nMuon(reader, "nMuon");
  TTreeReaderArray<Float_t> muon_pt(reader, "Muon_pt");
  TTreeReaderArray<Float_t> muon_eta(reader, "Muon_eta");
  TTreeReaderArray<Float_t> muon_phi(reader, "Muon_phi");
  auto muon_iso_chg = optionalArray<Float_t>(reader, tree, "Muon_pfRelIso04_chg");
  if (!muon_iso_chg) {
    muon_iso_chg = optionalArray<Float_t>(reader, tree, "Muon_pfRelIso03_chg");
  }
  auto muon_iso_all = optionalArray<Float_t>(reader, tree, "Muon_pfRelIso04_all");

  TTreeReaderValue<UInt_t> nElectron(reader, "nElectron");
  TTreeReaderArray<Float_t> electron_pt(reader, "Electron_pt");
  TTreeReaderArray<Float_t> electron_eta(reader, "Electron_eta");
  TTreeReaderArray<Float_t> electron_phi(reader, "Electron_phi");
  auto electron_iso_chg = optionalArray<Float_t>(reader, tree, "Electron_pfRelIso03_chg");
  auto electron_iso_all = optionalArray<Float_t>(reader, tree, "Electron_pfRelIso03_all");

  TTreeReaderValue<UInt_t> nJet(reader, "nSuperFatJetAK15");
  TTreeReaderArray<Float_t> jet_pt(reader, "SuperFatJetAK15_pt");
  TTreeReaderArray<Float_t> jet_eta(reader, "SuperFatJetAK15_eta");
  TTreeReaderArray<Float_t> jet_phi(reader, "SuperFatJetAK15_phi");
  TTreeReaderArray<Float_t> jet_mass(reader, "SuperFatJetAK15_mass");
  TTreeReaderArray<Float_t> jet_tau1(reader, "SuperFatJetAK15_tau1");
  TTreeReaderArray<Float_t> jet_tau2(reader, "SuperFatJetAK15_tau2");
  TTreeReaderArray<Float_t> jet_tau3(reader, "SuperFatJetAK15_tau3");
  TTreeReaderArray<Float_t> jet_tau4(reader, "SuperFatJetAK15_tau4");
  TTreeReaderArray<Float_t> jet_btag_probb(reader, "SuperFatJetAK15_btag_pfDeepCSVJetTags_probb");
  TTreeReaderArray<Float_t> jet_btag_probbb(reader, "SuperFatJetAK15_btag_pfDeepCSVJetTags_probbb");
  TTreeReaderArray<Float_t> jet_btag_probc(reader, "SuperFatJetAK15_btag_pfDeepCSVJetTags_probc");
  TTreeReaderArray<Float_t> jet_btag_probudsg(reader, "SuperFatJetAK15_btag_pfDeepCSVJetTags_probudsg");
  TTreeReaderArray<Int_t> jet_matchedGenJetExists(reader, "SuperFatJetAK15_matchedGenJetExists");
  TTreeReaderArray<Float_t> jet_matchedGenJetPt(reader, "SuperFatJetAK15_matchedGenJetPt");
  TTreeReaderArray<Float_t> jet_matchedGenJetEta(reader, "SuperFatJetAK15_matchedGenJetEta");
  TTreeReaderArray<Float_t> jet_matchedGenJetPhi(reader, "SuperFatJetAK15_matchedGenJetPhi");
  TTreeReaderArray<Float_t> jet_matchedGenJetMass(reader, "SuperFatJetAK15_matchedGenJetMass");
  TTreeReaderArray<Int_t> jet_nPFConstituents(reader, "SuperFatJetAK15_nPFConstituents");
  TTreeReaderArray<Int_t> jet_nGenConstituents(reader, "SuperFatJetAK15_nGenConstituents");
  TTreeReaderArray<Int_t> jet_hadronFlavor(reader, "SuperFatJetAK15_hadronFlavor");
  TTreeReaderArray<Int_t> jet_partonFlavor(reader, "SuperFatJetAK15_partonFlavor");

  TTreeReaderValue<UInt_t> nPFCand(reader, "nSuperFatJetAK15PFCand");
  TTreeReaderArray<Float_t> pf_pt(reader, "SuperFatJetAK15PFCand_pt");
  TTreeReaderArray<Float_t> pf_eta(reader, "SuperFatJetAK15PFCand_eta");
  TTreeReaderArray<Float_t> pf_phi(reader, "SuperFatJetAK15PFCand_phi");
  TTreeReaderArray<Float_t> pf_mass(reader, "SuperFatJetAK15PFCand_mass");
  TTreeReaderArray<Float_t> pf_energy(reader, "SuperFatJetAK15PFCand_energy");
  TTreeReaderArray<Float_t> pf_px(reader, "SuperFatJetAK15PFCand_px");
  TTreeReaderArray<Float_t> pf_py(reader, "SuperFatJetAK15PFCand_py");
  TTreeReaderArray<Float_t> pf_pz(reader, "SuperFatJetAK15PFCand_pz");
  TTreeReaderArray<Int_t> pf_jetIdx(reader, "SuperFatJetAK15PFCand_jetIdx");
  TTreeReaderArray<Int_t> pf_candIdx(reader, "SuperFatJetAK15PFCand_candIdx");
  TTreeReaderArray<Int_t> pf_srcPackedCandIdx(reader, "SuperFatJetAK15PFCand_srcPackedCandIdx");
  TTreeReaderArray<Int_t> pf_pdgId(reader, "SuperFatJetAK15PFCand_pdgId");
  TTreeReaderArray<Int_t> pf_charge(reader, "SuperFatJetAK15PFCand_charge");
  TTreeReaderArray<Int_t> pf_fromPV(reader, "SuperFatJetAK15PFCand_fromPV");

  TTreeReaderValue<UInt_t> nGenCand(reader, "nSuperFatJetAK15GenCand");
  TTreeReaderArray<Float_t> gen_pt(reader, "SuperFatJetAK15GenCand_pt");
  TTreeReaderArray<Float_t> gen_eta(reader, "SuperFatJetAK15GenCand_eta");
  TTreeReaderArray<Float_t> gen_phi(reader, "SuperFatJetAK15GenCand_phi");
  TTreeReaderArray<Float_t> gen_mass(reader, "SuperFatJetAK15GenCand_mass");
  TTreeReaderArray<Float_t> gen_energy(reader, "SuperFatJetAK15GenCand_energy");
  TTreeReaderArray<Float_t> gen_px(reader, "SuperFatJetAK15GenCand_px");
  TTreeReaderArray<Float_t> gen_py(reader, "SuperFatJetAK15GenCand_py");
  TTreeReaderArray<Float_t> gen_pz(reader, "SuperFatJetAK15GenCand_pz");
  TTreeReaderArray<Int_t> gen_jetIdx(reader, "SuperFatJetAK15GenCand_jetIdx");
  TTreeReaderArray<Int_t> gen_candIdx(reader, "SuperFatJetAK15GenCand_candIdx");
  TTreeReaderArray<Int_t> gen_srcGenCandIdx(reader, "SuperFatJetAK15GenCand_srcGenCandIdx");
  TTreeReaderArray<Int_t> gen_pdgId(reader, "SuperFatJetAK15GenCand_pdgId");
  TTreeReaderArray<Int_t> gen_charge(reader, "SuperFatJetAK15GenCand_charge");
  TTreeReaderArray<Int_t> gen_status(reader, "SuperFatJetAK15GenCand_status");

  TFile output(outputFile, "RECREATE");
  if (output.IsZombie()) {
    std::cerr << "ERROR: could not create output file '" << outputFile << "'" << std::endl;
    return 3;
  }

  TTree out("Events", "Selected leading AK15 jets from enriched NanoAOD");

  UInt_t out_run = 0;
  UInt_t out_luminosityBlock = 0;
  ULong64_t out_event = 0;
  std::string out_sourceLabel = sourceLabel;
  Long64_t inputEntry = -1;
  Int_t selectedJetIdx = -1;
  Int_t nInputAK15 = 0;
  Int_t nInputPFCand = 0;
  Int_t nInputGenCand = 0;
  Int_t nPart = 0;
  Int_t nGenPart = 0;
  Int_t is_signal_new = isSignal;
  Int_t idx = -1;
  Int_t origIdx = -1;
  Int_t ttv = 0;
  Int_t selectedLeptonPdgId = 0;
  Int_t selectedLeptonIdx = -1;
  Float_t selectedLeptonPt = kMissing;
  Float_t selectedLeptonEta = kMissing;
  Float_t selectedLeptonPhi = kMissing;
  Float_t selectedLeptonIso = kMissing;
  Float_t selectedLeptonDeltaPhi = kMissing;

  Float_t jetPt = kMissing;
  Float_t jetEta = kMissing;
  Float_t jetPhi = kMissing;
  Float_t jetMass = kMissing;
  Float_t jetEnergy = kMissing;
  Float_t jetPx = kMissing;
  Float_t jetPy = kMissing;
  Float_t jetPz = kMissing;
  Float_t jetP = kMissing;
  Float_t jetTau1 = kMissing;
  Float_t jetTau2 = kMissing;
  Float_t jetTau3 = kMissing;
  Float_t jetTau4 = kMissing;
  Float_t jetBtagDeepCSVProbb = kMissing;
  Float_t jetBtagDeepCSVProbbb = kMissing;
  Float_t jetBtagDeepCSVProbc = kMissing;
  Float_t jetBtagDeepCSVProbudsg = kMissing;
  Int_t matchedGenJetExists = 0;
  Float_t matchedGenJetPt = kMissing;
  Float_t matchedGenJetEta = kMissing;
  Float_t matchedGenJetPhi = kMissing;
  Float_t matchedGenJetMass = kMissing;
  Int_t jetNPFConstituents = 0;
  Int_t jetNGenConstituents = 0;
  Int_t jetHadronFlavor = 0;
  Int_t jetPartonFlavor = 0;

  Float_t truthPX = kMissing;
  Float_t truthPY = kMissing;
  Float_t truthPZ = kMissing;
  Float_t truthE = kMissing;
  Float_t E_tot = kMissing;
  Float_t PX_tot = kMissing;
  Float_t PY_tot = kMissing;
  Float_t PZ_tot = kMissing;
  Float_t P_tot = kMissing;
  Float_t Eta_tot = kMissing;
  Float_t Phi_tot = kMissing;

  std::vector<float> Part_E;
  std::vector<float> Part_PX;
  std::vector<float> Part_PY;
  std::vector<float> Part_PZ;
  std::vector<float> Part_E_log;
  std::vector<float> Part_P;
  std::vector<float> Part_P_log;
  std::vector<float> Part_Etarel;
  std::vector<float> Part_Phirel;
  std::vector<float> Part_pt;
  std::vector<float> Part_eta;
  std::vector<float> Part_phi;
  std::vector<float> Part_mass;
  std::vector<int> Part_pdgId;
  std::vector<int> Part_charge;
  std::vector<int> Part_fromPV;
  std::vector<int> Part_candIdx;
  std::vector<int> Part_srcPackedCandIdx;
  std::vector<int> Part_inputRow;

  std::vector<float> GenPart_pt;
  std::vector<float> GenPart_eta;
  std::vector<float> GenPart_phi;
  std::vector<float> GenPart_mass;
  std::vector<float> GenPart_energy;
  std::vector<float> GenPart_px;
  std::vector<float> GenPart_py;
  std::vector<float> GenPart_pz;
  std::vector<int> GenPart_pdgId;
  std::vector<int> GenPart_charge;
  std::vector<int> GenPart_status;
  std::vector<int> GenPart_candIdx;
  std::vector<int> GenPart_srcGenCandIdx;
  std::vector<int> GenPart_inputRow;

  out.Branch("run", &out_run);
  out.Branch("luminosityBlock", &out_luminosityBlock);
  out.Branch("event", &out_event);
  out.Branch("sourceLabel", &out_sourceLabel);
  out.Branch("inputEntry", &inputEntry);
  out.Branch("selectedJetIdx", &selectedJetIdx);
  out.Branch("nInputAK15", &nInputAK15);
  out.Branch("nInputPFCand", &nInputPFCand);
  out.Branch("nInputGenCand", &nInputGenCand);
  out.Branch("nPart", &nPart);
  out.Branch("nGenPart", &nGenPart);
  out.Branch("is_signal_new", &is_signal_new);
  out.Branch("idx", &idx);
  out.Branch("origIdx", &origIdx);
  out.Branch("ttv", &ttv);
  out.Branch("selectedLeptonPdgId", &selectedLeptonPdgId);
  out.Branch("selectedLeptonIdx", &selectedLeptonIdx);
  out.Branch("selectedLeptonPt", &selectedLeptonPt);
  out.Branch("selectedLeptonEta", &selectedLeptonEta);
  out.Branch("selectedLeptonPhi", &selectedLeptonPhi);
  out.Branch("selectedLeptonIso", &selectedLeptonIso);
  out.Branch("selectedLeptonDeltaPhi", &selectedLeptonDeltaPhi);

  out.Branch("jet_pt", &jetPt);
  out.Branch("jet_eta", &jetEta);
  out.Branch("jet_phi", &jetPhi);
  out.Branch("jet_mass", &jetMass);
  out.Branch("jet_energy", &jetEnergy);
  out.Branch("jet_px", &jetPx);
  out.Branch("jet_py", &jetPy);
  out.Branch("jet_pz", &jetPz);
  out.Branch("jet_p", &jetP);
  out.Branch("jet_tau1", &jetTau1);
  out.Branch("jet_tau2", &jetTau2);
  out.Branch("jet_tau3", &jetTau3);
  out.Branch("jet_tau4", &jetTau4);
  out.Branch("jet_btagDeepCSV_probb", &jetBtagDeepCSVProbb);
  out.Branch("jet_btagDeepCSV_probbb", &jetBtagDeepCSVProbbb);
  out.Branch("jet_btagDeepCSV_probc", &jetBtagDeepCSVProbc);
  out.Branch("jet_btagDeepCSV_probudsg", &jetBtagDeepCSVProbudsg);
  out.Branch("matchedGenJetExists", &matchedGenJetExists);
  out.Branch("matchedGenJetPt", &matchedGenJetPt);
  out.Branch("matchedGenJetEta", &matchedGenJetEta);
  out.Branch("matchedGenJetPhi", &matchedGenJetPhi);
  out.Branch("matchedGenJetMass", &matchedGenJetMass);
  out.Branch("jetNPFConstituents", &jetNPFConstituents);
  out.Branch("jetNGenConstituents", &jetNGenConstituents);
  out.Branch("jetHadronFlavor", &jetHadronFlavor);
  out.Branch("jetPartonFlavor", &jetPartonFlavor);

  out.Branch("truthPX", &truthPX);
  out.Branch("truthPY", &truthPY);
  out.Branch("truthPZ", &truthPZ);
  out.Branch("truthE", &truthE);
  out.Branch("E_tot", &E_tot);
  out.Branch("PX_tot", &PX_tot);
  out.Branch("PY_tot", &PY_tot);
  out.Branch("PZ_tot", &PZ_tot);
  out.Branch("P_tot", &P_tot);
  out.Branch("Eta_tot", &Eta_tot);
  out.Branch("Phi_tot", &Phi_tot);

  out.Branch("Part_E", &Part_E);
  out.Branch("Part_PX", &Part_PX);
  out.Branch("Part_PY", &Part_PY);
  out.Branch("Part_PZ", &Part_PZ);
  out.Branch("Part_E_log", &Part_E_log);
  out.Branch("Part_P", &Part_P);
  out.Branch("Part_P_log", &Part_P_log);
  out.Branch("Part_Etarel", &Part_Etarel);
  out.Branch("Part_Phirel", &Part_Phirel);
  out.Branch("Part_pt", &Part_pt);
  out.Branch("Part_eta", &Part_eta);
  out.Branch("Part_phi", &Part_phi);
  out.Branch("Part_mass", &Part_mass);
  out.Branch("Part_pdgId", &Part_pdgId);
  out.Branch("Part_charge", &Part_charge);
  out.Branch("Part_fromPV", &Part_fromPV);
  out.Branch("Part_candIdx", &Part_candIdx);
  out.Branch("Part_srcPackedCandIdx", &Part_srcPackedCandIdx);
  out.Branch("Part_inputRow", &Part_inputRow);

  out.Branch("GenPart_pt", &GenPart_pt);
  out.Branch("GenPart_eta", &GenPart_eta);
  out.Branch("GenPart_phi", &GenPart_phi);
  out.Branch("GenPart_mass", &GenPart_mass);
  out.Branch("GenPart_energy", &GenPart_energy);
  out.Branch("GenPart_px", &GenPart_px);
  out.Branch("GenPart_py", &GenPart_py);
  out.Branch("GenPart_pz", &GenPart_pz);
  out.Branch("GenPart_pdgId", &GenPart_pdgId);
  out.Branch("GenPart_charge", &GenPart_charge);
  out.Branch("GenPart_status", &GenPart_status);
  out.Branch("GenPart_candIdx", &GenPart_candIdx);
  out.Branch("GenPart_srcGenCandIdx", &GenPart_srcGenCandIdx);
  out.Branch("GenPart_inputRow", &GenPart_inputRow);

  Long64_t processed = 0;
  Long64_t selected = 0;
  Long64_t noPassingJet = 0;

  while (reader.Next()) {
    if (maxEvents >= 0 && processed >= maxEvents) {
      break;
    }
    ++processed;

    Int_t bestJetIdx = -1;
    float bestJetPt = -1.0f;
    Int_t bestLeptonPdgId = 0;
    Int_t bestLeptonIdx = -1;
    Float_t bestLeptonPt = kMissing;
    Float_t bestLeptonEta = kMissing;
    Float_t bestLeptonPhi = kMissing;
    Float_t bestLeptonIso = kMissing;
    Float_t bestLeptonDeltaPhi = kMissing;

    for (UInt_t j = 0; j < *nJet; ++j) {
      if (jet_pt[j] <= 170.0f || std::abs(jet_eta[j]) >= 3.0f) {
        continue;
      }

      bool hasValidLepton = false;
      Int_t thisLeptonPdgId = 0;
      Int_t thisLeptonIdx = -1;
      Float_t thisLeptonPt = kMissing;
      Float_t thisLeptonEta = kMissing;
      Float_t thisLeptonPhi = kMissing;
      Float_t thisLeptonIso = kMissing;
      Float_t thisLeptonDeltaPhi = kMissing;

      for (UInt_t i = 0; i < *nMuon; ++i) {
        const double iso = leptonIso(muon_iso_chg, muon_iso_all, i);
        const double dphi = std::abs(deltaPhi(jet_phi[j], muon_phi[i]));
        if (muon_pt[i] > 30.0f && std::abs(muon_eta[i]) < 2.5f && iso < 0.3 && dphi > 1.5) {
          hasValidLepton = true;
          thisLeptonPdgId = 13;
          thisLeptonIdx = static_cast<Int_t>(i);
          thisLeptonPt = muon_pt[i];
          thisLeptonEta = muon_eta[i];
          thisLeptonPhi = muon_phi[i];
          thisLeptonIso = iso;
          thisLeptonDeltaPhi = dphi;
          break;
        }
      }

      if (!hasValidLepton) {
        for (UInt_t i = 0; i < *nElectron; ++i) {
          const double iso = leptonIso(electron_iso_chg, electron_iso_all, i);
          const double dphi = std::abs(deltaPhi(jet_phi[j], electron_phi[i]));
          if (electron_pt[i] > 30.0f && std::abs(electron_eta[i]) < 2.5f && iso < 0.3 && dphi > 1.5) {
            hasValidLepton = true;
            thisLeptonPdgId = 11;
            thisLeptonIdx = static_cast<Int_t>(i);
            thisLeptonPt = electron_pt[i];
            thisLeptonEta = electron_eta[i];
            thisLeptonPhi = electron_phi[i];
            thisLeptonIso = iso;
            thisLeptonDeltaPhi = dphi;
            break;
          }
        }
      }

      if (!hasValidLepton) {
        continue;
      }

      if (jet_pt[j] > bestJetPt) {
        bestJetPt = jet_pt[j];
        bestJetIdx = static_cast<Int_t>(j);
        bestLeptonPdgId = thisLeptonPdgId;
        bestLeptonIdx = thisLeptonIdx;
        bestLeptonPt = thisLeptonPt;
        bestLeptonEta = thisLeptonEta;
        bestLeptonPhi = thisLeptonPhi;
        bestLeptonIso = thisLeptonIso;
        bestLeptonDeltaPhi = thisLeptonDeltaPhi;
      }
    }

    if (bestJetIdx < 0) {
      ++noPassingJet;
      continue;
    }

    Part_E.clear();
    Part_PX.clear();
    Part_PY.clear();
    Part_PZ.clear();
    Part_E_log.clear();
    Part_P.clear();
    Part_P_log.clear();
    Part_Etarel.clear();
    Part_Phirel.clear();
    Part_pt.clear();
    Part_eta.clear();
    Part_phi.clear();
    Part_mass.clear();
    Part_pdgId.clear();
    Part_charge.clear();
    Part_fromPV.clear();
    Part_candIdx.clear();
    Part_srcPackedCandIdx.clear();
    Part_inputRow.clear();

    GenPart_pt.clear();
    GenPart_eta.clear();
    GenPart_phi.clear();
    GenPart_mass.clear();
    GenPart_energy.clear();
    GenPart_px.clear();
    GenPart_py.clear();
    GenPart_pz.clear();
    GenPart_pdgId.clear();
    GenPart_charge.clear();
    GenPart_status.clear();
    GenPart_candIdx.clear();
    GenPart_srcGenCandIdx.clear();
    GenPart_inputRow.clear();

    out_run = *run;
    out_luminosityBlock = *luminosityBlock;
    out_event = *event;
    inputEntry = reader.GetCurrentEntry();
    selectedJetIdx = bestJetIdx;
    nInputAK15 = static_cast<Int_t>(*nJet);
    nInputPFCand = static_cast<Int_t>(*nPFCand);
    nInputGenCand = static_cast<Int_t>(*nGenCand);
    is_signal_new = isSignal;
    idx = safeInt(*event);
    origIdx = safeInt(static_cast<unsigned long long>(inputEntry));
    ttv = splitLabel(selected + 1);
    selectedLeptonPdgId = bestLeptonPdgId;
    selectedLeptonIdx = bestLeptonIdx;
    selectedLeptonPt = bestLeptonPt;
    selectedLeptonEta = bestLeptonEta;
    selectedLeptonPhi = bestLeptonPhi;
    selectedLeptonIso = bestLeptonIso;
    selectedLeptonDeltaPhi = bestLeptonDeltaPhi;

    jetPt = jet_pt[bestJetIdx];
    jetEta = jet_eta[bestJetIdx];
    jetPhi = jet_phi[bestJetIdx];
    jetMass = jet_mass[bestJetIdx];
    TLorentzVector jetVec;
    jetVec.SetPtEtaPhiM(jetPt, jetEta, jetPhi, jetMass);
    jetEnergy = jetVec.E();
    jetPx = jetVec.Px();
    jetPy = jetVec.Py();
    jetPz = jetVec.Pz();
    jetP = jetVec.P();
    jetTau1 = jet_tau1[bestJetIdx];
    jetTau2 = jet_tau2[bestJetIdx];
    jetTau3 = jet_tau3[bestJetIdx];
    jetTau4 = jet_tau4[bestJetIdx];
    jetBtagDeepCSVProbb = jet_btag_probb[bestJetIdx];
    jetBtagDeepCSVProbbb = jet_btag_probbb[bestJetIdx];
    jetBtagDeepCSVProbc = jet_btag_probc[bestJetIdx];
    jetBtagDeepCSVProbudsg = jet_btag_probudsg[bestJetIdx];
    matchedGenJetExists = jet_matchedGenJetExists[bestJetIdx];
    matchedGenJetPt = jet_matchedGenJetPt[bestJetIdx];
    matchedGenJetEta = jet_matchedGenJetEta[bestJetIdx];
    matchedGenJetPhi = jet_matchedGenJetPhi[bestJetIdx];
    matchedGenJetMass = jet_matchedGenJetMass[bestJetIdx];
    jetNPFConstituents = jet_nPFConstituents[bestJetIdx];
    jetNGenConstituents = jet_nGenConstituents[bestJetIdx];
    jetHadronFlavor = jet_hadronFlavor[bestJetIdx];
    jetPartonFlavor = jet_partonFlavor[bestJetIdx];

    E_tot = jetEnergy;
    PX_tot = jetPx;
    PY_tot = jetPy;
    PZ_tot = jetPz;
    P_tot = jetP;
    Eta_tot = jetEta;
    Phi_tot = jetPhi;

    if (matchedGenJetExists != 0) {
      TLorentzVector genJetVec;
      genJetVec.SetPtEtaPhiM(matchedGenJetPt, matchedGenJetEta, matchedGenJetPhi, matchedGenJetMass);
      truthPX = genJetVec.Px();
      truthPY = genJetVec.Py();
      truthPZ = genJetVec.Pz();
      truthE = genJetVec.E();
    } else {
      truthPX = truthPY = truthPZ = truthE = kMissing;
    }

    for (UInt_t i = 0; i < *nPFCand; ++i) {
      if (pf_jetIdx[i] != selectedJetIdx) {
        continue;
      }

      const double p = std::sqrt(static_cast<double>(pf_px[i]) * pf_px[i] +
                                 static_cast<double>(pf_py[i]) * pf_py[i] +
                                 static_cast<double>(pf_pz[i]) * pf_pz[i]);
      Part_E.push_back(pf_energy[i]);
      Part_PX.push_back(pf_px[i]);
      Part_PY.push_back(pf_py[i]);
      Part_PZ.push_back(pf_pz[i]);
      Part_E_log.push_back(std::log(static_cast<double>(pf_energy[i]) + kLogEps));
      Part_P.push_back(p);
      Part_P_log.push_back(std::log(p + kLogEps));
      Part_Etarel.push_back(pf_eta[i] - jetEta);
      Part_Phirel.push_back(deltaPhi(pf_phi[i], jetPhi));
      Part_pt.push_back(pf_pt[i]);
      Part_eta.push_back(pf_eta[i]);
      Part_phi.push_back(pf_phi[i]);
      Part_mass.push_back(pf_mass[i]);
      Part_pdgId.push_back(pf_pdgId[i]);
      Part_charge.push_back(pf_charge[i]);
      Part_fromPV.push_back(pf_fromPV[i]);
      Part_candIdx.push_back(pf_candIdx[i]);
      Part_srcPackedCandIdx.push_back(pf_srcPackedCandIdx[i]);
      Part_inputRow.push_back(static_cast<int>(i));
    }

    for (UInt_t i = 0; i < *nGenCand; ++i) {
      if (gen_jetIdx[i] != selectedJetIdx) {
        continue;
      }

      GenPart_pt.push_back(gen_pt[i]);
      GenPart_eta.push_back(gen_eta[i]);
      GenPart_phi.push_back(gen_phi[i]);
      GenPart_mass.push_back(gen_mass[i]);
      GenPart_energy.push_back(gen_energy[i]);
      GenPart_px.push_back(gen_px[i]);
      GenPart_py.push_back(gen_py[i]);
      GenPart_pz.push_back(gen_pz[i]);
      GenPart_pdgId.push_back(gen_pdgId[i]);
      GenPart_charge.push_back(gen_charge[i]);
      GenPart_status.push_back(gen_status[i]);
      GenPart_candIdx.push_back(gen_candIdx[i]);
      GenPart_srcGenCandIdx.push_back(gen_srcGenCandIdx[i]);
      GenPart_inputRow.push_back(static_cast<int>(i));
    }

    nPart = static_cast<Int_t>(Part_E.size());
    nGenPart = static_cast<Int_t>(GenPart_pt.size());

    if (nPart == 0) {
      ++noPassingJet;
      continue;
    }

    out.Fill();
    ++selected;
  }

  output.cd();
  out.Write();
  output.Close();

  std::cout << "AK15NanoFlatTreeProducer summary\n"
            << "  input: " << inputFile << "\n"
            << "  output: " << outputFile << "\n"
            << "  source label: " << sourceLabel << "\n"
            << "  processed events: " << processed << "\n"
            << "  selected events: " << selected << "\n"
            << "  dropped events: " << noPassingJet << std::endl;

  return 0;
}
