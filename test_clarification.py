#!/usr/bin/env python3
"""
Test script for query clarification feature
"""
import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_clarification_queries():
    """Test various ambiguous queries that should trigger clarification"""

    test_cases = [
        {
            "query": "I need help",
            "description": "Very vague query - should ask for clarification",
            "expected_type": "clarification_needed"
        },
        {
            "query": "Show me data",
            "description": "Ambiguous - could be SQL or document search",
            "expected_type": "clarification_needed"
        },
        {
            "query": "Information about orders",
            "description": "Could be order data or documentation",
            "expected_type": "clarification_needed"
        },
        {
            "query": "How many orders do I have?",
            "description": "Clear SQL query - should NOT need clarification",
            "expected_type": "sql_query"
        },
        {
            "query": "What is FastAPI?",
            "description": "Clear document search - should NOT need clarification",
            "expected_type": "document_search"
        }
    ]

    print("=" * 80)
    print("CLARIFICATION FEATURE TEST")
    print("=" * 80)

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\nTest {i}: {test_case['description']}")
        print(f"Query: \"{test_case['query']}\"")
        print(f"Expected type: {test_case['expected_type']}")
        print("-" * 80)

        try:
            response = requests.post(
                f"{BASE_URL}/process-inquiry",
                json={
                    "message": test_case["query"],
                    "user_id": "test-user",
                    "session_id": f"test-session-{i}"
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                query_type = data.get("query_type")

                print(f"✅ Status: {response.status_code}")
                print(f"📊 Actual type: {query_type}")

                if query_type == "clarification_needed":
                    clarification = data.get("response_data", {}).get("clarification_question")
                    reasoning = data.get("response_data", {}).get("reasoning")
                    confidence = data.get("response_data", {}).get("confidence")

                    print(f"❓ Clarification question: {clarification}")
                    print(f"💭 Reasoning: {reasoning}")
                    print(f"📈 Confidence: {confidence}")

                # Check if result matches expectation
                if query_type == test_case["expected_type"]:
                    print(f"✅ PASS: Got expected type")
                    results.append(True)
                else:
                    print(f"⚠️  NOTE: Got '{query_type}' instead of expected '{test_case['expected_type']}'")
                    results.append(False)

            else:
                print(f"❌ FAIL: Status {response.status_code}")
                print(f"Error: {response.text}")
                results.append(False)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append(False)

    # Summary
    print("\n\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(results)
    total = len(results)

    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {total - passed} test(s) had different results than expected")
        print("Note: This is expected as the LLM may classify differently")

    return results

if __name__ == "__main__":
    test_clarification_queries()
