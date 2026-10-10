/**
 * Generates the academic project report (Times New Roman) for RescueRoute Chennai.
 * Run: node scripts/generate_project_report.js
 */
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel,
  AlignmentType, WidthType, BorderStyle, PageBreak, ImageRun, Header, Footer,
  PageNumber, VerticalAlign, ShadingType } = require('docx');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const ASSETS = path.join(ROOT, 'docs', 'report_assets');
const OUT = path.join(ROOT, 'docs', 'RescueRoute_Chennai_Project_Report.docx');

const FONT = 'Times New Roman';
const BLUE = '1F4E79';
const PAGE_W = 11906; // A4
const MARGIN = 1080; // 0.75"
const CONTENT_W = PAGE_W - MARGIN * 2;

const thin = { style: BorderStyle.SINGLE, size: 8, color: '000000' };
const borders = { top: thin, bottom: thin, left: thin, right: thin };
const noBorder = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function t(text, opts = {}) {
  return new TextRun({
    text: String(text ?? ''),
    font: FONT,
    size: opts.size || 24, // 12pt
    bold: !!opts.bold,
    italics: !!opts.italics,
    color: opts.color,
  });
}

function p(text, opts = {}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.JUSTIFIED,
    spacing: { after: opts.after ?? 160, before: opts.before ?? 0, line: opts.line || 276 },
    indent: opts.indent,
    children: Array.isArray(text) ? text : [t(text, opts)],
  });
}

function center(text, opts = {}) {
  return p(text, { ...opts, align: AlignmentType.CENTER });
}

function heading(text, level = HeadingLevel.HEADING_1) {
  const size = level === HeadingLevel.HEADING_1 ? 28 : level === HeadingLevel.HEADING_2 ? 26 : 24;
  return new Paragraph({
    heading: level,
    spacing: { before: 280, after: 160 },
    children: [t(text, { bold: true, size })],
  });
}

function blank(n = 1) {
  return Array.from({ length: n }, () => new Paragraph({ children: [] }));
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function cell(text, opts = {}) {
  const width = opts.width || 1500;
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: opts.fill ? { type: ShadingType.CLEAR, fill: opts.fill } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      spacing: { after: 40, before: 40 },
      children: [t(text, { size: opts.size || 18, bold: !!opts.bold })],
    })],
  });
}

function makeTable(headers, rows, colWidths) {
  const head = new TableRow({
    children: headers.map((h, i) => cell(h, { width: colWidths[i], bold: true, fill: 'D9E2F3', align: AlignmentType.CENTER, size: 17 })),
  });
  const body = rows.map(r => new TableRow({
    children: r.map((c, i) => cell(c, { width: colWidths[i], size: 16 })),
  }));
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [head, ...body],
  });
}

function img(file, w, h, caption) {
  const buf = fs.readFileSync(path.join(ASSETS, file));
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 160, after: 80 },
      children: [new ImageRun({ type: 'png', data: buf, transformation: { width: w, height: h }, altText: { title: caption || file, description: caption || file, name: file } })],
    }),
    center(caption, { italics: true, size: 20, after: 200 }),
  ];
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    spacing: { after: 80 },
    children: [t(text, { size: 22 })],
  });
}

const litCols = [500, 1600, 1400, 1600, 1800, 2146]; // sum ~9046 ~ content

const children = [];

// ========== 1. BONAFIDE ==========
children.push(
  ...blank(2),
  center('ANNA UNIVERSITY / AFFILIATED INSTITUTION', { bold: true, size: 24 }),
  center('(College Name to be filled)', { size: 22 }),
  ...blank(2),
  center('BONAFIDE CERTIFICATE', { bold: true, size: 32, color: BLUE }),
  ...blank(1),
  center('PROJECT REPORT', { bold: true, size: 28 }),
  ...blank(1),
  center('ON', { size: 22 }),
  ...blank(1),
  center('RESCUEROUTE CHENNAI', { bold: true, size: 36, color: BLUE }),
  center('Emergency Ambulance Route Optimizer using A*, Machine Learning and AWS Serverless Services', { bold: true, size: 24 }),
  ...blank(2),
  center('Submitted in partial fulfillment of the requirements for the award of the degree of', { size: 20, italics: true }),
  ...blank(1),
  center('BACHELOR OF ENGINEERING', { bold: true, size: 26 }),
  center('IN', { size: 20 }),
  center('COMPUTER SCIENCE AND ENGINEERING', { bold: true, size: 24 }),
  ...blank(2),
  center('Submitted by', { size: 20 }),
  ...blank(1),
  center('[STUDENT NAME]', { bold: true, size: 26 }),
  center('Register No: [REGISTER NUMBER]', { size: 22 }),
  ...blank(2),
  center('Under the Guidance of', { size: 20 }),
  center('[GUIDE NAME], [Designation]', { bold: true, size: 22 }),
  ...blank(2),
  center('DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING', { bold: true, size: 20 }),
  center('[COLLEGE NAME]', { bold: true, size: 20 }),
  center('[CITY] – [PIN]', { size: 20 }),
  center('Academic Year: 2025 – 2026', { size: 20 }),
  pageBreak(),
);

