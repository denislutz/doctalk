# DocTalk React Frontend — Plan

## Stack

- Vite + React 18 + TypeScript strict
- Tailwind CSS v4
- shadcn/ui (Radix UI, owned source — not a runtime dep)
- React Router v6
- useState / useReducer only — no state library

## Structure

```text
frontend-react/src/
├── main.tsx
├── App.tsx                  # router + layout shell, useCollections at root
├── types/api.ts             # TS interfaces 1:1 with Pydantic models (+ UI-only types)
├── services/
│   ├── EnvS.ts              # apiUrl(), apiKey()
│   ├── QueryS.ts            # query(), stream(), useChat()
│   ├── CollectionS.ts       # list(), get(), create(), remove(), upload(), useCollections()
│   └── HealthS.ts           # check(), useHealth()
├── components/
│   ├── ui/                  # shadcn/ui owned components
│   ├── Sidebar.tsx          # nav + collection Select + HealthBadge
│   ├── HealthBadge.tsx
│   ├── ChatWindow.tsx
│   ├── MessageBubble.tsx
│   ├── SourceCard.tsx
│   ├── CollectionList.tsx
│   └── UploadDropzone.tsx
└── pages/
    ├── ChatPage.tsx
    ├── CollectionsPage.tsx
    └── UploadPage.tsx
```

## Service Pattern (strict)

All functions defined standalone first. Service object at the bottom references only the public ones — no logic inside the object literal. Private helpers never in the object.

```typescript
const privateHelper = (...) => { ... };   // not in object
const publicMethod  = (...) => { ... };   // in object
const useHook       = ()     => { ... };  // in object

const FooS = { publicMethod, useHook };
export default FooS;
```

Hooks live inside the service file as standalone functions, exposed through the service object. No separate hooks/ directory.

## Key Design Decisions

- **EnvS**: single source for all env reads (`import.meta.env`). All other services call `EnvS.apiUrl()` and `EnvS.apiKey()` — never read env directly.
- **Collection state**: `CollectionS.useCollections()` called once in `App.tsx`. `selected` + `setSelected` passed as props to Sidebar and pages.
- **Collection selector**: lives in the Sidebar (always visible, global context).
- **Streaming**: `POST /query/stream` via `fetch` + `ReadableStream` (not EventSource). `QueryS.stream()` returns an `AbortController` for cleanup on unmount.
- **No Docker** for React service yet — added in Phase 7 hardening.

## SSE Protocol (`POST /query/stream`)

```text
data: <token>\n\n            — one per LLM token
data: {"sources":[...]}\n\n  — after generation, before DONE
data: [DONE]\n\n             — stream end signal
```

## shadcn/ui Components

Button · Badge · Card · Select · Input · ScrollArea · Dialog · Tooltip · Separator · Progress · Sonner

## Types (api.ts)

Mirror Pydantic models exactly. UI-only additions:

- `Message` — `{ id, role, content, sources, streaming }` (local chat state)
- `HealthStatus` — `{ status: 'ok' | 'degraded' | 'error' }`

## Backend Changes Required

1. `app/retrieval/chain.py` — add `stream_answer()` using LangChain `.astream()`
2. `app/api/query.py` — add `POST /query/stream` using `StreamingResponse`

## Routes

```text
/              → ChatPage
/collections   → CollectionsPage
/upload        → UploadPage
```

## Build Order

1. Backend: `stream_answer()` + `POST /query/stream`
2. Vite scaffold + Tailwind + shadcn/ui init
3. `types/api.ts`
4. `EnvS` → `HealthS` → `CollectionS` → `QueryS`
5. `App.tsx` shell + `Sidebar`
6. `ChatPage` → `ChatWindow` → `MessageBubble` → `SourceCard`
7. `CollectionsPage` → `CollectionList`
8. `UploadPage` → `UploadDropzone`
9. `HealthBadge`

## Lint Setup

Install with the scaffold:

```bash
npm install -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks
```

`eslint.config.ts` — flat config, strict TS rules + react-hooks exhaustive-deps.

## Post-Implementation Verification

Run in order after all code is written (backends assumed running on :8000 and :8501):

```bash
# 1. Type check — no emit, just errors
npx tsc --noEmit

# 2. Lint
npx eslint src/

# 3. Build — catches any remaining compile/bundle errors
npm run build

# 4. Start dev server (port 3000)
npm run dev
```

## cmux Browser Verification

After dev server is up, run these in cmux to verify the frontend:

```bash
# Open the app
cmux browser open http://localhost:3000

# Wait for full load
cmux browser surface:2 wait --load-state complete --timeout-ms 15000

# Snapshot the chat page
cmux browser surface:2 snapshot --interactive --compact

# Check for JS errors
cmux browser surface:2 errors list

# Navigate to collections page
cmux browser surface:2 navigate http://localhost:3000/collections --snapshot-after

# Navigate to upload page
cmux browser surface:2 navigate http://localhost:3000/upload --snapshot-after

# Return to chat and take screenshot for review
cmux browser surface:2 navigate http://localhost:3000
cmux browser surface:2 screenshot --out /tmp/doctalk-react.png
```
