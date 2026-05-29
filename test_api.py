import httpx
resp = httpx.post('http://localhost:8000/api/chat-messages', json={
    'agentId': 'b2f4f098-3759-443e-ae4a-9ab8d42c421f',
    'sessionId': '269287f4-ff7a-4a08-92e2-abea8861fc84',
    'content': '你好',
    'role': 'user'
}, timeout=10)
print('Status:', resp.status_code)
print('Body:', resp.text[:500])
