from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from bni_training.data.bundles import GroupBundle
from bni_training.data.engine import CsvEngine
from bni_training.data.semantic_layer import SemanticModel
from bni_training.data.tool import DataRequest, WorkshopDataTool
from bni_training.guardrails import validate_input
from bni_training.llm_client import OpenAICompatibleClient
from bni_training.rag import HashingEmbedder, index_group_documents, search_group
from bni_training.workshop import group_paths
from bni_training.workshop.group_context import SessionContext, new_session_id
from bni_training.workshop.group_registry import (
    DatasetSpec,
    GroupRegistry,
    ScenarioSpec,
)

from .config import PortalConfig, PortalConfigError
from .gate import InferenceGate, Ticket, TicketState
from .instance_guard import SingleInstanceGuard
from .state import PortalSessionState
from .telemetry import NoopTracer, build_tracer, trace_attributes

MAX_ROWS_IN_ANSWER = 50
CTX_KEY = "portal::ctx"


class GroupLockedError(PermissionError):
    """The session already started working in a group; changing group needs an explicit reset."""


class RetrievalUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PortalAnswer:
    question: str
    answer: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    group_id: str = ""
    session_id: str = ""
    dataset_id: str = ""
    mission_id: str = ""
    truncated: bool = False


def bundle_for(registry: GroupRegistry, group_id: str, dataset: DatasetSpec) -> GroupBundle:
    scenario = registry.scenario(dataset.mission_id)
    return GroupBundle(
        group_id,
        dataset.dataset_id,
        dataset.mission_id,
        scenario.title,
        scenario.objective,
        dataset.tables,
        dict(dataset.row_filters),
        dataset.allowed_metrics,
        scenario.sample_questions,
        dataset.csv_dir,
    )


