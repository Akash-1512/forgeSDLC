import { useState, useEffect } from "react";
import { HitlPanel } from "./components/HitlPanel";
import { PipelineStatus } from "./components/PipelineStatus";
import { InterpretViewer } from "./components/InterpretViewer";
import { MemoryViewer } from "./components/MemoryViewer";
import { ToolRouterStatus } from "./components/ToolRouterStatus";
import { TokenHistory } from "./components/TokenHistory";
import { getElectronAPISafe } from "./electron_bridge";

const DEMO_STAGES = [
    { name: "gather_requirements", status: "complete" as const },
    { name: "design_architecture", status: "complete" as const },
    { name: "route_code_generation", status: "running" as const },
    { name: "run_security_scan", status: "pending" as const },
    { name: "generate_cicd", status: "pending" as const },
    { name: "deploy_project", status: "pending" as const },
    { name: "setup_monitoring", status: "pending" as const },
    { name: "generate_docs", status: "pending" as const },
];

export default function App() {
    const [mcpStatus, setMcpStatus] = useState<string>("checking...");
    const [projectId] = useState("demo-project");

    const api = getElectronAPISafe();

    useEffect(() => {
        if (!api) {
            setMcpStatus("browser mode");
            return;
        }
        api.getMcpStatus().then(s => setMcpStatus(s.status));
        const unsub = api.onStatusChange(data => setMcpStatus(data.status));
        return unsub;
    }, []);

    return (
        <div style={{
            background: "#0d1117", color: "#e2e8f0",
            minHeight: "100vh", fontFamily: "system-ui, sans-serif",
            display: "flex", flexDirection: "column",
        }}>
            {/* Header */}
            <div style={{
                padding: "0.75rem 1rem",
                borderBottom: "1px solid #1e293b",
                display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
                <span style={{ fontWeight: 700, fontSize: 14, color: "#14b8a6" }}>
                    ⚡ forgeSDLC
                </span>
                <span style={{
                    fontSize: 10, padding: "2px 8px",
                    background: mcpStatus === "running" ? "#14b8a6" : "#ef4444",
                    color: "#000", borderRadius: 4, fontWeight: 600,
                }}>
                    {mcpStatus}
                </span>
            </div>

            {/* 4-zone layout */}
            <div style={{ flex: 1, overflowY: "auto" }}>
                {/* Zone 1: HITL Panel */}
                <div style={{ borderBottom: "1px solid #1e293b" }}>
                    <HitlPanel
                        interpretation="Waiting for agent interpretation..."
                        stage="route_code_generation"
                        projectId={projectId}
                        isHardGate={false}
                        onApprove={() => console.log("approved")}
                        onCorrect={(c) => console.log("correction:", c)}
                    />
                </div>

                {/* Zone 2: Pipeline Status */}
                <div style={{ borderBottom: "1px solid #1e293b" }}>
                    <PipelineStatus
                        stages={DEMO_STAGES}
                        currentStage="route_code_generation"
                    />
                </div>

                {/* Zone 3: Current Interpretation */}
                <div style={{ borderBottom: "1px solid #1e293b" }}>
                    <InterpretViewer record={null} />
                </div>

                {/* Zone 4: Memory + Tools + Tokens */}
                <MemoryViewer entries={[]} projectId={projectId} />
                <div style={{ borderTop: "1px solid #1e293b" }}>
                    <ToolRouterStatus connectedTools={["cursor", "claude_code"]} lastDelegation={null} />
                </div>
                <div style={{ borderTop: "1px solid #1e293b" }}>
                    <TokenHistory entries={[]} totalCostUsd={0} />
                </div>
            </div>
        </div>
    );
}