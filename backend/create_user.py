"""CLI script to create the initial user. Run with: python create_user.py <username> <password>"""

import asyncio
import sys

from sqlalchemy import select

from app.auth import hash_password
from app.database import async_session, engine
from app.models import Base
from app.models.user import User


async def create_user(username: str, password: str):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            return

        user = User(username=username, hashed_password=hash_password(password))
        db.add(user)
        await db.commit()
        print(f"User '{username}' created successfully.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python create_user.py <username> <password>")
        sys.exit(1)
    asyncio.run(create_user(sys.argv[1], sys.argv[2]))
