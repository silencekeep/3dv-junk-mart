# API Protocol

This document defines the stable communication contract between the Flutter frontend and the FastAPI backend.

## 1. Design Goals
- Keep the frontend decoupled from the backend implementation.
- Keep the contract resource-oriented, while still supporting page bootstrap responses for fast rendering.
- Keep fields additive and versioned so existing clients continue to work after new releases.
- Keep layout logic out of the API; the backend returns data sections, not widget trees.

## 2. Transport Rules
- Base path: `/api/v1`
- Protocol: HTTPS in production, HTTP allowed only in local development
- Payload format: JSON UTF-8
- Default content type: `application/json`
- Auth header: `Authorization: Bearer <access_token>`
- Optional headers:
  - `X-Request-Id` for trace correlation
  - `Idempotency-Key` for write operations that must not be duplicated
  - `Accept-Language` for localized text
- IDs are opaque strings. Use ULID or UUID on the backend, but never expose database-specific numeric IDs to the client.
- Timestamps are RFC3339 UTC strings, for example `2026-04-08T10:15:30Z`.
- Money values use minor units plus currency code, for example `amount_minor: 24500`, `currency: "CNY"`.
- Empty collections must be returned as `[]`, not `null`.
- Optional fields may be omitted if not relevant to the current state.

## 3. Response Envelope
All endpoints should return the same envelope shape.

Success:
```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "meta": {
    "request_id": "01J...",
    "cache_ttl_seconds": 60
  }
}
```

Error:
```json
{
  "code": 2001,
  "message": "validation failed",
  "data": null,
  "errors": [
    {
      "field": "price_minor",
      "reason": "must be greater than zero"
    }
  ],
  "meta": {
    "request_id": "01J..."
  }
}
```

