from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone

import structlog

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord

logger = structlog.get_logger()

_MODEL = "gpt-5.4-mini"


class PlatformAgent(BaseAgent):
    """Agent 13 — OTel trace propagation + Docker Compose deployment sequence.

    Model: gpt-5.4-mini → groq
    Fires ONLY when architecture_type == "multi_service".
    Silent skip on monolith — no interpret_log entries.
    _topological_sort(): Kahn's algorithm (BFS + in-degree). Zero LLM.
    Docker Compose respects depends_on order from topological sort.
    """

    _skip_key = "agent_13_platform"

    async def run(self, state: dict[str, object]) -> dict[str, object]:
        """Override: silent skip on monolith."""
        arch_type = str(
            (state.get("service_graph") or {}).get("architecture_type", "monolith")
        )
        if arch_type != "multi_service":
            state[f"{self._skip_key}_skipped"] = True
            logger.info("agent_13.skipped", reason="monolith architecture")
            return state
        return await super().run(state)

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        services = list((state.get("service_graph") or {}).get("services", []) or [])
        service_names = [str(s.get("name", "")) for s in services if isinstance(s, dict)]
        deploy_order = self._topological_sort(services)

        return self._emit_l1_record(
            component="PlatformAgent",
            action=(
                f"PLATFORM CONFIGURATION\n"
                f"Services: {service_names}\n"
                f"Deploy order: {deploy_order}\n"
                f"OTel: trace propagation config (W3C TraceContext)\n"
                f"Docker Compose: respects depends_on order\n"
                f"Model: {_MODEL}"
            ),
            inputs={"service_count": len(services)},
            expected_outputs={
                "docker_compose": "docker-compose.yml",
                "otel_config": "otel_config.py",
            },
            external_calls=[_MODEL],
            model_selected=_MODEL,
            files_write=["docker-compose.yml", "otel_config.py"],
        )

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Generate Docker Compose + OTel config via DiffEngine."""
        services = list((state.get("service_graph") or {}).get("services", []) or [])

        # Build deployment order from depends_on graph (Kahn's — zero LLM)
        deploy_order = self._topological_sort(services)

        # Generate docker-compose.yml respecting deployment order
        compose = self._generate_compose(services, deploy_order)
        diff_compose = await self.diff_engine.generate_diff(
            "docker-compose.yml",
            compose,
            "Agent 13: multi-service Docker Compose",
        )
        await self.diff_engine.apply_diff(diff_compose)

        # Generate OTel trace propagation config
        otel_config = self._generate_otel_config(services)
        diff_otel = await self.diff_engine.generate_diff(
            "otel_config.py",
            otel_config,
            "Agent 13: OTel trace propagation",
        )
        await self.diff_engine.apply_diff(diff_otel)

        logger.info(
            "agent_13.executed",
            services=len(services),
            deploy_order=deploy_order,
        )
        return state

    def _topological_sort(self, services: list[object]) -> list[str]:
        """Kahn's algorithm: BFS with in-degree tracking. Zero LLM.

        Guarantees: if service B depends on service A, A appears before B.
        Safe on cycles (returns partial ordering).
        """
        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {}

        for svc in services:
            if not isinstance(svc, dict):
                continue
            name = str(svc.get("name", ""))
            if name not in in_degree:
                in_degree[name] = 0
            for dep in list(svc.get("depends_on", []) or []):
                dep_str = str(dep)
                graph[dep_str].append(name)
                in_degree[name] = in_degree.get(name, 0) + 1
                if dep_str not in in_degree:
                    in_degree[dep_str] = 0

        queue: deque[str] = deque(
            name for name, deg in in_degree.items() if deg == 0
        )
        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Append any remaining nodes (cycle protection)
        remaining = [n for n in in_degree if n not in order]
        order.extend(sorted(remaining))

        return order

    def _generate_compose(
        self, services: list[object], order: list[str]
    ) -> str:
        """Generate Docker Compose YAML respecting topological deployment order."""
        lines = [
            "version: '3.9'",
            "networks:",
            "  forgesdlc_net:",
            "    driver: bridge",
            "services:",
        ]
        for name in order:
            svc = next(
                (s for s in services if isinstance(s, dict) and s.get("name") == name),
                {},
            )
            deps = list(svc.get("depends_on", []) or [])
            lines.append(f"  {name}:")
            lines.append(f"    build: ./{name}")
            lines.append(f"    networks:")
            lines.append(f"      - forgesdlc_net")
            lines.append(f"    ports:")
            lines.append(f"      - '8000'")
            lines.append(
                f"    environment:"
                f"\n      - OTEL_SERVICE_NAME={name}"
                f"\n      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317"
            )
            if deps:
                lines.append(f"    depends_on:")
                for dep in deps:
                    lines.append(f"      {dep}:")
                    lines.append(f"        condition: service_healthy")

        # Add OTel collector sidecar
        lines.extend([
            "  otel-collector:",
            "    image: otel/opentelemetry-collector-contrib:latest",
            "    networks:",
            "      - forgesdlc_net",
            "    ports:",
            "      - '4317:4317'",
            "      - '55679:55679'",
        ])

        return "\n".join(lines) + "\n"

    def _generate_otel_config(self, services: list[object]) -> str:
        """Generate OTel trace propagation config with W3C TraceContext."""
        service_names = [
            str(s.get("name", ""))
            for s in services
            if isinstance(s, dict)
        ]
        return f"""\
\"\"\"
OTel trace propagation configuration — generated by forgeSDLC Agent 13.
Services: {service_names}
\"\"\"
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.sdk.resources import Resource


def configure_otel(service_name: str) -> TracerProvider:
    \"\"\"Configure OTel with W3C TraceContext propagation.\"\"\"
    resource = Resource.create({{
        "service.name": service_name,
        "service.version": "0.1.0",
        "deployment.environment": "production",
    }})

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317", insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # W3C TraceContext propagation for cross-service trace linking
    set_global_textmap(B3MultiFormat())

    return provider
"""