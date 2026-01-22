"""
pytest fixtures for testing
"""
import pytest
import os
from repositories.database import DatabaseManager
from repositories.user_repository import UserRepository
from repositories.site_repository import SiteRepository
from repositories.card_repository import CardRepository
from repositories.redemption_method_repository import RedemptionMethodRepository
from repositories.game_type_repository import GameTypeRepository
from repositories.game_repository import GameRepository
from repositories.purchase_repository import PurchaseRepository
from repositories.redemption_repository import RedemptionRepository
from repositories.game_session_repository import GameSessionRepository
from services.user_service import UserService
from services.site_service import SiteService
from services.card_service import CardService
from services.redemption_method_service import RedemptionMethodService
from services.game_type_service import GameTypeService
from services.game_service import GameService
from services.purchase_service import PurchaseService
from services.fifo_service import FIFOService
from services.redemption_service import RedemptionService
from services.game_session_service import GameSessionService


@pytest.fixture
def test_db():
    """Create fresh test database in memory"""
    db = DatabaseManager(':memory:')
    yield db
    db.close()


@pytest.fixture
def user_repo(test_db):
    """User repository with test database"""
    return UserRepository(test_db)


@pytest.fixture
def user_service(user_repo):
    """User service with test repository"""
    return UserService(user_repo)


@pytest.fixture
def sample_user(user_service):
    """Create a sample user for testing"""
    return user_service.create_user(
        name="Test User",
        email="test@example.com",
        notes="Sample user for testing"
    )


@pytest.fixture
def site_repo(test_db):
    """Site repository with test database"""
    return SiteRepository(test_db)


@pytest.fixture
def site_service(site_repo):
    """Site service with test repository"""
    return SiteService(site_repo)


@pytest.fixture
def sample_site(site_service):
    """Create a sample site for testing"""
    return site_service.create_site(
        name="Test Site",
        url="https://testsite.com",
        notes="Sample site for testing"
    )


@pytest.fixture
def card_repo(test_db):
    """Card repository with test database"""
    return CardRepository(test_db)


@pytest.fixture
def card_service(card_repo):
    """Card service with test repository"""
    return CardService(card_repo)


@pytest.fixture
def sample_card(card_service, sample_user):
    """Create a sample card for testing"""
    return card_service.create_card(
        name="Test Card",
        user_id=sample_user.id,
        last_four="1234",
        cashback_rate=2.0,
        notes="Sample card for testing"
    )


@pytest.fixture
def method_repo(test_db):
    """RedemptionMethod repository with test database"""
    return RedemptionMethodRepository(test_db)


@pytest.fixture
def method_service(method_repo):
    """RedemptionMethod service with test repository"""
    return RedemptionMethodService(method_repo)


@pytest.fixture
def sample_method(method_service):
    """Create a sample redemption method for testing"""
    return method_service.create_method(
        name="Test Method",
        notes="Sample method for testing"
    )


@pytest.fixture
def type_repo(test_db):
    """GameType repository with test database"""
    return GameTypeRepository(test_db)


@pytest.fixture
def type_service(type_repo):
    """GameType service with test repository"""
    return GameTypeService(type_repo)


@pytest.fixture
def sample_game_type(type_service):
    """Create a sample game type for testing"""
    return type_service.create_type(
        name="Test Type",
        notes="Sample game type for testing"
    )


@pytest.fixture
def game_repo(test_db):
    """Game repository with test database"""
    return GameRepository(test_db)


@pytest.fixture
def game_service(game_repo):
    """Game service with test repository"""
    return GameService(game_repo)


@pytest.fixture
def sample_game(game_service, sample_game_type):
    """Create a sample game for testing"""
    return game_service.create_game(
        name="Test Game",
        game_type_id=sample_game_type.id,
        rtp=96.0,
        notes="Sample game for testing"
    )


@pytest.fixture
def purchase_repo(test_db):
    """Purchase repository with test database"""
    return PurchaseRepository(test_db)


@pytest.fixture
def purchase_service(purchase_repo):
    """Purchase service with test repository"""
    return PurchaseService(purchase_repo)


@pytest.fixture
def sample_purchase(purchase_service, sample_user, sample_site):
    """Create a sample purchase for testing"""
    from decimal import Decimal
    from datetime import date
    return purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 15),
        notes="Sample purchase for testing"
    )


@pytest.fixture
def redemption_repo(test_db):
    """Redemption repository with test database"""
    return RedemptionRepository(test_db)


@pytest.fixture
def fifo_service(purchase_repo):
    """FIFO service with test repository"""
    return FIFOService(purchase_repo)


@pytest.fixture
def redemption_service(redemption_repo, fifo_service):
    """Redemption service with test repositories"""
    return RedemptionService(redemption_repo, fifo_service)


@pytest.fixture
def sample_redemption(redemption_service, sample_user, sample_site):
    """Create a sample redemption for testing (without FIFO)"""
    from decimal import Decimal
    from datetime import date
    return redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        redemption_date=date(2026, 1, 15),
        notes="Sample redemption for testing",
        apply_fifo=False
    )


@pytest.fixture
def game_session_repo(test_db):
    """Game session repository with test database"""
    return GameSessionRepository(test_db)


@pytest.fixture
def game_session_service(game_session_repo):
    """Game session service with test repository"""
    return GameSessionService(game_session_repo)


@pytest.fixture
def sample_game_session(game_session_service, sample_user, sample_site, sample_game):
    """Create a sample game session for testing"""
    from decimal import Decimal
    from datetime import date
    return game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00"),
        notes="Sample session for testing"
    )
