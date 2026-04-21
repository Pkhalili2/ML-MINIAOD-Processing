#auto generated configuration file
# using: 
# Revision: 1.19 
# Source: /local/reps/CMSSW/CMSSW/Configuration/Applications/python/ConfigBuilder.py,v 
# with command line options: --python_filename ExoHiggs_6b_UL18NanoAODv2_1_cfg.py --eventcontent NANOAODSIM --customise Configuration/DataProcessing/Utils.addMonitoring --datatier NANOAODSIM --fileout file:ExoHiggs_6b_UL18NanoAODv2.root --conditions 106X_upgrade2018_realistic_v15_L1v1 --step NANO --filein file:ExoHiggs_6b_UL18MiniAOD.root --era Run2_2018,run2_nanoAOD_106Xv1 --no_exec --mc -n 10
import FWCore.ParameterSet.Config as cms

from Configuration.Eras.Era_Run2_2018_cff import Run2_2018
from Configuration.Eras.Modifier_run2_nanoAOD_106Xv1_cff import run2_nanoAOD_106Xv1

process = cms.Process('NANO',Run2_2018,run2_nanoAOD_106Xv1)

# import of standard configurations
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
    input = cms.untracked.int32(-1)
)


import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing

options = VarParsing('analysis')
options.parseArguments()

# Input source
process.source = cms.Source("PoolSource",
   # fileNames = cms.untracked.vstring('file:ExoHiggs_6b_UL18MiniAOD.root'),
    fileNames = cms.untracked.vstring(options.inputFiles),
    duplicateCheckMode = cms.untracked.string('noDuplicateCheck'),
    secondaryFileNames = cms.untracked.vstring()
)

process.options = cms.untracked.PSet(
)

# Production Info
process.configurationMetadata = cms.untracked.PSet(
    annotation = cms.untracked.string('--python_filename nevts:10'),
    name = cms.untracked.string('Applications'),
    version = cms.untracked.string('$Revision: 1.19 $')
)

process.ak15ConstituentTables = cms.EDProducer(
    "AK15ConstituentTableProducer",
    jets = cms.InputTag("selectedPatJetsAK15PFCHS"),
    saveJetConstituents = cms.bool(True),
    jetTableName = cms.string("SuperFatJetAK15"),
    pfCandTableName = cms.string("SuperFatJetAK15PFCand"),
    genCandTableName = cms.string("SuperFatJetAK15GenCand"),
)

# Output definition
options.outputFile = options.outputFile.replace(".root", "_Nano.root")
process.NANOAODSIMoutput = cms.OutputModule("NanoAODOutputModule",
    compressionAlgorithm = cms.untracked.string('LZMA'),
    compressionLevel = cms.untracked.int32(9),
    dataset = cms.untracked.PSet(
        dataTier = cms.untracked.string('NANOAODSIM'),
        filterName = cms.untracked.string('')
    ),
    fileName = cms.untracked.string(options.outputFile),
    outputCommands = process.NANOAODSIMEventContent.outputCommands
)
'''
# Additional output definition
options.outputFile = options.outputFile.replace("_Nano.root", "_Mini.root")
process.outmini = cms.OutputModule("PoolOutputModule",
#    fileName = cms.untracked.string('test_mini.root'),
    fileName = cms.untracked.string(options.outputFile),
    outputCommands = cms.untracked.vstring('drop *')
)
from Configuration.EventContent.EventContent_cff import MINIAODSIMEventContent
process.outmini.outputCommands.extend(MINIAODSIMEventContent.outputCommands)

#from Configuration.EventContent.EventContent_cff import MINI_AOD_EVENT_CONTENT
#process.out.outputCommands.extend(MINIAODSIMEventContent.outputCommands)
#from PhysicsTools.PatAlgos.patInputFiles_cff import MiniAOD_PAT_EventContent
#process.outmini.outputCommands.extend(MiniAOD_PAT_EventContent.outputCommands)
process.outmini.outputCommands.append('keep *_selectedPatJetsAK15PFCHS_*_*')

#process.endpathmini = cms.EndPath(process.outmini)

'''

