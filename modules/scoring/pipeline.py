import os
import numpy as np
import pandas as pd

class ScoringEngine:
    """Toy polygenic + monogenic scoring (demo only)."""

    def __init__(self, csv_path: str):
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV not found: {csv_path}")
        self.df = pd.read_csv(csv_path)
        rng = np.random.RandomState(13)
        self.snp_cols = [c for c in self.df.columns if c.startswith("snp")]
        self.condition_weights = {
            "Type 2 Diabetes": dict(zip(self.snp_cols, rng.uniform(-1.0, 1.0, size=len(self.snp_cols)))),
            "Coronary Artery Disease": dict(zip(self.snp_cols, rng.uniform(-1.0, 1.0, size=len(self.snp_cols)))),
            "Hypertension": dict(zip(self.snp_cols, rng.uniform(-1.0, 1.0, size=len(self.snp_cols)))),
        }
        self.scale = 6.0
        self.monogenic_penalties = {"BRCA1": 25, "CFTR": 15}

    @staticmethod
    def _sigmoid(x):
        return 1.0 / (1.0 + np.exp(-x))

    def _polygenic_probability(self, row: pd.Series, condition: str) -> float:
        weights = self.condition_weights[condition]
        dot = sum(float(row[snp]) * w for snp, w in weights.items())
        return float(self._sigmoid(dot / self.scale))

    def compute_detailed_scores(self, embryo_id: str) -> dict:
        sub = self.df[self.df["id"] == embryo_id]
        if sub.empty:
            raise KeyError(f"Embryo {embryo_id} not found")
        row = sub.iloc[0]

        polygenic = {
            cond: round(100.0 * self._polygenic_probability(row, cond), 2)
            for cond in self.condition_weights
        }
        monogenic = {"BRCA1": row.get("BRCA1", "negative"), "CFTR": row.get("CFTR", "negative")}

        risk_component = sum(0.30 * pct for pct in polygenic.values())
        penalty = sum(self.monogenic_penalties[g] for g, s in monogenic.items() if str(s).lower() == "carrier")
        overall = max(0, round(100.0 - risk_component - penalty, 2))

        return {"embryo_id": embryo_id, "polygenic": polygenic, "monogenic": monogenic, "overall_score": overall}

    def score_all(self):
        return [self.compute_detailed_scores(eid) for eid in self.df["id"].tolist()]
