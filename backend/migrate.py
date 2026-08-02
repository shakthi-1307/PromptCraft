"""
Run this once to add password reset columns to an existing users table.
Usage: python migrate.py
"""
import asyncio
import asyncpg
from app.config import settings


async def run():
    # Parse the DATABASE_URL for asyncpg direct connection
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(url)
    try:
        # Add reset_token column if it doesn't exist
        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS reset_token VARCHAR DEFAULT NULL;
        """)
        print("✓ reset_token column added (or already exists)")

        # Add reset_token_expiry column if it doesn't exist
        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS reset_token_expiry TIMESTAMPTZ DEFAULT NULL;
        """)
        print("✓ reset_token_expiry column added (or already exists)")

        print("\nMigration complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())