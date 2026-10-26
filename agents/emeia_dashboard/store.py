"""Persistence for the EMEIA dashboard: plain SQL through SQLAlchemy Core."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


class DashboardStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def _run(self, sql: str, params: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(sql), params)

    def _rows(self, sql: str, params: dict | None = None) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(text(sql), params or {}).mappings().all()]

    def _row(self, sql: str, params: dict) -> dict | None:
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    # targets
    def create_target(self, record: dict) -> None:
        self._run(
            "INSERT INTO emeia_dashboard_targets (id, period, objective, key_result, target_value, current_value,"
            " unit, owner, created_at, updated_at) VALUES (:id, :period, :objective, :key_result, :target_value,"
            " :current_value, :unit, :owner, :created_at, :updated_at)", record)

    def update_target_current(self, target_id: str, current_value: float, updated_at: str) -> bool:
        if self._row("SELECT id FROM emeia_dashboard_targets WHERE id = :id", {"id": target_id}) is None:
            return False
        self._run("UPDATE emeia_dashboard_targets SET current_value = :v, updated_at = :u WHERE id = :id",
                  {"v": current_value, "u": updated_at, "id": target_id})
        return True

    def list_targets(self, period: str) -> list[dict]:
        return self._rows("SELECT * FROM emeia_dashboard_targets WHERE period = :period ORDER BY created_at",
                          {"period": period})

    # wins
    def create_win(self, record: dict) -> None:
        self._run(
            "INSERT INTO emeia_dashboard_wins (id, customer, description, value, currency, won_on, created_at)"
            " VALUES (:id, :customer, :description, :value, :currency, :won_on, :created_at)", record)

    def list_wins(self, start: str, end: str) -> list[dict]:
        return self._rows(
            "SELECT * FROM emeia_dashboard_wins WHERE won_on >= :start AND won_on <= :end ORDER BY won_on DESC",
            {"start": start, "end": end})

    # market items
    def create_market_item(self, record: dict) -> None:
        self._run(
            "INSERT INTO emeia_dashboard_market_items (id, kind, title, summary, source_url, reviewed, created_at)"
            " VALUES (:id, :kind, :title, :summary, :source_url, 0, :created_at)", record)

    def set_market_item_reviewed(self, item_id: str) -> bool:
        if self._row("SELECT id FROM emeia_dashboard_market_items WHERE id = :id", {"id": item_id}) is None:
            return False
        self._run("UPDATE emeia_dashboard_market_items SET reviewed = 1 WHERE id = :id", {"id": item_id})
        return True

    def list_market_items(self, reviewed: bool) -> list[dict]:
        return [dict(r, reviewed=bool(r["reviewed"])) for r in self._rows(
            "SELECT * FROM emeia_dashboard_market_items WHERE reviewed = :r ORDER BY created_at DESC",
            {"r": 1 if reviewed else 0})]

    # tool links
    def create_tool_link(self, record: dict) -> None:
        self._run("INSERT INTO emeia_dashboard_tool_links (id, label, url, created_at)"
                  " VALUES (:id, :label, :url, :created_at)", record)

    def list_tool_links(self) -> list[dict]:
        return self._rows("SELECT * FROM emeia_dashboard_tool_links ORDER BY created_at")
