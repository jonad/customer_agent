#!/bin/bash
set -e

USER_ID="test-user-123"
echo "============================================================"
echo "TEXT-TO-SQL INTEGRATION TEST"
echo "============================================================"
echo "User: $USER_ID"

# Test 1: Create session
echo -e "\n1️⃣  Creating test session..."
SESSION=$(curl -s -X POST "http://localhost:8000/api/create-session" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER_ID\", \"title\": \"SQL Test Session\"}")
SESSION_ID=$(echo "$SESSION" | jq -r '.session_id')
echo "✅ Session created: $SESSION_ID"

# Test 2: SQL Query - Count orders
echo -e "\n2️⃣  Testing SQL Query: 'How many orders do I have?'"
echo "Sending request..."
curl -N -X POST "http://localhost:8000/api/stream-chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"How many orders do I have?\", \"user_id\": \"$USER_ID\", \"session_id\": \"$SESSION_ID\"}" \
  2>/dev/null | head -20

echo -e "\n"

# Test 3: Customer Service Query
echo -e "\n3️⃣  Testing Customer Service Query: 'My internet is not working'"
echo "Sending request..."
SESSION2=$(curl -s -X POST "http://localhost:8000/api/create-session" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER_ID\", \"title\": \"CS Test Session\"}")
SESSION_ID2=$(echo "$SESSION2" | jq -r '.session_id')

curl -N -X POST "http://localhost:8000/api/stream-chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"My internet is not working\", \"user_id\": \"$USER_ID\", \"session_id\": \"$SESSION_ID2\"}" \
  2>/dev/null | head -20

echo -e "\n"

# Test 4: Check chat history
echo -e "\n4️⃣  Checking chat history..."
HISTORY=$(curl -s "http://localhost:8000/api/chat-history/$SESSION_ID" | jq '.messages | length')
echo "✅ Messages in SQL session: $HISTORY"

# Cleanup
echo -e "\n5️⃣  Cleaning up..."
curl -s -X DELETE "http://localhost:8000/api/sessions/$SESSION_ID" > /dev/null
curl -s -X DELETE "http://localhost:8000/api/sessions/$SESSION_ID2" > /dev/null
echo "✅ Test sessions deleted"

echo -e "\n============================================================"
echo "✅ INTEGRATION TEST COMPLETE!"
echo "============================================================"
