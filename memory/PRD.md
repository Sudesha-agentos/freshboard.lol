# FreshBoard.lol — PRD

## Original problem statement
Product Hunt–style leaderboard where **rank is bought, not voted**. Two sections:
- **Product Launches** (with category: SaaS, AI, Voice AI, CRM, DevTools, Fintech, Healthtech, E-commerce, Productivity, Social, Gaming, Other)
- **Social Promotions** (X / Instagram posts)

Anyone can submit a listing with a **$1 minimum bid**. Anyone can outbid an existing listing at any higher amount. When outbid, the previous holder drops one rank (no refund). Optional **$10 share-boost** add-on pushes the listing to 5 extra channels (simulated for MVP). Board resets every midnight **IST**. No user accounts — payment is the identity check.

## User personas
- **Startup founder** — pays to get their product in front of the daily audience.
- **Creator / marketer** — pays to promote an X post or Instagram reel.
- **Visitor** — browses today's leaderboard, clicks cards to visit the linked product/post.

## Architecture
- **Backend**: FastAPI (`/app/backend/server.py`), Motor + MongoDB. Stripe via `emergentintegrations` (Flow B, dynamic amounts, `STRIPE_API_KEY=sk_test_emergent`).
- **Frontend**: React (CRA + craco), react-router-dom, Tailwind + Shadcn UI, Sonner toasts. Dark neon brutalist theme (Unbounded / Outfit / JetBrains Mono).
- **Payment flow**: Frontend collects listing details → `/api/submit` or `/api/outbid` returns Stripe checkout URL → user pays → success page polls `/api/payments/status/{session_id}` → paid transaction triggers listing insert/bid update idempotently. Webhook `/api/webhook/stripe` mirrors the same.
- **Daily reset**: Purely a filter (`created_at_iso >= ist_day_start_utc`) — no destructive delete.

## Core requirements (static)
1. `$1` minimum bid; no maximum.
2. Outbid = new listing OR bid update at higher amount; ranks reflow automatically.
3. Card must show: rank, title, tagline, thumbnail, category (or platform), current bid (prominent), external link.
4. Countdown to next IST midnight visible on the board.
5. Two sections with independent ranking + optional category filter for products.
6. Optional +$10 share-boost checkbox at checkout.
7. No accounts, no login.

## Implemented (2026-02)
- Backend endpoints: `/api/config`, `/api/reset-info`, `/api/board`, `/api/listings/{id}`, `/api/listings/{id}/click`, `/api/submit`, `/api/outbid`, `/api/activity`, `/api/stats`, `/api/top-today`, `/api/payments/status/{session_id}`, `/api/webhook/stripe`.
- MongoDB collections: `listings` (now with `click_count`), `payment_transactions` with idempotent paid-transaction application.
- Frontend pages: `/` (Board with hero + countdown + marquee + "Claim #1 for $X+1" hero widget + tabs + category filter + ranked cards + latest-activity sidebar + stats bar + empty state), `/product/:id` (detail with sticky bid sidebar, click tracking, description, visit button), `/payment/success`, `/payment/cancel`.
- SubmissionModal doubles as outbid modal; category select (Shadcn), platform select, +$10 boost checkbox, total price display, redirect to Stripe hosted checkout.
- Design: dark neon brutalist, sharp 1px borders, no rounded corners, glow on #1 rank, marquee ticker, Unbounded display type. Fully responsive: mobile-first stacking, horizontal-scroll category chips, compact header + countdown row on mobile.
- Outbid.lol-style additions: activity feed (auto-refresh), stats/revenue counter, top-today hero widget, per-listing click tracking, time-ago timestamps, product detail pages with shareable URL.
- Backend testing: 18/18 checks passed (iteration_1.json). Manual smoke test on new endpoints: /activity, /stats, /top-today, /click tracking all working.

## Backlog (prioritized)
### P1
- **Auto-refresh live bids**: WebSocket / SSE push instead of 8s polling.
- **Real share-boost distribution**: connect email or social auto-post (currently simulated / stored only).
- **Yesterday's archive**: read-only "yesterday's #1" page for FOMO.
### P2
- Anti-abuse: URL blocklist / basic content moderation.
- Bid history per listing (mini-graph of climb).
- OpenGraph auto-fetch when a URL is pasted (auto title/tagline/image).
- Partial refund on outbid (policy toggle).
### P3
- Admin dashboard, analytics for submitters.
- Timezone selection.
- Native crypto payments option (Stripe crypto rail).
