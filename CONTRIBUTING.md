# Contributing to LLM Guard Bench

Thank you for your interest in contributing to **LLM Guard Bench**! This document provides guidelines and instructions for participating in this open-source security research project.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Types of Contributions](#types-of-contributions)
4. [Submission Guidelines](#submission-guidelines)
5. [Commit Message Standards](#commit-message-standards)
6. [Pull Request Process](#pull-request-process)

---

## Code of Conduct

By participating in this project, you agree to:

- **Respect all contributors** regardless of background, experience level, or identity
- **Report vulnerabilities responsibly** (see [Security Policy](#security-vulnerabilities))
- **Keep discussions technical and focused** on improving the framework
- **Avoid sharing sensitive data** (API keys, private models, personal information)
- **Respect intellectual property** of tested models and their owners

---

## Getting Started

### 1. Fork & Clone

```bash
# Fork the repository on GitHub (click "Fork" button)
git clone https://github.com/<your-github-username>/llm-guard-bench.git
cd llm-guard-bench
git remote add upstream https://github.com/original-author/llm-guard-bench.git
```

> **Note:** Replace `<your-github-username>` with your actual GitHub username and update the upstream URL to match the main repository.

### 2. Create a Feature Branch

```bash
# Always branch from main
git checkout main
git pull upstream main

# Create descriptive branch name (see Commit Standards section)
git checkout -b feature/new-attack-vector
# or
git checkout -b bugfix/timeout-protection
# or
git checkout -b refactor/async-pipeline
```

### 3. Set Up Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows

# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio black flake8

# Run tests to verify setup
python -m pytest
```

### 4. Make Your Changes

- Follow the existing code style (see below)
- Add tests for new functionality
- Update documentation as needed
- Keep commits atomic and focused

### 5. Run Tests & Validation

```bash
# Run entire test suite
python -m pytest

# Run specific test
python -m pytest tests/test_orchestration.py::test_database_lifecycle

# Check code style
black llm-guard-bench/
flake8 llm-guard-bench/

# Run the full benchmark
python llm-guard-bench/main.py
```

---

## Types of Contributions

### 🎯 New Attack Vectors

**Priority: High** | **Complexity: Medium** | **Review Time: 1-2 weeks**

Add novel adversarial attack prompts to benchmark against LLM robustness.

**How to contribute:**

1. Edit `llm-guard-bench/config/prompts.json`:

```json
{
  "id": "your_attack_id",
  "category": "prompt_injection|jailbreak|data_extraction|...",
  "prompt": "Your adversarial prompt here...",
  "description": "Brief explanation of attack mechanism",
  "severity": "low|medium|high",
  "references": ["Paper link or CVE if applicable"]
}
```

2. Create a corresponding test case in `tests/test_attacks.py`:

```python
def test_attack_your_attack_id():
    """Verify new attack loads and executes correctly."""
    attack = load_attack('your_attack_id')
    assert attack is not None
    assert attack.category == 'prompt_injection'
    # Additional assertions...
```

3. Document the attack's motivation:
   - Academic paper reference (if applicable)
   - Real-world vulnerability it simulates
   - Expected defender behavior
   - Why this vector strengthens the benchmark

4. Submit PR with:
   - ✅ Passing tests
   - ✅ Documentation in PR description
   - ✅ Link to relevant research (if available)

**Example PR Title:**

```
feat: Add prompt injection attack vector #42
```

**Example PR Description:**

```
Closes #42

## Description
Implements a novel multi-stage prompt injection attack that exploits role-playing
escape sequences in LLM system prompts.

## Reference
- Paper: "Prompt Injection Attacks on GPT-3" (arXiv:2208.12496)
- Category: prompt_injection
- Severity: high

## Testing
- [x] Attack definition loads correctly
- [x] Benchmark executes without timeout
- [x] Results persisted to SQLite and JSONL
- [x] Chart generation includes new attack

## Files Changed
- config/prompts.json (added 1 attack vector)
- tests/test_attacks.py (added test_attack_multi_stage_injection)
```

---

### 🔧 Bug Fixes & Performance Improvements

**Priority: Medium** | **Complexity: Low-Medium** | **Review Time: 3-7 days**

Report and fix issues discovered during benchmark execution.

**How to contribute:**

1. **Report in GitHub Issues first** (don't submit PR without discussion)
   - Describe the bug with full reproduction steps
   - Include error messages and stack traces
   - Attach relevant logs or database queries

2. **For performance improvements:**
   - Run benchmarks before/after (include timings)
   - Ensure no accuracy regression
   - Document async safety (timeouts, error handling)

3. **Submit PR with:**
   - ✅ Reference to issue number (`Fixes #123`)
   - ✅ Before/after test results
   - ✅ Updated error handling if applicable
   - ✅ All existing tests passing

**Example PR Title:**

```
fix: resolve database timeout in aggregator
perf: optimize batch query execution by 40%
```

---

### 🎓 New Adapters & Evaluation Methods

**Priority: Medium** | **Complexity: High** | **Review Time: 2-4 weeks**

Implement support for new target models (beyond Ollama) or judge LLMs (beyond Groq).

**How to contribute:**

1. **Create new adapter in `llm-guard-bench/core/adapters.py`:**

```python
class YourNewAdapter(BaseAdapter):
    """Adapter for YourModel API."""

    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key

    async def generate(self, prompt: str) -> str:
        """Generate response from target model."""
        # Implementation with 30s timeout protection
        response = await asyncio.wait_for(
            self._call_api(prompt),
            timeout=180.0
        )
        return response

    async def health_check(self) -> bool:
        """Verify adapter connectivity."""
        # Implementation
        return True
```

2. **Register in `llm-guard-bench/core/pipeline.py`:**

```python
# In run_benchmark() method
self.target_adapter = YourNewAdapter(
    endpoint=os.getenv('YOUR_ENDPOINT'),
    api_key=os.getenv('YOUR_API_KEY')
)
```

3. **Add comprehensive tests:**

```python
@pytest.mark.asyncio
async def test_your_adapter_generates_response():
    adapter = YourNewAdapter(endpoint='...', api_key='...')
    assert await adapter.health_check()
    response = await adapter.generate("test prompt")
    assert isinstance(response, str)
    assert len(response) > 0

@pytest.mark.asyncio
async def test_your_adapter_timeout_protection():
    adapter = YourNewAdapter(endpoint='...', api_key='...')
    # Verify 30s timeout works correctly
```

4. **Submit PR with:**
   - ✅ New adapter class with full error handling
   - ✅ Comprehensive test coverage (>80% lines)
   - ✅ Documentation of API keys / environment variables
   - ✅ Performance benchmarks (latency, cost per call)
   - ✅ Comparison with existing adapters

---

### 📖 Documentation & Examples

**Priority: Low-Medium** | **Complexity: Low** | **Review Time: 2-5 days**

Improve documentation, add examples, or clarify existing guides.

**How to contribute:**

- Add usage examples to README.md
- Create tutorials (e.g., "Adding Custom Attack Vectors")
- Improve API documentation with docstrings
- Add troubleshooting guide
- Translate documentation (other languages welcome)
- Create academic paper templates citing this framework

**Example PR Title:**

```
docs: add example for querying results across multiple sessions
docs: clarify adapter implementation requirements
```

---

## Submission Guidelines

### Issue Reporting

**Before submitting code, open a GitHub Issue to discuss:**

1. **Bug Reports** – Include:
   - Python version and OS
   - Exact reproduction steps
   - Expected vs. actual behavior
   - Full error trace (from console or logs)
   - Relevant code snippet (if applicable)

2. **Feature Requests** – Include:
   - Clear use case and motivation
   - How it aligns with LLM security research
   - Sketch of proposed implementation
   - Potential impact on existing code

3. **Security Vulnerabilities** – Do NOT open public issue:
   - Email maintainer privately
   - Include severity assessment
   - Provide proof-of-concept
   - Allow 90 days for patching before disclosure

### Code Style Guide

**Python Style:** Follow [PEP 8](https://pep8.org/) with Black formatter

```bash
# Auto-format your code
black llm-guard-bench/

# Check compliance
flake8 llm-guard-bench/
```

**Docstring Format:** Google-style docstrings for all public functions

```python
def calculate_metrics(results: List[TestResult]) -> MetricsSummary:
    """Calculate aggregate metrics from test results.

    Args:
        results: List of TestResult objects from benchmark execution.

    Returns:
        MetricsSummary with vulnerability rates, pass rates, and timings.

    Raises:
        ValueError: If results list is empty.
        TypeError: If results contains non-TestResult objects.

    Example:
        >>> results = [TestResult(...), TestResult(...)]
        >>> metrics = calculate_metrics(results)
        >>> print(f"Pass rate: {metrics.pass_rate:.2%}")
    """
    if not results:
        raise ValueError("Results list cannot be empty")
    # Implementation...
```

**Type Hints:** Always use type hints for function signatures

```python
async def run_benchmark(
    attacks: List[AttackDefinition],
    target_adapter: BaseAdapter,
    judge_adapter: BaseAdapter
) -> BenchmarkResults:
    """Execute benchmark suite against target model."""
    pass
```

---

## Commit Message Standards

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

- **feat**: New feature or attack vector
- **fix**: Bug fix or issue resolution
- **perf**: Performance optimization
- **refactor**: Code restructuring without behavior change
- **test**: Adding or updating tests
- **docs**: Documentation changes
- **ci**: CI/CD pipeline changes
- **chore**: Dependency updates, cleanup

### Scope

- **config**: Configuration files (prompts.json, settings)
- **core**: Core orchestration (pipeline, adapters, evaluator)
- **db**: Database layer (schema, migrations)
- **analysis**: Aggregation and visualization
- **ci**: Continuous integration (GitHub Actions, batch scripts)
- **test**: Test suite

### Subject

- Use imperative mood: "add" not "adds" or "added"
- Don't capitalize first letter
- No period at end
- Limit to 50 characters

### Body

- Explain **what** and **why**, not how
- Wrap at 72 characters
- Separate from subject with blank line
- Reference issue numbers: `Fixes #123`

### Footer

Include metadata:

```
Fixes #123
Co-authored-by: Name <email@example.com>
Reviewed-by: Maintainer <email@example.com>
```

### Examples

```
feat(config): add jailbreak attack vector for role-playing escape

Add a novel attack that exploits role-playing prompts to escape LLM
guardrails. Implements multi-stage prompt injection technique from
"Prompt Injection Attacks" (arXiv:2208.12496).

Category: jailbreak
Severity: high
Fixes #42

---

fix(core): resolve database timeout in aggregator

Wrap database queries in 15-second timeout using asyncio.wait_for().
Previously, slow queries could hang chart generation indefinitely.

Metrics now computed from JSON fallback if DB query times out.

Fixes #18
Reviewed-by: Maintainer <maintainer@example.com>

---

perf(core): optimize concurrent attack execution by 30%

Increase semaphore limit from 2 to 5 concurrent tasks. Benchmarks
show 30% reduction in total execution time (150s → 105s) without
increasing API rate limit errors.

Verified with 3 consecutive benchmark runs.

---

test(analysis): add chart generation timeout test

Ensure matplotlib chart generation respects 60-second timeout limit
and fails gracefully with error logged (not silent failure).

New test: test_chart_generation_timeout_protection()
```

---

## Pull Request Process

### 1. Before Submitting

- ✅ Create branch from `main` (not from older versions)
- ✅ Keep changes focused (one feature per PR)
- ✅ Run `black` and `flake8` on your code
- ✅ Run full test suite: `pytest`
- ✅ Update documentation and docstrings
- ✅ Add tests for new functionality (>80% coverage)

### 2. Create Pull Request

**Title Format:**

```
[type]([scope]): brief description

Examples:
- [feat][config]: add prompt injection attack vector
- [fix][core]: resolve async timeout deadlock
- [perf][db]: optimize query execution
```

**Description Template:**

```markdown
## Description

[Brief overview of changes]

## Type of Change

- [ ] New attack vector
- [ ] Bug fix
- [ ] Performance improvement
- [ ] New adapter/integration
- [ ] Documentation update
- [ ] Other: \_\_\_

## Related Issue

Closes #[issue_number]

## How to Test

[Reproduction steps or testing instructions]

## Testing Checklist

- [ ] All tests pass locally (`pytest`)
- [ ] No code style violations (`black`, `flake8`)
- [ ] Added/updated tests for new functionality
- [ ] Updated relevant documentation
- [ ] Tested with both SQLite and JSON fallback paths
- [ ] Verified timeout protection works correctly
- [ ] No new warnings or errors introduced

## Performance Impact

[Any changes to execution time, memory usage, API calls?]

## Security Implications

[Any security considerations?]

## Screenshots (if applicable)

[Chart generations, error logs, etc.]
```

### 3. Code Review Process

- **Initial Review**: Maintainer checks for:
  - Alignment with project goals
  - Code quality and style compliance
  - Test coverage and passing tests
  - Documentation completeness

- **Feedback Cycle**: If changes requested:
  - Push new commits to same branch (don't rebase)
  - Reply to comments in PR discussion
  - Re-request review when ready

- **Approval**: PR merged after:
  - ✅ All feedback addressed
  - ✅ At least one approval from maintainer
  - ✅ All CI checks passing
  - ✅ No conflicting branches

### 4. After Merge

- Your contribution is now part of LLM Guard Bench!
- You'll be added to [CONTRIBUTORS.md](#) if you contribute more than once
- Follow the project for future developments

---

## Recognition

We celebrate all contributions! Contributors will be:

- **Listed in CONTRIBUTORS.md** with GitHub profile links
- **Mentioned in release notes** for significant features
- **Featured in project README** for major research contributions
- **Eligible for co-authorship** on academic papers citing this framework

---

## Questions?

- **GitHub Issues**: Technical questions, feature requests
- **GitHub Discussions**: General questions, ideas
- **Email**: Contact maintainer directly for sensitive matters

---

## Thank You! 🙏

Your contributions help advance open-source LLM security research and make this framework more robust for the entire community. We appreciate your time and expertise!

---

**Last Updated:** 2026-05-26  
**Maintained By:** Md Eaftekhirul Islam
