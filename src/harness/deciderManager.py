"""DeciderManager that loads JSON schemas via DeciderFactory and exposes named Decider instances."""

from pathlib import Path
from typing import Any

from src.engines.base import DecisionEngine
from src.harness.deciderFactory import Decider, DeciderFactory, DecisionResult

DEFAULT_SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


class DeciderManager:
    """Manages a registry of Decider instances built from declarative JSON schemas."""

    def __init__(
        self,
        engine: DecisionEngine,
        schemas_dir: Path | None = None,
    ) -> None:
        self.engine = engine
        self.schemas_dir = schemas_dir or DEFAULT_SCHEMAS_DIR
        self.deciders: dict[str, Decider] = {}
        self._load_schemas()

    def _load_schemas(self) -> None:
        """Discover all non-empty *.json schema files and instantiate a Decider for each."""
        if not self.schemas_dir.is_dir():
            return
        for path in sorted(self.schemas_dir.glob("*.json")):
            text = path.read_text(encoding="utf-8").strip()
            if not text or text == "{}":
                continue
            decider = DeciderFactory.from_file(path=path, engine=self.engine)
            self.deciders[decider.name] = decider

    def register_decider(self, decider: Decider) -> None:
        """Register or override a Decider instance by name."""
        self.deciders[decider.name] = decider

    def get_decider(self, name: str) -> Decider:
        """Retrieve a registered Decider by name (e.g., 'intent' or 'star')."""
        if name not in self.deciders:
            available = ", ".join(sorted(self.deciders.keys()))
            raise KeyError(f"Unknown decider {name!r}. Available deciders: [{available}]")
        return self.deciders[name]

    def list_deciders(self) -> list[str]:
        """Return sorted names of all loaded deciders."""
        return sorted(self.deciders.keys())

    def decide(self, name: str, state: dict[str, Any]) -> DecisionResult:
        """Dispatch `state` to the named Decider and return its DecisionResult."""
        return self.get_decider(name).decide(state=state)
