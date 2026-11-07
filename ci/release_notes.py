"""Print one version's release notes from a Keep a Changelog file.

`release.yml` runs this for each `v*` tag. The notes are the body of the
version's `## [X.Y.Z]` section, kept as written except that hard-wrapped lines
are joined: GitHub renders every newline in a release body as a line break.
Link reference definitions sit at the end of the file in Keep a Changelog, so
they are taken out of the section, and the ones the notes use, wherever they
sit outside code, are appended to the notes.

When there are no notes (no changelog file, no section for the version, or a
section that is empty or holds only HTML comments), nothing is printed on
stdout and the reason goes to stderr; the workflow then falls back to
generated notes.

Usage: ``release_notes.py VERSION [CHANGELOG]``, or
``release_notes.py --prerelease VERSION`` to print ``true`` or ``false``.
Standard library only, so the notes job needs nothing but the runner's
``python3``.
"""

import re
import sys
from collections.abc import Iterable, Iterator
from itertools import pairwise
from pathlib import Path

from versions import is_prerelease

# A fence may sit inside a list item, so it opens at any indent outside an
# indented code block. A backtick fence's info string can't contain a backtick
# (CommonMark).
_FENCE = re.compile(r"\s*(`{3,}|~{3,})(.*)")
_ATX_HEADING = re.compile(r" {0,3}#{1,6}(\s|$)")
# A link reference definition, not a footnote one (`[^1]:`), which stays in place.
_LINK_DEFINITION = re.compile(r" {0,3}\[([^\]^][^\]]*)\]:")
# Bracketed text that may be a reference: `[x]`, and both parts of `[text][x]`
# and `[x][]`. Appending a definition nothing uses is harmless: it renders as
# nothing.
_BRACKETED = re.compile(r"\[([^\[\]]+)\]")
# Lines that start a block of their own, so they are never joined onto the line
# above: list items, headings, quotes, table rows, link and footnote
# definitions, and thematic breaks or setext underlines. A link definition
# can't interrupt a paragraph (CommonMark), so after paragraph text it is text;
# a footnote definition can (GitHub).
_BLOCK_START = re.compile(
    r"""\s*(
        ([-*+]|\d{1,9}[.)])(\s|$)
      | \#{1,6}(\s|$)
      | >
      | \|
      | \[[^\]]+\]:
      | ([-*_=]\s*){3,}$
      | [-=]+\s*$
    )""",
    re.VERBOSE,
)
_LIST_ITEM_WITH_TEXT = re.compile(r"\s*([-*+]|\d{1,9}[.)])\s+\S")
# `* * *` and `- - -` also match a list item, but a thematic break wins.
_THEMATIC_BREAK = re.compile(r"\s*([-*_])(\s*\1){2,}\s*$")
# A line starting with `<` and a letter, `/`, `!` or `?` opens an HTML block,
# kept as written to the next blank line. That is wider than CommonMark's rule,
# so a paragraph line that starts with an inline tag stays unjoined, but nothing
# inside HTML is joined. A line starting with an autolink is text.
_HTML_START = re.compile(r"\s*<[A-Za-z/!?]")
_AUTOLINK = re.compile(r"\s*<([A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*|[^\s<>@]+@[^\s<>]+)>")
# These blocks run to their closing tag, blank lines included.
_RAW_HTML_START = re.compile(r"\s*<(pre|script|style|textarea)(\s|>|$)", re.IGNORECASE)
_RAW_HTML_END = re.compile(r"</(pre|script|style|textarea)>", re.IGNORECASE)
_BLANK = re.compile(r"^\s*$")
# A GFM table's delimiter row, such as `| --- | :-: |`.
_TABLE_DELIMITER = re.compile(r"[\s|:-]*-[\s|:-]*")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_CODE_INDENT = 4


