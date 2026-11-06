#!/usr/bin/env python3
"""Check heading order in HTML and Markdown files, fail CI on a bad order.

Run: python3 src/heading_order_checker.py docs/
     python3 src/heading_order_checker.py page.html post.md

The tool reads HTML and Markdown files and checks two rules per file:

1. Exactly one H1 heading. A file with no H1, or with two or more,
   fails (unless you pass --allow-multiple-h1).
2. No skipped levels. A heading may not jump more than one level
   deeper than the heading before it: H1 followed by H3 is a fail,
   H2 followed by H4 is a fail, and a first heading that is not H1
   is a fail. Going back to a shallower level is always fine.

Every problem names the file and the exact line it is on. The tool
exits 1 when any file fails, so it can fail a CI run.

It is report-only: it never rewrites a file, and it runs fully
offline. It sends nothing anywhere and needs no API key.

HTML headings are found with the standard-library ``html.parser``;
Markdown headings are ATX headings (``#`` to ``######``) found by
plain-text matching. Setext headings (``Title`` underlined with
``===`` or ``---``) are not checked and are not counted — the tool
says so in the README rather than guessing at them.

Exit codes: 0 when every file passes, 1 when any file fails,
2 for a usage or input problem (missing file, bad flag, no files).
"""

import argparse
import contextlib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

VERSION = "1.0.0"

HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
MARKDOWN_EXTS = {".md", ".markdown"}
HTML_EXTS = {".html", ".htm"}

ATX_RE = re.compile(r"^(#{1,6})(?:[ \t]|$)")


class Heading:
    """One heading: its level (1-6) and the line it sits on."""

    def __init__(self, level, line):
        self.level = level
        self.line = line

    def __repr__(self):
        return "Heading(H%d, line %d)" % (self.level, self.line)


class _HtmlHeadingParser(HTMLParser):
    """Collect h1-h6 start tags with their line numbers.

    Tags inside comments, <script> and <style> blocks are not
    reported: HTMLParser treats those as data, not tags.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings = []

    def handle_starttag(self, tag, attrs):
        if tag in HEADING_TAGS:
            line, _ = self.getpos()
            self.headings.append(Heading(HEADING_TAGS[tag], line))


def extract_headings_html(text):
    """Return the list of headings in one HTML document."""
    parser = _HtmlHeadingParser()
    parser.feed(text)
    parser.close()
    return parser.headings


def extract_headings_markdown(text):
    """Return the list of ATX headings in one Markdown document.

    Fenced code blocks (``` or ~~~) are skipped, indented code
    (4 spaces or a tab) is skipped, and a leading frontmatter block
    (``---`` ... ``---``) is skipped, so a ``#`` inside any of those
    is never counted as a heading.
    """
    headings = []
    lines = text.splitlines()
    index = 0
    # Skip a leading frontmatter block, if the file starts with one.
    if lines and lines[0].strip() == "---":
        index = 1
        while index < len(lines) and lines[index].strip() != "---":
            index += 1
        index += 1
    fence = None
    while index < len(lines):
        raw = lines[index]
        line_no = index + 1
        index += 1
        # Indented code is not a heading.
        if raw.startswith("    ") or raw.startswith("\t"):
            continue
        stripped = raw.lstrip(" ")
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith("```"):
            fence = "```"
            continue
        if stripped.startswith("~~~"):
            fence = "~~~"
            continue
        match = ATX_RE.match(stripped)
        if match:
            headings.append(Heading(len(match.group(1)), line_no))
    return headings


def check_headings(headings, allow_multiple_h1=False):
    """Check one list of headings. Returns a list of problem strings."""
    if not headings:
        return ["no headings found (file has no H1)"]
    problems = []
    h1_lines = [h.line for h in headings if h.level == 1]
    if not h1_lines:
        problems.append("no H1 heading in file")
    elif len(h1_lines) > 1 and not allow_multiple_h1:
        for line in h1_lines[1:]:
            problems.append(
                "line %d: second H1 (first H1 at line %d)"
                % (line, h1_lines[0])
            )
    previous = 0
    for heading in headings:
        if heading.level > previous + 1:
            if previous == 0:
                problems.append(
                    "line %d: first heading is H%d, expected H1"
                    % (heading.line, heading.level)
                )
            else:
                problems.append(
                    "line %d: skipped level H%d -> H%d"
                    % (heading.line, previous, heading.level)
                )
        previous = heading.level
    return problems


def check_file(path, allow_multiple_h1=False):
    """Check one file. Returns a list of problem strings (empty = pass)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return ["cannot read file: %s" % exc]
    except UnicodeDecodeError:
        return ["file is not valid UTF-8 text"]
    suffix = path.suffix.lower()
    if suffix in HTML_EXTS:
        headings = extract_headings_html(text)
    elif suffix in MARKDOWN_EXTS:
        headings = extract_headings_markdown(text)
    else:
        return [
            "unknown file type (use .html, .htm, .md, or .markdown)"
        ]
    return check_headings(headings, allow_multiple_h1)


def collect_files(paths, recursive=True):
    """Expand paths into a sorted list of HTML/Markdown files.

    A path may be a file or a directory. Directories are scanned for
    ``.html``, ``.htm``, ``.md`` and ``.markdown`` files, recursively
    when ``recursive`` is true. Returns (files, problems) where
    problems are usage errors.
    """
    files = []
    problems = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            problems.append("no such file or directory: %s" % raw)
            continue
        if path.is_file():
            files.append(path)
            continue
        if recursive:
            found = []
            for ext in (".html", ".htm", ".md", ".markdown"):
                found.extend(path.rglob("*" + ext))
        else:
            found = []
            for ext in (".html", ".htm", ".md", ".markdown"):
                found.extend(path.glob("*" + ext))
        files.extend(sorted(set(found)))
    return files, problems


def build_parser():
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="heading_order_checker",
        description=(
            "Check heading order in HTML and Markdown files: exactly "
            "one H1 per file, no skipped levels. Prints PASS or FAIL "
            "per file and exits 1 when any file fails, so it can fail "
            "a CI run."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="HTML or Markdown file or directory to check. "
        "Directories are scanned for .html, .htm, .md and "
        ".markdown files.",
    )
    parser.add_argument(
        "--allow-multiple-h1",
        action="store_true",
        help="Allow more than one H1 per file. The skipped-level "
        "rule still applies. For pages that use several H1s on "
        "purpose.",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not look inside subdirectories of a named directory.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="heading_order_checker " + VERSION,
    )
    return parser


def run(argv=None, stdout=None, stderr=None):
    """Run the checker. Returns the exit code (0, 1, or 2)."""
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    try:
        # argparse writes --version output and usage errors to the real
        # sys.stdout/sys.stderr, so point those at the caller's streams.
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    files, problems = collect_files(args.paths, recursive=not args.no_recursive)
    if problems:
        for problem in problems:
            print("error: %s" % problem, file=err)
        return 2
    if not files:
        print("error: no HTML or Markdown files found", file=err)
        return 2
    passed = 0
    failed = 0
    for path in files:
        found = check_file(path, args.allow_multiple_h1)
        if found:
            failed += 1
            print("FAIL %s: %s" % (path, "; ".join(found)), file=out)
        else:
            passed += 1
            print("PASS %s" % path, file=out)
    print(
        "%d file(s) checked, %d passed, %d failed"
        % (passed + failed, passed, failed),
        file=out,
    )
    return 1 if failed else 0


def main():
    """Entry point for the command line."""
    sys.exit(run())


if __name__ == "__main__":
    main()
