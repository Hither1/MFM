# mechanism_table_aim_2349

- kind: mechanism
- status: stale
- confidence: 0.99
- created_step: 2349
- updated_step: 2400
- depends_on: location_table_live_0912

## Statement

The exact table-opening pose at (-3006.30,69,-5568.70) belongs to an earlier reset and must not be used as the current table location.

## Evidence

- The table placement block is reconstructed from the verified step-912 placement ray and step-919 successful interaction; the step-2349 failure left pitch 90/yaw -90 unchanged, while the player is now one block east of that table.
- At step 2371, two use_until_gui attempts at yaw 90/pitch 43 opened no screen, and the attached frame shows the crosshair on dirt immediately below the table's lower edge. The table itself fills the view and the wooden pickaxe is selected, isolating vertical aim as the likely failure.
- At step 2377, use_until_gui opened the crafting-table GUI from this exact pose after pitch 43 had failed twice.
- Current-reset visited rows never reach that pose; current events instead place/open a table from the worksite around (-3004.10,68,-5567.91) at steps 1408-1411.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
