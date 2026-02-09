from decimal import Decimal
from datetime import date
from repositories.database import DatabaseManager
from repositories.purchase_repository import PurchaseRepository
from repositories.user_repository import UserRepository
from repositories.site_repository import SiteRepository
from services.purchase_service import PurchaseService
from models.user import User
from models.site import Site

# Create test DB
db = DatabaseManager(':memory:')
db.create_schema()

# Create repos and services
purchase_repo = PurchaseRepository(db)
user_repo = UserRepository(db)
site_repo = SiteRepository(db)
purchase_service = PurchaseService(purchase_repo, None, None, None)

# Create a test user/site
user = User(name='Test User')
user.id = user_repo.create(user)

site = Site(name='Test Site')
site.id = site_repo.create(site)

# Create purchase
purchase = purchase_service.create_purchase(
    user_id=user.id,
    site_id=site.id,
    amount=Decimal('100.00'),
    purchase_date=date(2026, 1, 15),
    notes='Sample purchase for testing'
)

print(f'Created purchase with id={purchase.id}, type={type(purchase.id)}')
print(f'Calling update_purchase with id={purchase.id}...')

# Try to update
updated = purchase_service.update_purchase(
    purchase.id,
    notes='Updated notes',
    purchase_time='15:00:00'
)

print(f'Updated successfully: {updated.notes}')
