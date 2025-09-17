# eBay AI Sales Agent (MVP)

## Purpose
Let users upload an item → AI generates optimized eBay listing (title, description, price) → user approves → system posts via eBay API → monitors sale + inbox → drafts responses.

## Core Features (MVP)

1. **Auth**
   - Email login + eBay OAuth.

2. **Item Intake**
   - Upload photos, enter condition + price range.
   - Store in DB.

3. **AI Listing Generation**
   - LLM generates title/description.
   - Fetch comps via eBay Browse API for price suggestion.
   - Show draft → user approves/edits.

4. **eBay Integration**
   - Post listing via Inventory/Trading API.
   - Sync sale status (sold/delist).
   - Fetch buyer messages.

5. **Inbox + Messaging**
   - Display buyer questions in dashboard.
   - AI drafts replies → user approves/send.

6. **Notifications**
   - Email/SMS alert for offers/sales.

7. **Audit Logs**
   - Save AI outputs + user approvals.

---

## Stack (suggested)
- **Frontend**: React/Next.js
- **Backend**: Node.js + Express (or FastAPI if Python)
- **DB**: Postgres
- **AI**: OpenAI/GPT API for text generation
- **APIs**: eBay OAuth + Inventory/Trading/Browse/Messaging
- **Notifications**: SendGrid (email), Twilio (SMS)

---

## Non-Goals (MVP)
- Multi-marketplace posting
- Autonomous negotiation
- Payments/shipping outside eBay

---

## Success Metric
- User can: upload item → approve AI draft → see it live on eBay in <5 min
