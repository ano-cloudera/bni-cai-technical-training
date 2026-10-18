from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from apps.streamlit.service import CreditInsightService
from bni_training.backends.factory import create_backend
from bni_training.config import Settings
from bni_training.crew import CreditInsightWorkflow
from bni_training.llm_client import OpenAICompatibleClient
from bni_training.semantic import SemanticCatalog
from bni_training.tools.data_tool import DataQueryTool


@st.cache_resource
def build_service():
    settings = Settings.load()
    catalog = SemanticCatalog.load(Path(os.getenv("SEMANTIC_MODEL", "semantic/credit_portfolio.yaml")))
    workflow = CreditInsightWorkflow(
        DataQueryTool(create_backend(settings), catalog),
        OpenAICompatibleClient(settings.vllm_base_url, settings.vllm_api_key),
    )
    return CreditInsightService(settings.group_id, workflow)


st.set_page_config(page_title="Credit Portfolio Insight", layout="wide")
st.title("Synthetic Credit Portfolio Insight Assistant")
st.caption("Workshop data only. This application does not make lending decisions.")
question = st.text_input("Ask a portfolio question", "What is the outstanding balance by region?")
if st.button("Run analysis"):
    try:
        answer = build_service().ask(question)
        st.subheader("Answer")
        st.write(answer.answer)
        st.code(answer.query, language="sql")
        st.dataframe(
            [dict(zip(answer.data.columns, row, strict=True)) for row in answer.data.rows],
            use_container_width=True,
        )
    except Exception as exc:
        st.error(str(exc))