// ========== 2. CERTIFICATE ==========
children.push(
  heading('2. CERTIFICATE', HeadingLevel.HEADING_1),
  ...blank(1),
  p('This is to certify that the project report entitled “RescueRoute Chennai — Emergency Ambulance Route Optimizer using A*, Machine Learning and AWS Serverless Services” submitted by [STUDENT NAME], Register No. [REGISTER NUMBER], is a bonafide record of work carried out under my supervision in the Department of Computer Science and Engineering, [COLLEGE NAME], in partial fulfillment of the requirements for the award of the degree of Bachelor of Engineering in Computer Science and Engineering during the academic year 2025–2026.'),
  ...blank(2),
  p('The contents of this report, in full or in parts, have not been submitted to any other Institute or University for the award of any degree or diploma.'),
  ...blank(3),
  p([t('Date: _______________', { size: 22 })]),
  p([t('Place: _______________', { size: 22 })]),
  ...blank(3),
  new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W / 2, CONTENT_W / 2],
    rows: [new TableRow({
      children: [
        new TableCell({
          borders: noBorders,
          width: { size: CONTENT_W / 2, type: WidthType.DXA },
          children: [
            p('Signature of the Guide', { align: AlignmentType.LEFT, bold: true, size: 20 }),
            p('[GUIDE NAME]', { align: AlignmentType.LEFT, size: 20 }),
            p('Designation', { align: AlignmentType.LEFT, size: 18 }),
          ],
        }),
        new TableCell({
          borders: noBorders,
          width: { size: CONTENT_W / 2, type: WidthType.DXA },
          children: [
            p('Signature of the HOD', { align: AlignmentType.LEFT, bold: true, size: 20 }),
            p('[HOD NAME]', { align: AlignmentType.LEFT, size: 20 }),
            p('Head of the Department', { align: AlignmentType.LEFT, size: 18 }),
          ],
        }),
      ],
    })],
  }),
  ...blank(3),
  p('External Examiner: _______________________', { align: AlignmentType.LEFT, size: 20 }),
  p('Internal Examiner: _______________________', { align: AlignmentType.LEFT, size: 20 }),
  pageBreak(),
);

// ========== 3. INDEX ==========
children.push(
  heading('3. INDEX (TABLE OF CONTENTS)', HeadingLevel.HEADING_1),
  p('The following chapters constitute this project report.', { align: AlignmentType.LEFT }),
  makeTable(
    ['S. No.', 'Title', 'Page'],
    [
      ['1', 'Bonafide (Title, Name)', 'i'],
      ['2', 'Certificate', 'ii'],
      ['3', 'Index (Table)', 'iii'],
      ['4', 'Abstract', '1'],
      ['5', 'Introduction', '2'],
      ['6', 'Literature Review', '4'],
      ['7', 'Gaps Identified / Limitations', '7'],
      ['8', 'Modules', '8'],
      ['9', 'Screenshots (Project Flow)', '12'],
      ['10', 'Graphs', '14'],
      ['11', 'Conclusion', '16'],
      ['12', 'Future Work', '17'],
      ['13', 'References', '18'],
      ['—', 'Appendix A: AWS Services Used', '19'],
      ['—', 'Appendix B: How to Run Locally', '20'],
    ],
    [900, 6500, 1646],
  ),
  ...blank(1),
  p([t('List of Figures', { bold: true, size: 22 })]),
  makeTable(
    ['Fig.', 'Description'],
    [
      ['1', 'Operational flow of RescueRoute Chennai'],
      ['2', 'AWS serverless deployment topology'],
      ['3', 'Map view: pickup, hospital and route'],
      ['4', 'Active journey panel after dispatch'],
      ['5', 'ML model MAE comparison (holdout)'],
      ['6', 'Random Forest feature importance'],
    ],
    [900, 8146],
  ),
  pageBreak(),
);

