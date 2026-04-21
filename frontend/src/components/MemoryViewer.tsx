interface MemoryEntry {
    key: string;
    value: string;
    layer: number;
}

interface MemoryViewerProps {
    entries: MemoryEntry[];
    projectId: string;
}

export function MemoryViewer({ entries, projectId }: MemoryViewerProps) {
    return (
        <div style={{ padding: "0.75rem" }}>
            <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Memory · {projectId}
            </div>
            {entries.length === 0 ? (
                <div style={{ fontSize: 12, color: "#475569" }}>No memory entries yet.</div>
            ) : (
                entries.map((entry, i) => (
                    <div key={i} style={{
                        background: "#1e293b", borderRadius: 4,
                        padding: "0.5rem", marginBottom: 4,
                    }}>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>{entry.key}</span>
                            <span style={{ fontSize: 10, color: "#475569" }}>L{entry.layer}</span>
                        </div>
                        <div style={{ fontSize: 11, color: "#e2e8f0", marginTop: 2 }}>{entry.value}</div>
                    </div>
                ))
            )}
        </div>
    );
}