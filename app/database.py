import logging
from typing import Optional, Any
from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Global client holder
_supabase_client: Optional[Client] = None


class InMemorySupabaseMock:
    """
    In-memory fallback mock of Supabase PostgREST client.
    Ensures seamless local offline execution and automated tests
    when live Supabase credentials (SUPABASE_URL, SUPABASE_KEY) are not set.
    """

    def __init__(self):
        self._tables: dict[str, list[dict[str, Any]]] = {
            "generation_jobs": [],
            "certificates": [],
        }

    def table(self, table_name: str):
        return _MockTableQuery(self._tables, table_name)


class _MockTableQuery:
    def __init__(self, tables: dict[str, list[dict[str, Any]]], table_name: str):
        self.tables = tables
        self.table_name = table_name
        if table_name not in self.tables:
            self.tables[table_name] = []
        self._filters: list[tuple[str, str, Any]] = []
        self._pending_op: Optional[tuple[str, Any]] = None

    def insert(self, record_or_list: Any):
        self._pending_op = ("insert", record_or_list)
        return self

    def select(self, columns: str = "*"):
        self._pending_op = ("select", columns)
        return self

    def eq(self, column: str, value: Any):
        self._filters.append(("eq", column, value))
        return self

    def update(self, updates: dict[str, Any]):
        self._pending_op = ("update", updates)
        return self

    def _apply_filters(self):
        rows = self.tables.get(self.table_name, [])
        for ftype, col, val in self._filters:
            if ftype == "eq":
                rows = [r for r in rows if str(r.get(col)) == str(val)]
        return rows

    def execute(self):
        op_type, val = self._pending_op if self._pending_op else ("select", "*")
        if op_type == "insert":
            if isinstance(val, list):
                self.tables[self.table_name].extend(val)
                data = val
            else:
                self.tables[self.table_name].append(val)
                data = [val]
            return _MockResult(data=data)
        elif op_type == "update":
            matched = self._apply_filters()
            for row in matched:
                row.update(val)
            return _MockResult(data=matched)
        else:
            matched = [dict(r) for r in self._apply_filters()]
            return _MockResult(data=matched)


class _MockResult:
    def __init__(self, data: Any):
        self.data = data


def get_supabase_client():
    """
    Returns the initialized Supabase client, or falls back to an in-memory client
    if SUPABASE_URL/SUPABASE_KEY are not provided in .env.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if SUPABASE_URL and SUPABASE_KEY:
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Connected to Supabase client successfully.")
            return _supabase_client
        except Exception as e:
            logger.warning(f"Could not connect to Supabase: {e}. Using in-memory client.")

    return InMemorySupabaseMock()


def set_supabase_client(client_instance: Any):
    """Allows test fixtures to inject mock/isolated Supabase clients."""
    global _supabase_client
    _supabase_client = client_instance
