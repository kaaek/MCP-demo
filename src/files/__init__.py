"""File-system toolkit.

Plain-Python file operations rooted at a workspace directory. Paths are joined
to the workspace but NOT confined to it (minimal guards), so path traversal
such as ``../../etc/passwd`` remains possible and observable.
"""

from files.ops import (
    append_file,
    delete_file,
    list_dir,
    read_file,
    search_files,
    write_file,
)

__all__ = ["append_file", "delete_file", "list_dir", "read_file", "search_files", "write_file"]
