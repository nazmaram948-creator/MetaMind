from dataclasses import dataclass
import os


@dataclass
class Settings:
    dev_mode: bool = os.getenv("DEV_MODE", "false").lower() == "true"
    # ENGINE_MODE=true serves every route from the real engine (engine/, SQLite DB)
    # instead of the development fixtures. Response models are unchanged.
    engine_mode: bool = os.getenv("ENGINE_MODE", "false").lower() == "true"
    # one origin, or several separated by commas
    cors_origin: str = os.getenv("CORS_ORIGIN", "http://localhost:5173")
    assumption_note: str = os.getenv(
        "ASSUMPTION_NOTE",
        "Estimate based on dated public datasets and development fixtures; not a guarantee.",
    )
    simulation_runs: int = int(os.getenv("SIMULATION_RUNS", "1000"))
    simulation_variation: float = float(os.getenv("SIMULATION_VARIATION", "0.2"))
    runpod_api_key: str | None = os.getenv("RUNPOD_API_KEY")
    runpod_endpoint_id: str | None = os.getenv("RUNPOD_ENDPOINT_ID")
    runpod_base_url: str | None = os.getenv("RUNPOD_BASE_URL")
    runpod_timeout_seconds: float = float(os.getenv("RUNPOD_TIMEOUT_SECONDS", "8"))


settings = Settings()
