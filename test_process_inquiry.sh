#!/bin/bash

# Process-Inquiry Endpoint Integration Test Script
# Tests the unified /process-inquiry endpoint with 3-way routing

set -e  # Exit on error

BASE_URL="http://localhost:8000/api"
echo "Testing Process-Inquiry Endpoint at $BASE_URL"
echo "=============================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Helper function to test routing
test_route() {
    local test_name="$1"
    local message="$2"
    local expected_type="$3"

    echo -e "\n${BLUE}Test: $test_name${NC}"
    echo "Message: \"$message\""

    RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"$message\"}")

    ACTUAL_TYPE=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('query_type', 'ERROR'))" 2>/dev/null || echo "ERROR")

    if [ "$ACTUAL_TYPE" = "$expected_type" ]; then
        echo -e "${GREEN}✓ Correctly routed to: $ACTUAL_TYPE${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ Expected: $expected_type, Got: $ACTUAL_TYPE${NC}"
        echo "Full response: $RESPONSE"
        ((FAILED++))
        return 1
    fi
}

echo ""
echo "================================================"
echo "PART 1: Testing Router Classification"
echo "================================================"

# Customer Service Routes
test_route "Customer Service - Technical Issue" \
    "My internet is not working" \
    "customer_service"

test_route "Customer Service - Billing Question" \
    "I need help with my bill" \
    "customer_service"

test_route "Customer Service - General Inquiry" \
    "What are your business hours?" \
    "customer_service"

# Document Search Routes
test_route "Document Search - What is" \
    "What is Python programming?" \
    "document_search"

test_route "Document Search - Explain" \
    "Explain machine learning" \
    "document_search"

test_route "Document Search - Tutorial" \
    "Show me FastAPI tutorials" \
    "document_search"

# SQL Query Routes
test_route "SQL Query - Count" \
    "How many orders are in the database?" \
    "sql_query"

test_route "SQL Query - Show" \
    "Show me all customers" \
    "sql_query"

test_route "SQL Query - Analysis" \
    "What is the total revenue?" \
    "sql_query"

echo ""
echo "================================================"
echo "PART 2: Testing Response Structures"
echo "================================================"

# Test Customer Service Response Structure
echo -e "\n${YELLOW}Testing Customer Service Response Structure${NC}"
CS_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "My internet is broken"}')

CS_CATEGORY=$(echo "$CS_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('response_data', {}).get('category', 'MISSING'))" 2>/dev/null || echo "ERROR")

if [ "$CS_CATEGORY" != "MISSING" ] && [ "$CS_CATEGORY" != "ERROR" ]; then
    echo -e "${GREEN}✓ Customer service returns category: $CS_CATEGORY${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Customer service missing category field${NC}"
    ((FAILED++))
fi

# Test Document Search Response Structure
echo -e "\n${YELLOW}Testing Document Search Response Structure${NC}"
DOC_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "What is artificial intelligence?"}')

DOC_RESULTS=$(echo "$DOC_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('response_data', {}).get('total_results', 'MISSING'))" 2>/dev/null || echo "ERROR")

if [ "$DOC_RESULTS" != "MISSING" ] && [ "$DOC_RESULTS" != "ERROR" ]; then
    echo -e "${GREEN}✓ Document search returns total_results: $DOC_RESULTS${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Document search missing total_results field${NC}"
    ((FAILED++))
fi

# Test SQL Query Response Structure
echo -e "\n${YELLOW}Testing SQL Query Response Structure${NC}"
SQL_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "Count all users"}')

SQL_ANSWER=$(echo "$SQL_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('response_data', {}).get('natural_language_answer', 'MISSING'))" 2>/dev/null || echo "ERROR")

if [ "$SQL_ANSWER" != "MISSING" ] && [ "$SQL_ANSWER" != "ERROR" ]; then
    echo -e "${GREEN}✓ SQL query returns natural_language_answer${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ SQL query missing natural_language_answer field${NC}"
    ((FAILED++))
fi

echo ""
echo "================================================"
echo "PART 3: Testing Session Management"
echo "================================================"

# Test with explicit session_id
echo -e "\n${YELLOW}Testing Session Management${NC}"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello", "session_id": "test-session-123"}')

RETURNED_SESSION=$(echo "$SESSION_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', 'MISSING'))" 2>/dev/null || echo "ERROR")

if [ "$RETURNED_SESSION" = "test-session-123" ]; then
    echo -e "${GREEN}✓ Session ID preserved: $RETURNED_SESSION${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Session ID not preserved. Expected: test-session-123, Got: $RETURNED_SESSION${NC}"
    ((FAILED++))
fi

# Test with user_id
echo -e "\n${YELLOW}Testing User ID Support${NC}"
USER_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "Test message", "user_id": "test-user-456"}')

USER_SUCCESS=$(echo "$USER_RESPONSE" | python3 -c "import sys, json; print('query_type' in json.load(sys.stdin))" 2>/dev/null || echo "False")

if [ "$USER_SUCCESS" = "True" ]; then
    echo -e "${GREEN}✓ User ID parameter accepted${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ User ID parameter caused error${NC}"
    ((FAILED++))
