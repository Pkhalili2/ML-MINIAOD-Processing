#include "TBranch.h"
#include "TFile.h"
#include "TKey.h"
#include "TLeaf.h"
#include "TObject.h"
#include "TTree.h"

#include <algorithm>
#include <cstddef>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

bool startsWith(const std::string& value, const std::string& prefix) {
  return value.size() >= prefix.size() &&
         value.compare(0, prefix.size(), prefix) == 0;
}

char leafCode(const std::string& type) {
  if (type == "Float_t") return 'F';
  if (type == "Double_t") return 'D';
  if (type == "Int_t") return 'I';
  if (type == "UInt_t") return 'i';
  if (type == "Long64_t") return 'L';
  if (type == "ULong64_t") return 'l';
  if (type == "Short_t") return 'S';
  if (type == "UShort_t") return 's';
  if (type == "Char_t") return 'B';
  if (type == "UChar_t") return 'b';
  if (type == "Bool_t") return 'O';
  throw std::runtime_error("Unsupported NanoAOD leaf type: " + type);
}

std::size_t leafSize(char code) {
  switch (code) {
    case 'F': return sizeof(Float_t);
    case 'D': return sizeof(Double_t);
    case 'I': return sizeof(Int_t);
    case 'i': return sizeof(UInt_t);
    case 'L': return sizeof(Long64_t);
    case 'l': return sizeof(ULong64_t);
    case 'S': return sizeof(Short_t);
    case 's': return sizeof(UShort_t);
    case 'B': return sizeof(Char_t);
    case 'b': return sizeof(UChar_t);
    case 'O': return sizeof(Bool_t);
  }
  throw std::runtime_error("Unsupported NanoAOD leaf code");
}

struct PrimitiveArray {
  std::string name;
  TLeaf* inputLeaf = nullptr;
  char code = 0;
  std::size_t elementSize = 0;
  std::vector<ULong64_t> storage;

  PrimitiveArray(const std::string& branchName, TLeaf* leaf, std::size_t capacity)
      : name(branchName), inputLeaf(leaf), code(leafCode(leaf->GetTypeName())),
        elementSize(leafSize(code)),
        storage((std::max<std::size_t>(capacity, 1) * elementSize + sizeof(ULong64_t) - 1) /
                sizeof(ULong64_t), 0) {}

  void* data() { return storage.data(); }

  void set(std::size_t index, double value) {
    unsigned char* target = reinterpret_cast<unsigned char*>(storage.data()) + index * elementSize;
    switch (code) {
      case 'F': *reinterpret_cast<Float_t*>(target) = static_cast<Float_t>(value); break;
      case 'D': *reinterpret_cast<Double_t*>(target) = static_cast<Double_t>(value); break;
      case 'I': *reinterpret_cast<Int_t*>(target) = static_cast<Int_t>(value); break;
      case 'i': *reinterpret_cast<UInt_t*>(target) = static_cast<UInt_t>(value); break;
      case 'L': *reinterpret_cast<Long64_t*>(target) = static_cast<Long64_t>(value); break;
      case 'l': *reinterpret_cast<ULong64_t*>(target) = static_cast<ULong64_t>(value); break;
      case 'S': *reinterpret_cast<Short_t*>(target) = static_cast<Short_t>(value); break;
      case 's': *reinterpret_cast<UShort_t*>(target) = static_cast<UShort_t>(value); break;
      case 'B': *reinterpret_cast<Char_t*>(target) = static_cast<Char_t>(value); break;
      case 'b': *reinterpret_cast<UChar_t*>(target) = static_cast<UChar_t>(value); break;
      case 'O': *reinterpret_cast<Bool_t*>(target) = value != 0.0; break;
    }
  }
};

struct NanoTable {
  std::string countName;
  UInt_t count = 0;
  std::vector<PrimitiveArray> columns;

