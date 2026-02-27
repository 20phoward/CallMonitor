# Phase 2 Design: Call Rating & Review System

**Date:** 2026-02-27
**Approach:** Extend existing Claude tonality prompt to auto-score rubric categories (Approach A — single API call)

---

## Data Model

### New: `CallScore` table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| call_id | FK → calls | one-to-one |
| empathy | Float 0-10 | Empathy & Compassion score |
| professionalism | Float 0-10 | Professionalism score |
| resolution | Float 0-10 | Resolution & Follow-through score |
| compliance | Float 0-10 | Compliance & Safety score |
| overall_rating | Float 0-10 | Average of four category scores |
| category_details | JSON | AI reasoning per category |

### New: `Review` table
| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | |
| call_id | FK → calls | one-to-one |
| status | String | `unreviewed` / `approved` / `flagged` |
| score_overrides | JSON | `{"empathy": 7.5, ...}` — only changed categories |
| notes | Text | Optional supervisor notes |
| reviewed_at | DateTime | When review was submitted |

### Modified: `Call` model
- Add relationships to `CallScore` and `Review`

**Effective score** for any category = override (from Review) if exists, else AI score (from CallScore).

---

## Claude Prompt Extension

Extend `ANALYSIS_PROMPT` in `tonality.py` to return additional `rubric_scores` field:

```json
{
  "rubric_scores": {
    "empathy": {"score": 7.5, "reasoning": "Worker acknowledged patient's frustration..."},
    "professionalism": {"score": 8.0, "reasoning": "Maintained appropriate tone..."},
    "resolution": {"score": 6.0, "reasoning": "Addressed main concern but..."},
    "compliance": {"score": 9.0, "reasoning": "Proper introduction, no safety concerns..."}
  }
}
```

**Score scale (0-10):**
- 0-3: Poor / concerning
- 4-5: Below expectations
- 6-7: Meets expectations
- 8-9: Exceeds expectations
- 10: Exceptional

Prompt includes healthcare/rehab-specific guidance per category.

---

## API Endpoints

### New
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/calls/{id}/scores` | Rubric scores (AI + effective after overrides) |
| POST | `/api/calls/{id}/review` | Submit review (approve/flag, overrides, notes) |
| GET | `/api/calls/{id}/review` | Get existing review |

### Modified
| Endpoint | Change |
|----------|--------|
| `GET /api/calls` | Add `overall_rating`, `review_status` to CallSummary |
| `GET /api/calls/stats` | Add avg rubric scores, review counts |
| `GET /api/calls/{id}` | Include scores and review in CallDetail |

### Review payload
```json
{
  "status": "approved",
  "score_overrides": {"resolution": 8.0},
  "notes": "Good call, resolution was better than AI scored"
}
```

Review endpoint is idempotent — posting again updates the existing review.

---

## Frontend UI

### Score Card (on Call Detail page)
- Four category scores as colored bars/badges (red/yellow/green)
- Overall rating prominently displayed
- AI reasoning as expandable text per category
- Override-highlighted effective scores if review exists

### Review Panel (on Call Detail page)
- Approve / Flag buttons with current status badge
- Inline score override on click
- Optional notes textarea
- Submit saves via POST

### Dashboard & Call List updates
- Call list: new Rating and Review Status columns, filterable/sortable
- Dashboard: avg rating card, calls needing review count, flagged calls count

---

## Pipeline Integration

- `tonality.py`: Extend prompt, parse `rubric_scores` from response
- `pipeline.py`: After writing TonalityResult, also create CallScore record
- `overall_rating` = average of four category scores
- If `rubric_scores` missing from response, save CallScore with null scores (don't fail pipeline)
- Review records created only by supervisor action, never by pipeline

---

## Security Note

No real PHI until Phase 3 (auth/roles) and Phase 6 (encryption, HIPAA hardening) are complete. Dev/test data only.

## Out of Scope (deferred)
- Authentication & roles (Phase 3)
- Comment/annotation on transcript segments
- Team assignments
- Export/reporting
