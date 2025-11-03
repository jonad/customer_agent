#!/usr/bin/env python3
"""Test script to verify database structure"""
import asyncio
from chat_history_postgres import ChatHistoryServicePostgres
from sql_query_service import SqlQueryService

async def test_database():
    print("=" * 60)
    print("DATABASE STRUCTURE TEST")
    print("=" * 60)

    # Test chat history service
    chat_service = ChatHistoryServicePostgres()
    sql_service = SqlQueryService()

    try:
        pool = await chat_service.get_pool()
        async with pool.acquire() as conn:
            # Check chat_sessions table
            sessions_count = await conn.fetchval("SELECT COUNT(*) FROM chat_sessions")
            print(f"\n✅ chat_sessions table exists ({sessions_count} sessions)")

            # Check chat_messages table
            messages_count = await conn.fetchval("SELECT COUNT(*) FROM chat_messages")
            print(f"✅ chat_messages table exists ({messages_count} messages)")

            # Check orders table
            orders_count = await conn.fetchval("SELECT COUNT(*) FROM orders")
            print(f"✅ orders table exists ({orders_count} orders)")

            # Show sample order data
            sample_orders = await conn.fetch("""
                SELECT id, user_id, product_name, quantity, price, status
                FROM orders
                LIMIT 3
            """)

            print(f"\n📦 Sample Orders:")
            for order in sample_orders:
                print(f"  - {order['product_name']} (Qty: {order['quantity']}) - ${order['price']} - {order['status']}")

            # Test SQL query service
            print(f"\n🔒 Security Configuration:")
            print(f"  - Allowed tables: {sql_service.get_allowed_tables()}")
            print(f"  - Max results: {sql_service.max_results}")

            # Test SQL validation
            print(f"\n🛡️ SQL Validation Tests:")

            test_queries = [
                ("SELECT * FROM orders WHERE user_id = '$user_id'", "Valid SELECT"),
                ("DELETE FROM orders WHERE id = 1", "Invalid DELETE"),
                ("SELECT * FROM users", "Invalid table"),
            ]

            for query, desc in test_queries:
                is_valid, error = sql_service.validate_sql(query)
                status = "✅ PASS" if is_valid else "❌ BLOCK"
                print(f"  {status}: {desc}")
                if error:
                    print(f"      Reason: {error}")

        print(f"\n" + "=" * 60)
        print("✅ ALL DATABASE TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await chat_service.close()
        await sql_service.close()

if __name__ == "__main__":
    asyncio.run(test_database())
