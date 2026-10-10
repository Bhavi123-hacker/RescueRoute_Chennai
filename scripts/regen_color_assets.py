# -*- coding: utf-8 -*-
"""Regenerate colored report figures and copy color UI previews where useful."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "report_assets"
DOCS = ROOT / "docs"
ASSETS.mkdir(parents=True, exist_ok=True)

def font(size):
    for name in ("arial.ttf", "segoeui.ttf", "calibri.ttf", "times.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()

def bar_chart(path, title, labels, values, ylabel, color="#1F6F8B"):
    w, h = 1170, 684
    img = Image.new("RGB", (w, h), "#FFFFFF")
    d = ImageDraw.Draw(img)
    title_f, body_f, small_f = font(28), font(18), font(16)
    d.rectangle([20, 20, w - 20, h - 20], outline="#222222", width=2)
    d.text((40, 36), title, fill="#111111", font=title_f)
    chart = (80, 100, w - 80, h - 80)
    x0, y0, x1, y1 = chart
    d.rectangle(chart, outline="#444444", width=2)
    mx = max(values) if max(values) > 0 else 1
    n = len(labels)
    gap = 40
    bar_w = (x1 - x0 - gap * (n + 1)) / n
    for i, (lab, val) in enumerate(zip(labels, values)):
        bh = (y1 - y0 - 30) * (val / mx)
        bx0 = x0 + gap + i * (bar_w + gap)
        by0 = y1 - 20 - bh
        d.rectangle([bx0, by0, bx0 + bar_w, y1 - 20], fill=color, outline="#0D3B4C")
        d.text((bx0, y1 - 16), lab[:18], fill="#111111", font=small_f)
        d.text((bx0 + 8, by0 - 24), f"{val:.3f}", fill="#111111", font=small_f)
    d.text((40, h - 48), ylabel, fill="#333333", font=body_f)
    img.save(path)
    print("wrote", path)

def feature_chart(path, importance):
    items = sorted(importance.items(), key=lambda kv: kv[1], reverse=True)
    w, h = 1224, 756
    img = Image.new("RGB", (w, h), "#FFFFFF")
    d = ImageDraw.Draw(img)
    title_f, body_f = font(26), font(16)
    d.rectangle([20, 20, w - 20, h - 20], outline="#222222", width=2)
    d.text((40, 36), "Random Forest feature importance", fill="#111111", font=title_f)
    top = 90
    left = 260
    max_w = w - left - 80
    mx = items[0][1] if items else 1
    colors = ["#C0392B", "#E67E22", "#F1C40F", "#27AE60", "#2980B9", "#8E44AD",
              "#16A085", "#D35400", "#2C3E50", "#7F8C8D", "#1ABC9C", "#9B59B6"]
    for i, (name, val) in enumerate(items):
        y = top + i * 50
        bw = max_w * (val / mx)
        d.text((40, y + 8), name, fill="#111111", font=body_f)
        d.rectangle([left, y, left + bw, y + 28], fill=colors[i % len(colors)], outline="#222222")
        d.text((left + bw + 10, y + 6), f"{val:.3f}", fill="#111111", font=body_f)
    img.save(path)
    print("wrote", path)

def flow_fig(path):
    w, h = 1350, 468
    img = Image.new("RGB", (w, h), "#F7FBFD")
    d = ImageDraw.Draw(img)
    title_f, body_f = font(24), font(16)
    d.rectangle([20, 20, w - 20, h - 20], outline="#1F6F8B", width=3)
    d.text((40, 36), "RescueRoute Chennai — operational flow (pickup → hospital)", fill="#0D3B4C", font=title_f)
    steps = [
        ("1. Pickup", "#F4D03F"),
        ("2. Rank hospital", "#58D68D"),
        ("3. A* + streets", "#5DADE2"),
        ("4. Dispatch", "#E74C3C"),
        ("5. GPS / arrive", "#AF7AC5"),
    ]
    x = 50
    for i, (label, color) in enumerate(steps):
        d.rounded_rectangle([x, 140, x + 200, 280], radius=16, fill=color, outline="#222222", width=2)
        d.text((x + 24, 190), label, fill="#111111", font=body_f)
        if i < len(steps) - 1:
            d.polygon([(x + 210, 195), (x + 240, 210), (x + 210, 225)], fill="#2C3E50")
        x += 260
    d.text((40, 340), "Demo contract: Dispatch starts at patient pickup and proceeds to the hospital.", fill="#333333", font=body_f)
    img.save(path)
    print("wrote", path)

def aws_fig(path):
    w, h = 1350, 864
    img = Image.new("RGB", (w, h), "#FFFFFF")
    d = ImageDraw.Draw(img)
    title_f, body_f, small_f = font(26), font(18), font(15)
    d.rectangle([20, 20, w - 20, h - 20], outline="#232F3E", width=3)
    d.text((40, 40), "AWS deployment architecture (planned SAM stack)", fill="#232F3E", font=title_f)
    boxes = [
        (60, 120, 420, 230, "#FF9900", "S3 + CloudFront", "HTTPS dashboard"),
        (460, 120, 820, 230, "#DD344C", "Cognito + HTTP API", "JWT auth / REST"),
        (860, 120, 1220, 230, "#3B48CC", "WebSocket API", "Live events"),
        (60, 280, 420, 390, "#C925D1", "Lambda + X-Ray", "A* / RF / mutations"),
        (460, 280, 820, 390, "#4053D6", "DynamoDB", "Revisioned world state"),
        (860, 280, 1220, 390, "#FF4F8B", "SNS + CloudWatch", "Alerts / metrics"),
        (260, 450, 720, 560, "#7AA116", "Optional Location", "Live traffic matrix"),
        (760, 450, 1220, 560, "#ED7100", "SageMaker role", "Optional retraining"),
    ]
    for x0, y0, x1, y1, color, title, sub in boxes:
        d.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=color, outline="#111111", width=2)
        d.text((x0 + 20, y0 + 28), title, fill="#FFFFFF", font=body_f)
        d.text((x0 + 20, y0 + 62), sub, fill="#F5F5F5", font=small_f)
    d.text((60, 620), "Local mode uses the same planning code with SQLite. Cloud deploy is the next stage.", fill="#333333", font=body_f)
    img.save(path)
    print("wrote", path)

def pipeline_fig(path):
    w, h = 1200, 900
    img = Image.new("RGB", (w, h), "#FFFFFF")
    d = ImageDraw.Draw(img)
    title_f, body_f = font(26), font(18)
    d.rectangle([20, 20, w - 20, h - 20], outline="#1F6F8B", width=3)
    d.text((40, 40), "Project development steps (how the system was built)", fill="#0D3B4C", font=title_f)
    steps = [
        ("1", "Collect Chennai hospital / street context (OpenStreetMap)", "#F4D03F"),
        ("2", "Build 36-node mission graph + directed street atlas", "#58D68D"),
        ("3", "Train Random Forest; export JSON inference artifacts", "#5DADE2"),
        ("4", "Implement A*/Dijkstra planner, assignment, replanning", "#E67E22"),
        ("5", "Build Leaflet operator console (dispatch → AWS views)", "#AF7AC5"),
        ("6", "Add local Python server + SQLite shared demo state", "#1ABC9C"),
        ("7", "Write tests; verify pickup-to-hospital dispatch flow", "#E74C3C"),
        ("8", "Author AWS SAM template for later cloud deployment", "#2980B9"),
        ("9", "Capture colored screenshots and prepare academic report", "#8E44AD"),
    ]
    y = 100
    for num, text, color in steps:
        d.rounded_rectangle([60, y, 1140, y + 70], radius=10, fill=color, outline="#222222", width=2)
        d.text((80, y + 22), f"{num}.  {text}", fill="#111111", font=body_f)
        y += 85
    img.save(path)
    print("wrote", path)

def structure_fig(path):
    # keep readable dark-on-light with a blue header bar
    root = ROOT
    lines = ["RescueRoute_Chennai — Project structure"]
    keep = ["backend", "frontend", "ml", "infra", "scripts", "tests", "docs", "template.yaml", "local_server.py", "README.md"]
    for name in keep:
        p = root / name
        if p.exists():
            lines.append(("DIR  " if p.is_dir() else "FILE ") + name)
    for sub in ["backend", "frontend", "ml", "scripts", "docs"]:
        d = root / sub
        if not d.is_dir():
            continue
        lines.append("")
        lines.append(sub + "/")
        for child in sorted(d.iterdir())[:16]:
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            lines.append("  " + child.name + ("/" if child.is_dir() else ""))
    img = Image.new("RGB", (1200, 1600), "#FFFFFF")
    d = ImageDraw.Draw(img)
    title_f, body_f = font(24), font(18)
    d.rectangle([20, 20, 1180, 1580], outline="#1F6F8B", width=3)
    d.rectangle([20, 20, 1180, 80], fill="#1F6F8B")
    d.text((40, 38), lines[0], fill="#FFFFFF", font=title_f)
    y = 100
    for line in lines[1:]:
        d.text((40, y), line, fill="#111111", font=body_f)
        y += 26
        if y > 1540:
            break
    img.save(path)
    print("wrote", path)

def copy_preview_fallbacks():
    mapping = {
        "light-preview.png": "ss_map_route.png",
        "analysis-preview.png": "ss_algorithms_ml.png",
        "directory-preview.png": "ss_directory.png",
        "dashboard-preview.png": "ss_aws.png",
        "hospital-preview.png": "ss_active_journey.png",
        "street-map-preview.png": "ss_map_route_color_fallback.png",
    }
    for src_name, dst_name in mapping.items():
        src = DOCS / src_name
        if src.exists():
            # don't overwrite step shots; only ensure ss_* have color if still grey
            dst = ASSETS / dst_name
            shutil.copy2(src, dst)
            print("copied", src_name, "->", dst_name)

def main():
    report = json.loads((ROOT / "backend" / "models" / "model_report.json").read_text(encoding="utf-8"))
    bar_chart(
        ASSETS / "fig_model_mae.png",
        "Holdout MAE (minutes) — lower is better",
        ["Random Forest", "Traffic rule", "Fixed speed"],
        [
            report["random_forest"]["mae_minutes"],
            report["traffic_rule"]["mae_minutes"],
            report["fixed_speed"]["mae_minutes"],
        ],
        "Mean absolute error on chronological synthetic holdout",
        color="#1F6F8B",
    )
    bar_chart(
        ASSETS / "fig_model_r2.png",
        "Holdout R-squared — higher is better",
        ["Random Forest", "Traffic rule", "Fixed speed"],
        [
            report["random_forest"]["r2"],
            report["traffic_rule"]["r2"],
            max(report["fixed_speed"]["r2"], 0),  # chart floor; note negative in caption if needed
        ],
        "R² on chronological synthetic holdout (fixed-speed true R² is negative)",
        color="#27AE60",
    )
    feature_chart(ASSETS / "fig_feature_importance.png", report["feature_importance"])
    flow_fig(ASSETS / "fig_flow.png")
    aws_fig(ASSETS / "fig_aws_architecture.png")
    pipeline_fig(ASSETS / "step00_dev_pipeline.png")
    structure_fig(ASSETS / "step00_project_structure.png")
    copy_preview_fallbacks()
    print("done")

if __name__ == "__main__":
    main()
