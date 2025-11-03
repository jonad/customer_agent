#!/usr/bin/env python3
"""
Test script for SSE endpoint with unsupported queries
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def test_sse_unsupported_query(message, description):
    """Test SSE endpoint with an unsupported query"""
    print(f"\n{'='*60}")
    print(f"Test: {description}")
    print(f"Message: {message}")
    print('='*60)

    url = f"{BASE_URL}/stream-chat"
    payload = {
        "message": message,
        "user_id": "test-user"
    }

    try:
        # Make SSE request
        response = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=15,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code != 200:
            print(f"❌ Error: HTTP {response.status_code}")
            print(response.text)
            return False

        print("\n📡 SSE Events:")
        events = []
        final_response = None

        # Read SSE stream
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data = line_str[6:]  # Remove 'data: ' prefix
                    try:
                        event = json.loads(data)
                        events.append(event)

                        event_type = event.get('event_type', 'unknown')
                        event_data = event.get('data', '')

                        print(f"  • {event_type}: {event_data[:100]}")

                        # Capture final response
                        if event_type == 'final_response':
                            try:
                                final_response = json.loads(event_data)
                            except:
                                final_response = event_data
                    except json.JSONDecodeError:
                        print(f"  • [Raw]: {data[:100]}")

        # Analyze results
        print("\n📊 Analysis:")
        print(f"  Total events received: {len(events)}")

        if final_response:
            print(f"\n✅ Final Response:")
            print(json.dumps(final_response, indent=2))

            # Check if it's an unsupported error response
            if isinstance(final_response, dict):
                if 'error' in final_response and final_response.get('error') == 'unsupported_query_type':
                    print("\n✅ SUCCESS: Query correctly classified as unsupported!")
                    print(f"   Message: {final_response.get('message', 'N/A')}")
                    print(f"   Received type: {final_response.get('received_type', 'N/A')}")
                    return True
                else:
                    print("\n⚠️  WARNING: Response doesn't match expected unsupported structure")
                    return False
        else:
            print("\n❌ FAILED: No final response received")
            return False

    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("="*60)
    print("Testing SSE Endpoint with Unsupported Queries")
    print("="*60)

    test_cases = [
        ("Hello, how are you?", "Greeting (should be unsupported)"),
        ("Tell me a joke", "Joke request (should be unsupported)"),
        ("What's the weather like today?", "Weather query (should be unsupported)"),
        ("Write a Python function to sort a list", "Coding request (should be unsupported)"),
    ]

    results = []
    for message, description in test_cases:
        result = test_sse_unsupported_query(message, description)
        results.append((description, result))
        time.sleep(1)  # Brief pause between tests

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed

    for description, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {description}")

    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\n🎉 All tests passed! SSE unsupported query handling works correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the output above.")

if __name__ == "__main__":
    main()
