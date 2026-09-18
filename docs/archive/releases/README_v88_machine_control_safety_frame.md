# LaserProg v88 — Safe machine control and continuous FRAME mode

This build repairs the laser machine dialog launch and adds a guarded GRBL execution state machine.

## Launch repair

The dialog connected the FRAME button to `self._frame_job`, but the method did not exist. Construction therefore raised `AttributeError` before the window appeared. The method is now implemented, and the application controller shows a visible error dialog if startup fails instead of only writing a hidden traceback.

## FRAME mode

- Generates a laser-off program from the actual exterior cut contours.
- Falls back to the job bounding contour when no exterior cut path exists.
- Repeats until the user presses **STOP FRAME**.
- Emits `M5` before the operation and before each contour.
- Rejects every `M3`/`M4` command during FRAME validation.
- Stopping FRAME sends GRBL real-time hold + soft reset and requires reconnection.

## Safety layer

Before USB transmission, LaserProg now validates the complete edited G-code against:

- machine X/Y dimensions from **Preferences > Laser engraving**;
- optional XY safety inset;
- maximum feed rate and laser `S` value;
- explicit `G90`/`G91` coordinate mode;
- supported, auditable G-code subset only;
- no rapid `G0` while the laser is enabled;
- no movement before an explicit `M5`;
- no absolute Z movement;
- bounded relative Z depth with mandatory retraction;
- final laser-off state.

The generator no longer automatically returns to machine origin after a job, because that unverified move could cross clamps or leave a configured safe inset.

## Emergency stop

The machine dialog includes a red **EMERGENCY STOP — F12** control. It sends GRBL real-time feed hold (`!`) followed by soft reset (`0x18`), closes the serial connection, and requires inspection/reconnection before reuse. The physical emergency stop or power switch remains the authoritative safety device.

Pinned Python 3.12.4 and runtime package versions are unchanged from v87.
