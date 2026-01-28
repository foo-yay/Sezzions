# Dependencies and Libraries

## Overview

This document lists all required libraries, tools, and dependencies for the Sezzions OOP migration project, with rationale for each choice.

---

## Core Dependencies

### 1. Python 3.11+
**Purpose:** Base language  
**Why:** Modern type hints, dataclasses, performance improvements  
**Installation:** Already installed (legacy app uses 3.11+)

### 2. PySide6 (Qt for Python)
**Purpose:** Desktop GUI framework  
**Why:** Already used in legacy app, cross-platform, modern  
**Installation:**
```bash
pip install PySide6
```

### 3. SQLite3
**Purpose:** Embedded database (desktop)  
**Why:** Built into Python, zero-config, file-based  
**Installation:** Built-in to Python (no install needed)

### 4. psycopg2-binary
**Purpose:** PostgreSQL adapter  
**Why:** Industry standard for PostgreSQL, needed for web deployment  
**Installation:**
```bash
pip install psycopg2-binary
```

---

## Data & Validation

### 5. pydantic
**Purpose:** Data validation, settings management  
**Why:**
- Runtime type checking for domain models
- Automatic validation on model instantiation
- JSON serialization/deserialization
- Settings management with environment variables

**Installation:**
```bash
pip install pydantic
```

**Usage Example:**
```python
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import date

class Purchase(BaseModel):
    id: int | None = None
    purchase_date: date
    amount: Decimal = Field(gt=0, decimal_places=2)
    sc_received: Decimal = Field(ge=0)
    site_id: int
    user_id: int
    
    @validator('amount')
    def validate_currency(cls, v):
        if v.as_tuple().exponent < -2:
            raise ValueError('Max 2 decimal places')
        return v
```

---

## Database Abstraction

### 6. SQLAlchemy (Optional - Recommended)
**Purpose:** ORM and database abstraction  
**Why:**
- Abstracts SQLite vs PostgreSQL differences
- Migration management built-in (Alembic)
- Query builder prevents SQL injection
- Lazy loading, eager loading, relationship management

**Installation:**
```bash
pip install sqlalchemy alembic
```

**Alternative:** Raw SQL with database abstraction layer (lighter weight, more control)

**Recommendation:** Use SQLAlchemy for this project - it will save significant effort when supporting both SQLite and PostgreSQL.

---

## Testing Framework

### 7. pytest
**Purpose:** Testing framework  
**Why:**
- Industry standard for Python testing
- Fixtures for test data setup
- Parametrized tests for verification
- Coverage reporting integration

**Installation:**
```bash
pip install pytest pytest-cov
```

### 8. pytest-cov
**Purpose:** Code coverage reporting  
**Why:** Track test coverage, aim for 90%+  
**Installation:** Included with pytest-cov above

### 9. pytest-mock
**Purpose:** Mocking framework  
**Why:** Mock database calls for unit tests  
**Installation:**
```bash
pip install pytest-mock
```

---

## Development Tools

### 10. black
**Purpose:** Code formatter  
**Why:** Consistent code style, no arguments  
**Installation:**
```bash
pip install black
```

**Configuration:** Create `pyproject.toml`:
```toml
[tool.black]
line-length = 100
target-version = ['py311']
```

### 11. mypy
**Purpose:** Static type checker  
**Why:** Catch type errors before runtime  
**Installation:**
```bash
pip install mypy
```

### 12. ruff
**Purpose:** Fast linter (replaces flake8, isort, etc.)  
**Why:** Extremely fast, catches common errors  
**Installation:**
```bash
pip install ruff
```

---

## Date/Time Handling

### 13. python-dateutil
**Purpose:** Enhanced date parsing  
**Why:** Handle various date formats in CSV imports  
**Installation:**
```bash
pip install python-dateutil
```

---

## CSV Import/Export

### 14. csv (built-in)
**Purpose:** CSV reading/writing  
**Why:** Built into Python, sufficient for needs  
**Installation:** None (built-in)

---

