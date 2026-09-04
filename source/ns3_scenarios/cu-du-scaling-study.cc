// SPDX-License-Identifier: GPL-2.0-only
//
// cu-du-scaling-study.cc
//
// ============================================================================
// THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.
// IT IS NOT A REAL OAI CU-DU EXECUTION AND MUST NEVER BE PRESENTED AS SUCH.
// ============================================================================
//
// Same scenario as ue-scaling-study.cc (single-gNB, 6-class traffic model,
// IDEAL-analog channel, EPC core), extended with a topological CU/DU split:
//
//   UE(s) <--radio--> DU node (real NrGnbNetDevice: PHY/MAC/RLC/PDCP/RRC)
//                        |
//                        | F1 link (point-to-point, stands in for F1-C/F1-U)
//                        |
//                     CU node
//                        |
//                        | S1-U (unchanged from stock EPC helper wiring)
//                        |
//                    SGW/PGW <--> remote host
//
// IMPORTANT LIMITATION (must be read before interpreting any KPI from this
// scenario as a real CU/DU split result): the 5G-LENA `nr` module's gNB
// model bundles PHY, MAC, RLC, PDCP and RRC into a single NrGnbNetDevice
// object that must live on one ns-3 node. The module has no F1AP
// implementation and no supported way to relocate PDCP/RRC (the functions a
// real gNB-CU terminates) onto a separate node from PHY/MAC (the functions a
// real gNB-DU terminates) without modifying the module's internals. This
// scenario therefore does NOT move any protocol layer to the CU node. What
// it adds is a genuine, separate ns-3 CU node connected to the DU node by a
// dedicated point-to-point link (representing the F1 interface), carrying a
// periodic UDP "F1 heartbeat" flow whose byte counts and delay are collected
// as real, measured KPIs of that link. The actual UE bearer traffic
// continues to transit the DU node's existing automatic S1-U tunnel to the
// SGW/PGW (this is unavoidable without deep module surgery: the EPC helper's
// GTP-U application is bound to the node holding the real NrGnbNetDevice).
// This is a topological CU-DU split, not a functional one. Report this
// limitation alongside any KPI drawn from this scenario.

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

NS_LOG_COMPONENT_DEFINE("CuDuScalingStudy");

// ---------------------------------------------------------------------------
// Six-class traffic model (reference: OAI phase2 100-UE traffic_model.md)
// ---------------------------------------------------------------------------
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

