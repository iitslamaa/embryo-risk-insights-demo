import os, random, json
import pandas as pd
import numpy as np

class EngineConfig:
    def __init__(self, seed: int = 42, scale: float = 1.0):
        self.seed = seed
        self.scale = scale

class ScoringEngine:
    def __init__(self, csv_path: str, config: EngineConfig = None):
        self.csv_path = csv_path
        self.config = config or EngineConfig()
        self.embryos = pd.read_csv(csv_path)
        self.rng = np.random.default_rng(self.config.seed)

        # toy condition weights
        self.condition_weights = {
            "Diabetes": {c: self.rng.normal() for c in self.embryos.columns if c.startswith("snp")},
            "HeartDisease": {c: self.rng.normal() for c in self.embryos.columns if c.startswith("snp")},
            "Alzheimers": {c: self.rng.normal() for c in self.embryos.columns if c.startswith("snp")},
        }
        self.monogenic_penalties = {"BRCA1": 15, "CFTR": 10}

    # ----------------
    # CONFIG METHODS
    # ----------------
    def update_config(self, seed=None, scale=None):
        """Update config and reinit RNG + weights"""
        if seed is not None:
            self.config.seed = seed
        if scale is not None:
            self.config.scale = scale
        # reinit rng + weights
        self.rng = np.random.default_rng(self.config.seed)
        for cond in self.condition_weights:
            self.condition_weights[cond] = {
                c: self.rng.normal() for c in self.embryos.columns if c.startswith("snp")
            }
        return True

    # ----------------
    # SCORING HELPERS
    # ----------------
    def _sigmoid(self, x: float) -> float:
        return 1 / (1 + np.exp(-x))

    def _polygenic_logit(self, row, condition: str) -> float:
        weights = self.condition_weights[condition]
        return sum(float(row[snp]) * float(w) for snp, w in weights.items())

    def _polygenic_probability(self, row, condition: str) -> float:
        z = self._polygenic_logit(row, condition)
        return float(self._sigmoid(z / self.config.scale))

    def compute_detailed_scores(self, embryo_id: str) -> dict:
        row = self.embryos[self.embryos["embryo_id"] == embryo_id].iloc[0]
        polygenic = {
            cond: round(100.0 * self._polygenic_probability(row, cond), 2)
            for cond in self.condition_weights
        }
        monogenic = {
            "BRCA1": row.get("BRCA1", "negative"),
            "CFTR": row.get("CFTR", "negative"),
        }
        risk_component = sum(0.30 * pct for pct in polygenic.values())
        penalty = sum(
            self.monogenic_penalties[g]
            for g, s in monogenic.items()
            if str(s).lower() == "carrier"
        )
        overall = max(0, round(100.0 - risk_component - penalty, 2))
        return {
            "embryo_id": embryo_id,
            "polygenic": polygenic,
            "monogenic": monogenic,
            "overall_score": overall,
            "config": {"seed": self.config.seed, "scale": self.config.scale},
        }

    def score_all(self):
        return [self.compute_detailed_scores(eid) for eid in self.embryos["embryo_id"]]
