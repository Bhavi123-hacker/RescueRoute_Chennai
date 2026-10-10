# Chennai demonstration — eight minutes

Start `python local_server.py`, open http://localhost:8000, and reset shared state from the AWS tab. For AWS, use the deployed CloudFront URL and Cognito operator login. Prefer a desktop viewport of 1280 pixels or wider.

| Time | Action | Observe and explain |
| --- | --- | --- |
| 0:00–0:45 | Introduce Chennai / data provenance | 868 mapped records; 16 demo operational profiles; roads, traffic and capacity are modeled locally. |
| 0:45–1:30 | Select source, then calculate | Choose Arumbakkam, coordinates or a map point. Five hospital cards rank pickup-to-hospital time, not ambulance response. Switch Suitable demo care / Directory travel. |
| 1:30–2:15 | Search and choose MIOT | Preferred hospital constrains dispatch. Unknown directory profiles need explicit operator demo setup. Allow alternative is off by default. |
| 2:15–3:00 | Click Guided demo | It resets selections to a repeatable critical-trauma request at N22 and dispatches one ambulance. Availability becomes 3/4; unsuitable ICU options are excluded. |
| 3:00–3:45 | Inject road accident, then hospital unavailable | The first road is closed; A* replans. The automatic destination changes from Apollo First Med (H15) to Vijaya Hospital (H08) in the tested reset scenario. Two reroutes are recorded. |
| 3:45–4:30 | Explore map / themes | Pan, zoom, fit route, compare return and light/dark toggle. Hospital pins use OSM coordinates; illustrated streets are modeled links. |
| 4:30–5:15 | Advance the journey | Next GPS step moves through modeled junctions, pickup, transport and arrival. Complete releases the ambulance at the hospital; reported bed count is consumed. |
| 5:15–6:00 | Change traffic / compare algorithms | Normal/rush can alter routes. A* and Dijkstra costs agree for a fixed snapshot; BFS optimizes fewest links. |
| 6:00–6:45 | Show ML results | Synthetic temporal holdout; Random Forest MAE 0.624 minutes. Explain that this does not establish real Chennai accuracy. |
| 6:45–8:00 | Show AWS and export | Describe actual service responsibilities. If deployed, request Real roads & traffic and show provider timestamp/alternatives, S3 export and CloudWatch evidence. |

## Check the five-hospital feature

- Change the pickup between Arumbakkam and Alwarpet. Calculate and confirm exactly five distinct cards, sorted by minutes.
- Switch Directory travel: some cards say capacity unknown. These are travel suggestions, not certified emergency destinations.
- Choose a card or use hospital search. Confirm the selected destination is retained even if it is not first in the fastest list.
- For a configured preferred hospital, dispatch with alternatives off; mark it unavailable. Mission pauses. In a separate reset run, allow an alternative and repeat: a feasible alternative may be assigned.
- With AWS enabled, click Real roads & traffic explicitly. Its top five use provider durations; demo traffic sliders do not alter the provider feed. Requests are chargeable.

## Honest presentation boundaries

No live beds, physical GPS, patient messaging or hospital notifications are connected. Hospital notices are internal dashboard records. The map uses bundled mapped road geometry. Directed road preview, shared A* mission simulation and AWS traffic preview are separate modes. The directory is not an exhaustive registry. AWS traffic preview is independent of modeled A* mission advancement. Local screenshots and offline SDK stubs are not proof of cloud deployment.

## New map demonstration

1. Use Arumbakkam as pickup, choose MIOT, and calculate. Wait for the street preview.
2. Click Compare return. Purple goes to the hospital; gold returns. Direction arrows and independent ETAs explain the difference.
3. Switch Back to ambulance base, then back to pickup. Each return destination gets its own search.
4. Change Eastbound congestion. This is a scenario, not a live feed.
5. Click a mapped street and Close in preview; inspect the reroute or explicit unreachable result. Clear preview closures to restore it.
6. Play road preview and scrub progress. This animation follows mapped geometry but is simulated.
7. Fit all hospitals: the count remains 868 / 868. Zoom into a count cluster, search a hospital and inspect its name/source/profile. Unknown profiles are still visible.

The directory is not an exhaustive registry. All bundled records are visible; live clinical capability/capacity is still unknown or demonstration data.
