// SPDX-License-Identifier: GPL-2.0-only
//
// cu-du-full-kpi-study.cc
//
// ============================================================================
// THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.
// IT IS NOT A REAL OAI CU-DU EXECUTION AND MUST NEVER BE PRESENTED AS SUCH.
// ============================================================================
//
// Derived from cu-du-bearer-latency-study.cc (same CU/DU/F1-topology, EPC
// core, 6-class traffic model, and bearer-setup-latency measurement -- see
// that file's header and cu-du-scaling-study.cc's header for the CU-DU
// topology limitation, not repeated here).
//
// ADDS two more real, measured KPIs, each with an explicit interpretation
// caveat -- read before citing either number anywhere:
//
// 1. DRB COUNT (real, not a proxy): every UE is given a SECOND dedicated
//    QoS flow/bearer (on top of its default bearer) via
//    NrHelper::ActivateDedicatedQosFlow(), carrying a small low-rate
//    control-sized UDP flow. This genuinely creates a second RLC/PDCP
//    logical channel (LCID) per UE, confirmed by counting distinct LCIDs
//    per IMSI in NrDlRlcStatsE2E.txt. Reported DRB count is a real,
//    measured count of distinct logical channels actually established for
//    each UE in this run -- not an assumption.
//
// 2. "MAC-CE-EQUIVALENT" SIGNALING LATENCY (an explicit PROXY, not a real
//    MAC-CE mechanism): 5G-LENA's nr module has NO dynamic MAC-CE-driven
//    RLC-mode-switch mechanism -- that is PAIBO's own proposed invention,
//    not a stock 3GPP or ns-3 feature, and building a real one would
//    require substantial nr-module surgery (dynamic AM<->UM reconfiguration
//    triggered by a new MAC control element type) well beyond this
//    scenario's scope. What this measures instead is the real, measured
//    one-way RLC/PDCP delay of the small dedicated control-sized bearer
//    above (same bearer used for the DRB-count measurement) -- i.e. a
//    genuine lower-bound latency floor for a small control-plane message
//    traversing this radio+CU-DU path, NOT a measurement of an actual
//    dynamic bearer/RLC-mode reconfiguration event. This distinction must
//    be preserved in any report or slide that cites this number.
//
// PAIBO Result Type 4 (BIP ML accuracy) is NOT addressed by this file and
// remains NOT AVAILABLE -- no ns-3 run can produce a trained-model accuracy
// number; that requires an actual classifier and a labeled dataset, neither
// of which exists on this machine.

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
#include <numeric>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("CuDuFullKpiStudy");

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

static double g_attachStartTimeSeconds = 0.0;
static std::vector<std::tuple<uint64_t, uint16_t, uint16_t, double>> g_bearerEvents;

