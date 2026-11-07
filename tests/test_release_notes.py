"""Tests for `.github/scripts/release_notes.py`, which `release.yml` runs on each tag.

The script runs as the workflow runs it, a subprocess given a version and a
changelog path, so each test checks what the release would publish.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "release_notes.py"


def run(tmp_path: Path, changelog: str | None, version: str) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "CHANGELOG.md"
    if changelog is not None:
        path.write_text(textwrap.dedent(changelog), encoding="utf-8")
    return subprocess.run(  # noqa: S603 -- fixed interpreter and script, test-owned arguments
        [sys.executable, str(SCRIPT), version, str(path)],
        capture_output=True,
        text=True,
        check=True,
    )


def notes(tmp_path: Path, body: str, version: str = "1.2.0") -> str:
    changelog = f"# Changelog\n\n## [Unreleased]\n\n## [{version}] - 2026-11-07\n\n"
    changelog += textwrap.dedent(body) + "\n## [1.0.0] - 2026-01-01\n\n- Older.\n"
    return run(tmp_path, changelog, version).stdout


def test_wrapped_bullets_are_joined(tmp_path: Path) -> None:
    body = """\
        ### Fixed

        - A fix whose entry
          wraps over
          three lines.
        * Another, with *emphasis*
          kept as written.
        1. An ordered item that
           wraps.
        """
    assert notes(tmp_path, body) == (
        "### Fixed\n"
        "\n"
        "- A fix whose entry wraps over three lines.\n"
        "* Another, with *emphasis* kept as written.\n"
        "1. An ordered item that wraps.\n"
    )


def test_nested_list_items_stay_nested(tmp_path: Path) -> None:
    body = """\
        - Parent item that
          wraps.
          - Child item that
            wraps too.
            - Grandchild.
        """
    assert notes(tmp_path, body) == (
        "- Parent item that wraps.\n  - Child item that wraps too.\n    - Grandchild.\n"
    )


def test_wrapped_paragraph_is_joined(tmp_path: Path) -> None:
    body = """\
        A paragraph that is
        hard wrapped.

        A second paragraph.
        """
    assert notes(tmp_path, body) == "A paragraph that is hard wrapped.\n\nA second paragraph.\n"


def test_second_paragraph_of_a_list_item_is_joined(tmp_path: Path) -> None:
    body = """\
        - First paragraph.

          Second paragraph that
          wraps.
        """
    assert notes(tmp_path, body) == "- First paragraph.\n\n  Second paragraph that wraps.\n"


def test_code_fence_holding_a_heading_is_kept_whole(tmp_path: Path) -> None:
    body = """\
        - Run:

          ```console
          $ tool
          ## not a heading
          [x]: not a link definition
          ```
        - After the fence, still
          in the section.

        ~~~~
        ```
        ## inside a longer fence
        ~~~~
        """
    assert notes(tmp_path, body) == (
        "- Run:\n"
        "\n"
        "  ```console\n"
        "  $ tool\n"
        "  ## not a heading\n"
        "  [x]: not a link definition\n"
        "  ```\n"
        "- After the fence, still in the section.\n"
        "\n"
        "~~~~\n"
        "```\n"
        "## inside a longer fence\n"
        "~~~~\n"
    )


def test_fence_closes_only_on_its_own_marker(tmp_path: Path) -> None:
    body = """\
        ```
        ```js
        ## still code
        ```
        """
    assert notes(tmp_path, body) == "```\n```js\n## still code\n```\n"


def test_fence_closes_only_on_a_run_as_long(tmp_path: Path) -> None:
    body = "````\n```\n## still code\n````\n"
    assert notes(tmp_path, body) == body


def test_backticks_with_a_backtick_after_them_open_no_fence(tmp_path: Path) -> None:
    body = "```not `a fence`\n"
    assert notes(tmp_path, body) == body


def test_table_rows_are_not_joined(tmp_path: Path) -> None:
    body = """\
        | Setting | Default |
        |---|---|
        | a | b |

        Name | Value
        --- | ---
        c | d
        e | f
        """
    assert notes(tmp_path, body) == (
        "| Setting | Default |\n|---|---|\n| a | b |\n\nName | Value\n--- | ---\nc | d\ne | f\n"
    )


def test_hard_breaks_are_kept(tmp_path: Path) -> None:
    body = "Two spaces end this line  \nso it breaks, and this one\\\nbreaks too, but this\nline joins.\n"
    assert notes(tmp_path, body) == (
        "Two spaces end this line  \nso it breaks, and this one\\\nbreaks too, but this line joins.\n"
    )


def test_block_starts_are_not_joined(tmp_path: Path) -> None:
    body = """\
        A paragraph
        > a quote
        > continued
        <details>
        <summary>More</summary>
        </details>
        #### A heading
        Text under it
        that wraps.
        ---
        """
    assert notes(tmp_path, body) == (
        "A paragraph\n"
        "> a quote\n"
        "> continued\n"
        "<details>\n"
        "<summary>More</summary>\n"
        "</details>\n"
        "#### A heading\n"
        "Text under it that wraps.\n"
        "---\n"
    )


def test_indented_code_block_is_not_joined(tmp_path: Path) -> None:
    body = "Example:\n\n    first line\n    second line\n\n    after a blank\n\nText.\n"
    assert notes(tmp_path, body) == body


def test_link_definitions_are_dropped_and_footnotes_kept(tmp_path: Path) -> None:
    changelog = """\
        ## [1.0.0] - 2026-01-01

        - First release.[^1]

        [^1]: A footnote.

        [Unreleased]: https://example.com/compare/v1.0.0...HEAD
        [1.0.0]: https://example.com/releases/tag/v1.0.0
        """
    assert run(tmp_path, changelog, "1.0.0").stdout == (
        "- First release.[^1]\n\n[^1]: A footnote.\n"
    )


@pytest.mark.parametrize("version", ["1.2.0-rc.1", "1.2.0rc1", "1.2.0"])
def test_tag_matches_only_its_own_heading(tmp_path: Path, version: str) -> None:
    changelog = """\
        ## [1.2.0-rc.1]

        - From 1.2.0-rc.1.

        ## [1.2.0rc1]

        - From 1.2.0rc1.

        ## [1.2.0.1]

        - From 1.2.0.1.

        ## [1.2.0] - 2026-11-07

        - From 1.2.0.
        """
    assert run(tmp_path, changelog, version).stdout == f"- From {version}.\n"


@pytest.mark.parametrize(
    ("changelog", "reason"),
    [
        pytest.param(None, "No ", id="no changelog"),
        pytest.param("## [1.1.0]\n\n- Other.\n", "has nothing under '## [1.2.0]'", id="no section"),
        pytest.param("## [1.2.0]\n\n## [1.1.0]\n\n- Other.\n", "has nothing", id="empty section"),
        pytest.param(
            "## [1.2.0]\n\n<!-- Add entries here. -->\n<!--\nmulti-line\n-->\n",
            "has nothing",
            id="comments only",
        ),
    ],
)
def test_no_notes_prints_nothing_and_says_why(
    tmp_path: Path, changelog: str | None, reason: str
) -> None:
    result = run(tmp_path, changelog, "1.2.0")
    assert result.stdout == ""
    assert reason in result.stderr


def test_only_whitespace_changes(tmp_path: Path) -> None:
    body = """\
        ### Changed

        - Breaking: the `--foo` flag is renamed `--bar`; replace `--foo` in your
          scripts before upgrading. See [the docs](https://example.com/a_b*c)
          and **bold** text.
          - Nested *emphasis*
            that wraps.
        """
    assert notes(tmp_path, body).split() == textwrap.dedent(body).split()
