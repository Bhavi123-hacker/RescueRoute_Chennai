# -*- coding: utf-8 -*-
"""Generate a formal black-and-white academic project report (Times New Roman)."""
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, Twips, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "report_assets"
OUT = ROOT / "docs" / "RescueRoute_Chennai_Project_Report.docx"
OUT_FALLBACK = ROOT / "docs" / "RescueRoute_Chennai_Project_Report_NEW.docx"

def set_run_font(run, size=12, bold=False, italic=False):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)

def add_para(doc, text, *, size=12, bold=False, italic=False, align="justify",
             space_after=8, space_before=0, first_line=True):
    p = doc.add_paragraph()
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "left":
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    elif align == "right":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    if first_line and align == "justify":
        pf.first_line_indent = Cm(0.75)
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic)
    return p

def add_heading_bw(doc, text, level=1):
    # Manual heading so we control black color (no blue theme)
    sizes = {1: 14, 2: 13, 3: 12}
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, size=sizes.get(level, 12), bold=True)
    return p

def page_break(doc):
    doc.add_page_break()

def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(item)
        set_run_font(run, size=12)

def shade_cell(cell, fill="D9D9D9"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill}"/>')
    tcPr.append(shd)

def set_cell_text(cell, text, *, bold=False, size=9, center=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold)

def add_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], h, bold=True, size=9, center=True)
        shade_cell(table.rows[0].cells[i], "E7E6E6")
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            set_cell_text(table.rows[r_i + 1].cells[c_i], str(val), size=8)
    if col_widths:
        for row in table.rows:
            for idx, w in enumerate(col_widths):
                row.cells[idx].width = Cm(w)
    doc.add_paragraph()
    return table

def add_image(doc, name, width_in=5.8, caption=""):
    path = ASSETS / name
    if not path.exists():
        add_para(doc, f"[Figure missing: {name}]", italic=True, align="center", first_line=False)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width_in))
    if caption:
        add_para(doc, caption, size=10, italic=True, align="center", first_line=False, space_after=12)

def force_styles_black(doc):
    for style_name in ["Normal", "Heading 1", "Heading 2", "Heading 3", "List Bullet"]:
        try:
            st = doc.styles[style_name]
            st.font.name = "Times New Roman"
            st.font.color.rgb = RGBColor(0, 0, 0)
            if "Heading" in style_name:
                st.font.bold = True
        except KeyError:
            pass

