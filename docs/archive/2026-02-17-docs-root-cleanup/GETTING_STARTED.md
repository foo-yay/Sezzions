# Getting Started with Sezzions

## Quick Start

### 1. Install Dependencies

```bash
cd ./
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Run the App

```bash
python3 sezzions.py
```

By default, the app uses `./sezzions.db` (repo root).

To override the DB path:

```bash
SEZZIONS_DB_PATH=/path/to/your.db python3 sezzions.py
```

### 3. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

### 4. Verify Everything Works

You should see:
- ✅ App launches successfully
- ✅ All tests passing
- ✅ High test coverage (optional)

---
## Development Workflow

```bash
# 1. Make changes to code
# 2. Format code
black .

# 3. Lint
ruff check .

# 4. Run tests
pytest

# 5. Check coverage
pytest --cov=. --cov-report=term-missing
```

---

## Common Commands

```bash
# Run specific test file
pytest tests/unit/test_user_model.py

# Run specific test
pytest tests/unit/test_user_model.py::test_user_creation

# Run with verbose output
pytest -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s
```

## Need Help?

Refer to documentation:
- **[docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md)** - Master spec (recreate Sezzions from scratch)
- **[docs/INDEX.md](docs/INDEX.md)** - Docs index
- **[docs/status/STATUS.md](docs/status/STATUS.md)** - Rolling project status
- **[docs/status/CHANGELOG.md](docs/status/CHANGELOG.md)** - Chronological changelog
- **[docs/TODO.md](docs/TODO.md)** - Optional offline TODO mirror (GitHub Issues are primary)
