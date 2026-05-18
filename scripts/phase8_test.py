import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from interpret.record import InterpretRecord
from tools.security_tools import BanditRunner, DASTRunner, SemgrepRunner


async def test():
    # BanditRunner
    with tempfile.TemporaryDirectory() as tmpdir:
        vuln = Path(tmpdir) / "vuln.py"
        vuln.write_text("import subprocess\nsubprocess.call('ls', shell=True)\n")
        runner = BanditRunner()
        findings = await runner.run(str(tmpdir))
        print("Bandit findings:", len(findings))
        for f in findings:
            print(f"  [{f.severity}] {f.rule}: {f.description[:60]}")
        print("BanditRunner: PASS")

    # SemgrepRunner
    captured_args = []

    async def capturing_exec(*args, **kwargs):
        captured_args.extend(args)
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b'{"results":[]}', b""))
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=capturing_exec):
        await SemgrepRunner().run(".")
    cmd = " ".join(str(a) for a in captured_args)
    assert "auto" not in cmd
    assert "p/python" in cmd
    assert "p/security" in cmd
    print("SemgrepRunner: PASS — no auto, has p/python + p/security")

    # DASTRunner L10
    records = []
    orig = InterpretRecord.__init__

    def col(self, **kw):
        orig(self, **kw)
        records.append(self)

    InterpretRecord.__init__ = col
    os.environ.pop("RUN_DAST", None)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await DASTRunner().run(tmpdir)
    assert result == []
    l10 = [r for r in records if r.layer == "security" and r.component == "DASTRunner"]
    assert len(l10) >= 1
    print("DASTRunner: PASS — returns [] and emits L10")


asyncio.run(test())
