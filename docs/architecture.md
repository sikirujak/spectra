# Spectra Architecture

## System Overview

Spectra is a three-stage multi-agent pipeline for crypto market intelligence. Each agent is a specialized AI worker that performs a focused task and passes structured output to the next stage.

```
┌──────────────────────────────────────────────────────────┐
│                    SPECTRA PIPELINE                       │
│                                                          │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐            │
│  │  SCOUT   │───▶│ ANALYST  │───▶│ EXECUTOR │            │
│  │ (Discover)│   │ (Reason) │    │ (Deliver) │            │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘            │
│       │               │               │                  │
│  Signals          Assessments      Briefs               │
│  (JSON)           (JSON)          (Markdown/Telegram)    │
└──────────────────────────────────────────────────────────┘
                         │
                    ┌────▼─────┐
                    │  REDIS   │
                    │ Pub/Sub  │
                    └──────────┘
```

## Agent Details

### Scout Agent (Signal Discovery)

**Responsibility:** Monitor external data sources and emit structured signals when meaningful events are detected.

**Data Sources:**
| Source | Method | Data |
|--------|--------|------|
| DexScreener API | REST polling | New pools, price changes, volume surges |
| On-chain RPC | JSON-RPC | Whale transactions, new deployments |
| Telegram channels | Polling/scraping | Project announcements, community signals |

**Output:** `Signal` objects with type, source, chain, token info, and raw payload.

**Key Design Decisions:**
- Parallel source scanning via `asyncio.gather()`
- Configurable poll interval (default 30s)
- Graceful degradation — if one source fails, others continue
- All signals normalized to the same `Signal` schema regardless of source

### Analyst Agent (Deep Reasoning)

**Responsibility:** Consume signals and produce scored assessments using LLM chain-of-thought reasoning.

**Reasoning Framework (6-step):**
1. **Verify** — Is the signal data consistent and plausible?
2. **Fundamentals** — What does the project do? Any red flags?
3. **On-chain check** — Holder distribution, LP lock, dev wallet share
4. **Timing** — How fresh is this? Too late to act?
5. **Risk** — What could go wrong? Rate LOW/MEDIUM/HIGH/CRITICAL
6. **Score** — Assign confidence 0-100

**LLM Configuration:**
- Primary: Xiaomi MiMo (mimo-v2-pro) via OpenAI-compatible API
- Fallback: Claude via OpenRouter
- Temperature: 0.3 (deterministic reasoning)
- Response format: JSON for structured parsing

**Key Design Decisions:**
- Structured output via JSON response format + Pydantic validation
- Fallback assessment when LLM is unavailable (score=0, risk=CRITICAL)
- Batch processing with concurrent analysis via `asyncio.gather()`

### Executor Agent (Output & Delivery)

**Responsibility:** Convert assessments into human-readable briefs and deliver via configured channels.

**Output Formats:**
| Channel | Format | Priority |
|---------|--------|----------|
| Telegram | Markdown message | High confidence signals |
| Discord | Webhook embeds | High confidence signals |
| JSON file | Structured brief data | All signals |
| Periodic digest | Summary report | All signals |

**Routing Logic:**
- Confidence ≥ 80 + Risk ≤ MEDIUM → **IMMEDIATE** alert
- Confidence ≥ 60 → **MONITOR** alert
- Confidence ≥ 40 → Include in **DIGEST** only
- Confidence < 40 → **SKIP**

## Inter-Agent Communication

### Direct Pipeline Mode (default)
Agents pass data directly in-memory through Python async calls. Simple, fast, no external dependencies beyond what each agent needs.

### Redis Pub/Sub Mode (daemon)
Agents communicate through Redis channels:
- `spectra:signals` — Scout publishes, Analyst subscribes
- `spectra:assessments` — Analyst publishes, Executor subscribes

This enables:
- Independent agent deployment and scaling
- Agent restart without pipeline disruption
- Multiple consumers per channel (e.g., multiple analysts)

## Configuration

All configuration via environment variables (`.env` file):

| Category | Key | Purpose |
|----------|-----|---------|
| LLM | `MIMO_API_KEY` | MiMo API authentication |
| LLM | `MIMO_BASE_URL` | MiMo API endpoint |
| LLM | `ANALYST_MODEL` | Model for analysis |
| Redis | `REDIS_URL` | Message bus connection |
| Data | `DEXSCREENER_API` | DEX data endpoint |
| Output | `TELEGRAM_BOT_TOKEN` | Alert delivery bot |
| Output | `TELEGRAM_CHAT_ID` | Alert target chat |
| Agent | `SCOUT_POLL_INTERVAL` | Scan frequency (seconds) |
| Agent | `EXECUTOR_DIGEST_INTERVAL` | Digest frequency (seconds) |

## Extending Spectra

### Adding a new data source to Scout
1. Create a new method in `ScoutAgent` (e.g., `scan_twitter_sentiment`)
2. Return a list of `Signal` objects
3. Add the method to `run_cycle()`

### Adding a new delivery channel to Executor
1. Create a new delivery class (like `TelegramDelivery`)
2. Add it to `ExecutorAgent.process_assessment()`
3. Configure credentials in `OutputConfig`

### Adding a new agent
1. Create new agent class in `spectra/agents/`
2. Define input/output models in `spectra/models.py`
3. Add Redis channel for communication
4. Register in `PipelineOrchestrator`
