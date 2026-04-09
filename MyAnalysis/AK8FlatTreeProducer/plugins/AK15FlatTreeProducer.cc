#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"
#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/ParameterSet/interface/ParameterSet.h"

#include "DataFormats/PatCandidates/interface/Jet.h"
#include "DataFormats/JetReco/interface/GenJet.h"
#include "DataFormats/PatCandidates/interface/PackedCandidate.h"
#include "FWCore/Framework/interface/EventSetup.h"
#include "FWCore/Utilities/interface/InputTag.h"

#include "CommonTools/UtilAlgos/interface/TFileService.h"
#include "FWCore/ServiceRegistry/interface/Service.h"

#include "DataFormats/Math/interface/deltaPhi.h"

#include "TTree.h"
#include "TH1I.h"
#include "TLorentzVector.h"

#include <cmath>
#include <vector>

typedef std::vector<pat::Jet> JetCollection;

class AK15FlatTreeProducer : public edm::one::EDAnalyzer<edm::one::SharedResources> {
public:
  explicit AK15FlatTreeProducer(const edm::ParameterSet&);
  ~AK15FlatTreeProducer() override;

private:
  void beginJob() override;
  void analyze(const edm::Event&, const edm::EventSetup&) override;
  void endJob() override {}

  void registerParticleBranches(TTree* tree);

  edm::EDGetTokenT<JetCollection> recoJetsToken_;

  TTree* particleTree_{nullptr};
  TH1I* cutflow_{nullptr};

  bool is_signal_new_{false};
  bool fillAllEvents_{true};
  double minJetPt_{170.0};

  unsigned int run_;
  unsigned int lumi_;
  unsigned long long event_;

  std::vector<double> Part_E_, Part_PX_, Part_PY_, Part_PZ_;
  std::vector<double> Part_E_log_, Part_P_, Part_P_log_, Part_Etarel_, Part_Phirel_;

  double truthPX_, truthPY_, truthPZ_, truthE_;
  double E_tot_, PX_tot_, PY_tot_, PZ_tot_, P_tot_, Eta_tot_, Phi_tot_;
  int nPart_, idx_, origIdx_, ttv_;
};

AK15FlatTreeProducer::AK15FlatTreeProducer(const edm::ParameterSet& iConfig) {
  usesResource("TFileService");

  const edm::InputTag recoJetsTag = iConfig.getParameter<edm::InputTag>("recoJets");
  recoJetsToken_ = consumes<JetCollection>(recoJetsTag);

  is_signal_new_ = iConfig.getParameter<bool>("isSignal");
  fillAllEvents_ = iConfig.existsAs<bool>("fillAllEvents") ? iConfig.getParameter<bool>("fillAllEvents") : true;
  minJetPt_ = iConfig.existsAs<double>("minJetPt") ? iConfig.getParameter<double>("minJetPt") : 170.0;
}

AK15FlatTreeProducer::~AK15FlatTreeProducer() {}

void AK15FlatTreeProducer::registerParticleBranches(TTree* tree) {
  tree->Branch("run", &run_);
  tree->Branch("lumi", &lumi_);
  tree->Branch("event", &event_);

  tree->Branch("nPart", &nPart_);
  tree->Branch("Part_E", &Part_E_);
  tree->Branch("Part_PX", &Part_PX_);
  tree->Branch("Part_PY", &Part_PY_);
  tree->Branch("Part_PZ", &Part_PZ_);
  tree->Branch("Part_E_log", &Part_E_log_);
  tree->Branch("Part_P", &Part_P_);
  tree->Branch("Part_P_log", &Part_P_log_);
  tree->Branch("Part_Etarel", &Part_Etarel_);
  tree->Branch("Part_Phirel", &Part_Phirel_);

  tree->Branch("truthPX", &truthPX_);
  tree->Branch("truthPY", &truthPY_);
  tree->Branch("truthPZ", &truthPZ_);
  tree->Branch("truthE", &truthE_);

  tree->Branch("E_tot", &E_tot_);
  tree->Branch("PX_tot", &PX_tot_);
  tree->Branch("PY_tot", &PY_tot_);
  tree->Branch("PZ_tot", &PZ_tot_);
  tree->Branch("P_tot", &P_tot_);
  tree->Branch("Eta_tot", &Eta_tot_);
  tree->Branch("Phi_tot", &Phi_tot_);

  tree->Branch("is_signal_new", &is_signal_new_);
  tree->Branch("idx", &idx_);
  tree->Branch("origIdx", &origIdx_);
  tree->Branch("ttv", &ttv_);
}

