#!/usr/bin/env python3
"""Tests for heading_order_checker.

Standard library only — no third-party imports anywhere in this repo
(the Day 11 lesson: a test that imports yaml passes locally but fails
on a clean GitHub Actions runner).
"""

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from heading_order_checker import (  # noqa: E402
    Heading,
    check_file,
    check_headings,
    collect_files,
    extract_headings_html,
    extract_headings_markdown,
    run,
)

EXAMPLES = ROOT / "examples"


def levels(headings):
    """Just the levels, in order — handy for extraction tests."""
    return [h.level for h in headings]


def lines(headings):
    """Just the line numbers, in order."""
    return [h.line for h in headings]


class TestExtractHtml(unittest.TestCase):
    def test_levels_and_lines(self):
        text = (
            "<html><body>\n"
            "<h1>Title</h1>\n"
            "<p>text</p>\n"
            "<h2>One</h2>\n"
            "<h3>Deep</h3>\n"
            "<h2>Two</h2>\n"
            "</body></html>\n"
        )
        found = extract_headings_html(text)
        self.assertEqual(levels(found), [1, 2, 3, 2])
        self.assertEqual(lines(found), [2, 4, 5, 6])

    def test_uppercase_tags_and_attributes(self):
        text = '<H1 CLASS="big">Title</H1>\n<H2 id="a">One</H2>\n'
        self.assertEqual(levels(extract_headings_html(text)), [1, 2])

    def test_heading_inside_comment_is_ignored(self):
        text = "<!-- <h1>Not real</h1> -->\n<h1>Real</h1>\n"
        found = extract_headings_html(text)
        self.assertEqual(levels(found), [1])
        self.assertEqual(lines(found), [2])

    def test_heading_inside_script_is_ignored(self):
        text = (
            "<script>var s = '<h1>Not real</h1>';</script>\n"
            "<h1>Real</h1>\n"
        )
        found = extract_headings_html(text)
        self.assertEqual(levels(found), [1])
        self.assertEqual(lines(found), [2])

    def test_heading_inside_style_is_ignored(self):
        text = "<style>h1 { color: red; }</style>\n<h2>Real</h2>\n"
        found = extract_headings_html(text)
        self.assertEqual(levels(found), [2])

    def test_unclosed_heading_still_counts(self):
        # HTMLParser reports the start tag even if </h1> never comes.
        text = "<h1>Title\n<p>text</p>\n"
        found = extract_headings_html(text)
        self.assertEqual(levels(found), [1])

    def test_no_headings(self):
        self.assertEqual(extract_headings_html("<p>plain</p>\n"), [])

    def test_all_six_levels(self):
        text = "".join("<h%d>x</h%d>\n" % (n, n) for n in range(1, 7))
        self.assertEqual(levels(extract_headings_html(text)), [1, 2, 3, 4, 5, 6])


class TestExtractMarkdown(unittest.TestCase):
    def test_atx_levels_and_lines(self):
        text = "# Title\n\n## One\n\n### Deep\n\n## Two\n"
        found = extract_headings_markdown(text)
        self.assertEqual(levels(found), [1, 2, 3, 2])
        self.assertEqual(lines(found), [1, 3, 5, 7])

    def test_closing_hashes_are_ok(self):
        text = "## Title ##\n# Top #\n"
        self.assertEqual(levels(extract_headings_markdown(text)), [2, 1])

    def test_hash_without_space_is_not_a_heading(self):
        text = "#nospace\n# Real\n"
        found = extract_headings_markdown(text)
        self.assertEqual(levels(found), [1])
        self.assertEqual(lines(found), [2])

    def test_seven_hashes_is_not_a_heading(self):
        text = "####### Too many\n# Real\n"
        found = extract_headings_markdown(text)
        self.assertEqual(levels(found), [1])

    def test_up_to_three_leading_spaces_ok(self):
        text = "  ## Indented\n   ### More\n"
        self.assertEqual(levels(extract_headings_markdown(text)), [2, 3])

    def test_four_space_indent_is_code_not_heading(self):
        text = "    # Not a heading\n# Real\n"
        found = extract_headings_markdown(text)
        self.assertEqual(levels(found), [1])

    def test_fenced_code_block_ignored(self):
        text = (
            "# Real\n\n```md\n# Not a heading\n## Neither\n```\n\n"
            "## Also real\n"
        )
        found = extract_headings_markdown(text)
        self.assertEqual(levels(found), [1, 2])
        self.assertEqual(lines(found), [1, 8])

    def test_tilde_fence_ignored(self):
        text = "# Real\n\n~~~\n# Not a heading\n~~~\n\n## Also real\n"
        found = extract_headings_markdown(text)
        self.assertEqual(levels(found), [1, 2])

    def test_frontmatter_block_skipped(self):
        text = (
            "---\n"
            "title: My post\n"
            "# a comment line, not a heading\n"
            "---\n"
            "# Real title\n"
        )
        found = extract_headings_markdown(text)
        self.assertEqual(levels(found), [1])
        self.assertEqual(lines(found), [5])

    def test_setext_headings_not_counted(self):
        # Setext (underlined) headings are outside the supported
        # subset: they are not counted, and the tool says so.
        text = "Title\n===\n\nSubtitle\n---\n"
        self.assertEqual(extract_headings_markdown(text), [])

    def test_empty_document(self):
        self.assertEqual(extract_headings_markdown(""), [])
        self.assertEqual(extract_headings_markdown("\n\n"), [])


