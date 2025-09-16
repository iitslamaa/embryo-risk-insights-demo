# modules/scoring/pipeline.py
import pandas as pd
import numpy as np
from typing import Optional

class EngineConfig:
    def __init__(self, seed: int = 42, scale: float = 1.0):
        self.seed = seed
        self.scale = scale

class ScoringEngine:
    def __init__(self, csv_path: str, config: Optional[EngineConfig] = None):
        self.csv_path = csv_path
        self.config = config or EngineConfig()

        # Load CSV and normalize column names (lowercase, underscores)
        df = pd.read_csv(csv_path)
        df.columns = [str(c).strip() for c in df.columns]
        norm_map = {c: c.lower().replace(" ", "_") for c in df.columns}
        df.rename(columns=norm_map, inplace=True)

        # Choose an ID column robustly
        id_candidates = ["embryo_id", "embryoid", "id", "embryo"]
        self.id_col = next((c for c in id_candidates if c in df.columns), None)
        if self.id_col is None:
            self.id_col = "embryo_id"
            df[self.id_col] = [f"E{i+1}" for i in range(len(df))]

        # SNP features
        self.snp_cols = [c for c in df.columns if c.startswith("snp")]
        if not self.snp_cols:
            blacklist = {self.id_col, "brca1", "cftr"}
            self.snp_cols = [c for c in df.columns
                             if c not in blacklist and pd.api.types.is_numeric_dtype(df[c])]

        self.embryos = df

        # RNG + toy weights
        self.rng = np.random.default_rng(self.config.seed)
        self.condition_names = ["Diabetes", "HeartDisease", "Alzheimers"]
        self.condition_weights = {
            cond: {c: float(self.rng.normal()) for c in self.snp_cols}
            for cond in self.condition_names
        }
        # keep keys lowercase to match normalized columns
        self.monogenic_penalties = {"brca1": 15.0, "cftr": 10.0}

    # ---------- Config ----------
    def update_config(self, seed: Optional[int] = None, scale: Optional[float] = None) -> bool:
        if seed is not None:
            self.config.seed = int(seed)
        if scale is not None:
            self.config.scale = float(scale)
        # reinit rng + weights so config changes take effect
        self.rng = np.random.default_rng(self.config.seed)
        for cond in self.condition_weights:
            self.condition_weights[cond] = {c: float(self.rng.normal()) for c in self.snp_cols}
        return True

    # ---------- Helpers ----------
    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + np.exp(-x))

    def _polygenic_logit(self, row, condition: str) -> float:
        w = self.condition_weights[condition]
        return float(sum(float(row[c]) * float(w[c]) for c in self.snp_cols))

    def _polygenic_probability(self, row, condition: str) -> float:
        z = self._polygenic_logit(row, condition)
        return float(self._sigmoid(z / self.config.scale))

    def _row_for_id(self, embryo_id: str):
        m = self.embryos[self.embryos[self.id_col] == embryo_id]
        if m.empty:
            raise KeyError(embryo_id)
        return m.iloc[0]

    # ---------- Public ----------
    def compute_detailed_scores(self, embryo_id: str) -> dict:
        row = self._row_for_id(embryo_id)

        polygenic = {
            cond: round(100.0 * self._polygenic_probability(row, cond), 2)
            for cond in self.condition_weights
        }

        # monogenic flags (treat missing as 'negative')
        def get_flag(col):
            col_l = col.lower()
            if col_l in self.embryos.columns:
                return str(row[col_l])
            col_u = col.upper()
            if col_u in self.embryos.columns:
                return str(row[col_u])
            return "negative"

        monogenic = {"BRCA1": get_flag("brca1"), "CFTR": get_flag("cftr")}

        risk_component = sum(0.30 * pct for pct in polygenic.values())
        penalty = sum(self.monogenic_penalties[g.lower()]
                      for g, s in monogenic.items() if str(s).lower() == "carrier")
        overall = max(0, round(100.0 - risk_component - penalty, 2))

        return {
            "embryo_id": str(row[self.id_col]),
            "polygenic": polygenic,
            "monogenic": monogenic,
            "overall_score": overall,
            "config": {"seed": self.config.seed, "scale": self.config.scale},
        }

    def score_all(self):
        return [self.compute_detailed_scores(str(eid)) for eid in self.embryos[self.id_col]]
