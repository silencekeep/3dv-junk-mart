# Database Prototype

This document defines the conceptual database prototype for the backend. It is intentionally decoupled from the Flutter screens, but it covers the full feature set shown in the current app.

## 1. Storage Architecture
- Primary transactional database: PostgreSQL
- Cache and transient state: Redis
- Binary assets: object storage or CDN-backed blob storage
- Search and discovery: materialized search documents or an external search engine
- Async side effects: outbox pattern for notifications, search sync, and analytics

## 2. Conventions
- Primary keys are opaque strings, preferably ULID or UUID.
- Core tables should include `created_at`, `updated_at`, and, when needed, `deleted_at`.
- Monetary values are stored as integer minor units with a currency code.
- Status fields are string enums instead of integers.
- Historical purchase data uses immutable snapshots so orders remain stable even if listing data changes later.
- Chat messages are append-only.
- Soft delete is preferred for user-generated content.

## 3. Domain Model Overview

### 3.1 Authentication and Sessions
| table | purpose | key fields |
| --- | --- | --- |
| `auth_sessions` | active sessions and refresh token state | `id`, `user_id`, `refresh_token_hash`, `device_name`, `device_platform`, `ip_address`, `user_agent`, `expires_at`, `revoked_at`, `created_at`, `last_seen_at` |
| `user_consents` | registration terms and privacy acceptance | `id`, `user_id`, `consent_type`, `consent_version`, `accepted_at`, `metadata_json` |
| `login_attempts` | sign-in audit and rate-limiting data | `id`, `login_identifier`, `user_id`, `success`, `failure_reason`, `ip_address`, `user_agent`, `occurred_at` |

### 3.2 Identity and Profile
| table | purpose | key fields |
| --- | --- | --- |
| `users` | account identity and auth anchor | `id`, `phone`, `email`, `password_hash`, `status`, `registered_at`, `last_login_at`, `password_updated_at`, `account_locked_until` |
| `user_profiles` | public profile data | `user_id`, `display_name`, `avatar_url`, `birth_date`, `bio`, `location_city`, `location_region`, `profile_visibility`, `sesame_credit_score`, `vip_level`, `updated_at` |
| `user_stats` | aggregated profile counts | `user_id`, `posts_count`, `sold_count`, `bought_count`, `liked_count`, `followers_count`, `following_count`, `positive_rate` |
| `user_follows` | follower graph | `follower_user_id`, `following_user_id`, `created_at` |
| `user_addresses` | shipping and pickup addresses | `id`, `user_id`, `recipient_name`, `phone`, `region_code`, `address_line1`, `address_line2`, `is_default` |

### 3.3 Wallet and Membership
| table | purpose | key fields |
| --- | --- | --- |
| `wallet_accounts` | user wallet balance and holds | `id`, `user_id`, `available_minor`, `held_minor`, `currency`, `status` |
| `wallet_transactions` | immutable financial ledger | `id`, `wallet_account_id`, `transaction_type`, `amount_minor`, `currency`, `reference_type`, `reference_id`, `status` |
| `membership_plans` | VIP tier catalog | `id`, `plan_key`, `title`, `price_minor`, `currency`, `benefits_json`, `active` |
| `membership_subscriptions` | current membership state | `id`, `user_id`, `plan_id`, `status`, `started_at`, `expires_at` |

### 3.4 Catalog and Listings
| table | purpose | key fields |
| --- | --- | --- |
| `categories` | searchable category tree | `id`, `parent_id`, `name`, `slug`, `icon_key`, `sort_order`, `active` |
| `listings` | current live inventory and sell drafts | `id`, `seller_id`, `category_id`, `title`, `subtitle`, `description`, `price_minor`, `original_price_minor`, `currency`, `status`, `condition_level`, `location_city` |
| `listing_drafts` | editable pre-publish content | `id`, `seller_id`, `category_id`, `title`, `description`, `price_minor`, `currency`, `status`, `draft_payload_json` |
| `listing_media` | listing photos and videos | `id`, `listing_id`, `asset_id`, `kind`, `sort_order`, `is_cover` |
| `listing_specs` | structured attributes shown on detail page | `id`, `listing_id`, `spec_key`, `spec_value`, `sort_order` |
| `listing_tags` | reusable listing tags | `id`, `tag_key`, `display_name`, `tag_type`, `active` |
| `listing_tag_links` | many-to-many listing tags | `listing_id`, `tag_id` |
| `listing_favorites` | user likes and saved items | `user_id`, `listing_id`, `created_at` |
| `listing_views` | optional analytics and ranking input | `id`, `user_id`, `listing_id`, `viewed_at`, `source` |
| `listing_search_documents` | denormalized search projection | `listing_id`, `title_tokens`, `category_path`, `price_minor`, `location_city`, `status`, `ranking_score`, `facet_json` |

