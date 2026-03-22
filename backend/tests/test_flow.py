"""Tests for the Flow state machine engine."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from flow44.ai.core.flow import DuplicateStepError, Flow, MaxStepsExceededError, UnknownStepError


class CounterState(BaseModel):
    value: int = 0
    steps_run: list[str] = []


class TestFlowBasic:
    @pytest.mark.asyncio
    async def test_single_step(self) -> None:
        async def increment(state: CounterState) -> CounterState:
            state.value += 1
            state.steps_run.append("increment")
            return state

        flow: Flow[CounterState] = Flow(name="test")
        flow.add_step("start", increment)

        result = await flow.run(CounterState(), start="start")
        assert result.value == 1
        assert result.steps_run == ["increment"]

    @pytest.mark.asyncio
    async def test_chained_steps(self) -> None:
        async def step_a(state: CounterState) -> CounterState:
            state.steps_run.append("a")
            return state

        async def step_b(state: CounterState) -> CounterState:
            state.steps_run.append("b")
            return state

        async def step_c(state: CounterState) -> CounterState:
            state.steps_run.append("c")
            return state

        flow: Flow[CounterState] = Flow(name="chain")
        flow.add_step("a", step_a, next_step="b")
        flow.add_step("b", step_b, next_step="c")
        flow.add_step("c", step_c)

        result = await flow.run(CounterState(), start="a")
        assert result.steps_run == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_router_function(self) -> None:
        async def check(state: CounterState) -> CounterState:
            state.steps_run.append("check")
            return state

        async def high_path(state: CounterState) -> CounterState:
            state.steps_run.append("high")
            return state

        async def low_path(state: CounterState) -> CounterState:
            state.steps_run.append("low")
            return state

        def route(state: CounterState) -> str | None:
            return "high" if state.value > 5 else "low"

        flow: Flow[CounterState] = Flow(name="router")
        flow.add_step("check", check, next_step=route)
        flow.add_step("high", high_path)
        flow.add_step("low", low_path)

        # Low path
        result = await flow.run(CounterState(value=3), start="check")
        assert result.steps_run == ["check", "low"]

        # High path
        result = await flow.run(CounterState(value=10), start="check")
        assert result.steps_run == ["check", "high"]


class TestFlowErrors:
    @pytest.mark.asyncio
    async def test_unknown_step_raises(self) -> None:
        flow: Flow[CounterState] = Flow(name="test")
        with pytest.raises(UnknownStepError):
            await flow.run(CounterState(), start="nonexistent")

    def test_duplicate_step_raises(self) -> None:
        async def noop(state: CounterState) -> CounterState:
            return state

        flow: Flow[CounterState] = Flow(name="test")
        flow.add_step("a", noop)
        with pytest.raises(DuplicateStepError):
            flow.add_step("a", noop)

    @pytest.mark.asyncio
    async def test_max_steps_exceeded(self) -> None:
        async def loop_step(state: CounterState) -> CounterState:
            state.value += 1
            return state

        flow: Flow[CounterState] = Flow(name="infinite")
        flow.add_step("loop", loop_step, next_step="loop")

        with pytest.raises(MaxStepsExceededError):
            await flow.run(CounterState(), start="loop", max_steps=5)

    @pytest.mark.asyncio
    async def test_router_returning_none_stops(self) -> None:
        async def step(state: CounterState) -> CounterState:
            state.steps_run.append("step")
            return state

        def stop_router(state: CounterState) -> str | None:
            return None

        flow: Flow[CounterState] = Flow(name="test")
        flow.add_step("step", step, next_step=stop_router)

        result = await flow.run(CounterState(), start="step")
        assert result.steps_run == ["step"]