// ========== 4. ABSTRACT ==========
children.push(
  heading('4. ABSTRACT', HeadingLevel.HEADING_1),
  p('Emergency medical response in large metropolitan cities such as Chennai is constrained by traffic variability, fragmented hospital information and the need to assign scarce ambulance resources under time pressure. This project presents RescueRoute Chennai, an educational demonstration system that optimizes ambulance-to-hospital journeys using a combination of classical graph search, machine-learning traffic estimation and a deployable Amazon Web Services (AWS) serverless architecture.'),
  p('The system integrates an OpenStreetMap-derived directory of 868 named hospital records within a Chennai metro bounding box, a 36-neighborhood modeled road graph with 65 links for mission simulation, and a directed street atlas of 10,740 mapped driving corridors for visual routing. Route planning uses A* search with Dijkstra, BFS and shortest-distance baselines for algorithmic comparison. Edge travel times are estimated by a Random Forest model trained on 234,000 Chennai-calibrated synthetic traffic observations with a chronological train/test split.'),
  p('The operator dashboard supports pickup selection (neighborhood, map click, coordinates or browser geolocation), care-aware hospital ranking, dispatch of a simulated ambulance from the pickup location to the selected hospital, GPS-style journey stepping, road closures and hospital unavailability with automatic replanning. Local execution uses a Python standard-library server and SQLite; the cloud stack (AWS SAM) provides Cognito authentication, HTTP and WebSocket APIs, Lambda compute with X-Ray, DynamoDB shared state, S3 and CloudFront hosting, SNS mission alerts, CloudWatch observability, Budgets and an optional Amazon Location and SageMaker training path.'),
  p([t('Keywords: ', { bold: true }), t('Ambulance routing, A* algorithm, Random Forest, Chennai, OpenStreetMap, AWS Lambda, DynamoDB, serverless, emergency logistics')], { align: AlignmentType.LEFT }),
  pageBreak(),
);

// ========== 5. INTRODUCTION ==========
children.push(
  heading('5. INTRODUCTION', HeadingLevel.HEADING_1),
  heading('5.1 Background', HeadingLevel.HEADING_2),
  p('Urban emergency response depends on rapidly connecting a patient pickup point to a clinically suitable hospital while accounting for traffic, fleet availability and bed capacity. Commercial navigation applications optimize general driving time but typically do not model ambulance assignment, ICU/bed reservations or care-category constraints. Conversely, academic routing papers often evaluate algorithms on abstract graphs without an end-to-end operator interface or cloud deployment path.'),
  heading('5.2 Problem Statement', HeadingLevel.HEADING_2),
  p('Design and implement a demonstrable Chennai-focused ambulance route optimization system that (i) accepts a user-selected pickup, (ii) ranks feasible hospitals using predicted travel and care constraints, (iii) assigns an available ambulance, (iv) computes a shortest/traffic-aware path from pickup to hospital, (v) visualizes and simulates the journey, and (vi) can be deployed on AWS using serverless services.'),
  heading('5.3 Objectives', HeadingLevel.HEADING_2),
  bullet('Provide a searchable Chennai hospital directory grounded in OpenStreetMap records.'),
  bullet('Compute traffic-aware routes using A* on a modeled graph and a directed street network.'),
  bullet('Predict edge travel times with a Random Forest trained on synthetic but Chennai-calibrated data.'),
  bullet('Simulate dispatch, GPS progression, road incidents and hospital capacity changes.'),
  bullet('Package the system for local demo and AWS SAM deployment (API, auth, storage, alerts, observability).'),
  heading('5.4 Scope', HeadingLevel.HEADING_2),
  p('The project is an educational demonstration. Hospital beds, ICU counts and acceptance flags are operator demo inputs. Ambulance GPS is simulated. The Random Forest does not claim measured real-world Chennai accuracy. Optional Amazon Location provides provider traffic only when enabled after deployment. The simplified operational story used in the final interface is: select pickup → rank hospital → Dispatch starts the trip at pickup → hospital.'),
  heading('5.5 Organization of the Report', HeadingLevel.HEADING_2),
  p('Section 6 surveys related work in tabular form. Section 7 lists gaps and limitations. Section 8 describes software modules. Sections 9–10 present flow screenshots and evaluation graphs. Sections 11–13 conclude, outline future work and list references. Appendices summarize AWS services and local run instructions.'),
  pageBreak(),
);

