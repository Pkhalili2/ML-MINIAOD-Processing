import FWCore.ParameterSet.Config as cms

from Configuration.Eras.Era_Run2_2018_cff import Run2_2018
from Configuration.Eras.Modifier_run2_nanoAOD_106Xv1_cff import run2_nanoAOD_106Xv1

process = cms.Process('NANO', Run2_2018, run2_nanoAOD_106Xv1)

process.load('Configuration.StandardSequences.Services_cff')
process.load('SimGeneral.HepPDTESSource.pythiapdt_cfi')
process.load('FWCore.MessageService.MessageLogger_cfi')
process.load('Configuration.EventContent.EventContent_cff')
process.load('SimGeneral.MixingModule.mixNoPU_cfi')
process.load('Configuration.StandardSequences.GeometryRecoDB_cff')
process.load('Configuration.StandardSequences.MagneticField_cff')
process.load('PhysicsTools.NanoAOD.nano_cff')
process.load('Configuration.StandardSequences.EndOfProcess_cff')
process.load('Configuration.StandardSequences.FrontierConditions_GlobalTag_cff')

process.maxEvents = cms.untracked.PSet(
    input=cms.untracked.int32(-1)
)

from FWCore.ParameterSet.VarParsing import VarParsing
options = VarParsing('analysis')
options.parseArguments()

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring(options.inputFiles),
    duplicateCheckMode=cms.untracked.string('noDuplicateCheck'),
    secondaryFileNames=cms.untracked.vstring()
)

process.options = cms.untracked.PSet()

process.configurationMetadata = cms.untracked.PSet(
    annotation=cms.untracked.string('--python_filename nevts:10'),
    name=cms.untracked.string('Applications'),
    version=cms.untracked.string('$Revision: 1.19 $')
)

options.outputFile = options.outputFile.replace(".root", "_Nano.root")
process.NANOAODSIMoutput = cms.OutputModule(
    "NanoAODOutputModule",
    compressionAlgorithm=cms.untracked.string('LZMA'),
    compressionLevel=cms.untracked.int32(9),
    dataset=cms.untracked.PSet(
        dataTier=cms.untracked.string('NANOAODSIM'),
        filterName=cms.untracked.string('')
    ),
    fileName=cms.untracked.string(options.outputFile),
    outputCommands=process.NANOAODSIMEventContent.outputCommands
)

from Configuration.AlCa.GlobalTag import GlobalTag
process.GlobalTag = GlobalTag(process.GlobalTag, '106X_upgrade2018_realistic_v15_L1v1', '')

from JMEAnalysis.JetToolbox.jetToolbox_cff import jetToolbox

jetToolbox(
    process,
    'ak15',
    'ak15JetSubs',
    'out',
    PUMethod='CHS',
    runOnMC=True,
    addNsub=True,
    maxTau=4,
    addSoftDrop=True,
    addSoftDropSubjets=True,
    JETCorrPayload='AK8PFchs',
    JETCorrLevels=['L1FastJet', 'L2Relative', 'L3Absolute'],
    bTagDiscriminators=[
        'pfDeepCSVJetTags:probb',
        'pfDeepCSVJetTags:probbb',
        'pfDeepCSVJetTags:probc',
        'pfDeepCSVJetTags:probudsg',
    ],
)

from RecoJets.JetProducers.nJettinessAdder_cfi import Njettiness
process.NjettinessAK15 = Njettiness.clone(
    src=cms.InputTag("selectedPatJetsAK15PFCHS"),
    Njets=cms.vuint32(1, 2, 3, 4),
    R0=cms.double(1.5)
)

from PhysicsTools.NanoAOD.common_cff import Var

