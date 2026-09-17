// SPDX-License-Identifier: GPL-2.0-only
//
// standard-attach-baseline-study.cc
//
// ============================================================================
// THIS IS AN ns-3 / 5G-LENA DISCRETE-EVENT NETWORK SIMULATION.
// IT IS NOT A REAL OAI CU-DU EXECUTION, A REAL 5GC, OR A REAL 3GPP UE/gNB/AMF
// PROTOCOL STACK. IT MUST NEVER BE PRESENTED AS HAVING MEASURED REAL NAS/NGAP
// SIGNALING.
// ============================================================================
//
// Derived from cu-du-bearer-latency-study.cc (same CU/DU/F1-topology, EPC
// core, and 6-class traffic model -- see that file's header for the CU-DU
// topology limitation, which applies identically here and is not repeated).
//
// PURPOSE
// -------
// Build a standard 3GPP attach *timeline baseline* that follows the same
// message sequence as the "Standard 3GPP Attach Procedure" diagram in
// 5g-sa-paibo-attach-comparison.pptx, so that a later PAIBO-attach variant
// can be produced by moving exactly one block of steps (the
// RRCReconfiguration DRB/s step) earlier in the same chain and re-running,
// with the KPI columns below computed identically for both.
//
// WHAT IS ACTUALLY MEASURED vs. WHAT IS MODELED
// -----------------------------------------------
// Per docs/standard_attach_ns3_measurement_plan.md, NrPointToPointEpcHelper
// implements no NAS/NGAP stack: there is no real Registration Request/Accept,
// no real PDU Session Establishment, and no real PDU Session Resource Setup
// procedure anywhere in this simulator. Exactly ONE step in the diagram is a
// real, simulated ns-3 event:
//
//   MEASURED (real ns-3 discrete event):
//     "Till RRCSetupComplete (Registration Request)" (UE<->gNB)
//       == NrGnbRrc trace source ConnectionEstablished(imsi, cellId, rnti)
//
// Every other step in the diagram (Initial UE Message, Authentication,
// Security Mode Command/Complete at NAS and AS level, Initial Context Setup,
// UE Capability exchange, Registration Accept/Complete, PDU Session
// Establishment Request, PDU Session Resource Setup Request/Response, and
// RRCReconfiguration for the DRB/s) is NOT implemented by this module and is
// therefore MODELED as a fixed-size, scheduled-forward timing chain anchored
// at the real ConnectionEstablished timestamp. Each one-way hop in that
// chain advances simulated time by --hopDelayMs, a single configurable delay
// derived from (and, in this scenario, applied identically to) the EPC
// S1uLinkDelay attribute already used by the existing CU-DU scenarios -- no
// new, independently-invented latency constant is introduced. This keeps the
// model's only "made up" input the same one knob the existing baseline
// scenarios already expose.
//
// Every column produced by this scenario that is not the real RRC event is
// prefixed/documented below as MODELED. Do not cite MODELED columns as
// ns-3-measured 3GPP signaling latency; they are a synthetic scaffold for
// comparing "where does the DRB/s get configured" between the standard and
// (future) PAIBO attach chains.
//
// Diagram-step -> column mapping (standard order; see pptx image-1-1.png):
//   1  Initial UE Message (Registration Request)         initialUeMessageMs
//   2  Authentication Request                             authRequestMs
//   3  Authentication Response                             authResponseMs
//   4  Security Mode Command (NAS)                         securityModeCommandNasMs
//   5  Security Mode Complete (NAS)                        securityModeCompleteNasMs
//   6  Initial Context Setup Request                       initialContextSetupRequestMs
//   7  SecurityModeCommand (AS)                             securityModeCommandAsMs
//   8  SecurityModeComplete (AS)                            securityModeCompleteAsMs
//   9  UECapabilityEnquiry                                  ueCapabilityEnquiryMs
//   10 UECapabilityInformation                              ueCapabilityInformationMs
//   11 Initial Context Setup Response                       initialContextSetupResponseMs
//   12 Registration Accept via DLInformationTransfer        registrationAcceptMs
//   13 Registration Complete                                registrationCompleteMs
//   14 PDU Session Establishment Request                    pduSessionEstablishmentRequestMs
//   15 PDU Session Resource Setup Request                   pduSessionResourceSetupRequestMs
//   16 RRCReconfiguration(DRB/s) + PDU Session Est. Accept   rrcReconfigurationDrbMs
//   17 RRCReconfiguration Complete                          rrcReconfigurationCompleteMs
//   18 PDU Session Resource Setup Response                  pduSessionResourceSetupResponseMs
//   -- Data ready to flow (DL, UL)                          dataReadyMs (== step 18; the
//      diagram draws no further signaling hop after the PDU Session Resource
//      Setup Response, so no extra --hopDelayMs is added for it)
//
// In this STANDARD baseline, step 16 (RRCReconfiguration DRB/s) sits where
// the diagram puts it: after the PDU Session Resource Setup Request (step
// 15). A future PAIBO-attach variant is expected to move that same step to
// sit right after step 11 (Initial Context Setup Response), i.e. before the
// PDU Session Establishment Request, and is out of scope for this file.
//
// FIRST-DATA-PACKET KPI (added; see docs/standard_attach_baseline_ns3.md)
// -------------------------------------------------------------------------
// firstDataPacketTimeMs is a SECOND, INDEPENDENT MEASURED value -- it is
// FlowMonitor's actual recorded timeFirstRxPacket for this UE's application
// UDP flow (remoteHost -> UE), read via FlowMonitor::GetFlowStats() and
// joined to the UE's IMSI by matching the flow's destination
// address/port against the UE's assigned IP and application port. It is
// NOT derived from, and does not replace, the MODELED dataReadyMs chain.
// The two can differ substantially because application traffic starts at
// a separately-configured time (udpAppStartTime) that has no relationship
// to the modeled signaling chain's timing. If no packet was ever received
// for a UE (e.g. traffic never started, or was lost), firstDataPacketTimeMs
// and attachToFirstDataPacketLatencyMs are written as "NA" -- never a
// fabricated 0 or a substituted dataReadyMs value.