// ========== 6. LITERATURE REVIEW ==========
children.push(
  heading('6. LITERATURE REVIEW', HeadingLevel.HEADING_1),
  p('The literature review summarizes representative work on emergency vehicle routing, traffic-aware path finding and cloud-assisted logistics. Entries are presented in the required tabular format.'),
  ...blank(1),
  makeTable(
    ['S. No.', 'Journal / Source, Year', 'Model / System Name', 'Parameter (cost, resource, etc.)', 'Algorithm Comparison', 'Limitations'],
    [
      [
        '1',
        'Transportation Research / classical OR literature (Dijkstra, 1959; Hart et al., 1968)',
        'Shortest-path / A* search',
        'Edge cost (time or distance); heuristic admissibility',
        'Dijkstra optimal for non-negative weights; A* expands fewer nodes with consistent heuristic',
        'Static graphs; no live traffic or hospital capacity model',
      ],
      [
        '2',
        'ACM / AI planning literature — D* / D* Lite family (Koenig & Likhachev, 2002+)',
        'D* Lite dynamic replanning',
        'Incremental repair cost after edge changes',
        'Faster replan than full restart on small changes vs repeated A*',
        'More complex state; this project instead reruns A* after incidents for clarity',
      ],
      [
        '3',
        'IEEE Transactions on Intelligent Transportation Systems (representative traffic ML surveys, 2018–2023)',
        'Traffic speed / travel-time predictors (RF, GBDT, LSTM)',
        'MAE/RMSE of travel time; sensor or probe data volume',
        'Tree ensembles strong on tabular features; deep models need dense sensors',
        'Real Chennai probe data often unavailable for student projects',
      ],
      [
        '4',
        'Emergency logistics / OR journals (ambulance location & allocation models)',
        'Facility location / covering models (e.g., MCLP variants)',
        'Coverage probability, fleet size, response-time thresholds',
        'Strategic siting vs operational routing are complementary',
        'Often omit street-level routing UI and care-category filters',
      ],
      [
        '5',
        'OpenStreetMap / GIScience community resources (ODbL ecosystem)',
        'OSM hospital & road extracts',
        'Spatial coverage, tagging completeness, license compliance',
        'Crowd-sourced maps vs proprietary navigation graphs',
        'Tagging errors; emergency=yes is not clinical verification',
      ],
      [
        '6',
        'Amazon Web Services documentation & serverless patterns (SAM, 2018–2025)',
        'Serverless web backends (API Gateway + Lambda + DynamoDB)',
        'Request latency, cost per million requests, cold starts',
        'Serverless vs always-on VM for spiky demo traffic',
        'Vendor lock-in; regional service availability; matrix API cost',
      ],
      [
        '7',
        'Applied ML for routing demos / academic projects (scikit-learn RF baselines)',
        'Random Forest travel-time regression',
        'Feature set (hour, rain, congestion); holdout R²/MAE',
        'RF vs linear/rule baselines on synthetic holds',
        'Synthetic generators can overstate accuracy if not carefully separated',
      ],
      [
        '8',
        'Human–computer interaction for emergency dashboards (command-center UX studies)',
        'Operator dispatch consoles',
        'Time-to-decision, situation awareness, error rates',
        'Map-centric vs form-centric workflows',
        'Many systems are proprietary; few open Chennai-specific demos',
      ],
    ],
    litCols,
  ),
  ...blank(1),
  p('Summary: Prior work provides strong algorithmic foundations (A*/Dijkstra), dynamic replanning theory, traffic learning methods and cloud patterns, but few open projects combine a Chennai hospital atlas, care-aware assignment, ML-estimated edge costs, street visualization and a full AWS SAM stack in one demonstrable system. RescueRoute Chennai occupies that integration niche for education and evaluation.'),
  pageBreak(),
);

// ========== 7. GAPS / LIMITATIONS ==========
children.push(
  heading('7. GAPS IDENTIFIED / LIMITATIONS', HeadingLevel.HEADING_1),
  heading('7.1 Gaps Addressed by This Project', HeadingLevel.HEADING_2),
  bullet('Lack of an integrated Chennai demo linking OSM hospitals, A* assignment and operator UI.'),
  bullet('Weak linkage between ML traffic features and both mission costs and street ETAs.'),
  bullet('Missing student-deployable AWS reference architecture with auth, state and alerts.'),
  bullet('Insufficient clarity between modeled graph routing and real mapped street geometry.'),
  heading('7.2 Current Limitations (Honest Scope)', HeadingLevel.HEADING_2),
  bullet('Hospital capacity, ICU and acceptance are demonstration inputs, not live hospital APIs.'),
  bullet('Ambulance GPS and journey timing are simulated (accelerated junction / visual drive).'),
  bullet('The 36-node A* graph is an approximate neighborhood network, not surveyed lanes.'),
  bullet('Street preview omits turn restrictions, gates and live congestion sensors.'),
  bullet('Random Forest metrics are on synthetic holdout data; not a claim of field accuracy.'),
  bullet('Amazon Location traffic is optional and billable; disabled by default in deploy guidance.'),
  bullet('Not a production 108/EMS system; not for real emergency decision-making.'),
  pageBreak(),
);

