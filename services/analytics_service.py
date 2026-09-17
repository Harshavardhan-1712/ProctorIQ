"""
services/analytics_service.py
--------------------------------
Milestone 3, Part 8-9: Data Science Analytics Module.

Builds analytics from a Pandas DataFrame of session-level features
(services/integrity_scoring_service.build_sessions_dataframe) using
Matplotlib + Seaborn for charts and returns them as base64-encoded PNG
data URIs, so routes/insights.py's templates can embed them directly
with `<img src="{{ chart }}">` — no extra static files or endpoints
needed per chart.

Every chart function is empty-data-safe: if there isn't enough data to
plot something meaningful, it returns `None` for the chart and the
caller/template shows "Insufficient data for analysis." (Milestone 3,
Part 15) instead of a fabricated chart.
"""

import base64
import io

import matplotlib
matplotlib.use("Agg")  # headless — no display server available in a web server process
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid")

_FEATURE_COLUMNS = [
    "tab_switches", "focus_losses", "face_absent_events", "multiple_face_events",
    "copy_attempts", "paste_attempts", "fullscreen_exits", "network_interruptions",
    "object_detection_events", "face_movement_events",
]

_MIN_ROWS_FOR_CHART = 2


def _fig_to_data_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def integrity_score_distribution(df: pd.DataFrame):
    """Histogram of integrity scores across sessions (Milestone 3, Part 8A / Part 9.1)."""
    if df is None or len(df) < _MIN_ROWS_FOR_CHART or "integrity_score" not in df.columns:
        return None

    fig, ax = plt.subplots(figsize=(6, 4))
    sns.histplot(df["integrity_score"], bins=10, kde=True, ax=ax, color="#4C72B0")
    ax.set_title("Integrity Score Distribution")
    ax.set_xlabel("Integrity Score")
    ax.set_ylabel("Number of Sessions")
    ax.set_xlim(0, 100)
    return _fig_to_data_uri(fig)


def risk_level_distribution(df: pd.DataFrame):
    """Bar chart of LOW/MEDIUM/HIGH counts (Milestone 3, Part 9.2)."""
    if df is None or len(df) < _MIN_ROWS_FOR_CHART or "risk_level" not in df.columns:
        return None

    order = [lvl for lvl in ("LOW", "MEDIUM", "HIGH") if lvl in df["risk_level"].unique()]
    counts = df["risk_level"].value_counts().reindex(order).fillna(0)

    fig, ax = plt.subplots(figsize=(5, 4))
    palette = {"LOW": "#55a868", "MEDIUM": "#dd8452", "HIGH": "#c44e52"}
    sns.barplot(x=counts.index, y=counts.values, hue=counts.index, legend=False,
                palette=[palette.get(k, "#888") for k in counts.index], ax=ax)
    ax.set_title("Risk Level Distribution")
    ax.set_xlabel("Risk Level")
    ax.set_ylabel("Number of Sessions")
    return _fig_to_data_uri(fig)


def event_frequency_chart(df: pd.DataFrame):
    """Bar chart of total occurrences per violation event type (Milestone 3, Part 8B / Part 9.3)."""
    if df is None or len(df) < 1:
        return None

    present_cols = [c for c in _FEATURE_COLUMNS if c in df.columns]
    if not present_cols:
        return None
    totals = df[present_cols].sum().sort_values(ascending=False)
    totals = totals[totals > 0]
    if totals.empty:
        return None

    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(x=totals.values, y=[c.replace("_", " ").title() for c in totals.index], ax=ax, color="#4C72B0")
    ax.set_title("Event Frequency Across Sessions")
    ax.set_xlabel("Total Occurrences")
    return _fig_to_data_uri(fig)


def event_frequency_heatmap(df: pd.DataFrame):
    """
    Session x event-type heatmap (Milestone 3, Part 8C / Part 9's
    required heatmap). Rows are sessions (capped to the most recent 30
    for legibility), columns are event types.
    """
    present_cols = [c for c in _FEATURE_COLUMNS if c in df.columns]
    if df is None or len(df) < _MIN_ROWS_FOR_CHART or not present_cols:
        return None

    subset = df[present_cols].tail(30)
    if subset.to_numpy().sum() == 0:
        return None

    fig, ax = plt.subplots(figsize=(8, max(3, 0.3 * len(subset))))
    sns.heatmap(
        subset, cmap="YlOrRd", ax=ax, cbar_kws={"label": "Event Count"},
        yticklabels=[f"S{i}" for i in subset.index],
        xticklabels=[c.replace("_", " ").title() for c in subset.columns],
    )
    ax.set_title("Event Frequency Heatmap (per Session)")
    return _fig_to_data_uri(fig)


def cohort_risk_profile(df: pd.DataFrame) -> dict:
    """
    Milestone 3, Part 12: cohort profiling by risk level — session
    count, avg integrity score, avg violations, avg face presence,
    most frequent event per cohort.
    """
    if df is None or df.empty or "risk_level" not in df.columns:
        return {}

    present_cols = [c for c in _FEATURE_COLUMNS if c in df.columns]
    cohorts = {}
    for level in ("LOW", "MEDIUM", "HIGH"):
        subset = df[df["risk_level"] == level]
        if subset.empty:
            continue
        most_frequent_event = None
        if present_cols:
            sums = subset[present_cols].sum()
            if sums.sum() > 0:
                most_frequent_event = sums.idxmax().replace("_", " ").title()

        cohorts[level] = {
            "sessions": int(len(subset)),
            "avg_integrity_score": round(float(subset["integrity_score"].mean()), 2),
            "avg_violations": round(float(subset["total_violations"].mean()), 2) if "total_violations" in subset else None,
            "avg_face_presence_percent": round(float(subset["face_presence_ratio"].mean()) * 100, 2)
            if "face_presence_ratio" in subset else None,
            "most_frequent_event": most_frequent_event,
        }
    return cohorts


def cohort_comparison_chart(cohort_profile: dict):
    """Milestone 3, Part 9.6: bar chart comparing avg integrity score across risk cohorts."""
    if not cohort_profile:
        return None
    levels = [lvl for lvl in ("LOW", "MEDIUM", "HIGH") if lvl in cohort_profile]
    if not levels:
        return None

    scores = [cohort_profile[lvl]["avg_integrity_score"] for lvl in levels]
    fig, ax = plt.subplots(figsize=(5, 4))
    palette = {"LOW": "#55a868", "MEDIUM": "#dd8452", "HIGH": "#c44e52"}
    sns.barplot(x=levels, y=scores, hue=levels, legend=False, palette=[palette[l] for l in levels], ax=ax)
    ax.set_title("Average Integrity Score by Risk Cohort")
    ax.set_ylabel("Avg Integrity Score")
    ax.set_ylim(0, 100)
    return _fig_to_data_uri(fig)


def build_analytics_bundle(df: pd.DataFrame) -> dict:
    """Everything routes/insights.py's analytics page needs, in one call."""
    cohorts = cohort_risk_profile(df)
    return {
        "has_data": df is not None and not df.empty,
        "session_count": int(len(df)) if df is not None else 0,
        "score_distribution_chart": integrity_score_distribution(df),
        "risk_distribution_chart": risk_level_distribution(df),
        "event_frequency_chart": event_frequency_chart(df),
        "event_heatmap_chart": event_frequency_heatmap(df),
        "cohorts": cohorts,
        "cohort_comparison_chart": cohort_comparison_chart(cohorts),
    }