#include "ns3/antenna-module.h"
#include "ns3/applications-module.h"
#include "ns3/buildings-module.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/ipv4-flow-classifier.h"
#include "ns3/mobility-module.h"
#include "ns3/nr-module.h"
#include "ns3/point-to-point-module.h"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <map>
#include <numeric>
#include <sstream>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("StandardAttachBaselineStudy");

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

// ---- Standard-attach timeline: one MEASURED anchor (rrcSetupCompleteMs)
// plus 18 MODELED forward hops, one --hopDelayMs apart, following the
// diagram-step order documented in the file header. ----
struct AttachStepTimes
{
    uint64_t imsi = 0;
    uint16_t cellId = 0;
    uint16_t rnti = 0;

    double attachStartMs = 0.0;       // MEASURED (batch attach-call instant)
    double rrcSetupCompleteMs = 0.0;  // MEASURED (NrGnbRrc::ConnectionEstablished)

    double initialUeMessageMs = 0.0;             // MODELED
    double authRequestMs = 0.0;                  // MODELED
    double authResponseMs = 0.0;                 // MODELED
    double securityModeCommandNasMs = 0.0;       // MODELED
    double securityModeCompleteNasMs = 0.0;      // MODELED
    double initialContextSetupRequestMs = 0.0;   // MODELED
    double securityModeCommandAsMs = 0.0;        // MODELED
    double securityModeCompleteAsMs = 0.0;       // MODELED
    double ueCapabilityEnquiryMs = 0.0;          // MODELED
    double ueCapabilityInformationMs = 0.0;      // MODELED
    double initialContextSetupResponseMs = 0.0;  // MODELED
    double registrationAcceptMs = 0.0;           // MODELED
    double registrationCompleteMs = 0.0;         // MODELED
    double pduSessionEstablishmentRequestMs = 0.0; // MODELED
    double pduSessionResourceSetupRequestMs = 0.0; // MODELED
    double rrcReconfigurationDrbMs = 0.0;          // MODELED
    double rrcReconfigurationCompleteMs = 0.0;     // MODELED
    double pduSessionResourceSetupResponseMs = 0.0; // MODELED
    double dataReadyMs = 0.0;                      // MODELED (== step 18)

    // MEASURED (independent of the modeled chain above): FlowMonitor's own
    // recorded first-Rx-packet time for this UE's application flow, and the
    // latency from real attach start to that real event. -1.0 == "no packet
    // observed for this UE" (never fabricated as 0 or substituted with
    // dataReadyMs).
    double firstDataPacketTimeMs = -1.0;            // MEASURED (FlowMonitor)
    double attachToFirstDataPacketLatencyMs = -1.0; // MEASURED (FlowMonitor)
};