// ========== 8. MODULES ==========
children.push(
  heading('8. MODULES', HeadingLevel.HEADING_1),
  heading('8.1 System Overview', HeadingLevel.HEADING_2),
  p('RescueRoute Chennai is organized into frontend presentation, backend planning/state, machine-learning artifacts, city/street data packages and AWS infrastructure-as-code.'),
  ...img('fig_flow.png', 540, 190, 'Figure 1. Operational flow (pickup → hospital dispatch).'),
  heading('8.2 Module M1 — City Directory & Pickup Selection', HeadingLevel.HEADING_2),
  p('Loads 868 normalized OSM hospital records (name, coordinates, address/phone/website when mapped, source URL). Operators choose pickup via neighborhood selector, map click, lat/lon or browser geolocation inside metro bounds (approximately 12.80–13.25 N, 80.05–80.35 E). Preferred hospital can be Auto (nearest/fastest feasible) or an explicit directory choice.'),
  heading('8.3 Module M2 — Traffic Prediction (ML)', HeadingLevel.HEADING_2),
  p('A Random Forest (80 trees, max depth 12, 12 features) is trained on 234,000 synthetic observations (65 edges × 24 hours × 150 dates). Chronological split: 112 training dates / 38 holdout dates. Features include distance, free-flow speed, hour encodings, weekday/weekend, congestion, rain, road type, monsoon, corridor load and event shock. Exported JSON forest is loaded by the backend for inference without shipping scikit-learn to Lambda.'),
  heading('8.4 Module M3 — A* Mission Planning & Assignment', HeadingLevel.HEADING_2),
  p('Builds a weighted graph from modeled roads and current settings (traffic profile, hour, rain, ML on/off, closures). Filters hospitals by configured care profile, acceptance, beds and ICU. Scores ambulance–hospital pairs using readiness, path costs, on-scene time, connectors and handover wait. Compares A*, Dijkstra, BFS and shortest-distance on the same snapshot. In the simplified demo UX, Dispatch places the assigned unit at the pickup and plans pickup → hospital.'),
  heading('8.5 Module M4 — Directed Street Preview', HeadingLevel.HEADING_2),
  p('POST /api/street-plan runs Dijkstra on a cached directed OSM corridor graph (10,740 ways) to draw the gold pickup→hospital geometry, rank travel-only hospitals and support what-if closures / directional tides. This preview is separate from the 36-anchor mission simulator but shares the RF/scenario speed narrative when ML mode is enabled.'),
  heading('8.6 Module M5 — Dispatch, Journey Simulation & Replanning', HeadingLevel.HEADING_2),
  p('Dispatch creates a shared mission (revisioned state). GPS simulator / Next junction advances along remaining roads. Road closures and hospital unavailability trigger A* replan. Arrival allocates demo capacity; Release returns the ambulance to AVAILABLE at the hospital node. Command IDs provide idempotency; expected_revision prevents stale writes.'),
  heading('8.7 Module M6 — Operator Dashboard (Frontend)', HeadingLevel.HEADING_2),
  p('Single-page UI (HTML/CSS/JS, Leaflet map) with Dispatch console, Hospital board, City directory, Algorithms & ML and AWS architecture views. Dark/light themes, SOS shortcut, field helpers (navigate/call/share/print), and live event stream.'),
  heading('8.8 Module M7 — AWS Serverless Platform', HeadingLevel.HEADING_2),
  p('AWS SAM template provisions Cognito, HTTP API (JWT), WebSocket API, Lambda (+ X-Ray), DynamoDB (world + connections), S3 (frontend + private reports/models), CloudFront (OAC), SNS alerts, CloudWatch metrics/alarms, Budgets, IAM roles, optional Amazon Location (maps/places/routes) and a SageMaker execution role for cloud retraining. Local mode substitutes SQLite and a pure-Python static server.'),
  ...img('fig_aws_architecture.png', 540, 310, 'Figure 2. AWS serverless topology implemented in template.yaml.'),
  heading('8.9 Technology Stack Summary', HeadingLevel.HEADING_2),
  makeTable(
    ['Layer', 'Technology'],
    [
      ['Languages', 'Python 3.12+ (backend/ML), JavaScript (frontend), YAML (SAM)'],
      ['Algorithms', 'A*, Dijkstra, BFS, shortest-distance; street Dijkstra'],
      ['ML', 'scikit-learn Random Forest → exported JSON inference'],
      ['Maps / Data', 'Leaflet, OpenStreetMap extracts (ODbL), optional Amazon Location'],
      ['Local persistence', 'SQLite (rescueroute-chennai.sqlite3)'],
      ['Cloud', 'AWS Cognito, API Gateway, Lambda, DynamoDB, S3, CloudFront, SNS, CloudWatch, Budgets, X-Ray, optional Location & SageMaker'],
      ['Tests', 'unittest (51 tests), optional Playwright browser checks'],
    ],
    [2200, 6846],
  ),
  pageBreak(),
);

