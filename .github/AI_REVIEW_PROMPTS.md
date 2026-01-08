# AI-Assisted Code Review Prompts

This file provides prompts for AI-assisted code review during ScholarFlux development. These are **review tools**, not authorship shortcuts.

## Philosophy

AI assistance in ScholarFlux development is encouraged for:
- Planning and architecture discussions
- Test gap analysis and edge-case discovery
- Linting, type checking, and documentation verification
- Code review before submission

AI assistance is **not** a substitute for understanding your changes. If you generate code with AI, you take full responsibility to:
- Understand how the metaphorical tree (tool/feature) fits and contributes to the forest (package architecture)
- Understand every line before committing
- Clean up and refactor to match project patterns (docstrings/ruff/mypy)
- Account for all edge cases
- Ensure that tests cover all new code paths

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution guidelines.

---

## Review Prompts

### Test Gap Analysis

Use when adding new functionality or modifying existing code to identify missing test coverage.

```
Analyze the provided code for untested edge cases and missing test coverage.

ANALYSIS SCOPE:

1. **Boundary conditions** - Empty inputs, None values, zero/negative numbers
2. **Error paths** - Exception handling branches, invalid inputs
3. **State transitions** - Cache hits/misses, retry logic, connection states
4. **Concurrency concerns** - Race conditions, timeout scenarios
5. **Integration points** - API failures, malformed responses, rate limits

OUTPUT FORMAT:

For each gap identified:

```python
# test_<module>.py

def test_<descriptive_name>():
    """<What this tests and why it matters>."""
    # Arrange
    ...
    # Act
    ...
    # Assert
    ...
```

PRIORITIZATION:
- Flag gaps by severity: CRITICAL (data loss/security), HIGH (broken functionality), MEDIUM (edge cases)
- Focus on paths that could fail silently in production
- Skip trivial getters/setters unless they contain logic

If coverage appears comprehensive: "No significant test gaps identified."
```

---

### API Breaking Change Check

Use before releases or when modifying public interfaces to identify changes requiring documentation.

```
Compare the provided code versions and identify breaking changes for the CHANGELOG.

BREAKING CHANGES (must document):

1. **Removed** - Public functions, classes, methods, or parameters deleted
2. **Renamed** - Public API symbols changed
3. **Signature changes** - Required parameters added, parameter order changed
4. **Type changes** - Return type or parameter type modified
5. **Behavior changes** - Same signature but different semantics
6. **Default changes** - Default parameter values modified

NON-BREAKING (note but don't flag):
- New optional parameters with defaults
- New public functions/classes
- Internal/private changes (underscore prefix)
- Documentation-only changes

OUTPUT FORMAT:

## Breaking Changes

### Removed
- `function_name()` - <brief context if helpful>

### Changed
- `function_name(old_sig)` → `function_name(new_sig)`
  - Migration: <one-line upgrade instruction>

### Behavior Changes
- `function_name()` - <what changed and why it matters>

---

If no breaking changes: "No breaking changes detected."
```

---

### Type Hint Audit

Use to verify type hint correctness and completeness before submitting changes.

```
Audit Python type hints for correctness and completeness.

CHECK FOR:

1. **Missing hints** - Untyped function signatures in public API
2. **Any overuse** - Flag `Any` that could be more specific
3. **Incorrect hints** - Types that don't match runtime behavior
4. **Generic specificity** - `list` vs `list[str]`, `dict` vs `dict[str, int]`
5. **Optional correctness** - `Optional[X]` vs `X | None` consistency, missing None returns
6. **Protocol/ABC usage** - Opportunities to use `Sequence`, `Mapping`, `Iterable` over concrete types

IGNORE:
- Private methods (single underscore) unless part of documented API
- Test files
- Type: ignore comments (assume intentional)

OUTPUT FORMAT:

<filename>.py
============

Line <N>: `<current signature>`
Issue: <brief explanation>
Suggested: `<corrected signature>`

---

SUMMARY:
- Missing hints: <count>
- Any usage: <count>
- Incorrect hints: <count>

If all hints are correct: "Type hints verified. No changes needed."
```

---

## Project-Specific Context

When using these prompts, provide relevant context:

- **Style**: Google-style docstrings, 120 character line limit
- **Types**: mypy strict mode, all public functions typed
- **Testing**: pytest with 97% coverage target, mocked API responses
- **Patterns**: Dependency injection, Pydantic models for validation

For full project standards, see [CONTRIBUTING.md](../CONTRIBUTING.md).
