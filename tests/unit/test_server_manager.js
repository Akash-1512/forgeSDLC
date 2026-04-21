/**
 * Jest tests for electron/server_manager.js
 * Mocks child_process.spawn and fetch.
 */

const { ServerManager } = require('../../electron/server_manager');

// Mock child_process
jest.mock('child_process', () => ({
    spawn: jest.fn(),
}));
const { spawn } = require('child_process');

function makeMockProcess(exitCode = 0) {
    const proc = {
        pid: 12345,
        stdout: { on: jest.fn() },
        stderr: { on: jest.fn() },
        on: jest.fn(),
        kill: jest.fn(),
        _triggerExit: function(code) {
            const cb = this.on.mock.calls.find(c => c[0] === 'exit');
            if (cb) cb[1](code);
        },
    };
    return proc;
}

beforeEach(() => {
    jest.clearAllMocks();
    // Default: health check succeeds immediately
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
});

test('test_server_uses_python_path_env_when_set', async () => {
    const proc = makeMockProcess();
    spawn.mockReturnValue(proc);
    process.env.PYTHON_PATH = 'C:/venv/python.exe';

    const server = new ServerManager();
    const startPromise = server.start();
    // Trigger running status
    const stdoutCb = proc.stdout.on.mock.calls.find(c => c[0] === 'data');
    if (stdoutCb) stdoutCb[1](Buffer.from('Running on http://localhost:8080'));
    await startPromise;

    expect(spawn).toHaveBeenCalledWith(
        'C:/venv/python.exe',
        expect.any(Array),
        expect.any(Object)
    );
    delete process.env.PYTHON_PATH;
});

test('test_server_falls_back_to_python_when_no_python_path_env', async () => {
    const proc = makeMockProcess();
    spawn.mockReturnValue(proc);
    delete process.env.PYTHON_PATH;

    const server = new ServerManager();
    await server.start();

    expect(spawn).toHaveBeenCalledWith(
        'python',
        expect.any(Array),
        expect.any(Object)
    );
});

test('test_server_health_check_retries_every_500ms', async () => {
    const proc = makeMockProcess();
    spawn.mockReturnValue(proc);

    // Fail twice then succeed
    global.fetch = jest.fn()
        .mockRejectedValueOnce(new Error('ECONNREFUSED'))
        .mockRejectedValueOnce(new Error('ECONNREFUSED'))
        .mockResolvedValue({ ok: true });

    jest.useFakeTimers();
    const server = new ServerManager();
    const startPromise = server.start();

    // Advance time for retries
    jest.advanceTimersByTime(1500);
    await startPromise;

    expect(global.fetch).toHaveBeenCalledTimes(3);
    jest.useRealTimers();
});

test('test_server_auto_restarts_on_non_zero_exit', async () => {
    const proc = makeMockProcess();
    spawn.mockReturnValue(proc);

    const server = new ServerManager();
    await server.start();

    jest.useFakeTimers();
    const startSpy = jest.spyOn(server, 'start');

    // Simulate crash with non-zero exit
    proc._triggerExit(1);

    jest.advanceTimersByTime(2500);
    expect(startSpy).toHaveBeenCalled();
    jest.useRealTimers();
});

test('test_server_does_not_restart_on_code_null_graceful_stop', async () => {
    const proc = makeMockProcess();
    spawn.mockReturnValue(proc);

    const server = new ServerManager();
    await server.start();

    jest.useFakeTimers();
    const startSpy = jest.spyOn(server, 'start');

    server.stop();  // sets _intentionalStop = true
    proc._triggerExit(null);  // SIGTERM → code null

    jest.advanceTimersByTime(3000);
    expect(startSpy).not.toHaveBeenCalled();
    jest.useRealTimers();
});

test('test_server_status_transitions_stopped_starting_running', async () => {
    const proc = makeMockProcess();
    spawn.mockReturnValue(proc);

    const server = new ServerManager();
    expect(server.status).toBe('stopped');

    const startPromise = server.start();
    expect(server.status).toBe('starting');

    await startPromise;
    expect(server.status).toBe('running');
});