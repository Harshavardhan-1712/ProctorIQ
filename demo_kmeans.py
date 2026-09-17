import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# ---------------------------------------
# Synthetic session data for demonstration
# ---------------------------------------

data = {
    "integrity_score": [
        95, 92, 90, 88, 94,       # Low risk
        72, 68, 65, 70, 74,       # Medium risk
        38, 32, 25, 42, 28        # High risk
    ],
    "tab_switches": [
        0, 1, 0, 1, 0,
        2, 3, 2, 3, 2,
        6, 7, 8, 6, 9
    ],
    "face_absence_ratio": [
        0.01, 0.02, 0.03, 0.02, 0.01,
        0.15, 0.20, 0.18, 0.22, 0.16,
        0.45, 0.55, 0.60, 0.50, 0.65
    ]
}

df = pd.DataFrame(data)

# ---------------------------------------
# Prepare features
# ---------------------------------------

features = [
    "integrity_score",
    "tab_switches",
    "face_absence_ratio"
]

X = df[features]

# Standardize features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ---------------------------------------
# K-Means clustering
# ---------------------------------------

kmeans = KMeans(
    n_clusters=3,
    random_state=42,
    n_init=10
)

df["cluster"] = kmeans.fit_predict(X_scaled)

# ---------------------------------------
# Interpret clusters by average score
# ---------------------------------------

cluster_scores = df.groupby("cluster")["integrity_score"].mean()

ordered_clusters = cluster_scores.sort_values(ascending=False).index

risk_names = {
    ordered_clusters[0]: "Low Risk",
    ordered_clusters[1]: "Medium Risk",
    ordered_clusters[2]: "High Risk"
}

df["risk"] = df["cluster"].map(risk_names)

print("\nK-MEANS SESSION CLUSTERS")
print("=" * 40)
print(df[["integrity_score", "tab_switches",
          "face_absence_ratio", "cluster", "risk"]])

print("\nCluster Summary")
print("=" * 40)

summary = df.groupby("risk").agg(
    sessions=("cluster", "count"),
    avg_integrity_score=("integrity_score", "mean"),
    avg_tab_switches=("tab_switches", "mean"),
    avg_face_absence=("face_absence_ratio", "mean")
)

print(summary)

# ---------------------------------------
# VISUALIZATION 1 — K-Means clusters
# ---------------------------------------

plt.figure(figsize=(9, 6))

for risk in ["Low Risk", "Medium Risk", "High Risk"]:
    subset = df[df["risk"] == risk]

    plt.scatter(
        subset["tab_switches"],
        subset["integrity_score"],
        s=100,
        label=risk
    )

plt.xlabel("Tab Switches")
plt.ylabel("Integrity Score")
plt.title("K-Means Session Risk Clusters")
plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()
plt.show()

# ---------------------------------------
# VISUALIZATION 2 — Risk distribution
# ---------------------------------------

risk_counts = df["risk"].value_counts()

plt.figure(figsize=(8, 5))

plt.bar(
    risk_counts.index,
    risk_counts.values
)

plt.xlabel("Risk Category")
plt.ylabel("Number of Sessions")
plt.title("Session Risk Distribution")

plt.tight_layout()
plt.show()