  NanoTable(TTree* input,
            TTree* output,
            const std::string& countBranch,
            const std::string& branchPrefix,
            std::size_t capacity,
            const std::vector<std::string>& excluded = {})
      : countName(countBranch) {
    output->Branch(countName.c_str(), &count, (countName + "/i").c_str());

    std::size_t matches = 0;
    for (TObject* object : *input->GetListOfBranches()) {
      const std::string name = object->GetName();
      if (!startsWith(name, branchPrefix) ||
          std::find(excluded.begin(), excluded.end(), name) != excluded.end()) {
        continue;
      }
      ++matches;
    }
    columns.reserve(matches);

    for (TObject* object : *input->GetListOfBranches()) {
      const std::string name = object->GetName();
      if (!startsWith(name, branchPrefix) ||
          std::find(excluded.begin(), excluded.end(), name) != excluded.end()) {
        continue;
      }
      TBranch* branch = input->GetBranch(name.c_str());
      TLeaf* leaf = branch ? branch->GetLeaf(name.c_str()) : nullptr;
      if (!leaf) {
        throw std::runtime_error("Could not inspect branch " + name);
      }
      columns.emplace_back(name, leaf, capacity);
      PrimitiveArray& column = columns.back();
      const std::string leafList = name + "[" + countName + "]/" + column.code;
      output->Branch(name.c_str(), column.data(), leafList.c_str());
    }
  }

  void fill(const std::vector<UInt_t>& sourceRows, const std::string& remappedIndex = "") {
    count = static_cast<UInt_t>(sourceRows.size());
    for (PrimitiveArray& column : columns) {
      for (std::size_t row = 0; row < sourceRows.size(); ++row) {
        const double value = column.name == remappedIndex
                                 ? 0.0
                                 : column.inputLeaf->GetValue(sourceRows[row]);
        column.set(row, value);
      }
    }
  }
};

TLeaf* requireLeaf(TTree* tree, const char* name) {
  TLeaf* leaf = tree->GetLeaf(name);
  if (!leaf) throw std::runtime_error(std::string("Missing required branch: ") + name);
  return leaf;
}

std::size_t maximumCount(TTree* tree, const char* name) {
  return std::max<std::size_t>(1, static_cast<std::size_t>(tree->GetMaximum(name)));
}

void copyOtherObjects(TFile& input, TFile& output) {
  TIter keys(input.GetListOfKeys());
  while (TKey* key = static_cast<TKey*>(keys())) {
    if (std::string(key->GetName()) == "Events") continue;
    TObject* object = key->ReadObj();
    if (!object) continue;
    output.cd();
    if (object->InheritsFrom(TTree::Class())) {
      TTree* tree = static_cast<TTree*>(object);
      TTree* clone = tree->CloneTree(-1, "fast");
      clone->Write(tree->GetName(), TObject::kOverwrite);
    } else {
      object->Write(key->GetName(), TObject::kOverwrite);
    }
    delete object;
  }
}

}  // namespace

