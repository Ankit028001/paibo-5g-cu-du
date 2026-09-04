// SPDX-License-Identifier: GPL-2.0-only
//
// ue-scaling-study.cc
//
// ============================================================================
// THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.
// IT IS NOT A REAL OAI CU-DU EXECUTION AND MUST NEVER BE PRESENTED AS SUCH.
// It is a separate study, answering a different question than the OAI
// vrtsim/rfsimulator real-time experiments in this investigation, and its
// results must not be combined with OAI-measured data as if equivalent.
// ============================================================================
//
// Single-gNB NR cell, UE-count scaling study. Based on the stock 5G-LENA
// contrib/nr/examples/cttc-nr-demo.cc example (single band/CC/BWP variant),
// extended with:
//  - a single carrier approximating 189 PRB @ 30 kHz SCS, band n78 (~3.5 GHz)
//  - a channel configured for INIT_PROPAGATION only (no fading model
//    attached), i.e. deterministic path loss with no fast fading/multipath,
//    the closest 5G-LENA analog to the OAI "IDEAL" channel (chanmod=0)
//  - a 6-class heterogeneous downlink traffic model (mMTC, Web, Mobile, VoD,
//    Live, V2X) with per-UE rate caps taken from the OAI phase2 100-UE
//    traffic_model.md reference table, proportionally distributed by UE count
//  - RRC "ConnectionEstablished" trace counting for actual attach confirmation
//  - FlowMonitor XML output for per-UE/aggregate throughput, loss, delay
//  - NrHelper::EnableTraces() for PHY-level per-UE SINR/MCS traces

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

NS_LOG_COMPONENT_DEFINE("UeScalingStudy");

// ---------------------------------------------------------------------------
// Six-class traffic model (reference: OAI phase2 100-UE traffic_model.md)
// ---------------------------------------------------------------------------
struct TrafficClass
{
    std::string name;
    double shareOfUes; // fraction of total UE count assigned to this class
    double perUeCapBps; // per-UE downlink rate cap in bits/second
    uint32_t packetSize; // bytes
};

// Class order and shares match the OAI 100-UE reference table exactly:
// mMTC 40/100, Web 15/100, Mobile 15/100, VoD 12/100, Live 13/100, V2X 5/100.
// Per-UE caps also taken directly from that table (~3k/133k/166k/725k/478k/99k).
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

