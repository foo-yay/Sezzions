# Architecture Design

## Overview

This document defines the OOP architecture for Sezzions, organized in three layers:
1. **Models** - Domain entities (data structures with validation)
2. **Repositories** - Data access layer (database operations)
3. **Services** - Business logic layer (orchestration, calculations)

---

## Layer Responsibilities

### Models Layer (`models/`)
- Define domain entities as dataclasses or Pydantic models
- Include validation rules
- **NO** database access
- **NO** business logic
- Pure data containers with type safety

### Repository Layer (`repositories/`)
- All database access (SELECT, INSERT, UPDATE, DELETE)
- Convert database rows → models
- Convert models → database rows
- Abstract SQLite vs PostgreSQL differences
- **NO** business logic

### Service Layer (`services/`)
- Business logic and orchestration
- Call repositories for data access
- Implement accounting algorithms (FIFO, sessions)
- Coordinate multi-repository operations
- Transaction management

### UI Layer (`ui/`)
- Call services only (never repositories directly)
- Display data from models
- Collect user input
- **NO** business logic
- **NO** database access

---

## Directory Structure

```
sezzions/
├── models/
│   ├── __init__.py
│   ├── user.py                 # User domain model
│   ├── card.py                 # Card domain model
│   ├── site.py                 # Site domain model
│   ├── purchase.py             # Purchase domain model
│   ├── redemption.py           # Redemption domain model
│   ├── game_session.py         # GameSession domain model
│   ├── realized_transaction.py # RealizedTransaction (tax session)
│   └── base.py                 # Base model with common fields
│
├── repositories/
│   ├── __init__.py
│   ├── base_repository.py      # Base repo with common operations
│   ├── user_repository.py
│   ├── card_repository.py
│   ├── site_repository.py
│   ├── purchase_repository.py
│   ├── redemption_repository.py
│   ├── game_session_repository.py
│   ├── realized_transaction_repository.py
│   └── database.py             # Database connection manager
│
├── services/
│   ├── __init__.py
│   ├── user_service.py
│   ├── card_service.py
│   ├── site_service.py
│   ├── purchase_service.py
│   ├── redemption_service.py
│   ├── session_service.py
│   ├── fifo_service.py         # FIFO calculations (from FIFOCalculator)
│   └── audit_service.py
│
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── tabs/
│   │   ├── purchases_tab.py
│   │   ├── redemptions_tab.py
│   │   ├── sessions_tab.py
│   │   └── ...
│   └── widgets/
│       ├── searchable_table.py  # Ported from table_helpers.py
│       └── dialogs.py
│
└── sezzions.py                 # Main entry point
```

---

## Domain Models

### Base Model (`models/base.py`)

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class BaseModel:
    """Base class for all domain models"""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

---

### User Model (`models/user.py`)

```python
from dataclasses import dataclass
from typing import Optional
from .base import BaseModel

@dataclass
class User(BaseModel):
    """Represents a user/player"""
    name: str
    email: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    
    def __str__(self) -> str:
        return self.name
```

**Repository Methods:**
- `get_by_id(user_id) -> User`
- `get_all() -> list[User]`
- `get_active() -> list[User]`
- `create(user: User) -> User`
- `update(user: User) -> User`
- `delete(user_id: int) -> None`

**Service Methods:**
- `create_user(name, email, notes) -> User`
- `update_user(user_id, **kwargs) -> User`
- `deactivate_user(user_id) -> None`
- `list_active_users() -> list[User]`

---

### Site Model (`models/site.py`)

```python
from dataclasses import dataclass
from typing import Optional
from .base import BaseModel

@dataclass
class Site(BaseModel):
    """Represents a casino site"""
    name: str
    url: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    
    def __str__(self) -> str:
        return self.name
```

**Repository Methods:**
- `get_by_id(site_id) -> Site`
- `get_all() -> list[Site]`
- `get_active() -> list[Site]`
- `create(site: Site) -> Site`
- `update(site: Site) -> Site`
- `delete(site_id: int) -> None`

**Service Methods:**
- Similar to UserService

---

### Card Model (`models/card.py`)

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from .base import BaseModel

