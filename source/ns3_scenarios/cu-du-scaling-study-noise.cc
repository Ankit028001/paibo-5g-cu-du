// SPDX-License-Identifier: GPL-2.0-only
//
// cu-du-scaling-study-noise.cc
//
// ============================================================================
// THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.
// IT IS NOT A REAL OAI CU-DU EXECUTION AND MUST NEVER BE PRESENTED AS SUCH.
// ============================================================================
//
// Derived from cu-du-scaling-study.cc (same CU/DU/F1-topology, EPC core, and
// 6-class traffic model -- see that file's header for the CU-DU topology
// limitation, not repeated here). The VALIDATED baseline in
// cu-du-scaling-study.cc is left completely unmodified; this is a separate
// file, and its output must go to a separate directory
// (ns3_cudu_phase_noise/), never overwriting the validated baseline.
//
// ADDS an "iperf-inspired / noise-augmented traffic model" (do NOT call
// this "iperf3 traffic" in any report or paper -- the implementation is
// ns-3's OnOffApplication, not real iperf3), per the original instruction:
// "Create a traffic pattern of a UE and a cell using iperf ... add some
// noise."
//
// IMPORTANT HONEST LIMITATION -- read before citing any number from this
// file: ns-3 UEs/gNB have no OS-level socket layer, so a real `iperf3`
// process cannot run against them. This file does NOT run real iperf3; it
// generates ns-3 application traffic whose STATISTICAL PROPERTIES
// approximate iperf3-observed real traffic (rate variability, packet-size
// variability, non-simultaneous start times). It must never be described
// as "real iperf3 traffic" -- use "iperf-inspired / noise-augmented
// traffic model" instead.
//
// A second honest limitation: this scenario's traffic is a single
// continuous ON burst per UE for the whole simulated duration (same as the
// validated baseline), not a sequence of discrete ON/OFF bursts. The
// per-burst lognormal rate-noise formula from the original noise-model
// specification (redrawn at every ON transition) therefore degenerates
// here to ONE random draw per UE for its one continuous burst, not a
// time-varying rate within a UE's flow. This is documented, not hidden.
// Genuinely time-varying per-burst noise would require replacing
// OnOffApplication with a custom traffic-generator application (a larger
// change, not implemented here).
//
// Noise actually implemented (three of the four originally specified
// noise types; the fourth -- fine-grained inter-packet timing jitter -- is
// NOT implemented, see NOISE_MODEL.md for why):
//   1. Per-UE lognormal rate variation: actual_rate = target_rate *
//      exp(sigma * Z), Z ~ N(0,1), one draw per UE, class-specific sigma.
//   2. Per-UE packet-size variation, drawn once per UE from a per-class
//      distribution (uniform range or fixed, per class).
//   3. Per-UE staggered application start offset, uniform per class.
//
// RNG stream assignment (per the original specification):
//   base = ue_index * 20
//   rate noise stream   = base + 10
//   size noise stream   = base + 11
//   start-offset stream = base + 13

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
#include <cmath>
#include <fstream>
#include <numeric>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("CuDuScalingStudyNoise");

struct TrafficClass
{
    std::string name;
    double shareOfUes;
    double perUeCapBps;
    uint32_t packetSize;
    double rateSigma;         // lognormal sigma for per-UE rate noise
    uint32_t pktSizeMin;      // 0 => use fixed packetSize (no size noise)
    uint32_t pktSizeMax;
    double maxStartOffsetSec; // uniform [0, maxStartOffsetSec]
};