// Proportionally distribute ueTotal UEs across the six classes, preserving
// the class order and largest-remainder rounding so the counts sum exactly
// to ueTotal.
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
    // Distribute leftover UEs to classes with the largest fractional remainder
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
    // ---- Fixed identity / determinism ----
    uint32_t rngSeed = 20260901;
    uint32_t rngRun = 1;

    // ---- Scenario parameters ----
    uint32_t ueNum = 10;
    Time simTime = Seconds(30);
    Time udpAppStartTime = MilliSeconds(400);
    std::string outputDir = "./";
    std::string simTag = "ue-scaling";

    // ---- Carrier: target 189 PRB @ 30 kHz SCS, band n78 (~3.5 GHz) ----
    // 189 PRB * 12 subcarriers/PRB * 30 kHz = 68.04 MHz. Numerology 1 = 30 kHz SCS in the
    // NR module's numerology table (2^n * 15 kHz). This is the closest supported
    // approximation available via NrChannelHelper/CcBwpCreator; actual usable RB count
    // is computed internally by the module from bandwidth+numerology and is logged below
    // for verification (any deviation from 189 is documented in SUMMARY.md).
    double centralFrequency = 3.5e9;
    double bandwidth = 189.0 * 12.0 * 30e3; // 68,040,000 Hz
    uint16_t numerology = 1;                // 30 kHz SCS
    double totalTxPower = 35;               // dBm, matches cttc-nr-demo default

    CommandLine cmd(__FILE__);
    cmd.AddValue("ueNum", "Number of UEs attached to the single gNB", ueNum);
    cmd.AddValue("simTime", "Simulated duration", simTime);
    cmd.AddValue("outputDir", "Directory for output files", outputDir);
    cmd.AddValue("simTag", "Tag appended to output filenames", simTag);
    cmd.AddValue("rngSeed", "ns-3 RNG seed (RngSeedManager)", rngSeed);
    cmd.AddValue("rngRun", "ns-3 RNG run number (RngSeedManager)", rngRun);
    bool fullTraces = true;
    cmd.AddValue("fullTraces",
                 "If true (default), enable the full NrHelper::EnableTraces() set "
                 "(PHY/MAC ctrl msgs + pathloss + SINR/MCS + RLC/PDCP). If false, "
                 "enable only the reduced KPI-relevant set (SINR/MCS via "
                 "EnableDlDataPhyTraces, RLC/PDCP E2E) to reduce I/O and runtime at "
                 "high UE counts; this deviation, if used, must be documented in "
                 "the level's SUMMARY.md.",
                 fullTraces);
    cmd.Parse(argc, argv);

    // ---- Determinism: real ns-3 RNG seeding (verified separately by running
    // this program twice with identical arguments and diffing FlowMonitor XML) ----
    RngSeedManager::SetSeed(rngSeed);
    RngSeedManager::SetRun(rngRun);

    Config::SetDefault("ns3::NrRlcUm::MaxTxBufferSize", UintegerValue(999999999));

    // ---- Topology: single gNB cell, UEs in a small grid around it ----
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
    NodeContainer gnbContainer = gridScenario.GetBaseStations();

    NS_LOG_UNCOND("Configured UEs: " << ueContainer.GetN() << " gNBs: " << gnbContainer.GetN());

    // ---- NR stack helpers ----
    Ptr<NrPointToPointEpcHelper> nrEpcHelper = CreateObject<NrPointToPointEpcHelper>();
    Ptr<IdealBeamformingHelper> idealBeamformingHelper = CreateObject<IdealBeamformingHelper>();
    Ptr<NrHelper> nrHelper = CreateObject<NrHelper>();
    nrHelper->SetBeamformingHelper(idealBeamformingHelper);
    nrHelper->SetEpcHelper(nrEpcHelper);

    BandwidthPartInfoPtrVector allBwps;
    CcBwpCreator ccBwpCreator;
    CcBwpCreator::SimpleOperationBandConf bandConf(centralFrequency, bandwidth, 1);
    OperationBandInfo band = ccBwpCreator.CreateOperationBandContiguousCc(bandConf);

    // ---- Channel: IDEAL-analog = deterministic path loss only, NO fading model ----
    // NrChannelHelper::AssignChannelsToBands is called with INIT_PROPAGATION only
    // (fading/spectrum matrix model is deliberately NOT attached), which is the
    // closest 5G-LENA analog to the OAI IDEAL channel (chanmod=0, no added noise/
    // multipath). Path loss model selected: ns-3 ThreeGpp RMa LOS pathloss
    // (deterministic distance-based, no shadowing -- ShadowingEnabled=false below).
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

    NetDeviceContainer gnbNetDev = nrHelper->InstallGnbDevice(gnbContainer, allBwps);
    NetDeviceContainer ueNetDev = nrHelper->InstallUeDevice(ueContainer, allBwps);
    nrHelper->AssignStreams({.scenario = &gridScenario, .gnbDevs = gnbNetDev, .ueDevs = ueNetDev});

    NrHelper::GetGnbPhy(gnbNetDev.Get(0), 0)->SetAttribute("Numerology", UintegerValue(numerology));
    NrHelper::GetGnbPhy(gnbNetDev.Get(0), 0)
        ->SetAttribute("TxPower", DoubleValue(totalTxPower));

    NS_LOG_UNCOND("Actual RB count for this BWP: "
                  << allBwps[0].get()->m_channelBandwidth / (12.0 * 30e3) << " (target 189)");

    auto [remoteHost, remoteHostIpv4Address] =
        nrEpcHelper->SetupRemoteHost("100Gb/s", 2500, Seconds(0.000));

    InternetStackHelper internet;
    internet.Install(ueContainer);
    Ipv4InterfaceContainer ueIpIface = nrEpcHelper->AssignUeIpv4Address(ueNetDev);

    nrHelper->AttachToClosestGnb(ueNetDev, gnbNetDev);

    // ---- RRC connection tracking: count real ConnectionEstablished events, not
    // just device-object creation ----
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

    // ---- PHY/MAC/RLC/PDCP traces (per-UE SINR, MCS, TB size, pathloss, etc.) ----
    if (fullTraces)
    {
        nrHelper->EnableTraces();
    }
    else
    {
        // Reduced set: still covers every KPI required by this study (per-UE SINR,
        // MCS/TB size via RxPacketTrace, RLC/PDCP E2E delay) while skipping the very
        // high-volume PHY/MAC control-message and per-pair pathloss traces that do
        // not map to a required KPI and dominate I/O/runtime at high UE counts.
        nrHelper->EnableDlDataPhyTraces();
        nrHelper->EnableRlcE2eTraces();
        nrHelper->EnablePdcpE2eTraces();
    }

    // ---- FlowMonitor: per-flow (per-UE) throughput, loss, delay, jitter ----
    FlowMonitorHelper flowmonHelper;
    NodeContainer endpointNodes;
    endpointNodes.Add(remoteHost);
    endpointNodes.Add(ueContainer);
    Ptr<FlowMonitor> monitor = flowmonHelper.Install(endpointNodes);
    monitor->SetAttribute("DelayBinWidth", DoubleValue(0.001));
    monitor->SetAttribute("JitterBinWidth", DoubleValue(0.001));
    monitor->SetAttribute("PacketSizeBinWidth", DoubleValue(20));

    Simulator::Stop(simTime);

    auto wallClockStart = std::chrono::steady_clock::now();
    Simulator::Run();
    auto wallClockEnd = std::chrono::steady_clock::now();
    double wallClockSeconds =
        std::chrono::duration<double>(wallClockEnd - wallClockStart).count();

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
    summary.close();

    NS_LOG_UNCOND("RRC connected: " << rrcConnectedCount << " / " << ueNum);
    NS_LOG_UNCOND("Wall clock seconds: " << wallClockSeconds
                                         << " / simulated seconds: " << simTime.GetSeconds());

    Simulator::Destroy();
    return 0;
}
