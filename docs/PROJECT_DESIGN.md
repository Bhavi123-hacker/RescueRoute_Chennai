# Chennai project design

## Requirement coverage

| Requirement | Implemented behavior |
| --- | --- |
| Chennai hospital list | 868 normalized named OSM records, source URLs, real coordinates, search/filter/CSV |
| User source | Neighborhood selector, map point, coordinate entry and browser geolocation within metro bounds |
| Preferred hospital | All records searchable; hard destination constraint with explicit alternative permission |
| Five earliest hospitals | Unique pickup-to-hospital ranking by minimum predicted road minutes plus approximate connectors |
| Care-aware dispatch | Care category, acceptance, unreserved beds/ICU and configured profile required |
| Traffic / changing routes | Synthetic normal/rush/incident, closures and road overrides; fresh A* after changes |
| Real roads / traffic | Optional server-side Amazon Location matrix and route alternatives; traffic where provider supports it |
| Attractive dashboard | Dark/light themes, actual street atlas, all-directory clusters, directional arrows and animated road playback |
| ML | Synthetic dataset, temporal holdout, trained JSON Random Forest inference |
| AWS | SAM stack for Cognito/API Gateway/Lambda/DynamoDB/S3/CloudFront/CloudWatch/IAM/optional Location |

## Ranking and assignment

For each hospital, the travel-only list minimizes pickup-to-hospital edge minutes using A* with a conservative geographic lower bound. Add approximate source/hospital connectors at a scenario-dependent local-street speed. Sort by minutes, break ties by ID, keep five distinct hospitals. Ambulance response, on-scene service, hospital handover wait and rough-road penalties are excluded from this list.

Suitable demo care first excludes unknown profiles, missing category, no acceptance or insufficient unreserved bed/ICU. Directory travel first screens mapped names/ER tags: 621 candidates in this snapshot. It excludes obvious eye/dental/fertility/optical/pharmacy-only names unless OSM tags an emergency department, and records explicitly tagged emergency=no. This is a heuristic, not clinical verification.

Mission assignment is separate: readiness + ambulance-to-pickup + on-scene + pickup-to-hospital + rough-road penalties + handover wait + connectors. Arrival ETA excludes penalties/handover wait. A user-preferred destination is retained unless unavailable and explicit fallback permission allows another. Unknown directory records must have an operator demo profile before dispatch.

## Search correctness and geography

Road graph: 36 approximate Chennai neighborhood centers and 65 modeled undirected links. Lengths derive from haversine distances with a detour factor. Streets are not surveyed OSM road segments. Source/hospital points connect approximately to the nearest anchor. No route from this graph should be presented as real road navigation.

For a selected objective, the heuristic scale is the smallest current edge objective divided by geographic edge distance. The triangle inequality makes the scaled straight-line distance conservative and consistent. Dijkstra and independent Floyd–Warshall are correctness oracles. BFS minimizes link count; shortest-distance Dijkstra minimizes kilometers. Dynamic replanning reruns A*, not D* Lite.

## AWS provider path

`POST /api/live-plan` is disabled unless ENABLE_LOCATION=true. Lambda calls CalculateRouteMatrix with the actual pickup coordinate and candidate hospital coordinates, DepartNow, Car, FastestRoute and UseTrafficData. Lists are chunked at 500 destinations. Successful rows are sorted by provider duration; five are returned. CalculateRoutes requests geometry and up to two alternatives for the chosen hospital. No synthetic result is substituted as live.

The provider preview does not drive the modeled A* mission. Provider car travel estimates are not special emergency-vehicle routing or signal preemption. Capacity remains demo/unknown. Matrix failures are omitted; the response reports compared/failed counts and billed pairs. Directory scope may request hundreds of paid origin-destination pairs per click. Snapshot timestamps and state revisions are displayed; relevant source/condition changes clear previews.

## State / lifecycle

TO_PICKUP → ON_SCENE → TO_HOSPITAL → ARRIVED → COMPLETED. NO_ROUTE pauses until feasible conditions return. Junction stepping and accelerated playback are simulation. Source/hospital connector travel is included in modeled duration/distance. Arrival consumes reported capacity; completion frees the ambulance at the hospital anchor.

Four ambulances share one bounded demonstration world. Active reservations reduce hospital capacity. Earlier missions receive reallocation priority. Command IDs protect repeated mutations; stale dispatch revisions are rejected. SQLite immediate transactions serve local mode; DynamoDB consistent reads and conditional revision writes serve AWS. Histories are capped and writes guarded below DynamoDB's item limit. This is not a production-scale multi-city database.

## Privacy and data boundaries

Exact user-selected pickup coordinates are stored with demo missions and exported reports. Amazon Location receives coordinates only when its preview is requested. Use fictional pickup points for presentations. No names, diagnoses or patient identity fields are collected. Browser location remains optional and handles denial/out-of-bounds locations.

OSM positions/names have attribution and source record links. Sixteen operational seed profiles are artificial demonstration assumptions; do not infer actual hospital specialties, beds, ICU or acceptance from them. Other profiles are unknown until the operator supplies demo values. Operator changes still do not become authenticated live hospital information.

## Deployment topology

CloudFront serves private S3 frontend assets. Cognito operator ID tokens authorize API Gateway JWT calls. Lambda plans routes, performs exported ML inference, edits shared DynamoDB state, signs Location routing calls and writes private S3 mission exports. CloudWatch stores seven-day logs and latency/error metrics. Browser map keys are restricted to map actions and the CloudFront referer; no AWS access keys are put in the client.

No SageMaker, SNS/SMS or real hospital integration is implemented. Future work includes validated road feeds, authenticated hospital capacity, physical ambulance telemetry, real-data model calibration, WebSockets, separate entity transactions and city-scale road benchmarking.

## Directed street-map implementation

The main map is a Leaflet canvas road atlas built from a bundled OSM driving-corridor snapshot. It displays all directory records by default through clusters, with name search and zoom-to-record controls. The former city perspective and Bay of Bengal drawing are removed.

`POST /api/street-plan` uses a cached directed road graph. One-way=yes/-1, implied motorway/roundabout direction and motor-vehicle access screening control edges. Nearby geometry points are compressed while retaining intersections and shape coordinates. Source and hospital snapping use a spatial grid; disconnected components are not joined with fabricated streets. Dotted endpoint connectors are approximate.

Dijkstra searches source-to-hospital candidates once, sorts five successful travel-time rows, then independently searches ambulance-to-source and hospital-to-return. Return can target pickup or the selected ambulance base. The implementation compares arc sequences to report whether both directions coincide. Eastbound/Westbound what-if weights change only matching directed edges. Explicit local street closures omit entire way IDs. Preview state is browser-local and does not mutate shared A* mission state.

The snapshot contains 10,740 accepted road ways, 21,905 nodes, 25,595 segments and 6,010 one-way ways. Turn restrictions, conditional access, barriers and live congestion are outside this educational street preview. Its class/maxspeed scenario estimates are independent of the RF model. The serverless template includes the authenticated street-plan endpoint and 512MB Lambda memory.