@dataclass
class Card(BaseModel):
    """Represents a payment card"""
    name: str
    user_id: int
    last_four: Optional[str] = None
    cashback_rate: Decimal = Decimal('0.00')
    is_active: bool = True
    notes: Optional[str] = None
    
    def __post_init__(self):
        # Validate cashback_rate
        if self.cashback_rate < 0 or self.cashback_rate > 100:
            raise ValueError("Cashback rate must be 0-100%")
    
    def display_name(self) -> str:
        """Returns formatted name with suffix"""
        if self.last_four:
            return f"{self.name} -- x{self.last_four}"
        return self.name
```

**Repository Methods:**
- `get_by_id(card_id) -> Card`
- `get_by_user(user_id) -> list[Card]`
- `get_active_by_user(user_id) -> list[Card]`
- `create(card: Card) -> Card`
- `update(card: Card) -> Card`
- `delete(card_id: int) -> None`

**Service Methods:**
- `create_card(name, user_id, last_four, cashback_rate) -> Card`
- `update_card(card_id, **kwargs) -> Card`
- `deactivate_card(card_id) -> None`
- `list_user_cards(user_id, active_only=True) -> list[Card]`

---

### Purchase Model (`models/purchase.py`)

```python
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Optional
from .base import BaseModel

@dataclass
class Purchase(BaseModel):
    """Represents a purchase (adds basis to FIFO pool)"""
    purchase_date: date
    purchase_time: time
    site_id: int
    user_id: int
    amount: Decimal  # USD spent
    sc_received: Decimal  # Sweep Coins received
    card_id: Optional[int] = None
    remaining_amount: Decimal = Decimal('0.00')  # For FIFO tracking
    notes: Optional[str] = None
    
    def __post_init__(self):
        # Validate amount
        if self.amount <= 0:
            raise ValueError("Amount must be positive")
        if self.amount.as_tuple().exponent < -2:
            raise ValueError("Amount max 2 decimal places")
        
        # Validate sc_received
        if self.sc_received < 0:
            raise ValueError("SC received cannot be negative")
        
        # Set remaining_amount on creation
        if self.id is None and self.remaining_amount == 0:
            self.remaining_amount = self.amount
    
    @property
    def consumed(self) -> Decimal:
        """Amount of basis consumed (allocated to redemptions)"""
        return self.amount - self.remaining_amount
    
    @property
    def timestamp_str(self) -> str:
        """Combined date and time as string"""
        return f"{self.purchase_date} {self.purchase_time}"
```

**Repository Methods:**
- `get_by_id(purchase_id) -> Purchase`
- `get_by_site_user(site_id, user_id, start_date=None, end_date=None) -> list[Purchase]`
- `get_available_for_fifo(site_id, user_id, before_datetime) -> list[Purchase]`
- `create(purchase: Purchase) -> Purchase`
- `update(purchase: Purchase) -> Purchase`
- `delete(purchase_id: int) -> None`
- `update_remaining_amount(purchase_id, remaining_amount) -> None`

**Service Methods:**
- `create_purchase(purchase_date, purchase_time, site_id, user_id, amount, sc_received, card_id, notes) -> Purchase`
- `update_purchase(purchase_id, **kwargs) -> Purchase` (with consumed validation)
- `delete_purchase(purchase_id) -> None` (check if consumed > 0)
- `list_purchases(site_id=None, user_id=None, start_date=None, end_date=None) -> list[Purchase]`

---

### Redemption Model (`models/redemption.py`)

```python
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Optional
from .base import BaseModel

@dataclass
class Redemption(BaseModel):
    """Represents a redemption (consumes basis via FIFO)"""
    redemption_date: date
    redemption_time: time
    site_id: int
    user_id: int
    amount: Decimal  # USD redeemed
    method_id: Optional[int] = None
    is_free_sc: bool = False  # Discoverable SC redemption
    fees: Decimal = Decimal('0.00')
    notes: Optional[str] = None
    
    def __post_init__(self):
        # Validate amount
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
        if self.amount.as_tuple().exponent < -2:
            raise ValueError("Amount max 2 decimal places")
        
        # Validate fees
        if self.fees < 0:
            raise ValueError("Fees cannot be negative")
    
    @property
    def net_amount(self) -> Decimal:
        """Amount after fees"""
        return self.amount - self.fees
    
    @property
    def timestamp_str(self) -> str:
        """Combined date and time as string"""
        return f"{self.redemption_date} {self.redemption_time}"
