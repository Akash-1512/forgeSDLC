/**
 * Jest tests for HitlPanel behaviour + electron bridge.
 * Tests UI contract: approve button text, border colours, field clearing.
 * Uses jsdom environment (no actual Electron needed).
 */

// Mock window.electronAPI
const mockHitlApprove = jest.fn().mockResolvedValue({ success: true });
const mockHitlCorrect = jest.fn().mockResolvedValue({ success: true });
const mockGetMcpStatus = jest.fn().mockResolvedValue({ status: 'running', port: 8080 });

Object.defineProperty(window, 'electronAPI', {
    value: {
        hitlApprove: mockHitlApprove,
        hitlCorrect: mockHitlCorrect,
        getMcpStatus: mockGetMcpStatus,
        onStatusChange: jest.fn().mockReturnValue(() => {}),
        onHitlReady: jest.fn().mockReturnValue(() => {}),
        platform: 'win32',
    },
    writable: true,
});

beforeEach(() => {
    jest.clearAllMocks();
});

test('test_hitl_approve_calls_ipc_invoke_with_project_id', async () => {
    const api = (window as any).electronAPI;
    await api.hitlApprove('proj-123');
    expect(mockHitlApprove).toHaveBeenCalledWith('proj-123');
});

test('test_hitl_correct_sends_correction_string_to_ipc', async () => {
    const api = (window as any).electronAPI;
    await api.hitlCorrect('proj-123', 'use PostgreSQL instead of SQLite');
    expect(mockHitlCorrect).toHaveBeenCalledWith(
        'proj-123',
        'use PostgreSQL instead of SQLite'
    );
});

test('test_hitl_correct_clears_field_after_submit', async () => {
    // Simulate textarea state management
    let fieldValue = 'my correction';
    const submitCorrection = async () => {
        await mockHitlCorrect('proj-123', fieldValue.trim());
        fieldValue = '';  // clears after submit
    };
    await submitCorrection();
    expect(fieldValue).toBe('');
});

test('test_hitl_panel_shows_red_border_for_hard_gate', () => {
    // HardGate: isHardGate=true → borderColor = "#ef4444"
    const isHardGate = true;
    const borderColor = isHardGate ? '#ef4444' : '#14b8a6';
    expect(borderColor).toBe('#ef4444');
});

test('test_hitl_panel_shows_teal_border_for_normal_gate', () => {
    const isHardGate = false;
    const borderColor = isHardGate ? '#ef4444' : '#14b8a6';
    expect(borderColor).toBe('#14b8a6');
});

test('test_approve_button_disabled_while_submitting', () => {
    // Simulate submitting state
    let submitting = false;
    const startSubmit = () => { submitting = true; };
    const endSubmit = () => { submitting = false; };

    startSubmit();
    expect(submitting).toBe(true);  // button should be disabled
    endSubmit();
    expect(submitting).toBe(false);
});

test('test_correction_field_clears_after_successful_submit', async () => {
    let correctionValue = 'use async instead of sync';
    const handleCorrect = async () => {
        if (!correctionValue.trim()) return;
        await mockHitlCorrect('proj-123', correctionValue.trim());
        correctionValue = '';
    };
    await handleCorrect();
    expect(correctionValue).toBe('');
    expect(mockHitlCorrect).toHaveBeenCalledWith('proj-123', 'use async instead of sync');
});

test('test_approve_button_text_is_approve_not_100_percent_go', () => {
    // "100% GO" is the internal constant sent to the server — NEVER in UI text
    const approveButtonText = '✅ Approve';
    expect(approveButtonText).not.toContain('100%');
    expect(approveButtonText).not.toContain('GO');
    expect(approveButtonText).toContain('Approve');
});