class PortalService:
    """Shared by all sessions: configuration, the gate, and read-only data tools. Never user state."""

    def __init__(
        self,
        registry: GroupRegistry,
        config: PortalConfig,
        gate: InferenceGate,
        *,
        llm_factory: Callable[[], Any] | None = None,
        data_tool_factory: Callable[[str, DatasetSpec], Any] | None = None,
        csv_engine: CsvEngine | None = None,
        tracer: Any = None,
        qdrant_client: Any = None,
        embed: Callable[[str], list[float]] | None = None,
        runtime_dir: Path | None = None,
        closers: tuple[Callable[[], None], ...] = (),
        instance_guard: SingleInstanceGuard | None = None,
    ):
        if config.data_backend != "csv":
            raise PortalConfigError(
                "DATA_BACKEND=impala is a trainer-controlled extension and is not enabled for the Portal; "
                "the Portal never falls back between backends. Use DATA_BACKEND=csv."
            )
        self.registry = registry
        self.config = config
        self.gate = gate
        self._llm = (llm_factory or self._default_llm)()
        self._data_tool_factory = data_tool_factory or self._default_tool
        self._engine = csv_engine
        self._owns_engine = csv_engine is None
        self._semantic = SemanticModel.load()
        self._tools: dict[tuple[str, str], Any] = {}  # (group, dataset) -> tool bound to that bundle only
        self._tools_lock = threading.Lock()
        self._tracer = tracer or NoopTracer()
        self._qdrant = qdrant_client
        self._embed = embed
        self._runtime = Path(runtime_dir) if runtime_dir else group_paths.runtime_root()
        self._guard = instance_guard
        if instance_guard is not None:
            instance_guard.acquire()
            closers = (*closers, instance_guard.release)
        self._closers = closers

    # construction ---------------------------------------------------------------------------------
    def _default_tool(self, group_id: str, dataset: DatasetSpec):
        if self._engine is None:  # one shared, read-only, in-memory copy of the physical dataset
            self._engine = CsvEngine(dataset.csv_dir)
        return WorkshopDataTool(self._engine, self._semantic, bundle_for(self.registry, group_id, dataset))

    def _default_llm(self):
        if not self.config.llm_base_url:
            raise PortalConfigError(
                "No LLM endpoint: set LITELLM_BASE_URL or VLLM_BASE_URL (cai mode never uses a mock)"
            )
        return OpenAICompatibleClient(
            self.config.llm_base_url, self.config.llm_api_key, self.config.llm_model
        )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PortalService:
        env = dict(os.environ if env is None else env)
        config = PortalConfig.from_env(env)
        registry = (
            GroupRegistry.load(Path(env["WORKSHOP_SCENARIOS_DIR"]))
            if env.get("WORKSHOP_SCENARIOS_DIR")
            else GroupRegistry.load()
        )
        gate = InferenceGate(
            config.max_concurrent_inference,
            config.max_queue_depth,
            config.queue_timeout_s,
            config.request_timeout_s,
            config.max_retries,
            config.retry_backoff_s,
        )
        if config.mode == "local":
            return cls._local(registry, config, gate, env)
        tracer = build_tracer(env["PHOENIX_ENDPOINT"]) if env.get("PHOENIX_ENDPOINT") else None
        client = embed = None
        if env.get("QDRANT_URL") and env.get("EMBEDDING_MODEL_PATH"):
            from qdrant_client import QdrantClient
            from sentence_transformers import SentenceTransformer

            client = QdrantClient(url=env["QDRANT_URL"], api_key=env.get("QDRANT_API_KEY") or None)
            model = SentenceTransformer(env["EMBEDDING_MODEL_PATH"], device="cpu")

            def embed(text: str) -> list[float]:
                return model.encode([text], normalize_embeddings=True).tolist()[0]

        return cls(
            registry,
            config,
            gate,
            tracer=tracer,
            qdrant_client=client,
            embed=embed,
            instance_guard=cls._guard_for(config, env),
        )

    @staticmethod
    def _guard_for(config: PortalConfig, env: Mapping[str, str], runtime: Path | None = None):
        if not config.enforce_single_instance:
            return None
        root = runtime or group_paths.runtime_root(env)
        return SingleInstanceGuard(Path(root) / "shared" / "state")

    @classmethod
    def _local(
        cls, registry: GroupRegistry, config: PortalConfig, gate: InferenceGate, env: Mapping[str, str]
    ):
        """Explicit local mode: in-process mock LLM and in-memory Qdrant. Never used in cai mode."""
        import dataclasses

        from qdrant_client import QdrantClient

        from bni_training.labs import GLOSSARY
        from bni_training.mock_llm import MockOpenAIServer

        mock = MockOpenAIServer(reply="Mock summary of the supplied synthetic result.").start()
        config = dataclasses.replace(config, llm_base_url=mock.base_url, llm_api_key="local-placeholder")
        client = QdrantClient(":memory:")
        embedder = HashingEmbedder()
        glossary = [json.loads(x) for x in GLOSSARY.read_text(encoding="utf-8").splitlines() if x.strip()]
        for group_id in registry.group_ids:
            scenario = registry.scenario(registry.group(group_id).scenario_ids[0])
            note = {
                "chunk_id": f"scenario-{group_id}",
                "title": scenario.title,
                "document_type": "scenario",
                "source": "synthetic-workshop",
                "text": f"{scenario.title}. {scenario.description}",
            }
            index_group_documents(client, group_id, [*glossary, note], embedder.embed_many)
        runtime = (
            Path(env["WORKSHOP_RUNTIME_DIR"])
            if env.get("WORKSHOP_RUNTIME_DIR")
            else Path(tempfile.mkdtemp(prefix="bni-portal-local-"))
        )
        return cls(
            registry,
            config,
            gate,
            qdrant_client=client,
            embed=embedder.embed,
            runtime_dir=runtime,
            closers=(mock.stop,),
            instance_guard=cls._guard_for(config, env, runtime),
        )

    def close(self) -> None:
        self.gate.close()
        if self._owns_engine and self._engine is not None:
            self._engine.close()
        for closer in self._closers:
            closer()

    @property
    def mode(self) -> str:
        return self.config.mode

    # sessions -------------------------------------------------------------------------------------
    def open_session(self, group_id: str) -> SessionContext:
        """Validate the group against the registry and mint a fresh, unguessable session id."""
        return SessionContext(self.registry.validate(group_id), new_session_id())

    def join_group(self, backing: MutableMapping[str, Any], group_id: str) -> SessionContext:
        """Select a group for this browser session. Refuses to change group once the session has started."""
        group_id = self.registry.validate(group_id)
        current = backing.get(CTX_KEY)
        if current is not None and current.group_id == group_id:
            return current
        if current is not None:
            if PortalSessionState(backing, current).locked:
                raise GroupLockedError(
                    f"This session is locked to {current.group_id}. "
                    "Use 'Reset session' to choose another group."
                )
            PortalSessionState(backing, current).clear()  # nothing but selections existed yet
        backing[CTX_KEY] = self.open_session(group_id)
        return backing[CTX_KEY]

    def reset_session(self, backing: MutableMapping[str, Any]) -> None:
        """Explicit reset: cancel any request, delete this session's state, outputs and temp files."""
        ctx = backing.get(CTX_KEY)
        if ctx is None:
            return
        state = PortalSessionState(backing, ctx)
        self.cancel(state)
        state.clear()
        for directory in (
            group_paths.session_output_dir(self._runtime, ctx.group_id, ctx.session_id),
            group_paths.session_tmp_dir(self._runtime, ctx.group_id, ctx.session_id),
        ):
            if directory.is_dir():
                shutil.rmtree(directory)
        del backing[CTX_KEY]

    def state(self, backing: MutableMapping[str, Any], ctx: SessionContext) -> PortalSessionState:
        state = PortalSessionState(backing, ctx)
        group = self.registry.group(ctx.group_id)
        if state.dataset_id is None:
            state.dataset_id = group.dataset_ids[0]
        if state.scenario_id is None:
            state.scenario_id = group.scenario_ids[0]
        return state

    def scenario_for(self, state: PortalSessionState) -> ScenarioSpec:
        return self.registry.require_scenario(state.ctx.group_id, state.scenario_id)

    def select_dataset(self, state: PortalSessionState, dataset_id: str) -> None:
        self.registry.require_dataset(state.ctx.group_id, dataset_id)
        state.dataset_id = dataset_id

    def select_scenario(self, state: PortalSessionState, scenario_id: str) -> None:
        self.registry.require_scenario(state.ctx.group_id, scenario_id)
        state.scenario_id = scenario_id

    # asking ---------------------------------------------------------------------------------------
    def _tool_for(self, group_id: str, dataset: DatasetSpec):
        with self._tools_lock:
            key = (group_id, dataset.dataset_id)
            if key not in self._tools:
                self._tools[key] = self._data_tool_factory(group_id, dataset)
            return self._tools[key]

    def submit_question(self, state: PortalSessionState, question: str) -> Ticket:
        ctx = state.ctx
        question = validate_input(question)  # a rejected question never reaches the queue
        dataset = self.registry.require_dataset(ctx.group_id, state.dataset_id)
        scenario = self.registry.require_scenario(ctx.group_id, state.scenario_id)
        tool = self._tool_for(ctx.group_id, dataset)
        mission_id = scenario.scenario_id
        request = DataRequest(ctx.group_id, ctx.session_id, dataset.dataset_id, mission_id)
        attributes = trace_attributes(ctx, dataset.dataset_id, mission_id)
        llm, tracer, max_tokens = self._llm, self._tracer, self.config.max_tokens
        system = (
            f"You support the '{scenario.title}' mission on a fully synthetic banking portfolio. "
            "Summarize only the supplied result. Do not invent numbers. Never make lending decisions."
        )

        def job(token, timeout: float) -> PortalAnswer:
            with tracer.start_as_current_span("portal.ask", attributes=attributes):
                sql, result = tool.query(question, request)
                token.raise_if_cancelled()
                reply = llm.chat(
                    [
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": (
                                f"Question: {question}\nColumns: {result.columns}\n"
                                f"Rows: {result.rows[:MAX_ROWS_IN_ANSWER]}"
                            ),
                        },
                    ],
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                return PortalAnswer(
                    question,
                    reply["choices"][0]["message"]["content"],
                    sql,
                    list(result.columns),
                    [list(r) for r in result.rows[:MAX_ROWS_IN_ANSWER]],
                    result.row_count,
                    request.group_id,
                    request.session_id,
                    request.dataset_id,
                    request.mission_id,
                    bool(getattr(result, "truncated", False)),
                )

        state.lock()  # first chat action: the group can no longer change without a reset
        state.add_message("user", question)
        ticket = self.gate.submit(job, group_id=ctx.group_id, session_id=ctx.session_id)
        state.active_ticket = ticket
        state.add_event(type="submitted", state=ticket.state.value)
        return ticket

    def cancel(self, state: PortalSessionState) -> bool:
        ticket = state.active_ticket
        return bool(ticket and ticket.cancel())

    def collect(self, state: PortalSessionState) -> dict | None:
        """If this session's request has finished, record it once in chat, outputs, and telemetry."""
        ticket = state.active_ticket
        if ticket is None or not ticket.done:
            return None
        state.active_ticket = None
        state.add_event(type="finished", state=ticket.state.value, attempts=ticket.attempts)
        if ticket.state is TicketState.COMPLETED:
            answer: PortalAnswer = ticket.result
            number = state.next_answer_number()
            name = f"answer-{number:03d}.json"
            self.write_output(state.ctx, name, json.dumps(asdict(answer), indent=2, default=str))
            state.add_message("assistant", answer.answer, sql=answer.sql, output=name)
            return {"state": ticket.state.value, "output": name}
        state.add_message("system", ticket.message, state=ticket.state.value)
        return {"state": ticket.state.value}

    # retrieval ------------------------------------------------------------------------------------
    def retrieve(
        self, ctx: SessionContext, query: str, limit: int = 3, state: PortalSessionState | None = None
    ) -> list[dict]:
        if self._qdrant is None or self._embed is None:
            raise RetrievalUnavailable("Qdrant retrieval is not configured for this portal")
        if state is not None:
            state.lock()
        return search_group(self._qdrant, ctx.group_id, query, self._embed, limit=limit)

    # outputs (group and session scoped, through the safe-path gate) -----------------------------------
    def write_output(self, ctx: SessionContext, name: str, text: str) -> Path:
        return group_paths.write_session_file(self._runtime, ctx.group_id, ctx.session_id, name, text)

    def list_outputs(self, ctx: SessionContext) -> list[str]:
        out_dir = group_paths.session_output_dir(self._runtime, ctx.group_id, ctx.session_id)
        return sorted(p.name for p in out_dir.iterdir() if p.is_file()) if out_dir.is_dir() else []

    def read_output(self, ctx: SessionContext, name: str) -> str:
        group_paths.check_filename(name)
        out_dir = group_paths.session_output_dir(self._runtime, ctx.group_id, ctx.session_id)
        return group_paths.safe_join(out_dir, name).read_text(encoding="utf-8")