```

**Repository Methods:**
- `get_by_id(redemption_id) -> Redemption`
- `get_by_site_user(site_id, user_id, start_date=None, end_date=None) -> list[Redemption]`
- `get_chronological(site_id, user_id) -> list[Redemption]`
- `create(redemption: Redemption) -> Redemption`
- `update(redemption: Redemption) -> Redemption`
- `delete(redemption_id: int) -> None`

**Service Methods:**
- `create_redemption(redemption_date, redemption_time, site_id, user_id, amount, method_id, is_free_sc, fees, notes) -> Redemption`
  - Triggers FIFO allocation via FIFOService
  - Creates RealizedTransaction (tax session)
- `update_redemption(redemption_id, **kwargs) -> Redemption`
  - Reverses old allocation
  - Applies new allocation
- `delete_redemption(redemption_id) -> None`
  - Reverses allocation
  - Deletes RealizedTransaction

---

### RealizedTransaction Model (`models/realized_transaction.py`)

Formerly "tax_sessions" - represents taxable profit/loss events.

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional
from .base import BaseModel

@dataclass
class RealizedTransaction(BaseModel):
    """Represents a taxable transaction (tax session)"""
    redemption_date: date
    site_id: int
    user_id: int
    redemption_id: int  # Foreign key to redemption
    cost_basis: Decimal
    payout: Decimal
    net_pl: Decimal  # payout - cost_basis
    notes: Optional[str] = None
    
    def __post_init__(self):
        # Calculate net_pl if not provided
        if self.net_pl is None or self.net_pl == 0:
            self.net_pl = self.payout - self.cost_basis
```

**Repository Methods:**
- `get_by_id(transaction_id) -> RealizedTransaction`
- `get_by_redemption(redemption_id) -> Optional[RealizedTransaction]`
- `get_by_site_user(site_id, user_id, start_date=None, end_date=None) -> list[RealizedTransaction]`
- `create(transaction: RealizedTransaction) -> RealizedTransaction`
- `update(transaction: RealizedTransaction) -> RealizedTransaction`
- `delete(transaction_id: int) -> None`
- `delete_by_redemption(redemption_id: int) -> None`

**Service Methods:**
- Managed by RedemptionService (not accessed directly)

---

### GameSession Model (`models/game_session.py`)

```python
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Optional
from .base import BaseModel

@dataclass
class GameSession(BaseModel):
    """Represents an active game session"""
    session_date: date
    session_time: time
    site_id: int
    user_id: int
    game_id: Optional[int] = None
    starting_balance: Decimal = Decimal('0.00')
    ending_balance: Decimal = Decimal('0.00')
    starting_redeemable: Decimal = Decimal('0.00')
    ending_redeemable: Decimal = Decimal('0.00')
    basis_consumed: Decimal = Decimal('0.00')
    net_taxable_pl: Decimal = Decimal('0.00')
    notes: Optional[str] = None
    is_closed: bool = False
    
    @property
    def delta_play(self) -> Decimal:
        """Change in play balance"""
        return self.ending_balance - self.starting_balance
    
    @property
    def delta_redeemable(self) -> Decimal:
        """Change in redeemable balance"""
        return self.ending_redeemable - self.starting_redeemable
    
    @property
    def discoverable_sc(self) -> Decimal:
        """Discoverable SC (starting_redeemable - expected_start_redeemable)"""
        # Expected start = previous session's ending_redeemable
        # Implemented in SessionService
        return Decimal('0.00')  # Calculated by service
```

**Repository Methods:**
- `get_by_id(session_id) -> GameSession`
- `get_by_site_user(site_id, user_id, start_date=None, end_date=None) -> list[GameSession]`
- `get_chronological(site_id, user_id) -> list[GameSession]`
- `get_open_sessions(site_id=None, user_id=None) -> list[GameSession]`
- `create(session: GameSession) -> GameSession`
- `update(session: GameSession) -> GameSession`
- `delete(session_id: int) -> None`

**Service Methods:**
- `create_session(...) -> GameSession`
- `update_session(session_id, **kwargs, trigger_recalc=True) -> GameSession`
  - Administrative fields (notes, game_id) don't trigger recalc
  - Balance changes trigger scoped recalculation
