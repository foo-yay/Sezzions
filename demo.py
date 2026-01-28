#!/usr/bin/env python3
"""
Demo script to verify Phase 1 implementation works

Run with: python3 demo.py
"""
from repositories.database import DatabaseManager
from repositories.user_repository import UserRepository
from services.user_service import UserService


def main():
    print("=" * 60)
    print("Sezzions Demo - Phase 1: User Management")
    print("=" * 60)
    
    # Initialize
    print("\n1. Initializing database...")
    db = DatabaseManager('demo.db')
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    print("   ✓ Database initialized")
    
    # Create users
    print("\n2. Creating users...")
    user1 = user_service.create_user(
        name="John Doe",
        email="john@example.com",
        notes="First test user"
    )
    print(f"   ✓ Created: {user1.name} (ID: {user1.id})")
    
    user2 = user_service.create_user(
        name="Jane Smith",
        email="jane@example.com"
    )
    print(f"   ✓ Created: {user2.name} (ID: {user2.id})")
    
    # List users
    print("\n3. Listing all users...")
    all_users = user_service.list_all_users()
    for user in all_users:
        status = "Active" if user.is_active else "Inactive"
        print(f"   - {user.name} ({status})")
    
    # Update user
    print("\n4. Updating user...")
    updated = user_service.update_user(
        user1.id,
        email="john.doe@newdomain.com"
    )
    print(f"   ✓ Updated {updated.name}'s email to {updated.email}")
    
    # Deactivate user
    print("\n5. Deactivating user...")
    user_service.deactivate_user(user2.id)
    print(f"   ✓ Deactivated {user2.name}")
    
    # List active users
    print("\n6. Listing active users...")
    active_users = user_service.list_active_users()
    for user in active_users:
        print(f"   - {user.name}")
    
    print("\n" + "=" * 60)
    print("Demo complete! ✓")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run tests: pytest")
    print("  2. Check coverage: pytest --cov=sezzions --cov-report=html")
    print("  3. Continue to Phase 1, Week 3 (Sites & Cards)")
    print()
    
    db.close()


if __name__ == "__main__":
    main()
