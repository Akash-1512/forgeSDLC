from __future__ import annotations

from enum import Enum

import structlog

from orchestrator.constants import (
    BUDGET_ALERT_THRESHOLD,
    BUDGET_OPTIMISE_THRESHOLD,
    BUDGET_WARN_THRESHOLD,
)

logger = structlog.get_logger()


class BudgetStatus(str, Enum):
    OK       = "ok"        # < 50% — all clear
    WARN     = "warn"      # ≥ 50% — yellow in status bar
    OPTIMISE = "optimise"  # ≥ 80% — orange + ModelRouter auto-downgrade trigger
    ALERT    = "alert"     # ≥ 90% — red + confirm before calls > $0.01


class BudgetMonitor:
    """Watches cumulative cost against three thresholds from constants.py.

    WARN     (50%): informational — yellow status bar indicator
    OPTIMISE (80%): triggers ModelRouter auto-downgrade to cheaper models
    ALERT    (90%): requires explicit developer confirmation before expensive calls

    All thresholds imported from constants.py — zero magic numbers here.
    """

    async def check(
        self, budget_used: float, budget_total: float
    ) -> BudgetStatus:
        """Return the current budget status based on spend ratio."""
        if budget_total <= 0:
            # Free tier or unset — no spend tracking needed
            return BudgetStatus.OK

        ratio = budget_used / budget_total

        if ratio >= BUDGET_ALERT_THRESHOLD:
            logger.warning(
                "budget_monitor.alert",
                ratio=round(ratio, 3),
                budget_used=budget_used,
                budget_total=budget_total,
            )
            return BudgetStatus.ALERT

        if ratio >= BUDGET_OPTIMISE_THRESHOLD:
            logger.warning(
                "budget_monitor.optimise",
                ratio=round(ratio, 3),
                hint="ModelRouter will auto-downgrade to cheaper models",
            )
            return BudgetStatus.OPTIMISE

        if ratio >= BUDGET_WARN_THRESHOLD:
            logger.info(
                "budget_monitor.warn",
                ratio=round(ratio, 3),
            )
            return BudgetStatus.WARN

        return BudgetStatus.OK

    async def should_auto_downgrade(
        self, budget_used: float, budget_total: float
    ) -> bool:
        """True when ModelRouter should substitute expensive models automatically."""
        status = await self.check(budget_used, budget_total)
        return status in (BudgetStatus.OPTIMISE, BudgetStatus.ALERT)

    async def requires_confirmation(
        self,
        budget_used: float,
        budget_total: float,
        estimated_call_cost_usd: float,
        confirmation_threshold_usd: float = 0.01,
    ) -> bool:
        """True when ALERT state and call cost exceeds the confirmation threshold."""
        status = await self.check(budget_used, budget_total)
        return status == BudgetStatus.ALERT and (
            estimated_call_cost_usd >= confirmation_threshold_usd
        )