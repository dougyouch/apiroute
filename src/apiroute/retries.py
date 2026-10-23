import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Retries:
    """How many attempts a request gets and how long to sleep between them.

    attempts is the total number of attempts, not extra ones. The sleep before retry n is
    sleep * backoff ** (n - 1), capped at max_sleep. jitter=True sleeps a random time up to
    that; a float in 0..1 shortens it by up to that fraction. Defaults match the Ruby gem.
    """

    attempts: int = 1
    sleep: float = 0.05
    backoff: float = 1
    max_sleep: float | None = None
    jitter: bool | float = False

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be at least 1")
        if not isinstance(self.jitter, bool) and not 0 <= self.jitter <= 1:
            raise ValueError("jitter must be True, False or a number from 0 to 1")

    @classmethod
    def exponential(
        cls,
        *,
        attempts: int,
        initial: float = 0.1,
        max: float = 10,
        multiplier: float = 2,
        jitter: bool | float = False,
    ) -> "Retries":
        return cls(attempts, initial, backoff=multiplier, max_sleep=max, jitter=jitter)

    def delay(self, retry_number: int, rng: random.Random | None = None) -> float:
        delay = self.capped(self.sleep * self.backoff ** (retry_number - 1))
        return self._jittered(delay, rng or random)

    def capped(self, delay: float) -> float:
        return delay if self.max_sleep is None else min(delay, self.max_sleep)

    def _jittered(self, delay: float, rng) -> float:
        if self.jitter is True:
            return rng.uniform(0, delay)
        if self.jitter:
            return delay * (1 - rng.uniform(0, self.jitter))
        return delay