int ReduceAK15NanoToLeading(const char* inputPath,
                            const char* outputPath,
                            Long64_t maxEvents = -1) {
  try {
    TFile input(inputPath, "READ");
    if (input.IsZombie()) throw std::runtime_error("Could not open input file");
    TTree* events = static_cast<TTree*>(input.Get("Events"));
    if (!events) throw std::runtime_error("Input file has no Events tree");

    TLeaf* nJetLeaf = requireLeaf(events, "nSuperFatJetAK15");
    TLeaf* jetPtLeaf = requireLeaf(events, "SuperFatJetAK15_pt");
    TLeaf* pfJetIndex = requireLeaf(events, "SuperFatJetAK15PFCand_jetIdx");
    TLeaf* genJetIndex = events->GetLeaf("SuperFatJetAK15GenCand_jetIdx");
    TLeaf* existingSourceJet = events->GetLeaf("SuperFatJetAK15_leadingAK15SourceJetIdx");
    TLeaf* existingMultiplicity = events->GetLeaf("SuperFatJetAK15_originalAK15Multiplicity");

    TFile output(outputPath, "RECREATE", "", input.GetCompressionSettings());
    if (output.IsZombie()) throw std::runtime_error("Could not create output file");
    output.cd();

    events->SetBranchStatus("nSuperFatJetAK15", 0);
    events->SetBranchStatus("SuperFatJetAK15_*", 0);
    events->SetBranchStatus("nSuperFatJetAK15PFCand", 0);
    events->SetBranchStatus("SuperFatJetAK15PFCand_*", 0);
    if (genJetIndex) {
      events->SetBranchStatus("nSuperFatJetAK15GenCand", 0);
      events->SetBranchStatus("SuperFatJetAK15GenCand_*", 0);
    }
    TTree* reduced = events->CloneTree(0);
    events->SetBranchStatus("*", 1);

    const std::vector<std::string> jetMetadata = {
        "SuperFatJetAK15_leadingAK15SourceJetIdx",
        "SuperFatJetAK15_originalAK15Multiplicity"};
    NanoTable jets(events, reduced, "nSuperFatJetAK15", "SuperFatJetAK15_", 1, jetMetadata);
    NanoTable pf(events, reduced, "nSuperFatJetAK15PFCand", "SuperFatJetAK15PFCand_",
                 maximumCount(events, "nSuperFatJetAK15PFCand"));
    std::unique_ptr<NanoTable> gen;
    if (genJetIndex) {
      gen.reset(new NanoTable(events, reduced,
                              "nSuperFatJetAK15GenCand",
                              "SuperFatJetAK15GenCand_",
                              maximumCount(events, "nSuperFatJetAK15GenCand")));
    }
    Int_t sourceJetIndex[1] = {-1};
    Int_t originalJetMultiplicity[1] = {0};
    reduced->Branch("SuperFatJetAK15_leadingAK15SourceJetIdx", sourceJetIndex,
                    "SuperFatJetAK15_leadingAK15SourceJetIdx[nSuperFatJetAK15]/I");
    reduced->Branch("SuperFatJetAK15_originalAK15Multiplicity", originalJetMultiplicity,
                    "SuperFatJetAK15_originalAK15Multiplicity[nSuperFatJetAK15]/I");

    const Long64_t available = events->GetEntries();
    const Long64_t entries = maxEvents < 0 ? available : std::min(maxEvents, available);
    for (Long64_t entry = 0; entry < entries; ++entry) {
      if (events->GetEntry(entry) <= 0) {
        throw std::runtime_error("Failed to read Events entry " + std::to_string(entry));
      }

      const UInt_t nJets = static_cast<UInt_t>(nJetLeaf->GetValue());
      int leading = -1;
      double leadingPt = -std::numeric_limits<double>::infinity();
      for (UInt_t jet = 0; jet < nJets; ++jet) {
        if (jetPtLeaf->GetValue(jet) > leadingPt) {
          leadingPt = jetPtLeaf->GetValue(jet);
          leading = static_cast<int>(jet);
        }
      }

      std::vector<UInt_t> jetRows;
      std::vector<UInt_t> pfRows;
      std::vector<UInt_t> genRows;
      if (leading >= 0) {
        jetRows.push_back(static_cast<UInt_t>(leading));
        const UInt_t nPf = static_cast<UInt_t>(events->GetLeaf("nSuperFatJetAK15PFCand")->GetValue());
        for (UInt_t row = 0; row < nPf; ++row) {
          if (static_cast<int>(pfJetIndex->GetValue(row)) == leading) pfRows.push_back(row);
        }
        if (genJetIndex) {
          const UInt_t nGen =
              static_cast<UInt_t>(events->GetLeaf("nSuperFatJetAK15GenCand")->GetValue());
          for (UInt_t row = 0; row < nGen; ++row) {
            if (static_cast<int>(genJetIndex->GetValue(row)) == leading) genRows.push_back(row);
          }
        }
      }

      jets.fill(jetRows);
      pf.fill(pfRows, "SuperFatJetAK15PFCand_jetIdx");
      if (gen) gen->fill(genRows, "SuperFatJetAK15GenCand_jetIdx");

      if (leading >= 0) {
        sourceJetIndex[0] = existingSourceJet
                                ? static_cast<Int_t>(existingSourceJet->GetValue(leading))
                                : leading;
        originalJetMultiplicity[0] = existingMultiplicity
                                         ? static_cast<Int_t>(existingMultiplicity->GetValue(leading))
                                         : static_cast<Int_t>(nJets);
      }
      reduced->Fill();
    }

    output.cd();
    reduced->Write("Events", TObject::kOverwrite);
    copyOtherObjects(input, output);
    output.Close();
    input.Close();

    std::cout << "Wrote " << entries << " events to " << outputPath << std::endl;
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << std::endl;
    return 1;
  }
}