// Per-UE join key so the FlowMonitor first-Rx-packet measurement (only
// available after Simulator::Run() completes) can be matched back to the
// IMSI recorded by OnConnectionEstablished during the run.
struct UeFlowKey
{
    uint64_t imsi = 0;
    Ipv4Address destAddress;
    uint16_t destPort = 0;
};

static double g_attachStartTimeSeconds = 0.0;
static double g_modeledHopDelayMs = 0.1;
static std::vector<AttachStepTimes> g_attachTimelines;
static std::vector<UeFlowKey> g_ueFlowKeys;

static void
OnConnectionEstablished(uint64_t imsi, uint16_t cellId, uint16_t rnti)
{
    AttachStepTimes rec;
    rec.imsi = imsi;
    rec.cellId = cellId;
    rec.rnti = rnti;
    rec.attachStartMs = g_attachStartTimeSeconds * 1000.0;
    rec.rrcSetupCompleteMs = Simulator::Now().GetSeconds() * 1000.0;

    double t = rec.rrcSetupCompleteMs;
    auto nextHop = [&]() {
        t += g_modeledHopDelayMs;
        return t;
    };

    rec.initialUeMessageMs = nextHop();
    rec.authRequestMs = nextHop();
    rec.authResponseMs = nextHop();
    rec.securityModeCommandNasMs = nextHop();
    rec.securityModeCompleteNasMs = nextHop();
    rec.initialContextSetupRequestMs = nextHop();
    rec.securityModeCommandAsMs = nextHop();
    rec.securityModeCompleteAsMs = nextHop();
    rec.ueCapabilityEnquiryMs = nextHop();
    rec.ueCapabilityInformationMs = nextHop();
    rec.initialContextSetupResponseMs = nextHop();
    rec.registrationAcceptMs = nextHop();
    rec.registrationCompleteMs = nextHop();
    rec.pduSessionEstablishmentRequestMs = nextHop();
    rec.pduSessionResourceSetupRequestMs = nextHop();
    rec.rrcReconfigurationDrbMs = nextHop();
    rec.rrcReconfigurationCompleteMs = nextHop();
    rec.pduSessionResourceSetupResponseMs = nextHop();
    rec.dataReadyMs = rec.pduSessionResourceSetupResponseMs;

    g_attachTimelines.push_back(rec);
}

