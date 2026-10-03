"""SQLite toolkit.

Thin wrapper over :mod:`sqlite3` exposing schema introspection, read queries
and raw statement execution. Statements are executed verbatim (minimal guards),
so SQL injection through tool arguments remains possible and observable.
"""

from sqlite_db.db import describe_table, execute, init_db, list_tables, query

__all__ = ["describe_table", "execute", "init_db", "list_tables", "query"]
