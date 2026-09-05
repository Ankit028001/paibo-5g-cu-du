// SPDX-License-Identifier: GPL-2.0-only
//
// cu-du-macce-model-study.cc
//
// ============================================================================
// THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.
// IT IS NOT A REAL OAI CU-DU EXECUTION AND MUST NEVER BE PRESENTED AS SUCH.
// ============================================================================
//
// Derived from cu-du-scaling-study.cc (identical CU/DU/F1-topology, EPC
// core, 6-class traffic model -- see that file's header for the CU-DU
// topology limitation, not repeated here). The VALIDATED baseline in
// cu-du-scaling-study.cc is left completely unmodified; this is a
// separate file, with its own separate output directory
// (ns3_macce_test/), never overwriting any validated baseline result.
//
// ADDS a MODELED MAC-CE adaptation event, per explicit instruction:
//
// *** THIS IS A MODELED EVENT, NOT A REAL MAC-CE MEASUREMENT. ***
// It does NOT implement or measure a real 3GPP MAC-CE. It does NOT
// perform a real RLC AM/UM reconfiguration. 5G-LENA's `nr` module has no
// MAC-CE-driven RLC-mode-switch mechanism at all -- that is PAIBO's own
// proposed invention, not a stock 3GPP or ns-3 feature.
//
// The modeled event is simply: trigger at time T, assume the adaptation
// applies at the next 30 kHz NR slot boundary, i.e.
//   apply_time = T + 0.5 ms  =>  macce_latency_ms = 0.5 (a constant,
// by construction, for every UE, every run). This is a MODELED
// NEXT-SLOT APPLICATION INTERVAL, not a measured transmission latency,
// not a real OAI MAC-CE latency, not a measured over-the-air latency,
// and not an actual RLC mode-change latency. Every output row carries
// the label "modeled_macce_next_slot_interval -- NOT real OAI MAC-CE".
//
// RRC baseline values (rrcBaseline map below) are the REAL, MEASURED
// bearer-setup-latency numbers from cu-du-bearer-latency-study.cc's
// validated ladder, cross-checked against
// ns3_phase01/ns3_phase01_validated_kpis.xlsx (Baseline_NonPAIBO_Ladder
// sheet) before being hardcoded here -- verified matching exactly at
// N=1,10,25,50,100,150,200 prior to writing this file.

#include "ns3/antenna-module.h"
#include "ns3/applications-module.h"
#include "ns3/buildings-module.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/nr-module.h"
#include "ns3/point-to-point-module.h"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <map>
#include <numeric>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("CuDuMacCeModelStudy");

struct TrafficClass
{
    std::string name;
    double shareOfUes;
    double perUeCapBps;
    uint32_t packetSize;
};

static std::vector<TrafficClass>
GetTrafficClasses()
{
    return {
        {"mMTC", 0.40, 3000.0, 100},
        {"Web", 0.15, 133000.0, 600},
        {"Mobile", 0.15, 166000.0, 800},
        {"VoD", 0.12, 725000.0, 1200},
        {"Live", 0.13, 478000.0, 1200},
        {"V2X", 0.05, 99000.0, 300},
    };
}

static std::vector<uint32_t>
DistributeUesAcrossClasses(uint32_t ueTotal, const std::vector<TrafficClass>& classes)
{
    std::vector<double> raw;
    std::vector<uint32_t> counts;
    for (auto& c : classes)
    {
        raw.push_back(c.shareOfUes * ueTotal);
        counts.push_back(static_cast<uint32_t>(std::floor(raw.back())));
    }
    uint32_t assigned = std::accumulate(counts.begin(), counts.end(), 0u);
    int32_t remainder = static_cast<int32_t>(ueTotal) - static_cast<int32_t>(assigned);
    std::vector<size_t> order(classes.size());
    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(), [&](size_t a, size_t b) {
        return (raw[a] - std::floor(raw[a])) > (raw[b] - std::floor(raw[b]));
    });
    for (int32_t i = 0; i < remainder; ++i)
    {
        counts[order[i % order.size()]]++;
    }
    return counts;
}

