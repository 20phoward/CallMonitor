# Phase 5: Reporting & Analytics — Design Document

## Goal
Add reporting and analytics capabilities so supervisors and admins can track worker performance trends, compare teams, monitor compliance, and export reports as CSV or PDF.

## Architecture
Backend-driven approach: new `/api/reports/` endpoints handle all aggregation and export generation. The frontend renders pre-computed data using Recharts. Role-based scoping reuses existing patterns (workers see own data, supervisors see team, admins see all). PDF generated server-side with ReportLab.

## API Endpoints

All endpoints require authentication and apply role-based scoping. Common query params: `start_date`, `end_date`.

### GET /api/reports/trends
Worker performance over time, bucketed by week or month.

**Query params:** `period=weekly|monthly`, `start_date`, `end_date`, `worker_id` (optional)

**Response:**
```json
{
  "period": "weekly",
  "buckets": [
    {
      "start_date": "2026-02-24",
      "end_date": "2026-03-02",
      "call_count": 12,
      "avg_sentiment": 0.45,
      "avg_rating": 7.8,
      "avg_empathy": 8.1,
      "avg_professionalism": 7.5,
      "avg_resolution": 7.2,
      "avg_compliance": 8.4,
      "flagged_count": 1
    }
  ],
  "workers": [
    {
      "worker_id": 5,
      "worker_name": "Jane Smith",
      "buckets": [...]
    }
  ]
}
```

- Top-level `buckets`: aggregate across all visible workers
- `workers`: per-worker breakdown (supervisors see team, admins see all, workers see only their own with no `workers` array)

### GET /api/reports/team-comparison
Side-by-side team metrics. Supervisors see their team's workers compared; admins see all teams compared. Workers do not have access.

**Query params:** `start_date`, `end_date`

**Response:**
```json
{
  "teams": [
    {
      "team_id": 1,
      "team_name": "Outreach",
      "call_count": 45,
      "avg_sentiment": 0.52,
      "avg_rating": 7.9,
      "flagged_pct": 4.4,
      "approved_pct": 82.2,
      "top_worker": "Jane Smith",
      "lowest_scorer": "John Doe"
    }
  ]
}
```

### GET /api/reports/compliance
Score threshold compliance and review completion rates.

**Query params:** `start_date`, `end_date`, `threshold` (default 7.0)

**Response:**
```json
{
  "score_compliance": {
    "threshold": 7.0,
    "total_calls": 120,
    "passing_calls": 98,
    "passing_pct": 81.7,
    "failing_workers": [
      {"worker_id": 3, "name": "John Doe", "avg_score": 5.8, "calls_below": 4}
    ]
  },
  "review_completion": {
    "total_completed_calls": 120,
    "reviewed_count": 95,
    "review_pct": 79.2,
    "avg_days_to_review": 1.3,
    "unreviewed_backlog": 25
  }
}
```

### GET /api/reports/export/csv
Streams a CSV file download.

**Query params:** `start_date`, `end_date`, `report_type=trends|team|compliance|calls`

- `calls` exports raw call list (title, date, duration, sentiment, scores, review status)
- Other types flatten their JSON endpoint data to CSV rows
- Uses Python built-in `csv` module

### GET /api/reports/export/pdf
Streams a formatted PDF report.

**Query params:** Same as CSV

- Generated with ReportLab
- Includes: header (title, date range, user), summary stats table, data table, footer with timestamp
- No charts in PDF (charts are web-only)

## Frontend

New `/reports` page accessible from navbar (all roles).

### Filter Bar
- Date range inputs with presets ("Last 7 days", "Last 30 days", "Last 90 days")
- Period toggle (weekly/monthly) for trends
- Export buttons (CSV, PDF) with report type dropdown

### Trends Chart
- Recharts LineChart: avg rating and avg sentiment over time buckets
- Toggle "Overall" vs "By Worker" (supervisors/admins only)
- Workers see only their own trend line

### Team Comparison (supervisors/admins only)
- Recharts BarChart comparing teams on avg rating, call volume, flagged %
- Supervisors: workers within their team compared
- Admins: teams compared

### Compliance Summary
- Two stat cards: score compliance % and review completion %
- Table of workers below threshold

## Dependencies

**New:** `reportlab` (PDF generation)

## Files

**Create:**
- `backend/routers/reports.py` — 5 report endpoints
- `backend/services/reports.py` — Aggregation/bucketing/compliance query logic
- `frontend/src/components/Reports.jsx` — Reports page

**Modify:**
- `backend/main.py` — Register reports router
- `backend/requirements.txt` — Add reportlab
- `frontend/src/App.jsx` — Add /reports route + navbar link
- `frontend/src/api/client.js` — Report API functions

## Out of Scope
- Scheduled/emailed reports
- Custom metric definitions
- Saved report templates
- Charts in PDF exports
- Worker self-comparison to team average

## Testing
- Backend pytest tests for each endpoint (aggregation, scoping, date filtering, CSV/PDF)
- All existing tests must continue to pass
