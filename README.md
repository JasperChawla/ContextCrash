# ContextCrash

Adversarial reliability benchmarking dashboard for LLM-powered RAG pipelines.
Define a test suite in YAML, run it against multiple models, and explore a failure heatmap, degradation curve, and regression delta in a local React dashboard.

---

## Demo data vs live provider data

The included example suites contain **synthetic adversarial benchmark data** -- fictional company names, figures, and scenarios designed for reproducible local demos without requiring real API keys or sensitive data.

When real provider API keys are configured (see Setup), the same CLI, storage, and dashboard pipeline visualises live results from real model calls. The included examples should **not** be used to claim one provider is universally better than another.

---

## Architecture



---

## Failure taxonomy

| Category | What it tests |
|---|---|
| instruction_loss | Model ignores system-prompt instructions under long context |
| retrieval_overshadowing | Retrieved chunks dominate; the actual query is ignored |
| position_bias | Model overweights first/last chunks, misses middle content |
| answer_truncation | Response cuts off mid-sentence under token pressure |
| multi_turn_memory_decay | Earlier conversation context forgotten or contradicted |
| contradiction_long_context | Conflicting evidence silently selected rather than flagged |
| citation_drift | Citations do not map to the actual source chunks |
| hallucination_overload | Model fabricates facts not present in any chunk |

---

## Setup

```bash
git clone <repo>
cd contextcrash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scriptsctivate
pip install -e .
```

### API keys (optional for included examples)

```bash
cp .env.example .env
# Add ANTHROPIC_API_KEY and/or OPENAI_API_KEY
```

---

## Quick start

### Basic suite -- populates metric cards and heatmap

```bash
py -m cli.main run examples/suite.yaml
```

### Advanced suite -- populates metric cards, heatmap, and degradation curve

The advanced suite includes context_depth_levels: [0.25, 0.5, 0.75, 1.0] on selected
test cases. This triggers extra model calls at 25/50/75/100 percent of the full
context window, producing the per-model degradation curves in the dashboard.

```bash
py -m cli.main run examples/advanced_suite.yaml
```

### Compare two runs

```bash
py -m cli.main compare examples/suite.yaml examples/advanced_suite.yaml
```

---

## CLI reference

```
py -m cli.main run SUITE_FILE [--db PATH] [--models a,b] [--output rich|json]
py -m cli.main compare BASELINE CANDIDATE [--db PATH] [--output rich|json]
py -m cli.main cleanup-runs [--db PATH] [--stale-only] [--all]
```

### cleanup-runs

Remove stale or all local benchmark runs from DuckDB:

```bash
# Safe: remove only runs with no result data (e.g. left over from schema migrations)
py -m cli.main cleanup-runs --stale-only

# Nuclear: remove all local run data
py -m cli.main cleanup-runs --all
```

---

## Web dashboard

```bash
# Terminal 1 -- backend
py -m uvicorn api.main:app --reload

# Terminal 2 -- frontend
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

Sidebar navigation:
- Dashboard -- returns to the main view
- API Docs -- opens FastAPI Swagger UI at http://127.0.0.1:8000/docs in a new tab
- Settings -- not yet implemented (shown as disabled)

---

## Writing a test suite

```yaml
suite:
  name: "My RAG Suite"

models:
  - claude-haiku-4-5-20251001
  - gpt-4o-mini

judge_model: claude-haiku-4-5-20251001
parallel_workers: 3
db_path: "./data/results.duckdb"
failure_threshold: 0.5

defaults:
  system_prompt: |
    You are a helpful assistant. Always cite sources using [1], [2] format.

test_cases:
  - name: "citation_in_long_context"
    failure_category: instruction_loss
    perturbation: instruction_burial
    perturbation_config:
      depth: 0.85
      padding_count: 6
    query: "What was Q3 revenue?"
    expected_behavior: "Must include citation markers [1] or [2]"
    # Add context_depth_levels to populate the degradation curve
    context_depth_levels: [0.25, 0.5, 0.75, 1.0]
    chunks:
      - "Q3 revenue was .2B, up 15% YoY."
      - "Operating margin reached 24%."
    validators:
      - type: contains_pattern
        pattern: "\[\d+\]"
        description: "Citation markers required"
```

### context_depth_levels

When a test case includes context_depth_levels, the runner re-executes it at each
fraction of the full chunk list (0.25 = first 25% of chunks). Scores are stored in
the depth_scores table and surface as the degradation curve in the dashboard.

### Perturbation types

| Value | What it does |
|---|---|
| chunk_shuffle | Reorders chunks randomly |
| distractor_injection | Injects irrelevant filler chunks |
| conflicting_evidence | Injects a chunk that contradicts another |
| instruction_burial | Pushes key instructions deep into context |
| history_contamination | Injects false turns into conversation history |
| paraphrase_evidence | Rewrites chunks with synonyms |

---

## How evaluation works

Every test runs deterministic rules first. The LLM judge is only called when the
deterministic score is in the ambiguous band [threshold-0.2, threshold+0.2]
(default [0.3, 0.7]). This keeps judge API costs low on typical suites.

---

## Testing

```bash
py -m pytest
```

---

## Limitations

- Included examples use synthetic data and are not suitable for comparing real production workloads.
- Cost tracking is estimated from a static pricing table in core/runner.py.
- Degradation curves only appear for test cases with context_depth_levels configured.
  The basic suite.yaml does not include them; advanced_suite.yaml does.
