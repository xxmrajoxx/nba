"""Shared regression machinery: player-season fixed effects with clustered standard errors."""
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests


def player_season(df: pd.DataFrame) -> pd.Series:
    return df["player_id"].astype(str) + "_" + df["season"]


def week_dummies(df: pd.DataFrame) -> pd.DataFrame:
    # One column per week of the season; the first week is left out as the reference.
    return pd.get_dummies(df["week_of_season"], prefix="week", drop_first=True, dtype=float)


def demean(frame, groups: pd.Series):
    """Subtract each group's average (the "within transformation"). Afterwards every value
    means "above or below this player's own average that season"."""
    return frame - frame.groupby(groups).transform("mean")


def fit_within(y: pd.Series, X: pd.DataFrame, groups: pd.Series, clusters: pd.Series):
    """OLS on demeaned data: identical estimates to giving every group its own intercept,
    without thousands of extra columns. Standard errors are clustered, because one
    player's games are not independent of each other."""
    y_within = demean(y, groups)
    X_within = demean(X, groups)
    X_within = X_within.loc[:, X_within.abs().sum() > 0]   # drop columns that never vary within a group
    return sm.OLS(y_within, X_within).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(clusters)[0]})


def coefficient_rows(model, names: list, **labels) -> list:
    """Estimate, 95% interval and p-value for each named coefficient, plus any fixed labels."""
    ci = model.conf_int()
    return [
        {**labels, "term": name, "estimate": model.params[name], "ci_low": ci.loc[name, 0],
         "ci_high": ci.loc[name, 1], "p_value": model.pvalues[name]}
        for name in names if name in model.params
    ]


def add_q_values(results: pd.DataFrame) -> pd.DataFrame:
    """Benjamini-Hochberg adjusted p-values ("q-values"). Testing many stats and days means
    some will look significant by luck; q < 0.05 keeps the share of false alarms among the
    "significant" results to about 5%."""
    results = results.copy()
    results["q_value"] = multipletests(results["p_value"], method="fdr_bh")[1]
    results["significant"] = results["q_value"] < 0.05
    return results