// ---- STEP 1.A: MacCeRecord struct ----
struct MacCeRecord
{
    uint32_t ue_id;
    std::string traffic_class;
    double trigger_time_ms;
    double apply_time_ms;
    double macce_latency_ms;
    double rrc_baseline_ms;
    double saving_ms;
    double saving_pct;
    std::string from_mode;
    std::string to_mode;
    uint32_t num_ues;
    uint32_t seed;
    std::string label;
};
std::vector<MacCeRecord> macceLog;

// ---- STEP 1.B: modeled-event logging function ----
void
ModelMacCeAdaptation(uint32_t numUes,
                      std::vector<std::string> trafficClasses,
                      double triggerTimeMs,
                      double rrcBaselineMs,
                      uint32_t seed)
{
    const double slotMs = 0.5; // next-slot interval at 30 kHz SCS
    double applyMs = triggerTimeMs + slotMs;
    double savingMs = rrcBaselineMs - slotMs;
    double savingPct = (savingMs / rrcBaselineMs) * 100.0;

    for (uint32_t i = 0; i < numUes; i++)
    {
        macceLog.push_back({i,
                            (i < trafficClasses.size() ? trafficClasses[i] : "unknown"),
                            triggerTimeMs,
                            applyMs,
                            slotMs,
                            rrcBaselineMs,
                            savingMs,
                            savingPct,
                            "UM",
                            "AM",
                            numUes,
                            seed,
                            "modeled_macce_next_slot_interval -- NOT real OAI MAC-CE"});
    }
}