static std::vector<TrafficClass>
GetTrafficClasses()
{
    return {
        {"mMTC", 0.40, 3000.0, 100, 0.25, 64, 256, 30.0},
        {"Web", 0.15, 133000.0, 600, 0.40, 512, 1500, 15.0},
        {"Mobile", 0.15, 166000.0, 800, 0.35, 512, 1400, 15.0},
        {"VoD", 0.12, 725000.0, 1200, 0.05, 0, 0, 10.0},    // fixed 1316B per spec; kept at 1200 to match baseline unless overridden below
        {"Live", 0.13, 478000.0, 1200, 0.10, 0, 0, 10.0},   // fixed 1316B per spec
        {"V2X", 0.05, 99000.0, 300, 0.08, 300, 600, 5.0},
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
    std::string simTag = "cu-du-scaling-noise";

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

    std::ofstream trafficCfgFile(outputDir + "/" + simTag + "_traffic_config.tsv");
    trafficCfgFile << "class\tueCount\tperUeCapBps\tpacketSizeBytes\n";

    std::ofstream noiseFile(outputDir + "/" + simTag + "_noise_applied.csv");
    noiseFile << "ue_id,imsi,class,nominal_rate_bps,actual_rate_bps,rate_sigma,"
                 "nominal_packet_size,actual_packet_size,start_offset_s,noise_model\n";

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

            uint32_t base = ueIndex * 20;

            // ---- Noise type 1: per-UE lognormal rate variation ----
            Ptr<NormalRandomVariable> rateNoiseRv = CreateObject<NormalRandomVariable>();
            rateNoiseRv->SetAttribute("Mean", DoubleValue(0.0));
            rateNoiseRv->SetAttribute("Variance", DoubleValue(1.0));
            rateNoiseRv->SetStream(base + 10);
            double z = rateNoiseRv->GetValue();
            double actualRateBps = classes[c].perUeCapBps * std::exp(classes[c].rateSigma * z);

            // ---- Noise type 2: per-UE packet-size variation ----
            uint32_t actualPacketSize = classes[c].packetSize;
            if (classes[c].pktSizeMin > 0)
            {
                Ptr<UniformRandomVariable> sizeNoiseRv = CreateObject<UniformRandomVariable>();
                sizeNoiseRv->SetAttribute("Min", DoubleValue(classes[c].pktSizeMin));
                sizeNoiseRv->SetAttribute("Max", DoubleValue(classes[c].pktSizeMax));
                sizeNoiseRv->SetStream(base + 11);
                actualPacketSize = static_cast<uint32_t>(sizeNoiseRv->GetValue());
            }

            // ---- Noise type 3: per-UE staggered start offset ----
            Ptr<UniformRandomVariable> offsetRv = CreateObject<UniformRandomVariable>();
            offsetRv->SetAttribute("Min", DoubleValue(0.0));
            offsetRv->SetAttribute("Max", DoubleValue(classes[c].maxStartOffsetSec));
            offsetRv->SetStream(base + 13);
            double startOffsetSec = offsetRv->GetValue();

            noiseFile << ueIndex << "," << (ueIndex + 1) << "," << classes[c].name << ","
                      << classes[c].perUeCapBps << "," << actualRateBps << "," << classes[c].rateSigma
                      << "," << classes[c].packetSize << "," << actualPacketSize << ","
                      << startOffsetSec << ",lognormal_rate_jitter_v1\n";

            OnOffHelper onoff("ns3::UdpSocketFactory",
                              InetSocketAddress(ueIpIface.GetAddress(ueIndex), port));
            onoff.SetAttribute("DataRate", DataRateValue(DataRate(uint64_t(actualRateBps))));
            onoff.SetAttribute("PacketSize", UintegerValue(actualPacketSize));
            onoff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1e9]"));
            onoff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0]"));
            ApplicationContainer thisClientApp = onoff.Install(remoteHost);
            thisClientApp.Start(udpAppStartTime + Seconds(startOffsetSec));
            thisClientApp.Stop(simTime);
            clientApps.Add(thisClientApp);
        }
    }
    trafficCfgFile.close();
    noiseFile.close();

    serverApps.Start(udpAppStartTime);
    serverApps.Stop(simTime);
    // clientApps already have individual (staggered) Start()/Stop() times set above.

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
    summary << "noiseEnabled\ttrue\n";
    summary << "noiseModel\tlognormal_rate_jitter_v1\n";
    summary.close();

    NS_LOG_UNCOND("RRC connected: " << rrcConnectedCount << " / " << ueNum);
    NS_LOG_UNCOND("Wall clock seconds: " << wallClockSeconds
                                         << " / simulated seconds: " << simTime.GetSeconds());

    Simulator::Destroy();
    return 0;
}
