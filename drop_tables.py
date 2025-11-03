#!/usr/bin/env python3
"""
Drop and recreate database tables with new schema
"""
import asyncio
from chat_history_postgres import ChatHistoryServicePostgres

async def main():
    print("Connecting to PostgreSQL...")
    service = ChatHistoryServicePostgres()

    try:
        pool = await service.get_pool()
        async with pool.acquire() as conn:
            print("Dropping old tables...")
            await conn.execute("DROP TABLE IF EXISTS chat_messages CASCADE")
            await conn.execute("DROP TABLE IF EXISTS chat_sessions CASCADE")
            print("✅ Tables dropped successfully")

            print("\nRecreating tables with new schema...")
            await service.init_db()
            print("✅ Tables created successfully")

    finally:
        await service.close()
        print("\n✅ Database migration complete!")

if __name__ == "__main__":
    asyncio.run(main())