class TestCheckRules(unittest.TestCase):
    def h(self, level, line):
        return Heading(level, line)

    def test_valid_sequence_passes(self):
        headings = [self.h(1, 1), self.h(2, 3), self.h(3, 5),
                    self.h(2, 7), self.h(3, 9), self.h(4, 11)]
        self.assertEqual(check_headings(headings), [])

    def test_single_h1_only_passes(self):
        self.assertEqual(check_headings([self.h(1, 1)]), [])

    def test_no_headings(self):
        self.assertEqual(
            check_headings([]),
            ["no headings found (file has no H1)"],
        )

    def test_no_h1(self):
        found = check_headings([self.h(2, 1), self.h(3, 3)])
        self.assertIn("no H1 heading in file", found)

    def test_two_h1s(self):
        found = check_headings([self.h(1, 1), self.h(2, 3), self.h(1, 5)])
        self.assertIn("line 5: second H1 (first H1 at line 1)", found)
        self.assertEqual(len(found), 1)

    def test_three_h1s_reports_each_extra(self):
        found = check_headings(
            [self.h(1, 1), self.h(1, 4), self.h(1, 8)]
        )
        self.assertEqual(len(found), 2)
        self.assertIn("line 4: second H1 (first H1 at line 1)", found)
        self.assertIn("line 8: second H1 (first H1 at line 1)", found)

    def test_allow_multiple_h1(self):
        found = check_headings(
            [self.h(1, 1), self.h(2, 3), self.h(1, 5)],
            allow_multiple_h1=True,
        )
        self.assertEqual(found, [])

    def test_skipped_level_h1_to_h3(self):
        found = check_headings([self.h(1, 1), self.h(3, 4)])
        self.assertIn("line 4: skipped level H1 -> H3", found)

    def test_skipped_level_h2_to_h4(self):
        found = check_headings([self.h(1, 1), self.h(2, 2), self.h(4, 5)])
        self.assertIn("line 5: skipped level H2 -> H4", found)

    def test_first_heading_h2(self):
        found = check_headings([self.h(2, 1), self.h(3, 3)])
        self.assertIn("no H1 heading in file", found)
        self.assertIn("line 1: first heading is H2, expected H1", found)

    def test_first_heading_h3(self):
        found = check_headings([self.h(3, 1)])
        self.assertIn("line 1: first heading is H3, expected H1", found)

    def test_going_shallower_is_fine(self):
        headings = [self.h(1, 1), self.h(3, 2), self.h(2, 3)]
        found = check_headings(headings)
        # Only the H1 -> H3 skip is a problem; H3 -> H2 is fine.
        self.assertEqual(found, ["line 2: skipped level H1 -> H3"])

    def test_h1_after_skip_still_reports_both(self):
        found = check_headings([self.h(1, 1), self.h(3, 2), self.h(1, 4)])
        self.assertEqual(len(found), 2)


