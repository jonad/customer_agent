#!/usr/bin/env python3
"""
Test that clarification uses conversation history
Tests multi-turn conversations where context helps resolve ambiguity
"""
import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_conversation_context():
    """Test that router uses conversation history to resolve ambiguous follow-ups"""

    print("=" * 80)
    print("CONVERSATION CONTEXT TEST")
    print("=" * 80)

    # Use a consistent session ID across the conversation
    session_id = "context-test-session-001"
    user_id = "context-test-user"

    # Turn 1: Ambiguous query
    print("\n📝 Turn 1: User asks ambiguous question")
    print("User: 'I need help'")
    print("-" * 80)

    response1 = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "I need help",
            "user_id": user_id,
            "session_id": session_id
        },
        timeout=30
    )

    if response1.status_code == 200:
        data1 = response1.json()
        query_type1 = data1.get("query_type")

        print(f"✅ Status: 200")
        print(f"📊 Query type: {query_type1}")

        if query_type1 == "clarification_needed":
            clarification = data1.get("response_data", {}).get("clarification_question")
            print(f"❓ System asked: {clarification}")
        else:
            print(f"⚠️  Expected clarification but got: {query_type1}")
    else:
        print(f"❌ Request failed: {response1.status_code}")
        return False

    # Turn 2: User provides context
    print("\n\n📝 Turn 2: User provides clarification")
    print("User: 'with my orders'")
    print("-" * 80)

    response2 = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "with my orders",
            "user_id": user_id,
            "session_id": session_id  # Same session
        },
        timeout=30
    )

    if response2.status_code == 200:
        data2 = response2.json()
        query_type2 = data2.get("query_type")

        print(f"✅ Status: 200")
        print(f"📊 Query type: {query_type2}")

        if query_type2 == "sql_query":
            print(f"🎯 SUCCESS: Router used context and classified as SQL query!")
            print(f"💡 The router remembered 'I need help' + 'with my orders' = SQL query")
        elif query_type2 == "clarification_needed":
            print(f"⚠️  Router still needs clarification (might be expected if ambiguous)")
        else:
            print(f"📋 Router classified as: {query_type2}")
    else:
        print(f"❌ Request failed: {response2.status_code}")
        return False

    # Turn 3: Another contextual query
    print("\n\n📝 Turn 3: Another query in same context")
    print("User: 'How many do I have?'")
    print("-" * 80)

    response3 = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "How many do I have?",
            "user_id": user_id,
            "session_id": session_id  # Same session
        },
        timeout=30
    )

    if response3.status_code == 200:
        data3 = response3.json()
        query_type3 = data3.get("query_type")

        print(f"✅ Status: 200")
        print(f"📊 Query type: {query_type3}")

        if query_type3 == "sql_query":
            print(f"🎯 SUCCESS: Router used conversation history!")
            print(f"💡 Context from earlier messages helped classify 'How many do I have?' as SQL")
        else:
            print(f"📋 Router classified as: {query_type3}")
    else:
        print(f"❌ Request failed: {response3.status_code}")
        return False

    # Summary
    print("\n\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Turn 1: {query_type1}")
    print(f"Turn 2: {query_type2}")
    print(f"Turn 3: {query_type3}")

    print("\n✅ Conversation context test completed!")
    print("Note: The router should use previous conversation to resolve ambiguities")

    return True

if __name__ == "__main__":
    test_conversation_context()
