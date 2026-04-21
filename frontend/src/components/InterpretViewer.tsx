interface InterpretRecord {
    layer: string;
    component: string;
    action: string;
    model_selected: string | null;
    timestamp: string;
    reversible: boolean;
}

interface InterpretViewerProps {
    record: InterpretRecord | null;
}

export function InterpretViewer({ record }: InterpretViewerProps) {
    if (!record) {
        return (
            <div style={{ padding: "0.75rem", color: "#475569", fontSize: 12 }}>
                No interpretation yet.
            </div>
        );
    }

    return (
        <div style={{ padding: "0.75rem" }}>
            <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Current Interpretation
            </div>
            <div style={{ background: "#1e293b", borderRadius: 6, padding: "0.75rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 11, color: "#14b8a6", fontWeight: 600 }}>
                        {record.component}
                    </span>
                    <span style={{ fontSize: 10, color: "#475569" }}>
                        L{layerNumber(record.layer)} · {record.layer}
                    </span>
                </div>
                <pre style={{
                    whiteSpace: "pre-wrap", fontSize: 11,
                    color: "#e2e8f0", margin: 0, lineHeight: 1.5,
                }}>
                    {record.action}
                </pre>
                {record.model_selected && (
                    <div style={{ marginTop: 6, fontSize: 10, color: "#64748b" }}>
                        Model: {record.model_selected}
                        {!record.reversible && (
                            <span style={{ color: "#ef4444", marginLeft: 8 }}>⚠️ irreversible</span>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

function layerNumber(layer: string): number {
    const map: Record<string, number> = {
        agent: 1, workspace: 2, diff: 3, model_router: 4, tool_router: 5,
        memory: 6, docs_fetcher: 7, tool: 8, provider: 9, security: 10,
        context_window_manager: 11, mcp_server: 12, context_file_manager: 13,
    };
    return map[layer] ?? 0;
}