class TestCheckFile(unittest.TestCase):
    def write(self, directory, name, text):
        path = Path(directory) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_good_html_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(
                tmp, "page.html",
                "<h1>T</h1>\n<h2>A</h2>\n<h3>B</h3>\n",
            )
            self.assertEqual(check_file(path), [])

    def test_good_markdown_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "post.md", "# T\n\n## A\n\n### B\n")
            self.assertEqual(check_file(path), [])

    def test_bad_html_reports_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "page.html", "<h1>T</h1>\n<h3>B</h3>\n")
            found = check_file(path)
            self.assertEqual(found, ["line 2: skipped level H1 -> H3"])

    def test_unknown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, "notes.txt", "# T\n")
            found = check_file(path)
            self.assertEqual(
                found,
                ["unknown file type (use .html, .htm, .md, or .markdown)"],
            )

    def test_missing_file(self):
        found = check_file(Path("/nonexistent-xyz/page.html"))
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("cannot read file:"))

    def test_not_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.html"
            path.write_bytes(b"<h1>\xff\xfe</h1>\n")
            found = check_file(path)
            self.assertEqual(found, ["file is not valid UTF-8 text"])

    def test_bom_is_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "post.md"
            path.write_bytes(b"\xef\xbb\xbf# Title\n")
            self.assertEqual(check_file(path), [])


class TestCollectFiles(unittest.TestCase):
    def test_directory_scan_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.html").write_text("<h1>A</h1>\n")
            (root / "b.md").write_text("# B\n")
            (root / "c.txt").write_text("plain\n")
            sub = root / "sub"
            sub.mkdir()
            (sub / "d.htm").write_text("<h1>D</h1>\n")
            (sub / "e.markdown").write_text("# E\n")
            files, problems = collect_files([str(root)])
            self.assertEqual(problems, [])
            self.assertEqual(
                [p.name for p in files],
                ["a.html", "b.md", "d.htm", "e.markdown"],
            )

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.html").write_text("<h1>A</h1>\n")
            sub = root / "sub"
            sub.mkdir()
            (sub / "d.html").write_text("<h1>D</h1>\n")
            files, problems = collect_files([str(root)], recursive=False)
            self.assertEqual(problems, [])
            self.assertEqual([p.name for p in files], ["a.html"])

    def test_missing_path(self):
        files, problems = collect_files(["/nonexistent-xyz"])
        self.assertEqual(files, [])
        self.assertEqual(problems, ["no such file or directory: /nonexistent-xyz"])

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.html"
            path.write_text("<h1>A</h1>\n")
            files, problems = collect_files([str(path)])
            self.assertEqual(problems, [])
            self.assertEqual(files, [path])


