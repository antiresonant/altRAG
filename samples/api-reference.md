---
title: Platform API Reference
version: 2.4.0
last_updated: 2026-03-15
---

# Platform API Reference

REST API for the core platform. Base URL: `https://api.platform.io/v2`

## Authentication

All requests require authentication via one of the following methods.

### API Keys

Include your API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: sk_live_abc123" https://api.platform.io/v2/users
```

Keys are scoped: `read`, `write`, or `admin`. Rotate every 90 days.

### OAuth 2.0

For user-facing integrations. Supports authorization code flow.

1. Redirect to `/oauth/authorize?client_id=...&redirect_uri=...&scope=read+write`
2. User approves, redirected back with `?code=...`
3. Exchange code for token: `POST /oauth/token`
4. Use Bearer token in `Authorization` header

Token lifetime: 1 hour. Refresh tokens last 30 days.

### JWT Tokens

For service-to-service auth. Sign with your private key:

```python
import jwt
token = jwt.encode({"sub": "service-id", "exp": time() + 3600}, private_key, algorithm="RS256")
```

Include as `Authorization: Bearer <token>`.

## Endpoints

### Users

**Create User**

`POST /users`

```json
{
  "email": "user@example.com",
  "name": "Jane Doe",
  "role": "member"
}
```

Returns `201` with user object. Sends welcome email.

**Get User**

`GET /users/:id`

Returns user profile. Requires `read` scope.

**Update User**

`PATCH /users/:id`

Partial update. Only include fields to change.

**Delete User**

`DELETE /users/:id`

Soft-deletes the user. Data retained for 30 days. Requires `admin` scope.

### Products

**List Products**

`GET /products?page=1&per_page=20`

Supports filtering: `?category=electronics&min_price=100`
Supports sorting: `?sort=price&order=desc`

**Get Product**

`GET /products/:id`

Returns full product details including inventory count and pricing tiers.

**Create Product**

`POST /products`

```json
{
  "name": "Widget Pro",
  "sku": "WGT-PRO-001",
  "price": 29.99,
  "category": "electronics"
}
```

### Orders

**Place Order**

`POST /orders`

```json
{
  "items": [{"product_id": "prod_123", "quantity": 2}],
  "shipping_address": {"..."},
  "payment_method": "pm_456"
}
```

Returns `202 Accepted` — order processing is async.
Poll `GET /orders/:id` for status updates.

**Get Order Status**

`GET /orders/:id`

Status values: `pending`, `confirmed`, `shipped`, `delivered`, `cancelled`.

## Webhooks

### Event Types

Subscribe to events via `POST /webhooks`:

- `user.created` — new user registered
- `order.placed` — order submitted
- `order.shipped` — tracking number assigned
- `payment.failed` — charge declined

### Payload Format

```json
{
  "id": "evt_789",
  "type": "order.placed",
  "created_at": "2026-03-15T10:30:00Z",
  "data": {"order_id": "ord_123", "total": 59.98}
}
```

### Verification

Verify webhook signatures using HMAC-SHA256:

```python
import hmac, hashlib
expected = hmac.new(webhook_secret, payload_bytes, hashlib.sha256).hexdigest()
assert expected == request.headers["X-Signature"]
```

## Rate Limits

| Scope    | Limit          | Window |
|----------|----------------|--------|
| API Key  | 1000 req/min   | sliding |
| OAuth    | 500 req/min    | sliding |
| Admin    | 100 req/min    | fixed   |

Rate limit headers: `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

When rate limited, you receive `429 Too Many Requests` with `Retry-After` header.

## Error Codes

| Code | Meaning                | Action                          |
|------|------------------------|---------------------------------|
| 400  | Bad Request            | Check request body/params       |
| 401  | Unauthorized           | Check auth credentials          |
| 403  | Forbidden              | Insufficient scope/permissions  |
| 404  | Not Found              | Verify resource ID exists       |
| 409  | Conflict               | Resource already exists         |
| 422  | Unprocessable Entity   | Validation failed — see errors  |
| 429  | Rate Limited           | Back off, retry after header    |
| 500  | Internal Server Error  | Retry with exponential backoff  |
| 503  | Service Unavailable    | System maintenance, retry later |

Error response format:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Email is already in use",
    "field": "email"
  }
}
```