# Other statements
from Configuration.AlCa.GlobalTag import GlobalTag
process.GlobalTag = GlobalTag(process.GlobalTag, '106X_upgrade2018_realistic_v15_L1v1', '')
#process.GlobalTag = GlobalTag(process.GlobalTag, '106X_dataRun2_v35', '')

import FWCore.ParameterSet.Config as cms
from PhysicsTools.PatAlgos.tools.jetTools import updateJetCollection

# --- Assume `process` is already defined and miniAOD is loaded ---

# 1) Recluster AK15 PF jets (CHS) if not already present
#from RecoJets.JetProducers.ak8PFJets_cfi import ak8PFJets
#process.ak15PFJetsCHS = ak8PFJets.clone(
#    rParam = 1.5,
#    src = "packedPFCandidates",
#    srcPVs = "offlineSlimmedPrimaryVertices",
#    doAreaFastjet = True
#)
'''
# 2) Update PAT collection for AK15
updateJetCollection(
    process,
    jetSource      = cms.InputTag('ak15PFJetsCHS'),       # input jets
    pvSource       = cms.InputTag('offlineSlimmedPrimaryVertices'),
    pfCandidates   = cms.InputTag('packedPFCandidates'),
    svSource       = cms.InputTag('slimmedSecondaryVertices'),
    muSource       = cms.InputTag('slimmedMuons'),
    elSource       = cms.InputTag('slimmedElectrons'),
    jetCorrections = ('AK8PFchs', ['L2Relative','L3Absolute'], 'None'),
    btagDiscriminators = [
        'pfDeepCSVJetTags:probb',
        'pfDeepCSVJetTags:probbb',
        'pfDeepCSVJetTags:probc',
        'pfDeepCSVJetTags:probudsg'
    ],
    labelName      = 'AK15'
)

# 3) Add to NanoAOD output
# In your NanoAOD producer config, extend the jetCollections list:
jetCollections = cms.PSet(
     ak4 = cms.InputTag("slimmedJets"),
     ak15 = cms.InputTag("updatedPatJetsAK15")
 )

'''

import FWCore.ParameterSet.Config as cms
from JMEAnalysis.JetToolbox.jetToolbox_cff import jetToolbox
 #   'ak15CHS',      # 2) module label postfix
# --- Assume `process` is already defined and miniAOD is loaded ---
jetToolbox(
    process,
    'ak15',                          # jet algorithm
    'ak15JetSubs', 
    'out',                           # output label
    PUMethod            = 'CHS',     # charged hadron subtraction
    runOnMC              = True,     # True for MC
    addNsub=True,
    maxTau=4,
    addSoftDrop=True,
    addSoftDropSubjets=True,
    JETCorrPayload       = 'AK8PFchs',
    JETCorrLevels        = ['L1FastJet','L2Relative', 'L3Absolute'],
    bTagDiscriminators   = [
        'pfDeepCSVJetTags:probb',
        'pfDeepCSVJetTags:probbb',
        'pfDeepCSVJetTags:probc',
        'pfDeepCSVJetTags:probudsg',
#        'pfMassIndependentDeepDoubleBvLV2JetTags:probHbb',

    ],
)

from RecoJets.JetProducers.nJettinessAdder_cfi import Njettiness
process.NjettinessAK15 = Njettiness.clone(
    src = cms.InputTag("selectedPatJetsAK15PFCHS"),
    Njets=cms.vuint32(1,2,3,4),
    R0 = cms.double( 1.5 )
)


from PhysicsTools.NanoAOD.common_cff import Var
#from PhysicsTools.NanoAOD.simpleCandidateFlatTableProducer_cfi import simpleCandidateFlatTableProducer

