"""Neo4j driver lifecycle for the Fraud service.

One application-level driver is created at startup and reused for every query;
it is closed cleanly on shutdown. Connection settings come from environment
variables. Passwords are never logged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from types import TracebackType
from typing import Any

from neo4j import Driver, GraphDatabase


@dataclass(frozen=True)
class GraphSettings:
    uri: str
    username: str
    password: str

    @classmethod
    def from_env(cls) -> GraphSettings:
        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "pybank_neo4j_password"),
        )


class GraphClient:
    """Thin wrapper owning the single Neo4j driver instance."""

    def __init__(self, settings: GraphSettings) -> None:
        self._settings = settings
        self._driver: Driver | None = None
        self._schema_ready = False

    @property
    def settings(self) -> GraphSettings:
        return self._settings

    def connect(self) -> None:
        """Create the driver. Does NOT raise when Neo4j is down: the graph is
        an advisory dependency and the service must degrade gracefully."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self._settings.uri,
                auth=(self._settings.username, self._settings.password),
            )

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None
        self._schema_ready = False

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self.connect()
        assert self._driver is not None
        return self._driver

    def is_available(self) -> bool:
        """Cheap reachability probe used for advisory readiness reporting."""
        try:
            self.driver.verify_connectivity()
        except Exception:
            return False
        return True

    def ensure_schema(self) -> None:
        """Create uniqueness constraints once per driver lifetime."""
        if self._schema_ready:
            return
        with self.driver.session() as session:
            for statement in (
                "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS "
                "FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
                "CREATE CONSTRAINT account_id_unique IF NOT EXISTS "
                "FOR (a:Account) REQUIRE a.account_id IS UNIQUE",
                "CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS "
                "FOR (t:Transaction) REQUIRE t.transaction_id IS UNIQUE",
            ):
                session.run(statement)
        self._schema_ready = True

    def execute_read(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            return [
                dict(record)
                for record in session.execute_read(
                    lambda tx: list(tx.run(query, parameters))
                )
            ]

    def execute_write(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            return [
                dict(record)
                for record in session.execute_write(
                    lambda tx: list(tx.run(query, parameters))
                )
            ]

    def __enter__(self) -> GraphClient:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
