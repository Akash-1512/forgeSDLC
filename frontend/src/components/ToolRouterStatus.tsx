interface ToolRouterStatusProps {
    connectedTools: string[];
    lastDelegation: string | null;
}

export function ToolRouterStatus({ connectedTools, lastDelegation }: ToolRouterStatusProps) {
    return (
        <div style={{ padding: "0.75rem" }}>
            <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Tool Router
            </div>
            <div style={{ marginBottom: 6 }}>
                {connectedTools.length === 0 ? (
                    <span style={{ fontSize: 12, color: "#475569" }}>No tools connected</span>
                ) : (
                    connectedTools.map(tool => (
                        <span key={tool} style={{
                            display: "inline-block", fontSize: 11,
                            background: "#1e293b", color: "#14b8a6",
                            borderRadius: 4, padding: "2px 6px",
                            marginRight: 4, marginBottom: 4,
                        }}>
                            {tool}
                        </span>
                    ))
                )}
            </div>
            {lastDelegation && (
                <div style={{ fontSize: 11, color: "#94a3b8" }}>
                    Last: <span style={{ color: "#e2e8f0" }}>{lastDelegation}</span>
                </div>
            )}
        </div>
    );
}