process.jetAK15Table = cms.EDProducer("SimpleCandidateFlatTableProducer",
    src = cms.InputTag("selectedPatJetsAK15PFCHS"),
    cut = cms.string("pt > 170"),
    name = cms.string("SuperFatJetAK15"),
    doc = cms.string("AK15 jets with Njettiness and SoftDrop mass"),
    singleton = cms.bool(False),
    subjets = cms.InputTag("ak15PFJetsCHSSoftDrop"),
    variables = cms.PSet(
        pt = Var("pt", float, doc="pt", precision=10),
        eta = Var("eta", float, doc="eta", precision=10),
        phi = Var("phi", float, doc="phi", precision=10),
        mass = Var("mass", float, doc="mass", precision=10),

        tau1 = Var("userFloat('NjettinessAK15CHS:tau1')",float,  doc="N-subjettiness tau1",precision=10),
        tau2 = Var("userFloat('NjettinessAK15CHS:tau2')", float, doc="N-subjettiness tau2", precision=10),
        tau3 = Var("userFloat('NjettinessAK15CHS:tau3')", float, doc="N-subjettiness tau3", precision=10),
        tau4 = Var("userFloat('NjettinessAK15CHS:tau4')", float, doc="N-subjettiness tau4", precision=10),
        area = Var("jetArea()", float, doc="jet catchment area, for JECs",precision=10),
        nMuons = Var("?hasOverlaps('muons')?overlaps('muons').size():0", int, doc="number of muons in the jet"),
        muonIdx1 = Var("?overlaps('muons').size()>0?overlaps('muons')[0].key():-1", int, doc="index of first matching muon"),
        muonIdx2 = Var("?overlaps('muons').size()>1?overlaps('muons')[1].key():-1", int, doc="index of second matching muon"),
        electronIdx1 = Var("?overlaps('electrons').size()>0?overlaps('electrons')[0].key():-1", int, doc="index of first matching electron"),
        electronIdx2 = Var("?overlaps('electrons').size()>1?overlaps('electrons')[1].key():-1", int, doc="index of second matching electron"),
        nElectrons = Var("?hasOverlaps('electrons')?overlaps('electrons').size():0", int, doc="number of electrons in the jet"),
    #    msoftdrop = Var("groomedMass('ak15PFJetsCHSSoftDrop')",float, doc="Corrected soft drop mass with PUPPI",precision=10),
	btag_pfDeepCSVJetTags_probb = Var("bDiscriminator('pfDeepCSVJetTags:probb')",float,doc="pfDeepCSVJetTags:probb",precision=10),
	btag_pfDeepCSVJetTags_probbb = Var("bDiscriminator('pfDeepCSVJetTags:probbb')",float,doc="pfDeepCSVJetTags:probbb",precision=10),
	btag_pfDeepCSVJetTags_probc = Var("bDiscriminator('pfDeepCSVJetTags:probc')",float,doc="pfDeepCSVJetTags:probc",precision=10),
	btag_pfDeepCSVJetTags_probudsg = Var("bDiscriminator('pfDeepCSVJetTags:probudsg')",float,doc="pfDeepCSVJetTags:probudsg",precision=10),
#btag_DeepDoubleBvLV2JetTags_probHbb = Var("bDiscriminator('pfMassIndependentDeepDoubleBvLV2JetTags:probHbb')",float,doc="pfMassIndependentDeepDoubleBvLV2JetTags:probHbb",precision=10),
    )
)

process.genJetAK15Table = cms.EDProducer("SimpleCandidateFlatTableProducer",
    src = cms.InputTag("selectedPatJetsAK15PFCHS"),
    cut = cms.string("pt > 100."),
    name = cms.string("GenJetAK15"),
    doc  = cms.string("selectedPatJetsAK15PFCHS, i.e. ak15 Jets made with visible genparticles"),
    singleton = cms.bool(False), # the number of entries is variable
    extension = cms.bool(False), # this is the main table for the genjets
    variables = cms.PSet(
        pt  = Var("pt",  "float", doc="pt"),
        eta = Var("eta", "float", doc="eta"),
        phi = Var("phi", "float", doc="phi"),
        mass = Var("mass", "float", doc="mass"),
	#anything else?
    )
)


