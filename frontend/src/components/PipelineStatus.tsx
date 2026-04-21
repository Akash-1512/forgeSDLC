interface Stage {
    name: string;
    status: "pending" | "running" | "complete" | "error" | "skipped";
}

interface PipelineStatusProps {
    stages: Stage[];
    currentStage: string;
}

const STATUS_COLORS: Record<string, string> = {
    pending:  "#475569",
    running:  "#14b8a6",
    complete: "#22c55e",
    error:    "#ef4444",
    skipped:  "#64748b",
};

const STATUS_ICONS: Record<string, string> = {
    pending:  "○",
    running:  "◉",
    complete: "✓",
    error:    "✗",
    skipped:  "—",
};

export function PipelineStatus({ stages, currentStage }: PipelineStatusProps) {
    return (
        <div style={{ padding: "0.75rem" }}>
            <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Pipeline
            </div>
            {stages.map((stage) => (
                <div key={stage.name} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "0.3rem 0",
                    opacity: stage.status === "skipped" ? 0.5 : 1,
                }}>
                    <span style={{ color: STATUS_COLORS[stage.status], fontSize: 14, width: 16 }}>
                        {STATUS_ICONS[stage.status]}
                    </span>
                    <span style={{
                        fontSize: 12,
                        color: stage.name === currentStage ? "#e2e8f0" : "#94a3b8",
                        fontWeight: stage.name === currentStage ? 600 : 400,
                    }}>
                        {stage.name}
                    </span>
                </div>
            ))}
        </div>
    );
}