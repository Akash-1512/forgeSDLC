interface TokenEntry {
    agent: string;
    model: string;
    tokens: number;
    cost_usd: number;
}

interface TokenHistoryProps {
    entries: TokenEntry[];
    totalCostUsd: number;
}

export function TokenHistory({ entries, totalCostUsd }: TokenHistoryProps) {
    return (
        <div style={{ padding: "0.75rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    Token Usage
                </span>
                <span style={{ fontSize: 11, color: "#22c55e" }}>
                    ${totalCostUsd.toFixed(4)}
                </span>
            </div>
            {entries.map((entry, i) => (
                <div key={i} style={{
                    display: "flex", justifyContent: "space-between",
                    padding: "0.25rem 0", borderBottom: "1px solid #1e293b",
                }}>
                    <div>
                        <span style={{ fontSize: 11, color: "#e2e8f0" }}>{entry.agent}</span>
                        <span style={{ fontSize: 10, color: "#475569", marginLeft: 6 }}>{entry.model}</span>
                    </div>
                    <div style={{ textAlign: "right" }}>
                        <span style={{ fontSize: 10, color: "#94a3b8" }}>{entry.tokens.toLocaleString()}t</span>
                        <span style={{ fontSize: 10, color: "#64748b", marginLeft: 6 }}>${entry.cost_usd.toFixed(4)}</span>
                    </div>
                </div>
            ))}
        </div>
    );
}