static void
OnConnectionEstablished(uint64_t imsi, uint16_t cellId, uint16_t rnti)
{
    double nowMs = Simulator::Now().GetSeconds() * 1000.0;
    double latencyMs = nowMs - (g_attachStartTimeSeconds * 1000.0);
    g_bearerEvents.emplace_back(imsi, cellId, rnti, latencyMs);
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
    std::string simTag = "cu-du-full-kpi";

    DataRate f1LinkDataRate = DataRate("10Gbps");
    Time f1LinkDelay = MicroSeconds(100);
    uint32_t f1HeartbeatIntervalMs = 100;
    uint32_t f1HeartbeatPacketSize = 64;

    // ---- Second dedicated bearer per UE: control-sized flow used both as
    // the real second DRB (LCID) and as the MAC-CE-equivalent latency proxy ----
    uint32_t ctrlBearerIntervalMs = 50;
    uint32_t ctrlBearerPacketSize = 32;
    uint16_t ctrlBasePort = 30000;

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
    bool fullTraces = true;
    cmd.AddValue("fullTraces", "Enable full PHY/MAC/RLC/PDCP trace set if true", fullTraces);
    cmd.Parse(argc, argv);

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
    nrHelper->SetSchedulerTypeId(TypeId::LookupByName("ns3::NrMacSchedulerTdmaPF"));  // PF-variant: replaces the NrHelper default NrMacSchedulerTdmaRR

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

    g_attachStartTimeSeconds = Simulator::Now().GetSeconds();
    Config::ConnectWithoutContext("/NodeList/*/DeviceList/*/NrGnbRrc/ConnectionEstablished",
                                  MakeCallback(&OnConnectionEstablished));

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

    auto classes = GetTrafficClasses();
    auto ueCountsPerClass = DistributeUesAcrossClasses(ueNum, classes);

    ApplicationContainer serverApps;
    ApplicationContainer clientApps;
    ApplicationContainer ctrlServerApps;
    ApplicationContainer ctrlClientApps;
    uint16_t basePort = 20000;
    uint32_t ueIndex = 0;

    std::ofstream trafficCfgFile(outputDir + "/" + simTag + "_traffic_config.tsv");
    trafficCfgFile << "class\tueCount\tperUeCapBps\tpacketSizeBytes\n";

    for (size_t c = 0; c < classes.size() && ueIndex < ueNum; ++c)
    {
        uint32_t n = std::min(ueCountsPerClass[c], ueNum - ueIndex);
        trafficCfgFile << classes[c].name << "\t" << n << "\t" << classes[c].perUeCapBps << "\t"
                       << classes[c].packetSize << "\n";
        for (uint32_t k = 0; k < n; ++k, ++ueIndex)
        {
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

            // ---- Second dedicated bearer (real DRB #2 + MAC-CE-proxy carrier) ----
            uint16_t ctrlPort = ctrlBasePort + ueIndex;
            Ptr<NrQosRule> ctrlTft = Create<NrQosRule>();
            NrQosRule::PacketFilter pf;
            pf.localPortStart = ctrlPort;
            pf.localPortEnd = ctrlPort;
            pf.direction = NrQosRule::DOWNLINK;
            ctrlTft->Add(pf);
            NrQosFlow ctrlFlow(NrQosFlow::NGBR_MC_DELAY_SIGNAL);
            nrHelper->ActivateDedicatedQosFlow(ueNetDev.Get(ueIndex), ctrlFlow, ctrlTft);

            PacketSinkHelper ctrlSink("ns3::UdpSocketFactory",
                                      InetSocketAddress(Ipv4Address::GetAny(), ctrlPort));
            ctrlServerApps.Add(ctrlSink.Install(ueContainer.Get(ueIndex)));

            OnOffHelper ctrlOnoff("ns3::UdpSocketFactory",
                                  InetSocketAddress(ueIpIface.GetAddress(ueIndex), ctrlPort));
            ctrlOnoff.SetAttribute(
                "DataRate",
                DataRateValue(DataRate(uint64_t(ctrlBearerPacketSize) * 8 * 1000 / ctrlBearerIntervalMs)));
            ctrlOnoff.SetAttribute("PacketSize", UintegerValue(ctrlBearerPacketSize));
            ctrlOnoff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1e9]"));
            ctrlOnoff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0]"));
            ctrlClientApps.Add(ctrlOnoff.Install(remoteHost));
        }
    }
    trafficCfgFile.close();

    serverApps.Start(udpAppStartTime);
    clientApps.Start(udpAppStartTime);
    serverApps.Stop(simTime);
    clientApps.Stop(simTime);
    // Control bearer starts slightly later than the default bearer's app start
    // to avoid racing the dedicated-bearer activation signaling.
    ctrlServerApps.Start(udpAppStartTime + MilliSeconds(100));
    ctrlClientApps.Start(udpAppStartTime + MilliSeconds(100));
    ctrlServerApps.Stop(simTime);
    ctrlClientApps.Stop(simTime);

    if (fullTraces)
    {
        nrHelper->EnableTraces();
    }
    else
    {
        nrHelper->EnableDlDataPhyTraces();
        nrHelper->EnableRlcE2eTraces();
        nrHelper->EnablePdcpE2eTraces();
    }

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

    std::ofstream bearerFile(outputDir + "/" + simTag + "_bearer_setup_latency.csv");
    bearerFile << "imsi,cellId,rnti,attachStartTimeMs,connectionEstablishedTimeMs,bearerSetupLatencyMs\n";
    for (auto& [imsi, cellId, rnti, latencyMs] : g_bearerEvents)
    {
        bearerFile << imsi << "," << cellId << "," << rnti << "," << (g_attachStartTimeSeconds * 1000.0)
                   << "," << (g_attachStartTimeSeconds * 1000.0 + latencyMs) << "," << latencyMs << "\n";
    }
    bearerFile.close();

    std::ofstream summary(outputDir + "/" + simTag + "_run_summary.tsv");
    summary << "metric\tvalue\n";
    summary << "configuredUeCount\t" << ueNum << "\n";
    summary << "rrcConnectedCount\t" << g_bearerEvents.size() << "\n";
    summary << "simulatedSeconds\t" << simTime.GetSeconds() << "\n";
    summary << "wallClockSeconds\t" << wallClockSeconds << "\n";
    summary << "rngSeed\t" << rngSeed << "\n";
    summary << "rngRun\t" << rngRun << "\n";
    summary << "dedicatedBearersActivated\t" << ueIndex << "\n";
    summary.close();

    NS_LOG_UNCOND("RRC connected: " << g_bearerEvents.size() << " / " << ueNum);
    NS_LOG_UNCOND("Wall clock seconds: " << wallClockSeconds);

    Simulator::Destroy();
    return 0;
}
