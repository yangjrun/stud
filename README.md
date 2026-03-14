# A股超短线复盘与情绪分析系统

## Quick Start

```bash
# Install dependencies
uv sync

# Run API server
uv run uvicorn src.api.main:app --reload

# Load historical data
uv run python -m src.data.loader
```

## Project Structure

```
src/
├── config/         # Configuration
├── data/           # Data collection & storage
├── engine/         # Analysis engines (emotion, limit-up, theme, dragon-tiger)
├── api/            # FastAPI routes
└── scheduler/      # Scheduled tasks
```
