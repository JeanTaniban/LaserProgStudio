# Pass 308 — machine control safety and FRAME state machine

## Root launch failure

`MachineEngravingDialog._build_usb_box()` connected `btn_frame.clicked` to `_frame_job`, but `_frame_job` was absent. Python raised `AttributeError` while constructing the dialog. `MachineController` caught the exception and only logged it, making the tool appear to do nothing.

## Runtime state machine

```text
DISCONNECTED
    | connect
    v
IDLE / READY
    | start job                 | start frame
    v                           v
STREAMING                    FRAMING (loop, M5)
    | complete                  | user stop
    v                           v
IDLE                         STOPPING -> DISCONNECTED

Any connected/active state -- F12 --> EMERGENCY -> reconnect required
```

USB job/frame streaming runs in a `QThread`, keeping the Qt UI responsive so the emergency control remains usable.

## Preflight state machine

```text
G-code text
  -> lexical allow-list
  -> modal coordinate tracking
  -> X/Y endpoint envelope
  -> feed and S-power limits
  -> laser/motion interlocks
  -> relative-Z depth tracking
  -> final M5 + Z retraction
  -> SAFE or BLOCKED
```

Unsupported commands are blocked instead of guessed. Linear endpoints are checked because LaserProg emits only G0/G1 paths; circular interpolation and coordinate-system mutation commands are not accepted by this sender.

## Z correction

The prior generator documented relative Z steps but emitted them under `G90`, creating absolute negative Z commands. It now brackets every bounded Z delta with `G91` and restores `G90`, then retracts the cumulative offset at job end.

## Validation

- Machine generator and safety tests: 10 passed.
- Machine + architecture targeted tests: 16 passed.
- `scripts/quality_gate.py`: OK.