// ========== 9. SCREENSHOTS ==========
children.push(
  heading('9. SCREENSHOTS (REPRESENTING FLOW OF PROJECT)', HeadingLevel.HEADING_1),
  p('The following figures illustrate the end-to-end demonstration flow used for evaluation. Operators should capture additional cloud-console screenshots after SAM deploy for submission binders.'),
  heading('9.1 Flow Step Narrative', HeadingLevel.HEADING_2),
  bullet('Step A — Open http://localhost:8020 (or CloudFront URL) and hard-refresh.'),
  bullet('Step B — Click the map to set pickup (P). Nearby hospitals appear.'),
  bullet('Step C — System ranks feasible hospitals; gold path shows pickup → hospital.'),
  bullet('Step D — Click Dispatch ambulance (or SOS). Active journey becomes TO HOSPITAL.'),
  bullet('Step E — Red ambulance marker drives along the route; GPS simulator advances modeled junctions.'),
  bullet('Step F — On ARRIVED, release the ambulance or reset the shared demo.'),
  heading('9.2 Map Route View', HeadingLevel.HEADING_2),
  ...img('ss_map_route.png', 520, 300, 'Figure 3. Map after pickup selection: P (pickup), H (hospital), gold street route and cyan A* overlay.'),
  heading('9.3 Active Journey Panel', HeadingLevel.HEADING_2),
  ...img('ss_active_journey.png', 480, 320, 'Figure 4. Active journey card showing mission phase, ETA, GPS simulator controls and scenario injection.'),
  p('Note: Earlier prototypes showed an ambulance-base → pickup → hospital approach path. The evaluated demo flow was simplified so Dispatch starts at the patient pickup and proceeds directly to the hospital, matching the intended real-life storyboard.'),
  pageBreak(),
);

// ========== 10. GRAPHS ==========
children.push(
  heading('10. GRAPHS', HeadingLevel.HEADING_1),
  heading('10.1 Model Error Comparison', HeadingLevel.HEADING_2),
  p('On the chronological holdout set (59,280 rows), the Random Forest achieves substantially lower mean absolute error than a fixed-speed baseline and also improves on a handcrafted traffic-rule baseline.'),
  makeTable(
    ['Model', 'MAE (min)', 'RMSE (min)', 'R²'],
    [
      ['Random Forest', '0.526', '0.765', '0.995'],
      ['Traffic rule', '1.241', '1.818', '0.972'],
      ['Fixed speed', '9.741', '12.590', '−0.363'],
    ],
    [2500, 2000, 2000, 2546],
  ),
  ...blank(1),
  ...img('fig_model_mae.png', 420, 240, 'Figure 5. Holdout MAE by model family.'),
  heading('10.2 Feature Importance', HeadingLevel.HEADING_2),
  p('Congestion and rain dominate learned importance, followed by event shock and cyclic hour encodings—consistent with the synthetic generator’s Chennai-like peak/monsoon structure.'),
  ...img('fig_feature_importance.png', 450, 270, 'Figure 6. Random Forest feature importance.'),
  heading('10.3 Algorithmic Verification (Summary)', HeadingLevel.HEADING_2),
  p('Automated tests include thousands of A* versus Dijkstra endpoint comparisons on shared snapshots and independent Floyd–Warshall checks for cost consistency. BFS optimizes hop count; shortest-distance Dijkstra optimizes kilometers. These graphs are correctness oracles rather than runtime benchmarks of production cities.'),
  pageBreak(),
);

