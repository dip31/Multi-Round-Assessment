# EDI5 Retell Transcript Pipeline — Diagnostic Report

**Date:** 2026-10-09
**Subject:** `Transcript WebSocket error: Event` / `Transcript WebSocket closed: 1006` on `/api/v1/interview/session/46/transcript`
**Method:** static trace of the full chain (frontend → Vite proxy → ASGI middleware → router → auth → authz → connection manager → producers), followed by elimination of eleven candidate causes.

> **Runtime-verification caveat, stated up front.** The brief asks that an obvious code defect still be confirmed at runtime before being declared root cause. I could not do that from this environment: the Linux sandbox available to me has no backend dependencies installed (`ModuleNotFoundError: No module named 'fastapi'`, likewise `websockets`) and no Postgres, Redis, or Retell credentials. Section 7 therefore specifies the exact commands and the exact log lines that confirm or refute this diagnosis, and the fix in section 6 deliberately includes the instrumentation needed to make that confirmation possible. The primary cause below is a deterministic consequence of two pieces of code that are both present and both read directly, so the confidence is high — but it is code-level confidence, not observed-runtime confidence, and it is labelled as such.

---

## 1. Root Cause

**The reported `error` + `1006` pair is produced by the frontend, not by the backend, and not by Retell.**

Two independent defects are involved. They must both be fixed: the first causes the symptom, the second is why the symptom carries no diagnostic information.

**PRIMARY BLOCKER — unguarded `close()` on a still-connecting socket, triggered by React StrictMode's double mount.**

`frontend/src/main.jsx:7` wraps the app in `<StrictMode>`. In React 19 development, StrictMode deliberately runs every effect twice: mount → cleanup → mount. `RetellInterviewRoom.jsx:461-478` is a mount-only effect (`[]` deps) that calls `initializeRetell()`, which at line 158 calls `connectTranscriptWebSocket()` **synchronously**, creating the socket at line 250. The socket is therefore in `readyState === CONNECTING` when React immediately runs the effect's cleanup, and that cleanup calls `transcriptWsRef.current.close()` at line 472 **with no `readyState` check**.

Per the WHATWG WebSocket specification, calling `close()` while the connection is still `CONNECTING` aborts the handshake, fails the connection, and fires `error` followed by `close` with code **1006** and an **empty reason**. That is precisely the observed output, including the empty reason string and the fact that it appears before `[Retell] call_started`.

**SECONDARY BLOCKER — the backend closes before it accepts, so every genuine rejection is also reported as 1006.**

`app/modules/interview/routers/transcript_websocket.py` calls `await websocket.close(...)` at line 134 (auth failure, code 4001) and line 155 (interview not found, code 4004) **before** `websocket.accept()` is ever reached — `accept()` only happens later, inside `transcript_manager.connect()` at line 49. Under the ASGI contract, sending `websocket.close` before `websocket.accept` makes uvicorn reject the HTTP upgrade with a **403** response. The browser never completes a handshake, so it discards the application's close code entirely and surfaces a bare **1006**.

The consequence is important for this investigation: **a 1006 in this codebase is indistinguishable between a frontend handshake abort, an auth failure, and an authz failure.** This is exactly why the brief's constraint "do not assume close code 1006 identifies the root cause by itself" is correct, and it is why the fix must make the two cases distinguishable rather than guessing between them.

---

## 2. Evidence

Every candidate cause was checked against source. Note that the brief's own stated primary suspicion is **disproven**.

