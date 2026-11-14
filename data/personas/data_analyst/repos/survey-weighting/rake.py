# source: synthetic · persona: data_analyst · repo: survey-weighting
import pandas as pd


def rake(df: pd.DataFrame, margins: dict[str, dict[str, float]], iterations: int = 50) -> pd.Series:
    """Iterative proportional fitting: adjust weights until each variable matches its margin."""
    weights = pd.Series(1.0, index=df.index)
    for _ in range(iterations):
        for column, targets in margins.items():
            current = weights.groupby(df[column]).sum() / weights.sum()
            factors = {level: targets[level] / current[level] for level in targets}
            weights *= df[column].map(factors)
    return weights / weights.mean()
