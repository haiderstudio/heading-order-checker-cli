# heading-order-checker-cli

Check heading order in HTML and Markdown, one H1, no skipped levels, fail CI.

[![CI](https://github.com/haiderstudio/heading-order-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/heading-order-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`heading_order_checker` reads HTML and Markdown files and checks
two rules per file:

1. **Exactly one H1.** A file with no H1, or with two or more H1s,
   fails.
2. **No skipped levels.** A heading may not jump more than one level
   deeper than the heading before it: H1 followed by H3 is a fail,
   H2 followed by H4 is a fail, and a first heading that is not H1
   is a fail. Going back to a shallower level is always fine.

- It prints `PASS` or `FAIL` per file, with the exact line of each
  problem, and a summary line. It exits 1 when any file fails, so it
  can fail a CI run.
- It checks one file, several files, or a whole directory
  (directories are scanned for `.html`, `.htm`, `.md` and
  `.markdown` files, including subdirectories, unless you pass
  `--no-recursive`).
- `--allow-multiple-h1` allows more than one H1 per file, for pages
  that use several H1s on purpose. The skipped-level rule still
  applies.
- It is report-only and runs fully offline: it never rewrites a
  file, sends nothing anywhere, and needs no API key.
- HTML headings are found with the standard-library `html.parser`,
  so headings inside comments, `<script>` and `<style>` blocks are
  not counted. Markdown headings are ATX headings (`#` to `######`)
  found by plain-text matching; a `#` inside a fenced code block,
  an indented code block, or a frontmatter block is not counted.

## What it does NOT do

- It does not check setext headings (a title underlined with `===`
  or `---`). Those are not counted at all, and the tool says so
  rather than guessing at them.
- It does not check heading text, spelling, or whether a heading
  matches the page title. Only the order and the count.
- It does not check links, images, alt text, or anything else about
  the page. Those are other tools' jobs.
- It does not fix a file. A bad heading order is reported, not
  repaired.
- It does not fetch a live site. Only files on your own machine.

## Who it is for

Anyone who keeps HTML or Markdown files that need their headings in
order before a build: a docs site where a skipped level breaks the
page outline, a blog where every post needs exactly one H1, or a
team adding a CI step that fails the build when a page ships with
two H1s or a jump from H1 to H3. If the files are right, you get a
quiet pass; if one is wrong, the report says exactly which file and
which line.

## How this differs from similar tools

Heading order already exists as one check inside bigger tools, but
no small tool owns it on its own. The quoted GitHub search for the
exact name, `"heading-order-checker"`, returns 0 results. The
unquoted search returns 3 results, and the top one is a static HTML
accessibility checker (language, titles, alt text, labels and
heading order) — a whole accessibility list, not a heading-order
tool for CI. The `heading hierarchy checker` search returns 2
results, both 0 stars: a PHP temp repo and a TypeScript MCP server
for web accessibility (alt text, heading hierarchy, WCAG contrast,
ARIA validation). The big accessibility engines, like axe-core,
check heading order as one rule among dozens and need a browser or
Node. The `seo-meta-audit-skill` (Day 9 in this same series) checks
one page's H1 structure as part of a single-page SEO audit; this
is the standalone, multi-file, CI version of that one check.

This tool does a narrower job: a Python standard-library-only CLI
that checks one thing — heading order, one H1, no skipped levels —
on one file or a whole folder, reports the exact line per failure,
and exits 1 for CI. No install beyond Python, no browser, no Node,
no fixing.

## Install

Python standard library only — no packages to download. Clone the
repo and run it in place:

```sh
git clone https://github.com/haiderstudio/heading-order-checker-cli.git
cd heading-order-checker-cli
```

Python 3.10 or newer.

## Usage

Check the example files:

```sh
python3 src/heading_order_checker.py examples/good.html examples/good.md examples/skipped-level.html examples/two-h1.md examples/no-h1.html
```

Real output:

```text
PASS examples/good.html
PASS examples/good.md
FAIL examples/skipped-level.html: line 8: skipped level H1 -> H3
FAIL examples/two-h1.md: line 5: second H1 (first H1 at line 1)
FAIL examples/no-h1.html: no H1 heading in file; line 7: first heading is H2, expected H1
5 file(s) checked, 2 passed, 3 failed
```

The command exits 1, because three files fail. The same output is
saved in `examples/sample-output.txt`.

Check the good files alone:

```sh
python3 src/heading_order_checker.py examples/good.html examples/good.md
```

Real output:

```text
PASS examples/good.html
PASS examples/good.md
2 file(s) checked, 2 passed, 0 failed
```

The command exits 0.

Check a whole folder:

```sh
python3 src/heading_order_checker.py docs/
```

Directories are scanned for `.html`, `.htm`, `.md` and
`.markdown` files, including subdirectories. Add
`--no-recursive` to stay in the top folder only.

## Examples

### 1. A skipped level fails CI

`examples/skipped-level.html` goes straight from H1 to H3:

```sh
python3 src/heading_order_checker.py examples/skipped-level.html
```

```text
FAIL examples/skipped-level.html: line 8: skipped level H1 -> H3
1 file(s) checked, 0 passed, 1 failed
```

The exit code is 1. Put the same command in CI and the build
fails until the heading is fixed. With a valid file the same
command prints `PASS examples/skipped-level.html` and exits 0.

### 2. Two H1s in one file

`examples/two-h1.md` has an H1 on line 1 and another on line 5:

```sh
python3 src/heading_order_checker.py examples/two-h1.md
```

```text
FAIL examples/two-h1.md: line 5: second H1 (first H1 at line 1)
1 file(s) checked, 0 passed, 1 failed
```

If the page uses several H1s on purpose, pass
`--allow-multiple-h1` and the same file passes:

```sh
python3 src/heading_order_checker.py --allow-multiple-h1 examples/two-h1.md
```

```text
PASS examples/two-h1.md
1 file(s) checked, 1 passed, 0 failed
```

### 3. A page with no H1 at all

`examples/no-h1.html` starts with an H2 and never has an H1:

```sh
python3 src/heading_order_checker.py examples/no-h1.html
```

```text
FAIL examples/no-h1.html: no H1 heading in file; line 7: first heading is H2, expected H1
1 file(s) checked, 0 passed, 1 failed
```

The report names both problems: the missing H1, and the exact
line where the order first breaks.

## How it is tested

```sh
python3 tests/test_heading_order_checker.py
```

60 tests, standard library `unittest` only. They cover HTML
extraction (levels, line numbers, comments, script and style
blocks ignored), Markdown extraction (ATX headings, closing
hashes, fenced and indented code ignored, frontmatter skipped),
the two rules (missing H1, extra H1s, skipped levels, first
heading not H1, going shallower), the command line (exit codes
0, 1 and 2, directory scan, `--allow-multiple-h1`,
`--no-recursive`, `--version`), the bundled examples, and the
repo hygiene checks (standard-library imports only, no
placeholder text, no secrets, no absolute paths).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Small, focused
improvements are welcome. Run the tests before opening a pull
request.

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea — a
small checker for one heading-order rule — follows the same
pattern as the other single-job tools in this series; no code was
copied from any other project.