| # | Candidate cause | Verdict | Evidence |
|---|---|---|---|
| A | Frontend builds WS URL from `window.location.host`, hitting Vite (5173) instead of FastAPI (8000) | **DISPROVEN** | `RetellInterviewRoom.jsx:244-246` does use `window.location.host`, but that is the *intended* design: the Vite proxy forwards it. See B. |
| B | Vite proxy does not forward WebSocket upgrades | **DISPROVEN** | `frontend/vite.config.js:10-14` — the `/api` proxy targets `http://localhost:8000` and sets **`ws: true`**, which is exactly what enables upgrade proxying. Vite 7.3.1 installed. |
| C | Route not registered / path mismatch | **DISPROVEN** | `app/api/v1/router.py` uses `APIRouter(prefix="/api/v1")` and includes `transcript_websocket_router` at line 31; that router declares `prefix="/interview"` (line 22) and `@router.websocket("/session/{interview_id}/transcript")` (line 102). Composed path `/api/v1/interview/session/{id}/transcript` is a character-for-character match for the URL in the console log. |
| D | JWT rejected — wrong secret, wrong algorithm, or `sub` claim mismatch | **UNLIKELY (not fully excluded)** | `auth_router.py:68` mints `data={"sub": str(user.id), ...}`; the WS decodes with the same `settings.SECRET_KEY` / `settings.ALGORITHM` and parses `int(payload.get("sub", 0))` at line 130. Contract matches. Cannot be fully excluded without runtime logs — **because of the secondary blocker, a failure here would look identical to the primary.** |
| E | Authz join raises `AttributeError` (no `user_id` on `AssessmentSession`) | **DISPROVEN** | `app/models/assessment.py:34` — `user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)`. The join at `transcript_websocket.py:144-149` is valid. |
| F | Frontend aborts its own handshake | **CONFIRMED — PRIMARY** | `main.jsx:7` (`<StrictMode>`, React 19.2.0) + `RetellInterviewRoom.jsx:158` (synchronous open) + `:471-474` (cleanup closes with no `readyState` guard). Deterministic in dev. |
| G | `BaseHTTPMiddleware` breaking the websocket scope | **DISPROVEN** | All three middlewares (`rate_limit.py`, `request_logging.py`, CORS) subclass `BaseHTTPMiddleware`, which passes non-`http` scopes straight through to the inner app without ever calling `dispatch()`. The `scope == "websocket"` guards at `rate_limit.py:43` and `request_logging.py:25` are unreachable dead code. Harmless, but misleading to a reader. |
| H | `websockets` library missing from the uvicorn install | **WEAKENED** | `requirements.txt` declares `uvicorn[standard]`, which pulls it in. Installed state unverified from here. If it were missing, uvicorn would log a handshake-unsupported warning — section 7 checks for it. |
| I | Backend down, or proxy not working at all | **DISPROVEN** | The same console log shows `Interview ID found: 46` and a real `Retell Call ID`, both of which are fetched over HTTP through the same `/api` proxy. Backend is up and the proxy works. |
| J | Retell is broken | **DISPROVEN** | `[Retell] call_started`, `call_ready`, and `call started` all fire *after* the WS failure. Retell's media path is healthy and is independent of the transcript socket. |
| K | Backend masks its real close code | **CONFIRMED — SECONDARY** | `transcript_websocket.py:134` and `:155` close before `accept()` (which lives at line 49, reached only later via line 161). ASGI turns this into HTTP 403; browser reports 1006 with no reason. |

**Open item that only runtime can settle.** The reported log contains no `Transcript WebSocket connected` line, which the second StrictMode pass should produce. Either the pasted log is abridged, or the second socket also fails — and if it fails, cause D is live underneath the primary. I am not going to guess which; the instrumentation in section 6 makes the answer unambiguous on the next run, and the fix addresses both possibilities.

---

## 3. Failure Path

