from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from itertools import pairwise

from regime_trader.schemas.regime import RegimeOutput, TransitionProbability


class TransitionModel:
    def probabilities(self, history: Sequence[RegimeOutput]) -> tuple[TransitionProbability, ...]:
        if len(history) < 2:
            return ()
        counts: dict[str, Counter[str]] = defaultdict(Counter)
        for previous, current in pairwise(history):
            counts[previous.regime_label][current.regime_label] += 1
        probabilities: list[TransitionProbability] = []
        for from_regime, transitions in counts.items():
            total = sum(transitions.values())
            for to_regime, count in transitions.items():
                probabilities.append(
                    TransitionProbability(
                        from_regime=from_regime,
                        to_regime=to_regime,
                        probability=count / total,
                        observations=count,
                    )
                )
        return tuple(probabilities)
