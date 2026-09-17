"""
services/synthetic_data_service.py
------------------------------------
Milestone 3, Part 13: Synthetic Session Data Corpus.

Generates clearly-labelled synthetic examination sessions with
controlled LOW/MEDIUM/HIGH-risk behavioural profiles, entirely in
memory (never written to the real candidate tables). Used to:

  1. Validate the integrity scoring engine's consistency/boundaries
     (services/integrity_scoring_service.py) against known-good inputs
     — see validate_scoring_consistency() below.
  2. Give the analytics/clustering modules a large-enough, realistic
     dataset to demonstrate on when the real database doesn't have
     enough completed sessions yet (Milestone 3, Part 10's K-Means
     needs a meaningful sample size).

Every row this module produces carries `data_source = "SYNTHETIC"` so
it can never be mistaken for real candidate data by a template or
export (Milestone 3, Part 13's explicit requirement).
"""

import random

import pandas as pd

_PROFILES = {
    "LOW": dict(
        tab_switches=(0, 1), focus_losses=(0, 1), face_absent_events=(0, 1),
        face_absent_duration=(0, 15), multiple_face_events=(0, 0), copy_attempts=(0, 0),
        paste_attempts=(0, 0), fullscreen_exits=(0, 0), network_interruptions=(0, 0),
        object_detection_events=(0, 0), face_movement_events=(0, 0),
        face_presence_ratio=(0.95, 1.0),
    ),
    "MEDIUM": dict(
        tab_switches=(2, 4), focus_losses=(1, 3), face_absent_events=(1, 3),
        face_absent_duration=(15, 90), multiple_face_events=(0, 1), copy_attempts=(0, 2),
        paste_attempts=(0, 1), fullscreen_exits=(0, 1), network_interruptions=(0, 1),
        object_detection_events=(0, 0), face_movement_events=(0, 1),
        face_presence_ratio=(0.80, 0.95),
    ),
    "HIGH": dict(
        tab_switches=(5, 12), focus_losses=(4, 10), face_absent_events=(4, 10),
        face_absent_duration=(120, 400), multiple_face_events=(1, 4), copy_attempts=(2, 6),
        paste_attempts=(1, 4), fullscreen_exits=(1, 4), network_interruptions=(1, 3),
        object_detection_events=(0, 2), face_movement_events=(1, 3),
        face_presence_ratio=(0.40, 0.79),
    ),
}


def _rand_int(bounds):
    lo, hi = bounds
    return random.randint(lo, hi)


def _rand_float(bounds):
    lo, hi = bounds
    return round(random.uniform(lo, hi), 4)


def generate_synthetic_session(profile: str, index: int) -> dict:
    """One synthetic session row, matching integrity_scoring_service.session_feature_row()'s shape."""
    if profile not in _PROFILES:
        raise ValueError(f"Unknown synthetic profile: {profile!r}")
    p = _PROFILES[profile]

    row = {
        "session_id": None,
        "synthetic_session_id": f"SYN-{profile}-{index:03d}",
        "candidate_id": None,
        "candidate_name": f"Synthetic Candidate {index:03d}",
        "assessment_id": None,
        "status": "submitted",
        "tab_switches": _rand_int(p["tab_switches"]),
        "focus_losses": _rand_int(p["focus_losses"]),
        "face_absent_events": _rand_int(p["face_absent_events"]),
        "face_absent_duration": _rand_int(p["face_absent_duration"]),
        "multiple_face_events": _rand_int(p["multiple_face_events"]),
        "copy_attempts": _rand_int(p["copy_attempts"]),
        "paste_attempts": _rand_int(p["paste_attempts"]),
        "fullscreen_exits": _rand_int(p["fullscreen_exits"]),
        "network_interruptions": _rand_int(p["network_interruptions"]),
        "object_detection_events": _rand_int(p["object_detection_events"]),
        "face_movement_events": _rand_int(p["face_movement_events"]),
        "face_presence_ratio": _rand_float(p["face_presence_ratio"]),
        "intended_profile": profile,
        "data_source": "SYNTHETIC",
    }
    row["total_violations"] = (
        row["tab_switches"] + row["focus_losses"] + row["face_absent_events"]
        + row["multiple_face_events"] + row["copy_attempts"] + row["paste_attempts"]
        + row["fullscreen_exits"] + row["network_interruptions"]
        + row["object_detection_events"] + row["face_movement_events"]
    )
    return row


