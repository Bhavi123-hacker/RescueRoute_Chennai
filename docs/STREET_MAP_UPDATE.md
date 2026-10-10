# Street map update - quick use

The Bay of Bengal decoration was removed. The map now uses actual mapped Chennai driving corridors and shows every bundled hospital record through zoomable clusters.

- **Find a hospital on the map:** search any name; unknown profiles stay visible.
- **Fit all hospitals:** include all 868 records. Expand count clusters by zooming.
- **Compare return:** overlay outgoing purple and return gold with direction arrows.
- **Three journey cards:** ambulance to pickup, pickup to hospital, hospital to return. Return can target pickup or ambulance base. All directions are searched independently.
- **Directional traffic:** balanced/eastbound/westbound what-if weights.
- **Street closures:** click a mapped road, close in preview; clear to restore. These are local preview changes, separate from shared mission events.
- **Road playback:** animate the selected leg or scrub progress; this is simulation.
- **Street labels / basemap:** optionally load online OSM tiles. Bundled vector road geometry and labels work without tiles.

The top five use the directed street preview when it is current, or explicit AWS provider durations after a live request. A* dispatch assignments and mission stats still use the separate 36-anchor ML demonstration engine. Street preview speeds use mapped maxspeed or class assumptions and scenario weights, not ML predictions or live traffic. Dotted endpoint access links are approximate. Turn restrictions, conditional access and barriers are not implemented. Hospital capacity is demo/unknown; directory coverage is not exhaustive.

Checked example: Arumbakkam to MIOT has different outgoing and return paths in the snapshot. A return path may coincide in other cases; the UI reports this honestly instead of forcing an unnecessary detour.

Run locally from RescueRoute_Chennai: `python local_server.py`, then http://localhost:8000.
