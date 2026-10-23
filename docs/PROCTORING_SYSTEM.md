# Proctoring System

This is the shared proctoring contract for all rounds.

## Event Sources

- Browser visibility changes
- Fullscreen entry and exit
- Tab switch events
- Copy/paste events if enabled
- Webcam availability and frame interruptions
- Window focus loss

## Event Shape

Recommended proctoring event payload:

```json
{
  "round_id": 21,
  "event_type": "tab_switch",
  "severity": "medium",
  "event_data": {
    "timestamp": "2026-05-21T10:05:00Z",
    "details": "candidate switched away from the assessment tab"
  }
}
```

## Violation Thresholds

- Low severity: logged only.
- Medium severity: logged and counted.
- High severity: logged, counted, and may trigger warnings.
- Critical severity: immediate escalation and possible termination.

## Storage

- Persist events in `proctoring_events`.
- Link every event to a specific `round_id`.
- Store structured metadata in `event_data`.

## Shared Behavior

- Proctoring must work across aptitude, coding, and interview rounds.
- Timer expiry and proctoring violations are separate concerns.
- The session manager should consult proctoring status only when policy requires it.