void AK15FlatTreeProducer::beginJob() {
  edm::Service<TFileService> fs;
  if (!fs.isAvailable()) {
    throw cms::Exception("AK15FlatTreeProducer") << "TFileService is not available.";
  }

  cutflow_ = fs->make<TH1I>("cutflow", "cutflow", 3, 0, 3);
  cutflow_->GetXaxis()->SetBinLabel(1, "processed");
  cutflow_->GetXaxis()->SetBinLabel(2, "hasAK15");
  cutflow_->GetXaxis()->SetBinLabel(3, "ptCut");

  particleTree_ = fs->make<TTree>("ParticleTree", "Particle-level AK15 tree");
  registerParticleBranches(particleTree_);
}

void AK15FlatTreeProducer::analyze(const edm::Event& iEvent, const edm::EventSetup&) {
  cutflow_->Fill(0);

  run_ = iEvent.id().run();
  lumi_ = iEvent.id().luminosityBlock();
  event_ = iEvent.id().event();

  Part_E_.clear();
  Part_PX_.clear();
  Part_PY_.clear();
  Part_PZ_.clear();
  Part_E_log_.clear();
  Part_P_.clear();
  Part_P_log_.clear();
  Part_Etarel_.clear();
  Part_Phirel_.clear();

  nPart_ = 0;
  E_tot_ = PX_tot_ = PY_tot_ = PZ_tot_ = P_tot_ = Eta_tot_ = Phi_tot_ = -999.;
  truthPX_ = truthPY_ = truthPZ_ = truthE_ = -999.;
  idx_ = static_cast<int>(iEvent.id().event());
  origIdx_ = static_cast<int>(iEvent.id().event());
  ttv_ = 0;

  edm::Handle<JetCollection> recoJets;
  iEvent.getByToken(recoJetsToken_, recoJets);

  const pat::Jet* selectedJet = nullptr;
  float max_pt = -1.0;

  if (recoJets.isValid()) {
    for (const auto& jet : *recoJets) {
      if (jet.pt() > max_pt) {
        max_pt = jet.pt();
        selectedJet = &jet;
      }
    }
  }

  if (selectedJet) {
    cutflow_->Fill(1);
    if (selectedJet->pt() > minJetPt_) cutflow_->Fill(2);

    E_tot_ = selectedJet->energy();
    PX_tot_ = selectedJet->px();
    PY_tot_ = selectedJet->py();
    PZ_tot_ = selectedJet->pz();
    P_tot_ = selectedJet->p();
    Eta_tot_ = selectedJet->eta();
    Phi_tot_ = selectedJet->phi();

    const reco::GenJet* genJet = selectedJet->genJet();
    if (genJet) {
      TLorentzVector genVec;
      genVec.SetPtEtaPhiE(genJet->pt(), genJet->eta(), genJet->phi(), genJet->energy());
      truthPX_ = genVec.Px();
      truthPY_ = genVec.Py();
      truthPZ_ = genVec.Pz();
      truthE_ = genVec.E();
    }

    for (const auto& cand : selectedJet->daughterPtrVector()) {
      const pat::PackedCandidate* pf = dynamic_cast<const pat::PackedCandidate*>(cand.get());
      if (!pf) continue;

      const double p = pf->p();
      const double e = pf->energy();

      Part_E_.push_back(e);
      Part_PX_.push_back(pf->px());
      Part_PY_.push_back(pf->py());
      Part_PZ_.push_back(pf->pz());
      Part_E_log_.push_back(std::log(e + 1e-6));
      Part_P_.push_back(p);
      Part_P_log_.push_back(std::log(p + 1e-6));
      Part_Etarel_.push_back(pf->eta() - selectedJet->eta());
      Part_Phirel_.push_back(reco::deltaPhi(pf->phi(), selectedJet->phi()));
    }

    nPart_ = static_cast<int>(Part_E_.size());
  }

  if (fillAllEvents_ || selectedJet) {
    particleTree_->Fill();
  }
}

DEFINE_FWK_MODULE(AK15FlatTreeProducer);
