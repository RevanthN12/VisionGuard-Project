"""
report_generator.py — Vision Guard Enhanced Report and Analytics Module
Generates detailed session CSV reports, executive text summaries, and styled PDF analytics reports 
with Camera 1 vs Camera 2 multi-source breakdowns.
"""

import os
import csv
import datetime
import config
import database

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_csv(filepath: str = None, video_source: str = None) -> str:
    """
    Exports monitoring_history to CSV with video source (Camera 1 / Camera 2) tagging.
    Returns the generated CSV filepath.
    """
    if filepath is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        cam_suffix = f"_{video_source.replace(' ', '_')}" if video_source else ""
        filepath = os.path.join(config.REPORTS_DIR, f"vision_guard_analytics{cam_suffix}_{ts}.csv")

    rows = database.get_recent_history(limit=10000, video_source=video_source)
    if not rows:
        rows = []

    fieldnames = ["timestamp", "video_source", "person_count", "density_score", "movement_speed", "risk_score", "risk_level"]

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return filepath


def generate_summary_text(stats: dict, cam1_stats: dict = None, cam2_stats: dict = None) -> str:
    """Return a styled plain-text executive summary string divided by Camera 1 & Camera 2."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 60,
        "  VISION GUARD — CROWD MONITORING & STAMPEDE RISK REPORT",
        f"  Generated: {now}",
        "=" * 60,
    ]

    if cam1_stats:
        lines.extend([
            "  CAMERA 1 METRICS:",
            f"    Frames Analyzed      : {cam1_stats.get('total_frames', 0)}",
            f"    Peak Crowd Count     : {cam1_stats.get('max_people', 0)} persons",
            f"    Average Crowd Density: {cam1_stats.get('avg_people', 0)} persons/frame",
            f"    Peak Risk Score      : {cam1_stats.get('max_risk', 0)}%",
            f"    Incidents Recorded   : {cam1_stats.get('total_incidents', 0)}",
            "-" * 60,
        ])

    if cam2_stats:
        lines.extend([
            "  CAMERA 2 METRICS:",
            f"    Frames Analyzed      : {cam2_stats.get('total_frames', 0)}",
            f"    Peak Crowd Count     : {cam2_stats.get('max_people', 0)} persons",
            f"    Average Crowd Density: {cam2_stats.get('avg_people', 0)} persons/frame",
            f"    Peak Risk Score      : {cam2_stats.get('max_risk', 0)}%",
            f"    Incidents Recorded   : {cam2_stats.get('total_incidents', 0)}",
            "-" * 60,
        ])

    lines.extend([
        "  COMBINED SYSTEM METRICS:",
        f"    Total Frames Logged  : {stats.get('total_frames', 0)}",
        f"    Maximum Risk Score   : {stats.get('max_risk', 0)}%",
        f"    Total Incidents      : {stats.get('total_incidents', 0)}",
        f"    Total System Alerts  : {stats.get('total_alerts', 0)}",
        "=" * 60,
        "  STATUS ADVISORY:",
        f"  {get_risk_advisory(stats.get('max_risk', 0))}",
        "=" * 60,
    ])
    return "\n".join(lines)


def get_risk_advisory(max_risk_score: float) -> str:
    """Generates an executive safety advisory statement based on peak risk score."""
    if max_risk_score >= 85:
        return "CRITICAL EMERGENCY: High stampede risk detected. Immediate crowd dispersion mandated."
    elif max_risk_score >= 70:
        return "HIGH RISK: Severe crowd congestion observed. Deploy monitors and open auxiliary exits."
    elif max_risk_score >= 50:
        return "WARNING: Moderate crowd density building up. Monitor flow rates closely."
    elif max_risk_score >= 30:
        return "CAUTION: Minor crowd accumulation. Standard surveillance operational."
    else:
        return "SAFE: Crowd parameters remain within normal safety limits."


def generate_pdf(filepath: str = None, video_source: str = None) -> str | None:
    """
    Generates a professional PDF executive analytics report with Camera 1 vs Camera 2 breakdown.
    Returns the output PDF file path.
    """
    if filepath is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        cam_suffix = f"_{video_source.replace(' ', '_')}" if video_source else ""
        filepath = os.path.join(config.REPORTS_DIR, f"vision_guard_summary{cam_suffix}_{ts}.pdf")

    stats = database.get_session_stats(video_source=video_source)
    cam1_stats = database.get_session_stats(video_source="Camera 1")
    cam2_stats = database.get_session_stats(video_source="Camera 2")

    history = database.get_recent_history(limit=100, video_source=video_source)

    if not REPORTLAB_AVAILABLE:
        txt_path = filepath.replace(".pdf", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(generate_summary_text(stats, cam1_stats, cam2_stats))
        return txt_path

    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    PRIMARY_COLOR = colors.HexColor("#0f172a")
    SECONDARY_COLOR = colors.HexColor("#0284c7")
    TEXT_COLOR = colors.HexColor("#334155")

    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, leading=24, textColor=PRIMARY_COLOR, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=SECONDARY_COLOR, fontName='Helvetica-Bold')
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, leading=13, textColor=TEXT_COLOR)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, leading=16, textColor=PRIMARY_COLOR, fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=6)

    story = []

    # Header Banner
    story.append(Paragraph("<b>VISION GUARD — MULTI-CAMERA ANALYTICS REPORT</b>", title_style))
    story.append(Paragraph("Automated Stampede Risk & Camera Source Surveillance Assessment", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=SECONDARY_COLOR, spaceAfter=12))

    # Multi-Camera Executive Breakdown Table
    story.append(Paragraph("Multi-Camera Surveillance Metrics Breakdown", h2_style))
    multi_cam_table = [
        [
            Paragraph("<b>Metric</b>", subtitle_style),
            Paragraph("<b>Camera 1</b>", subtitle_style),
            Paragraph("<b>Camera 2</b>", subtitle_style),
            Paragraph("<b>Total System</b>", subtitle_style)
        ],
        [
            Paragraph("Frames Analyzed", body_style),
            Paragraph(str(cam1_stats.get('total_frames', 0)), body_style),
            Paragraph(str(cam2_stats.get('total_frames', 0)), body_style),
            Paragraph(str(stats.get('total_frames', 0)), body_style)
        ],
        [
            Paragraph("Peak Crowd Count", body_style),
            Paragraph(f"<b>{cam1_stats.get('max_people', 0)}</b>", body_style),
            Paragraph(f"<b>{cam2_stats.get('max_people', 0)}</b>", body_style),
            Paragraph(f"<b>{stats.get('max_people', 0)}</b>", body_style)
        ],
        [
            Paragraph("Average Crowd Count", body_style),
            Paragraph(f"{cam1_stats.get('avg_people', 0)}", body_style),
            Paragraph(f"{cam2_stats.get('avg_people', 0)}", body_style),
            Paragraph(f"{stats.get('avg_people', 0)}", body_style)
        ],
        [
            Paragraph("Peak Risk Score", body_style),
            Paragraph(f"<b>{cam1_stats.get('max_risk', 0)}%</b>", body_style),
            Paragraph(f"<b>{cam2_stats.get('max_risk', 0)}%</b>", body_style),
            Paragraph(f"<b>{stats.get('max_risk', 0)}%</b>", body_style)
        ],
        [
            Paragraph("Incidents Recorded", body_style),
            Paragraph(str(cam1_stats.get('total_incidents', 0)), body_style),
            Paragraph(str(cam2_stats.get('total_incidents', 0)), body_style),
            Paragraph(str(stats.get('total_incidents', 0)), body_style)
        ]
    ]

    t_multi = Table(multi_cam_table, colWidths=[150, 130, 130, 130])
    t_multi.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_multi)
    story.append(Spacer(1, 14))

    # Safety Advisory
    advisory = get_risk_advisory(stats.get('max_risk', 0))
    story.append(Paragraph("Executive Safety Assessment Advisory", h2_style))
    story.append(Paragraph(f"<b>Status:</b> {advisory}", body_style))
    story.append(Spacer(1, 14))

    # Surveillance Logs Table
    story.append(Paragraph("Recent Multi-Camera Surveillance Logs", h2_style))
    log_data = [[
        Paragraph("<b>Timestamp</b>", subtitle_style),
        Paragraph("<b>Source</b>", subtitle_style),
        Paragraph("<b>Count</b>", subtitle_style),
        Paragraph("<b>Density%</b>", subtitle_style),
        Paragraph("<b>Speed</b>", subtitle_style),
        Paragraph("<b>Risk%</b>", subtitle_style),
        Paragraph("<b>Level</b>", subtitle_style)
    ]]

    for r in history[:15]:
        log_data.append([
            Paragraph(str(r.get('timestamp', ''))[:19], body_style),
            Paragraph(str(r.get('video_source', 'Camera 1')), body_style),
            Paragraph(str(r.get('person_count', 0)), body_style),
            Paragraph(f"{r.get('density_score', 0):.1f}%", body_style),
            Paragraph(f"{r.get('movement_speed', 0):.1f}", body_style),
            Paragraph(f"{r.get('risk_score', 0):.1f}%", body_style),
            Paragraph(str(r.get('risk_level', 'SAFE')), body_style)
        ])

    t_log = Table(log_data, colWidths=[110, 80, 50, 60, 50, 55, 135])
    t_log.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_log)

    doc.build(story)
    return filepath
