# API Protocol

This document defines the initial communication contract between the Flutter app and the FastAPI backend.

## Transport
- HTTP over JSON
- Base path: /api/v1
- Content-Type: application/json

## Response envelope
Success:
```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

Error:
```json
{
  "code": 1000,
  "message": "error message",
  "data": null
}
```

## Reserved endpoints
- GET /health
- GET /version
- POST /auth/login
- POST /auth/logout

## Notes
- Fields, validation rules, and auth details will be expanded with implementation.
- TODO: JerryChen-USTB
