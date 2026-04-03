import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing
import os
import sys

options = VarParsing('analysis')
options.maxEvents = -1

options.register(
    'inputList',
    '',
    VarParsing.multiplicity.singleton,
    VarParsing.varType.string,
    'Text file with input files'
)

options.register(
    'flatOut',
    'ak15_flat.root',
    VarParsing.multiplicity.singleton,
    VarParsing.varType.string,
    'Single ROOT output file containing NanoTree and ParticleTree'
)

options.register(
    'isSignal',
    0,
    VarParsing.multiplicity.singleton,
    VarParsing.varType.int,
    'Signal flag'
)

options.register(
    'fillAllEvents',
    1,
    VarParsing.multiplicity.singleton,
    VarParsing.varType.int,
    'Fill all events'
)

options.parseArguments()

base_cfg = os.path.join(os.getcwd(), "condor", "AK15JetProducer_cfg.py")
if not os.path.exists(base_cfg):
    raise RuntimeError("Cannot find AK15JetProducer_cfg.py at: " + base_cfg)

saved_argv = sys.argv[:]
try:
    sys.argv = ["cmsRun", base_cfg]
    _ns = {"__file__": base_cfg}
    exec(compile(open(base_cfg, "rb").read(), base_cfg, "exec"), _ns)
finally:
    sys.argv = saved_argv

process = _ns["process"]

file_list = []
with open(options.inputList, "r") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("/hdfs/"):
            line = "file:" + line
        elif line.startswith("/store/"):
            line = "root://cms-xrd-global.cern.ch/" + line
        file_list.append(line)

if len(file_list) == 0:
    raise RuntimeError("No valid input files found in inputList")

process.source.fileNames = cms.untracked.vstring(*file_list)
process.maxEvents = cms.untracked.PSet(
    input=cms.untracked.int32(options.maxEvents)
)

if hasattr(process, "NANOAODSIMoutput_step"):
    process.schedule.remove(process.NANOAODSIMoutput_step)
if hasattr(process, "NANOAODSIMoutput"):
    del process.NANOAODSIMoutput

process.TFileService = cms.Service(
    "TFileService",
    fileName=cms.string(options.flatOut)
)

process.ak15FlatTree = cms.EDAnalyzer(
    "AK15FlatTreeProducer",
    recoJets=cms.InputTag("selectedPatJetsAK15PFCHS"),
    isSignal=cms.bool(bool(options.isSignal)),
    fillAllEvents=cms.bool(bool(options.fillAllEvents))
)

process.nanoSequenceMC += process.ak15FlatTree