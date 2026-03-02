"""Report endpoints — trends, team comparison, compliance, CSV/PDF export."""

import csv
import io
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, User
from dependencies import get_current_user, get_call_scope_filter, require_supervisor_or_admin
from models.schemas import TrendsResponse, TeamComparisonResponse, ComplianceResponse
from services.reports import (
    compute_trends, compute_team_comparison, compute_compliance, get_calls_for_export,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _parse_date(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {d}. Use YYYY-MM-DD.")


@router.get("/trends", response_model=TrendsResponse)
def trends_report(
    period: str = Query("weekly", pattern="^(weekly|monthly)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    worker_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    return compute_trends(db, scope_filter, current_user, period, sd, ed, worker_id)


@router.get("/team-comparison", response_model=TeamComparisonResponse)
def team_comparison_report(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    return compute_team_comparison(db, scope_filter, current_user, sd, ed)


@router.get("/compliance", response_model=ComplianceResponse)
def compliance_report(
    threshold: float = Query(7.0, ge=0, le=10),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    return compute_compliance(db, scope_filter, current_user, threshold, sd, ed)


@router.get("/export/csv")
def export_csv(
    report_type: str = Query("calls", pattern="^(calls|trends|compliance)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "calls":
        rows = get_calls_for_export(db, scope_filter, sd, ed)
        if rows:
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow(row.values())
        else:
            writer.writerow(["No data"])
    elif report_type == "trends":
        data = compute_trends(db, scope_filter, current_user, "weekly", sd, ed)
        writer.writerow(["start_date", "end_date", "call_count", "avg_sentiment",
                         "avg_rating", "avg_empathy", "avg_professionalism",
                         "avg_resolution", "avg_compliance", "flagged_count"])
        for b in data["buckets"]:
            writer.writerow([b["start_date"], b["end_date"], b["call_count"],
                             b["avg_sentiment"], b["avg_rating"], b["avg_empathy"],
                             b["avg_professionalism"], b["avg_resolution"],
                             b["avg_compliance"], b["flagged_count"]])
    elif report_type == "compliance":
        data = compute_compliance(db, scope_filter, current_user, 7.0, sd, ed)
        sc = data["score_compliance"]
        rc = data["review_completion"]
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Score Threshold", sc["threshold"]])
        writer.writerow(["Total Calls with Scores", sc["total_calls"]])
        writer.writerow(["Passing Calls", sc["passing_calls"]])
        writer.writerow(["Passing %", sc["passing_pct"]])
        writer.writerow(["Reviewed Count", rc["reviewed_count"]])
        writer.writerow(["Review %", rc["review_pct"]])
        writer.writerow(["Avg Days to Review", rc["avg_days_to_review"]])
        writer.writerow(["Unreviewed Backlog", rc["unreviewed_backlog"]])

    output.seek(0)
    today = datetime.now().strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report-{report_type}-{today}.csv"},
    )


@router.get("/export/pdf")
def export_pdf(
    report_type: str = Query("calls", pattern="^(calls|trends|compliance)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)

    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph(f"Call Monitor — {report_type.title()} Report", styles["Title"]))
    date_range = f"{sd or 'All time'} to {ed or 'today'}"
    elements.append(Paragraph(f"Date range: {date_range} | Generated by: {current_user.name}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    if report_type == "calls":
        rows = get_calls_for_export(db, scope_filter, sd, ed)
        if rows:
            headers = ["Title", "Date", "Worker", "Sentiment", "Rating", "Review"]
            table_data = [headers]
            for r in rows:
                table_data.append([
                    r["title"][:30], r["date"], r["worker"],
                    str(r["sentiment"]), str(r["rating"]), r["review_status"],
                ])
        else:
            table_data = [["No data"]]
    elif report_type == "trends":
        data = compute_trends(db, scope_filter, current_user, "weekly", sd, ed)
        headers = ["Period", "Calls", "Avg Sentiment", "Avg Rating", "Flagged"]
        table_data = [headers]
        for b in data["buckets"]:
            table_data.append([
                f"{b['start_date']} - {b['end_date']}", str(b["call_count"]),
                str(b["avg_sentiment"] or "—"), str(b["avg_rating"] or "—"),
                str(b["flagged_count"]),
            ])
    elif report_type == "compliance":
        data = compute_compliance(db, scope_filter, current_user, 7.0, sd, ed)
        sc = data["score_compliance"]
        rc = data["review_completion"]
        table_data = [
            ["Metric", "Value"],
            ["Score Threshold", str(sc["threshold"])],
            ["Total Calls", str(sc["total_calls"])],
            ["Passing", f"{sc['passing_calls']} ({sc['passing_pct']}%)"],
            ["Reviewed", f"{rc['reviewed_count']} ({rc['review_pct']}%)"],
            ["Avg Days to Review", str(rc["avg_days_to_review"] or "—")],
            ["Unreviewed Backlog", str(rc["unreviewed_backlog"])],
        ]

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4338ca")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    footer = datetime.now().strftime("Generated %Y-%m-%d %H:%M UTC")
    elements.append(Paragraph(footer, styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    today = datetime.now().strftime("%Y-%m-%d")
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{report_type}-{today}.pdf"},
    )
