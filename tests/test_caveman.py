#!/usr/bin/env python3
"""
Unit tests for caveman.py.

Best-practice patterns demonstrated:
  - Fixture loading via `load_fixture(name)` helper
  - Property-based assertions (preservation invariants)
  - Idempotency verification (cave(cave(x)) == cave(x))
  - Parameterized substitution checks via subTest
  - Edge case coverage (empty, only-frontmatter, only-code, only-tables)
  - CLI integration tests via subprocess (real argv, real stdout/stderr)
  - Each test states the *behavior under verification* in its docstring.

Run:
    python3 -m unittest discover tests -v
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(SCRIPTS))
import caveman  # noqa: E402


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# ----- Property-based: structure preservation across all modes ---------------

class TestPreservationInvariants(unittest.TestCase):
    """For every supported mode, certain things MUST survive untouched.

    These are property tests: they assert invariants, not specific outputs.
    Whenever a substitution rule is added, these still need to pass.
    """

    SAMPLE = load_fixture("full_skill.md")

    def test_frontmatter_preserved_in_all_modes(self):
        for mode in ("lite", "default", "ultra"):
            with self.subTest(mode=mode):
                out = caveman.cave(self.SAMPLE, mode=mode)
                self.assertTrue(out.startswith("---\nname: full-skill\n"),
                                f"frontmatter altered in {mode} mode")
                self.assertIn("description: A representative skill", out)

    def test_urls_preserved(self):
        text_with_url = dedent("""\
            See https://example.com/docs for details.
            And https://other.example.org/path?q=1.
        """)
        for mode in ("lite", "default", "ultra"):
            with self.subTest(mode=mode):
                out = caveman.cave(text_with_url, mode=mode)
                problems = caveman.validate_preservation(text_with_url, out)
                self.assertEqual([], problems, f"URL preservation failed in {mode}")

    def test_file_paths_preserved(self):
        text = "Run /skills/build-jd/scripts/jd_builder.py and ./templates/Full_Template.pptx."
        for mode in ("lite", "default", "ultra"):
            with self.subTest(mode=mode):
                out = caveman.cave(text, mode=mode)
                self.assertIn("/skills/build-jd/scripts/jd_builder.py", out)
                self.assertIn("./templates/Full_Template.pptx", out)

    def test_code_blocks_byte_identical(self):
        out = caveman.cave(self.SAMPLE, mode="ultra")
        # The intensifier "very fancy words" inside ``` and inline `...` must survive
        self.assertIn('"""Docstring with very fancy words should NOT be compressed."""', out)
        self.assertIn("`code with very fancy words`", out)

    def test_heading_count_preserved(self):
        for mode in ("lite", "default", "ultra"):
            with self.subTest(mode=mode):
                out = caveman.cave(self.SAMPLE, mode=mode)
                problems = [p for p in caveman.validate_preservation(self.SAMPLE, out)
                            if "heading" in p]
                self.assertEqual([], problems)

    def test_table_structure_preserved(self):
        for mode in ("lite", "default", "ultra"):
            with self.subTest(mode=mode):
                out = caveman.cave(self.SAMPLE, mode=mode)
                # Separator row intact
                self.assertIn("|------|--------|-------|", out)
                # Header row intact
                self.assertIn("| Step | Action | Notes |", out)


# ----- Idempotency -----------------------------------------------------------

class TestIdempotency(unittest.TestCase):
    """cave(cave(x)) MUST equal cave(x) — once compressed, no further reduction."""

    SAMPLE = load_fixture("full_skill.md")

    def test_idempotent_lite(self):
        once = caveman.cave(self.SAMPLE, mode="lite")
        twice = caveman.cave(once, mode="lite")
        self.assertEqual(once, twice)

    def test_idempotent_default(self):
        once = caveman.cave(self.SAMPLE, mode="default")
        twice = caveman.cave(once, mode="default")
        self.assertEqual(once, twice)

    def test_idempotent_ultra(self):
        once = caveman.cave(self.SAMPLE, mode="ultra")
        twice = caveman.cave(once, mode="ultra")
        self.assertEqual(once, twice)


# ----- Parameterized substitution checks -------------------------------------

class TestSubstitutions(unittest.TestCase):
    """Each row asserts a specific input phrase produces a specific output phrase."""

    LITE_CASES = [
        ("In order to build, gather data.", "to build, gather data."),
        ("Due to the fact that X happened, Y.", "because X happened, Y."),
        ("It might possibly fail.", "It might fail."),
        ("Prior to running, check config.", "before running, check config."),
    ]

    DEFAULT_ONLY_CASES = [
        ("Make sure to validate input.", "validate input."),
        ("You should run tests first.", "run tests first."),
        ("Please configure the API key.", "configure the API key."),
        ("It is very important.", "It is important."),  # intensifier "very" goes
        ("As mentioned above, retry.", "retry."),
    ]

    def test_lite_substitutions(self):
        for src, expected in self.LITE_CASES:
            with self.subTest(src=src):
                self.assertEqual(expected, caveman.cave(src, mode="lite").strip())

    def test_default_only_substitutions(self):
        """Default mode applies these; lite must NOT (these would alter meaning)."""
        for src, expected in self.DEFAULT_ONLY_CASES:
            with self.subTest(src=src):
                self.assertEqual(expected, caveman.cave(src, mode="default").strip())
                # Lite mode should NOT have made these changes — input survives mostly intact
                lite_out = caveman.cave(src, mode="lite").strip()
                self.assertNotEqual(lite_out, expected,
                                    f"lite mode should not transform: {src!r}")


# ----- Mode monotonicity -----------------------------------------------------

class TestModeMonotonicity(unittest.TestCase):
    """Compression must increase: lite ≥ default ≥ ultra (in word count out)."""

    def test_word_count_decreases_with_intensity(self):
        sample = load_fixture("full_skill.md")
        wl = caveman.words(caveman.cave(sample, mode="lite"))
        wd = caveman.words(caveman.cave(sample, mode="default"))
        wu = caveman.words(caveman.cave(sample, mode="ultra"))
        self.assertGreaterEqual(wl, wd, "default should compress at least as much as lite")
        self.assertGreaterEqual(wd, wu, "ultra should compress at least as much as default")
        # And on this fixture, strictly less:
        self.assertGreater(wl, wd)
        self.assertGreater(wd, wu)


# ----- Structural validation -------------------------------------------------

class TestStructuralValidation(unittest.TestCase):
    """validate_structure detects intrinsic problems."""

    def test_well_formed_returns_empty(self):
        self.assertEqual([], caveman.validate_structure(load_fixture("full_skill.md")))

    def test_unbalanced_fence_detected(self):
        bad = load_fixture("edge_unbalanced_fence.md")
        problems = caveman.validate_structure(bad)
        self.assertTrue(any("unbalanced" in p for p in problems),
                        f"expected 'unbalanced' in {problems}")

    def test_unclosed_frontmatter_detected(self):
        bad = "---\nname: x\nNo closing fence\n"
        problems = caveman.validate_structure(bad)
        self.assertTrue(any("never closed" in p for p in problems))

    def test_orphan_table_separator_detected(self):
        bad = "Some prose\n|------|------|\n| a | b |\n"
        problems = caveman.validate_structure(bad)
        self.assertTrue(any("table separator" in p for p in problems))


# ----- Preservation validation (input vs output) -----------------------------

class TestPreservationValidation(unittest.TestCase):
    """validate_preservation flags lost URLs/paths/headings/code/bullets."""

    def test_clean_compression_passes(self):
        sample = load_fixture("full_skill.md")
        compressed = caveman.cave(sample, mode="default")
        self.assertEqual([], caveman.validate_preservation(sample, compressed))

    def test_url_loss_detected(self):
        original = "See https://example.com/docs for details."
        damaged = "See for details."
        problems = caveman.validate_preservation(original, damaged)
        self.assertTrue(any("URLs lost" in p for p in problems))

    def test_heading_count_change_detected(self):
        original = "# A\n## B\n## C\n"
        damaged = "# A\n## B\n"
        problems = caveman.validate_preservation(original, damaged)
        self.assertTrue(any("heading count changed" in p for p in problems))

    def test_bullet_count_change_detected(self):
        original = "- one\n- two\n- three\n"
        damaged = "- one\n- two\n"
        problems = caveman.validate_preservation(original, damaged)
        self.assertTrue(any("bullet count changed" in p for p in problems))


# ----- Edge cases ------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    """Pathological / minimal inputs must not crash or corrupt."""

    def test_empty_input(self):
        self.assertEqual("", caveman.cave("", mode="default"))
        self.assertEqual([], caveman.validate_structure(""))

    def test_only_frontmatter(self):
        sample = load_fixture("edge_only_frontmatter.md")
        out = caveman.cave(sample, mode="default")
        self.assertIn("name: only-frontmatter", out)
        self.assertEqual(out.strip().count("---"), 2)

    def test_only_code(self):
        sample = "```python\nprint('hello')\n```\n"
        for mode in ("lite", "default", "ultra"):
            with self.subTest(mode=mode):
                out = caveman.cave(sample, mode=mode)
                self.assertIn("print('hello')", out)

    def test_only_table(self):
        sample = "| a | b |\n|---|---|\n| 1 | 2 |\n"
        for mode in ("lite", "default", "ultra"):
            with self.subTest(mode=mode):
                out = caveman.cave(sample, mode=mode)
                self.assertIn("|---|---|", out)
                self.assertIn("| 1 | 2 |", out)


# ----- CLI integration via subprocess ---------------------------------------

class TestCLI(unittest.TestCase):
    """Invoke caveman.py as a subprocess. Verifies argparse, exit codes, IO."""

    SCRIPT = SCRIPTS / "caveman.py"

    @classmethod
    def setUpClass(cls):
        cls.fixture = FIXTURES / "full_skill.md"

    def _run(self, *args, stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_stdout_default(self):
        r = self._run(str(self.fixture))
        self.assertEqual(0, r.returncode, msg=r.stderr)
        self.assertIn("# Full Skill", r.stdout)
        self.assertIn("caveman[default]", r.stderr)

    def test_lite_flag(self):
        r = self._run(str(self.fixture), "--lite", "--report")
        self.assertEqual(0, r.returncode)
        self.assertIn("caveman[lite]", r.stderr)

    def test_ultra_flag(self):
        r = self._run(str(self.fixture), "--ultra", "--report")
        self.assertEqual(0, r.returncode)
        self.assertIn("caveman[ultra]", r.stderr)

    def test_stdin(self):
        r = self._run("-", stdin="In order to test, run.")
        self.assertEqual(0, r.returncode)
        self.assertIn("to test, run.", r.stdout)

    def test_validate_only_ok(self):
        r = self._run(str(self.fixture), "--validate-only")
        self.assertEqual(0, r.returncode)
        self.assertIn("OK", r.stderr)

    def test_validate_only_fails_on_bad(self):
        r = self._run(str(FIXTURES / "edge_unbalanced_fence.md"), "--validate-only")
        self.assertEqual(1, r.returncode)
        self.assertIn("validation", r.stderr)

    def test_write_creates_bak(self):
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "SKILL.md"
            shutil.copy(self.fixture, target)
            r = self._run(str(target), "-w")
            self.assertEqual(0, r.returncode, msg=r.stderr)
            self.assertTrue((Path(td) / "SKILL.md.bak").exists(),
                            "expected SKILL.md.bak backup")
            # Backup matches original byte-for-byte
            self.assertEqual(self.fixture.read_text(), (Path(td) / "SKILL.md.bak").read_text())
            # Compressed file is shorter (in word count)
            self.assertLess(caveman.words(target.read_text()),
                            caveman.words(self.fixture.read_text()))

    def test_write_with_stdin_errors(self):
        r = self._run("-", "-w", stdin="x")
        self.assertEqual(2, r.returncode)
        self.assertIn("incompatible", r.stderr)


if __name__ == "__main__":
    unittest.main()