### 3.1 Pagination Meta
Paginated responses should use `meta.page`.

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": []
  },
  "meta": {
    "page": {
      "page": 1,
      "page_size": 20,
      "next_cursor": null,
      "total": 126
    }
  }
}
```

### 3.2 Error Code Ranges
- `0` - success
- `1000-1999` - authentication and authorization
- `2000-2999` - validation and request shape issues
- `3000-3999` - business rule conflicts and state violations
- `4000-4999` - payment, logistics, and order lifecycle errors
- `5000-5999` - system and infrastructure errors

## 4. Shared Resource Schemas
The frontend should build screens from these shared resources instead of reading page-specific ad hoc payloads.

### 4.1 media_asset
| field | type | note |
| --- | --- | --- |
| id | string | opaque asset id |
| kind | string | `image`, `video`, `document` |
| url | string | CDN or signed URL |
| thumbnail_url | string | optional preview URL |
| width | integer | optional |
| height | integer | optional |
| mime_type | string | optional |
| sort_order | integer | stable ordering |

### 4.2 money
| field | type | note |
| --- | --- | --- |
| amount_minor | integer | minor units, never float |
| currency | string | ISO 4217 code such as `CNY` |

### 4.3 user_summary
| field | type | note |
| --- | --- | --- |
| id | string | user id |
| display_name | string | profile name |
| avatar_url | string | avatar image |
| bio | string | optional |
| location | string | optional city/region |
| sesame_credit_score | integer | profile trust score |
| vip_level | string | example: `none`, `silver`, `gold` |
| follower_count | integer | optional aggregated value |
| following_count | integer | optional aggregated value |
| positive_rate | number | optional ratio |

### 4.4 listing_summary
| field | type | note |
| --- | --- | --- |
| id | string | listing id |
| title | string | listing title |
| subtitle | string | optional short desc |
| price | money | current price |
| original_price | money | optional crossed-out price |
| status | string | `draft`, `live`, `reserved`, `sold`, `archived` |
| cover_media | media_asset | primary card image |
| location | string | seller location or shipping region |
| badges | array[string] | example: `verified`, `nearby` |
| seller | user_summary | seller snapshot |

### 4.5 conversation_summary
| field | type | note |
| --- | --- | --- |
| id | string | conversation id |
| listing_id | string | related listing |
| other_user | user_summary | counterpart snapshot |
| last_message_preview | string | preview text |
| unread_count | integer | badge count |
| updated_at | string | last activity time |

### 4.6 order_summary
| field | type | note |
| --- | --- | --- |
| id | string | order id |
| status | string | `unpaid`, `paid`, `shipped`, `in_transit`, `delivered`, `completed`, `canceled`, `refunded` |
| buyer | user_summary | buyer snapshot |
| seller | user_summary | seller snapshot |
| item_snapshot | object | immutable item data captured at order time |
| totals | object | money breakdown |
| logistics | object | shipment snapshot |
| can_confirm_receipt | boolean | UI action flag |

### 4.7 review_summary
| field | type | note |
| --- | --- | --- |
| id | string | review id |
| order_id | string | source order |
| listing_id | string | related listing |
| rating | integer | 1 to 5 |
| tags | array[string] | review tag keys |
| content | string | free text |
| media | array[media_asset] | optional review photos |
| anonymity_enabled | boolean | privacy flag |

### 4.8 service_card
| field | type | note |
| --- | --- | --- |
| service_key | string | stable key |
| title | string | visible label |
| icon | string | icon key or asset ref |
| badge | string | optional badge |
| description | string | short helper text |
| destination_type | string | `route`, `url`, `feature_flag`, `resource` |
| destination_ref | string | deep-link target |

### 4.9 page_section
| field | type | note |
| --- | --- | --- |
| section_type | string | example: `hero`, `grid`, `list`, `form`, `notice` |
| section_id | string | stable identifier |
| title | string | optional |
| subtitle | string | optional |
| items | array[object] | section payload |
| actions | array[object] | CTA metadata |
| ui_hints | object | optional rendering hints only |

### 4.10 auth_identity
| field | type | note |
| --- | --- | --- |
| id | string | identity id |
| user_id | string | owning user id |
| kind | string | `phone`, `email`, `username`, or `oauth` |
| value | string | normalized login value |
| is_primary | boolean | primary sign-in identity |
| is_verified | boolean | verification state |
| verified_at | string | optional verification time |

### 4.11 auth_session
| field | type | note |
| --- | --- | --- |
| id | string | session id |
| user | user_summary | current user snapshot |
| access_token | string | short-lived bearer token |
| access_token_expires_at | string | access token expiry |
| refresh_token_expires_at | string | refresh token expiry |
| device_name | string | optional device label |
| device_platform | string | optional platform label |
| is_new_user | boolean | true for first registration response |

### 4.12 user_profile_detail
| field | type | note |
| --- | --- | --- |
| id | string | user id |
| display_name | string | nickname shown in the UI |
| avatar_url | string | avatar image |
| birth_date | string | stored date of birth |
| age_years | integer | derived from birth date |
| bio | string | optional profile bio |
| location | string | optional location string |
| sesame_credit_score | integer | trust score |
| vip_level | string | membership tier |
| profile_visibility | string | `public`, `friends`, `private` |
| updated_at | string | last profile update time |

### 4.13 user_profile_update
| field | type | note |
| --- | --- | --- |
| display_name | string | nickname shown in the UI |
| avatar_url | string | avatar image URL |
| birth_date | string | date of birth |
| bio | string | optional profile bio |
| location | string | optional location string |
| profile_visibility | string | `public`, `friends`, `private` |

## 5. System Endpoints
| method | path | purpose |
| --- | --- | --- |
| GET | `/health` | health probe |
| GET | `/version` | build and API version |
| GET | `/config/public` | public app config and feature flags |

## 6. Auth and Session
The auth flow is the entry point for the app and must stay aligned with the login and register pages.

| method | path | purpose |
| --- | --- | --- |
| GET | `/pages/auth/login` | bootstrap login screen |
| GET | `/pages/auth/register` | bootstrap register screen |
| POST | `/auth/register` | create account and issue session |
| POST | `/auth/login` | sign in |
| POST | `/auth/logout` | sign out |
| POST | `/auth/refresh` | refresh access token |
| GET | `/auth/session` | current session snapshot |
| GET | `/pages/me/settings` | bootstrap profile settings screen |
| GET | `/users/me` | current user profile detail |
| PATCH | `/users/me` | update current user profile detail |

Auth bootstrap should include:
- login screen: identifier field, password field, remember-device state, guest entry action, and switch-to-register action
- register screen: display name, identifier field, password fields, terms consent, and switch-to-login action
- profile settings screen: avatar, nickname, birth date, age preview, bio, location, and profile visibility selector

Auth responses should return `user_summary` and `auth_session` together so the app can enter the marketplace shell without extra round-trips.
`PATCH /users/me` should accept `user_profile_update` and return `user_profile_detail`.
Profile settings responses should return `user_profile_detail` so avatar, nickname, and age can be edited from a single source of truth.

## 7. Home and Navigation Data
The home screen is composed from server-driven sections.

| method | path | purpose |
| --- | --- | --- |
| GET | `/pages/home` | bootstrap the home screen |
| GET | `/home/feed` | curated feed and recommendations |
| GET | `/categories` | category grid data |
| GET | `/service-catalog` | profile service tiles and shortcuts |
| GET | `/banners` | promotional hero banners |

Home page sections should include:
- hero banner
- category grid
- curated picks
- quick action cards
- recommended items

## 8. Search and Discovery
The search screen should work from query plus facets, never from hardcoded cards.

| method | path | purpose |
| --- | --- | --- |
| GET | `/pages/search` | bootstrap search screen |
| GET | `/search/suggestions` | typeahead and recent queries |
| GET | `/search/facets` | facet counts and filter chips |
| GET | `/listings` | search results and listing collection |
| GET | `/categories/{category_id}/listings` | category browsing |

The search bootstrap should return:
- query summary card
- selected chips
- result list or grid
- empty state hints
- related suggestions

## 9. Listings and Sell Flow
These endpoints cover the product detail screen, the sell flow, and the seller-side listing management.

| method | path | purpose |
| --- | --- | --- |
| GET | `/pages/listings/{listing_id}` | bootstrap product detail |
| GET | `/listings/{listing_id}` | listing detail |
| GET | `/listings/{listing_id}/media` | listing media gallery |
| GET | `/listings/{listing_id}/seller` | seller snapshot |
| GET | `/listings/{listing_id}/specs` | structured item attributes |
| GET | `/listings/{listing_id}/similar` | similar listings |
| GET | `/listings/{listing_id}/inquiries` | question and answer thread summaries |
| POST | `/listings/{listing_id}/favorite` | mark as liked |
| DELETE | `/listings/{listing_id}/favorite` | remove from liked |
| POST | `/listings/drafts` | create a sell draft |
| GET | `/listings/drafts/{draft_id}` | load draft for editing |
| PATCH | `/listings/drafts/{draft_id}` | update draft content |
| POST | `/listings/drafts/{draft_id}/publish` | publish the listing |
| POST | `/uploads/presign` | request upload URL for photos/videos |

Sell flow bootstrap should return:
- photo slots and upload state
- title and description fields
- category and condition selectors
- pricing controls
- shipping options
- trust and risk notices

## 10. Conversations and Chat
The message screen should be powered by conversation resources and a message stream.

| method | path | purpose |
| --- | --- | --- |
| GET | `/pages/conversations/{conversation_id}` | bootstrap chat detail |
| GET | `/conversations` | conversation list |
| GET | `/conversations/{conversation_id}` | conversation detail snapshot |
| GET | `/conversations/{conversation_id}/messages` | message history |
| POST | `/conversations/{conversation_id}/messages` | send a message |
| POST | `/conversations/{conversation_id}/read` | mark messages as read |
| POST | `/conversations/{conversation_id}/typing` | optional typing indicator |

Conversation detail payload should include:
- item preview card
- safety banner
- message list
- composer state
- unread badge count

## 11. Orders and Logistics
These endpoints cover the order detail screen, receipt confirmation, and shipping timeline.

| method | path | purpose |
| --- | --- | --- |
| GET | `/pages/orders/{order_id}/success` | bootstrap payment success view |
| GET | `/pages/orders/{order_id}` | bootstrap order detail |
| GET | `/orders/{order_id}` | order detail |
| GET | `/orders/{order_id}/timeline` | logistics timeline |
| GET | `/orders/{order_id}/receipt` | receipt and summary data |
| POST | `/orders/{order_id}/confirm-receipt` | confirm delivery |
| POST | `/orders/{order_id}/cancel` | cancel if allowed |
| POST | `/orders/{order_id}/dispute` | open a dispute |

Order detail payload should include:
- status panel
- shipping address
- item snapshot card
- order information
- price breakdown
- action bar

## 12. Reviews and Trust
These endpoints cover the review form and trust metadata shown in profile/order flows.

| method | path | purpose |
| --- | --- | --- |
| GET | `/pages/reviews/{order_id}` | bootstrap review form |
| GET | `/reviews/tags` | available review tags |
| POST | `/reviews` | submit review |
| GET | `/orders/{order_id}/review-draft` | load draft review |
| PATCH | `/orders/{order_id}/review-draft` | update draft review |
| GET | `/listings/{listing_id}/reviews` | listing review list |

Review bootstrap should include:
- order snapshot
- star rating state
- selectable tags
- media upload slots
- review text box state
- privacy toggle

## 13. Profile, Wallet, and Membership
These endpoints cover the entire "My" tab, including stats, listings, services, balance, and VIP state.

| method | path | purpose |
| --- | --- | --- |
| GET | `/pages/me` | bootstrap profile screen |
| GET | `/users/me/stats` | aggregated counts and trust score |
| GET | `/users/me/listings` | current user listings |
| GET | `/users/me/favorites` | liked listings |
| GET | `/users/{user_id}` | public profile snapshot |
| GET | `/users/{user_id}/followers` | follower list |
| GET | `/users/{user_id}/following` | following list |
| GET | `/wallet/summary` | balance and holding summary |
| GET | `/wallet/transactions` | wallet ledger |
| GET | `/memberships/current` | VIP membership state |
| POST | `/memberships/upgrade` | upgrade membership |
| GET | `/service-catalog` | profile service tiles |

Profile bootstrap should include:
- avatar block
- follower and following counters
- posting/selling/buying metrics
- my listings carousel
- VIP card
- service grid
- shortcuts to orders, reviews, and success states

## 14. Notifications and Badges
| method | path | purpose |
| --- | --- | --- |
| GET | `/notifications` | notification list |
| POST | `/notifications/{notification_id}/read` | mark one notification as read |
| POST | `/notifications/read-all` | mark all as read |
| GET | `/badges/summary` | global badge counts |

## 15. Realtime and Sync
- Chat and notification updates may use WebSocket or SSE, but the REST API must remain the source of truth.
- Suggested channels:
  - `/ws/conversations/{conversation_id}`
  - `/ws/notifications`
- Realtime events should be modeled as append-only events with ids and server timestamps.

## 16. Compatibility Rules
- Additive fields are allowed.
- Removing or renaming fields requires a new API version.
- Page bootstrap endpoints should return reusable resources, not hardcoded UI coordinates.
- The client should tolerate extra fields and ignore unknown properties.
- The backend should never depend on Flutter widget names or layout hierarchy.

## 17. Coverage Checklist
- Auth pages: login, register, guest entry, and session restore are covered by `/pages/auth/login`, `/pages/auth/register`, `/auth/login`, `/auth/register`, and `/auth/session`.
- Home page: hero banner, categories, curated picks, and quick actions are covered by `/pages/home` plus shared resource endpoints.
- Search page: query summary, filter chips, and result grid are covered by `/pages/search`, `/search/facets`, and `/listings`.
- Product detail page: listing media, seller, specs, inquiries, actions, and related items are covered by `/pages/listings/{listing_id}`.
- Sell page: draft, uploads, title, description, pricing, logistics, and publish action are covered by the draft and upload endpoints.
- Chat page: thread list, detail header, messages, and composer are covered by `/conversations` and `/messages` endpoints.
- Order page: status, address, item snapshot, logistics, and confirmation are covered by `/pages/orders/{order_id}`.
- Payment success page: receipt summary, next steps, and recommendations are covered by `/pages/orders/{order_id}/success` and receipt data.
- Review page: rating, tags, photos, privacy, and submission are covered by `/pages/reviews/{order_id}` and `/reviews`.
- Profile page: summary, stats, listings, wallet, membership, and service tiles are covered by `/pages/me` and related profile endpoints.
- Profile settings page: avatar, nickname, birth date, age preview, bio, location, and visibility are covered by `/pages/me/settings` and `PATCH /users/me`.
- Profile settings page: avatar, nickname, age, bio, and location are covered by `/pages/me/settings` and `/users/me`.

## 18. Notes
- Keep DTO mapping in the Flutter app strict and centralized.
- Keep search, feed, and profile summary endpoints cache-friendly.
- Use server-side composition for page bootstrap endpoints, but keep domain resources separately accessible.
- `POST /auth/register` should create the user row, profile row, consent record, and session record in one logical workflow.
- `POST /auth/logout` should revoke the active session so the Flutter app can return to the auth gate cleanly.
- `PATCH /users/me` should update avatar, nickname, birth date, bio, and location atomically so the settings page stays consistent.
- TODO: JerryChen-USTB
