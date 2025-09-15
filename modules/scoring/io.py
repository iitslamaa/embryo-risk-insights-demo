# modules/scoring/io.py
import pickle
from pathlib import Path
from typing import Any, Dict

def save_engine_state(engine: Any, path: str = "data/weights.pkl") -> None:
    """
    Persist the engine's minimal state needed to recreate results.
    We intentionally store plain Python objects (dicts, floats, etc.)
    so the pickle remains portable and resilient across code changes.
    """
    payload: Dict[str, Any] = {
        "condition_weights": getattr(engine, "condition_weights", {}),
        "monogenic_penalties": getattr(engine, "monogenic_penalties", {}),
        "config": {
            "seed": getattr(getattr(engine, "config", None), "seed", None),
            "scale": getattr(getattr(engine, "config", None), "scale", None),
        },
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(payload, f)

def load_engine_state(path: str = "data/weights.pkl") -> Dict[str, Any]:
    """
    Load a previously saved engine state. Returns a dict with keys:
      - condition_weights
      - monogenic_penalties
      - config (dict with seed, scale)
    """
    with open(path, "rb") as f:
        return pickle.load(f)
