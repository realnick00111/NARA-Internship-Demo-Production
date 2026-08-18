# Repository Agent Guidance

## Testing

- Use `venv\Scripts\python.exe`; the system `python` may be unavailable.
- Start with a focused test: `venv\Scripts\python.exe -m pytest path\to\test.py::Class::test_name -q`.
- Use `-q --tb=short` for focused groups and `--tb=line` for minimal failures. Run the full suite after the focused slice passes.
- Assert targeted rendered markers or concise booleans; avoid assertions that dump full HTML.

## Live UI State

- For Flask pages using `fetch()` or AJAX, saving to the database does not update the existing DOM. Synchronize every visible dependent value immediately, or re-fetch the affected component.
- When adding backend context to an existing template, replace hard-coded display values and wire both initial rendering and post-save updates.
- Test UI workflows without refreshing: perform the user action and verify progress, summaries, badges, and navigation update immediately, then verify the same state after a reload.
- Prefer API responses that return updated calculated state so the frontend can render authoritative values.