// ========== 11. CONCLUSION ==========
children.push(
  heading('11. CONCLUSION', HeadingLevel.HEADING_1),
  p('RescueRoute Chennai demonstrates an end-to-end educational pipeline for emergency route optimization in a Chennai setting. It combines OSM hospital geography, A*-based assignment, Random Forest travel-time estimation, interactive street visualization and a complete AWS serverless deployment blueprint.'),
  p('The system meets the stated objectives of pickup selection, hospital ranking, dispatch simulation and cloud readiness, while clearly documenting what is real (mapped directory geometry, deployable infrastructure) versus modeled (capacity, GPS, synthetic traffic). The final operator narrative—pickup to hospital under Dispatch—matches stakeholder expectations for a clear demonstration storyboard.'),
  p('Within its declared limitations, the project is suitable for academic evaluation, live demos and as a foundation for future integration with authenticated hospital data and calibrated traffic feeds.'),
  pageBreak(),
);

// ========== 12. FUTURE WORK ==========
children.push(
  heading('12. FUTURE WORK', HeadingLevel.HEADING_1),
  bullet('Integrate authenticated live bed/ICU feeds from partner hospitals.'),
  bullet('Calibrate the traffic model on real Chennai probe or signal data; publish confidence intervals.'),
  bullet('Replace the 36-node mission graph with city-scale contracted road networks while keeping sub-second plans.'),
  bullet('Add multi-ambulance optimization under simultaneous incidents (fleet dispatch, not single assignment).'),
  bullet('Implement true incremental replanners (D* Lite) where repeated full A* becomes costly.'),
  bullet('Mobile field application with offline maps and secure role separation (dispatcher vs paramedic).'),
  bullet('Expand Amazon Location usage with cost guards and caching for directory-scale matrices.'),
  bullet('Formal human-factors study of the dispatch console with emergency-operations volunteers.'),
  pageBreak(),
);

// ========== 13. REFERENCES ==========
children.push(
  heading('13. REFERENCES', HeadingLevel.HEADING_1),
  p('[1] E. W. Dijkstra, “A note on two problems in connexion with graphs,” Numerische Mathematik, 1959.', { align: AlignmentType.LEFT }),
  p('[2] P. E. Hart, N. J. Nilsson and B. Raphael, “A formal basis for the heuristic determination of minimum cost paths,” IEEE Trans. Syst. Sci. Cybern., 1968.', { align: AlignmentType.LEFT }),
  p('[3] S. Koenig and M. Likhachev, “D* Lite,” AAAI, 2002.', { align: AlignmentType.LEFT }),
  p('[4] OpenStreetMap contributors, OpenStreetMap database, ODbL 1.0. https://www.openstreetmap.org/copyright', { align: AlignmentType.LEFT }),
  p('[5] Pedregosa et al., “Scikit-learn: Machine Learning in Python,” JMLR, 2011.', { align: AlignmentType.LEFT }),
  p('[6] Amazon Web Services, “AWS Serverless Application Model (SAM) Developer Guide.” https://docs.aws.amazon.com/serverless-application-model/', { align: AlignmentType.LEFT }),
  p('[7] Amazon Web Services, “Amazon DynamoDB Developer Guide — Condition Expressions.”', { align: AlignmentType.LEFT }),
  p('[8] Amazon Web Services, “Amazon API Gateway HTTP API — JWT authorizers.”', { align: AlignmentType.LEFT }),
  p('[9] Amazon Web Services, “Amazon Location Service — CalculateRouteMatrix API.”', { align: AlignmentType.LEFT }),
  p('[10] Amazon Web Services, “Amazon CloudFront — Restricting access to S3 with OAC.”', { align: AlignmentType.LEFT }),
  p('[11] Leaflet.js documentation. https://leafletjs.com/', { align: AlignmentType.LEFT }),
  p('[12] RescueRoute Chennai project documentation: README.md, docs/PROJECT_DESIGN.md, docs/AWS_DEPLOYMENT.md, docs/DATA_CARD.md (repository artifacts, 2026).', { align: AlignmentType.LEFT }),
  pageBreak(),
);

