#!/usr/bin/env python3
"""
Quick diagnostic test for SQL agent
"""
import requests
import json

BASE_URL = "http://localhost:8000/api"

# Test 1: Simple SQL query
print("=" * 70)
print("TEST: Simple SQL Query")
print("=" * 70)

response = requests.post(
    f"{BASE_URL}/process-inquiry",
    json={
        "message": "Show me all my orders",
        "user_id": "test123",
        "session_id": "test-session-123"
    }
)

print(f"Status Code: {response.status_code}")
print(f"Response:")
print(json.dumps(response.json(), indent=2))

print("\n" + "=" * 70)
print("TEST 2: Count query")
print("=" * 70)

response2 = requests.post(
    f"{BASE_URL}/process-inquiry",
    json={
        "message": "How many orders do I have?",
        "user_id": "test123",
        "session_id": "test-session-456"
    }
)

print(f"Status Code: {response2.status_code}")
print(f"Response:")
print(json.dumps(response2.json(), indent=2))