```
1.  Route /interview/room/retell mounts RetellInterviewRoom.
2.  StrictMode mount pass #1 — effect at :461 runs.
3.      initializeRetell()                                    (:145)
4.          isInitializedRef.current = true                   (:147)
5.          connectTranscriptWebSocket()                      (:158, SYNCHRONOUS)
6.              new WebSocket(ws://localhost:5173/api/v1/...)  (:250)
                → readyState = CONNECTING
                → console: "Connecting to transcript WebSocket: <URL WITH FULL JWT>"
7.          await retellClient.initialize(...)                (:161) — yields to event loop
8.  StrictMode runs the cleanup for pass #1.
9.      retellClient.endCall()                                (:469)
10.     transcriptWsRef.current.close()                       (:472) ← NO readyState GUARD
            socket is still CONNECTING
            → handshake ABORTED by the client
            → "The WebSocket connection was closed before it was established"
            → fires onerror  → console: "Transcript WebSocket error: Event"
            → fires onclose  → console: "Transcript WebSocket closed: 1006 ''"
11.     isInitializedRef.current = false                      (:475)
12. onclose handler schedules a 3s reconnect, but guards on
    transcriptWsRef.current?.readyState — and step 10 just set that ref to
    null, so the optional chain yields undefined and the reconnect never
    fires.                                                    (:277)
13. Pass #1's awaited continuation resumes, sees isInitializedRef === false,
    and returns early.                                        (:164)
14. StrictMode mount pass #2 — effect runs again, opens a second socket.
    Whether that one survives is exactly what the current logging cannot tell
    us, because if it is rejected for auth/authz the backend closes before
    accept and the browser reports another indistinguishable 1006.
15. Retell's own media path, which never depended on this socket, proceeds:
    call_started → call_ready → call started.
16. Transcript events are produced server-side and broadcast to a connection
    set that may be empty, or whose registration was evicted by the
    connection-id collision in section 5. Nothing reaches the UI.
```

---

## 4. Correct Path

```
Frontend
  mount → initializeRetell → connectTranscriptWebSocket
  new WebSocket(ws://localhost:5173/api/v1/interview/session/46/transcript?token=…)

Vite dev server (5173)
  '/api' proxy, ws: true → forwards the Upgrade to http://localhost:8000

Uvicorn / Starlette
  scope type "websocket" → BaseHTTPMiddleware chain passes straight through
  → api_router (/api/v1) → transcript router (/interview)
  → transcript_websocket_endpoint(interview_id=46, token=…)

Backend endpoint
  accept()                                  ← must come FIRST
  decode JWT → user_id
  authz: InterviewSession JOIN AssessmentSession ON user_id
  on failure: send {"type":"error", …} then close(4001 | 4004)  ← now visible
  on success: register in TranscriptConnectionManager under a UNIQUE conn_id
  send {"type":"connected","data":{"interview_id":46}}
  block on receive_text() until disconnect

Producers (both modes converge on one canonical format)
  edi5_core      retell_llm_websocket.py:265-271
                   normalize_retell_transcript(...) → broadcast_transcript_update(...)
  retell_hosted  retell_webhook.py:222-228
                   normalize_retell_transcript(...) → broadcast_transcript_update(...)

  → transcript_manager.broadcast_to_interview(46, {"type":"transcript","data":…})
  → ws.send_text(json)

Frontend
  onmessage → handleTranscriptMessage → handleTranscriptUpdate
  dedupe/merge on turn_id, order by sequence, finality from data.is_final
  → setLiveTranscript → rendered
```

The transport design is sound. Nothing in the architecture needs to change — which is consistent with the brief's prohibition on replacing Retell, redesigning the transport, or falling back to polling.

---

## 5. Secondary Issues

**Primary blocker** — frontend closes a `CONNECTING` socket (`RetellInterviewRoom.jsx:471-474`). Section 1.

**Secondary blocker** — backend closes before accepting (`transcript_websocket.py:134, 155`). Section 1. Must be fixed for the pipeline to be diagnosable at all.