// ========== APPENDIX A AWS ==========
children.push(
  heading('APPENDIX A — AWS SERVICES USED', HeadingLevel.HEADING_1),
  p('The following Amazon Web Services are defined in template.yaml and supporting scripts. Exact account deployment depends on sam deploy in the student/operator AWS account.'),
  makeTable(
    ['S. No.', 'AWS Service', 'Role in RescueRoute Chennai'],
    [
      ['1', 'Amazon Cognito', 'Operator user pool and app client; short-lived ID tokens for API access'],
      ['2', 'Amazon API Gateway (HTTP API)', 'REST endpoints with JWT authorizer, CORS and throttling'],
      ['3', 'Amazon API Gateway (WebSocket)', 'Real-time mission/state fan-out to connected dashboards'],
      ['4', 'AWS Lambda', 'Plan, street-plan, ML inference, mutations, exports, optional Location calls'],
      ['5', 'AWS X-Ray', 'Distributed tracing for Lambda troubleshooting'],
      ['6', 'Amazon DynamoDB', 'Shared WORLD/DEMO state with conditional revision writes; connection registry'],
      ['7', 'Amazon S3', 'Private frontend origin; private reports, datasets, model JSON, city catalog'],
      ['8', 'Amazon CloudFront', 'HTTPS CDN for the dashboard with Origin Access Control to S3'],
      ['9', 'Amazon SNS', 'Optional email alerts on dispatch / reroute / arrival when AlertEmail set'],
      ['10', 'Amazon CloudWatch', 'Logs, latency/error metrics, dispatch-error alarm'],
      ['11', 'AWS Budgets', 'Cost budget monitoring for the stack'],
      ['12', 'AWS IAM', 'Least-privilege roles for Lambda, SageMaker and Location routing'],
      ['13', 'Amazon Location Service (optional)', 'Maps basemap key, Places search, CalculateRouteMatrix / CalculateRoutes'],
      ['14', 'Amazon SageMaker (role + script)', 'Optional cloud training job entry for ml/sagemaker_entry.py'],
      ['15', 'AWS SAM / CloudFormation', 'Infrastructure as code packaging and deployment'],
    ],
    [700, 2800, 5546],
  ),
  ...blank(1),
  p('Security notes: browser map keys are restricted; no long-term AWS access keys are embedded in the frontend. Exact pickup coordinates are sent to Amazon Location only when a live preview is explicitly requested.'),
  pageBreak(),
);

// ========== APPENDIX B ==========
children.push(
  heading('APPENDIX B — HOW TO RUN LOCALLY', HeadingLevel.HEADING_1),
  p('Prerequisites: Python 3.12+.'),
  p('Commands (Windows):', { bold: true, align: AlignmentType.LEFT }),
  p('cd /d E:\\RescueRoute_Chennai', { align: AlignmentType.LEFT, size: 20 }),
  p('py local_server.py', { align: AlignmentType.LEFT, size: 20 }),
  p('Open http://localhost:8020 and press Ctrl+F5.', { align: AlignmentType.LEFT }),
  ...blank(1),
  p('Optional tests:', { bold: true, align: AlignmentType.LEFT }),
  p('python -m unittest discover -s tests -v', { align: AlignmentType.LEFT, size: 20 }),
  ...blank(1),
  p('Optional AWS deploy outline: aws configure → sam build → sam deploy --guided → python scripts/publish_frontend.py → python scripts/setup_user.py. See docs/AWS_DEPLOYMENT.md for parameters (EnableLocation, AlertEmail) and cost cautions.'),
  ...blank(2),
  center('— End of Report —', { bold: true, size: 22 }),
  center('Replace bracketed placeholders (student name, register number, college, guide) before final binding.', { italics: true, size: 18 }),
);

const doc = new Document({
  styles: {
    default: {
      document: {
        styles: [{
          // fallback
        }],
      },
    },
    paragraphStyles: [
      {
        id: 'Normal',
        name: 'Normal',
        run: { font: FONT, size: 24 },
        paragraph: { spacing: { line: 276, after: 120 } },
      },
      {
        id: 'Heading1',
        name: 'Heading 1',
        basedOn: 'Normal',
        next: 'Normal',
        quickStyle: true,
        run: { font: FONT, size: 28, bold: true, color: '000000' },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2',
        name: 'Heading 2',
        basedOn: 'Normal',
        next: 'Normal',
        quickStyle: true,
        run: { font: FONT, size: 26, bold: true, color: '000000' },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 },
      },
    ],
  },
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{
        level: 0,
        format: 'bullet',
        text: '•',
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }],
    }],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: 16838 },
        margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [t('RescueRoute Chennai — Project Report', { size: 16, italics: true, color: '666666' })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [t('Page ', { size: 16 }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16 }), t(' of ', { size: 16 }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16 })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log('Wrote', OUT, '(' + buf.length + ' bytes)');
}).catch(err => {
  console.error(err);
  process.exit(1);
});
