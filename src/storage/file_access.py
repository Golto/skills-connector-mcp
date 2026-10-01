import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.storage.exceptions import NonTextFileError


# NOTE: directories that are almost never what an agent is looking for, and
# that can hold thousands of files drowning the listing.
IGNORED_DIRECTORY_NAMES = frozenset({".git", "__pycache__", "node_modules", ".venv"})

_ENCODING = "utf-8"

_BINARY_SNIFF_SIZE_BYTES = 8192

_NEW_FILE_MODE = 0o644


# ----------------------------------------------------------------
# Listing
# ----------------------------------------------------------------


@dataclass(frozen=True)
class DirectoryListing:
    """Files found under a directory, relative to it.

    Attributes:
        entries: Relative file paths, in walk order (sorted per directory).
            Empty directories appear with a trailing '/'.
        is_truncated: True if the walk stopped at the entry limit.
    """

    entries: list[str]
    is_truncated: bool


def list_directory(host_dir: Path, max_entries: int) -> DirectoryListing:
    """List every file under a directory, recursively, up to a limit.

    Symbolic links are listed but never followed, and directories named in
    IGNORED_DIRECTORY_NAMES are skipped entirely. Empty directories are
    listed too, so that a freshly mounted, empty workspace remains visible.

    Args:
        host_dir: Absolute path of the directory on the host.
        max_entries: Number of entries after which the walk stops.

    Returns:
        The DirectoryListing.
    """
    entries: list[str] = []

    for directory, directory_names, file_names in os.walk(host_dir, followlinks=False):
        directory_names[:] = sorted(
            name for name in directory_names if name not in IGNORED_DIRECTORY_NAMES
        )
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(host_dir).as_posix()

        if not directory_names and not file_names and relative_directory != ".":
            entries.append(f"{relative_directory}/")

        for file_name in sorted(file_names):
            if len(entries) >= max_entries:
                return DirectoryListing(entries=entries, is_truncated=True)
            entries.append((directory_path / file_name).relative_to(host_dir).as_posix())

    return DirectoryListing(entries=entries, is_truncated=False)


# ----------------------------------------------------------------
# Reading
# ----------------------------------------------------------------


@dataclass(frozen=True)
class TextFileSlice:
    """A run of consecutive lines read from a text file.

    Attributes:
        content: The lines, line breaks included.
        start_line: One-based number of the first returned line.
        end_line: One-based number of the last returned line (start_line - 1
            when the file is empty).
        total_lines: Number of lines in the whole file.
        next_start_line: Line to start from to read the rest, None when the
            end of the file was reached.
    """

    content: str
    start_line: int
    end_line: int
    total_lines: int
    next_start_line: int | None


def read_text_file_slice(
    host_path: Path,
    start_line: int,
    max_bytes: int,
    max_file_size_bytes: int,
) -> TextFileSlice:
    """Read whole lines of a UTF-8 text file, from a line, within a size budget.

    Lines are added until the next one would exceed max_bytes, so a slice
    never ends mid-line. The exception is a first line longer than the whole
    budget (minified JSON, for instance): it is cut, and reading resumes at
    the following line.

    Args:
        host_path: Absolute path of the file on the host.
        start_line: One-based number of the first line to return.
        max_bytes: Maximum size of the returned content.
        max_file_size_bytes: Files larger than this are refused outright.

    Returns:
        The TextFileSlice.

    Raises:
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If the path is a directory.
        NonTextFileError: If the file is too large, binary or not UTF-8.
        ValueError: If start_line is past the end of the file.
    """
    if not host_path.exists():
        raise FileNotFoundError("File not found.")
    if host_path.is_dir():
        raise IsADirectoryError("Path is a directory, not a file.")

    file_size_bytes = host_path.stat().st_size
    if file_size_bytes > max_file_size_bytes:
        raise NonTextFileError(
            f"File is {file_size_bytes} bytes, above the {max_file_size_bytes} bytes "
            "this tool reads. Inspect it with a shell command (head, grep, wc)."
        )

    raw_content = host_path.read_bytes()
    if b"\x00" in raw_content[:_BINARY_SNIFF_SIZE_BYTES]:
        raise NonTextFileError(f"Binary file ({file_size_bytes} bytes), not shown as text.")
    try:
        text = raw_content.decode(_ENCODING)
    except UnicodeDecodeError as error:
        raise NonTextFileError(f"File is not valid UTF-8 text ({file_size_bytes} bytes).") from error

    lines = text.splitlines(keepends=True)
    total_lines = len(lines)
    if start_line > max(total_lines, 1):
        raise ValueError(f"start_line {start_line} is past the end of the file ({total_lines} lines).")

    selected_lines: list[str] = []
    used_bytes = 0
    line_index = start_line - 1

    while line_index < total_lines:
        line = lines[line_index]
        line_size_bytes = len(line.encode(_ENCODING))
        if used_bytes + line_size_bytes > max_bytes:
            if not selected_lines:
                selected_lines.append(_cut_to_bytes(line, max_bytes) + "\n[... line cut ...]\n")
                line_index += 1
            break
        selected_lines.append(line)
        used_bytes += line_size_bytes
        line_index += 1

    return TextFileSlice(
        content="".join(selected_lines),
        start_line=start_line,
        end_line=line_index,
        total_lines=total_lines,
        next_start_line=line_index + 1 if line_index < total_lines else None,
    )


def _cut_to_bytes(text: str, max_bytes: int) -> str:
    """Cut a string to at most max_bytes of UTF-8, without splitting a character."""
    return text.encode(_ENCODING)[:max_bytes].decode(_ENCODING, errors="ignore")


# ----------------------------------------------------------------
# Writing
# ----------------------------------------------------------------


def write_text_file_atomic(host_path: Path, content: str) -> bool:
    """Write a UTF-8 text file in one atomic step, creating parent directories.

    The content goes to a temporary file in the same directory, which then
    replaces the target, so a reader never sees a half-written file and an
    interrupted write leaves the previous version intact.

    Args:
        host_path: Absolute path of the file on the host.
        content: Full content of the file.

    Returns:
        True if the file was created, False if an existing file was replaced.

    Raises:
        IsADirectoryError: If the path is an existing directory.
        OSError: If the file or its parent directories cannot be written.
    """
    if host_path.is_dir():
        raise IsADirectoryError("Path is a directory, not a file.")

    was_created = not host_path.exists()
    file_mode = _NEW_FILE_MODE if was_created else host_path.stat().st_mode & 0o777
    host_path.parent.mkdir(parents=True, exist_ok=True)

    # NOTE: mkstemp creates the file with mode 0600, which os.replace would
    # carry over to the target. The mode is set explicitly before replacing.
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=host_path.parent, prefix=f".{host_path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding=_ENCODING) as temporary_file:
            temporary_file.write(content)
        os.chmod(temporary_name, file_mode)
        os.replace(temporary_name, host_path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise

    return was_created