class TestCli(unittest.TestCase):
    def run_cli(self, argv):
        out = io.StringIO()
        err = io.StringIO()
        code = run(argv, stdout=out, stderr=err)
        return code, out.getvalue(), err.getvalue()

    def test_pass_exit_0(self):
        code, out, err = self.run_cli(
            [str(EXAMPLES / "good.html"), str(EXAMPLES / "good.md")]
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            out,
            "PASS %s\nPASS %s\n2 file(s) checked, 2 passed, 0 failed\n"
            % (EXAMPLES / "good.html", EXAMPLES / "good.md"),
        )
        self.assertEqual(err, "")

    def test_fail_exit_1(self):
        code, out, err = self.run_cli(
            [str(EXAMPLES / "skipped-level.html")]
        )
        self.assertEqual(code, 1)
        self.assertIn(
            "FAIL %s: line 8: skipped level H1 -> H3"
            % (EXAMPLES / "skipped-level.html"),
            out,
        )
        self.assertIn("1 file(s) checked, 0 passed, 1 failed", out)

    def test_directory_check(self):
        code, out, err = self.run_cli([str(EXAMPLES)])
        self.assertEqual(code, 1)
        self.assertIn("5 file(s) checked, 2 passed, 3 failed", out)

    def test_missing_path_exit_2(self):
        code, out, err = self.run_cli(["/nonexistent-xyz"])
        self.assertEqual(code, 2)
        self.assertIn("error: no such file or directory", err)

    def test_empty_directory_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = self.run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("error: no HTML or Markdown files found", err)

    def test_allow_multiple_h1_flag(self):
        code, out, err = self.run_cli(
            ["--allow-multiple-h1", str(EXAMPLES / "two-h1.md")]
        )
        self.assertEqual(code, 0)
        self.assertIn("PASS %s" % (EXAMPLES / "two-h1.md"), out)

    def test_version(self):
        code, out, err = self.run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("heading_order_checker 1.0.0", out)

    def test_bad_flag_exit_2(self):
        code, out, err = self.run_cli(["--nope", str(EXAMPLES / "good.md")])
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments: --nope", err)

    def test_files_are_not_changed(self):
        # Report-only: running the checker must not touch any file.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.html"
            path.write_text("<h1>T</h1>\n<h3>Skip</h3>\n")
            before = path.read_bytes()
            code, _, _ = self.run_cli([str(path)])
            self.assertEqual(code, 1)
            self.assertEqual(path.read_bytes(), before)

    def test_example_output_matches_sample(self):
        # The committed sample-output.txt must match a fresh run.
        # Run from the repo root with relative paths, so the output
        # matches the committed file word for word.
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(ROOT)
            code, out, _ = self.run_cli(
                [
                    "examples/good.html",
                    "examples/good.md",
                    "examples/skipped-level.html",
                    "examples/two-h1.md",
                    "examples/no-h1.html",
                ]
            )
        finally:
            os.chdir(old_cwd)
        self.assertEqual(code, 1)
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertEqual(out, saved)

    def test_run_example_script(self):
        result = subprocess.run(
            ["sh", str(EXAMPLES / "run-example.sh")],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertEqual(result.stdout, saved)


class TestRepoHygiene(unittest.TestCase):
    def test_stdlib_only_imports(self):
        allowed = {
            "argparse", "contextlib", "re", "sys", "html",
            "pathlib", "io", "subprocess", "tempfile", "unittest",
        }
        for path in list(SRC.rglob("*.py")) + list(
            (ROOT / "tests").rglob("*.py")
        ):
            for line in path.read_text().splitlines():
                if line.startswith("import "):
                    for name in line[7:].split(","):
                        top = name.strip().split(".")[0].split(" ")[0]
                        self.assertIn(
                            top,
                            allowed | {"heading_order_checker"},
                            "%s in %s" % (top, path),
                        )
                elif line.startswith("from "):
                    top = line.split()[1].split(".")[0]
                    self.assertIn(
                        top,
                        allowed | {"heading_order_checker"},
                        "%s in %s" % (top, path),
                    )

    def test_no_placeholders_or_secrets(self):
        banned = (
            "TODO",
            "FIXME",
            "lorem",
            "coming soon",
            "API_KEY",
            "api_key",
            "password =",
        )
        # The tests directory is excluded from this scan: the test file
        # itself names the banned words in its own check list, and it
        # uses temp paths. The shipped content is what must be clean.
        # .git is excluded too: GitHub's checkout ships sample hooks
        # under .git/hooks/ that contain "TODO" (Day 21 CI failure).
        shipped = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in str(path)
            and ".git" not in path.parts
            and "tests" not in path.parts
        ]
        for path in shipped:
            text = path.read_text(errors="ignore")
            for word in banned:
                self.assertNotIn(word, text, "%s in %s" % (word, path))

    def test_no_absolute_paths(self):
        # Same exclusion as the placeholder scan: the test file itself
        # names temp paths in its own check list.
        shipped = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "__pycache__" not in str(path)
            and ".git" not in path.parts
            and "tests" not in path.parts
        ]
        for path in shipped:
            text = path.read_text(errors="ignore")
            self.assertNotIn(
                "/home/hatch", text, "absolute path in %s" % path
            )
            self.assertNotIn("/tmp/", text, "absolute path in %s" % path)

    def test_gitignore_lists_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_the_tests(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("python3 tests/test_heading_order_checker.py", ci)
        self.assertIn('python-version: "3.12"', ci)

    def test_readme_contains_sample_output(self):
        readme = (ROOT / "README.md").read_text()
        saved = (EXAMPLES / "sample-output.txt").read_text()
        self.assertIn(saved.strip(), readme)


if __name__ == "__main__":
    unittest.main()