### 3.5 Home and Navigation Content
| table | purpose | key fields |
| --- | --- | --- |
| `home_banners` | hero cards and promotions | `id`, `title`, `subtitle`, `media_asset_id`, `action_type`, `action_ref`, `sort_order`, `active` |
| `home_sections` | curated home page composition | `id`, `section_key`, `section_type`, `title`, `subtitle`, `priority`, `payload_json`, `active` |
| `service_catalog` | profile shortcuts and tools | `id`, `service_key`, `title`, `icon_key`, `description`, `destination_type`, `destination_ref`, `badge_text`, `active` |

### 3.6 Messaging
| table | purpose | key fields |
| --- | --- | --- |
| `conversations` | chat threads between buyer and seller | `id`, `listing_id`, `buyer_id`, `seller_id`, `status`, `last_message_at`, `last_message_preview` |
| `conversation_members` | thread membership and read state | `conversation_id`, `user_id`, `role`, `last_read_message_id`, `unread_count` |
| `messages` | append-only chat messages | `id`, `conversation_id`, `sender_id`, `message_type`, `content_text`, `asset_id`, `created_at`, `read_at` |
| `message_reactions` | optional message reactions | `id`, `message_id`, `user_id`, `reaction_key`, `created_at` |

### 3.7 Orders, Logistics, and Payments
| table | purpose | key fields |
| --- | --- | --- |
| `orders` | order header and lifecycle | `id`, `order_no`, `buyer_id`, `seller_id`, `listing_id`, `status`, `payment_status`, `shipping_status`, `currency`, `subtotal_minor`, `shipping_minor`, `discount_minor`, `total_minor` |
| `order_items` | immutable item snapshot | `id`, `order_id`, `listing_id`, `snapshot_title`, `snapshot_price_minor`, `snapshot_currency`, `snapshot_cover_asset_id`, `quantity` |
| `order_status_events` | order timeline events | `id`, `order_id`, `status`, `event_note`, `actor_user_id`, `occurred_at` |
| `shipments` | shipping header | `id`, `order_id`, `carrier_name`, `tracking_no`, `status`, `shipped_at`, `estimated_delivery_at` |
| `shipment_events` | logistics timeline entries | `id`, `shipment_id`, `event_code`, `event_text`, `event_city`, `occurred_at` |
| `payments` | payment header | `id`, `order_id`, `payment_method`, `status`, `amount_minor`, `currency`, `provider_ref` |
| `payment_transactions` | provider-side ledger | `id`, `payment_id`, `transaction_type`, `amount_minor`, `currency`, `provider_status`, `created_at` |

### 3.8 Reviews and Trust
| table | purpose | key fields |
| --- | --- | --- |
| `reviews` | submitted review data | `id`, `order_id`, `listing_id`, `reviewer_user_id`, `seller_user_id`, `rating`, `content`, `is_anonymous`, `status`, `created_at` |
| `review_media` | review photos or clips | `id`, `review_id`, `asset_id`, `sort_order` |
| `review_tags` | reusable review tag dictionary | `id`, `tag_key`, `display_name`, `tag_group`, `active` |
| `review_tag_links` | many-to-many review tags | `review_id`, `tag_id` |
| `trust_scores` | optional trust snapshots | `id`, `user_id`, `score_type`, `score_value`, `source`, `calculated_at` |

### 3.9 Notifications and Platform
| table | purpose | key fields |
| --- | --- | --- |
| `notifications` | in-app notifications | `id`, `user_id`, `notification_type`, `title`, `body`, `entity_type`, `entity_id`, `read_at`, `created_at` |
| `feature_flags` | server-controlled UI switches | `id`, `flag_key`, `enabled`, `target_scope`, `payload_json` |
| `app_config` | public bootstrap configuration | `id`, `config_key`, `config_value_json`, `active` |
| `outbox_events` | async integration events | `id`, `event_type`, `aggregate_type`, `aggregate_id`, `payload_json`, `status`, `created_at`, `published_at` |
| `audit_logs` | admin and sensitive action log | `id`, `actor_user_id`, `action_type`, `entity_type`, `entity_id`, `payload_json`, `created_at` |