**Latent 1 — colliding connection ids silently evict live connections.**
`_generate_connection_id` (`transcript_websocket.py:44-45`) returns `f"{interview_id}:{user_id}:{id(self)}"`. `self` is the module-level `transcript_manager` singleton, so `id(self)` is a **constant**. Two connections for the same interview and user therefore produce the *same* conn_id, and the second registration overwrites the first in `_all_connections`. When the first socket's `finally` block runs `disconnect(conn_id)` (line 186), it pops that shared id and discards the **second, still-live** connection from `_connections[interview_id]` — so a connected client stops receiving broadcasts. StrictMode's double-connect triggers this on every dev page load; two browser tabs or a reconnect would trigger it in production. The cleanup path inside `broadcast_to_interview` (lines 90-92) recomputes the same colliding id and has the same flaw.

**Latent 2 — `broadcast_transcript_final` is dead code.**
No caller anywhere in the repo. Only `broadcast_transcript_update` is ever invoked (both producers), so the frontend's `case 'transcript_final'` (line 293) never executes. Finality is in fact carried by `data.is_final`, which `handleTranscriptUpdate` does read (line 326). Not a bug today, but a trap: anyone reading the frontend would reasonably conclude finality arrives as its own message type.

**Latent 3 — the reconnect logic cannot work as written.** Three compounding problems at `RetellInterviewRoom.jsx:271-282`: it closes over a stale `roomState` (the callback is recreated on `roomState` change, but the socket keeps whichever closure it was created with); it guards on `transcriptWsRef.current?.readyState`, which the cleanup may already have nulled (step 12 above); and it has a fixed 3s delay with no attempt cap or backoff, so a persistently rejecting backend produces an unbounded reconnect loop.

**Latent 4 — the JWT is logged in full, and travels in the query string.**
`RetellInterviewRoom.jsx:248` logs the complete URL including `?token=<full JWT>` to the browser console — visible in the user's own pasted log. The token also necessarily appears in Vite and any upstream proxy access logs. The query-string placement is hard to avoid for browser WebSockets (the WS API allows no custom headers), so that part is an accepted constraint, but **logging the full token is not**, and the brief explicitly forbids it.

**Latent 5 — unreachable middleware guards.** `rate_limit.py:43` and `request_logging.py:25`. Dead code; documentation-only concern.

**Latent 6 — every broadcast resends the entire transcript.**
`retell_llm_websocket.py:265-271` calls `normalize_retell_transcript(transcript, base_sequence=0)` on each update, where `transcript` is the full array to date. So on utterance *N* the frontend receives *N* events, re-numbered from 1 each time. The frontend absorbs this correctly because `handleTranscriptUpdate` upserts on `turn_id` (line 319) and Retell supplies a stable `utterance_id` that `normalize_retell_utterance` uses as `turn_id` (line 128). It is O(N²) chatter rather than a correctness bug — **but** it becomes a correctness bug for any utterance where Retell omits `utterance_id`, because the fallback `turn-{sequence}-{uuid4}` (line 128) generates a *fresh random* turn_id on every rebroadcast, so such utterances would accumulate as duplicate rows. Out of scope for this fix; flagged.

---

## 6. Minimal Fix

Four changes. No architecture change, no new transport, no polling, no schema change, no auth removal, no `/v2` endpoint, no unrelated refactor. Phase 1/2/3 architecture is untouched.

**Fix 1 (frontend, primary) — never abort a connecting socket, and make teardown explicit.**
In `RetellInterviewRoom.jsx`, add a `closeTranscriptWebSocket(intentional)` helper that detaches `onopen`/`onmessage`/`onerror`/`onclose` *before* closing, closes only when `OPEN`, and when the socket is still `CONNECTING` attaches a one-shot `onopen` that immediately closes it. Detaching the handlers first is what removes the spurious `error`/`1006` console pair on the StrictMode pass. Guard `connectTranscriptWebSocket` against opening a duplicate when one is already `CONNECTING` or `OPEN`, clear any pending reconnect timer on teardown, and have the mount cleanup call the helper with `intentional = true` so the reconnect path stays dormant during unmount.

**Fix 2 (frontend) — make the reconnect correct.** Track `roomState` in a ref so the handler reads the current value rather than a stale closure; key the reconnect decision off the intentional-close flag rather than a possibly-nulled ref; cap attempts and apply exponential backoff.

