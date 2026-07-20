#include "TBranch.h"
#include "TChain.h"
#include "TFile.h"
#include "TH1D.h"
#include "TTree.h"
#include "TTreeReader.h"
#include "TTreeReaderArray.h"
#include "TTreeReaderValue.h"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr double kMissing = -999.0;

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

std::string lower(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
    return static_cast<char>(std::tolower(c));
  });
  return value;
}

bool endsWith(const std::string& value, const std::string& suffix) {
  return value.size() >= suffix.size() &&
         value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
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

template <typename T>
std::unique_ptr<TTreeReaderValue<T>> optionalValue(TTreeReader& reader, TTree* tree, const char* name) {
  if (!hasBranch(tree, name)) {
    return std::unique_ptr<TTreeReaderValue<T>>();
  }
  return std::unique_ptr<TTreeReaderValue<T>>(new TTreeReaderValue<T>(reader, name));
}

double deltaPhiSigned(double phi1, double phi2) {
  double dphi = std::fmod(phi1 - phi2, 2.0 * M_PI);
  if (dphi > M_PI) {
    dphi -= 2.0 * M_PI;
  } else if (dphi <= -M_PI) {
    dphi += 2.0 * M_PI;
  }
  return dphi;
}

double deltaR(double eta1, double phi1, double eta2, double phi2) {
  const double deta = eta1 - eta2;
  const double dphi = deltaPhiSigned(phi1, phi2);
  return std::sqrt(deta * deta + dphi * dphi);
}

double readMuonIso(const std::string& requested,
                   const std::unique_ptr<TTreeReaderArray<Float_t>>& iso04All,
                   const std::unique_ptr<TTreeReaderArray<Float_t>>& iso03All,
                   const std::unique_ptr<TTreeReaderArray<Float_t>>& iso04Chg,
                   const std::unique_ptr<TTreeReaderArray<Float_t>>& iso03Chg,
                   unsigned int idx) {
  const std::string mode = lower(requested);
  if (mode == "muon_pfreliso04_all" && iso04All) return (*iso04All)[idx];
  if (mode == "muon_pfreliso03_all" && iso03All) return (*iso03All)[idx];
  if (mode == "muon_pfreliso04_chg" && iso04Chg) return (*iso04Chg)[idx];
  if (mode == "muon_pfreliso03_chg" && iso03Chg) return (*iso03Chg)[idx];

  if (mode == "auto" || mode.empty()) {
    if (iso04All) return (*iso04All)[idx];
    if (iso03All) return (*iso03All)[idx];
    if (iso04Chg) return (*iso04Chg)[idx];
    if (iso03Chg) return (*iso03Chg)[idx];
  }
  return std::numeric_limits<double>::infinity();
}

using LumiMask = std::map<UInt_t, std::vector<std::pair<UInt_t, UInt_t>>>;

LumiMask loadLumiMask(const char* pathArg) {
  LumiMask mask;
  const std::string path = trim(pathArg ? pathArg : "");
  if (path.empty()) {
    return mask;
  }

  std::ifstream input(path.c_str());
  if (!input.is_open()) {
    throw std::runtime_error("Could not open lumi-mask ranges file: " + path);
  }

  std::string line;
  unsigned int lineNumber = 0;
  while (std::getline(input, line)) {
    ++lineNumber;
    const std::string::size_type comment = line.find('#');
    if (comment != std::string::npos) {
      line = line.substr(0, comment);
    }
    line = trim(line);
    if (line.empty()) {
      continue;
    }
    std::istringstream values(line);
    UInt_t run = 0;
    UInt_t first = 0;
    UInt_t last = 0;
    if (!(values >> run >> first >> last) || first == 0 || last < first) {
      throw std::runtime_error("Invalid lumi-mask range at line " + std::to_string(lineNumber));
    }
    mask[run].push_back(std::make_pair(first, last));
  }
  return mask;
}

bool passesLumiMask(const LumiMask& mask, UInt_t run, UInt_t lumi) {
  if (mask.empty()) {
    return true;
  }
  const LumiMask::const_iterator found = mask.find(run);
  if (found == mask.end()) {
    return false;
  }
  for (const auto& range : found->second) {
    if (lumi >= range.first && lumi <= range.second) {
      return true;
    }
  }
  return false;
}

void labelCutflow(TH1D& hist) {
  hist.GetXaxis()->SetBinLabel(1, "processed");
  hist.GetXaxis()->SetBinLabel(2, "certified_lumi");
  hist.GetXaxis()->SetBinLabel(3, "has_muon");
  hist.GetXaxis()->SetBinLabel(4, "muon_pass");
  hist.GetXaxis()->SetBinLabel(5, "has_ak15");
  hist.GetXaxis()->SetBinLabel(6, "ak15_pt_eta");
  hist.GetXaxis()->SetBinLabel(7, "dphi_pass");
  hist.GetXaxis()->SetBinLabel(8, "selected");
}

}  // namespace