def build():
    doc = Document()
    force_styles_black(doc)
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)

    # Header / footer
    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hr = hp.add_run("RescueRoute Chennai — Project Report")
    set_run_font(hr, size=9, italic=True)
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = fp.add_run("Page ")
    set_run_font(fr, size=9)
    # simple page field
    fld = parse_xml(
        f'<w:fldSimple {nsdecls("w")} w:instr=" PAGE "/>'
    )
    fp._p.append(fld)

    # ========== 1 BONAFIDE / TITLE ==========
    for _ in range(4):
        doc.add_paragraph()
    add_para(doc, "BONAFIDE CERTIFICATE", bold=True, size=16, align="center", first_line=False)
    doc.add_paragraph()
    doc.add_paragraph()
    add_para(doc, "RESCUEROUTE CHENNAI", bold=True, size=20, align="center", first_line=False)
    add_para(
        doc,
        "Emergency Ambulance Route Optimizer using A* Search, Random Forest Traffic Prediction and AWS Serverless Architecture",
        bold=True, size=12, align="center", first_line=False,
    )
    doc.add_paragraph()
    doc.add_paragraph()
    add_para(doc, "Submitted by", size=11, align="center", first_line=False)
    add_para(doc, "BHAVY GARG", bold=True, size=14, align="center", first_line=False)
    add_para(doc, "Register No.: 24BAI1088", size=12, align="center", first_line=False)
    add_para(
        doc,
        "GitHub Repository: https://github.com/Bhavi123-hacker/RescueRoute_Chennai",
        size=11, align="center", first_line=False,
    )
    page_break(doc)

    # ========== 2 CERTIFICATE ==========
    add_heading_bw(doc, "2. CERTIFICATE", 1)
    add_para(
        doc,
        "This is to certify that the project report entitled “RescueRoute Chennai — Emergency Ambulance Route Optimizer using A* Search, Random Forest Traffic Prediction and AWS Serverless Architecture” submitted by Bhavy Garg, Register No. 24BAI1088, is a bonafide record of work carried out under my supervision in partial fulfillment of the requirements for the award of the degree of Bachelor of Engineering in Computer Science and Engineering during the academic year 2025–2026. The project source code is available at https://github.com/Bhavi123-hacker/RescueRoute_Chennai.",
    )
    add_para(
        doc,
        "Certified further that, to the best of my knowledge, the matter embodied in this report has not been submitted to any other University or Institution for the award of any degree or diploma. The work described here is an educational demonstration system for emergency routing in Chennai. Hospital capacity values used in the software are operator demonstration inputs. Ambulance GPS progression is simulated. The machine-learning metrics reported in this document are computed on a synthetic holdout set and must not be interpreted as measured field accuracy for Chennai traffic.",
    )
    add_para(
        doc,
        "The student has demonstrated the local execution of the system and has prepared the AWS SAM infrastructure definition for subsequent cloud deployment. Final cloud account deployment, if performed, shall be documented with stack outputs and operator screenshots in the viva voce submission package.",
    )
    doc.add_paragraph()
    add_para(doc, "Date: ____________________", align="left", first_line=False)
    add_para(doc, "Place: ___________________", align="left", first_line=False)
    doc.add_paragraph()
    add_para(doc, "Signature of the Guide: ______________________", align="left", first_line=False)
    doc.add_paragraph()
    add_para(doc, "Internal Examiner: ______________________", align="left", first_line=False)
    add_para(doc, "External Examiner: ______________________", align="left", first_line=False)
    page_break(doc)

    # ========== 3 INDEX ==========
    add_heading_bw(doc, "3. INDEX (TABLE OF CONTENTS)", 1)
    add_para(doc, "The report is organized as follows. Page numbers below are indicative and will update after printing.", first_line=False)
    add_table(
        doc,
        ["S. No.", "Title of the Chapter / Section", "Page"],
        [
            ["1", "Bonafide (Title, Name)", "i"],
            ["2", "Certificate", "ii"],
            ["3", "Index (Table)", "iii"],
            ["4", "Abstract", "1"],
            ["5", "Introduction", "2"],
            ["6", "Literature Review", "5"],
            ["7", "Gaps Identified / Limitations", "9"],
            ["8", "Modules", "11"],
            ["9", "Screenshots — Development Steps & Project Execution Flow", "16"],
            ["10", "Graphs", "28"],
            ["11", "Conclusion", "31"],
            ["12", "Future Work", "32"],
            ["13", "References", "33"],
            ["A", "Appendix A — AWS Services Used", "35"],
            ["B", "Appendix B — Local Execution and Planned AWS Deploy", "37"],
        ],
        [2, 11, 2],
    )
    add_para(doc, "List of Figures", bold=True, align="left", first_line=False)
    add_table(
        doc,
        ["Fig. No.", "Description"],
        [
            ["1", "Operational flow of RescueRoute Chennai"],
            ["2", "AWS deployment architecture (planned / SAM template)"],
            ["3", "Project development pipeline (how the system was built)"],
            ["4", "Repository structure snapshot"],
            ["5", "Step 1 — Dispatch console loaded"],
            ["6", "Step 2 — Pickup neighborhood selected"],
            ["7", "Step 3 — Emergency / traffic parameters"],
            ["8", "Step 4 — Route calculated on Chennai map"],
            ["9", "Step 5 — Suggested hospitals ranked"],
            ["10", "Step 6 — Active journey after Dispatch"],
            ["11", "Step 7 — Map path / GPS progress"],
            ["12", "Step 8 — Hospital operations board"],
            ["13", "Step 9 — City directory (868 hospitals)"],
            ["14", "Step 10 — Algorithms & ML comparison"],
            ["15", "Step 11 — AWS architecture screen"],
            ["16", "Holdout MAE comparison of travel-time models"],
            ["17", "Holdout R-squared comparison"],
            ["18", "Random Forest feature importance"],
        ],
        [2.5, 12.5],
    )
    page_break(doc)

    # ========== 4 ABSTRACT ==========
    add_heading_bw(doc, "4. ABSTRACT", 1)
    add_para(
        doc,
        "Urban emergency medical response requires rapid selection of a suitable hospital and a traffic-aware driving path under uncertainty. Commercial navigation products optimize general driving time, but they rarely encode ambulance assignment, intensive-care constraints or shared operational state suitable for classroom demonstration and controlled evaluation. This project presents RescueRoute Chennai, an end-to-end educational system that optimizes ambulance journeys for the Chennai metropolitan context using classical graph search, machine-learning travel-time estimation and a deployable Amazon Web Services (AWS) serverless blueprint.",
    )
    add_para(
        doc,
        "The implemented software integrates three geographic layers: (i) an OpenStreetMap-derived directory of 868 named hospital records inside a Chennai metro bounding box; (ii) a 36-neighborhood modeled road graph with 65 links used by the mission simulator; and (iii) a directed street atlas of 10,740 mapped driving corridors used for visual shortest-path preview. Mission planning uses the A* algorithm with Dijkstra, breadth-first search and shortest-distance baselines for comparison. Edge travel times are estimated by a Random Forest regressor trained on 234,000 Chennai-calibrated synthetic observations with a chronological train/test split (112 training dates and 38 holdout dates).",
    )
    add_para(
        doc,
        "The operator interface supports pickup selection by neighborhood, map click, coordinates or browser geolocation; care-aware hospital ranking; dispatch of a simulated ambulance starting at the patient pickup and proceeding to the hospital; GPS-style journey stepping; road closures; and hospital unavailability with automatic replanning. Local execution uses a Python standard-library HTTP server and SQLite persistence. The cloud design, expressed with AWS SAM, includes Amazon Cognito, API Gateway (HTTP and WebSocket), AWS Lambda with X-Ray, Amazon DynamoDB, Amazon S3, Amazon CloudFront, Amazon SNS, Amazon CloudWatch, AWS Budgets, IAM roles, optional Amazon Location Service and a SageMaker training role. Cloud deployment is the planned next stage after local verification.",
    )
    add_para(
        doc,
        "Results reported in this document include algorithm-oracle agreement under automated tests, Random Forest holdout MAE of approximately 0.53 minutes against stronger baselines on the synthetic corpus, and a verified local demonstration flow captured in coloured screenshots. The work does not claim clinical authority, live hospital telemetry or measured field traffic accuracy. Its contribution is a reproducible, examiner-ready integration of algorithms, data, interface and cloud-ready architecture for Chennai-focused emergency routing education.",
    )
    add_para(
        doc,
        "Keywords: Ambulance routing; A* algorithm; Dijkstra; Random Forest; Chennai; OpenStreetMap; AWS Lambda; DynamoDB; serverless computing; emergency logistics.",
        first_line=False,
    )
    page_break(doc)

    # ========== 5 INTRODUCTION ==========
    add_heading_bw(doc, "5. INTRODUCTION", 1)
    add_heading_bw(doc, "5.1 Background", 2)
    add_para(
        doc,
        "Chennai is a large metropolitan region with dense arterial corridors, monsoon-related travel disruption and a heterogeneous hospital landscape that includes government tertiary centres and private multi-specialty hospitals. In an emergency, the operational question is not only “what is the shortest geometric path,” but also “which available ambulance should be assigned,” “which hospital can accept the required care,” and “how should the plan change when a road closes or a destination becomes unavailable.” These questions couple algorithms, data quality, human operators and infrastructure reliability.",
    )
    add_para(
        doc,
        "Academic treatments of shortest paths (Dijkstra, A*) and dynamic replanning (D* Lite) are mature. Likewise, machine-learning methods for travel-time estimation are widely studied. What is less common in student-accessible form is a coherent demonstration that joins a city hospital atlas, an operator console, reproducible ML artifacts and a concrete cloud deployment description. RescueRoute Chennai was built to fill that integration gap for teaching, evaluation and subsequent AWS deployment.",
    )
    add_heading_bw(doc, "5.2 Problem Statement", 2)
    add_para(
        doc,
        "Design and implement a demonstrable Chennai-focused ambulance route optimization system that accepts a user-selected pickup location, ranks feasible hospitals using predicted travel and care constraints, assigns an available ambulance unit, computes a traffic-aware path from the pickup to the hospital, visualizes and simulates the journey for an operator, and is packaged for local demonstration today and AWS serverless deployment next.",
    )
    add_heading_bw(doc, "5.3 Objectives", 2)
    add_bullets(doc, [
        "To construct a searchable Chennai hospital directory grounded in OpenStreetMap records with source attribution.",
        "To compute traffic-aware routes using A* on a modeled mission graph and Dijkstra on a directed street network.",
        "To predict edge travel times using a Random Forest trained on synthetic but Chennai-calibrated data with a temporal holdout.",
        "To simulate dispatch, GPS progression, road incidents and hospital capacity changes with versioned shared state.",
        "To provide a usable operator dashboard covering dispatch, hospital board, directory, algorithms/ML and AWS explanation views.",
        "To define and document an AWS SAM stack (Cognito, API Gateway, Lambda, DynamoDB, S3, CloudFront, SNS, CloudWatch, Budgets, optional Location and SageMaker) for deployment after local validation.",
    ])
    add_heading_bw(doc, "5.4 Scope and Assumptions", 2)
    add_para(
        doc,
        "The system is an educational demonstration, not a production emergency medical service. Hospital beds, ICU counts and acceptance flags are operator demonstration inputs. Ambulance positions advance through simulated GPS updates. The Random Forest results are holdout metrics on synthetic data and do not claim measured real-world Chennai accuracy. Optional Amazon Location traffic is available only after cloud enablement and may incur cost. In the final demonstration storyboard, Dispatch starts the trip at the patient pickup and proceeds to the hospital, which matches the operator mental model used during evaluation.",
    )
    add_heading_bw(doc, "5.5 Significance of the Study", 2)
    add_para(
        doc,
        "The significance of RescueRoute Chennai is threefold. First, it provides a transparent teaching artifact: every major decision—algorithm, model feature, hospital filter and AWS service—can be inspected in source form. Second, it localizes the demonstration to Chennai using OSM hospitals and neighborhood anchors that students recognize, which improves engagement during viva and peer review. Third, it prepares a realistic transition to cloud hosting: the same planning code is intended to run behind Cognito-protected APIs with DynamoDB shared state, so the project is not trapped as a laptop-only script.",
    )
    add_para(
        doc,
        "From an engineering-education viewpoint, the project also models professional practice: unit tests, infrastructure as code, data attribution (ODbL), cost awareness for optional Location APIs and explicit non-claims about clinical authority. These practices matter as much as the A* implementation itself when graduates join industry teams.",
    )
    add_heading_bw(doc, "5.6 Methodology Overview", 2)
    add_para(
        doc,
        "The methodology follows a build–measure–demonstrate cycle. Requirements were derived from the emergency-routing storyboard (pickup, hospital selection, dispatch, progress, arrival). Algorithms were selected from classical literature with Dijkstra as the optimality oracle. Travel times were estimated by Random Forest on a temporally split synthetic corpus. The user interface was iterated until the operator flow was unambiguous: Find route, then Dispatch from pickup to hospital. Persistence and concurrency were modeled with revisioned shared state so multi-tab demos do not silently overwrite one another. Finally, the AWS SAM template was authored so that local success can be followed by cloud deployment without a redesign.",
    )
    add_heading_bw(doc, "5.7 Organization of the Report", 2)
    add_para(
        doc,
        "Section 6 presents a detailed literature review in the prescribed tabular format. Section 7 records gaps and limitations. Section 8 describes software modules and technology choices. Section 9 presents screenshots of the working application flow. Section 10 reports graphs from the ML evaluation. Sections 11–13 provide conclusion, future work and references. Appendices enumerate AWS services and run/deploy steps.",
    )
    page_break(doc)

    # ========== 6 LITERATURE ==========
    add_heading_bw(doc, "6. LITERATURE REVIEW", 1)
    add_para(
        doc,
        "This chapter reviews representative work relevant to emergency vehicle routing, traffic-aware path finding, hospital data sources and cloud-hosted operational systems. The review is presented in the required table format and is followed by a narrative synthesis explaining how the present project positions itself relative to prior art.",
    )
    add_heading_bw(doc, "6.1 Tabular Review", 2)
    add_table(
        doc,
        ["S. No.", "Journal / Source, Year", "Model Name", "Parameter (cost, resource, etc.)", "Algorithm Comparison", "Limitations"],
        [
            ["1", "Numerische Mathematik, 1959 (Dijkstra)", "Dijkstra shortest path", "Non-negative edge weights; optimality of path cost", "Optimal for non-negative weights; expands more nodes than informed search", "Static graphs; no traffic learning; no hospital capacity model"],
            ["2", "IEEE Trans. Syst. Sci. Cybern., 1968 (Hart, Nilsson, Raphael)", "A* heuristic search", "Admissible/consistent heuristic; node expansions; path cost", "Fewer expansions than Dijkstra when heuristic is informative; same optimal cost under consistency", "Heuristic design dependent on domain; static unless replanned"],
            ["3", "AAAI, 2002 (Koenig & Likhachev)", "D* Lite", "Incremental repair cost after edge weight changes", "Often cheaper than full A* restart for small map edits", "Higher implementation complexity; this project uses full A* replan for clarity"],
            ["4", "Transportation / ITS surveys, 2018–2023", "Travel-time predictors (RF, GBDT, LSTM)", "MAE/RMSE of travel time; data volume; feature set", "Tree models strong on tabular sensors; sequence models need dense probes", "Real Chennai probe datasets are often unavailable for student projects"],
            ["5", "Operations Research / EMS location literature", "Covering / allocation models (e.g., MCLP family)", "Coverage probability; fleet size; response-time thresholds", "Strategic siting complements operational routing", "Often omit street-level UI and care-category filters"],
            ["6", "OpenStreetMap / GIScience (ODbL ecosystem)", "OSM hospital and road extracts", "Spatial coverage; tagging completeness; license compliance", "Crowd-sourced openness vs proprietary navigation graphs", "Tagging errors; emergency tags are not clinical verification"],
            ["7", "JMLR, 2011 (Pedregosa et al.) / applied ML practice", "scikit-learn Random Forest", "Number of trees; depth; feature importance; holdout R²", "Strong baseline for tabular regression versus linear rules", "Overfitting risk if temporal leakage is ignored"],
            ["8", "AWS SAM / serverless pattern documentation, 2018–2025", "API Gateway + Lambda + DynamoDB backends", "Latency; cost per million requests; cold starts; IAM scope", "Serverless suits bursty demos versus always-on VMs", "Vendor lock-in; regional limits; Location matrix cost"],
            ["9", "HCI / command-center dashboard studies", "Operator dispatch consoles", "Time-to-decision; situation awareness; error rate", "Map-centric workflows vs form-centric workflows", "Many systems proprietary; few open Chennai demos"],
            ["10", "Amazon Location Service API references", "CalculateRouteMatrix / CalculateRoutes", "Provider duration; billed matrix pairs; geometry fidelity", "Provider traffic vs synthetic scenario weights", "Billable; coverage varies; not EMS-priority routing"],
        ],
        [1.2, 3.2, 2.4, 3.0, 3.0, 3.0],
    )
    add_heading_bw(doc, "6.2 Narrative Synthesis — Path Algorithms", 2)
    add_para(
        doc,
        "Classical path algorithms remain the correct foundation for route optimality on static weighted graphs. Dijkstra’s algorithm guarantees minimum path cost when edge weights are non-negative. It is conceptually simple and therefore an excellent correctness oracle. A* augments Dijkstra with a heuristic estimate of remaining cost. When the heuristic is admissible and consistent, A* returns the same optimal cost while typically expanding fewer nodes. In RescueRoute Chennai the heuristic is a scaled geographic lower bound; the scaling constant is chosen so that predicted travel times remain consistent with free-flow and scenario constraints. Dijkstra remains available as a side-by-side comparison row so that students can verify that A* costs match the oracle on identical graphs.",
    )
    add_para(
        doc,
        "Breadth-first search is retained as a pedagogical contrast because it minimizes hop count rather than minutes. Shortest-distance Dijkstra minimizes kilometers and is useful when explaining that the word “shortest” is objective-dependent: a short geometric path may be slow under congestion, while a longer arterial may be faster in minutes. Presenting all four results on the Algorithms screen prevents the common viva mistake of equating hop count with emergency response quality.",
    )
    add_heading_bw(doc, "6.3 Narrative Synthesis — Dynamic Replanning", 2)
    add_para(
        doc,
        "Dynamic replanners such as D* Lite are theoretically attractive when maps change frequently. They repair an existing search tree instead of discarding all prior work. For an educational mission simulator with a modest 36-node graph, however, repeatedly running A* after a closure or hospital change is transparent and easy to test. That design choice is deliberate: clarity and verifiability outweigh incremental complexity at the present scale. Section 12 records D* Lite as a future option if the mission graph grows to city scale.",
    )
    add_heading_bw(doc, "6.4 Narrative Synthesis — Travel-Time Learning", 2)
    add_para(
        doc,
        "On the learning side, Random Forests provide a robust tabular baseline when features encode hour-of-day, rain, congestion and corridor shocks. Gradient-boosted trees and recurrent networks appear frequently in intelligent-transportation surveys, but they demand denser probe data and heavier serving stacks. For a student-deployable system that must also run inside AWS Lambda cold starts, a compact exported forest is preferable. The project’s dataset is synthetic but calibrated to plausible Chennai patterns (peak hours, weekend relief, monsoon bias). A chronological split avoids random-row leakage that would inflate accuracy. Metrics are therefore honest relative to the generator, yet they are not a substitute for field calibration with traffic cameras or floating-car data.",
    )
    add_heading_bw(doc, "6.5 Narrative Synthesis — EMS Allocation and GIS Data", 2)
    add_para(
        doc,
        "Emergency medical service literature often emphasizes facility location and covering models. Those strategic models answer where ambulances should be stationed over months. RescueRoute Chennai instead focuses on the operational decision once a pickup is known: which configured hospital to choose and which path to drive. OpenStreetMap contributes the metro-scale hospital names and coordinates under the Open Database License. Tagging quality varies; therefore the software treats OSM as a geographic directory, not as a clinical accreditation database. Demonstration capacity profiles are applied by the operator before a directory hospital can accept a simulated mission.",
    )
    add_heading_bw(doc, "6.6 Narrative Synthesis — Cloud and Operator Consoles", 2)
    add_para(
        doc,
        "From an information-systems perspective, AWS serverless patterns supply a realistic deployment target for a shared demonstration world. Cognito authenticates operators; API Gateway exposes planning and mutation endpoints; Lambda executes the same Python planning modules used locally; DynamoDB stores revisioned world state; S3 and CloudFront host the dashboard; SNS can notify stakeholders; CloudWatch and Budgets provide operational and cost visibility. Command-center HCI studies emphasize map-centric situation awareness; the Leaflet console follows that guidance with a large map card and secondary tabular boards. The literature rarely packages algorithms, Chennai GIS, ML artifacts and cloud blueprints together. RescueRoute Chennai’s contribution is therefore integrative.",
    )
    add_heading_bw(doc, "6.7 Relevance to the Present Project", 2)
    add_para(
        doc,
        "Table rows 1–3 justify the algorithm suite and the choice to replan with full A*. Rows 4 and 7 justify Random Forest as the travel-time estimator and scikit-learn as the training toolchain. Rows 5–6 justify hospital ranking plus OSM directory data. Rows 8–10 justify the AWS SAM architecture and the cautious stance on Amazon Location billing. Collectively, the review supports the claim that the project is grounded in established methods while filling an integration gap for Chennai-focused educational demonstration and subsequent cloud deployment.",
    )
    page_break(doc)

    # ========== 7 GAPS ==========
    add_heading_bw(doc, "7. GAPS IDENTIFIED / LIMITATIONS", 1)
    add_heading_bw(doc, "7.1 Gaps Addressed", 2)
    add_para(
        doc,
        "Prior student projects often stop at algorithm animation on toy graphs, or at a map without assignment logic, or at a cloud diagram without runnable code. Industry navigation products hide internals and do not expose care constraints. The gaps addressed by this work are therefore practical and pedagogical.",
    )
    add_bullets(doc, [
        "Absence of an open Chennai hospital atlas wired into an assignment engine.",
        "Weak coupling between traffic features and both mission costs and street ETAs.",
        "Missing student-deployable AWS reference architecture with authentication and shared state.",
        "Insufficient separation, in demos, between modeled graph routing and mapped street geometry.",
        "Lack of a clear operator storyboard: pickup selection, dispatch from pickup, arrival and release.",
    ])
    add_heading_bw(doc, "7.2 Current Limitations", 2)
    add_para(
        doc,
        "Honest limitation statements are required for scientific integrity and for viva examination. The following constraints apply to the present implementation and must be stated whenever the system is demonstrated.",
    )
    add_bullets(doc, [
        "Hospital beds, ICU counts and acceptance flags are demonstration inputs, not live hospital information systems.",
        "Ambulance GPS and journey timing are simulated; they are not telemetry from physical vehicles.",
        "The 36-node A* graph is an approximate neighborhood network and must not be presented as surveyed lane geometry.",
        "The street preview omits turn restrictions, barriers and live sensor congestion.",
        "Random Forest metrics are synthetic-holdout results; they are not a claim of field accuracy.",
        "Amazon Location is optional, billable and disabled in the default deploy guidance until costs are understood.",
        "The application is not a substitute for official emergency numbers or clinical triage protocols.",
    ])
    add_heading_bw(doc, "7.3 Implications for Evaluation", 2)
    add_para(
        doc,
        "Evaluation in this report therefore emphasizes software correctness (unit tests, algorithm oracles), reproducibility (exported model JSON, fixed seeds) and demonstration completeness (operator flow screenshots), rather than claiming operational EMS performance. After AWS deployment, additional evidence should include stack outputs, CloudWatch metrics and authenticated operator login screenshots.",
    )
    add_heading_bw(doc, "7.4 Ethical and Safety Limitations", 2)
    add_para(
        doc,
        "Because the system can look like a real command console, ethical presentation is part of the limitation statement. Demonstrators must tell audiences that the product is educational software. Exact patient locations should not be retained beyond a demonstration reset when real personal data are ever introduced. Optional Amazon Location calls that transmit coordinates must be deliberate and logged. The application must never be marketed as a replacement for dialing official emergency services.",
    )
    add_para(
        doc,
        "These limitations do not diminish the engineering value of the project; they bound the claims so that academic credit rests on correct design, clear explanation and reproducible demonstration rather than on unsafe operational promises.",
    )
    page_break(doc)

    # ========== 8 MODULES ==========
    add_heading_bw(doc, "8. MODULES", 1)
    add_heading_bw(doc, "8.1 System Overview", 2)
    add_para(
        doc,
        "RescueRoute Chennai is organized into frontend presentation, backend planning and state, machine-learning artifacts, city and street data packages, automated tests and AWS infrastructure-as-code. Figure 1 summarizes the operator flow used in demonstrations.",
    )
    add_image(doc, "fig_flow.png", 5.9, "Figure 1. Demonstration operational flow (pickup to hospital).")
    # Figures 3–15 are step-wise screenshots in Chapter 9.
    add_heading_bw(doc, "8.2 Module M1 — City Directory and Pickup Selection", 2)
    add_para(
        doc,
        "This module loads 868 normalized hospital records derived from an OpenStreetMap snapshot (dated 8 October 2026 in the bundled catalog). Each record includes a name, coordinates, optional address/phone/website fields and a source URL for inspection. Operators choose a pickup using a neighborhood selector (36 anchors), map click, latitude/longitude entry or browser geolocation, provided the point lies inside the metro bounding box. Destination may be left on Auto (nearest/fastest feasible configured hospital) or set explicitly from the directory. Unknown-capacity directory rows require an operator demo profile before they can accept a simulated mission.",
    )
    add_heading_bw(doc, "8.3 Module M2 — Traffic Prediction (Machine Learning)", 2)
    add_para(
        doc,
        "A Random Forest with 80 trees and maximum depth 12 is trained on 234,000 synthetic observations formed as 65 edges × 24 hours × 150 dates. Twelve features encode distance, free-flow speed, cyclic hour, weekday/weekend, congestion, rain, road type, monsoon, corridor load and event shock. Training uses the first 112 dates; testing uses the remaining 38 dates. The trained forest is exported to JSON so Lambda and the local server can run inference without shipping the full scikit-learn runtime. On the holdout set, Random Forest MAE is approximately 0.53 minutes, improving on a traffic-rule baseline (about 1.24 minutes) and a fixed-speed baseline (about 9.74 minutes).",
    )
    add_heading_bw(doc, "8.4 Module M3 — A* Mission Planning and Assignment", 2)
    add_para(
        doc,
        "The planner builds a weighted graph from modeled roads and the current scenario (traffic profile, hour, rain, ML toggle, closures). Hospitals are filtered by configured care capability, acceptance, unreserved beds and ICU. Candidates are scored using readiness, path costs, on-scene time, approximate connectors and handover wait. Algorithm comparison rows expose A*, Dijkstra, BFS and shortest-distance results on the same snapshot. In the simplified demonstration contract used for this report, Dispatch places the assigned unit at the pickup node and plans the transport leg to the hospital, so the Active Journey begins as TO HOSPITAL from the patient location.",
    )
    add_heading_bw(doc, "8.5 Module M4 — Directed Street Preview", 2)
    add_para(
        doc,
        "The endpoint POST /api/street-plan executes Dijkstra on a cached directed OSM corridor graph. It returns gold pickup-to-hospital geometry, travel-only hospital rankings and optional response/return legs. One-way restrictions and motor-vehicle access screening are applied. Local street closures and directional traffic tides are browser-side what-if controls and do not mutate the shared A* mission document unless the operator also injects modeled road events. Approximate dotted connectors acknowledge that building entrances are not surveyed.",
    )
    add_heading_bw(doc, "8.6 Module M5 — Dispatch, Simulation and Replanning", 2)
    add_para(
        doc,
        "Dispatch creates a revisioned mission in shared state. The GPS simulator and Next-junction controls advance the remaining route. Road closures and hospital unavailability trigger A* replan with event logging. Arrival consumes demonstration capacity; Release returns the ambulance to AVAILABLE at the hospital node. Command identifiers provide idempotency. Expected-revision checks prevent stale writes when multiple operators share a demonstration world.",
    )
    add_heading_bw(doc, "8.7 Module M6 — Operator Dashboard", 2)
    add_para(
        doc,
        "The frontend is a Leaflet-based single-page application with Dispatch console, Hospital board, City directory, Algorithms & ML and AWS architecture views. Light and dark themes are supported; light theme screenshots are used in this report for print clarity. Field helpers include Google Maps navigation, call, share, copy and print card actions. SOS provides a one-click critical-trauma path for demos.",
    )
    add_heading_bw(doc, "8.8 Module M7 — AWS Serverless Platform (Planned Deployment)", 2)
    add_para(
        doc,
        "Infrastructure is defined in template.yaml using AWS SAM. The intended topology is shown in Figure 2. Local mode substitutes SQLite and a pure-Python static server so the same business logic can be graded without cloud credentials. After verification, the planned deployment sequence is sam build, sam deploy, frontend publish and Cognito operator setup. Amazon Location remains optional until cost controls are accepted.",
    )
    add_image(doc, "fig_aws_architecture.png", 5.9, "Figure 2. AWS deployment architecture defined for RescueRoute Chennai.")
    add_heading_bw(doc, "8.9 Technology Stack", 2)
    add_table(
        doc,
        ["Layer", "Technology / Artifact"],
        [
            ["Languages", "Python 3.12+ (backend, ML), JavaScript (frontend), YAML (SAM)"],
            ["Algorithms", "A*, Dijkstra, BFS, shortest-distance; street Dijkstra"],
            ["Machine learning", "scikit-learn Random Forest → exported JSON inference"],
            ["Maps and data", "Leaflet, OpenStreetMap extracts (ODbL), optional Amazon Location"],
            ["Local persistence", "SQLite (rescueroute-chennai.sqlite3)"],
            ["Cloud services", "Cognito, API Gateway, Lambda, DynamoDB, S3, CloudFront, SNS, CloudWatch, Budgets, X-Ray, IAM, optional Location & SageMaker"],
            ["Verification", "unittest suite (51 tests), optional Playwright checks"],
        ],
        [4, 11],
    )
    add_heading_bw(doc, "8.10 Module Interaction Summary", 2)
    add_para(
        doc,
        "During a typical demonstration, Module M1 captures the pickup and optional preferred hospital. Module M2 supplies edge minutes when the ML toggle is on. Module M3 ranks hospitals and builds the mission path. Module M4 optionally decorates the map with street geometry and travel-only rankings. Module M5 writes the revisioned mission and advances simulation. Module M6 renders all of the above for the operator. Module M7 is dormant in local mode and becomes active after AWS deployment. This interaction map is useful during viva when an examiner asks where a particular behavior is implemented.",
    )
    add_para(
        doc,
        "Failure handling is also modular. If street planning fails, the console can still show the A* mission path. If ML artifacts are missing, rule-based minutes remain available. If a preferred hospital lacks a demo capacity profile, the UI asks the operator to configure it rather than silently inventing beds. These graceful degradations are intentional teaching features: they show that production systems must degrade safely when a dependency is unavailable.",
    )
    page_break(doc)

    # ========== 9 SCREENSHOTS ==========
    add_heading_bw(doc, "9. SCREENSHOTS — DEVELOPMENT STEPS & PROJECT EXECUTION FLOW", 1)
    add_para(
        doc,
        "This chapter answers the examiner requirement for step-wise photographs showing how the project was built and how it runs. Part A documents the development sequence. Part B documents a complete local execution walkthrough captured from http://localhost:8020. Report text is black; screenshots and figures are kept in colour. After AWS deployment, Cognito sign-in and CloudFront URL screenshots should be appended.",
    )

    add_heading_bw(doc, "9.1 Part A — How the Project Was Built (Development Steps)", 2)
    add_para(
        doc,
        "RescueRoute Chennai was constructed in ordered engineering stages rather than as a single unstructured script. Figure 3 summarizes the development pipeline used by the project team. Figure 4 shows the repository layout that results from those stages.",
    )
    add_image(doc, "step00_dev_pipeline.png", 5.7, "Figure 3. Project development pipeline — stages of building RescueRoute Chennai.")
    add_image(doc, "step00_project_structure.png", 5.4, "Figure 4. Repository structure snapshot (implementation artifacts).")
    add_para(doc, "Development step summary:", bold=True, align="left", first_line=False)
    add_bullets(doc, [
        "Collect Chennai hospital and street context from OpenStreetMap (ODbL) and normalize a metro directory.",
        "Build the 36-node mission graph and the directed street atlas used for visual shortest paths.",
        "Train the Random Forest travel-time model on synthetic Chennai-calibrated data; export JSON inference artifacts.",
        "Implement A*/Dijkstra planning, hospital assignment, dispatch, GPS simulation and replanning.",
        "Build the Leaflet operator console (Dispatch, Hospital board, Directory, Algorithms & ML, AWS views).",
        "Add the local Python server with SQLite shared demo state for classroom demonstration.",
        "Write automated tests and verify the pickup-to-hospital dispatch storyboard.",
        "Author the AWS SAM template so the same logic can be deployed after local acceptance.",
        "Capture coloured screenshots and assemble this academic report.",
    ])
    page_break(doc)

    add_heading_bw(doc, "9.2 Part B — Step-wise Project Execution Screenshots", 2)
    add_para(
        doc,
        "The following numbered screenshots show how an operator uses the completed system. They are intended for viva demonstration: each figure is one clear action in the journey from opening the console to inspecting algorithms and the planned AWS stack.",
    )
    add_table(
        doc,
        ["Step", "Operator action", "Figure"],
        [
            ["1", "Open Dispatch console (local server running)", "Fig. 5"],
            ["2", "Select pickup neighborhood (e.g., Thiruvanmiyur / N55)", "Fig. 6"],
            ["3", "Set emergency / care / ML traffic parameters", "Fig. 7"],
            ["4", "Find shortest route — map shows pickup→hospital path", "Fig. 8"],
            ["5", "Review suggested hospitals ranked by travel time", "Fig. 9"],
            ["6", "Dispatch ambulance — Active Journey starts at pickup", "Fig. 10"],
            ["7", "Observe map path / GPS progress / arrival", "Fig. 11"],
            ["8", "Open Hospital board (capacity / accepting status)", "Fig. 12"],
            ["9", "Browse City directory (868 mapped hospitals)", "Fig. 13"],
            ["10", "Compare A*, Dijkstra, BFS on Algorithms & ML", "Fig. 14"],
            ["11", "Review AWS architecture screen (planned deploy)", "Fig. 15"],
        ],
        [1.5, 10.5, 2.5],
    )

    add_heading_bw(doc, "9.2.1 Step 1 — Console loaded", 3)
    add_para(doc, "The Dispatch console opens with fleet statistics (available ambulances) and the pickup-to-hospital storyboard. This is the starting screen after py local_server.py.", first_line=False)
    add_image(doc, "step01_console_loaded.png", 5.5, "Figure 5. Step 1 — Emergency dispatch console loaded (4/4 ambulances available).")

    add_heading_bw(doc, "9.2.2 Step 2 — Pickup selected", 3)
    add_para(doc, "The operator selects a pickup neighborhood (example: N55 · Thiruvanmiyur) or clicks the map. Destination may remain Auto — nearest / fastest.", first_line=False)
    add_image(doc, "step02_pickup_selected.png", 5.5, "Figure 6. Step 2 — Pickup neighborhood selected (Thiruvanmiyur).")

    add_heading_bw(doc, "9.2.3 Step 3 — Parameters set", 3)
    add_para(doc, "Emergency type, care category, ICU need and traffic scenario (including Use ML traffic prediction) are confirmed before routing.", first_line=False)
    add_image(doc, "step03_parameters_set.png", 5.5, "Figure 7. Step 3 — Trip parameters and road-condition controls.")

    add_heading_bw(doc, "9.2.4 Step 4 — Route calculated", 3)
    add_para(doc, "Find shortest way / Find shortest route computes the traffic-aware path. The map shows pickup (P), hospital (H), gold street path and cyan A* overlay.", first_line=False)
    add_image(doc, "step04_route_calculated.png", 5.5, "Figure 8. Step 4 — Pickup-to-hospital route drawn on the Chennai street map.")

    add_heading_bw(doc, "9.2.5 Step 5 — Hospital suggestions", 3)
    add_para(doc, "Suggested hospitals are ranked by predicted travel time. The selected hospital (example: Fortis Malar Hospital) is highlighted for dispatch.", first_line=False)
    add_image(doc, "step05_hospital_suggestions.png", 5.5, "Figure 9. Step 5 — Suggested hospitals ranked by traffic-aware travel time.")

    add_heading_bw(doc, "9.2.6 Step 6 — Dispatch / Active Journey", 3)
    add_para(doc, "Dispatch ambulance starts the trip at the patient pickup. Active Journey shows phase progress (At pickup → On scene → To hospital → Arrived).", first_line=False)
    add_image(doc, "step06_dispatch_active.png", 5.5, "Figure 10. Step 6 — Active Journey after dispatch from pickup.")

    add_heading_bw(doc, "9.2.7 Step 7 — Map / GPS progress", 3)
    add_para(doc, "The map updates as the simulated ambulance follows the path. ETA and distance remain visible for viva explanation.", first_line=False)
    add_image(doc, "step07_gps_progress.png", 5.5, "Figure 11. Step 7 — Map showing path progress / arrival state.")

    add_heading_bw(doc, "9.2.8 Step 8 — Hospital board", 3)
    add_para(doc, "Hospital board shows demo capacity, ICU and accepting status. Changes can trigger A* replanning.", first_line=False)
    add_image(doc, "step08_hospital_board.png", 5.5, "Figure 12. Step 8 — Hospital operations board.")

    add_heading_bw(doc, "9.2.9 Step 9 — City directory", 3)
    add_para(doc, "City directory lists 868 mapped hospital records with search, profile filters and CSV download.", first_line=False)
    add_image(doc, "step09_city_directory.png", 5.5, "Figure 13. Step 9 — Chennai hospital atlas (city directory).")

    add_heading_bw(doc, "9.2.10 Step 10 — Algorithms & ML", 3)
    add_para(doc, "Algorithms & ML compares A*, Dijkstra, BFS and shortest-distance on the same endpoints and summarizes Random Forest training.", first_line=False)
    add_image(doc, "step10_algorithms_ml.png", 5.5, "Figure 14. Step 10 — Algorithm comparison lab.")

    add_heading_bw(doc, "9.2.11 Step 11 — AWS architecture", 3)
    add_para(doc, "AWS architecture screen explains the planned serverless stack (S3/CloudFront, Cognito, API Gateway, Lambda, DynamoDB, SNS, etc.). Cloud deploy is the next stage after local verification.", first_line=False)
    add_image(doc, "step11_aws_architecture.png", 5.5, "Figure 15. Step 11 — AWS deployment & demonstration screen.")

    add_heading_bw(doc, "9.3 Screenshot Interpretation Notes", 2)
    add_para(
        doc,
        "All execution screenshots were captured in colour (light theme). Report body text remains black Times New Roman. Labels, path overlays and step numbers remain the primary evidence for viva. If the UI changes before final binding, regenerate this chapter with scripts/capture_step_screenshots.js (or manual capture) and rebuild the DOCX.",
    )
    page_break(doc)

    # ========== 10 GRAPHS ==========
    add_heading_bw(doc, "10. GRAPHS", 1)
    add_para(
        doc,
        "This chapter presents quantitative graphs derived from the machine-learning evaluation pipeline that supports RescueRoute Chennai. The graphs are simple coloured bar charts for print clarity. They answer three examiner questions: (1) Does the learned model improve upon naive speed assumptions? (2) Does it improve upon a handcrafted traffic rule? (3) Which features drive predictions? All numbers refer to the chronological synthetic holdout (38 dates) and must be interpreted within that regime.",
    )
    add_heading_bw(doc, "10.1 Model Error Comparison", 2)
    add_para(
        doc,
        "Table 10.1 and Figures 16–17 summarize holdout performance of the travel-time models. Mean Absolute Error (MAE) measures typical minute-level mistake magnitude and is easy to explain in viva. Root Mean Squared Error (RMSE) penalizes larger mistakes more heavily. The coefficient of determination (R²) summarizes explained variance relative to predicting the holdout mean. Random Forest clearly dominates the fixed-speed baseline and improves on the handcrafted traffic rule. These results validate the learning pipeline inside the synthetic regime; they are not field accuracy claims for live Chennai traffic.",
    )
    add_para(
        doc,
        "The fixed-speed baseline performs poorly because it ignores hour-of-day and rain. The traffic-rule baseline captures some of those effects with explicit formulas and therefore achieves a respectable R², yet Random Forest still reduces MAE by roughly half relative to that rule. This gap justifies shipping the exported forest for inference rather than relying only on static rules when the ML toggle is enabled.",
    )
    add_table(
        doc,
        ["Model", "MAE (min)", "RMSE (min)", "R²"],
        [
            ["Random Forest", "0.526", "0.765", "0.995"],
            ["Traffic rule baseline", "1.241", "1.818", "0.972"],
            ["Fixed-speed baseline", "9.741", "12.590", "−0.363"],
        ],
        [5, 3.5, 3.5, 3],
    )
    add_image(doc, "fig_model_mae.png", 5.4, "Figure 16. Holdout mean absolute error by model.")
    add_image(doc, "fig_model_r2.png", 5.4, "Figure 17. Holdout R-squared by model.")
    add_heading_bw(doc, "10.2 Feature Importance", 2)
    add_para(
        doc,
        "Figure 18 shows that congestion and rain dominate learned importance, followed by event shock and cyclic hour encodings. This ordering is consistent with the generator’s design, which emphasizes peak-period congestion and monsoon effects. Distance and free-flow speed remain relevant but secondary because many edges share similar corridor classes; the model therefore leans on temporal and weather context to differentiate minutes.",
    )
    add_image(doc, "fig_feature_importance.png", 5.5, "Figure 18. Random Forest feature importance.")
    add_heading_bw(doc, "10.3 Algorithmic Verification Summary", 2)
    add_para(
        doc,
        "Automated tests include thousands of A* versus Dijkstra comparisons on shared snapshots and Floyd–Warshall checks for cost consistency. These tests support the claim that the mission planner’s A* costs agree with classical optimal references under the modeled graph. Runtime columns in the UI are illustrative single-run timings and are not presented as asymptotic benchmarks. When presenting graphs in the viva, students should keep algorithm verification and ML evaluation separate: algorithm tests prove optimality on the modeled graph; ML graphs prove relative error reduction on synthetic travel times.",
    )
    add_heading_bw(doc, "10.4 Interpretation Guidance for Examiners", 2)
    add_para(
        doc,
        "If an examiner asks whether RescueRoute Chennai “predicts Chennai traffic accurately,” the correct answer is that the current metrics characterize the synthetic generator under a temporal split, and that the software architecture is ready to accept a recalibrated model once real probe data are available. If an examiner asks whether graphs prove A* correctness, the answer is no: A* correctness is established by oracle comparisons in the test suite, while the graphs characterize travel-time regression quality.",
    )
    page_break(doc)

    # ========== 11 CONCLUSION ==========
    add_heading_bw(doc, "11. CONCLUSION", 1)
    add_para(
        doc,
        "RescueRoute Chennai demonstrates a complete educational pipeline for emergency route optimization in a Chennai setting. The system joins an OSM hospital atlas, A*-based assignment, Random Forest travel-time estimation, interactive street visualization and a documented AWS serverless deployment blueprint. The demonstration storyboard used for evaluation is deliberately simple: select a pickup, compute a traffic-aware path to a feasible hospital, dispatch from that pickup and observe simulated progress until arrival.",
    )
    add_para(
        doc,
        "Relative to the problem statement stated in Section 5, the project achieves (i) metro-scale hospital discovery, (ii) multi-algorithm mission planning with Dijkstra as oracle, (iii) ML-assisted travel-time estimation with exported inference artifacts, (iv) operator controls for incidents and hospital unavailability, and (v) local executability with a concrete AWS SAM path for the next stage. The literature gaps concerning integration—rather than invention of a new shortest-path theorem—are addressed by packaging algorithms, data, interface and cloud design into one reproducible repository.",
    )
    add_para(
        doc,
        "Technically, the dual-layer routing design is an important conclusion: the 36-node A* graph remains the auditable mission model, while the directed street Dijkstra layer supplies mapped geometry for explanation and ETA context. Confusing the two layers would either overclaim geometric fidelity or under-explain why the operator map looks like real Chennai corridors. Keeping both, with explicit approximate connectors, preserves honesty and usefulness.",
    )
    add_para(
        doc,
        "Within the declared limitations (demo capacity, simulated GPS, synthetic ML holdout), the work is suitable for academic evaluation and live demonstration. The immediate next milestone is AWS deployment using the SAM template, followed by authenticated operator trials and optional Amazon Location enablement under budget control. Until that deployment is completed, claims about cloud availability should be limited to architecture readiness rather than production hosting.",
    )
    page_break(doc)

    # ========== 12 FUTURE WORK ==========
    add_heading_bw(doc, "12. FUTURE WORK", 1)
    add_para(
        doc,
        "Future development should move from educational completeness toward operational realism, without discarding the clarity of the present architecture. The items below are ordered from near-term deployment tasks to longer research directions.",
    )
    add_heading_bw(doc, "12.1 Near-Term: AWS Deployment and Evidence Pack", 2)
    add_para(
        doc,
        "The immediate next step is to deploy the SAM stack to an activated AWS account, create a Cognito operator user, publish the frontend to S3/CloudFront and archive stack outputs. Screenshots of signed-in dispatch, CloudWatch dashboards and Budgets thresholds should be appended to this report or to a viva evidence folder. Amazon Location should remain disabled until matrix cost implications are understood and approved.",
    )
    add_heading_bw(doc, "12.2 Data Realism", 2)
    add_para(
        doc,
        "Authenticated live bed/ICU feeds from partner hospitals, under formal data agreements, would replace demonstration capacity profiles. Separately, calibrating the traffic model on real Chennai probe or signal data would convert the current synthetic holdout story into a measured accuracy story, complete with confidence intervals and seasonal drift monitoring.",
    )
    add_heading_bw(doc, "12.3 Algorithmic Scale-Up", 2)
    add_para(
        doc,
        "Replacing the 36-node mission graph with city-scale contracted networks while preserving interactive latency is a major engineering task. At that scale, evaluating D* Lite or similar incremental replanners becomes worthwhile. Extending from single-mission assignment to multi-ambulance optimization under simultaneous incidents would also align the system more closely with real dispatch floors.",
    )
    add_heading_bw(doc, "12.4 Clients, Cost Controls and Human Factors", 2)
    add_bullets(doc, [
        "Build a mobile field client with offline maps and role separation between dispatcher and paramedic.",
        "Add cost guards and caching around Amazon Location matrix calls for directory-scale comparisons.",
        "Conduct a structured usability study with emergency-operations volunteers, measuring time-to-decision and error rates.",
        "Explore privacy-preserving logging so that exact patient pickup coordinates are retained only for the mission lifetime.",
    ])
    page_break(doc)

    # ========== 13 REFERENCES ==========
    add_heading_bw(doc, "13. REFERENCES", 1)
    add_para(
        doc,
        "The following references support the algorithms, data sources, machine-learning toolchain and cloud services used in RescueRoute Chennai. Online documentation URLs are current as of the project year 2025–2026; students should re-verify links before final binding if required by the department.",
        first_line=False,
    )
    refs = [
        "[1] E. W. Dijkstra, “A note on two problems in connexion with graphs,” Numerische Mathematik, vol. 1, pp. 269–271, 1959.",
        "[2] P. E. Hart, N. J. Nilsson and B. Raphael, “A formal basis for the heuristic determination of minimum cost paths,” IEEE Transactions on Systems Science and Cybernetics, vol. 4, no. 2, pp. 100–107, 1968.",
        "[3] S. Koenig and M. Likhachev, “D* Lite,” Proceedings of AAAI, 2002.",
        "[4] OpenStreetMap contributors, OpenStreetMap database, Open Database License (ODbL) 1.0. https://www.openstreetmap.org/copyright",
        "[5] F. Pedregosa et al., “Scikit-learn: Machine Learning in Python,” Journal of Machine Learning Research, vol. 12, pp. 2825–2830, 2011.",
        "[6] Amazon Web Services, “AWS Serverless Application Model (SAM) Developer Guide.” https://docs.aws.amazon.com/serverless-application-model/",
        "[7] Amazon Web Services, “Amazon DynamoDB Developer Guide — Condition Expressions.”",
        "[8] Amazon Web Services, “Amazon API Gateway — HTTP API JWT authorizers.”",
        "[9] Amazon Web Services, “Amazon Location Service API Reference — CalculateRouteMatrix.”",
        "[10] Amazon Web Services, “Amazon CloudFront — Restrict access to an Amazon S3 origin with OAC.”",
        "[11] Leaflet.js documentation. https://leafletjs.com/",
        "[12] Amazon Web Services, “Amazon Cognito Developer Guide.”",
        "[13] Amazon Web Services, “AWS Lambda Developer Guide” and “AWS X-Ray Developer Guide.”",
        "[14] Amazon Web Services, “Amazon Simple Notification Service (SNS) Developer Guide.”",
        "[15] Amazon Web Services, “AWS Budgets User Guide.”",
        "[16] Amazon Web Services, “Amazon SageMaker Developer Guide.”",
        "[17] L. Breiman, “Random Forests,” Machine Learning, vol. 45, pp. 5–32, 2001.",
        "[18] R. Church and C. ReVelle, “The maximal covering location problem,” Papers of the Regional Science Association, vol. 32, pp. 101–118, 1974.",
        "[19] RescueRoute Chennai repository documentation: README.md, docs/PROJECT_DESIGN.md, docs/AWS_DEPLOYMENT.md, docs/DATA_CARD.md, docs/HOW_TO_RUN.md (project artifacts, 2026).",
        "[20] World Wide Web Consortium (W3C), “Geolocation API,” for browser location pickup selection.",
        "[21] B. Garg, RescueRoute_Chennai source repository. https://github.com/Bhavi123-hacker/RescueRoute_Chennai",
    ]
    for r in refs:
        add_para(doc, r, align="left", first_line=False, space_after=6)
    page_break(doc)

    # ========== APPENDIX A ==========
    add_heading_bw(doc, "APPENDIX A — AWS SERVICES USED", 1)
    add_para(
        doc,
        "The following Amazon Web Services are defined in the project’s SAM template and supporting scripts. Local mode does not require them. They are the planned production/demo hosting stack after account deployment.",
        first_line=False,
    )
    add_table(
        doc,
        ["S. No.", "AWS Service", "Role in RescueRoute Chennai"],
        [
            ["1", "Amazon Cognito", "Operator user pool and app client; ID tokens for API authorization"],
            ["2", "Amazon API Gateway (HTTP API)", "REST endpoints with JWT authorizer, CORS and throttling"],
            ["3", "Amazon API Gateway (WebSocket)", "Live mission/state event fan-out to dashboards"],
            ["4", "AWS Lambda", "Planning, street-plan, ML inference, mutations, exports, optional Location calls"],
            ["5", "AWS X-Ray", "Distributed tracing for Lambda diagnostics"],
            ["6", "Amazon DynamoDB", "Shared WORLD/DEMO state with conditional revision writes; connection registry"],
            ["7", "Amazon S3", "Private frontend origin; private reports, datasets, model JSON, city catalog"],
            ["8", "Amazon CloudFront", "HTTPS CDN for the dashboard with Origin Access Control"],
            ["9", "Amazon SNS", "Optional email alerts on dispatch, reroute and arrival"],
            ["10", "Amazon CloudWatch", "Logs, latency/error metrics and alarms"],
            ["11", "AWS Budgets", "Cost monitoring for the stack"],
            ["12", "AWS IAM", "Least-privilege roles for Lambda, SageMaker and Location"],
            ["13", "Amazon Location Service (optional)", "Maps, Places, CalculateRouteMatrix / CalculateRoutes"],
            ["14", "Amazon SageMaker (role + script)", "Optional cloud retraining entry point"],
            ["15", "AWS SAM / CloudFormation", "Infrastructure as code packaging and deployment"],
        ],
        [1.5, 4.5, 9],
    )
    add_para(
        doc,
        "Security notes for deployment: browser map keys must remain restricted; long-term AWS access keys must never be embedded in frontend source; exact pickup coordinates should be sent to Amazon Location only on explicit live preview requests.",
    )
    page_break(doc)

    # ========== APPENDIX B ==========
    add_heading_bw(doc, "APPENDIX B — LOCAL EXECUTION AND PLANNED AWS DEPLOY", 1)
    add_heading_bw(doc, "B.1 Local execution (completed for this report)", 2)
    add_para(doc, "Prerequisites: Python 3.12 or newer on Microsoft Windows.", first_line=False)
    add_para(doc, "cd /d E:\\RescueRoute_Chennai", align="left", first_line=False, size=11)
    add_para(doc, "py local_server.py", align="left", first_line=False, size=11)
    add_para(doc, "Open http://localhost:8020 and press Ctrl+F5.", first_line=False)
    add_para(doc, "Optional tests:", bold=True, align="left", first_line=False)
    add_para(doc, "python -m unittest discover -s tests -v", align="left", first_line=False, size=11)
    add_heading_bw(doc, "B.2 Planned AWS deployment (next stage)", 2)
    add_para(
        doc,
        "After the local demonstration is accepted, deploy using an activated AWS account and a configured CLI identity. Do not paste secret keys into chat logs or commit credentials to the repository.",
    )
    add_para(doc, "aws configure", align="left", first_line=False, size=11)
    add_para(doc, "aws sts get-caller-identity", align="left", first_line=False, size=11)
    add_para(doc, "sam build", align="left", first_line=False, size=11)
    add_para(doc, "sam deploy --guided --stack-name rescueroute-chennai --region <REGION>", align="left", first_line=False, size=11)
    add_para(doc, "python -m pip install -r requirements-aws.txt", align="left", first_line=False, size=11)
    add_para(doc, "python scripts/publish_frontend.py --stack rescueroute-chennai --region <REGION>", align="left", first_line=False, size=11)
    add_para(doc, "python scripts/setup_user.py --stack rescueroute-chennai --region <REGION> --username dispatcher", align="left", first_line=False, size=11)
    add_para(
        doc,
        "Initially keep EnableLocation=false. After basic stack health is verified, optionally redeploy with EnableLocation=true and republish the frontend. Set AlertEmail to enable SNS mission alerts. Record the CloudFront URL, Cognito user creation and a successful signed-in dispatch as deployment evidence for the final submission.",
    )
    doc.add_paragraph()
    add_para(doc, "— End of Report —", bold=True, align="center", first_line=False)
    add_para(
        doc,
        "Student: Bhavy Garg · Register No.: 24BAI1088 · GitHub: https://github.com/Bhavi123-hacker/RescueRoute_Chennai",
        italic=True, size=10, align="center", first_line=False,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(OUT)
        print("Wrote", OUT, "bytes", OUT.stat().st_size)
    except PermissionError:
        doc.save(OUT_FALLBACK)
        print("LOCKED:", OUT)
        print("Wrote", OUT_FALLBACK, "bytes", OUT_FALLBACK.stat().st_size)

if __name__ == "__main__":
    build()