def section(changelog: str, version: str) -> list[str]:
    """Return the lines of ``version``'s section, without its heading.

    The section runs to the next ``## `` heading outside a code block. Link
    reference definitions are dropped; footnote definitions stay.

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
    for line, in_code, definition in _with_definitions(changelog.splitlines()):
        if not in_code and line.startswith("## "):
            in_section = line.startswith(heading)
            continue
        if in_section and not definition:
            lines.append(line)
    return lines


def _with_definitions(lines: Iterable[str]) -> Iterator[tuple[str, bool, re.Match[str] | None]]:
    """Yield each line with whether it is code and, if it is a link reference definition, its match.

    A definition can't interrupt a paragraph (CommonMark), so a ``[label]:`` line
    counts as one only first, or after a blank line, code, a heading or another
    definition. Elsewhere it may be a wrapped line of text, and dropping it would
    lose that text.
    """
    may_define = True
    for line, in_code in _with_code_state(lines):
        definition = _LINK_DEFINITION.match(line) if may_define and not in_code else None
        may_define = (
            in_code or definition is not None or not line.strip() or bool(_ATX_HEADING.match(line))
        )
        yield line, in_code, definition


def _with_code_state(lines: Iterable[str]) -> Iterator[tuple[str, bool]]:
    """Yield each line with whether it is code: a fence, its contents or an indented code block.

    An indented code block is taken to be any run of lines indented four or more
    columns (a tab reaching the next multiple of four, as in CommonMark) that
    follows a blank line, a heading, a thematic break or a closing fence. A
    fence marker inside one is code, so it opens no fence.
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
            closed_fence = opened is not None and fence is None
            code_may_start = closed_fence or (
                not in_code and bool(_ATX_HEADING.match(line) or _THEMATIC_BREAK.match(line))
            )
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

    A line is never joined inside a code block, an HTML block or a table, after
    a blank line, after a hard break (two trailing spaces or a ``\``), or when
    it starts a block of its own, a table's header row included. A quote's lines
    are never joined either, so a wrapped quote keeps its line breaks.

    Args:
        lines: Markdown lines.

    Returns:
        The lines with continuations joined, each joined pair separated by one
        space.
    """
    out: list[str] = []
    joinable = in_table = False
    html_end: re.Pattern[str] | None = None
    # A table starts at its header row, which can interrupt a paragraph, so it is
    # known only from the delimiter row after it.
    classified = [*_with_code_state(lines), ("", False)]
    for (line, in_code), (next_line, _) in pairwise(classified):
        if (
            html_end is None
            and not in_code
            and _HTML_START.match(line)
            and not _AUTOLINK.match(line)
        ):
            html_end = _RAW_HTML_END if _RAW_HTML_START.match(line) else _BLANK
        if html_end is not None:
            if html_end.search(line):
                html_end = None
            joinable = in_table = False
        elif in_code or not line.strip():
            joinable = in_table = False
        elif in_table or (
            "|" in line and "|" in next_line and _TABLE_DELIMITER.fullmatch(next_line)
        ):
            in_table = True
        elif _BLOCK_START.match(line) and not (joinable and _LINK_DEFINITION.match(line)):
            joinable = bool(_LIST_ITEM_WITH_TEXT.match(line)) and not _THEMATIC_BREAK.match(line)
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
        The section with its wrapped lines joined, its surrounding blank lines
        removed and the link reference definitions it uses appended, ending in
        a newline; empty when the section is missing, empty or holds only HTML
        comments.
    """
    notes = "\n".join(join_wrapped_lines(section(changelog, version))).strip("\n")
    if not _HTML_COMMENT.sub("", notes).strip():
        return ""
    definitions = _used_definitions(changelog, notes)
    if definitions:
        notes += "\n\n" + "\n".join(definitions)
    return notes + "\n"


def _used_definitions(changelog: str, notes: str) -> list[str]:
    """Return the changelog's link reference definitions that ``notes`` may use.

    Labels match as CommonMark matches them, ignoring case and runs of
    whitespace, and the first definition of a label wins. They come back in file
    order.
    """
    used = {
        _label(text)
        for line, in_code in _with_code_state(notes.splitlines())
        if not in_code
        for text in _BRACKETED.findall(line)
    }
    definitions: dict[str, str] = {}
    for line, _, match in _with_definitions(changelog.splitlines()):
        if match and _label(match[1]) in used:
            definitions.setdefault(_label(match[1]), line)
    return list(definitions.values())


def _label(text: str) -> str:
    return " ".join(text.split()).casefold()


def main(argv: list[str]) -> int:
    """Print the notes for a version, or whether it is a pre-release.

    Args:
        argv: The version, then optionally the changelog path (default
            ``CHANGELOG.md``); or ``--prerelease`` and the version.

    Returns:
        The exit status: 0, also when there are no notes; 2 for bad arguments.
    """
    match argv:
        case ["--prerelease", version]:
            sys.stdout.write("true\n" if is_prerelease(version) else "false\n")
            return 0
        case [version] if not version.startswith("-"):
            path = Path("CHANGELOG.md")
        case [version, changelog] if not version.startswith("-"):
            path = Path(changelog)
        case _:
            sys.stderr.write(
                "usage: release_notes.py VERSION [CHANGELOG]\n"
                "       release_notes.py --prerelease VERSION\n"
            )
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
