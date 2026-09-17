"""
routes/insights.py
---------------------
Milestone 3 routing: Analytics, Behavioral Clusters, Cohort Analysis,
Alerts, Evidence, and the AI Integrity Report — all examiner-only
(`@role_required("invigilator", "admin")`), mounted under
`/invigilator/insights/...` so they sit alongside the existing
Module 6 invigilator dashboard rather than fragmenting navigation.

Like routes/invigilator.py, this file stays thin: every computation
lives in services/integrity_scoring_service.py,
services/analytics_service.py, services/clustering_service.py,
services/synthetic_data_service.py, services/integrity_report_agent.py,
services/alert_service.py, and services/evidence_service.py.
"""

import json

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user

from models import db
from models.analytics import Alert, AIIntegrityReport, ClusterRun, ClusterAssignment
from models.assessment import AssessmentSession
from services import (
    assessment_service, integrity_scoring_service, analytics_service,
    clustering_service, synthetic_data_service, integrity_report_agent,
    alert_service, evidence_service,
)
from utils.rbac import role_required

insights_bp = Blueprint("insights", __name__, url_prefix="/invigilator/insights")


def _completed_sessions():
    """Sessions with a definite outcome — the population Milestone 3 analytics/clustering run over."""
    return (
        AssessmentSession.query.filter(
            AssessmentSession.status.in_(["submitted", "auto_submitted", "terminated"])
        )
        .order_by(AssessmentSession.id)
        .all()
    )


@insights_bp.route("/analytics")
@role_required("invigilator", "admin")
def analytics():
    """Milestone 3, Parts 8-9, 12: integrity/analytics dashboard."""
    from flask import current_app

    use_synthetic = request.args.get("source") == "synthetic"

    if use_synthetic:
        weights = current_app.config.get("EVENT_SCORING_WEIGHTS", {})
        base_score = current_app.config.get("EVENT_SCORING_BASE_SCORE", 100)
        df = synthetic_data_service.generate_scored_corpus(
            weights, base_score, integrity_scoring_service.risk_label_from_score,
        )
    else:
        sessions = _completed_sessions()
        df = integrity_scoring_service.build_sessions_dataframe(sessions)

    bundle = analytics_service.build_analytics_bundle(df)

    return render_template(
        "invigilator/analytics.html",
        bundle=bundle,
        use_synthetic=use_synthetic,
        min_sessions_note=None if bundle["has_data"] else "Insufficient data for analysis.",
    )


@insights_bp.route("/clusters")
@role_required("invigilator", "admin")
def clusters():
    """Milestone 3, Parts 10-11: K-Means session clustering + PCA visualization."""
    from flask import current_app

    use_synthetic = request.args.get("source") == "synthetic"
    n_clusters = current_app.config.get("KMEANS_CLUSTERS", 3)
    random_state = current_app.config.get("KMEANS_RANDOM_STATE", 42)
    min_sessions = current_app.config.get("MIN_SESSIONS_FOR_CLUSTERING", 6)

    if use_synthetic:
        weights = current_app.config.get("EVENT_SCORING_WEIGHTS", {})
        base_score = current_app.config.get("EVENT_SCORING_BASE_SCORE", 100)
        df = synthetic_data_service.generate_scored_corpus(
            weights, base_score, integrity_scoring_service.risk_label_from_score,
        )
        data_source = "SYNTHETIC"
    else:
        sessions = _completed_sessions()
        df = integrity_scoring_service.build_sessions_dataframe(sessions)
        data_source = "REAL"

    insufficient = df is None or len(df) < min_sessions
    result = None if insufficient else clustering_service.run_kmeans(df, n_clusters=n_clusters, random_state=random_state)
    chart = clustering_service.pca_scatter_chart(result) if result else None

    if result is not None:
        # Persist this run so the interpreted labels are stable if the
        # page is revisited (Milestone 3, Part 10's "cluster numbers
        # aren't automatically meaningful" — the interpretation is
        # computed once per run and stored, not silently re-derived).
        run = ClusterRun(
            n_clusters=result["n_clusters"], n_sessions=len(df),
            features_json=json.dumps(result["features_used"]), data_source=data_source,
        )
        db.session.add(run)
        db.session.flush()
        for row in result["assignments"]:
            db.session.add(ClusterAssignment(
                run_id=run.id,
                session_id=row.get("session_id") if data_source == "REAL" else None,
                cluster_index=row["cluster_index"], cluster_label=row["cluster_label"],
            ))
        db.session.commit()

    return render_template(
        "invigilator/clusters.html",
        result=result, chart=chart, use_synthetic=use_synthetic,
        insufficient=insufficient, min_sessions=min_sessions, session_count=len(df) if df is not None else 0,
    )


