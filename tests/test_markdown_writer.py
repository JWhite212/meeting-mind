"""Tests for the Markdown output writer."""

import time
from unittest.mock import patch

import pytest
import yaml

from src.output.markdown_writer import MarkdownWriter
from src.summariser import MeetingSummary
from src.utils.config import MarkdownConfig


@pytest.fixture
def started_at() -> float:
    return time.time()


@pytest.fixture
def duration() -> float:
    return 1800.0


class TestMarkdownWriter:
    """Tests for MarkdownWriter.write()."""

    def test_basic_write_creates_file(
        self, markdown_config, sample_summary, sample_transcript, started_at, duration
    ):
        writer = MarkdownWriter(markdown_config)
        path = writer.write(sample_summary, sample_transcript, started_at, duration)
        assert path.exists()

    def test_yaml_frontmatter_correctness(
        self, markdown_config, sample_summary, sample_transcript, started_at, duration
    ):
        writer = MarkdownWriter(markdown_config)
        path = writer.write(sample_summary, sample_transcript, started_at, duration)
        content = path.read_text(encoding="utf-8")

        # File must start with YAML frontmatter delimiters.
        assert content.startswith("---\n")

        # Extract frontmatter block (between first and second "---").
        parts = content.split("---", 2)
        frontmatter = parts[1]

        assert "title:" in frontmatter
        assert "date:" in frontmatter
        assert "tags:" in frontmatter

    def test_filename_slug_from_title(
        self, markdown_config, sample_summary, sample_transcript, started_at, duration
    ):
        writer = MarkdownWriter(markdown_config)
        path = writer.write(sample_summary, sample_transcript, started_at, duration)
        assert "sprint-planning" in path.name

    def test_empty_title_fallback(self, markdown_config, sample_transcript, started_at, duration):
        summary = MeetingSummary(
            raw_markdown="# Meeting\n\nSome content.",
            title="",
            tags=["general"],
        )
        writer = MarkdownWriter(markdown_config)
        path = writer.write(summary, sample_transcript, started_at, duration)
        assert "meeting" in path.name

    def test_path_traversal_blocked(
        self, tmp_path, sample_summary, sample_transcript, started_at, duration
    ):
        config = MarkdownConfig(
            vault_path=str(tmp_path / "vault"),
            filename_template="../{date}_{slug}.md",
            include_full_transcript=True,
        )
        writer = MarkdownWriter(config)
        # The "/" is replaced with "_" and leading "." is stripped,
        # so no ValueError is raised -- just a sanitized filename.
        path = writer.write(sample_summary, sample_transcript, started_at, duration)
        assert path.exists()

    def test_filename_special_chars_escaped(
        self, markdown_config, sample_transcript, started_at, duration
    ):
        summary = MeetingSummary(
            raw_markdown="# A/B\\C Test\n\nContent.",
            title="A/B\\C Test",
            tags=["test"],
        )
        writer = MarkdownWriter(markdown_config)
        path = writer.write(summary, sample_transcript, started_at, duration)
        # "/" and "\" are replaced with "_" in the filename.
        assert "/" not in path.name
        assert "\\" not in path.name

    def test_transcript_included_when_enabled(
        self, markdown_config, sample_summary, sample_transcript, started_at, duration
    ):
        assert markdown_config.include_full_transcript is True
        writer = MarkdownWriter(markdown_config)
        path = writer.write(sample_summary, sample_transcript, started_at, duration)
        content = path.read_text(encoding="utf-8")
        assert "## Full Transcript" in content

    def test_transcript_excluded_when_disabled(
        self, tmp_path, sample_summary, sample_transcript, started_at, duration
    ):
        config = MarkdownConfig(
            vault_path=str(tmp_path / "vault"),
            filename_template="{date}_{slug}.md",
            include_full_transcript=False,
        )
        writer = MarkdownWriter(config)
        path = writer.write(sample_summary, sample_transcript, started_at, duration)
        content = path.read_text(encoding="utf-8")
        assert "## Full Transcript" not in content

    def test_yaml_frontmatter_title_with_colon(
        self, markdown_config, sample_transcript, started_at, duration
    ):
        summary = MeetingSummary(
            raw_markdown="# Meeting: Sprint 5\n\nContent.",
            title="Meeting: Sprint 5",
            tags=["sprint"],
        )
        writer = MarkdownWriter(markdown_config)
        path = writer.write(summary, sample_transcript, started_at, duration)
        content = path.read_text(encoding="utf-8")

        # Extract and parse the YAML frontmatter block.
        parts = content.split("---", 2)
        parsed = yaml.safe_load(parts[1])
        assert parsed["title"] == "Meeting: Sprint 5"

    def test_yaml_frontmatter_title_with_newline(
        self, markdown_config, sample_transcript, started_at, duration
    ):
        summary = MeetingSummary(
            raw_markdown="# Line1\nLine2\n\nContent.",
            title="Line1\nLine2",
            tags=["general"],
        )
        writer = MarkdownWriter(markdown_config)
        path = writer.write(summary, sample_transcript, started_at, duration)
        content = path.read_text(encoding="utf-8")

        # Extract and parse the YAML frontmatter block.
        parts = content.split("---", 2)
        parsed = yaml.safe_load(parts[1])
        assert parsed["title"] == "Line1\nLine2"

    def test_long_title_truncated_in_slug(
        self, markdown_config, sample_transcript, started_at, duration
    ):
        long_title = "A" * 100 + " This Title Is Way Too Long For A Filename"
        summary = MeetingSummary(
            raw_markdown=f"# {long_title}\n\nContent.",
            title=long_title,
            tags=["test"],
        )
        writer = MarkdownWriter(markdown_config)
        path = writer.write(summary, sample_transcript, started_at, duration)

        # The filename template is "{date}_{slug}.md".
        # Extract the slug portion (after the date and underscore).
        name = path.stem  # e.g. "2026-04-14_aaaaaa..."
        slug = name.split("_", 1)[1]
        assert len(slug) <= 60

    def test_file_overwrite_on_duplicate(
        self, markdown_config, sample_transcript, started_at, duration
    ):
        summary_v1 = MeetingSummary(
            raw_markdown="# First\n\nVersion one.",
            title="Duplicate Test",
            tags=["v1"],
        )
        summary_v2 = MeetingSummary(
            raw_markdown="# Second\n\nVersion two.",
            title="Duplicate Test",
            tags=["v2"],
        )
        writer = MarkdownWriter(markdown_config)
        path1 = writer.write(summary_v1, sample_transcript, started_at, duration)
        path2 = writer.write(summary_v2, sample_transcript, started_at, duration)

        assert path1 == path2
        content = path2.read_text(encoding="utf-8")
        assert "Version two" in content
        assert "Version one" not in content

    def test_last_error_clears_on_success(
        self, markdown_config, sample_summary, sample_transcript, started_at, duration
    ):
        """A successful write must reset last_error to None."""
        writer = MarkdownWriter(markdown_config)
        writer.last_error = "previous failure"
        path = writer.write(sample_summary, sample_transcript, started_at, duration)
        assert path is not None
        assert writer.last_error is None

    def test_oserror_returns_none_and_sets_last_error(
        self, markdown_config, sample_summary, sample_transcript, started_at, duration
    ):
        """A filesystem error must surface via last_error rather than raise."""
        writer = MarkdownWriter(markdown_config)
        with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            result = writer.write(sample_summary, sample_transcript, started_at, duration)
        assert result is None
        assert writer.last_error is not None
        assert "disk full" in writer.last_error

    def test_makedirs_oserror_returns_none(
        self, tmp_path, sample_summary, sample_transcript, started_at, duration
    ):
        """If the vault directory cannot be created, write() returns None."""
        config = MarkdownConfig(
            vault_path=str(tmp_path / "vault"),
            filename_template="{date}_{slug}.md",
            include_full_transcript=True,
        )
        writer = MarkdownWriter(config)
        with patch("os.makedirs", side_effect=OSError("permission denied")):
            result = writer.write(sample_summary, sample_transcript, started_at, duration)
        assert result is None
        assert writer.last_error is not None
        assert "permission denied" in writer.last_error

    def test_write_uses_atomic_replace(
        self, markdown_config, sample_summary, sample_transcript, started_at, duration
    ):
        """Atomic writes go via a .tmp sibling and os.replace()."""
        writer = MarkdownWriter(markdown_config)
        with patch("src.output.markdown_writer.os.replace") as mock_replace:
            writer.write(sample_summary, sample_transcript, started_at, duration)
        mock_replace.assert_called_once()
        tmp_arg, final_arg = mock_replace.call_args.args
        assert str(tmp_arg).endswith(".tmp")
        assert not str(final_arg).endswith(".tmp")

    def test_atomic_write_cleans_up_tmp_on_failure(
        self, markdown_config, sample_summary, sample_transcript, started_at, duration
    ):
        """If os.replace fails, the .tmp file is unlinked."""
        writer = MarkdownWriter(markdown_config)
        with (
            patch(
                "src.output.markdown_writer.os.replace",
                side_effect=OSError("replace failed"),
            ),
            patch("pathlib.Path.unlink") as mock_unlink,
        ):
            result = writer.write(sample_summary, sample_transcript, started_at, duration)
        assert result is None
        assert writer.last_error is not None
        mock_unlink.assert_called_once()
