from __future__ import annotations

import logging
import re
from typing import Any

from .client import get_supabase

logger = logging.getLogger(__name__)


def create_issue(
    *,
    project_id: str,
    title: str,
    description: str | None = None,
    severity: str = "P2",
    category: str | None = None,
    run_id: str | None = None,
    slack_user_id: str | None = None,
) -> dict[str, Any]:
    """Insert a new issue and return the full record.

    severity: P0 | P1 | P2 | P3
    category: backend | frontend | ux | performance | integration
    slack_user_id: Slack user ID of the assigned owner
    """
    sb = get_supabase()
    row: dict[str, Any] = {
        "project_id": project_id,
        "title": title,
        "severity": severity,
        "status": "assigned",
    }
    if run_id:
        row["run_id"] = run_id
    if description:
        row["description"] = description
    if slack_user_id:
        row["slack_user_id"] = slack_user_id
    if category:
        # Map our prompt categories to DB categories
        category_map = {
            "functional": "frontend",
            "visual": "ux",
            "performance": "performance",
            "accessibility": "ux",
            "mobile": "frontend",
            "regression": "regression",
            "flaky": "flaky",
            "backend": "backend",
            "frontend": "frontend",
            "ux": "ux",
            "integration": "integration",
        }
        row["category"] = category_map.get(category, "frontend")

    result = sb.table("issues").insert(row).execute()
    return result.data[0]


def link_issue_to_run(issue_id: str, run_id: str) -> None:
    """Create an issue_runs junction record."""
    sb = get_supabase()
    sb.table("issue_runs").insert({
        "issue_id": issue_id,
        "run_id": run_id,
    }).execute()


def get_issues_for_run(run_id: str) -> list[dict[str, Any]]:
    """Fetch all issues linked to a run via issue_runs."""
    sb = get_supabase()
    result = (
        sb.table("issue_runs")
        .select("issues(*)")
        .eq("run_id", run_id)
        .execute()
    )
    return [row["issues"] for row in result.data if row.get("issues")]


def get_issues_for_project(
    project_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List issues for a project, optionally filtered by status."""
    sb = get_supabase()
    query = (
        sb.table("issues")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
    )
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data


# ── Root Cause Intelligence ─────────────────────────────────────────────


def _tokenize(text: str) -> set[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove stopwords."""
    STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "must", "can", "could", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "during", "before", "after", "above", "below", "between", "out",
        "off", "over", "under", "again", "further", "then", "once", "and",
        "but", "or", "nor", "not", "no", "so", "than", "too", "very",
        "just", "that", "this", "it", "its", "i", "me", "my", "we", "our",
    }
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return words - STOPWORDS


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


def find_similar_issues(
    project_id: str,
    title: str,
    description: str | None = None,
    threshold: float = 0.35,
    max_results: int = 5,
    exclude_issue_id: str | None = None,
) -> list[dict[str, Any]]:
    """Find existing issues similar to a new one using token-based similarity.

    Returns a list of dicts with the issue data plus a `similarity_score` field,
    sorted by descending similarity.

    Args:
        project_id: Scope similarity to the same project
        title: Title of the new issue
        description: Description of the new issue
        threshold: Minimum similarity score (0.0 to 1.0)
        max_results: Maximum number of similar issues to return
        exclude_issue_id: Skip this issue (useful when checking after creation)
    """
    sb = get_supabase()

    # Fetch recent issues for the same project
    result = (
        sb.table("issues")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    existing = result.data

    if not existing:
        return []

    # Build token set for the new issue
    new_text = title + " " + (description or "")
    new_tokens = _tokenize(new_text)

    if not new_tokens:
        return []

    # Score each existing issue
    scored: list[tuple[float, dict[str, Any]]] = []
    for issue in existing:
        if exclude_issue_id and issue["id"] == exclude_issue_id:
            continue

        existing_text = issue.get("title", "") + " " + (issue.get("description") or "")
        existing_tokens = _tokenize(existing_text)
        score = _jaccard_similarity(new_tokens, existing_tokens)

        if score >= threshold:
            scored.append((score, issue))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, issue in scored[:max_results]:
        results.append({
            **issue,
            "similarity_score": round(score, 3),
        })

    return results


def get_issue_frequency(
    project_id: str,
    title_pattern: str | None = None,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Get issue frequency counts for trend analysis.

    Groups issues by title similarity to detect recurring problems.
    Returns [{title, count, severities, first_seen, last_seen}].
    """
    sb = get_supabase()
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    result = (
        sb.table("issues")
        .select("*")
        .eq("project_id", project_id)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .execute()
    )

    if not result.data:
        return []

    # Group by tokenized title similarity
    groups: list[dict[str, Any]] = []
    assigned: set[str] = set()

    for issue in result.data:
        if issue["id"] in assigned:
            continue

        tokens = _tokenize(issue["title"])
        group = {
            "representative_title": issue["title"],
            "issues": [issue],
            "severities": {issue["severity"]},
            "first_seen": issue["created_at"],
            "last_seen": issue["created_at"],
        }
        assigned.add(issue["id"])

        # Find similar issues
        for other in result.data:
            if other["id"] in assigned:
                continue
            other_tokens = _tokenize(other["title"])
            if _jaccard_similarity(tokens, other_tokens) >= 0.4:
                group["issues"].append(other)
                group["severities"].add(other["severity"])
                assigned.add(other["id"])
                if other["created_at"] < group["first_seen"]:
                    group["first_seen"] = other["created_at"]
                if other["created_at"] > group["last_seen"]:
                    group["last_seen"] = other["created_at"]

        groups.append({
            "title": group["representative_title"],
            "count": len(group["issues"]),
            "severities": sorted(group["severities"]),
            "first_seen": group["first_seen"],
            "last_seen": group["last_seen"],
            "issue_ids": [i["id"] for i in group["issues"]],
        })

    # Sort by count descending
    groups.sort(key=lambda g: g["count"], reverse=True)
    return groups