fi

echo ""
echo "================================================"
echo "PART 4: Testing Edge Cases"
echo "================================================"

# Test empty message
echo -e "\n${YELLOW}Testing Empty Message Handling${NC}"
EMPTY_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": ""}' 2>&1)

if echo "$EMPTY_RESPONSE" | grep -q "detail"; then
    echo -e "${GREEN}✓ Empty message rejected with proper error${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ Empty message handling unclear${NC}"
fi

# Test very long message
echo -e "\n${YELLOW}Testing Long Message Handling${NC}"
LONG_MSG="$(printf 'word %.0s' {1..500})"
LONG_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"$LONG_MSG\"}" 2>&1)

if echo "$LONG_RESPONSE" | grep -q "query_type"; then
    echo -e "${GREEN}✓ Long message handled successfully${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ Long message may have issues${NC}"
fi

# Test special characters
echo -e "\n${YELLOW}Testing Special Characters${NC}"
SPECIAL_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "What is SQL injection? SELECT * FROM users; DROP TABLE users;"}')

SPECIAL_TYPE=$(echo "$SPECIAL_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('query_type', 'ERROR'))" 2>/dev/null || echo "ERROR")

if [ "$SPECIAL_TYPE" != "ERROR" ]; then
    echo -e "${GREEN}✓ Special characters handled: $SPECIAL_TYPE${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Special characters caused error${NC}"
    ((FAILED++))
fi

echo ""
echo "================================================"
echo "PART 5: Testing Unsupported Query Types"
echo "================================================"

# Test greeting
echo -e "\n${YELLOW}Testing Greeting (Unsupported)${NC}"
GREETING_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello, how are you?"}')

GREETING_TYPE=$(echo "$GREETING_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('query_type', 'ERROR'))" 2>/dev/null || echo "ERROR")

if [ "$GREETING_TYPE" = "unsupported" ]; then
    echo -e "${GREEN}✓ Greeting correctly classified as unsupported${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Greeting not handled correctly. Got: $GREETING_TYPE${NC}"
    ((FAILED++))
fi

# Test weather query
echo -e "\n${YELLOW}Testing Weather Query (Unsupported)${NC}"
WEATHER_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "What is the weather like today?"}')

WEATHER_TYPE=$(echo "$WEATHER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('query_type', 'ERROR'))" 2>/dev/null || echo "ERROR")

if [ "$WEATHER_TYPE" = "unsupported" ]; then
    echo -e "${GREEN}✓ Weather query correctly classified as unsupported${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Weather query not handled correctly. Got: $WEATHER_TYPE${NC}"
    ((FAILED++))
fi

# Test joke request
echo -e "\n${YELLOW}Testing Joke Request (Unsupported)${NC}"
JOKE_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "Tell me a joke"}')

JOKE_TYPE=$(echo "$JOKE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('query_type', 'ERROR'))" 2>/dev/null || echo "ERROR")

if [ "$JOKE_TYPE" = "unsupported" ]; then
    echo -e "${GREEN}✓ Joke request correctly classified as unsupported${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Joke request not handled correctly. Got: $JOKE_TYPE${NC}"
    ((FAILED++))
fi

# Test coding request
echo -e "\n${YELLOW}Testing Coding Request (Unsupported)${NC}"
CODE_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "Write a Python function to sort a list"}')

CODE_TYPE=$(echo "$CODE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('query_type', 'ERROR'))" 2>/dev/null || echo "ERROR")

if [ "$CODE_TYPE" = "unsupported" ]; then
    echo -e "${GREEN}✓ Coding request correctly classified as unsupported${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Coding request not handled correctly. Got: $CODE_TYPE${NC}"
    ((FAILED++))
fi

# Test that unsupported message is clear
echo -e "\n${YELLOW}Testing Unsupported Error Message${NC}"
UNSUPPORTED_MSG=$(echo "$CODE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('response_data', {}).get('message', 'MISSING'))" 2>/dev/null || echo "ERROR")

if echo "$UNSUPPORTED_MSG" | grep -q "SQL queries, document search queries, and customer service"; then
    echo -e "${GREEN}✓ Unsupported message is clear and informative${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Unsupported message unclear${NC}"
    ((FAILED++))
fi

echo ""
echo "================================================"
echo "PART 6: Testing Response Time"
echo "================================================"

echo -e "\n${YELLOW}Testing Response Time (should be < 30s)${NC}"
START_TIME=$(date +%s)
TIME_RESPONSE=$(curl -s -X POST "$BASE_URL/process-inquiry" \
    -H "Content-Type: application/json" \
    -d '{"message": "Quick test"}')
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [ $DURATION -lt 30 ]; then
    echo -e "${GREEN}✓ Response time: ${DURATION}s (acceptable)${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ Response time: ${DURATION}s (slow)${NC}"
fi

echo ""
echo "================================================"
echo "Test Summary"
echo "================================================"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! The endpoint is working correctly.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the errors above.${NC}"
    exit 1
fi
