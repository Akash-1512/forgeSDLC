from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interpret.record import InterpretRecord
from tools.render_tool import RenderTool


def _capture_l8(emitted: list[str]) -> object:
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "RenderTool":
            emitted.append(str(kwargs.get("layer", "")))

    return capturing_init


@pytest.mark.asyncio
async def test_render_tool_trigger_deploy_emits_l8_interpret_record() -> None:
    emitted: list[str] = []
    mock_response = MagicMock()
    mock_response.text = "deploy triggered"
    mock_response.raise_for_status = MagicMock()

    with (
        patch.object(InterpretRecord, "__init__", _capture_l8(emitted)),
        patch.dict(os.environ, {"RENDER_DEPLOY_HOOK_URL": "https://hook.render.com/test"}),
        patch("httpx.AsyncClient") as mock_client,
    ):
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(post=AsyncMock(return_value=mock_response))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        tool = RenderTool()
        await tool.trigger_deploy()

    assert "tool" in emitted


@pytest.mark.asyncio
async def test_render_tool_wait_for_health_emits_l8_interpret_record() -> None:
    emitted: list[str] = []

    with patch.object(InterpretRecord, "__init__", _capture_l8(emitted)):
        tool = RenderTool()
        # url=None returns immediately — L8 still fires
        result = await tool.wait_for_health(None)

    assert "tool" in emitted
    assert result is True


@pytest.mark.asyncio
async def test_render_tool_wait_for_health_returns_true_on_200() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_response))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        tool = RenderTool()
        result = await tool.wait_for_health("https://myapp.onrender.com", timeout_seconds=5)

    assert result is True


@pytest.mark.asyncio
async def test_render_tool_wait_for_health_returns_false_on_timeout() -> None:
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(
                get=AsyncMock(side_effect=Exception("connection refused"))
            )
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("asyncio.sleep", AsyncMock()):
            tool = RenderTool()
            result = await tool.wait_for_health(
                "https://myapp.onrender.com", timeout_seconds=0
            )

    assert result is False


@pytest.mark.asyncio
async def test_render_tool_wait_for_health_returns_true_when_url_is_none() -> None:
    """Local Docker case — no public URL, return True immediately."""
    tool = RenderTool()
    result = await tool.wait_for_health(None)
    assert result is True