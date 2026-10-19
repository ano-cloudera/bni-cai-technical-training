"""Streamlit UI of the shared Workshop Portal. All per-user data lives in PortalSessionState."""

from __future__ import annotations

import types

import streamlit as st

from bni_training.guardrails import GuardrailError
from bni_training.workshop.group_registry import GroupAccessError, UnknownGroupError
from bni_training.workshop.portal.gate import TicketState
from bni_training.workshop.portal.service import (
    CTX_KEY,
    GroupLockedError,
    PortalService,
    RetrievalUnavailable,
)

PLACEHOLDER = "Select your group..."
ICONS = types.MappingProxyType(
    {
        TicketState.QUEUED: "⏳ Queued",
        TicketState.PROCESSING: "⚙️ Processing",
        TicketState.COMPLETED: "✅ Completed",
        TicketState.FAILED: "❌ Failed",
        TicketState.CANCELLED: "🚫 Cancelled",
        TicketState.TIMED_OUT: "⌛ Timed out",
        TicketState.REJECTED: "🚦 Busy",
    }
)


@st.cache_resource(show_spinner="Starting the workshop portal...")
def get_service() -> PortalService:
    """One shared, stateless-for-users service per Streamlit process."""
    return PortalService.from_env()


GROUP_SELECT_KEY = "group-select"
RESET_CONFIRM_KEY = "reset-confirm"


def _choose_group(service: PortalService):
    options = list(service.registry.group_ids)
    current = st.session_state.get(CTX_KEY)
    locked = current is not None and service.state(st.session_state, current).locked
    if GROUP_SELECT_KEY not in st.session_state:
        initial = current.group_id if current else PLACEHOLDER
        requested = st.query_params.get("group_id")
        if current is None and requested:
            try:
                initial = service.registry.validate(requested)
            except UnknownGroupError as exc:
                st.sidebar.error(f"{exc}. Choose your group from the list.")
        st.session_state[GROUP_SELECT_KEY] = initial
    # A stable key keeps the widget's identity independent of the current group, so every change is honoured.
    choice = st.sidebar.selectbox(
        "Your group",
        [PLACEHOLDER, *options],
        key=GROUP_SELECT_KEY,
        disabled=locked,
        help="The group is locked after your first question. Use Reset session to change it.",
    )
    if locked:
        st.sidebar.caption(f"Locked to {current.group_id} for this session.")
        _reset_control(service)
        return current
    if choice == PLACEHOLDER:
        return None
    try:
        return service.join_group(st.session_state, choice)
    except GroupLockedError as exc:  # defensive: the selector is disabled when locked
        st.sidebar.warning(str(exc))
        return st.session_state.get(CTX_KEY)


def _do_reset(service: PortalService) -> None:
    """Button callback (runs before the script body, so widget state may be changed here)."""
    service.reset_session(st.session_state)
    st.session_state[GROUP_SELECT_KEY] = PLACEHOLDER
    st.session_state[RESET_CONFIRM_KEY] = False


def _reset_control(service: PortalService) -> None:
    with st.sidebar.expander("Reset session"):
        st.caption("Clears this session's chat, outputs and temporary files, then lets you choose a group.")
        confirmed = st.checkbox(
            "I understand my saved outputs for this session will be deleted", key=RESET_CONFIRM_KEY
        )
        st.button(
            "Reset session",
            disabled=not confirmed,
            key="reset-session",
            on_click=_do_reset,
            args=(service,),
        )


def _sidebar_status(service: PortalService, state) -> None:
    stats = service.gate.stats()
    st.sidebar.caption(
        f"Shared model: {stats['processing']} of {stats['max_concurrent']} running, {stats['queued']} waiting"
    )
    outputs = service.list_outputs(state.ctx)
    with st.sidebar.expander(f"My outputs ({len(outputs)})"):
        for name in outputs:
            st.download_button(name, service.read_output(state.ctx, name), file_name=name, key=f"dl::{name}")
    with st.sidebar.expander("My session telemetry"):
        st.json(state.events()[-20:])


def _status_panel(service: PortalService, state) -> None:
    ticket = state.active_ticket
    refresh = 1.0 if ticket is not None and not ticket.done else None

    @st.fragment(run_every=refresh)
    def panel() -> None:
        current = state.active_ticket
        if current is None:
            return
        if current.done:
            service.collect(state)
            st.rerun()
            return
        label = ICONS[current.state]
        if current.state is TicketState.QUEUED:
            st.info(f"{label}: position {current.position()}. {current.message}")
        else:
            st.info(f"{label}: {current.message}")
        if st.button("Cancel request", key="cancel-request"):
            service.cancel(state)
            st.rerun()

    panel()


def render() -> None:
    st.set_page_config(page_title="Workshop Portal", layout="wide")
    st.title("Synthetic Banking Portfolio Assistant")
    st.caption(
        "Fully synthetic workshop data. No lending decisions. Group separation is operational, "
        "not a security boundary."
    )
    try:
        service = get_service()
    except Exception as exc:  # noqa: BLE001 - show a safe message, never environment values
        st.error(f"The portal is not configured: {type(exc).__name__}. Tell the trainer.")
        return
    if service.mode == "local":
        st.warning("LOCAL MODE: answers come from a mock model. Use PORTAL_MODE=cai on CAI.")
    ctx = _choose_group(service)
    if ctx is None:
        st.info("Choose your group in the sidebar to begin.")
        return
    state = service.state(st.session_state, ctx)
    service.collect(state)

    group = service.registry.group(ctx.group_id)
    scenario = service.scenario_for(state)
    st.subheader(f"{ctx.group_id}: {scenario.title}")
    st.write(scenario.description)
    left, right = st.columns(2)
    try:
        service.select_scenario(
            state, left.selectbox("Scenario", group.scenario_ids, key=f"scenario::{ctx.group_id}")
        )
        service.select_dataset(
            state, right.selectbox("Dataset", group.dataset_ids, key=f"dataset::{ctx.group_id}")
        )
    except GroupAccessError as exc:
        st.error(str(exc))
        return

    for question in scenario.sample_questions:
        if st.button(question, key=f"sample::{question}", disabled=state.active_ticket is not None):
            _ask(service, state, question)
    for message in state.chat():
        with st.chat_message(message["role"] if message["role"] != "system" else "assistant"):
            st.write(message["content"])
            if message.get("sql"):
                st.code(message["sql"], language="sql")
    _status_panel(service, state)
    typed = st.chat_input("Ask about your mission", disabled=state.active_ticket is not None)
    if typed:
        _ask(service, state, typed)

    with st.expander("Related glossary and scenario notes (my group only)"):
        query = st.text_input("Search", key="retrieval-query")
        if query:
            try:
                for hit in service.retrieve(ctx, query, state=state):
                    st.write(f"**{hit['title']}**: {hit['text']}")
            except RetrievalUnavailable as exc:
                st.caption(f"SKIPPED: {exc}")
    _sidebar_status(service, state)


def _ask(service: PortalService, state, question: str) -> None:
    try:
        service.submit_question(state, question)
    except GuardrailError as exc:
        st.warning(str(exc))
        return
    st.rerun()
