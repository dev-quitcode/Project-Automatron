"""Integration checks for SQLite checkpoints."""

from __future__ import annotations

from typing_extensions import TypedDict

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from orchestrator.graph.graph import compile_graph


class _CounterState(TypedDict, total=False):
    count: int


@pytest.mark.asyncio
async def test_compile_graph_succeeds_with_temp_sqlite_checkpointer(tmp_path):
    checkpoint_db = tmp_path / "checkpoints.db"
    checkpointer_cm = AsyncSqliteSaver.from_conn_string(str(checkpoint_db))
    checkpointer = await checkpointer_cm.__aenter__()
    try:
        graph = await compile_graph(checkpointer=checkpointer)
        assert graph is not None
    finally:
        await checkpointer_cm.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_sqlite_checkpoint_history_supports_resume(tmp_path):
    async def gate_node(state: _CounterState):
        approved = interrupt({"type": "approval"})
        return {"count": state.get("count", 0) + (1 if approved else 0)}

    builder = StateGraph(_CounterState)
    builder.add_node("gate", gate_node)
    builder.add_edge(START, "gate")
    builder.add_edge("gate", END)

    checkpoint_db = tmp_path / "resume.db"
    checkpointer_cm = AsyncSqliteSaver.from_conn_string(str(checkpoint_db))
    checkpointer = await checkpointer_cm.__aenter__()
    try:
        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "checkpoint-test"}}

        first_result = await graph.ainvoke({"count": 1}, config)
        assert "__interrupt__" in first_result

        history = []
        async for checkpoint in graph.aget_state_history(config):
            history.append(checkpoint)
        assert history

        await graph.ainvoke(Command(resume=True), config)
        snapshot = await graph.aget_state(config)
        assert snapshot.values["count"] == 2
    finally:
        await checkpointer_cm.__aexit__(None, None, None)
