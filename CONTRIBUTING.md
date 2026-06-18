# Contributing

Thank you for your interest in contributing to `docling-ocr-lib`! This document outlines the process for contributing.

## Development Setup

```bash
git clone https://github.com/canvascoding/docling-ocr-lib.git
cd docling-ocr-lib
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

For VLM features (picture annotations or VLM pipeline):

```bash
pip install "docling[vlm]"
```

## Workflow

1. **Fork** the repository and create your branch from `main`
2. **Write tests** for your changes — aim to maintain or increase coverage
3. **Ensure code quality**:
   ```bash
   ruff check src/ tests/
   ruff format --check src/ tests/
   pytest
   ```
4. **Update documentation** — README.md, CHANGELOG.md, and docs/plan.md if architecture changes
5. **Submit a Pull Request** with a clear description of what and why

## Code Style

- Python 3.10+
- Ruff for linting and formatting (line-length 120)
- Pydantic v2 for data models
- Type hints required on all public functions
- No comments unless explaining non-obvious logic
- Exceptions inherit from `DoclingOCRError`

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_markdown.py
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add VLM pipeline support for scanned documents
fix: handle float dimensions in PageDimensions
docs: update README with annotation examples
test: add image_utils tests for JPEG fallback
refactor: split page index building into separate method
```

## Reporting Issues

- Use GitHub Issues
- Include: Python version, OS, Docling version, minimal reproduction
- For conversion errors: include the document type and pipeline setting

## License

By contributing, you agree that your contributions will be licensed under the MIT License.