int
main(int argc, char* argv[])
{
    uint32_t rngSeed = 20260901;
    uint32_t rngRun = 1;

    uint32_t ueNum = 10;
    Time simTime = Seconds(30);
    Time udpAppStartTime = MilliSeconds(400);
    std::string outputDir = "./";
    std::string simTag = "cu-du-macce-model";

    DataRate f1LinkDataRate = DataRate("10Gbps");
    Time f1LinkDelay = MicroSeconds(100);
    uint32_t f1HeartbeatIntervalMs = 100;
    uint32_t f1HeartbeatPacketSize = 64;

    double centralFrequency = 3.5e9;
    double bandwidth = 189.0 * 12.0 * 30e3;
    uint16_t numerology = 1;
    double totalTxPower = 35;

    CommandLine cmd(__FILE__);
    cmd.AddValue("ueNum", "Number of UEs attached to the single gNB (DU)", ueNum);
    cmd.AddValue("simTime", "Simulated duration", simTime);
    cmd.AddValue("outputDir", "Directory for output files", outputDir);
    cmd.AddValue("simTag", "Tag appended to output filenames", simTag);
    cmd.AddValue("rngSeed", "ns-3 RNG seed (RngSeedManager)", rngSeed);
    cmd.AddValue("rngRun", "ns-3 RNG run number (RngSeedManager)", rngRun);
    cmd.Parse(argc, argv);

    // ---- RRC BASELINE VALIDATION ----
    // Verified exactly against ns3_phase01/ns3_phase01_validated_kpis.xlsx,
    // sheet "Baseline_NonPAIBO_Ladder", bearer_setup_latency_mean_ms column,
    // before this file was written. No interpolation, no fallback.
    std::map<uint32_t, double> rrcBaseline = {
        {1, 18.04},
        {10, 18.04},
        {25, 20.48},
        {50, 25.13},
        {100, 34.43},
        {150, 45.02},
        {200, 53.16},
    };
    if (rrcBaseline.count(ueNum) == 0)
    {
        NS_FATAL_ERROR("No validated RRC baseline for numUes=" << ueNum
                                                                << ". Add it to the map.");
    }
    double baseline = rrcBaseline[ueNum];

    RngSeedManager::SetSeed(rngSeed);
    RngSeedManager::SetRun(rngRun);

    Config::SetDefault("ns3::NrRlcUm::MaxTxBufferSize", UintegerValue(999999999));

    GridScenarioHelper gridScenario;
    gridScenario.SetRows(1);
    gridScenario.SetColumns(1);
    gridScenario.SetHorizontalBsDistance(10.0);
    gridScenario.SetVerticalBsDistance(10.0);
    gridScenario.SetBsHeight(10);
    gridScenario.SetUtHeight(1.5);
    gridScenario.SetSectorization(GridScenarioHelper::SINGLE);
    gridScenario.SetBsNumber(1);
    gridScenario.SetUtNumber(ueNum);
    gridScenario.SetScenarioHeight(3);
    gridScenario.SetScenarioLength(3);
    gridScenario.CreateScenario();

    NodeContainer ueContainer = gridScenario.GetUserTerminals();
    NodeContainer duContainer = gridScenario.GetBaseStations();

    Ptr<Node> cuNode = CreateObject<Node>();
    NodeContainer cuContainer(cuNode);

    NS_LOG_UNCOND("Configured UEs: " << ueContainer.GetN() << " DU(gNB)s: " << duContainer.GetN()
                                      << " CUs: " << cuContainer.GetN());

    Ptr<NrPointToPointEpcHelper> nrEpcHelper = CreateObject<NrPointToPointEpcHelper>();
    Ptr<IdealBeamformingHelper> idealBeamformingHelper = CreateObject<IdealBeamformingHelper>();
    Ptr<NrHelper> nrHelper = CreateObject<NrHelper>();
    nrHelper->SetBeamformingHelper(idealBeamformingHelper);
    nrHelper->SetEpcHelper(nrEpcHelper);

    BandwidthPartInfoPtrVector allBwps;
    CcBwpCreator ccBwpCreator;
    CcBwpCreator::SimpleOperationBandConf bandConf(centralFrequency, bandwidth, 1);
    OperationBandInfo band = ccBwpCreator.CreateOperationBandContiguousCc(bandConf);

    Ptr<NrChannelHelper> channelHelper = CreateObject<NrChannelHelper>();
    channelHelper->ConfigureFactories("RMa", "LOS", "ThreeGpp");
    channelHelper->SetPathlossAttribute("ShadowingEnabled", BooleanValue(false));
    channelHelper->AssignChannelsToBands({band}, NrChannelHelper::INIT_PROPAGATION);
    allBwps = CcBwpCreator::GetAllBwps({band});

    Packet::EnableChecking();
    Packet::EnablePrinting();

    idealBeamformingHelper->SetAttribute("BeamformingMethod",
                                         TypeIdValue(DirectPathBeamforming::GetTypeId()));
    nrEpcHelper->SetAttribute("S1uLinkDelay", TimeValue(MilliSeconds(0)));

    nrHelper->SetUeAntennaAttribute("NumRows", UintegerValue(2));
    nrHelper->SetUeAntennaAttribute("NumColumns", UintegerValue(4));
    nrHelper->SetUeAntennaAttribute("AntennaElement",
                                    PointerValue(CreateObject<IsotropicAntennaModel>()));
    nrHelper->SetGnbAntennaAttribute("NumRows", UintegerValue(4));
    nrHelper->SetGnbAntennaAttribute("NumColumns", UintegerValue(8));
    nrHelper->SetGnbAntennaAttribute("AntennaElement",
                                     PointerValue(CreateObject<IsotropicAntennaModel>()));

    NetDeviceContainer duNetDev = nrHelper->InstallGnbDevice(duContainer, allBwps);
    NetDeviceContainer ueNetDev = nrHelper->InstallUeDevice(ueContainer, allBwps);
    nrHelper->AssignStreams({.scenario = &gridScenario, .gnbDevs = duNetDev, .ueDevs = ueNetDev});

    NrHelper::GetGnbPhy(duNetDev.Get(0), 0)->SetAttribute("Numerology", UintegerValue(numerology));
    NrHelper::GetGnbPhy(duNetDev.Get(0), 0)->SetAttribute("TxPower", DoubleValue(totalTxPower));

    auto [remoteHost, remoteHostIpv4Address] =
        nrEpcHelper->SetupRemoteHost("100Gb/s", 2500, Seconds(0.000));

    InternetStackHelper internet;
    internet.Install(ueContainer);
    internet.Install(cuContainer);
    Ipv4InterfaceContainer ueIpIface = nrEpcHelper->AssignUeIpv4Address(ueNetDev);

    nrHelper->AttachToClosestGnb(ueNetDev, duNetDev);

    PointToPointHelper f1P2p;
    f1P2p.SetDeviceAttribute("DataRate", DataRateValue(f1LinkDataRate));
    f1P2p.SetChannelAttribute("Delay", TimeValue(f1LinkDelay));
    NetDeviceContainer f1Devices = f1P2p.Install(duContainer.Get(0), cuNode);

    Ipv4AddressHelper f1AddressHelper;
    f1AddressHelper.SetBase("10.63.0.0", "255.255.255.252");
    Ipv4InterfaceContainer f1IpIfaces = f1AddressHelper.Assign(f1Devices);

    uint16_t f1HeartbeatPort = 9999;
    PacketSinkHelper f1Sink("ns3::UdpSocketFactory",
                            InetSocketAddress(Ipv4Address::GetAny(), f1HeartbeatPort));
    ApplicationContainer f1SinkApp = f1Sink.Install(cuNode);
    OnOffHelper f1Heartbeat("ns3::UdpSocketFactory",
                            InetSocketAddress(f1IpIfaces.GetAddress(1), f1HeartbeatPort));
    f1Heartbeat.SetAttribute("DataRate",
                             DataRateValue(DataRate(uint64_t(f1HeartbeatPacketSize) * 8 * 1000 /
                                                     f1HeartbeatIntervalMs)));
    f1Heartbeat.SetAttribute("PacketSize", UintegerValue(f1HeartbeatPacketSize));
    f1Heartbeat.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1e9]"));
    f1Heartbeat.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0]"));
    ApplicationContainer f1HeartbeatApp = f1Heartbeat.Install(duContainer.Get(0));
    f1HeartbeatApp.Start(MilliSeconds(0));
    f1HeartbeatApp.Stop(simTime);
    f1SinkApp.Start(MilliSeconds(0));
    f1SinkApp.Stop(simTime);

    static uint32_t rrcConnectedCount = 0;
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/*/NrGnbRrc/ConnectionEstablished",
        MakeCallback(+[](uint64_t imsi, uint16_t cellId, uint16_t rnti) {
            rrcConnectedCount++;
        }));

    auto classes = GetTrafficClasses();
    auto ueCountsPerClass = DistributeUesAcrossClasses(ueNum, classes);

    ApplicationContainer serverApps;
    ApplicationContainer clientApps;
    uint16_t basePort = 20000;
    uint32_t ueIndex = 0;
    std::vector<std::string> trafficClassPerUe; // built inline below (Step 1.C note)

    std::ofstream trafficCfgFile(outputDir + "/" + simTag + "_traffic_config.tsv");
    trafficCfgFile << "class\tueCount\tperUeCapBps\tpacketSizeBytes\n";

    for (size_t c = 0; c < classes.size() && ueIndex < ueNum; ++c)
    {
        uint32_t n = std::min(ueCountsPerClass[c], ueNum - ueIndex);
        trafficCfgFile << classes[c].name << "\t" << n << "\t" << classes[c].perUeCapBps << "\t"
                       << classes[c].packetSize << "\n";
        for (uint32_t k = 0; k < n; ++k, ++ueIndex)
        {
            trafficClassPerUe.push_back(classes[c].name);

            uint16_t port = basePort + ueIndex;
            PacketSinkHelper sink("ns3::UdpSocketFactory",
                                  InetSocketAddress(Ipv4Address::GetAny(), port));
            serverApps.Add(sink.Install(ueContainer.Get(ueIndex)));

            OnOffHelper onoff("ns3::UdpSocketFactory",
                              InetSocketAddress(ueIpIface.GetAddress(ueIndex), port));
            onoff.SetAttribute("DataRate", DataRateValue(DataRate(uint64_t(classes[c].perUeCapBps))));
            onoff.SetAttribute("PacketSize", UintegerValue(classes[c].packetSize));
            onoff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1e9]"));
            onoff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0]"));
            clientApps.Add(onoff.Install(remoteHost));
        }
    }
    trafficCfgFile.close();

    serverApps.Start(udpAppStartTime);
    clientApps.Start(udpAppStartTime);
    serverApps.Stop(simTime);
    clientApps.Stop(simTime);

    // ---- STEP 1.C: schedule the modeled MAC-CE event at settle-time + 5s ----
    // "Settle time" analog = udpAppStartTime (the post-attach delay before
    // traffic apps begin); no variable literally named "settleTime" exists
    // in the base scenario (see Step 0 report).
    double triggerTimeSec = udpAppStartTime.GetSeconds() + 5.0;
    Simulator::Schedule(Seconds(triggerTimeSec),
                        &ModelMacCeAdaptation,
                        ueNum,
                        trafficClassPerUe,
                        triggerTimeSec * 1000.0,
                        baseline,
                        rngSeed);

    nrHelper->EnableTraces();

    FlowMonitorHelper flowmonHelper;
    NodeContainer endpointNodes;
    endpointNodes.Add(remoteHost);
    endpointNodes.Add(ueContainer);
    endpointNodes.Add(duContainer);
    endpointNodes.Add(cuContainer);
    Ptr<FlowMonitor> monitor = flowmonHelper.Install(endpointNodes);

    Simulator::Stop(simTime);

    auto wallClockStart = std::chrono::steady_clock::now();
    Simulator::Run();
    auto wallClockEnd = std::chrono::steady_clock::now();
    double wallClockSeconds = std::chrono::duration<double>(wallClockEnd - wallClockStart).count();

    monitor->CheckForLostPackets();
    monitor->SerializeToXmlFile(outputDir + "/" + simTag + "_flowmonitor.xml", true, true);

    // ---- STEP 1.D: write macce_latency.csv ----
    {
        std::string path = outputDir + "/macce_latency.csv";
        std::ofstream f(path);
        f << "ue_id,traffic_class,trigger_time_ms,"
             "apply_time_ms,macce_latency_ms,"
             "rrc_baseline_ms,saving_ms,saving_pct,"
             "from_mode,to_mode,num_ues,seed,label\n";

        for (auto& r : macceLog)
        {
            f << r.ue_id << "," << r.traffic_class << "," << r.trigger_time_ms << ","
              << r.apply_time_ms << "," << r.macce_latency_ms << "," << r.rrc_baseline_ms << ","
              << r.saving_ms << "," << r.saving_pct << "," << r.from_mode << "," << r.to_mode
              << "," << r.num_ues << "," << r.seed << "," << r.label << "\n";
        }

        if (!macceLog.empty())
        {
            double meanSaving = 0;
            for (auto& r : macceLog)
            {
                meanSaving += r.saving_ms;
            }
            meanSaving /= macceLog.size();
            double meanPct = (meanSaving / macceLog[0].rrc_baseline_ms) * 100.0;
            f << "CELL_SUMMARY,ALL," << macceLog[0].trigger_time_ms << ","
              << macceLog[0].apply_time_ms << "," << macceLog[0].macce_latency_ms << ","
              << macceLog[0].rrc_baseline_ms << "," << meanSaving << "," << meanPct << ","
              << "UM,AM," << macceLog[0].num_ues << "," << macceLog[0].seed << ","
              << "modeled_macce_next_slot_interval -- NOT real OAI MAC-CE\n";
        }
        f.close();
    }

    std::ofstream summary(outputDir + "/" + simTag + "_run_summary.tsv");
    summary << "metric\tvalue\n";
    summary << "configuredUeCount\t" << ueNum << "\n";
    summary << "rrcConnectedCount\t" << rrcConnectedCount << "\n";
    summary << "simulatedSeconds\t" << simTime.GetSeconds() << "\n";
    summary << "wallClockSeconds\t" << wallClockSeconds << "\n";
    summary << "rngSeed\t" << rngSeed << "\n";
    summary << "rngRun\t" << rngRun << "\n";
    summary.close();

    NS_LOG_UNCOND("RRC connected: " << rrcConnectedCount << " / " << ueNum);
    NS_LOG_UNCOND("Wall clock seconds: " << wallClockSeconds);
    NS_LOG_UNCOND("modeled macce_latency_ms = 0.5 (modeled next-slot application interval, "
                  "NOT a measured latency); rrc_baseline_ms = " << baseline);

    Simulator::Destroy();
    return 0;
}