**Fix 3 (backend, secondary) — accept before rejecting.**
In `transcript_websocket.py`, call `await websocket.accept()` at the top of the endpoint, before JWT decoding. On auth or authz failure, send `{"type": "error", …}` and then `close(4001)` / `close(4004)`, so the browser receives the real code and reason instead of an opaque 1006. `TranscriptConnectionManager.connect()` drops its own `accept()` call and becomes registration-only, with its docstring updated to say so. The tradeoff is deliberate and worth stating: the socket is briefly accepted before the caller is authenticated. No data is sent before authentication succeeds, the socket is closed immediately on failure, and this is the documented FastAPI pattern for WebSocket auth — there is no way to return a meaningful close code without it.

**Fix 4 (backend, latent 1) — unique connection ids.** Give `TranscriptConnection` a monotonic id from an `itertools.count()` and derive `conn_id` from the connection object rather than from the manager, so concurrent connections for the same interview and user can no longer evict one another.

**Also, per the brief's logging requirement:** add `[TranscriptWS]` prefixed diagnostics on both ends — frontend logs URL (**token stripped**), `interviewId`, connection state, `onopen`, `onerror`, `onclose code`, `onclose reason`; backend logs connection requested, `interview_id`, `token received: yes/no` (**never the token**), authentication successful, websocket accepted, websocket disconnected, broadcast event, and broadcast recipient count. Latent 4 is fixed as part of this: the URL is logged with `token=<redacted>`.

Latents 2, 5, and 6 are **documented, not changed** — fixing them is not required to restore the transcript and would violate "do not make unrelated refactors."

---

## 7. Validation Plan

**Prerequisite:** run the pending migration explicitly, not with a bare `upgrade head` — the repo has two Alembic heads.

```bash
alembic upgrade add_interviewer_id_001
```

**Step 1 — confirm uvicorn can serve WebSockets at all** (settles cause H):

```bash
python -c "import websockets, uvicorn; print('ws ok', websockets.__version__)"
uvicorn app.main:app --reload --port 8000 --log-level info
```

A missing `websockets` would surface as a handshake-unsupported warning on the first upgrade attempt.

**Step 2 — isolate the backend from the frontend lifecycle entirely.** This is the decisive test, because it removes StrictMode from the equation. Connect directly to port 8000, bypassing both Vite and React:

```bash
# Get a token (do not paste it into logs or tickets)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<user>","password":"<pass>"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

python - <<'PY'
import asyncio, os, websockets
async def main():
    url = f"ws://localhost:8000/api/v1/interview/session/46/transcript?token={os.environ['TOKEN']}"
    async with websockets.connect(url) as ws:
        print("OPEN"); print(await ws.recv())
        while True: print(await ws.recv())
asyncio.run(main())
PY
```

- `OPEN` followed by `{"type":"connected","data":{"interview_id":46}}` → the backend is healthy, and the primary blocker was indeed the frontend.
- Close **4001** → auth is the real problem (cause D), now visible only because of Fix 3.
- Close **4004** → interview 46 is not owned by this user (cause D/E variant), likewise now visible.

Repeat against `ws://localhost:5173/...` to confirm the Vite proxy leg independently.

**Step 3 — browser, post-fix.** Load the interview room in dev with StrictMode still enabled. Expected console sequence, with **no** `error` and **no** `1006`:

```
[TranscriptWS] URL: ws://localhost:5173/api/v1/interview/session/46/transcript?token=<redacted>
[TranscriptWS] interviewId: 46
[TranscriptWS] connection state: CONNECTING
[TranscriptWS] onopen
[TranscriptWS] message: connected
```

On the StrictMode teardown, expect `[TranscriptWS] intentional close (state=CONNECTING)` and no error pair.

**Step 4 — backend log for the same load:**