## 4. Page Coverage Matrix
This matrix maps the current Flutter screens to the tables they should read or write.

| screen | primary tables | supporting tables |
| --- | --- | --- |
| Auth login/register | `users`, `user_profiles`, `auth_sessions`, `user_consents` | `login_attempts`, `app_config` |
| Home | `home_banners`, `home_sections`, `categories`, `listings`, `service_catalog` | `listing_search_documents`, `user_profiles` |
| Search | `listing_search_documents`, `categories`, `listings` | `listing_tags`, `user_profiles` |
| Sell | `listing_drafts`, `listing_media`, `listing_specs`, `categories` | `service_catalog`, `feature_flags` |
| Chat list and chat detail | `conversations`, `conversation_members`, `messages` | `listings`, `user_profiles`, `notifications` |
| Product detail | `listings`, `listing_media`, `listing_specs`, `user_profiles` | `listing_favorites`, `conversations`, `reviews` |
| Order detail | `orders`, `order_items`, `order_status_events`, `shipments`, `shipment_events`, `payments` | `user_addresses`, `wallet_transactions` |
| Payment success | `orders`, `order_items`, `payments` | `home_sections`, `listing_search_documents`, `wallet_transactions` |
| Review form | `reviews`, `review_tags`, `review_media`, `orders` | `order_items`, `listing_media` |
| Profile | `user_profiles`, `user_stats`, `listings`, `wallet_accounts`, `membership_subscriptions`, `service_catalog` | `user_follows`, `notifications`, `reviews`, `auth_sessions` |
| Profile settings | `user_profiles`, `users`, `auth_sessions` | `app_config`, `feature_flags` |

## 5. Recommended Constraints and Indexes
- `users.phone` and `users.email` should be unique when present.
- `auth_sessions.user_id`, `auth_sessions.revoked_at`, and `auth_sessions.expires_at` should be indexed.
- `login_attempts.login_identifier` and `login_attempts.occurred_at` should be indexed for rate limiting.
- `user_consents.user_id` and `user_consents.consent_type` should be indexed for compliance lookups.
- `user_profiles.display_name` should be indexed if profile search or mentions are required.
- `listings.status`, `orders.status`, and `messages.created_at` should be indexed.
- `listing_search_documents` should have search-oriented indexes on title, category, location, and status.
- `conversations` should have a composite index on `(buyer_id, seller_id, listing_id)`.
- `messages` should have `(conversation_id, created_at)` indexed for chronological loads.
- `orders` should have `(buyer_id, seller_id, status, created_at)` indexed.
- `notifications` should have `(user_id, read_at, created_at)` indexed.

## 6. Data Integrity Rules
- Registration should create the `users`, `user_profiles`, `user_consents`, and `auth_sessions` rows in one logical transaction or an outbox-coordinated workflow.
- Login should update `last_login_at`, create a new `auth_sessions` row, and keep prior revoked sessions immutable.
- Logout should set `auth_sessions.revoked_at` instead of deleting the row so audit trails remain intact.
- Profile edits should update avatar, nickname, birth date, bio, and location in the same `user_profiles` row; age should be derived from `birth_date`, not stored separately.
- A `user_profiles` row must not outlive its owning `users` row.
- Order records must snapshot item title, price, media, and seller identity at purchase time.
- Messages must never be edited in place after delivery; use append-only corrections if needed.
- Reviews should only be inserted for completed orders unless an admin overrides the rule.
- Published listings should not depend on the mutable draft row after publish.
- Wallet and payment balances should be updated through ledger entries, not direct overwrites.
- Search projections should be rebuilt from canonical listing rows and events.

## 7. Seed Data Prototype
The initial demo dataset should include:
- 1 to 3 demo auth users with active session and consent rows
- avatar, nickname, and birth_date values for each demo auth user
- 5 to 10 categories for the home grid and search filters
- 20 to 30 sample listings with media and seller snapshots
- 3 to 5 conversations with message history
- 3 to 5 orders with shipping timelines and payment records
- 5 to 10 reusable review tags
- 8 service catalog entries for the profile page shortcuts
- 1 membership plan and 1 wallet account per test user

## 8. Notes
- Keep API payloads aligned with these tables, but never expose the table names directly to the Flutter app.
- Keep the schema evolvable with additive fields and migration scripts.
- The auth login/register UI should map directly to `users`, `user_profiles`, `user_consents`, and `auth_sessions` without introducing a second source of truth.
- TODO: JerryChen-USTB