int PhysicsAnalysisTreeProducer(const char* inputFile = "input_nano.root",
                                const char* outputFile = "physics_analysis.root",
                                const char* sampleLabelArg = "",
                                int isData = 0,
                                Long64_t maxEvents = -1,
                                double jetPtMin = 200.0,
                                double jetEtaMax = 3.0,
                                const char* leptonModeArg = "muon",
                                double muonPtMin = 30.0,
                                double muonEtaMax = 2.5,
                                double muonIsoMax = 0.3,
                                double minDeltaPhi = 1.5,
                                const char* muonIsoBranchArg = "auto",
                                const char* lumiMaskRangesArg = "") {
  const std::string leptonMode = lower(trim(leptonModeArg ? leptonModeArg : "muon"));
  if (leptonMode != "muon") {
    std::cerr << "ERROR: PhysicsAnalysisTreeProducer currently supports only lepton_mode=muon; got '"
              << leptonMode << "'" << std::endl;
    return 2;
  }

  TChain chain("Events");
  const int added = addInputs(chain, inputFile);
  if (added == 0) {
    std::cerr << "ERROR: no input files matched '" << inputFile << "'" << std::endl;
    return 1;
  }

  TTree* tree = &chain;
  const char* requiredBranches[] = {
      "run",
      "luminosityBlock",
      "event",
      "nMuon",
      "Muon_pt",
      "Muon_eta",
      "Muon_phi",
      "nSuperFatJetAK15",
      "SuperFatJetAK15_pt",
      "SuperFatJetAK15_eta",
      "SuperFatJetAK15_phi",
      "SuperFatJetAK15_mass",
  };

  try {
    for (const char* branch : requiredBranches) {
      requireBranch(tree, branch);
    }
  } catch (const std::exception& err) {
    std::cerr << "ERROR: " << err.what() << std::endl;
    return 3;
  }

  TTreeReader reader(tree);
  TTreeReaderValue<UInt_t> run(reader, "run");
  TTreeReaderValue<UInt_t> luminosityBlock(reader, "luminosityBlock");
  TTreeReaderValue<ULong64_t> event(reader, "event");

  TTreeReaderValue<UInt_t> nMuon(reader, "nMuon");
  TTreeReaderArray<Float_t> muonPt(reader, "Muon_pt");
  TTreeReaderArray<Float_t> muonEta(reader, "Muon_eta");
  TTreeReaderArray<Float_t> muonPhi(reader, "Muon_phi");
  auto muonIso04All = optionalArray<Float_t>(reader, tree, "Muon_pfRelIso04_all");
  auto muonIso03All = optionalArray<Float_t>(reader, tree, "Muon_pfRelIso03_all");
  auto muonIso04Chg = optionalArray<Float_t>(reader, tree, "Muon_pfRelIso04_chg");
  auto muonIso03Chg = optionalArray<Float_t>(reader, tree, "Muon_pfRelIso03_chg");

  TTreeReaderValue<UInt_t> nJet(reader, "nSuperFatJetAK15");
  TTreeReaderArray<Float_t> jetPt(reader, "SuperFatJetAK15_pt");
  TTreeReaderArray<Float_t> jetEta(reader, "SuperFatJetAK15_eta");
  TTreeReaderArray<Float_t> jetPhi(reader, "SuperFatJetAK15_phi");
  TTreeReaderArray<Float_t> jetMass(reader, "SuperFatJetAK15_mass");
  auto jetSourceIdx =
      optionalArray<Int_t>(reader, tree, "SuperFatJetAK15_leadingAK15SourceJetIdx");
  auto jetOriginalMultiplicity =
      optionalArray<Int_t>(reader, tree, "SuperFatJetAK15_originalAK15Multiplicity");
  auto genWeight = optionalValue<Float_t>(reader, tree, "genWeight");
  if (!isData && !genWeight) {
    std::cerr << "ERROR: MC input is missing required genWeight branch" << std::endl;
    return 4;
  }

  LumiMask lumiMask;
  try {
    lumiMask = loadLumiMask(lumiMaskRangesArg);
  } catch (const std::exception& err) {
    std::cerr << "ERROR: " << err.what() << std::endl;
    return 4;
  }

  TFile output(outputFile, "RECREATE");
  if (output.IsZombie()) {
    std::cerr << "ERROR: could not create output file '" << outputFile << "'" << std::endl;
    return 5;
  }

  TTree out("Events", "Muon-channel AK15 analysis tree");
  TH1D cutflow("cutflow", "Muon-channel AK15 cutflow (raw events)", 8, 0.5, 8.5);
  TH1D cutflowWeighted(
      "cutflow_weighted", "Muon-channel AK15 cutflow (generator-weight sums)", 8, 0.5, 8.5);
  labelCutflow(cutflow);
  labelCutflow(cutflowWeighted);
  cutflow.Sumw2();
  cutflowWeighted.Sumw2();

  TH1D normalization("normalization", "Analysis normalization metadata", 5, 0.5, 5.5);
  normalization.GetXaxis()->SetBinLabel(1, "processed_events");
  normalization.GetXaxis()->SetBinLabel(2, "sum_genweights");
  normalization.GetXaxis()->SetBinLabel(3, "sum_abs_genweights");
  normalization.GetXaxis()->SetBinLabel(4, "selected_events");
  normalization.GetXaxis()->SetBinLabel(5, "selected_sum_genweights");

  TTree luminosityBlocks("LuminosityBlocks", "Certified luminosity blocks seen in data input");
  UInt_t lumiRun = 0;
  UInt_t lumiBlock = 0;
  luminosityBlocks.Branch("run", &lumiRun);
  luminosityBlocks.Branch("luminosityBlock", &lumiBlock);

  UInt_t outRun = 0;
  UInt_t outLuminosityBlock = 0;
  ULong64_t outEvent = 0;
  Long64_t inputEntry = -1;
  std::string sample = (sampleLabelArg && sampleLabelArg[0] != '\0') ? sampleLabelArg : "sample";
  Int_t outIsData = isData ? 1 : 0;
  Int_t selectedLeptonPdgId = 13;
  Int_t selectedMuonIdx = -1;
  Int_t selectedJetIdx = -1;
  Int_t selectedSourceJetIdx = -1;
  Int_t nInputMuon = 0;
  Int_t nInputAK15 = 0;
  Float_t selectedMuonPt = kMissing;
  Float_t selectedMuonEta = kMissing;
  Float_t selectedMuonPhi = kMissing;
  Float_t selectedMuonIso = kMissing;
  Float_t selectedLeptonPt = kMissing;
  Float_t selectedLeptonEta = kMissing;
  Float_t selectedLeptonPhi = kMissing;
  Float_t selectedLeptonIso = kMissing;
  Float_t jet_pt = kMissing;
  Float_t jet_eta = kMissing;
  Float_t jet_phi = kMissing;
  Float_t jet_mass = kMissing;
  Float_t muonJetDeltaR = kMissing;
  Float_t muonJetDeltaPhi = kMissing;
  Float_t muonJetSignedDeltaPhi = kMissing;
  Float_t outGenWeight = 1.0;
  Int_t hasGenWeight = genWeight ? 1 : 0;

  out.Branch("run", &outRun);
  out.Branch("luminosityBlock", &outLuminosityBlock);
  out.Branch("event", &outEvent);
  out.Branch("inputEntry", &inputEntry);
  out.Branch("sample", &sample);
  out.Branch("isData", &outIsData);
  out.Branch("nInputMuon", &nInputMuon);
  out.Branch("nInputAK15", &nInputAK15);
  out.Branch("selectedLeptonPdgId", &selectedLeptonPdgId);
  out.Branch("selectedLeptonPt", &selectedLeptonPt);
  out.Branch("selectedLeptonEta", &selectedLeptonEta);
  out.Branch("selectedLeptonPhi", &selectedLeptonPhi);
  out.Branch("selectedLeptonIso", &selectedLeptonIso);
  out.Branch("selectedMuonIdx", &selectedMuonIdx);
  out.Branch("selectedMuonPt", &selectedMuonPt);
  out.Branch("selectedMuonEta", &selectedMuonEta);
  out.Branch("selectedMuonPhi", &selectedMuonPhi);
  out.Branch("selectedMuonIso", &selectedMuonIso);
  out.Branch("selectedJetIdx", &selectedJetIdx);
  out.Branch("selectedSourceJetIdx", &selectedSourceJetIdx);
  out.Branch("jet_pt", &jet_pt);
  out.Branch("jet_eta", &jet_eta);
  out.Branch("jet_phi", &jet_phi);
  out.Branch("jet_mass", &jet_mass);
  out.Branch("muonJetDeltaR", &muonJetDeltaR);
  out.Branch("muonJetDeltaPhi", &muonJetDeltaPhi);
  out.Branch("muonJetSignedDeltaPhi", &muonJetSignedDeltaPhi);
  out.Branch("genWeight", &outGenWeight);
  out.Branch("hasGenWeight", &hasGenWeight);

  Long64_t processed = 0;
  Long64_t selected = 0;
  double sumGenWeights = 0.0;
  double sumAbsGenWeights = 0.0;
  double selectedSumGenWeights = 0.0;
  std::set<std::pair<UInt_t, UInt_t>> certifiedLumis;

  while (reader.Next()) {
    if (maxEvents >= 0 && processed >= maxEvents) {
      break;
    }
    ++processed;
    const double eventWeight = isData ? 1.0 : static_cast<double>(**genWeight);
    sumGenWeights += eventWeight;
    sumAbsGenWeights += std::abs(eventWeight);
    cutflow.Fill(1);
    cutflowWeighted.Fill(1, eventWeight);

    if (isData && !passesLumiMask(lumiMask, *run, *luminosityBlock)) {
      continue;
    }
    cutflow.Fill(2);
    cutflowWeighted.Fill(2, eventWeight);
    if (isData) {
      certifiedLumis.insert(std::make_pair(*run, *luminosityBlock));
    }

    nInputMuon = static_cast<Int_t>(*nMuon);
    nInputAK15 = (jetOriginalMultiplicity && *nJet > 0)
                     ? (*jetOriginalMultiplicity)[0]
                     : static_cast<Int_t>(*nJet);
    if (*nMuon > 0) {
      cutflow.Fill(3);
      cutflowWeighted.Fill(3, eventWeight);
    }
    int bestMuonIdx = -1;
    double bestMuonPt = -1.0;
    double bestMuonIso = std::numeric_limits<double>::infinity();
    for (UInt_t i = 0; i < *nMuon; ++i) {
      const double iso = readMuonIso(muonIsoBranchArg ? muonIsoBranchArg : "auto",
                                     muonIso04All,
                                     muonIso03All,
                                     muonIso04Chg,
                                     muonIso03Chg,
                                     i);
      if (muonPt[i] <= muonPtMin) continue;
      if (std::abs(muonEta[i]) >= muonEtaMax) continue;
      if (iso >= muonIsoMax) continue;
      if (muonPt[i] > bestMuonPt) {
        bestMuonPt = muonPt[i];
        bestMuonIdx = static_cast<int>(i);
        bestMuonIso = iso;
      }
    }

    if (bestMuonIdx < 0) {
      continue;
    }
    cutflow.Fill(4);
    cutflowWeighted.Fill(4, eventWeight);

    if (*nJet == 0) {
      continue;
    }
    cutflow.Fill(5);
    cutflowWeighted.Fill(5, eventWeight);

    int bestJetIdx = -1;
    for (UInt_t j = 0; j < *nJet; ++j) {
      if (bestJetIdx < 0 || jetPt[j] > jetPt[bestJetIdx]) {
        bestJetIdx = static_cast<int>(j);
      }
    }
    if (bestJetIdx < 0 ||
        jetPt[bestJetIdx] <= jetPtMin ||
        std::abs(jetEta[bestJetIdx]) >= jetEtaMax) {
      continue;
    }
    cutflow.Fill(6);
    cutflowWeighted.Fill(6, eventWeight);

    const double bestSignedDeltaPhi =
        deltaPhiSigned(jetPhi[bestJetIdx], muonPhi[bestMuonIdx]);
    if (std::abs(bestSignedDeltaPhi) <= minDeltaPhi) {
      continue;
    }
    cutflow.Fill(7);
    cutflowWeighted.Fill(7, eventWeight);

    outRun = *run;
    outLuminosityBlock = *luminosityBlock;
    outEvent = *event;
    inputEntry = reader.GetCurrentEntry();
    outIsData = isData ? 1 : 0;
    selectedLeptonPdgId = 13;
    selectedMuonIdx = bestMuonIdx;
    selectedJetIdx = bestJetIdx;
    selectedSourceJetIdx = jetSourceIdx ? (*jetSourceIdx)[bestJetIdx] : bestJetIdx;
    selectedMuonPt = muonPt[bestMuonIdx];
    selectedMuonEta = muonEta[bestMuonIdx];
    selectedMuonPhi = muonPhi[bestMuonIdx];
    selectedMuonIso = bestMuonIso;
    selectedLeptonPt = selectedMuonPt;
    selectedLeptonEta = selectedMuonEta;
    selectedLeptonPhi = selectedMuonPhi;
    selectedLeptonIso = selectedMuonIso;
    jet_pt = jetPt[bestJetIdx];
    jet_eta = jetEta[bestJetIdx];
    jet_phi = jetPhi[bestJetIdx];
    jet_mass = jetMass[bestJetIdx];
    muonJetSignedDeltaPhi = bestSignedDeltaPhi;
    muonJetDeltaPhi = std::abs(bestSignedDeltaPhi);
    muonJetDeltaR = deltaR(selectedMuonEta, selectedMuonPhi, jet_eta, jet_phi);
    hasGenWeight = genWeight ? 1 : 0;
    outGenWeight = genWeight ? **genWeight : 1.0;

    out.Fill();
    cutflow.Fill(8);
    cutflowWeighted.Fill(8, eventWeight);
    ++selected;
    selectedSumGenWeights += eventWeight;
  }

  normalization.SetBinContent(1, static_cast<double>(processed));
  normalization.SetBinContent(2, sumGenWeights);
  normalization.SetBinContent(3, sumAbsGenWeights);
  normalization.SetBinContent(4, static_cast<double>(selected));
  normalization.SetBinContent(5, selectedSumGenWeights);

  for (const auto& runLumi : certifiedLumis) {
    lumiRun = runLumi.first;
    lumiBlock = runLumi.second;
    luminosityBlocks.Fill();
  }

  output.cd();
  out.Write();
  cutflow.Write();
  cutflowWeighted.Write();
  normalization.Write();
  luminosityBlocks.Write();
  output.Close();

  std::cout << "PhysicsAnalysisTreeProducer summary\n"
            << "  input: " << inputFile << "\n"
            << "  output: " << outputFile << "\n"
            << "  sample: " << sample << "\n"
            << "  lepton mode: " << leptonMode << "\n"
            << "  jet pt min: " << jetPtMin << "\n"
            << "  muon pt min: " << muonPtMin << "\n"
            << "  processed events: " << processed << "\n"
            << "  certified data lumis: " << certifiedLumis.size() << "\n"
            << "  sum gen weights: " << sumGenWeights << "\n"
            << "  selected events: " << selected << "\n"
            << "  selected sum gen weights: " << selectedSumGenWeights << std::endl;

  return 0;
}
