#!/usr/bin/env python3
"""
Debug script to test SQL agent pipeline directly
"""
import asyncio
import json
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from agents.sql_agent import SqlAgentOrchestrator

async def test_sql_agent():
    # Initialize SQL agent
    sql_agent = SqlAgentOrchestrator()

    # Initialize session service
    session_service = DatabaseSessionService(db_url="sqlite:///multi_agent_data.db")

    # Create test session
    user_id = "test-user-123"
    session_id = "test-session-sql"

    session = await session_service.create_session(
        app_name="agents",
        user_id=user_id,
        session_id=session_id
    )

    print(f"✅ Created session: {session_id}")

    # Create runner with SQL generation agent
    runner = Runner(
        app_name="agents",
        agent=sql_agent.sql_generation_agent,
        session_service=session_service,
    )

    # Test query
    test_query = "Show me all my pending orders"
    print(f"\n📝 Testing query: '{test_query}'")
    print("="*60)

    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=test_query)]
    )

    # Run the agent pipeline
    events = runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    )

    # Collect all events
    event_count = 0
    final_response = None

    async for event in events:
        event_count += 1
        print(f"\n📨 Event #{event_count}:")
        print(f"   Type: {type(event).__name__}")
        print(f"   Is Final: {event.is_final_response()}")

        if event.content and event.content.parts:
            content_text = event.content.parts[0].text
            print(f"   Content Preview: {content_text[:200]}...")

            if event.is_final_response():
                final_response = content_text
                print(f"\n✅ FINAL RESPONSE:")
                print("="*60)
                print(content_text)
                print("="*60)

                # Try to parse as JSON
                try:
                    parsed = json.loads(content_text)
                    print(f"\n📊 Parsed JSON:")
                    print(json.dumps(parsed, indent=2))
                except json.JSONDecodeError as e:
                    print(f"\n⚠️  JSON Parse Error: {e}")

    print(f"\n\n📈 Summary:")
    print(f"   Total Events: {event_count}")
    print(f"   Final Response Found: {final_response is not None}")

    # Cleanup
    await session_service.close()

if __name__ == "__main__":
    asyncio.run(test_sql_agent())
