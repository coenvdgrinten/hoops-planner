# PDF Export Improvement Plan

## Overview
Enhance the existing PDF export (`src/sixth_man/core/pdf_export.py`) to produce a more polished, informative schedule document, and add calendar export support.

---

## 1. Quick Wins

### 1.1 Team Logo in Header
- Load the BC Vido logo from `media/assets/` and embed it in the PDF header next to the title.
- Use ReportLab's `Image` flowable to place it at the top-left.
- Fallback: if logo file doesn't exist, skip gracefully (no crash).

### 1.2 Unassigned Slot Indicator
- Replace empty cells with a subtle "—" or "unassigned" text.
- Style it differently (lighter gray, italic) so it's visually distinct from assigned names.

### 1.3 Generation Date Footer
- Add a small footer on each page: "Generated on 2026-07-22".
- Use ReportLab's `onFirstPage`/`onLaterPages` callbacks to add the footer.

---

## 2. Visual Polish

### 2.1 Team Colors
- Replace the generic gray (`#d0d0d0`) header background with BC Vido colors.
- Define team colors as constants in `pdf_export.py` (e.g., primary color, secondary color).

### 2.2 Header Accent
- Add a colored accent bar or gradient behind the title row for a more modern look.
- Use a colored `TableStyle` background for the header row.

### 2.3 Refined Table Styling
- Slightly increase row padding for better readability.
- Add subtle box shadows or borders around date group headers.
- Use rounded corners if feasible with ReportLab.

---

## 3. Per-Player Summary

### 3.1 Summary Page
- After the schedule table, add a second section: "Player Summary".
- For each player, show their total assignments grouped by task type.
- Example: "Coen van Dgrinten: 5× Scorer, 2× Timer"
- Sort alphabetically by last name.
- Only include players who have at least one assignment.

---

## 4. Calendar Export (`.ics`)

### 4.1 Calendar File Generation
- Create `src/sixth_man/core/calendar_export.py` with a function `export_schedule_ics(season: Season) -> bytes`.
- The `.ics` format is plain text — no external library required.
- Each game becomes a `VEVENT` with:
  - `SUMMARY`: "Vido X14-1 vs Opponent"
  - `DTSTART`/`DTEND`: game date + time (duration ~2 hours)
  - `DESCRIPTION`: list of assigned tasks per role
  - `LOCATION`: court name

### 4.2 API Endpoint
- Add `export_ics` action to `SeasonViewSet` in `views.py`.
- Endpoint: `GET /api/seasons/{id}/export_ics/`
- Returns `.ics` file as attachment.

### 4.3 Frontend Integration
- Add an "Export Calendar" button next to the existing PDF/CSV export buttons in the frontend.
- Clicking it downloads the `.ics` file, which opens in the user's calendar app.

---

## Implementation Order

1. **Quick wins** (logo, unassigned indicator, generation date) — ✅ DONE
2. **Visual polish** (team colors, header accent, refined styling) — ✅ DONE
3. **Per-player summary** — ✅ DONE
4. **Calendar export** — ✅ DONE

---

## Files to Modify/Create

| File | Action |
|------|--------|
| `src/sixth_man/core/pdf_export.py` | Modify — all PDF improvements |
| `src/sixth_man/core/calendar_export.py` | Create — calendar export logic |
| `src/sixth_man/core/views.py` | Modify — add `export_ics` endpoint |
| `frontend/src/components/Planner.tsx` | Modify — add calendar export button |
| `tests/test_pdf_export.py` | Modify — update tests for new features |
| `tests/test_calendar_export.py` | Create — calendar export tests |