process.jetAK15Table = cms.EDProducer(
    "SimpleCandidateFlatTableProducer",
    src=cms.InputTag("selectedPatJetsAK15PFCHS"),
    cut=cms.string("pt > 170"),
    name=cms.string("SuperFatJetAK15"),
    doc=cms.string("AK15 jets with Njettiness and SoftDrop mass"),
    singleton=cms.bool(False),
    extension=cms.bool(False),
    variables=cms.PSet(
        pt=Var("pt", float, doc="pt", precision=10),
        eta=Var("eta", float, doc="eta", precision=10),
        phi=Var("phi", float, doc="phi", precision=10),
        mass=Var("mass", float, doc="mass", precision=10),
        tau1=Var("userFloat('NjettinessAK15CHS:tau1')", float, doc="N-subjettiness tau1", precision=10),
        tau2=Var("userFloat('NjettinessAK15CHS:tau2')", float, doc="N-subjettiness tau2", precision=10),
        tau3=Var("userFloat('NjettinessAK15CHS:tau3')", float, doc="N-subjettiness tau3", precision=10),
        tau4=Var("userFloat('NjettinessAK15CHS:tau4')", float, doc="N-subjettiness tau4", precision=10),
        area=Var("jetArea()", float, doc="jet catchment area", precision=10),
        nMuons=Var("?hasOverlaps('muons')?overlaps('muons').size():0", int, doc="number of muons in the jet"),
        muonIdx1=Var("?overlaps('muons').size()>0?overlaps('muons')[0].key():-1", int, doc="index of first matching muon"),
        muonIdx2=Var("?overlaps('muons').size()>1?overlaps('muons')[1].key():-1", int, doc="index of second matching muon"),
        electronIdx1=Var("?overlaps('electrons').size()>0?overlaps('electrons')[0].key():-1", int, doc="index of first matching electron"),
        electronIdx2=Var("?overlaps('electrons').size()>1?overlaps('electrons')[1].key():-1", int, doc="index of second matching electron"),
        nElectrons=Var("?hasOverlaps('electrons')?overlaps('electrons').size():0", int, doc="number of electrons in the jet"),
        btag_pfDeepCSVJetTags_probb=Var("bDiscriminator('pfDeepCSVJetTags:probb')", float, doc="pfDeepCSVJetTags:probb", precision=10),
        btag_pfDeepCSVJetTags_probbb=Var("bDiscriminator('pfDeepCSVJetTags:probbb')", float, doc="pfDeepCSVJetTags:probbb", precision=10),
        btag_pfDeepCSVJetTags_probc=Var("bDiscriminator('pfDeepCSVJetTags:probc')", float, doc="pfDeepCSVJetTags:probc", precision=10),
        btag_pfDeepCSVJetTags_probudsg=Var("bDiscriminator('pfDeepCSVJetTags:probudsg')", float, doc="pfDeepCSVJetTags:probudsg", precision=10),
    )
)

process.genJetAK15Table = cms.EDProducer(
    "SimpleCandidateFlatTableProducer",
    src=cms.InputTag("selectedPatJetsAK15PFCHS"),
    cut=cms.string("pt > 100."),
    name=cms.string("GenJetAK15"),
    doc=cms.string("selectedPatJetsAK15PFCHS, i.e. ak15 jets made with visible genparticles"),
    singleton=cms.bool(False),
    extension=cms.bool(False),
    variables=cms.PSet(
        pt=Var("pt", "float", doc="pt"),
        eta=Var("eta", "float", doc="eta"),
        phi=Var("phi", "float", doc="phi"),
        mass=Var("mass", "float", doc="mass"),
    )
)

process.subjetTable = cms.EDProducer(
    "SimpleCandidateFlatTableProducer",
    src=cms.InputTag("selectedPatJetsAK15PFCHSSoftDropPacked"),
    cut=cms.string(""),
    name=cms.string("SuperFat_SubJetAK8"),
    doc=cms.string("Softdrop subjets"),
    singleton=cms.bool(False),
    extension=cms.bool(False),
    variables=cms.PSet(
        pt=Var("pt", "float", doc="pt"),
        eta=Var("eta", "float", doc="eta"),
        phi=Var("phi", "float", doc="phi"),
        mass=Var("mass", "float", doc="mass"),
        btagDeepB=Var(
            "bDiscriminator('pfDeepCSVJetTags:probb') + bDiscriminator('pfDeepCSVJetTags:probbb')",
            "float",
            doc="DeepCSV b+bb discriminator"
        ),
    )
)

process.nanoSequenceMC += process.selectedPatJetsAK15PFCHS
process.nanoSequenceMC += process.NjettinessAK15
process.nanoSequenceMC += process.subjetTable
process.nanoSequenceMC += process.jetAK15Table
process.nanoSequenceMC += process.genJetAK15Table

process.nanoAOD_step = cms.Path(process.nanoSequenceMC)
process.endjob_step = cms.EndPath(process.endOfProcess)
process.NANOAODSIMoutput_step = cms.EndPath(process.NANOAODSIMoutput)

process.schedule = cms.Schedule(
    process.nanoAOD_step,
    process.endjob_step,
    process.NANOAODSIMoutput_step
)

from PhysicsTools.PatAlgos.tools.helpers import associatePatAlgosToolsTask
associatePatAlgosToolsTask(process)

from PhysicsTools.NanoAOD.nano_cff import nanoAOD_customizeMC
process = nanoAOD_customizeMC(process)

from Configuration.DataProcessing.Utils import addMonitoring
process = addMonitoring(process)

from Configuration.StandardSequences.earlyDeleteSettings_cff import customiseEarlyDelete
process = customiseEarlyDelete(process)
