"""
services/clustering_service.py
--------------------------------
Milestone 3, Parts 10-11: K-Means Session Clustering Module.

Pipeline (per spec): Session Logs -> Pandas -> Feature Extraction ->
Missing-value handling -> StandardScaler -> KMeans -> Cluster
Assignment -> Cluster Analysis.

Cluster NUMBERS from KMeans have no inherent meaning — this module
never assumes "cluster 0 = low risk". Instead it computes each
cluster's mean integrity_score after fitting and ranks clusters by
that mean to derive an interpretable label ("Normal behavioural
pattern" / "Moderate-risk behavioural pattern" / "High-risk
behavioural pattern"), documenting the derivation in the returned
`interpretation_basis` field rather than leaving it implicit.
"""

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

CLUSTER_FEATURES = [
    "tab_switches", "focus_losses", "face_absent_events", "face_absent_duration",
    "multiple_face_events", "copy_attempts", "paste_attempts", "fullscreen_exits",
    "network_interruptions", "total_violations", "integrity_score",
]


def _interpret_clusters(df: pd.DataFrame) -> dict:
    """
    cluster_index -> interpretable label, derived from each cluster's
    mean integrity_score (highest mean = lowest-risk cluster). This is
    the "analyze cluster characteristics, then assign a label" step
    the spec requires — never a hardcoded 0/1/2 -> risk mapping.
    """
    means = df.groupby("cluster_index")["integrity_score"].mean().sort_values(ascending=False)
    labels_by_rank = ["Normal behavioural pattern", "Moderate-risk behavioural pattern", "High-risk behavioural pattern"]
    # If there are more/fewer clusters than 3 labels, extend/truncate gracefully.
    while len(labels_by_rank) < len(means):
        labels_by_rank.append(f"Behavioural pattern (rank {len(labels_by_rank) + 1})")

    return {cluster_idx: labels_by_rank[rank] for rank, cluster_idx in enumerate(means.index)}


def run_kmeans(df: pd.DataFrame, n_clusters: int = 3, random_state: int = 42) -> dict:
    """
    Fit K-Means on session-level features.

    Returns None (rather than a fabricated result) if there isn't
    enough data to cluster meaningfully — Milestone 3, Part 15's
    "insufficient data" rule.
    """
    available_features = [f for f in CLUSTER_FEATURES if f in df.columns]
    if df is None or len(df) < max(n_clusters, 2) or not available_features:
        return None

    work = df.copy()
    # Missing-value handling: numeric columns default-fill with the
    # column median rather than dropping rows (Milestone 3 pipeline
    # step "Missing-value handling").
    for col in available_features:
        work[col] = pd.to_numeric(work[col], errors="coerce")
        if work[col].isna().any():
            work[col] = work[col].fillna(work[col].median())

    X = work[available_features].to_numpy(dtype=float)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    k = min(n_clusters, len(work))
    model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    cluster_index = model.fit_predict(X_scaled)

    work = work.reset_index(drop=True)
    work["cluster_index"] = cluster_index

    label_map = _interpret_clusters(work)
    work["cluster_label"] = work["cluster_index"].map(label_map)

    # PCA to 2D purely for visualization — never treated as the
    # original features themselves (Milestone 3, Part 11).
    pca = PCA(n_components=2, random_state=random_state)
    coords = pca.fit_transform(X_scaled)
    work["pca_x"] = coords[:, 0]
    work["pca_y"] = coords[:, 1]

    cluster_stats = (
        work.groupby(["cluster_index", "cluster_label"])[available_features]
        .mean()
        .round(2)
        .reset_index()
        .to_dict(orient="records")
    )
    cluster_sizes = work["cluster_index"].value_counts().to_dict()

    return {
        "assignments": work[["session_id", "cluster_index", "cluster_label", "pca_x", "pca_y"]].to_dict(orient="records")
        if "session_id" in work.columns else work[["cluster_index", "cluster_label", "pca_x", "pca_y"]].to_dict(orient="records"),
        "cluster_stats": cluster_stats,
        "cluster_sizes": {int(k): int(v) for k, v in cluster_sizes.items()},
        "features_used": available_features,
        "n_clusters": k,
        "explained_variance_ratio": [round(float(v), 3) for v in pca.explained_variance_ratio_],
        "interpretation_basis": (
            "Clusters are ranked by mean integrity_score across their member sessions "
            "(highest mean = lowest-risk pattern); cluster index numbers themselves carry "
            "no meaning and can change between runs."
        ),
        "_work_df": work,  # kept for the PCA chart function below; not serialized to templates
    }


def pca_scatter_chart(cluster_result: dict):
    """2D PCA scatter of clusters (Milestone 3, Part 11)."""
    if not cluster_result:
        return None
    work = cluster_result.get("_work_df")
    if work is None or work.empty:
        return None

    fig, ax = plt.subplots(figsize=(6, 5))
    palette = {"Normal behavioural pattern": "#55a868",
               "Moderate-risk behavioural pattern": "#dd8452",
               "High-risk behavioural pattern": "#c44e52"}
    for label, group in work.groupby("cluster_label"):
        ax.scatter(group["pca_x"], group["pca_y"], label=label,
                   color=palette.get(label, "#4C72B0"), alpha=0.75, s=50)
    ax.set_title("Session Clusters (PCA Projection)")
    ax.set_xlabel("PCA Component 1")
    ax.set_ylabel("PCA Component 2")
    ax.legend(fontsize=8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