- `close_session(session_id) -> GameSession`
- `delete_session(session_id) -> None`
- `calculate_session_pl(session: GameSession, prev_session: GameSession) -> Decimal`
- `recalculate_affected_sessions(site_id, user_id, from_datetime) -> None`

---

## Repository Pattern

### Base Repository (`repositories/base_repository.py`)

```python
from typing import Generic, TypeVar, Optional, List
from abc import ABC, abstractmethod

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    """Base repository with common CRUD operations"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[T]:
        pass
    
    @abstractmethod
    def get_all(self) -> List[T]:
        pass
    
    @abstractmethod
    def create(self, entity: T) -> T:
        pass
    
    @abstractmethod
    def update(self, entity: T) -> T:
        pass
    
    @abstractmethod
    def delete(self, id: int) -> None:
        pass
```

### Example: UserRepository (`repositories/user_repository.py`)

```python
from typing import Optional, List
from models.user import User
from .base_repository import BaseRepository

class UserRepository(BaseRepository[User]):
    """Repository for User entity"""
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        query = "SELECT * FROM users WHERE id = ?"
        row = self.db.fetch_one(query, (user_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[User]:
        query = "SELECT * FROM users ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def get_active(self) -> List[User]:
        query = "SELECT * FROM users WHERE is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def create(self, user: User) -> User:
        query = """
            INSERT INTO users (name, email, is_active, notes)
            VALUES (?, ?, ?, ?)
        """
        user_id = self.db.execute(query, (
            user.name, user.email, user.is_active, user.notes
        ))
        user.id = user_id
        return user
    
    def update(self, user: User) -> User:
        query = """
            UPDATE users
            SET name = ?, email = ?, is_active = ?, notes = ?
            WHERE id = ?
        """
        self.db.execute(query, (
            user.name, user.email, user.is_active, user.notes, user.id
        ))
        return user
    
    def delete(self, user_id: int) -> None:
        query = "DELETE FROM users WHERE id = ?"
        self.db.execute(query, (user_id,))
    
    def _row_to_model(self, row) -> User:
        """Convert database row to User model"""
        return User(
            id=row['id'],
            name=row['name'],
            email=row['email'] if 'email' in row.keys() else None,
            is_active=bool(row['is_active']),
            notes=row['notes'] if 'notes' in row.keys() else None
        )
```

---

## Service Pattern

### Example: UserService (`services/user_service.py`)

```python
from typing import List, Optional
from models.user import User
from repositories.user_repository import UserRepository

class UserService:
    """Business logic for User operations"""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    def create_user(self, name: str, email: Optional[str] = None, notes: Optional[str] = None) -> User:
        """Create new user with validation"""
        # Business rule: name required
        if not name or not name.strip():
            raise ValueError("User name is required")
        
        # Create user
        user = User(name=name.strip(), email=email, notes=notes)
        return self.user_repo.create(user)
    
    def update_user(self, user_id: int, **kwargs) -> User:
        """Update user with validation"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        return self.user_repo.update(user)
    
    def deactivate_user(self, user_id: int) -> None:
        """Deactivate user (soft delete)"""
        self.update_user(user_id, is_active=False)
    
    def list_active_users(self) -> List[User]:
        """Get all active users"""
        return self.user_repo.get_active()
```

---

## Dependency Injection

Services receive repositories via constructor injection:

```python
# In main app initialization (sezzions.py):
from repositories.database import DatabaseManager
from repositories.user_repository import UserRepository
from services.user_service import UserService

# Initialize database
db_manager = DatabaseManager('sezzions.db')

# Initialize repositories
user_repo = UserRepository(db_manager)
card_repo = CardRepository(db_manager)
# ...

# Initialize services
user_service = UserService(user_repo)
card_service = CardService(card_repo, user_repo)
# ...

# Pass services to UI
main_window = MainWindow(
    user_service=user_service,
    card_service=card_service,
    # ...
)
```

---

## Next Steps

1. Read **[DATABASE_DESIGN.md](DATABASE_DESIGN.md)** for schema details
2. Read **[ACCOUNTING_LOGIC.md](ACCOUNTING_LOGIC.md)** for FIFO and SessionService
3. Read **[TESTING_STRATEGY.md](TESTING_STRATEGY.md)** for testing approach
4. Start implementing models → repositories → services

---

**Last Updated:** January 16, 2026
