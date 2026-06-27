#!/usr/bin/env python3
"""
Seed the database with test users for load testing.

Usage:
    python scripts/seed_users.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.logging import setup_logging
from app.core.security import hash_password
from app.db.session import AsyncSessionFactory
from app.models.document import (
    RoleEnum,
    User,
)


async def seed() -> None:
    setup_logging()
    print("Seeding test users...")

    async with AsyncSessionFactory() as session:
        existing = await session.scalar(select(User.id).limit(1))
        if existing is not None:
            print("✓ Users already exist — skipping seed")
            return

        users_to_create: list[User] = []

        for i in range(1, 51):
            users_to_create.append(
                User(
                    username=f"operator_{i}",
                    email=f"operator_{i}@test.local",
                    hashed_password=hash_password("Test1234!"),
                    full_name=f"Operator {i}",
                    role=RoleEnum.OPERATOR,
                )
            )

        for i in range(1, 6):
            users_to_create.append(
                User(
                    username=f"supervisor_{i}",
                    email=f"supervisor_{i}@test.local",
                    hashed_password=hash_password("Test1234!"),
                    full_name=f"Supervisor {i}",
                    role=RoleEnum.SUPERVISOR,
                )
            )

        users_to_create.append(
            User(
                username="admin",
                email="admin@test.local",
                hashed_password=hash_password("Admin1234!"),
                full_name="Administrator",
                role=RoleEnum.ADMIN,
            )
        )

        session.add_all(users_to_create)
        await session.commit()
        print(f"✓ Created {len(users_to_create)} users")


if __name__ == "__main__":
    asyncio.run(seed())
