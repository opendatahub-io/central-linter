"""Tests for validators.files module.

Ported from TestFileOperations and TestNewlineAtEOF in test_mr_commit_linter.py.
"""

import os

import pytest
from unittest.mock import patch

from config import CommitInfo
from validators.files import (
    is_binary_file,
    should_skip_newline_check,
    validate_files_newline_at_eof,
    read_linterignore_file,
    expand_directory_patterns,
)


# ============================================================================
# FILE OPERATIONS TESTS
# ============================================================================

class TestFileOperations:
    def test_read_linterignore_file(self, tmp_path):
        linterignore = tmp_path / "linterignore"
        linterignore.write_text("file1.txt\ndir1/*\n\nfile2.py\n")
        result = read_linterignore_file(linterignore)
        assert result == ["file1.txt", "dir1/*", "file2.py"]

    def test_expand_directory_patterns_without_wildcards(self):
        patterns = ["file1.txt", "file2.py"]
        result = expand_directory_patterns(patterns)
        assert result == {"file1.txt", "file2.py"}

    def test_expand_directory_patterns_with_wildcards(self, tmp_path):
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        (test_dir / "file1.txt").touch()
        (test_dir / "file2.py").touch()

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            patterns = ["testdir/*", "other.txt"]
            result = expand_directory_patterns(patterns)
            assert "testdir/*" in result
            assert "other.txt" in result
            assert any("file1.txt" in str(f) for f in result)
            assert any("file2.py" in str(f) for f in result)
        finally:
            os.chdir(original_cwd)


# ============================================================================
# NEWLINE AT EOF VALIDATION TESTS
# ============================================================================

class TestNewlineAtEOF:
    def test_is_binary_file_with_binary(self, tmp_path):
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')
        assert is_binary_file(str(binary_file)) is True

    def test_is_binary_file_with_text(self, tmp_path):
        text_file = tmp_path / "test.txt"
        text_file.write_text("This is plain text\n")
        assert is_binary_file(str(text_file)) is False

    def test_is_binary_file_with_nonexistent(self):
        assert is_binary_file("/nonexistent/file.txt") is True

    def test_should_skip_newline_check_nonexistent(self):
        assert should_skip_newline_check("/nonexistent/file.txt") is True

    def test_should_skip_newline_check_directory(self, tmp_path):
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        assert should_skip_newline_check(str(test_dir)) is True

    def test_should_skip_newline_check_symlink(self, tmp_path):
        real_file = tmp_path / "real.txt"
        real_file.write_text("content\n")
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)
        assert should_skip_newline_check(str(symlink)) is True

    def test_should_skip_newline_check_binary(self, tmp_path):
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')
        assert should_skip_newline_check(str(binary_file)) is True

    def test_should_skip_newline_check_text_file(self, tmp_path):
        text_file = tmp_path / "text.txt"
        text_file.write_text("regular text file\n")
        assert should_skip_newline_check(str(text_file)) is False

    @pytest.mark.parametrize("filename", [
        "image.svg",
        "changes.patch",
        "changes.diff",
        "server.pem",
        "server.crt",
        "id_rsa.pub",
        "id_rsa.key",
        "uv.lock",
        "poetry.lock",
        "package-lock.json.lock",
        "IMAGE.SVG",
        "CERT.PEM",
    ])
    def test_should_skip_newline_check_tool_generated_extension(self, tmp_path, filename):
        f = tmp_path / filename
        f.write_text("content without newline")
        assert should_skip_newline_check(str(f)) is True

    @pytest.mark.parametrize("filename", [
        "RPM-GPG-KEY-redhat",
        "RPM-GPG-KEY-epel-9",
        "RPM-GPG-KEY-",
    ])
    def test_should_skip_newline_check_gpg_key_filename(self, tmp_path, filename):
        f = tmp_path / filename
        f.write_text("-----BEGIN PGP PUBLIC KEY BLOCK-----\n")
        assert should_skip_newline_check(str(f)) is True

    def test_should_skip_newline_check_python_not_skipped(self, tmp_path):
        py_file = tmp_path / "script.py"
        py_file.write_text("print('hello')")
        assert should_skip_newline_check(str(py_file)) is False

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_skips_tool_generated(self, mock_get_files, tmp_path):
        svg_file = tmp_path / "icon.svg"
        svg_file.write_bytes(b"<svg></svg>")
        patch_file = tmp_path / "fix.patch"
        patch_file.write_bytes(b"--- a/foo\n+++ b/foo")
        gpg_key = tmp_path / "RPM-GPG-KEY-redhat"
        gpg_key.write_bytes(b"-----BEGIN PGP PUBLIC KEY BLOCK-----")

        mock_get_files.return_value = [str(svg_file), str(patch_file), str(gpg_key)]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is True

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_py_still_checked(self, mock_get_files, tmp_path):
        py_file = tmp_path / "script.py"
        py_file.write_bytes(b"print('hello')")
        svg_file = tmp_path / "icon.svg"
        svg_file.write_bytes(b"<svg></svg>")

        mock_get_files.return_value = [str(py_file), str(svg_file)]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is False
        assert str(py_file) in result.error_message
        assert str(svg_file) not in result.error_message

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_success(self, mock_get_files, tmp_path):
        file1 = tmp_path / "file1.txt"
        file1.write_text("content\n")
        file2 = tmp_path / "file2.py"
        file2.write_text("#!/usr/bin/env python3\nprint('hello')\n")

        mock_get_files.return_value = [str(file1), str(file2)]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is True
        assert result.error_message is None

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_missing_newline(self, mock_get_files, tmp_path):
        file1 = tmp_path / "file1.txt"
        file1.write_bytes(b"content without newline")
        file2 = tmp_path / "file2.py"
        file2.write_bytes(b"print('hello')")

        mock_get_files.return_value = [str(file1), str(file2)]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is False
        assert "do not end with a newline" in result.error_message
        assert str(file1) in result.error_message
        assert str(file2) in result.error_message

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_empty_file(self, mock_get_files, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        mock_get_files.return_value = [str(empty_file)]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is True

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_skips_binary(self, mock_get_files, tmp_path):
        binary_file = tmp_path / "image.png"
        binary_file.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00')

        mock_get_files.return_value = [str(binary_file)]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is True

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_skips_symlinks(self, mock_get_files, tmp_path):
        real_file = tmp_path / "real.txt"
        real_file.write_bytes(b"content without newline")
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        mock_get_files.return_value = [str(symlink)]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is True

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_skips_deleted(self, mock_get_files):
        mock_get_files.return_value = ["/nonexistent/deleted.txt"]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is True

    @patch('validators.files.get_commit_modified_files')
    def test_validate_files_newline_at_eof_mixed_files(self, mock_get_files, tmp_path):
        good_file = tmp_path / "good.txt"
        good_file.write_text("content\n")
        bad_file = tmp_path / "bad.txt"
        bad_file.write_bytes(b"no newline")
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02')
        real_file = tmp_path / "real.txt"
        real_file.write_text("content\n")
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        mock_get_files.return_value = [str(good_file), str(bad_file), str(binary_file), str(symlink)]

        commit = CommitInfo(commit_id="abc123", title="RHELAI-1234: Test", body="Test\n\nSigned-off-by: Dev")
        result = validate_files_newline_at_eof(commit)
        assert result.success is False
        assert str(bad_file) in result.error_message
        assert str(binary_file) not in result.error_message
        assert str(symlink) not in result.error_message
