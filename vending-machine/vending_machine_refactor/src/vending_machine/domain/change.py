from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Tuple

from .exceptions import ChangeUnavailableError


@dataclass(frozen=True)
class ChangePlan:
    breakdown: Dict[int, int]
    amount: int


class ChangeCalculator:
    """
    재고 제한이 있는 정확한 거스름돈 계산기.
    단순 greedy가 아닌 DFS + memo 방식으로 조합을 찾는다.
    """

    def __init__(self, denominations: tuple[int, ...] = (1000, 500, 100, 50, 10)) -> None:
        self.denominations = denominations

    def calculate(self, amount: int, available: Dict[int, int]) -> Dict[int, int]:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        if amount == 0:
            return {}

        denoms = tuple(d for d in self.denominations if d in available and available[d] > 0)

        @lru_cache(maxsize=None)
        def solve(index: int, remaining: int, state: Tuple[int, ...]) -> Tuple[int, ...] | None:
            if remaining == 0:
                return tuple(0 for _ in denoms)
            if index >= len(denoms):
                return None

            denom = denoms[index]
            max_use = min(state[index], remaining // denom)

            for use in range(max_use, -1, -1):
                new_remaining = remaining - (use * denom)
                if new_remaining == 0:
                    rest = tuple(0 for _ in denoms[index + 1 :])
                    return tuple([0] * index + [use] + list(rest))
                next_state = list(state)
                next_state[index] -= use
                candidate = solve(index + 1, new_remaining, tuple(next_state))
                if candidate is not None:
                    mutable = list(candidate)
                    mutable[index] = use
                    return tuple(mutable)
            return None

        state = tuple(available.get(d, 0) for d in denoms)
        solution = solve(0, amount, state)
        if solution is None:
            raise ChangeUnavailableError(amount)
        return {d: q for d, q in zip(denoms, solution) if q > 0}