int
main(int argc, char* argv[])
{
    uint32_t rngSeed = 20260901;
    uint32_t rngRun = 1;

    uint32_t ueNum = 10;
    Time simTime = Seconds(30);
    Time udpAppStartTime = MilliSeconds(400);
    std::string outputDir = "./";
    std::string simTag = "cu-du-scaling";

    // ---- F1 link parameters (DU <-> CU) ----
    // 10 Gb/s, 100 us one-way delay: a typical midhaul/fronthaul-class assumption
    // for a co-sited or nearby CU-DU split (F1 has no fixed 3GPP delay budget;
    // this is a documented assumption, not a measured or standardized value).
    DataRate f1LinkDataRate = DataRate("10Gbps");
    Time f1LinkDelay = MicroSeconds(100);
    // Small periodic UDP flow standing in for F1AP heartbeat/keep-alive traffic
    // (real F1AP messages are much smaller and event-driven; this is a
    // simplified, constant-rate placeholder so the F1 link carries measurable,
    // real traffic instead of being a purely idle topological prop).
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
    cmd.AddValue("f1LinkDataRate", "DU<->CU F1 link data rate", f1LinkDataRate);
    cmd.AddValue("f1LinkDelay", "DU<->CU F1 link one-way delay", f1LinkDelay);
    bool fullTraces = true;
    cmd.AddValue("fullTraces",
                 "If true (default), enable the full NrHelper::EnableTraces() set. "
                 "If false, enable only the reduced KPI-relevant set to reduce I/O "
                 "and runtime at high UE counts.",
                 fullTraces);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(rngSeed);
    RngSeedManager::SetRun(rngRun);

    Config::SetDefault("ns3::NrRlcUm::MaxTxBufferSize", UintegerValue(999999999));

    // ---- Topology: single gNB (DU) cell, UEs in a small grid around it ----
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
    NodeContainer duContainer = gridScenario.GetBaseStations(); // DU: hosts the real NrGnbNetDevice

    // ---- CU node: separate ns-3 node, connected to the DU via a dedicated
    // point-to-point link standing in for the F1 interface ----
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

    NS_LOG_UNCOND("Actual RB count for this BWP: "
                  << allBwps[0].get()->m_channelBandwidth / (12.0 * 30e3) << " (target 189)");

    auto [remoteHost, remoteHostIpv4Address] =
        nrEpcHelper->SetupRemoteHost("100Gb/s", 2500, Seconds(0.000));

    InternetStackHelper internet;
    internet.Install(ueContainer);
    internet.Install(cuContainer);
    Ipv4InterfaceContainer ueIpIface = nrEpcHelper->AssignUeIpv4Address(ueNetDev);

    nrHelper->AttachToClosestGnb(ueNetDev, duNetDev);

    // ---- F1 link: DU <-> CU point-to-point, own IP subnet, own traffic ----
    PointToPointHelper f1P2p;
    f1P2p.SetDeviceAttribute("DataRate", DataRateValue(f1LinkDataRate));
    f1P2p.SetChannelAttribute("Delay", TimeValue(f1LinkDelay));
    NetDeviceContainer f1Devices = f1P2p.Install(duContainer.Get(0), cuNode);

    Ipv4AddressHelper f1AddressHelper;
    f1AddressHelper.SetBase("10.63.0.0", "255.255.255.252");
    Ipv4InterfaceContainer f1IpIfaces = f1AddressHelper.Assign(f1Devices);
    Ipv4Address duF1Address = f1IpIfaces.GetAddress(0);
    Ipv4Address cuF1Address = f1IpIfaces.GetAddress(1);

    uint16_t f1HeartbeatPort = 9999;
    PacketSinkHelper f1Sink("ns3::UdpSocketFactory",
                            InetSocketAddress(Ipv4Address::GetAny(), f1HeartbeatPort));
    ApplicationContainer f1SinkApp = f1Sink.Install(cuNode);

    OnOffHelper f1Heartbeat("ns3::UdpSocketFactory", InetSocketAddress(cuF1Address, f1HeartbeatPort));
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

    // ---- RRC connection tracking ----
    static uint32_t rrcConnectedCount = 0;
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/*/NrGnbRrc/ConnectionEstablished",
        MakeCallback(+[](uint64_t imsi, uint16_t cellId, uint16_t rnti) {
            rrcConnectedCount++;
        }));

    // ---- Traffic: 6-class heterogeneous downlink model, proportional to ueNum ----
    auto classes = GetTrafficClasses();
    auto ueCountsPerClass = DistributeUesAcrossClasses(ueNum, classes);

    ApplicationContainer serverApps;
    ApplicationContainer clientApps;
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
        }
    }
    trafficCfgFile.close();

    serverApps.Start(udpAppStartTime);
    clientApps.Start(udpAppStartTime);
    serverApps.Stop(simTime);
    clientApps.Stop(simTime);

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

    // ---- FlowMonitor: UE bearer traffic (remote host <-> UEs) AND the F1
    // heartbeat flow (DU <-> CU), so the F1 link's own delay/throughput are
    // measured KPIs, not assumed ----
    FlowMonitorHelper flowmonHelper;
    NodeContainer endpointNodes;
    endpointNodes.Add(remoteHost);
    endpointNodes.Add(ueContainer);
    endpointNodes.Add(duContainer);
    endpointNodes.Add(cuContainer);
    Ptr<FlowMonitor> monitor = flowmonHelper.Install(endpointNodes);
    monitor->SetAttribute("DelayBinWidth", DoubleValue(0.001));
    monitor->SetAttribute("JitterBinWidth", DoubleValue(0.001));
    monitor->SetAttribute("PacketSizeBinWidth", DoubleValue(20));

    Simulator::Stop(simTime);

    auto wallClockStart = std::chrono::steady_clock::now();
    Simulator::Run();
    auto wallClockEnd = std::chrono::steady_clock::now();
    double wallClockSeconds = std::chrono::duration<double>(wallClockEnd - wallClockStart).count();

    monitor->CheckForLostPackets();
    monitor->SerializeToXmlFile(outputDir + "/" + simTag + "_flowmonitor.xml", true, true);

    std::ofstream summary(outputDir + "/" + simTag + "_run_summary.tsv");
    summary << "metric\tvalue\n";
    summary << "configuredUeCount\t" << ueNum << "\n";
    summary << "rrcConnectedCount\t" << rrcConnectedCount << "\n";
    summary << "simulatedSeconds\t" << simTime.GetSeconds() << "\n";
    summary << "wallClockSeconds\t" << wallClockSeconds << "\n";
    summary << "rngSeed\t" << rngSeed << "\n";
    summary << "rngRun\t" << rngRun << "\n";
    summary << "actualRbCount\t" << (allBwps[0].get()->m_channelBandwidth / (12.0 * 30e3)) << "\n";
    summary << "duNodeId\t" << duContainer.Get(0)->GetId() << "\n";
    summary << "cuNodeId\t" << cuNode->GetId() << "\n";
    summary << "f1LinkDataRateBps\t" << f1LinkDataRate.GetBitRate() << "\n";
    summary << "f1LinkDelaySeconds\t" << f1LinkDelay.GetSeconds() << "\n";
    summary << "duF1Address\t" << duF1Address << "\n";
    summary << "cuF1Address\t" << cuF1Address << "\n";
    summary.close();

    NS_LOG_UNCOND("RRC connected: " << rrcConnectedCount << " / " << ueNum);
    NS_LOG_UNCOND("Wall clock seconds: " << wallClockSeconds
                                         << " / simulated seconds: " << simTime.GetSeconds());
    NS_LOG_UNCOND("DU node id: " << duContainer.Get(0)->GetId()
                                 << " CU node id: " << cuNode->GetId()
                                 << " F1 link: " << duF1Address << " <-> " << cuF1Address);

    Simulator::Destroy();
    return 0;
}
