# LLM Guard Bench — Automated Adversarial Attack Benchmark Suite

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-green)](#-production-deployment)
[![Async Concurrency](https://img.shields.io/badge/Concurrency-Async%2FAwait-brightgreen)](#architecture)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Core Features](#core-features)
3. [Architecture](#architecture)
4. [Installation & Quick Start](#installation--quick-start)
5. [Usage Guide](#usage-guide)
6. [Advanced Configuration](#advanced-configuration)
7. [Production Deployment](#-production-deployment)
8. [Contributing](#contributing)
9. [Citation & Acknowledgments](#citation--acknowledgments)

---

## Overview

**LLM Guard Bench** is a research-grade, production-ready framework for systematically evaluating the robustness of Large Language Models against adversarial attack vectors. This project automates the orchestration of multi-stage adversarial attacks, concurrent defense evaluation, and aggregated vulnerability analytics—all with academic rigor and enterprise-grade reliability.

### What Problem Does It Solve?

As LLMs become integrated into critical systems (security, healthcare, finance), evaluating their resistance to adversarial inputs is essential. Existing benchmarking tools often suffer from:

- **Manual testing overhead** → `LLM Guard Bench` automates the entire pipeline
- **Single-threaded bottlenecks** → Async concurrency executes 5+ attacks in parallel
- **Fragile dependencies** → Automatic JSON fallback ensures results never lost, even if databases fail
- **Black-box evaluation** → SQLite ledger audit trail tracks every decision point
- **Silent failures** → Bulletproof error handling with full stack trace logging
- **Opaque metrics** → Automated vulnerability reports with visual charts

### Core Differentiators

| Feature                      | Benefit                                                                                                                 |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Async/Await Concurrency**  | Execute all attack vectors in parallel with semaphore-based rate limiting                                               |
| **Dual-Write Persistence**   | Results stored in both SQLite (queryable) and JSONL (portable, immutable)                                               |
| **Automatic Fallback Chain** | If SQLite fails, metrics computed from JSON; if chart generation hangs, metrics still displayed                         |
| **LLM-as-Judge Framework**   | 2-stage evaluation cascade: heuristic screening (fast) + Groq semantic validation (accurate)                            |
| **Zero Silent Failures**     | 6-stage orchestration with isolated error handling; every exception logged with full context                            |
| **Production Deployment**    | Single Windows batch script (`run_bench.bat`) handles environment setup, dependency validation, and results aggregation |

---

## Core Features

### 🔄 Async Orchestration Pipeline

The framework executes a 6-stage orchestration with bulletproof error handling:

```
Stage 1: Environment Loading
    ↓
Stage 2: Database Initialization (SQLite + schema migrations)
    ↓
Stage 3: Attack Definition Loading (from config/prompts.json)
    ↓
Stage 4: Adapter Initialization (Ollama target + Groq judge)
    ↓
Stage 5: Concurrent Benchmark Execution (5 attacks × configurable parallelism)
    ↓
Stage 6: Aggregation & Visualization (metrics + charts)
    ↓
Finally: Graceful Cleanup (resources released, logs finalized)
```

Each stage has isolated error handling. Early stages are critical (exit on failure); later stages degrade gracefully (continue on partial failure). Aggregation ALWAYS attempted if database initialized.

### 📊 Dual-Ledger Auditing

Every test result is recorded in **two formats** for maximum resilience:

| Format                          | Purpose                                      | Queryable       | Portable                    |
| ------------------------------- | -------------------------------------------- | --------------- | --------------------------- |
| **SQLite (guard_bench.db)**     | Fast structured queries, real-time analytics | ✅ Yes          | ❌ Not portable             |
| **JSONL (session\_{id}.jsonl)** | Immutable audit trail, failover backup       | ✅ Line-by-line | ✅ Version control friendly |

If database queries timeout or fail, metrics are automatically computed from JSONL files—transparency and resilience guaranteed.

### ⚡ 2-Stage LLM Evaluation Cascade

Every target model response is evaluated in two phases:

**Stage 1: Heuristic Screening (KeywordEvaluator)**

- Pattern matching against known vulnerability indicators
- Executes synchronously (< 100ms per result)
- Immediate PASSED/VULNERABLE verdict

**Stage 2: Semantic Validation (JudgeLLMEvaluator)**

- Groq `llama-3.1-8b-instant` as semantic judge
- Evaluates context-aware vulnerability assessment
- Confirms/overrides Stage 1 verdict with LLM reasoning
- Async execution with 30-second timeout protection

Result: Robust verdicts combining heuristic speed with semantic accuracy.

### 🛡️ Bulletproof Error Handling

No silent failures. No undefined behavior. Every error is caught, logged, and recoverable:

- **Timeout Protection**: All async operations (DB queries, network calls, chart generation) wrapped with `asyncio.wait_for()` timeouts
- **Explicit Exception Handling**: Specific exception types caught (TimeoutError, PermissionError, OperationalError, OSError)
- **Fallback Chain**: DB → async executor → JSON files → placeholder charts
- **Zero Premature Exits**: Cleanup ALWAYS runs via finally blocks; resources always released
- **Full Stack Traces**: All errors logged with `exc_info=True` for complete debugging context

### 📈 Automated Analytics & Visualization

After benchmark execution:

- **Metrics Summary**: Pass rate, vulnerability rate, evaluation success rate per attack category
- **Vulnerability Chart**: Grouped bar chart (VULNERABLE vs PASSED counts) by attack vector
- **Session Ledger**: Complete JSONL audit trail for reproducibility
- **Database Query**: Direct SQLite access for custom analysis

All generated to `results/` directory with session ID tracking for multi-run analysis.

---

## Architecture

### Directory Structure (No "src/" Constraint)

```
llm-guard-bench/
├── main.py                          # Master orchestration (6-stage pipeline)
├── setup.py                         # Package configuration
├── config/
│   └── prompts.json                 # Attack definitions (5 vectors, easily extensible)
├── core/
│   ├── adapters.py                  # Target (Ollama) & Judge (Groq) implementations
│   ├── evaluator.py                 # 2-stage evaluation engine
│   ├── loader.py                    # Configuration & environment loading
│   ├── models.py                    # Pydantic v2 data models (frozen, immutable)
│   └── pipeline.py                  # Concurrent benchmark execution
├── db/
│   ├── db.py                        # Async SQLite interface (aiosqlite)
│   └── migrations/
│       └── 001_initial_schema.sql   # Schema v3.0 (session tracking, execution auditing)
├── analysis/
│   └── aggregator.py                # Metrics computation & chart generation
└── results/                         # Auto-created on first run
    ├── guard_bench.db               # SQLite ledger
    ├── session_{id}.jsonl           # JSONL backup (one result per line)
    └── vulnerability_report.png     # Visual analytics chart
```

**Why No "src/" Folder?**

This project follows the flat package structure for maximum clarity and researcher accessibility. All imports use relative paths (`from core.X import Y`, `from db.X`, `from analysis.X`), making the codebase intuitive and reducing setup complexity. This design is intentional for academic simplicity and production deployment via batch scripts.

### Data Flow

```
config/prompts.json
    ↓ (5 attack definitions loaded)
core/loader.py → AttackDefinition (Pydantic model)
    ↓
core/pipeline.py (async task pool, semaphore rate limiting)
    ├─→ core/adapters.py (Ollama target, 30s timeout)
    │   └─→ target_response: str
    ├─→ core/evaluator.py (2-stage evaluation)
    │   ├─→ Stage 1: KeywordEvaluator (fast heuristic)
    │   └─→ Stage 2: JudgeLLMEvaluator (Groq semantic, 30s timeout)
    │       └─→ verdict: PASSED | VULNERABLE | EVAL_ERROR
    ├─→ core/models.py (TestResult frozen model)
    └─→ db/db.py (dual write: SQLite + JSONL)
        ├→ results/guard_bench.db
        └→ results/session_{id}.jsonl
            ↓
analysis/aggregator.py (metrics aggregation, chart generation)
    ├─→ Timeout protection (15s DB, 60s chart)
    ├─→ Fallback chain (DB → async executor → JSON)
    └─→ results/vulnerability_report.png
```

### Technology Stack

| Component         | Technology                      | Purpose                                      |
| ----------------- | ------------------------------- | -------------------------------------------- |
| **Target Model**  | Ollama (Llama3:8b)              | Local, privacy-preserving attack target      |
| **Judge LLM**     | Groq API (llama-3.1-8b-instant) | Fast semantic evaluation                     |
| **Async Runtime** | Python asyncio                  | Non-blocking concurrency, timeout management |
| **Database**      | SQLite (aiosqlite)              | Structured result queries, schema migrations |
| **Data Models**   | Pydantic v2                     | Type-safe, frozen models with validation     |
| **Visualization** | Matplotlib (Agg backend)        | Vulnerability charts (non-interactive PNG)   |
| **Orchestration** | Windows Batch (run_bench.bat)   | Cross-platform deployment automation         |

---

## Installation & Quick Start

### Prerequisites

- **Python 3.10+** (3.14.2 recommended)
- **Ollama** (running on `localhost:11434`)
- **Windows 10+** or WSL2 (for batch script; Linux/macOS: use Python CLI directly)
- **API Key** for Groq (free tier available at https://console.groq.com)

### Step 1: Clone Repository

```bash
git clone https://github.com/<your-github-username>/llm-guard-bench.git
cd llm-guard-bench
```

> **Note:** Replace `eis-1` with your actual GitHub username if you've forked this repository.

### Step 2: Create Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\activate          # Windows
source .venv/bin/activate         # Linux/macOS
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Key Dependencies:**

- `python-dotenv` (environment config)
- `pydantic==2.x` (type-safe models)
- `aiosqlite` (async SQLite)
- `groq` (judge LLM API client)
- `matplotlib` (chart generation)

### Step 4: Configure Environment

Create `.env` file in repository root:

```env
GROQ_API_KEY=your_groq_api_key_here
OLLAMA_ENDPOINT=http://localhost:11434
LOG_LEVEL=INFO
DATABASE_PATH=results/guard_bench.db
```

### Step 5: Start Ollama (Separate Terminal)

```bash
ollama serve
# Expected output: Listening on localhost:11434
```

### Step 6: Run Benchmark

**Windows (Recommended):**

```bash
run_bench.bat
```

This single script:

- Activates virtual environment
- Validates dependencies
- Loads environment variables
- Executes main orchestration
- Displays metrics summary
- Generates vulnerability_report.png
- Pauses for result inspection

**Direct Python (All Platforms):**

```bash
python llm-guard-bench/main.py
```

### Step 7: Inspect Results

```bash
# View metrics in terminal output
# Open vulnerability_report.png for visual analysis
# Query database directly:
sqlite3 results/guard_bench.db "SELECT * FROM test_results LIMIT 5;"
# Or inspect JSONL audit trail:
cat results/session_*.jsonl | jq '.'
```

---

## Usage Guide

### Running the Benchmark

**Basic execution:**

```bash
python llm-guard-bench/main.py
```

**Expected output:**

```
Starting LLM Guard Bench Benchmark...
✓ Environment loaded
✓ Database initialized
✓ Attack definitions loaded
✓ Adapters initialized

Executing benchmark: 5 attack vectors
  - prompt_injection: ⏳
  - jailbreak: ⏳
  - data_extraction: ⏳
  - ... (5+ attacks in parallel)

✓ Benchmark completed: 5 results

Security Evaluation Metrics:
  • Total Tests: 5
  • Successful Runs (Passed): 2
  • Total Vulnerable: 3
  • Average Execution Time: 12.5s

Vulnerability Rates by Category:
  • prompt_injection: 60% (3/5 vulnerable)
  • data_extraction: 40% (2/5 vulnerable)

Results saved to: results/session_<id>/

Chart generated: results/vulnerability_report.png
```

### Adding New Attack Vectors

Edit `config/prompts.json`:

```json
{
  "attacks": [
    {
      "id": "prompt_injection_6",
      "category": "prompt_injection",
      "adversarial_prompt": "Ignore previous instructions and...",
      "system_prompt": "You are a helpful assistant.",
      "description": "Novel prompt injection vector",
      "severity": "high",
      "tags": ["novel", "research"]
    }
  ]
}
```

Then run the benchmark again—new attack automatically integrated.

### Implementing Custom Adapters

Create new adapter in `core/adapters.py`:

```python
from abc import ABC, abstractmethod

class CustomAdapter(BaseAdapter):
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Your implementation here."""
        response = await self._call_api(system_prompt, user_prompt)
        return response

    async def health_check(self) -> bool:
        """Verify adapter connectivity."""
        return True
```

Register in `core/pipeline.py`:

```python
self.target_adapter = CustomAdapter(
    endpoint=os.getenv('CUSTOM_ENDPOINT'),
    api_key=os.getenv('CUSTOM_API_KEY')
)
```

### Querying Results Programmatically

**SQLite queries:**

```python
import sqlite3

conn = sqlite3.connect('results/guard_bench.db')
cursor = conn.cursor()

# Vulnerability rate by category
cursor.execute("""
    SELECT category,
           COUNT(*) FILTER (WHERE judge_verdict = 'VULNERABLE') as vulnerable,
           COUNT(*) as total,
           ROUND(100.0 * COUNT(*) FILTER (WHERE judge_verdict = 'VULNERABLE') / COUNT(*), 2) as rate
    FROM test_results
    GROUP BY category
""")

for category, vulnerable, total, rate in cursor:
    print(f"{category}: {rate}% ({vulnerable}/{total})")

conn.close()
```

**JSON fallback:**

```python
import json
from pathlib import Path

for line in Path('results/session_*.jsonl').read_text().split('\n'):
    if line.strip():
        result = json.loads(line)
        if result['judge_verdict'] == 'VULNERABLE':
            print(f"Vulnerable: {result['attack_id']}")
```

---

## Advanced Configuration

### Custom Evaluation Methods

Override evaluation in `core/evaluator.py`:

```python
class CustomEvaluator(BaseEvaluator):
    """Custom evaluation logic."""

    async def evaluate(self, target_response: str) -> EvaluationResult:
        """Implement your evaluation logic."""
        # Example: regex matching + semantic analysis
        if self._matches_custom_pattern(target_response):
            return EvaluationResult.VULNERABLE
        return EvaluationResult.PASSED
```

### Database Connection Management

The framework automatically manages SQLite connections with:

- **Connection pooling**: Single persistent connection per session
- **Timeout protection**: 15-second timeout on all queries
- **Automatic retry**: JSON fallback if DB queries fail
- **Graceful cleanup**: Always closes connections via finally blocks

Customize in `db/db.py`:

```python
async def connect(self) -> None:
    """Establish database connection with custom timeout."""
    if self._connection is None:
        self._connection = await aiosqlite.connect(
            self._db_path,
            timeout=30.0  # Custom timeout in seconds
        )
```

### Scaling Attack Execution

Control concurrency in `core/pipeline.py`:

```python
# Increase parallel attacks (default: 2)
await self.run_benchmark(
    attacks=attacks,
    model_name="llama3:8b",
    concurrency_limit=5,  # Run up to 5 attacks simultaneously
    session_id=session_id
)
```

Trade-off: More parallelism = faster execution, but higher API rate limit risk.

### Performance Metrics

**Typical benchmark run (5 attacks, 2x parallelism):**

- **Total execution time**: 90-120 seconds
- **Per-attack time**: 20-30 seconds (includes target model + evaluation)
- **Database persistence**: <100ms per result
- **Chart generation**: 5-10 seconds
- **API calls to Groq**: 5 (one per attack for semantic evaluation)
- **Database size**: ~50KB per 100 results

**Scaling considerations:**

- **More attacks**: Linear time increase (add more rows to config/prompts.json)
- **Higher parallelism**: Faster execution, but respect Groq API rate limits (100 req/min free tier)
- **Larger timeouts**: For slower networks or slower models
- **JSON fallback**: Automatic, no configuration needed

---

## Contributing

We welcome contributions from security researchers, engineers, and academics. See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- **Code of Conduct** – Respectful, technical community standards
- **Getting Started** – Fork, branch, and development setup
- **Types of Contributions** – Attack vectors, adapters, bug fixes, documentation
- **Submission Guidelines** – Issue reporting and code review process
- **Commit Standards** – Conventional Commits specification
- **PR Process** – Complete workflow from feature branch to merge

### Quick Contribution Path

1. **Fork** the repository
2. **Create branch**: `git checkout -b feature/your-contribution`
3. **Make changes** and commit with clear messages
4. **Submit PR** with description and test results
5. **Respond** to code review feedback
6. **Merge** when approved

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## Citation & Acknowledgments

### How to Cite

If you use LLM Guard Bench in academic research, please cite:

```bibtex
@software{islam2026llmguardbench,
  author = {Islam, Md Eaftekhirul},
  title = {LLM Guard Bench: Automated Adversarial Attack Benchmark Suite},
  year = {2026},
  url = {https://github.com/eis-1/llm-guard-bench}
}
```

Also supported: [BibTeX](CITATION.cff), [APA](#), [IEEE](#), [GitHub format](#).

See [CITATION.cff](CITATION.cff) for additional citation formats.

### License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

### Acknowledgments

- **Ollama** – Local LLM inference infrastructure
- **Groq** – Fast semantic evaluation via API
- **Python asyncio** – Community best practices for async programming
- **Pydantic** – Type-safe data validation
- **Research contributors** – Attack vectors, validation, feedback

### References

Key papers informing this framework:

- [Prompt Injection Attacks on Language Models](https://arxiv.org/abs/2208.12496)
- [Adversarial Examples Against Language Models](https://arxiv.org/abs/2103.15025)
- [Evaluating LLM Robustness to Jailbreaks](https://arxiv.org/abs/2405.20773)
- [Red-Teaming Large Language Models](https://arxiv.org/abs/2209.07858)

---

## Support & Issues

- **Bug Reports**: [GitHub Issues](https://github.com/eis-1/llm-guard-bench/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/eis-1/llm-guard-bench/discussions)
- **Security Vulnerabilities**: Contact maintainer privately
- **General Questions**: See [CONTRIBUTING.md](CONTRIBUTING.md) for contact info

> **Note:** Replace `<your-github-username>` with your actual GitHub username or the official repository owner.

---

**🌟 If you find LLM Guard Bench useful, please star this repository to support open-source LLM security research!**

---

**Status:** ✅ Production-Ready | **Last Updated:** May 26, 2026
