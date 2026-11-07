"""Print one version's release notes from a Keep a Changelog file.

`release.yml` runs this for each `v*` tag. The notes are the body of the
version's `## [X.Y.Z]` section, kept as written except that hard-wrapped lines
are joined: GitHub renders every newline in a release body as a line break.
Link reference definitions are dropped, since Keep a Changelog puts its compare
links at the end of the file, inside the oldest section.

When there are no notes (no changelog file, no section for the version, or a
section that is empty or holds only HTML comments), nothing is printed on
stdout and the reason goes to stderr; the workflow then falls back to
generated notes.

Usage: ``release_notes.py VERSION [CHANGELOG]``. Standard library only, so the
release job needs nothing but the runner's ``python3``.
"""

import re
import sys
from collections.abc import Iterable, Iterator
from itertools import pairwise
from pathlib import Path

# A fence may sit inside a list item, so any indent opens one. A backtick
# fence's info string can't contain a backtick (CommonMark).
_FENCE = re.compile(r"\s*(`{3,}|~{3,})(.*)")
_ATX_HEADING = re.compile(r" {0,3}#{1,6}(\s|$)")
_LINK_DEFINITION = re.compile(r" {0,3}\[[^\]^][^\]]*\]:")
# Lines that start a block of their own, so they are never joined onto the line
# above: list items, headings, quotes, table rows, HTML, link and footnote
# definitions, and thematic breaks or setext underlines.
_BLOCK_START = re.compile(
    r"""\s*(
        ([-*+]|\d{1,9}[.)])(\s|$)
      | \#{1,6}(\s|$)
      | >
      | \|
      | <
      | \[[^\]]+\]:
      | ([-*_=]\s*){3,}$
      | [-=]+\s*$
    )""",
    re.VERBOSE,
)
_LIST_ITEM_WITH_TEXT = re.compile(r"\s*([-*+]|\d{1,9}[.)])\s+\S")
# A GFM table's delimiter row, such as `| --- | :-: |`.
_TABLE_DELIMITER = re.compile(r"[\s|:-]*-[\s|:-]*")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# A line indented this far after a blank line or a heading starts an indented
# code block.
_CODE_INDENT = 4


def section(changelog: str, version: str) -> list[str]:
    """Return the lines of ``version``'s section, without its heading.

    The section runs to the next ``## `` heading outside a code block. Link
    reference definitions outside code are dropped; footnote definitions stay.

    Args:
        changelog: The changelog's text.
        version: The version as its heading writes it, such as ``1.2.0``.

    Returns:
        The section's lines, or an empty list when no heading starts with
        ``## [<version>]``.
    """
    heading = f"## [{version}]"
    lines: list[str] = []
    in_section = False
    for line, in_code in _with_code_state(changelog.splitlines()):
        if not in_code and line.startswith("## "):
            in_section = line.startswith(heading)
            continue
        if in_section and (in_code or not _LINK_DEFINITION.match(line)):
            lines.append(line)
    return lines


def _with_code_state(lines: Iterable[str]) -> Iterator[tuple[str, bool]]:
    """Yield each line with whether it is code: a fence, its contents or an indented code block.

    An indented code block is taken to be any run of lines indented four or more
    columns that follows a blank line or a heading, a tab reaching the next
    multiple of four as in CommonMark. A fence marker inside one is code, so it
    opens no fence.
    """
    fence: tuple[str, int] | None = None
    code_may_start = True
    for line in lines:
        expanded = line.expandtabs(4)
        indent = len(expanded) - len(expanded.lstrip(" "))
        if not line.strip():
            in_code = fence is not None
            code_may_start = True
        elif fence is None and code_may_start and indent >= _CODE_INDENT:
            in_code = True
        else:
            opened = fence
            fence = _next_fence_state(line, fence)
            in_code = opened is not None or fence is not None
            code_may_start = not in_code and bool(_ATX_HEADING.match(line))
        yield line, in_code


def _next_fence_state(line: str, fence: tuple[str, int] | None) -> tuple[str, int] | None:
    """Return the fence open after ``line``, as (character, length), or None."""
    match = _FENCE.match(line)
    if match is None:
        return fence
    marks, rest = match.groups()
    if fence is None:
        if marks[0] == "`" and "`" in rest:
            return None
        return marks[0], len(marks)
    char, length = fence
    if marks[0] == char and len(marks) >= length and not rest.strip():
        return None
    return fence


def join_wrapped_lines(lines: list[str]) -> list[str]:
    r"""Join each line that continues a paragraph or list item onto the one above.

    A line is never joined inside a code block or a table, after a blank line,
    after a hard break (two trailing spaces or a ``\``), or when it starts a
    block of its own, a table's header row included.

    Args:
        lines: Markdown lines.

    Returns:
        The lines with continuations joined, each joined pair separated by one
        space.
    """
    out: list[str] = []
    joinable = in_table = False
    # A table starts at its header row, which can interrupt a paragraph, so it is
    # known only from the delimiter row after it.
    classified = [*_with_code_state(lines), ("", False)]
    for (line, in_code), (next_line, _) in pairwise(classified):
        if in_code or not line.strip():
            joinable = in_table = False
        elif in_table or (
            "|" in line and "|" in next_line and _TABLE_DELIMITER.fullmatch(next_line)
        ):
            in_table = True
        elif _BLOCK_START.match(line):
            joinable = bool(_LIST_ITEM_WITH_TEXT.match(line))
        elif joinable and not out[-1].endswith(("  ", "\\")):
            out[-1] = f"{out[-1].rstrip()} {line.lstrip()}"
            continue
        else:
            joinable = True
        out.append(line)
    return out


def release_notes(changelog: str, version: str) -> str:
    """Return ``version``'s release notes, or an empty string when it has none.

    Args:
        changelog: The changelog's text.
        version: The version as its heading writes it, such as ``1.2.0``.

    Returns:
        The section with its wrapped lines joined and its surrounding blank
        lines removed, ending in a newline; empty when the section is missing,
        empty or holds only HTML comments.
    """
    notes = "\n".join(join_wrapped_lines(section(changelog, version))).strip("\n")
    if not _HTML_COMMENT.sub("", notes).strip():
        return ""
    return notes + "\n"


def main(argv: list[str]) -> int:
    """Print the notes for ``argv[0]`` from the changelog at ``argv[1]``.

    Args:
        argv: The version, then optionally the changelog path (default
            ``CHANGELOG.md``).

    Returns:
        The exit status: 0, also when there are no notes; 2 for bad arguments.
    """
    match argv:
        case [version]:
            path = Path("CHANGELOG.md")
        case [version, changelog]:
            path = Path(changelog)
        case _:
            sys.stderr.write("usage: release_notes.py VERSION [CHANGELOG]\n")
            return 2
    if not path.is_file():
        sys.stderr.write(f"No {path}\n")
        return 0
    notes = release_notes(path.read_text(encoding="utf-8"), version)
    if not notes:
        sys.stderr.write(f"{path} has nothing under '## [{version}]'\n")
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