def score_synthetic_row(row: dict, weights: dict, base_score: int, risk_label_fn) -> dict:
    """Apply the SAME weighted-scoring formula used for real sessions, for consistency validation."""
    penalty = 0
    penalty += row["tab_switches"] * weights.get("tab_switch", 0)
    penalty += row["focus_losses"] * weights.get("window_blur", 0)
    penalty += row["face_absent_events"] * weights.get("no_face", 0)
    penalty += row["multiple_face_events"] * weights.get("multiple_faces", 0)
    penalty += row["copy_attempts"] * weights.get("copy_attempt", 0)
    penalty += row["paste_attempts"] * weights.get("paste_attempt", 0)
    penalty += row["fullscreen_exits"] * weights.get("fullscreen_exit", 0)
    penalty += row["network_interruptions"] * weights.get("camera_lost", 0)
    penalty += row["object_detection_events"] * weights.get("phone_detected", 0)
    penalty += row["face_movement_events"] * weights.get("face_covered", 0)

    score = max(0, min(100, base_score - penalty))
    row = dict(row)
    row["integrity_score"] = score
    row["risk_level"] = risk_label_fn(score)
    return row


def generate_corpus(n_low: int = 40, n_medium: int = 35, n_high: int = 25, seed: int = 42) -> pd.DataFrame:
    """
    A full synthetic session corpus (default 100 sessions, Milestone 3
    Part 13's example size), as a labelled Pandas DataFrame.
    `seed` makes the corpus reproducible across runs/tests.
    """
    rng_state = random.getstate()
    random.seed(seed)
    try:
        rows = []
        idx = 1
        for profile, n in (("LOW", n_low), ("MEDIUM", n_medium), ("HIGH", n_high)):
            for _ in range(n):
                rows.append(generate_synthetic_session(profile, idx))
                idx += 1
        return pd.DataFrame(rows)
    finally:
        random.setstate(rng_state)


def generate_scored_corpus(weights: dict, base_score: int, risk_label_fn, n_low: int = 40, n_medium: int = 35,
                            n_high: int = 25, seed: int = 42):
    """
    Same as generate_corpus(), but with the weighted integrity score
    and risk label already applied to every row (via the SAME formula
    used for real sessions) — the shape services/analytics_service.py
    and services/clustering_service.py expect, so the "Synthetic Demo"
    view of Analytics/Clusters can reuse the exact real-data pipeline.
    """
    corpus = generate_corpus(n_low=n_low, n_medium=n_medium, n_high=n_high, seed=seed)
    scored_rows = [score_synthetic_row(row, weights, base_score, risk_label_fn) for row in corpus.to_dict(orient="records")]
    return pd.DataFrame(scored_rows)


def validate_scoring_consistency(weights: dict, base_score: int, risk_label_fn, seed: int = 7) -> dict:
    """
    Milestone 3, Part 14: automated validation that the weighted
    scoring engine produces the expected ordering/boundaries against
    synthetic sessions of each known risk profile.

    Returns a dict with pass/fail per profile plus the aggregate
    pass/fail, so a caller (route or test) can surface it directly
    without re-deriving anything.
    """
    corpus = generate_corpus(n_low=15, n_medium=15, n_high=15, seed=seed)
    scored = corpus.apply(lambda r: score_synthetic_row(r.to_dict(), weights, base_score, risk_label_fn), axis=1)
    scored_df = pd.DataFrame(list(scored))

    results = {}
    all_passed = True
    for profile in ("LOW", "MEDIUM", "HIGH"):
        subset = scored_df[scored_df["intended_profile"] == profile]
        expected_risk = profile
        match_rate = (subset["risk_level"] == expected_risk).mean() if len(subset) else 0.0
        avg_score = subset["integrity_score"].mean() if len(subset) else None
        bounds_ok = bool(((subset["integrity_score"] >= 0) & (subset["integrity_score"] <= 100)).all())
        # Synthetic profiles are generated with enough separation that
        # we expect a strong (not necessarily 100%) match rate; require
        # a majority to flag a genuine scoring-policy regression.
        passed = bounds_ok and match_rate >= 0.6
        all_passed = all_passed and passed
        results[profile] = {
            "sessions": int(len(subset)),
            "expected_risk_level": expected_risk,
            "match_rate": round(float(match_rate), 3),
            "avg_integrity_score": round(float(avg_score), 2) if avg_score is not None else None,
            "score_bounds_ok": bounds_ok,
            "passed": passed,
        }

    # Monotonicity check: LOW should score higher on average than
    # MEDIUM, which should score higher than HIGH.
    low_avg = results["LOW"]["avg_integrity_score"] or 0
    med_avg = results["MEDIUM"]["avg_integrity_score"] or 0
    high_avg = results["HIGH"]["avg_integrity_score"] or 0
    monotonic = low_avg >= med_avg >= high_avg
    all_passed = all_passed and monotonic

    return {"profiles": results, "monotonic_ordering": monotonic, "all_passed": all_passed}