@insights_bp.route("/validate")
@role_required("invigilator", "admin")
def validate():
    """Milestone 3, Part 14: automated scoring-consistency validation against synthetic sessions."""
    from flask import current_app

    weights = current_app.config.get("EVENT_SCORING_WEIGHTS", {})
    base_score = current_app.config.get("EVENT_SCORING_BASE_SCORE", 100)
    result = synthetic_data_service.validate_scoring_consistency(
        weights, base_score, integrity_scoring_service.risk_label_from_score,
    )
    return render_template("invigilator/validate.html", result=result)


@insights_bp.route("/alerts")
@role_required("invigilator", "admin")
def alerts():
    """Milestone 3, Part 19: alert review — open/acknowledged/resolved."""
    status_filter = request.args.get("status", "").strip().upper() or None
    all_alerts = alert_service.get_all_alerts(status=status_filter, limit=300)
    return render_template("invigilator/alerts.html", alerts=all_alerts, status_filter=status_filter)


@insights_bp.route("/alerts/<int:alert_id>/acknowledge", methods=["POST"])
@role_required("invigilator", "admin")
def acknowledge_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert_service.acknowledge_alert(alert, current_user.id)
    if request.is_json:
        return jsonify(success=True)
    flash("Alert acknowledged.", "info")
    return redirect(url_for("insights.alerts"))


@insights_bp.route("/alerts/<int:alert_id>/resolve", methods=["POST"])
@role_required("invigilator", "admin")
def resolve_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert_service.resolve_alert(alert, current_user.id)
    if request.is_json:
        return jsonify(success=True)
    flash("Alert resolved.", "info")
    return redirect(url_for("insights.alerts"))


@insights_bp.route("/session/<int:session_id>/report")
@role_required("invigilator", "admin")
def session_report(session_id):
    """Milestone 3, Parts 16-18: view (or generate) the AI integrity report for one session."""
    assessment_session = assessment_service.get_session(session_id)
    existing = (
        AIIntegrityReport.query.filter_by(session_id=session_id)
        .order_by(AIIntegrityReport.generated_at.desc())
        .first()
    )
    return render_template(
        "invigilator/report.html", assessment_session=assessment_session, report=existing,
    )


@insights_bp.route("/session/<int:session_id>/report/generate", methods=["POST"])
@role_required("invigilator", "admin")
def generate_report(session_id):
    """(Re)generate the AI integrity report for one session and persist it."""
    assessment_session = assessment_service.get_session(session_id)
    score_result = integrity_scoring_service.score_session(assessment_session)
    incidents = evidence_service.get_incidents_for_session(session_id)

    evidence_payload = integrity_report_agent.build_evidence_payload(assessment_session, score_result, incidents)
    generated = integrity_report_agent.generate_report(evidence_payload)

    report = AIIntegrityReport(
        session_id=session_id, user_id=assessment_session.user_id,
        integrity_score=score_result["integrity_score"], risk_level=score_result["risk_level"],
        summary_text=generated["summary"], recommendations_text=generated["recommendations"],
        structured_input_json=json.dumps(evidence_payload, default=str),
        model_used=generated["model_used"], is_fallback=generated["is_fallback"],
    )
    db.session.add(report)
    db.session.commit()

    flash("AI integrity report generated." + (" (fallback template — no LLM available)" if generated["is_fallback"] else ""), "info")
    return redirect(url_for("insights.session_report", session_id=session_id))


@insights_bp.route("/session/<int:session_id>/evidence")
@role_required("invigilator", "admin")
def session_evidence(session_id):
    """Milestone 3, Parts 20-23: incidents + stored evidence for one session — examiner-only."""
    assessment_session = assessment_service.get_session(session_id)
    incidents = evidence_service.get_incidents_for_session(session_id)
    evidence_list = evidence_service.get_evidence_for_session(session_id)
    integrity_ok = {e.id: evidence_service.verify_evidence_integrity(e) for e in evidence_list}

    return render_template(
        "invigilator/evidence.html",
        assessment_session=assessment_session, incidents=incidents,
        evidence_list=evidence_list, integrity_ok=integrity_ok,
    )