int
main(int argc, char* argv[])
{
    uint32_t rngSeed = 20260901;
    uint32_t rngRun = 1;

    uint32_t ueNum = 1;
    Time simTime = Seconds(30);
    Time udpAppStartTime = MilliSeconds(400);
    std::string outputDir = "./";
    std::string simTag = "standard-attach-baseline";

    DataRate f1LinkDataRate = DataRate("10Gbps");
    Time f1LinkDelay = MicroSeconds(100);
    uint32_t f1HeartbeatIntervalMs = 100;
    uint32_t f1HeartbeatPacketSize = 64;

    // Single MODELED-chain hop delay (ms), one-way. Derived from / applied
    // identically to the EPC S1uLinkDelay attribute -- see file header.
    // Default matches the F1 link delay already used by the existing CU-DU
    // scenarios (100us) so this scenario introduces no new latency constant.
    double hopDelayMs = 0.1;

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
    cmd.AddValue("hopDelayMs",
                 "MODELED one-way delay (ms) applied per signaling hop after the real "
                 "RRC ConnectionEstablished event; also applied to the real EPC "
                 "S1uLinkDelay attribute so both share the same basis",
                 hopDelayMs);
    bool fullTraces = true;
    cmd.AddValue("fullTraces", "Enable full PHY/MAC/RLC/PDCP trace set if true", fullTraces);
    cmd.Parse(argc, argv);

    g_modeledHopDelayMs = hopDelayMs;

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
    nrEpcHelper->SetAttribute("S1uLinkDelay", TimeValue(MilliSeconds(hopDelayMs)));

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

    // ---- Standard-attach timeline measurement: record the attach-start
    // instant immediately before triggering attach, then hook
    // ConnectionEstablished (the one real ns-3 attach event) to compute the
    // rest of the MODELED chain -- see file header. ----
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

            // Record the (imsi, destAddress, destPort) join key for this UE's
            // application flow so the real FlowMonitor first-Rx-packet time
            // can be matched back to this UE's IMSI after Simulator::Run().
            uint64_t ueImsi = DynamicCast<NrUeNetDevice>(ueNetDev.Get(ueIndex))->GetImsi();
            g_ueFlowKeys.push_back({ueImsi, ueIpIface.GetAddress(ueIndex), port});

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

    // ---- MEASURED first-data-packet join: read FlowMonitor's own recorded
    // timeFirstRxPacket per flow and match it to the UE it belongs to via
    // the (destAddress, destPort) join key captured per UE above. This does
    // not touch, recompute, or substitute for the MODELED dataReadyMs chain.
    {
        Ptr<Ipv4FlowClassifier> classifier =
            DynamicCast<Ipv4FlowClassifier>(flowmonHelper.GetClassifier());
        std::map<FlowId, FlowMonitor::FlowStats> flowStats = monitor->GetFlowStats();
        for (auto& [flowId, stats] : flowStats)
        {
            if (stats.rxPackets == 0)
            {
                continue; // no packet actually received for this flow -- nothing to report
            }
            Ipv4FlowClassifier::FiveTuple tuple = classifier->FindFlow(flowId);
            for (auto& key : g_ueFlowKeys)
            {
                if (tuple.destinationAddress == key.destAddress &&
                    tuple.destinationPort == key.destPort && tuple.protocol == 17 /* UDP */)
                {
                    double firstRxMs = stats.timeFirstRxPacket.GetSeconds() * 1000.0;
                    for (auto& r : g_attachTimelines)
                    {
                        if (r.imsi == key.imsi)
                        {
                            r.firstDataPacketTimeMs = firstRxMs;
                            r.attachToFirstDataPacketLatencyMs = firstRxMs - r.attachStartMs;
                            break;
                        }
                    }
                    break;
                }
            }
        }
    }

    // ---- Standard attach timeline CSV: one row per UE that reached the
    // real RRC ConnectionEstablished event, all 18 downstream columns
    // MODELED as described in the file header. ----
    std::ofstream timelineFile(outputDir + "/" + simTag + "_attach_timeline.csv");
    timelineFile << "imsi,cellId,rnti,"
                 << "attachStartMs,rrcSetupCompleteMs,"
                 << "initialUeMessageMs,authRequestMs,authResponseMs,"
                 << "securityModeCommandNasMs,securityModeCompleteNasMs,"
                 << "initialContextSetupRequestMs,securityModeCommandAsMs,securityModeCompleteAsMs,"
                 << "ueCapabilityEnquiryMs,ueCapabilityInformationMs,initialContextSetupResponseMs,"
                 << "registrationAcceptMs,registrationCompleteMs,"
                 << "pduSessionEstablishmentRequestMs,pduSessionResourceSetupRequestMs,"
                 << "rrcReconfigurationDrbMs,rrcReconfigurationCompleteMs,"
                 << "pduSessionResourceSetupResponseMs,dataReadyMs,"
                 << "rrcSetupLatencyMs,firstDataPacketTimeMs,attachToFirstDataPacketLatencyMs,"
                 << "coreSignalingLatencyMs,totalAttachToDataLatencyMs\n";

    double sumRrcSetupLatencyMs = 0.0;
    double sumCoreSignalingLatencyMs = 0.0;
    double sumTotalLatencyMs = 0.0;
    double sumFirstDataPacketTimeMs = 0.0;
    double sumAttachToFirstDataPacketLatencyMs = 0.0;
    size_t firstDataObservedCount = 0;

    auto fmtOrNa = [](double v) {
        std::ostringstream oss;
        if (v < 0.0)
        {
            oss << "NA";
        }
        else
        {
            oss << v;
        }
        return oss.str();
    };

    for (auto& r : g_attachTimelines)
    {
        double rrcSetupLatencyMs = r.rrcSetupCompleteMs - r.attachStartMs;
        double coreSignalingLatencyMs = r.dataReadyMs - r.rrcSetupCompleteMs;
        double totalLatencyMs = r.dataReadyMs - r.attachStartMs;
        sumRrcSetupLatencyMs += rrcSetupLatencyMs;
        sumCoreSignalingLatencyMs += coreSignalingLatencyMs;
        sumTotalLatencyMs += totalLatencyMs;

        if (r.firstDataPacketTimeMs >= 0.0)
        {
            sumFirstDataPacketTimeMs += r.firstDataPacketTimeMs;
            sumAttachToFirstDataPacketLatencyMs += r.attachToFirstDataPacketLatencyMs;
            firstDataObservedCount++;
        }

        timelineFile << r.imsi << "," << r.cellId << "," << r.rnti << "," << r.attachStartMs << ","
                     << r.rrcSetupCompleteMs << "," << r.initialUeMessageMs << ","
                     << r.authRequestMs << "," << r.authResponseMs << ","
                     << r.securityModeCommandNasMs << "," << r.securityModeCompleteNasMs << ","
                     << r.initialContextSetupRequestMs << "," << r.securityModeCommandAsMs << ","
                     << r.securityModeCompleteAsMs << "," << r.ueCapabilityEnquiryMs << ","
                     << r.ueCapabilityInformationMs << "," << r.initialContextSetupResponseMs
                     << "," << r.registrationAcceptMs << "," << r.registrationCompleteMs << ","
                     << r.pduSessionEstablishmentRequestMs << ","
                     << r.pduSessionResourceSetupRequestMs << "," << r.rrcReconfigurationDrbMs
                     << "," << r.rrcReconfigurationCompleteMs << ","
                     << r.pduSessionResourceSetupResponseMs << "," << r.dataReadyMs << ","
                     << rrcSetupLatencyMs << "," << fmtOrNa(r.firstDataPacketTimeMs) << ","
                     << fmtOrNa(r.attachToFirstDataPacketLatencyMs) << ","
                     << coreSignalingLatencyMs << "," << totalLatencyMs << "\n";
    }
    timelineFile.close();

    size_t n = g_attachTimelines.size();
    double meanRrcSetupLatencyMs = n ? sumRrcSetupLatencyMs / n : 0.0;
    double meanCoreSignalingLatencyMs = n ? sumCoreSignalingLatencyMs / n : 0.0;
    double meanTotalLatencyMs = n ? sumTotalLatencyMs / n : 0.0;
    double meanFirstDataPacketTimeMs =
        firstDataObservedCount ? sumFirstDataPacketTimeMs / firstDataObservedCount : -1.0;
    double meanAttachToFirstDataPacketLatencyMs =
        firstDataObservedCount ? sumAttachToFirstDataPacketLatencyMs / firstDataObservedCount
                               : -1.0;

    std::ofstream summary(outputDir + "/" + simTag + "_run_summary.tsv");
    summary << "metric\tvalue\n";
    summary << "configuredUeCount\t" << ueNum << "\n";
    summary << "rrcConnectedCount\t" << n << "\n";
    summary << "modeledHopDelayMs\t" << g_modeledHopDelayMs << "\n";
    summary << "meanRrcSetupLatencyMs\t" << meanRrcSetupLatencyMs << "\n";
    summary << "firstDataPacketObservedCountMEASURED\t" << firstDataObservedCount << "\n";
    summary << "meanFirstDataPacketTimeMsMEASURED\t" << fmtOrNa(meanFirstDataPacketTimeMs) << "\n";
    summary << "meanAttachToFirstDataPacketLatencyMsMEASURED\t"
           << fmtOrNa(meanAttachToFirstDataPacketLatencyMs) << "\n";
    summary << "meanCoreSignalingLatencyMsMODELED\t" << meanCoreSignalingLatencyMs << "\n";
    summary << "meanTotalAttachToDataLatencyMsMODELED\t" << meanTotalLatencyMs << "\n";
    summary << "simulatedSeconds\t" << simTime.GetSeconds() << "\n";
    summary << "wallClockSeconds\t" << wallClockSeconds << "\n";
    summary << "rngSeed\t" << rngSeed << "\n";
    summary << "rngRun\t" << rngRun << "\n";
    summary.close();

    NS_LOG_UNCOND("RRC connected (MEASURED): " << n << " / " << ueNum);
    NS_LOG_UNCOND("Mean RRC setup latency (MEASURED, ms): " << meanRrcSetupLatencyMs);
    NS_LOG_UNCOND("First data packet observed for (MEASURED, count): " << firstDataObservedCount
                                                                      << " / " << n);
    NS_LOG_UNCOND("Mean first-data-packet time (MEASURED, ms): " << fmtOrNa(meanFirstDataPacketTimeMs));
    NS_LOG_UNCOND("Mean attach-to-first-data-packet latency (MEASURED, ms): "
                 << fmtOrNa(meanAttachToFirstDataPacketLatencyMs));
    NS_LOG_UNCOND("Mean core-signaling latency (MODELED, ms): " << meanCoreSignalingLatencyMs);
    NS_LOG_UNCOND("Mean total attach-to-data latency (MODELED, ms): " << meanTotalLatencyMs);
    NS_LOG_UNCOND("Wall clock seconds: " << wallClockSeconds);

    Simulator::Destroy();
    return 0;
}
