from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

StateT = TypeVar("StateT", bound=BaseModel)


class FlowError(Exception):
    pass


class DuplicateStepError(FlowError):
    def __init__(self, step_name: str) -> None:
        super().__init__(f"Step '{step_name}' already exists")
        self.step_name = step_name


class UnknownStepError(FlowError):
    def __init__(self, step_name: str) -> None:
        super().__init__(f"Unknown step: {step_name}")
        self.step_name = step_name


class MaxStepsExceededError(FlowError):
    def __init__(self, max_steps: int) -> None:
        super().__init__(f"Flow exceeded max steps ({max_steps})")
        self.max_steps = max_steps


class Step(Generic[StateT]):
    def __init__(
        self,
        name: str,
        func: Callable[[StateT], Awaitable[StateT]],
        next_step: str | Callable[[StateT], str | None] | None = None,
    ) -> None:
        self.name = name
        self.func = func
        self.next_step = next_step

    async def execute(self, state: StateT) -> StateT:
        return await self.func(state)

    def get_next(self, state: StateT) -> str | None:
        if self.next_step is None:
            return None
        if isinstance(self.next_step, str):
            return self.next_step
        return self.next_step(state)


class Flow(Generic[StateT]):
    def __init__(self, name: str = "flow") -> None:
        self.name = name
        self.steps: dict[str, Step[StateT]] = {}

    def add_step(
        self,
        name: str,
        func: Callable[[StateT], Awaitable[StateT]],
        next_step: str | Callable[[StateT], str | None] | None = None,
    ) -> None:
        if name in self.steps:
            raise DuplicateStepError(name)
        self.steps[name] = Step(name, func, next_step)

    async def run(self, state: StateT, start: str = "start", max_steps: int = 50) -> StateT:
        current: str | None = start
        step_count = 0

        while current and step_count < max_steps:
            if current not in self.steps:
                raise UnknownStepError(current)

            step = self.steps[current]
            logger.debug("[flow:%s] step=%s (#%d)", self.name, current, step_count)
            state = await step.execute(state)
            current = step.get_next(state)
            step_count += 1

        if step_count >= max_steps:
            raise MaxStepsExceededError(max_steps)

        return state