from PhysicsTools.NanoAOD.common_cff import Var

process.subjetTable = cms.EDProducer("SimpleCandidateFlatTableProducer",
    src = cms.InputTag("selectedPatJetsAK15PFCHSSoftDropPacked"),  # or your AK15 subjets
    cut = cms.string(""),  # or selection
    name = cms.string("SuperFat_SubJetAK8"),
    doc = cms.string("Softdrop subjets"),
    singleton = cms.bool(False),  # it's a collection
    extension = cms.bool(False),
    variables = cms.PSet(
        pt  = Var("pt",  "float", doc="pt"),
        eta = Var("eta", "float", doc="eta"),
        phi = Var("phi", "float", doc="phi"),
        mass = Var("mass", "float", doc="mass"),
        btagDeepB = Var("bDiscriminator('pfDeepCSVJetTags:probb') + bDiscriminator('pfDeepCSVJetTags:probbb')", "float", doc="DeepCSV b+bb discriminator"),
    )
)



# Make sure that `process.path` and `process.endpath` replace or insert into your existing schedule.


process.nanoSequenceMC += process.selectedPatJetsAK15PFCHS
process.nanoSequenceMC += process.NjettinessAK15
process.nanoSequenceMC += process.subjetTable
process.nanoSequenceMC += process.jetAK15Table 
process.nanoSequenceMC += process.genJetAK15Table
process.nanoSequenceMC += process.ak15ConstituentTables
# Then ensure 'updatedPatJetsAK15' is included in your PAT sequences and NanoAOD output modules.

#from Configuration.EventContent.EventContent_cff import MINIAODSIMEventContent
#process.out.outputCommands = MINIAODSIMEventContent.outputCommands
#process.out.outputCommands.append('keep *_*_*_*')


#process.out = cms.OutputModule("PoolOutputModule",
#    fileName = cms.untracked.string('jettoolbox.root'),
#    outputCommands = cms.untracked.vstring(
#        'drop *',
#	'keep keep *_slimmedElectrons_*_*')
#)

#process.outMINI = cms.EndPath(process.out)


# Path and EndPath definitions
process.nanoAOD_step = cms.Path(process.nanoSequenceMC)
process.endjob_step = cms.EndPath(process.endOfProcess)
#process.endpathmini = cms.EndPath(process.outmini)
process.NANOAODSIMoutput_step = cms.EndPath(process.NANOAODSIMoutput)

# Schedule definition
#process.schedule = cms.Schedule(process.nanoAOD_step,process.endjob_step,process.endpathmini,process.NANOAODSIMoutput_step)
process.schedule = cms.Schedule(process.nanoAOD_step,process.endjob_step,process.NANOAODSIMoutput_step)
from PhysicsTools.PatAlgos.tools.helpers import associatePatAlgosToolsTask
associatePatAlgosToolsTask(process)

# customisation of the process.

# Automatic addition of the customisation function from PhysicsTools.NanoAOD.nano_cff
from PhysicsTools.NanoAOD.nano_cff import nanoAOD_customizeMC 

#call to customisation function nanoAOD_customizeMC imported from PhysicsTools.NanoAOD.nano_cff
process = nanoAOD_customizeMC(process)

# Automatic addition of the customisation function from Configuration.DataProcessing.Utils
from Configuration.DataProcessing.Utils import addMonitoring 

#call to customisation function addMonitoring imported from Configuration.DataProcessing.Utils
process = addMonitoring(process)

# End of customisation functions

# Customisation from command line

#print process.dumpPython()


# Add early deletion of temporary data products to reduce peak memory need
from Configuration.StandardSequences.earlyDeleteSettings_cff import customiseEarlyDelete
process = customiseEarlyDelete(process)
# End adding early deletion
