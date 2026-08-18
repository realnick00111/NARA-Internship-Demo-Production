# Testing

Use the project virtual environment because the system `python` command may not be available:

```powershell
venv\Scripts\python.exe -m pytest tests\test_facility_identification.py::FacilityIdentificationTests::test_name -q
```

Start with one focused test. For a related group, use `-q --tb=short`; use `--tb=line` when the smallest failure output is preferred. Avoid `-v` during routine runs because it adds test-by-test output. Run the full suite only after the focused slice passes.

Tests that inspect rendered pages should assert targeted markers or use a concise boolean assertion with a custom message. Avoid `assertNotIn` on a large rendered HTML string because its failure output includes the entire page.