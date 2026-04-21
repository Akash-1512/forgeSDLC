import { useState } from "react";

interface HitlPanelProps {
    interpretation: string;
    stage: string;
    projectId: string;
    isHardGate: boolean;    // true for Agents 3+8 — red left border
    onApprove: () => void;
    onCorrect: (correction: string) => void;
}

export function HitlPanel({
    interpretation, stage, projectId, isHardGate, onApprove, onCorrect
}: HitlPanelProps) {
    const [correction, setCorrection] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const handleApprove = async () => {
        setSubmitting(true);
        // Sends "100% GO" internally — NEVER shown in UI text
        await (window as any).electronAPI.hitlApprove(projectId);
        onApprove();
        setSubmitting(false);
    };

    const handleCorrect = async () => {
        if (!correction.trim()) return;
        setSubmitting(true);
        // Correction OVERWRITES state["human_corrections"][-1] on server
        // displayed_interpretation replaced — user always sees ONE current interpretation
        await (window as any).electronAPI.hitlCorrect(projectId, correction.trim());
        setCorrection("");   // clear field after submit
        onCorrect(correction.trim());
        setSubmitting(false);
    };

    const borderColor = isHardGate ? "#ef4444" : "#14b8a6";

    return (
        <div style={{
            borderLeft: `4px solid ${borderColor}`,
            padding: "1rem",
            marginBottom: "1rem",
            borderRadius: "0 6px 6px 0",
            background: "#0f172a",
        }}>
            {isHardGate && (
                <div style={{
                    fontSize: 11, color: "#ef4444",
                    marginBottom: 4, fontWeight: 600,
                    letterSpacing: "0.05em",
                }}>
                    ⚠️ ARCHITECTURAL COMMITMENT
                </div>
            )}
            <div style={{
                fontSize: 11, color: "#94a3b8",
                marginBottom: 8, textTransform: "uppercase",
                letterSpacing: "0.08em",
            }}>
                {stage}
            </div>

            {/* Single current interpretation — NEVER a stack */}
            <pre style={{
                whiteSpace: "pre-wrap",
                fontSize: 12,
                background: "#1e293b",
                padding: "0.75rem",
                borderRadius: 6,
                marginBottom: "1rem",
                maxHeight: 300,
                overflow: "auto",
                color: "#e2e8f0",
                fontFamily: "monospace",
                lineHeight: 1.5,
            }}>
                {interpretation || "Waiting for interpretation..."}
            </pre>

            {/* [✅ Approve] button — sends "100% GO" internally, NOT in label */}
            <button
                onClick={handleApprove}
                disabled={submitting}
                data-testid="approve-button"
                style={{
                    width: "100%",
                    padding: "0.6rem",
                    background: submitting ? "#475569" : "#14b8a6",
                    color: "#000",
                    border: "none",
                    borderRadius: 6,
                    cursor: submitting ? "not-allowed" : "pointer",
                    fontWeight: 600,
                    marginBottom: "0.75rem",
                    fontSize: 14,
                    transition: "background 0.2s",
                }}
            >
                {submitting ? "Processing..." : "✅ Approve"}
            </button>

            {/* Correction textarea — overwrites last correction on submit */}
            <textarea
                value={correction}
                onChange={e => setCorrection(e.target.value)}
                placeholder="Describe what to change... (overwrites previous correction)"
                rows={3}
                data-testid="correction-input"
                style={{
                    width: "100%",
                    boxSizing: "border-box",
                    background: "#1e293b",
                    color: "#e2e8f0",
                    border: "1px solid #334155",
                    borderRadius: 6,
                    padding: "0.5rem",
                    fontSize: 12,
                    resize: "vertical",
                    marginBottom: "0.5rem",
                    fontFamily: "inherit",
                }}
            />
            <button
                onClick={handleCorrect}
                disabled={submitting || !correction.trim()}
                data-testid="submit-correction-button"
                style={{
                    width: "100%",
                    padding: "0.5rem",
                    background: "transparent",
                    color: correction.trim() ? "#14b8a6" : "#475569",
                    border: `1px solid ${correction.trim() ? "#14b8a6" : "#475569"}`,
                    borderRadius: 6,
                    cursor: (submitting || !correction.trim()) ? "not-allowed" : "pointer",
                    fontSize: 12,
                    transition: "all 0.2s",
                }}
            >
                Submit Correction
            </button>
        </div>
    );
}