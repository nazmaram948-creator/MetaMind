from dataclasses import dataclass
import os


@dataclass
class Settings:
    dev_mode: bool = os.getenv("DEV_MODE", "false").lower() == "true"
    cors_origin: str = os.getenv("CORS_ORIGIN", "http://localhost:5173")
    assumption_note: str = os.getenv(
        "ASSUMPTION_NOTE",
        "Estimate based on dated public datasets and development fixtures; not a guarantee.",
    )
    simulation_runs: int = int(os.getenv("SIMULATION_RUNS", "1000"))
    simulation_variation: float = float(os.getenv("SIMULATION_VARIATION", "0.2"))


settings = Settings()
