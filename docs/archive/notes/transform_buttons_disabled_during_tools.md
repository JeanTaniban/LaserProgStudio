# Transform buttons disabled while a tool is active

Update summary:

- The persistent transform mode is still remembered while a tool is open.
- The N/T/R/S transform buttons are disabled and shown in grey while a tool owns the preview/apply/cancel workflow.
- Opening a tool clears/hides the transform overlay without switching the stored mode back to N.
- Closing/applying/canceling the tool re-enables the transform buttons and restores the selected transform mode for the next selected part.
- Transform gizmo picking, hover, wheel refresh, and live inspector edits now check the same availability rule.

This prevents users from trying to transform geometry while another tool is waiting for Apply/Cancel, while keeping the user's chosen transform mode intact.
