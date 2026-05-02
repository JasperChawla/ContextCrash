# ContextCrash

Adversarial reliability benchmarking for LLM-powered RAG pipelines. Define a test suite in YAML, run it against Claude/GPT-4o/Gemini simultaneously, get a failure heatmap and regression delta.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        ContextCrash                          │
└─────────────────────────┬────────────────────────────────────┘
                          │
          ┌───────────────┴────────────────┐
          ▼                                ▼
    ┌──────────┐                    ┌────────────┐
    │   CLI    │                    │  Web UI    │
    │ (click + │                    │ (React +   │
    │  rich)   │                    │  D3.js)    │
    └────┬─────┘                    └─────┬──────┘
         │                                │
         └───────────────┬────────────────┘
                         │
                ┌────────▼────────┐
                │  FastAPI Server │
                │  /runs  /results│
                └────────┬────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
  ┌──────────────┐ ┌──────────┐ ┌────────────┐
  │ Test Runner  │ │ DuckDB   │ │ Aggregator │
  │  (asyncio)   │ │ storage  │ │ summaries  │
  │  semaphore   │ │          │ │ + deltas   │
  └──────┬───────┘ └──────────┘ └────────────┘
         │
   ┌─────┴──────────────────────────────────┐
   │                                        │
   ▼                                        ▼
┌──────────────────┐              ┌─────────────────────┐
│  Perturbations   │              │     Evaluators      │
│                  │              │                     │
│ chunk_shuffle    │              │ deterministic rules │
│ distractor_inject│              │  (cheap, runs first)│
│ conflicting_evid │              │                     │
│ instruction_bury │              │ LLM judge           │
│ history_contamin │              │  (only if ambiguous)│
│ paraphrase_evid  │              │                     │
└──────────────────┘              │ disagreement tracker│
                                  └─────────────────────┘
                                          │
                     ┌────────────────────┘
                     ▼
              ┌─────────────────────────────┐
              │          LiteLLM            │
              │  claude  │  gpt-4o  │ gemini│
              └─────────────────────────────┘
```

---

## Failure Taxonomy

| Category | What it tests |
|---|---|
| `instruction_loss` | Model ignores system prompt instructions under long context |
| `retrieval_overshadowing` | Retrieved chunks dominate response; actual query ignored |
| `position_bias` | Model overweights first/last chunks, ignores middle content |
| `answer_truncation` | Response cuts off mid-sentence due to token pressure |
| `multi_turn_memory_decay` | Earlier conversation context forgotten or contradicted |
| `contradiction_long_context` | Conflicting evidence silently picked vs. flagged |
| `citation_drift` | Citations don't map to the actual source chunks |
| `hallucination_overload` | Model fabricates facts not present in any chunk |

---

## Setup

### 1. Install

```bash
git clone <repo>
cd contextcrash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -e .
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env with your keys
```

Or export directly:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

### 3. Run your first suite

```bash
contextcrash run examples/suite.yaml
```

### 4. Compare two configurations

```bash
contextcrash compare examples/baseline.yaml examples/candidate.yaml
```

---

## CLI Reference

```
contextcrash run SUITE_FILE [OPTIONS]

  Options:
    --db PATH          Override DuckDB path (default: from suite config)
    --models TEXT      Comma-separated model overrides
    --output [rich|json]

contextcrash compare BASELINE_FILE CANDIDATE_FILE [OPTIONS]

  Options:
    --db PATH
    --output [rich|json]
```

---

## Web UI

### Development

```bash
# Terminal 1 - backend
uvicorn api.main:app --reload

# Terminal 2 - frontend
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Docker

```bash
docker-compose up --build
# API: http://localhost:8000
# UI:  http://localhost:3000
```

---

## Writing a Test Suite

```yaml
suite:
  name: "My RAG Suite"

models:
  - claude-haiku-4-5-20251001
  - gpt-4o-mini

judge_model: claude-haiku-4-5-20251001
parallel_workers: 5

defaults:
  system_prompt: |
    You are a helpful assistant. Always cite sources using [1], [2] format.

test_cases:
  - name: "test_citation_in_long_context"
    failure_category: instruction_loss
    perturbation: instruction_burial
    perturbation_config:
      depth: 0.85          # bury instructions 85% deep in context
      padding_count: 6
    query: "What was Q3 revenue?"
    expected_behavior: "Must include citation markers [1] or [2]"
    chunks:
      - "Q3 revenue was $1.2B, up 15% YoY."
      - "Operating margin reached 24%."
    validators:
      - type: contains_pattern
        pattern: "\\[\\d+\\]"
        description: "Citation markers required"
    metadata:
      severity: critical
```

### Perturbation types

| `perturbation` value | What it does |
|---|---|
| `chunk_shuffle` | Randomly reorders chunks (exposes position bias) |
| `distractor_injection` | Adds irrelevant chunks (tests retrieval focus) |
| `conflicting_evidence` | Injects a chunk that contradicts another |
| `instruction_burial` | Pushes key instructions deep into context |
| `history_contamination` | Injects false turns into conversation history |
| `paraphrase_evidence` | Rewrites chunks with synonyms (tests exact vs semantic match) |

### Validator types

| `type` | Config | What it checks |
|---|---|---|
| `contains_pattern` | `pattern: regex` | Response matches regex |
| `not_contains` | `pattern: regex` | Response does NOT match regex |
| `min_length` | `value: int` | `len(response) >= value` |
| `max_length` | `value: int` | `len(response) <= value` |
| `ends_with_punctuation` | — | Response ends with `.!?` |
| `contains_all` | `value: [str, ...]` | All strings present in response |

---

## Testing

```bash
pytest tests/ -v
```

---

## Project Structure

```
contextcrash/
├── core/
│   ├── models.py          # Pydantic data models
│   ├── config.py          # YAML DSL loader + perturbation application
│   ├── runner.py          # Async test runner (asyncio + LiteLLM)
│   └── storage.py         # DuckDB read/write layer
├── evaluators/
│   ├── deterministic.py   # Rule-based validators (8 categories)
│   ├── llm_judge.py       # LLM-as-judge (Claude, ambiguous cases only)
│   └── aggregator.py      # Summary + regression delta computation
├── perturbations/
│   ├── chunk_shuffle.py
│   ├── distractor.py
│   ├── conflicting.py
│   ├── instruction_burial.py
│   ├── history_contamination.py
│   └── paraphrase.py
├── cli/
│   └── main.py            # click CLI: run, compare
├── api/
│   ├── main.py            # FastAPI app
│   └── routes/            # /runs, /results endpoints
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── Heatmap.jsx        # D3.js failure heatmap
│           ├── ComparisonView.jsx # Regression delta bars
│           └── RunHistory.jsx     # Sidebar run list
├── tests/
├── examples/
│   └── suite.yaml
├── docker-compose.yml
└── requirements.txt
```

---

## How Evaluation Works

Every test runs deterministic rules first. The LLM judge is only called when the deterministic score falls in the ambiguous range `[threshold-0.2, threshold+0.2]` (default `[0.3, 0.7]`). This cuts judge API costs by ~60-80% on typical suites.

```
test response
      │
      ▼
deterministic rules ──► score < 0.3 ──► FAIL (no judge needed)
      │
      ├──► score > 0.7 ──► PASS (no judge needed)
      │
      └──► 0.3–0.7 ──► LLM judge ──► final_score
                              │
                              └──► |det - judge| > 0.4 ──► disagreement logged
```

Judge disagreement rates are tracked per run and surfaced in the summary. High disagreement in a category means the deterministic rules need tuning.
