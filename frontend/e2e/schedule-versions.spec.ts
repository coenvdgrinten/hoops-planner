import { test, expect } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

const API = "/api";

/**
 * Schedule versions on export (issue #3).
 *
 * Covers the user-facing flow: the Export PDF / Export CSV dialog offers a
 * "Save a schedule version" checkbox (+ optional note); saving captures an
 * immutable whole-season snapshot, the download filename gains a _vN suffix,
 * a toast reports the outcome, and re-exporting an unchanged schedule dedupes
 * against the latest version.
 */
test.describe("Schedule versions", () => {
  let seasonName: string;
  let token: string;
  let teamA: string;
  let teamB: string;

  test.beforeEach(async ({ request, page }) => {
    // Every test gets its OWN season + teams (uniqueName): the backend keys
    // seasons/teams by name globally, so fixed names would collide across
    // parallel workers.
    token = await authenticate(request, page, uniqueName("sv-"));
    seasonName = uniqueName("Snap-");
    teamA = uniqueName("Team A");
    teamB = uniqueName("Team B");

    const scheduleCsv =
      `date,time,court,home_team,away_team\n2025-10-01,14:00,1,${teamA},${teamB}`;
    const schedRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(schedRes.status(), "import_schedule should succeed").toBe(201);
  });

  async function selectSeason(page: import("@playwright/test").Page) {
    await page.getByTestId("season-dropdown-toggle").click();
    await page
      .getByTestId("season-dropdown-menu")
      .getByText(seasonName, { exact: true })
      .click();
  }

  /** Open the export dialog for the given format and check the snapshot box. */
  async function openExportWithVersion(
    page: import("@playwright/test").Page,
    format: "csv" | "pdf",
  ) {
    await page
      .getByTestId(format === "csv" ? "export-csv-btn" : "export-pdf-btn")
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await dialog.getByTestId("save-version-checkbox").check();
    return dialog;
  }

  test("export dialog saves a schedule version with a note", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page);

    await page.getByTestId("export-csv-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();

    // The note field only appears once the checkbox is ticked.
    await expect(dialog.getByTestId("version-note-input")).toHaveCount(0);
    await dialog.getByTestId("save-version-checkbox").check();
    const noteInput = dialog.getByTestId("version-note-input");
    await expect(noteInput).toBeVisible();
    await noteInput.fill("sent to team managers");

    const downloadPromise = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const download = await downloadPromise;

    // First snapshot → v1 in the filename.
    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}_v1.csv`);
    // Success toast reports the saved version.
    await expect(
      page.getByRole("alert").filter({ hasText: "Saved schedule version v1." }),
    ).toBeVisible();
  });

  test("re-exporting an unchanged schedule dedupes against the latest version", async ({
    page,
  }) => {
    await page.goto("/");
    await selectSeason(page);

    // First export: save v1.
    let dialog = await openExportWithVersion(page, "csv");
    const firstDownload = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const d1 = await firstDownload;
    expect(d1.suggestedFilename()).toBe(`schedule_${seasonName}_v1.csv`);

    // Second export of the SAME schedule: deduped, no new version.
    dialog = await openExportWithVersion(page, "csv");
    const secondDownload = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const d2 = await secondDownload;

    // No _vN suffix when nothing was saved…
    expect(d2.suggestedFilename()).toBe(`schedule_${seasonName}.csv`);
    // …and the skip is reported, not silent.
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "No changes since v1 - no new version saved." }),
    ).toBeVisible();
  });

  test("changing the schedule creates the next version", async ({
    page,
    request,
  }) => {
    await page.goto("/");
    await selectSeason(page);

    // Save v1 via the UI.
    let dialog = await openExportWithVersion(page, "csv");
    const firstDownload = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const d1 = await firstDownload;
    expect(d1.suggestedFilename()).toBe(`schedule_${seasonName}_v1.csv`);

    // Mutate the schedule: add a second game to the same season via the
    // importer (creates tasks for it → the payload really changes).
    const extraCsv =
      `date,time,court,home_team,away_team\n2025-10-08,14:00,1,${teamA},${teamB}`;
    const importRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: extraCsv },
    });
    expect(importRes.status()).toBe(201);

    // Re-export with the checkbox: a real change exists now → v2.
    dialog = await openExportWithVersion(page, "csv");
    const secondDownload = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const d2 = await secondDownload;
    expect(d2.suggestedFilename()).toBe(`schedule_${seasonName}_v2.csv`);
    await expect(
      page.getByRole("alert").filter({ hasText: "Saved schedule version v2." }),
    ).toBeVisible();
  });

  test("PDF export also saves a version", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page);
    // Wait for stats so the open-task warning renders inside the dialog.
    await expect(page.getByTestId("fill-rate-bar")).toBeVisible();

    await page.getByTestId("export-pdf-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    // Open tasks exist → the warning list shows above the snapshot option.
    await expect(dialog.getByTestId("pdf-warning-list")).toBeVisible();
    await dialog.getByTestId("save-version-checkbox").check();

    const downloadPromise = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}_v1.pdf`);
  });
});
