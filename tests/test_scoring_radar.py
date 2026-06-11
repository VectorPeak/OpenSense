from datetime import timedelta

from opensense.core.radar import score_radar
from opensense.core.ranking import rank_issues
from opensense.core.scoring import score_issue
from opensense.github.radar import fetch_radar
from opensense.models import Issue, utc_now


def test_score_issue_prefers_recent_unassigned_small_bug() -> None:
    issue = Issue(
        owner="vllm-project",
        repo="vllm",
        number=123,
        title="Fix flaky scheduler test",
        labels=("bug", "tests", "help wanted"),
        comments=3,
        updated_at=utc_now() - timedelta(days=2),
        repository_stars=80000,
    )

    scored = score_issue(issue, min_stars=500, updated_days=14, max_comments=10)

    assert scored.total >= 80
    assert scored.contribution_type == "test"
    assert "unassigned" in scored.reasons
    assert not scored.risks


def test_rank_issues_filters_noisy_low_star_candidates() -> None:
    good = Issue(
        owner="encode",
        repo="httpx",
        number=1,
        title="Fix docs typo",
        labels=("docs",),
        comments=1,
        updated_at=utc_now(),
        repository_stars=14000,
    )
    noisy = Issue(
        owner="tiny",
        repo="repo",
        number=2,
        title="Huge redesign",
        labels=("feature",),
        comments=99,
        updated_at=utc_now(),
        repository_stars=10,
    )

    ranked = rank_issues([noisy, good], min_stars=500, max_comments=10)

    assert [item.issue.ref for item in ranked] == ["encode/httpx#1"]


def test_radar_scores_external_merges_and_language_match() -> None:
    result = score_radar(
        "vllm-project/vllm",
        stars=80000,
        open_prs=12,
        merged_prs=30,
        stale_prs=2,
        external_merged_prs=10,
        languages=("Python", "Cuda"),
        skills=("python", "llm"),
    )

    assert result.score >= 75
    assert result.recommendation == "Go"
    assert "external contributors are getting merged" in result.reasons


def test_fetch_radar_counts_open_issues_from_search_total_count() -> None:
    class FakeClient:
        def get_json(self, path: str, params: dict | None = None):
            if path == "/repos/owner/repo":
                return {"stargazers_count": 1000}
            if path == "/repos/owner/repo/languages":
                return {"Python": 100}
            if path == "/repos/owner/repo/pulls":
                return [
                    {
                        "state": "closed",
                        "merged_at": "2026-06-01T00:00:00Z",
                        "user": {"login": "contributor"},
                    }
                ]
            if path == "/search/issues":
                assert params == {"q": "repo:owner/repo is:issue is:open", "per_page": 1}
                return {"total_count": 42}
            raise AssertionError(f"Unexpected request: {path}")

    result = fetch_radar(FakeClient(), "owner/repo", skills=("python",))

    assert result.open_issues == 42