## Data Visualization (Optional)

### 15. matplotlib
**Purpose:** Charts and graphs  
**Why:** Already used in legacy app for reports  
**Installation:**
```bash
pip install matplotlib
```

---

## Complete requirements.txt

Create this file in `sezzions/requirements.txt`:

```txt
# Core Framework
PySide6>=6.6.0

# Database
psycopg2-binary>=2.9.9
sqlalchemy>=2.0.23
alembic>=1.13.1

# Data Validation
pydantic>=2.5.0

# Testing
pytest>=7.4.3
pytest-cov>=4.1.0
pytest-mock>=3.12.0

# Development Tools
black>=23.12.1
mypy>=1.7.1
ruff>=0.1.8

# Utilities
python-dateutil>=2.8.2
matplotlib>=3.8.2
```

**Installation:**
```bash
cd ./
pip install -r requirements.txt
```

---

## Optional Dependencies (Future)

### Web Framework (Phase 7+)
When building web version:
- **FastAPI** - Modern async web framework
- **uvicorn** - ASGI server
- **pydantic** - Already included, perfect for FastAPI

### Mobile (Phase 8+)
When building mobile version:
- **Kivy** - Cross-platform Python mobile framework
- **BeeWare** - Native mobile apps in Python

---

## Architecture Decision: SQLAlchemy vs Raw SQL

### Option A: SQLAlchemy (Recommended)
**Pros:**
- Database-agnostic queries (SQLite ↔ PostgreSQL seamless)
- Built-in migration management (Alembic)
- Relationship management, lazy loading
- Prevents SQL injection
- Less code to maintain

**Cons:**
- Learning curve
- Slight performance overhead
- Adds dependency weight

### Option B: Raw SQL with Abstraction Layer
**Pros:**
- Full control over queries
- Lighter weight
- Easier to debug
- No ORM magic

**Cons:**
- Must manually handle SQLite vs PostgreSQL differences
- More code to maintain
- More prone to SQL injection if not careful
- Manual migration management

### **Recommendation:** Use SQLAlchemy

Given the requirement to support both SQLite and PostgreSQL without code changes, SQLAlchemy's database abstraction is worth the learning curve.

---

## Testing Dependencies Rationale

### Why pytest over unittest?
- More concise syntax
- Better fixture management
- Parametrized tests for verification
- Industry standard for Python

### Why pytest-cov?
- Integrated coverage reporting
- Shows untested code paths
- Enforces coverage thresholds

### Why pytest-mock?
- Mock database calls in unit tests
- Test error handling without real database
- Faster test execution

---

## Development Workflow Tools

### Code Quality Pipeline
```bash
# Format code
black .

# Lint code
ruff check .

# Type check
mypy .

# Run tests with coverage
pytest --cov=. --cov-report=html tests/

# Coverage report location: htmlcov/index.html
```

### Pre-commit Hook (Optional)
Create `.pre-commit-config.yaml` to run checks automatically:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.8
    hooks:
      - id: ruff
```

---

## Installation Instructions

### Step 1: Create Virtual Environment
```bash
cd "Session App/Claude Version/V28 - multi session testing 2/sezzions"
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
```

### Step 2: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Verify Installation
```bash
python3 -c "import PySide6; import sqlalchemy; import pytest; print('All dependencies installed')"
```

### Step 4: Configure Development Tools
```bash
# Initialize mypy
mypy --install-types

# Test pytest
pytest --version
```

---

## Version Management

Use `pip freeze` to lock versions after successful installation:
```bash
pip freeze > requirements-lock.txt
```

This creates a reproducible environment.

---

## Next Steps

1. ✅ Install all dependencies using requirements.txt
2. ✅ Verify installation with test imports
3. ✅ Configure development tools (black, mypy, ruff)
4. → Read **[DATABASE_DESIGN.md](DATABASE_DESIGN.md)** to set up database
5. → Read **[ARCHITECTURE.md](ARCHITECTURE.md)** to understand OOP design

---

**Last Updated:** January 16, 2026