```
[TranscriptWS] connection requested
[TranscriptWS] interview_id: 46
[TranscriptWS] token received: yes
[TranscriptWS] websocket accepted
[TranscriptWS] authentication successful user_id=<id>
[TranscriptWS] registered conn_id=46:<id>:<counter> active=1
```

**Step 5 — end-to-end transcript.** Speak one answer. Expect `[TranscriptWS] broadcast event: transcript` with `broadcast recipient count: 1` (**not 0** — a 0 here with a connected client would indicate latent 1 is still biting), and the text appearing in the live transcript panel.

**Step 6 — regression check on the production build**, where StrictMode double-invocation does not occur:

```bash
cd frontend && npm run lint && npm run build
```

**Step 7 — latent 1 directly.** Open the interview room in two tabs. Both must keep receiving transcript events; `broadcast recipient count` must read 2. Before Fix 4, closing either tab would silently starve the other.

---

## 8. Regression Risks

**Fix 3 carries the only material risk.** Accepting before authenticating changes the handshake result for an unauthorised caller from HTTP 403 to a completed handshake followed by an immediate 4001 close. Anything that treats a 403 as the auth signal would need updating — I found no such consumer in the repo, and the frontend only inspects close codes, but it is the change to watch. It also means an unauthenticated client can briefly hold an accepted socket; no data is sent before auth succeeds, and the existing per-IP rate limiter does not cover WebSocket upgrades (latent 5), so a determined caller could open and be dropped repeatedly. That exposure already exists for every WS endpoint in the app and is not made meaningfully worse here, but it is worth a follow-up ticket rather than silence.

**Fix 1 risk: a genuinely slow handshake now closes later rather than never.** The one-shot `onopen`-then-close path means that if a real unmount happens while connecting, the socket opens momentarily before closing. The backend handles this as a normal disconnect through the existing `finally` block.

**Fix 2 risk: capped reconnect attempts mean a long backend outage now stops retrying** instead of looping forever. That is the intended behaviour — the loop was pathological — but it does change failure-mode semantics: after the cap, the user must reload. The transcript panel is non-blocking, and Retell's media path is unaffected, so the interview itself still completes.

**Fix 4 risk: minimal.** `conn_id` is an opaque internal token, not persisted and not exposed over any API, so changing its shape has no external contract.

**Not at risk:** database schema (unchanged), auth (unchanged — Fix 3 reorders when the same check runs, it does not weaken it), Retell integration for either mode (untouched), the canonical transcript format (untouched), Phase 3 analysis (untouched), and the interviewer-selection work in Phases 1–8 (untouched).

---

## Answers to the four closing questions

**Why did the transcript fail?** Because the frontend aborted its own WebSocket handshake. React StrictMode synthetically unmounts the component on first mount, and the mount effect's cleanup calls `close()` on a socket that is still `CONNECTING` — which the WebSocket spec defines as failing the connection with code 1006 and an empty reason. The backend never got the chance to reject or accept anything on that attempt; Retell was never involved.

**Where exactly did it fail?** `frontend/src/pages/RetellInterviewRoom.jsx`, line 472 — `transcriptWsRef.current.close()` — against a socket created synchronously at line 250 via the call chain at line 158, under `<StrictMode>` declared at `frontend/src/main.jsx:7`. The reason the failure looked like a backend problem is a second, independent defect at `app/modules/interview/routers/transcript_websocket.py` lines 134 and 155, where `close()` precedes `accept()` and so collapses the real 4001/4004 codes into the same opaque 1006.

**Why did it fail?** Two reasons, and they need separating. Mechanically: no `readyState` guard before `close()`, so a dev-mode lifecycle quirk became a hard connection failure. Diagnostically: the ASGI accept-then-close ordering means this codebase cannot currently distinguish a client-side handshake abort from an authentication failure from an authorisation failure — they all print `1006` with no reason. The brief's instruction not to treat 1006 as identifying the root cause was well founded; the code guarantees that it cannot.

