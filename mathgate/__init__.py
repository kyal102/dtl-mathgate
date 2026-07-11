"""mathgate (DTL MathGate) — deterministic exact-arithmetic engine with replayable certificates."""
from .engine import calculate, Result, Refused

__all__ = ["calculate", "Result", "Refused"]
__version__ = "0.1.0"
