# Getting Started with Sezzions

## Quick Start

### 1. Install Dependencies

```bash
cd sezzions/
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Run the Demo

```bash
python3 demo.py
```

This will:
- Create a demo database
- Create and manage users
- Show all CRUD operations working

### 3. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sezzions --cov-report=html

# View coverage report
open htmlcov/index.html
```

### 4. Verify Everything Works

You should see:
- ✅ Demo script completes successfully
- ✅ All tests passing
- ✅ High test coverage (90%+)

---

## What's Been Completed

### Phase 0: ✅ Complete
- Directory structure created
- Dependencies configured
- Database manager implemented
- Initial schema created

### Phase 1, Week 2: ✅ Complete
- ✅ User model with validation
- ✅ User repository with all CRUD operations
- ✅ User service with business logic
- ✅ Comprehensive unit tests
- ✅ Demo script showing it all works

---

## Next Steps

### Phase 1, Week 3: Sites & Cards

Create the Site and Card domains following the same pattern:

**Site:**
1. `models/site.py` - Site model
2. `repositories/site_repository.py` - Site repository
3. `services/site_service.py` - Site service
4. `tests/unit/test_site_*.py` - Tests

**Card:**
1. `models/card.py` - Card model with `display_name()` method
2. `repositories/card_repository.py` - Card repository
3. `services/card_service.py` - Card service
4. `tests/unit/test_card_*.py` - Tests

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for full specifications.

---

## Development Workflow

```bash
# 1. Make changes to code
# 2. Format code
black sezzions/

# 3. Lint
ruff check sezzions/

# 4. Run tests
pytest

# 5. Check coverage
pytest --cov=sezzions --cov-report=term-missing
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

---

## Project Status

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 0: Setup | ✅ Complete | 100% |
| Phase 1, Week 2: Users | ✅ Complete | 100% |
| Phase 1, Week 3: Sites | 📝 Next | 0% |
| Phase 1, Week 4: Cards | 📝 Planned | 0% |

---

## Need Help?

Refer to documentation:
- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Overall plan
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - OOP patterns
- **[docs/DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md)** - Schema details
- **[docs/MIGRATION_PHASES.md](docs/MIGRATION_PHASES.md)** - Timeline