**What is the minimal fix?** Guard and sequence the frontend teardown (detach handlers, close only when `OPEN`, defer when `CONNECTING`, suppress the reconnect on intentional close); accept before rejecting on the backend so real close codes survive; and make connection ids unique so concurrent clients stop evicting each other. Plus redacted `[TranscriptWS]` instrumentation on both ends.

**How do we prove the fix works?** Section 7, and specifically step 2: connect to port 8000 directly with a standalone Python client, which removes React, StrictMode, and Vite from the picture. If that yields `{"type":"connected"}`, the backend was never the blocker and the frontend fix is sufficient. If it yields 4001 or 4004, the real rejection reason is now legible for the first time — which is itself the point of Fix 3. Step 5 then proves the full path with `broadcast recipient count: 1`, and step 7 proves the connection-id fix with two tabs and a count of 2.

---

## Appendix — what was actually changed

Applied after the above was written, in the order the ranking implies.

`frontend/src/pages/RetellInterviewRoom.jsx`
- Added `TRANSCRIPT_MAX_RECONNECTS` (module scope) and four refs: `transcriptWsIntentionalRef`, `transcriptReconnectTimerRef`, `transcriptReconnectAttemptsRef`, `roomStateRef`.
- Added `closeTranscriptWebSocket()` — detaches `onmessage`/`onerror`/`onclose`, closes with 1000 when `OPEN`, and when still `CONNECTING` defers the close to a one-shot `onopen` instead of aborting the handshake. Clears any pending reconnect timer. **This is the primary fix.**
- `connectTranscriptWebSocket()` now refuses to open a duplicate when one is `CONNECTING` or `OPEN`, logs the URL with `token=<redacted>`, and emits the requested `[TranscriptWS]` lines.
- `onclose` no longer reconnects after an intentional close, after a superseding socket has replaced it, or on 4001/4004; it reads `roomStateRef` rather than a stale `roomState`, and backs off 1s→2s→4s→8s→15s with a cap of five attempts.
- The mount effect's cleanup calls `closeTranscriptWebSocket()` instead of a bare `.close()`.

`app/modules/interview/routers/transcript_websocket.py`
- `accept()` now runs at the top of the endpoint, before JWT decoding, with the reasoning recorded in the docstring.
- New `_reject()` helper sends `{"type":"error", …}` and then closes with the real 4001/4004 code and reason.
- A missing or empty `sub` claim is now an explicit rejection rather than `user_id = 0` falling through to an authz query that could never match.
- `_generate_connection_id` uses an `itertools.count()` instead of `id(self)`; `TranscriptConnection` carries its own `conn_id`, and `broadcast_to_interview` disconnects by that id rather than recomputing a colliding one. It also iterates a snapshot of the connection set, since a send failure mutates it.
- `TranscriptConnectionManager.connect()` no longer calls `accept()` — the endpoint owns the handshake — and the docstring says so.
- Logging switched to the `[TranscriptWS]` prefixes, including `broadcast event:` and `broadcast recipient count:`. The token is never logged, only `token received: yes/no`.

Not changed, deliberately: latent 2 (`broadcast_transcript_final` has no callers), latent 5 (unreachable middleware guards), latent 6 (full-transcript rebroadcast). Also left alone: `fetchFirstQuestion` and `fetchNextQuestion` in `RetellInterviewRoom.jsx` are unreachable and call an unimported `getNextQuestion`, which ESLint reports as `no-undef`. That is a real latent defect but it predates this investigation and is outside the transcript pipeline, so fixing it here would be an unrelated refactor.

Verification performed from this environment: `python3 -m py_compile` on the backend file passes, and ESLint on the frontend file reports no new diagnostics (the 10 errors and 3 warnings it does report are all pre-existing — unused imports and the two dead functions above). Runtime verification remains outstanding and is the user's to run, per section 7.
