"""JAR-687 — the `claude` job in `.github/workflows/claude.yml` triggers on
`issue_comment`, `pull_request_review_comment`, `issues` and
`pull_request_review`. `author_association` gates the trigger, but that field
cannot tell a human org member from a machine account in the same org — every
agent workforce account is `MEMBER` (JAR-681). The run must not hold write
capability regardless of who or what passes the gate, and must not skip
permission checks.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "claude.yml"


def _job_text() -> str:
    text = WORKFLOW.read_text()
    # One job in this file — slice from its own `permissions:` block onward so
    # the repo-level `permissions: {}` line above it isn't what gets read below.
    return text[text.index("runs-on:") :]


def test_untrusted_trigger_mints_no_write_scope() -> None:
    job = _job_text()
    for scope in ("contents", "issues", "pull-requests"):
        assert f"\n      {scope}: write" not in job, (
            f"job permissions grants {scope}: write to a run triggered by "
            "issue/comment/review content — JAR-687"
        )
    for scope in ("permission-contents", "permission-issues", "permission-pull-requests"):
        assert f"{scope}: write" not in job, (
            f"App token is minted with {scope}: write on an untrusted-authorable trigger — JAR-687"
        )
        assert f"{scope}: read" in job, (
            f"App token must set {scope}: read explicitly rather than inherit "
            "the App installation's grant — JAR-687"
        )


def test_permission_checks_are_not_skipped() -> None:
    job = _job_text()
    assert "--dangerously-skip-permissions" not in job, (
        "a run triggered by issue/comment/review content must not skip permission checks — JAR-687"
    )
