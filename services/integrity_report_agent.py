"""
services/integrity_report_agent.py
--------------------------------------
Milestone 3, Parts 16-18: LangChain AI Integrity Report Agent.

The agent is handed ONLY structured, already-computed evidence —
integrity score, risk level, face presence ratio, event counts,
confirmed incidents (services/integrity_scoring_service.py +
services/alert_service.py + services/evidence_service.py) — and its
job is to SUMMARIZE that evidence in plain English for an examiner. It
never independently decides whether a candidate cheated (Part 17): the
rule-based score and recorded events are the source of truth, and the
agent's text is clearly generated FROM them, not instead of them.

If LangChain / an API key isn't available, `generate_report()`
transparently falls back to `_deterministic_report()`, a structured-
template generator that produces the same schema without an LLM call.
The response always says which path was used (`is_fallback`) — this
module never fakes AI output (Milestone 3, Part 31).
"""

import json

from flask import current_app

_SYSTEM_PROMPT = (
    "You are an assistant that writes integrity-monitoring summaries for exam "
    "invigilators. You are given ONLY structured facts already computed by the "
    "proctoring system: an integrity score, a risk level, a face presence ratio, "
    "counts of specific monitoring event types, and any confirmed incidents. "
    "Write a concise, neutral summary of what was OBSERVED. Do not invent events "
    "that are not in the data. Do not accuse the candidate of cheating or state "
    "a conclusion about intent — only describe the recorded behaviour and the "
    "system's risk classification, and end with 1-2 short, concrete recommendations "
    "for what the invigilator should review next."
)


def _build_prompt(evidence: dict) -> str:
    return (
        f"Session evidence (JSON):\n{json.dumps(evidence, indent=2, default=str)}\n\n"
        "Write the report in this exact structure:\n"
        "Summary: <2-4 sentences describing what was observed, grounded only in the JSON above>\n"
        "Recommendations: <1-2 short sentences of concrete next steps for the invigilator>"
    )


def _get_llm():
    """
    Returns a configured LangChain chat model, or None if unavailable
    (missing package or missing API key) — the caller falls back to
    the deterministic generator in that case.
    """
    try:
        api_key = current_app.config.get("LANGCHAIN_API_KEY")
        model_name = current_app.config.get("LLM_MODEL", "claude-sonnet-4-6")
    except RuntimeError:
        return None

    if not api_key:
        return None

    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        return None

    try:
        return ChatAnthropic(model=model_name, api_key=api_key, max_tokens=500, temperature=0)
    except Exception:
        return None


def _parse_llm_text(text: str) -> tuple:
    """Split the LLM's 'Summary: ... Recommendations: ...' response into (summary, recommendations)."""
    summary, recommendations = text, ""
    if "Recommendations:" in text:
        parts = text.split("Recommendations:", 1)
        summary = parts[0].replace("Summary:", "", 1).strip()
        recommendations = parts[1].strip()
    elif "Summary:" in text:
        summary = text.replace("Summary:", "", 1).strip()
    return summary.strip(), recommendations.strip()


def _deterministic_report(evidence: dict) -> tuple:
    """
    Structured-template fallback — no LLM call. Produces the same
    kind of grounded, no-hallucination summary using plain string
    formatting over the evidence dict (Milestone 3, Part 17's required
    fallback for when the LLM/API is unavailable).
    """
    score = evidence["integrity_score"]
    risk = evidence["risk_level"]
    presence = evidence.get("face_presence_percent")
    counts = evidence.get("event_counts", {})
    incidents = evidence.get("confirmed_incidents", [])

    event_phrases = []
    _labels = {
        "tab_switch": "tab-switch event", "window_blur": "focus-loss event",
        "no_face": "face-absence interval", "multiple_faces": "confirmed multiple-face event",
        "camera_lost": "camera-interruption event", "fullscreen_exit": "fullscreen-exit event",
        "copy_attempt": "copy attempt", "paste_attempt": "paste attempt",
        "phone_detected": "prohibited-object detection", "face_covered": "face-covering detection",
    }
    for key, label in _labels.items():
        count = counts.get(key, 0)
        if count:
            event_phrases.append(f"{count} {label}{'s' if count != 1 else ''}")

    if presence is not None:
        presence_sentence = f"The candidate maintained face presence for {presence:.1f}% of the monitored duration."
    else:
        presence_sentence = "Face presence could not be determined for this session."

    if event_phrases:
        events_sentence = "Recorded events: " + ", ".join(event_phrases) + "."
    else:
        events_sentence = "No violation events were recorded during this session."

    incident_sentence = (
        f" {len(incidents)} confirmed incident(s) with stored evidence." if incidents else ""
    )

    summary = (
        f"{presence_sentence} {events_sentence}{incident_sentence} "
        f"The session is classified as {risk} risk based on the configured integrity scoring policy "
        f"(integrity score {score}/100)."
    )

    if risk == "HIGH":
        recommendations = "Review the flagged incidents and face-absence intervals before releasing results; consider a manual re-check."
    elif risk == "MEDIUM":
        recommendations = "Review the recorded tab-switch and focus-loss events for context before finalizing the result."
    else:
        recommendations = "No further review is required based on recorded monitoring data."

    return summary, recommendations


def build_evidence_payload(session, score_result: dict, incidents: list = None) -> dict:
    """
    Assembles the exact structured evidence the agent (or fallback) is
    allowed to see — candidate/session info, score, risk, face
    presence, event counts, and confirmed incidents only. Nothing else
    is passed to the LLM (Milestone 3, Part 17).
    """
    return {
        "candidate_id": session.user_id,
        "candidate_name": session.user.full_name if session.user else "Unknown",
        "assessment_name": session.assessment.name if session.assessment else "Unknown",
        "session_id": session.id,
        "integrity_score": score_result["integrity_score"],
        "risk_level": score_result["risk_level"],
        "face_presence_percent": score_result.get("face_presence_percent"),
        "event_counts": score_result.get("event_counts", {}),
        "total_violations": score_result.get("total_violations", 0),
        "confirmed_incidents": [
            {"event_type": i.event_type, "severity": i.severity, "description": i.description}
            for i in (incidents or [])
        ],
    }


def generate_report(evidence: dict) -> dict:
    """
    Produces {"summary": ..., "recommendations": ..., "model_used": ..., "is_fallback": bool}.

    Tries the configured LangChain/Anthropic model first; falls back
    to the deterministic template generator on any failure (missing
    package, missing key, API error) — never raises up to the route.
    """
    llm = _get_llm()
    if llm is not None:
        try:
            response = llm.invoke([
                ("system", _SYSTEM_PROMPT),
                ("human", _build_prompt(evidence)),
            ])
            text = response.content if hasattr(response, "content") else str(response)
            summary, recommendations = _parse_llm_text(text)
            if summary:
                model_name = current_app.config.get("LLM_MODEL", "claude-sonnet-4-6")
                return {
                    "summary": summary, "recommendations": recommendations,
                    "model_used": model_name, "is_fallback": False,
                }
        except Exception:
            pass  # fall through to deterministic fallback below

    summary, recommendations = _deterministic_report(evidence)
    return {
        "summary": summary, "recommendations": recommendations,
        "model_used": "deterministic-template-fallback", "is_fallback": True,
    }
