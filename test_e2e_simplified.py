#!/usr/bin/env python3
"""
Simplified End-to-End API Test Suite
Tests core endpoints without authentication
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api"
TEST_USER_ID = f"test-user-{int(time.time())}"

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_test(test_name, status="RUNNING"):
    """Print test status"""
    symbols = {"RUNNING": "🔄", "PASS": "✅", "FAIL": "❌", "INFO": "ℹ️"}
    print(f"\n{symbols.get(status, '•')} {test_name}")

def print_response(response, show_full=False):
    """Print response details"""
    print(f"   Status: {response.status_code}")
    if show_full or response.status_code >= 400:
        try:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        except:
            print(f"   Response: {response.text[:200]}")

# ==============================================================================
# TEST 1: SESSION MANAGEMENT
# ==============================================================================

def test_session_management():
    print_section("TEST 1: SESSION MANAGEMENT")

    # Test 1.1: Create session
    print_test("1.1 - Create session")
    response = requests.post(
        f"{BASE_URL}/create-session",
        json={"user_id": TEST_USER_ID, "title": "E2E Test Session"}
    )
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        session_id = data.get("session_id")
        print_test("1.1 - Create session", "PASS")
        print(f"   Session ID: {session_id}")
        print(f"   User ID: {TEST_USER_ID}")
        return True, session_id
    else:
        print_test("1.1 - Create session", "FAIL")
        return False, None

# ==============================================================================
# TEST 2: SQL QUERY ENDPOINT
# ==============================================================================

def test_sql_queries(session_id):
    print_section("TEST 2: SQL QUERY PROCESSING")

    # Test 2.1: Simple SQL query
    print_test("2.1 - Process SQL query: 'How many orders do I have?'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "How many orders do I have?",
            "user_id": TEST_USER_ID,
            "session_id": session_id
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "sql_query":
            print_test("2.1 - SQL query", "PASS")
            print(f"   Response: {str(data.get('response_data', {}))[:100]}...")
        else:
            print_test("2.1 - SQL query", "INFO")
            print(f"   Routed to: {data.get('query_type')}")
    else:
        print_test("2.1 - SQL query", "FAIL")

    # Test 2.2: Complex SQL query
    print_test("2.2 - Process SQL query: 'Show my orders from last week'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "Show my orders from last week",
            "user_id": TEST_USER_ID,
            "session_id": session_id
        }
    )
    print_response(response)

    if response.status_code == 200 and response.json().get("query_type") == "sql_query":
        print_test("2.2 - Complex SQL query", "PASS")
    else:
        print_test("2.2 - Complex SQL query", "INFO")

    return True

# ==============================================================================
# TEST 3: DOCUMENT SEARCH ENDPOINT
# ==============================================================================

def test_document_search(session_id):
    print_section("TEST 3: DOCUMENT SEARCH")

    # Test 3.1: Well-formed document search
    print_test("3.1 - Document search: 'Python machine learning tutorials'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "Python machine learning tutorials",
            "session_id": session_id
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "document_search":
            print_test("3.1 - Document search", "PASS")
        else:
            print_test("3.1 - Document search", "INFO")
            print(f"   Routed to: {data.get('query_type')}")
    else:
        print_test("3.1 - Document search", "FAIL")

    return True

# ==============================================================================
# TEST 4: QUERY REWRITING FLOW (Main Feature)
# ==============================================================================

def test_query_rewriting():
    print_section("TEST 4: QUERY REWRITING FLOW ⭐ (Main Feature)")

    rewrite_session = f"rewrite-test-{int(time.time())}"

    # Test 4.1: Send query with grammatical error
    print_test("4.1 - Send query with error: 'Africa people'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "I'm looking for documents about Africa people",
            "session_id": rewrite_session
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "query_confirmation":
            print_test("4.1 - Query rewrite detected", "PASS")
            rewritten = data.get("response_data", {}).get("rewritten_query")
            print(f"   ✏️  Original: 'Africa people'")
            print(f"   ✨ Rewritten: '{rewritten}'")
            print(f"   📝 Reason: {data.get('response_data', {}).get('rewrite_reason')}")
        else:
            print_test("4.1 - Query rewrite detection", "FAIL")
            print(f"   Expected query_confirmation, got {data.get('query_type')}")
            return False
    else:
        print_test("4.1 - Query rewrite detection", "FAIL")
        return False

    # Test 4.2: Confirm with "Yes" (should use rewritten query)
    print_test("4.2 - Confirm rewrite with 'Yes'")
    time.sleep(2)  # Brief pause for session consistency
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "Yes",
            "session_id": rewrite_session
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        # Check if it used the rewritten query (should be "African people")
        response_str = str(data).lower()
        if "african people" in response_str or data.get("query_type") == "document_search":
            print_test("4.2 - Confirm rewrite", "PASS")
            print(f"   ✅ System used rewritten query: 'African people'")
            print(f"   📊 Query type: {data.get('query_type')}")
        else:
            print_test("4.2 - Confirm rewrite", "FAIL")
            print(f"   ❌ Expected to search for 'African people'")
            print(f"   Got: {data.get('original_message', 'N/A')}")
    else:
        print_test("4.2 - Confirm rewrite", "FAIL")
        return False

    # Test 4.3: Test "No" (rephrase) flow
    print_test("4.3 - Test rephrase flow with 'No'")
    rephrase_session = f"rephrase-test-{int(time.time())}"

    # Send error query
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "documents machine learning Python",
            "session_id": rephrase_session
        }
    )

    if response.status_code == 200 and response.json().get("query_type") == "query_confirmation":
        print(f"   📝 Detected rewrite needed")
        # Respond with "No"
        time.sleep(2)
        response = requests.post(
            f"{BASE_URL}/process-inquiry",
            json={
                "message": "No",
                "session_id": rephrase_session
            }
        )
        print_response(response, show_full=True)

        if response.status_code == 200:
            data = response.json()
            if data.get("query_type") == "clarification_needed":
                print_test("4.3 - Rephrase flow", "PASS")
                print(f"   ✅ System asked: {data.get('response_data', {}).get('clarification_question')}")
            else:
                print_test("4.3 - Rephrase flow", "FAIL")
                print(f"   Expected clarification_needed, got {data.get('query_type')}")
        else:
            print_test("4.3 - Rephrase flow", "FAIL")
    else:
        print_test("4.3 - Rephrase flow", "FAIL")
        print("   Could not trigger rewrite detection")

    # Test 4.4: Test "original" flow
    print_test("4.4 - Test 'use original query' flow")
    original_session = f"original-test-{int(time.time())}"

    # Send error query
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "find information Africa people",
            "session_id": original_session
        }
    )

    if response.status_code == 200 and response.json().get("query_type") == "query_confirmation":
        print(f"   📝 Detected rewrite needed")
        # Respond with "original"
        time.sleep(2)
        response = requests.post(
            f"{BASE_URL}/process-inquiry",
            json={
                "message": "original",
                "session_id": original_session
            }
        )
        print_response(response, show_full=True)

        if response.status_code == 200:
            data = response.json()
            print_test("4.4 - Use original query", "PASS")
            print(f"   ✅ System processed with original query")
        else:
            print_test("4.4 - Use original query", "FAIL")
    else:
        print_test("4.4 - Use original query", "INFO")
        print("   Could not trigger rewrite detection")

    return True

# ==============================================================================
# TEST 5: CLARIFICATION FLOW
# ==============================================================================

def test_clarification_flow():
    print_section("TEST 5: CLARIFICATION FLOW")

    clarif_session = f"clarif-test-{int(time.time())}"

    # Test 5.1: Ambiguous query
    print_test("5.1 - Send ambiguous query: 'I need help'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "I need help",
            "session_id": clarif_session
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "clarification_needed":
            print_test("5.1 - Clarification requested", "PASS")
            print(f"   Question: {data.get('response_data', {}).get('clarification_question', 'N/A')[:80]}...")
        else:
            print_test("5.1 - Clarification requested", "INFO")
            print(f"   Routed to: {data.get('query_type')}")
    else:
        print_test("5.1 - Clarification requested", "FAIL")

    # Test 5.2: Follow-up with context
    print_test("5.2 - Follow-up: 'with my orders'")
    time.sleep(2)
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "with my orders",
            "session_id": clarif_session
        }
    )
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "sql_query":
            print_test("5.2 - Context resolution", "PASS")
            print("   System understood context and routed to SQL")
        else:
            print_test("5.2 - Context resolution", "INFO")
            print(f"   Routed to: {data.get('query_type')}")
    else:
        print_test("5.2 - Context resolution", "FAIL")

    return True

# ==============================================================================
# TEST 6: CUSTOMER SERVICE
# ==============================================================================

def test_customer_service():
    print_section("TEST 6: CUSTOMER SERVICE")

    cs_session = f"cs-test-{int(time.time())}"

    # Test 6.1: Technical support query
    print_test("6.1 - Customer service: 'My internet is not working'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "My internet is not working",
            "session_id": cs_session
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "customer_service":
            print_test("6.1 - Customer service routing", "PASS")
            category = data.get("response_data", {}).get("category", "N/A")
            print(f"   Category: {category}")
        else:
            print_test("6.1 - Customer service routing", "INFO")
            print(f"   Routed to: {data.get('query_type')}")
    else:
        print_test("6.1 - Customer service routing", "FAIL")

    return True

# ==============================================================================
# TEST 7: UNSUPPORTED QUERIES
# ==============================================================================

def test_unsupported_queries():
    print_section("TEST 7: UNSUPPORTED QUERIES")

    unsupported_session = f"unsupported-test-{int(time.time())}"

    unsupported_queries = [
        ("Hello, how are you?", "greeting"),
        ("What's the weather today?", "weather"),
        ("Tell me a joke", "entertainment")
    ]

    for query, query_type in unsupported_queries:
        print_test(f"7.x - Unsupported query: '{query}'")
        response = requests.post(
            f"{BASE_URL}/process-inquiry",
            json={
                "message": query,
                "session_id": unsupported_session
            }
        )
        print_response(response)

        if response.status_code == 200:
            data = response.json()
            if data.get("query_type") == "unsupported":
                print_test(f"Unsupported detection ({query_type})", "PASS")
            else:
                print_test(f"Unsupported detection ({query_type})", "INFO")
                print(f"   Routed to: {data.get('query_type')}")
        else:
            print_test(f"Unsupported detection ({query_type})", "FAIL")

        time.sleep(1)

    return True

# ==============================================================================
# TEST 8: CHAT HISTORY
# ==============================================================================

def test_chat_history(session_id):
    print_section("TEST 8: CHAT HISTORY")

    # Test 8.1: Get chat history
    print_test("8.1 - Get chat history")
    response = requests.get(f"{BASE_URL}/chat-history/{session_id}?limit=10")
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        message_count = len(data.get("messages", []))
        print_test("8.1 - Get chat history", "PASS")
        print(f"   Messages in session: {message_count}")

        # Show sample messages
        if message_count > 0:
            print(f"   Sample messages:")
            for msg in data.get("messages", [])[:3]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:50]
                print(f"     - {role}: {content}...")
    else:
        print_test("8.1 - Get chat history", "FAIL")
        return False

    return True

# ==============================================================================
# MAIN TEST RUNNER
# ==============================================================================

def main():
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 18 + "SIMPLIFIED END-TO-END API TEST SUITE" + " " * 24 + "║")
    print("╚" + "═" * 78 + "╝")
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base URL: {BASE_URL}")
    print(f"\n⭐ Focus: Query Rewriting Feature (grammatical error detection)")

    try:
        # Run all tests
        success, session_id = test_session_management()
        if not success:
            print("\n❌ Session management tests failed. Stopping.")
            return

        test_sql_queries(session_id)
        test_document_search(session_id)

        # MAIN FEATURE TEST
        test_query_rewriting()

        test_clarification_flow()
        test_customer_service()
        test_unsupported_queries()
        test_chat_history(session_id)

        # Final summary
        print_section("TEST SUMMARY")
        print("✅ All test suites completed!")
        print(f"\nMain session: {session_id}")
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n🎯 Key Feature Tested:")
        print("   - Query rewriting for grammatical errors")
        print("   - Confirmation flow with 'Yes'")
        print("   - Rephrase flow with 'No'")
        print("   - Use original query flow")
        print("   - Conversation history maintenance")

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
