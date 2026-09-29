# collect_recessed_diamond
Preconditions: the y9 west-pocket diamond ore has already broken, at least one inventory stack slot can accept diamonds, and the player is near `(-2999.3,9,-5572.7)`.
1. Clear the stone above/in front of the pocket until the player can move through; step 11408 and 11422 stone breaks opened the route.
2. Face approximately north and move through the opening toward `(-2999.1,9,-5571.3)` rather than repeatedly sweeping from the original ore face.
3. Run `collect_drops(ticks=48)` once. In the successful replay it moved into the recessed drop cell, settled at `(-2997.7,8,-5571.4)`, and fired `pickup diamond +3` at step 11499.
4. Require the pickup event; the ore-break event alone is not enough because the drops can remain below/behind the visible wall.
