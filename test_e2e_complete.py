#!/usr/bin/env python3
"""
Complete End-to-End API Test Suite
Tests all major endpoints and flows
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api"
TEST_USER = f"testuser_{int(time.time())}"
TEST_EMAIL = f"{TEST_USER}@example.com"
TEST_PASSWORD = "SecurePass123!"

# Global variables
auth_token = None
current_user = None

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
# TEST 1: AUTHENTICATION ENDPOINTS
# ==============================================================================

def test_authentication():
    global auth_token, current_user

    print_section("TEST 1: AUTHENTICATION ENDPOINTS")

    # Test 1.1: Register new user
    print_test("1.1 - Register new user")
    response = requests.post(
        f"{BASE_URL}/register",
        json={
            "username": TEST_USER,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "full_name": "Test User E2E"
        }
    )
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        auth_token = data.get("access_token")
        current_user = data.get("user")
        print_test("1.1 - Register new user", "PASS")
        print(f"   Token: {auth_token[:20]}...")
        print(f"   User ID: {current_user.get('user_id')}")
    else:
        print_test("1.1 - Register new user", "FAIL")
        return False

    # Test 1.2: Login with credentials
    print_test("1.2 - Login with credentials")
    response = requests.post(
        f"{BASE_URL}/login",
        json={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        }
    )
    print_response(response)

    if response.status_code == 200:
        print_test("1.2 - Login", "PASS")
    else:
        print_test("1.2 - Login", "FAIL")
        return False

    # Test 1.3: Get current user info
    print_test("1.3 - Get current user info (/me)")
    response = requests.get(
        f"{BASE_URL}/me",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    print_response(response)

    if response.status_code == 200:
        print_test("1.3 - Get user info", "PASS")
    else:
        print_test("1.3 - Get user info", "FAIL")
        return False

    return True

# ==============================================================================
# TEST 2: SESSION MANAGEMENT
# ==============================================================================

def test_session_management():
    print_section("TEST 2: SESSION MANAGEMENT")

    # Test 2.1: Create session (authenticated)
    print_test("2.1 - Create session (authenticated)")
    response = requests.post(
        f"{BASE_URL}/create-session",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={}
    )
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        session_id = data.get("session_id")
        print_test("2.1 - Create session", "PASS")
        print(f"   Session ID: {session_id}")
    else:
        print_test("2.1 - Create session", "FAIL")
        return False, None

    # Test 2.2: Create session (unauthenticated)
    print_test("2.2 - Create session (unauthenticated)")
    response = requests.post(f"{BASE_URL}/create-session", json={})
    print_response(response)

    if response.status_code == 200:
        print_test("2.2 - Create unauthenticated session", "PASS")
    else:
        print_test("2.2 - Create unauthenticated session", "FAIL")

    return True, session_id

# ==============================================================================
# TEST 3: SQL QUERY ENDPOINT
# ==============================================================================

def test_sql_queries(session_id):
    print_section("TEST 3: SQL QUERY PROCESSING")

    # Test 3.1: Simple SQL query
    print_test("3.1 - Process SQL query: 'How many orders do I have?'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "How many orders do I have?",
            "user_id": current_user.get("user_id"),
            "session_id": session_id
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "sql_query":
            print_test("3.1 - SQL query", "PASS")
            print(f"   SQL: {data.get('response_data', {}).get('generated_sql', 'N/A')[:80]}...")
        else:
            print_test("3.1 - SQL query", "FAIL")
            print(f"   Expected sql_query, got {data.get('query_type')}")
    else:
        print_test("3.1 - SQL query", "FAIL")

    # Test 3.2: Complex SQL query
    print_test("3.2 - Process SQL query: 'Show my orders from last week'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "Show my orders from last week",
            "user_id": current_user.get("user_id"),
            "session_id": session_id
        }
    )
    print_response(response)

    if response.status_code == 200 and response.json().get("query_type") == "sql_query":
        print_test("3.2 - Complex SQL query", "PASS")
    else:
        print_test("3.2 - Complex SQL query", "FAIL")

    return True

# ==============================================================================
# TEST 4: DOCUMENT SEARCH ENDPOINT
# ==============================================================================

def test_document_search(session_id):
    print_section("TEST 4: DOCUMENT SEARCH")

    # Test 4.1: Well-formed document search
    print_test("4.1 - Document search: 'Python machine learning tutorials'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "Python machine learning tutorials",
            "user_id": current_user.get("user_id"),
            "session_id": session_id
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "document_search":
            print_test("4.1 - Document search", "PASS")
        else:
            print_test("4.1 - Document search", "FAIL")
            print(f"   Expected document_search, got {data.get('query_type')}")
    else:
        print_test("4.1 - Document search", "FAIL")

    return True

# ==============================================================================
# TEST 5: QUERY REWRITING FLOW
# ==============================================================================

def test_query_rewriting():
    print_section("TEST 5: QUERY REWRITING FLOW")

    rewrite_session = f"rewrite-test-{int(time.time())}"

    # Test 5.1: Send query with grammatical error
    print_test("5.1 - Send query with error: 'Africa people'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "I'm looking for documents about Africa people",
            "user_id": current_user.get("user_id"),
            "session_id": rewrite_session
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "query_confirmation":
            print_test("5.1 - Query rewrite detected", "PASS")
            rewritten = data.get("response_data", {}).get("rewritten_query")
            print(f"   Original: 'Africa people'")
            print(f"   Rewritten: '{rewritten}'")
        else:
            print_test("5.1 - Query rewrite detection", "FAIL")
            return False
    else:
        print_test("5.1 - Query rewrite detection", "FAIL")
        return False

    # Test 5.2: Confirm with "Yes"
    print_test("5.2 - Confirm rewrite with 'Yes'")
    time.sleep(1)  # Brief pause for session consistency
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "Yes",
            "user_id": current_user.get("user_id"),
            "session_id": rewrite_session
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        original_msg = data.get("original_message", "")
        if "African people" in original_msg or "African people" in str(data):
            print_test("5.2 - Confirm rewrite", "PASS")
            print(f"   Used rewritten query: '{original_msg}'")
        else:
            print_test("5.2 - Confirm rewrite", "FAIL")
            print(f"   Expected 'African people', got '{original_msg}'")
    else:
        print_test("5.2 - Confirm rewrite", "FAIL")
        return False

    # Test 5.3: Test "No" (rephrase) flow
    print_test("5.3 - Test rephrase flow")
    rephrase_session = f"rephrase-test-{int(time.time())}"

    # Send error query
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "documents machine learning Python",
            "user_id": current_user.get("user_id"),
            "session_id": rephrase_session
        }
    )

    if response.status_code == 200 and response.json().get("query_type") == "query_confirmation":
        # Respond with "No"
        time.sleep(1)
        response = requests.post(
            f"{BASE_URL}/process-inquiry",
            json={
                "message": "No",
                "user_id": current_user.get("user_id"),
                "session_id": rephrase_session
            }
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("query_type") == "clarification_needed":
                print_test("5.3 - Rephrase flow", "PASS")
                print(f"   System asked: {data.get('response_data', {}).get('clarification_question')}")
            else:
                print_test("5.3 - Rephrase flow", "FAIL")
        else:
            print_test("5.3 - Rephrase flow", "FAIL")
    else:
        print_test("5.3 - Rephrase flow", "FAIL")

    return True

# ==============================================================================
# TEST 6: CLARIFICATION FLOW
# ==============================================================================

def test_clarification_flow():
    print_section("TEST 6: CLARIFICATION FLOW")

    clarif_session = f"clarif-test-{int(time.time())}"

    # Test 6.1: Ambiguous query
    print_test("6.1 - Send ambiguous query: 'I need help'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "I need help",
            "user_id": current_user.get("user_id"),
            "session_id": clarif_session
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "clarification_needed":
            print_test("6.1 - Clarification requested", "PASS")
            print(f"   Question: {data.get('response_data', {}).get('clarification_question', 'N/A')[:80]}...")
        else:
            print_test("6.1 - Clarification requested", "FAIL")
    else:
        print_test("6.1 - Clarification requested", "FAIL")

    # Test 6.2: Follow-up with context
    print_test("6.2 - Follow-up: 'with my orders'")
    time.sleep(1)
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "with my orders",
            "user_id": current_user.get("user_id"),
            "session_id": clarif_session
        }
    )
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "sql_query":
            print_test("6.2 - Context resolution", "PASS")
            print("   System understood context and routed to SQL")
        else:
            print_test("6.2 - Context resolution", "INFO")
            print(f"   Routed to: {data.get('query_type')}")
    else:
        print_test("6.2 - Context resolution", "FAIL")

    return True

# ==============================================================================
# TEST 7: CUSTOMER SERVICE
# ==============================================================================

def test_customer_service(session_id):
    print_section("TEST 7: CUSTOMER SERVICE")

    # Test 7.1: Technical support query
    print_test("7.1 - Customer service: 'My internet is not working'")
    response = requests.post(
        f"{BASE_URL}/process-inquiry",
        json={
            "message": "My internet is not working",
            "user_id": current_user.get("user_id"),
            "session_id": session_id
        }
    )
    print_response(response, show_full=True)

    if response.status_code == 200:
        data = response.json()
        if data.get("query_type") == "customer_service":
            print_test("7.1 - Customer service routing", "PASS")
            category = data.get("response_data", {}).get("category", "N/A")
            print(f"   Category: {category}")
        else:
            print_test("7.1 - Customer service routing", "FAIL")
            print(f"   Expected customer_service, got {data.get('query_type')}")
    else:
        print_test("7.1 - Customer service routing", "FAIL")

    return True

# ==============================================================================
# TEST 8: UNSUPPORTED QUERIES
# ==============================================================================

def test_unsupported_queries(session_id):
    print_section("TEST 8: UNSUPPORTED QUERIES")

    unsupported_queries = [
        ("Hello, how are you?", "greeting"),
        ("What's the weather today?", "weather"),
        ("Tell me a joke", "entertainment")
    ]

    for query, query_type in unsupported_queries:
        print_test(f"8.x - Unsupported query: '{query}'")
        response = requests.post(
            f"{BASE_URL}/process-inquiry",
            json={
                "message": query,
                "user_id": current_user.get("user_id"),
                "session_id": session_id
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

    return True

# ==============================================================================
# TEST 9: CHAT HISTORY
# ==============================================================================

def test_chat_history(session_id):
    print_section("TEST 9: CHAT HISTORY")

    # Test 9.1: Get chat history
    print_test("9.1 - Get chat history")
    response = requests.get(f"{BASE_URL}/chat-history/{session_id}?limit=10")
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        message_count = len(data.get("messages", []))
        print_test("9.1 - Get chat history", "PASS")
        print(f"   Messages in session: {message_count}")
    else:
        print_test("9.1 - Get chat history", "FAIL")
        return False

    # Test 9.2: Get user sessions (authenticated)
    print_test("9.2 - Get user sessions")
    response = requests.get(
        f"{BASE_URL}/me/sessions",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        session_count = len(data.get("sessions", []))
        print_test("9.2 - Get user sessions", "PASS")
        print(f"   User has {session_count} sessions")
    else:
        print_test("9.2 - Get user sessions", "FAIL")

    return True

# ==============================================================================
# MAIN TEST RUNNER
# ==============================================================================

def main():
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "COMPLETE END-TO-END API TEST SUITE" + " " * 24 + "║")
    print("╚" + "═" * 78 + "╝")
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base URL: {BASE_URL}")

    try:
        # Run all tests
        if not test_authentication():
            print("\n❌ Authentication tests failed. Stopping.")
            return

        success, session_id = test_session_management()
        if not success:
            print("\n❌ Session management tests failed. Stopping.")
            return

        test_sql_queries(session_id)
        test_document_search(session_id)
        test_query_rewriting()
        test_clarification_flow()
        test_customer_service(session_id)
        test_unsupported_queries(session_id)
        test_chat_history(session_id)

        # Final summary
        print_section("TEST SUMMARY")
        print("✅ All test suites completed!")
        print(f"\nTest user: {TEST_USER}")
        print(f"Main session: {session_id}")
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
