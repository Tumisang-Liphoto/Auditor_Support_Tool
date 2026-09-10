# Runtime and performance review — 10 September 2026

The next release should focus on import robustness, UI responsiveness, and usable results. Runtime testing identified concrete defects that take priority over expanding the procedure catalogue.

## Scope and method

Tested the current source build (version `0.1.3-beta.2`), including the uncommitted changes present at the start. No application source files were changed. All generated data, settings, workspaces, screenshots, and profiling output are isolated under `build/runtime-review`.

The native desktop-control runtime was unavailable. This is a running Qt widget test using the Windows Python environment and Qt's offscreen platform, not a manual test of an already-open installed executable. The harness creates the real MainWindow, invokes actual button signals and page handlers, and renders widgets. It substitutes file-dialog selections, seeds a synthetic workspace identity, and supplies deterministic field mappings. It therefore does not establish native file-dialog usability or fully manual onboarding. The report dialog is constructed and shown nonmodally for measurement using the same dialog class.

Python 3.14.4; PySide6 6.11.1; Intel Core i7-1255U. Offscreen Qt did not enumerate Segoe UI, so the final runs explicitly loaded the installed Segoe UI fonts. Initial substitute-font screenshots and timings are exploratory and excluded from the final table. Icon fallback and Windows display scaling need native verification.

Synthetic sources contain ten columns, dates spanning 2026, 2% duplicate-invoice records, 10% same-user entry/approval records, and a calculable weekend population. Tested 1,000, 10,000, and 100,000 CSV rows and 10,000 conventional XLSX rows. A second XLSX fixture exercises omitted worksheet dimensions.

Timings are wall-clock measurements on this machine, not statistical percentiles or service-level guarantees. Procedure timings include the page handler and result population. A 10 ms Qt timer was observed around each operation; the timer delivered no callbacks during the long import, procedure, paging, report-construction, or reopen calls. Normal event processing was allowed between operations. A separate experiment changed column sizing only in the test process and restored it afterward.

## What passed

- All **484 existing tests passed in 12.12 seconds**. One pytest cache warning occurred; no assertion failures. An initial test attempt used a missing temporary-directory parent; creating that parent resolved the harness setup errors.
- Required-profile validation, profile saving, and the no-workspace procedure guard were exercised.
- CSV and conventional XLSX import, source confirmation, preparation confirmation, deterministic mapping confirmation, all three procedures, result pagination/search, report construction, and workspace save/reopen completed.
- All three procedure counts matched independently calculated expectations. At 100,000 records: GL001 = 2,000, GL006 = 10,000, and GL003 = 28,494 exceptions.
- Results use a 50-row page, so the main exception table already limits visible rows.

## Measurements

Final recorded run for each workload, in seconds:

| Operation | CSV 1,000 | CSV 10,000 | CSV 100,000 | XLSX 10,000 |
|---|---:|---:|---:|---:|
| Load and analyse | 0.04 | 0.31 | 3.88 | 2.37 |
| GL001 duplicate invoices | 0.05 | 0.35 | 2.50 | 0.34 |
| GL006 segregation of duties | 0.07 | 0.26 | 1.76 | 0.22 |
| GL003 weekend transactions | 0.08 | 0.38 | 2.99 | 0.38 |
| Next 50-row result page | 3.35 | 2.90 | 2.63 | 2.53 |
| Construct full GL003 report dialog | 1.37 | 6.83 | 8.93 | 4.08 |
| Show/paint report after construction | 0.25 | 0.72 | 0.42 | 0.46 |
| Reopen saved workspace | 0.49 | 0.94 | 4.42 | 2.71 |

The earlier 100,000-row run measured 4.53 seconds for loading and 11.15 seconds for report construction. Both runs produced the same counts. This variation is why the findings use approximate ranges rather than claiming precise repeatable latency.

For 100,000 CSV rows, process working set was about **317 MB** after running the procedures and **608 MB** with the full report shown. Peak working set reached **655 MB**. This is whole-process memory, not just the dataset. XLSX generation also occurred in the test process, so its memory is not used for a clean cross-format comparison.

## Prioritised findings and next work

### 1. Handle valid Excel files without declared dimensions

`DataImportService._inspect_excel` assumes `worksheet.max_row` is numeric and subtracts one. The streaming XLSX fixture returns `None`, producing an unhandled `TypeError` in the Browse button handler and leaving Load and Analyse disabled. The application process remains alive, but the import cannot proceed and the error is not presented through the normal import-error UI.

The workbook is readable: openpyxl iterates all 10,001 rows including the header. It was generated with `Workbook(write_only=True)`, which omits worksheet dimension metadata.

**Change:** determine dimensions when missing, support the corresponding column case, and translate inspection failures into the existing import-error boundary. Add a regression using an XLSX with omitted dimensions.

Source: [data_import_service.py](C:/Projects/Auditor_Support_Tool/src/auditor_support_tool/core/data_import_service.py:95).

### 2. Remove repeated column sizing during result paging

A cProfile run attributed **2.898 of 2.937 seconds** to 500 `QTableWidget.setItem` calls for one 50-row, ten-column page. The result table uses `ResizeToContents` for most columns.

Three repeated page changes took **3.304, 3.653, and 3.132 seconds**. Temporarily switching the header to interactive column sizing reduced subsequent page changes to **0.0153, 0.0121, and 0.0073 seconds**. This is a diagnostic experiment, not a production fix, but it strongly identifies automatic sizing during population as the bottleneck.

**Change:** batch table updates and avoid recalculating column widths for each cell. Calculate suitable widths once or expose adjustable widths. Verify values, column visibility, and pagination after the change. A proposed target is under 100 ms per page on this benchmark.

Source: [results_page.py](C:/Projects/Auditor_Support_Tool/src/auditor_support_tool/gui/pages/results_page.py:1423).

### 3. Keep import, execution, and reopen work off the UI thread

At 100,000 records, the UI cannot service the timer for roughly four seconds during loading, two to three seconds during procedure execution, and four seconds during reopening. The active page handlers invoke these operations synchronously. Displaying a status message before the call does not make the operation responsive.

**Change:** run the processing in workers and return results through Qt signals. Show progress and implement cooperative cancellation, with controls guarded against conflicting actions. An `AuditExecutionWorker` exists, but the measured procedure-page path calls the test engine directly; connect or adapt the appropriate worker to that path.

Sources: [data_sources_page.py](C:/Projects/Auditor_Support_Tool/src/auditor_support_tool/gui/pages/data_sources_page.py:450), [audit_procedures_page.py](C:/Projects/Auditor_Support_Tool/src/auditor_support_tool/gui/pages/audit_procedures_page.py:499).

### 4. Load full report details on demand

The report dialog creates a `QTableWidgetItem` for every exception cell. For 28,494 exceptions and 16 columns, that is **455,904 cells**. Report-model construction took only 0.27 seconds in the final run, while constructing the dialog took 8.93 seconds and substantially increased memory.

**Change:** use a model-backed table or paginated detail view and show the summary immediately. Avoid eagerly creating every cell. Export should still include all records. Keep Qt widget creation on the UI thread; optimise how much it creates rather than moving widgets to a worker.

Source: [audit_procedure_report_dialog.py](C:/Projects/Auditor_Support_Tool/src/auditor_support_tool/gui/dialogs/audit_procedure_report_dialog.py:414).

### 5. Fix layouts at supported window sizes

At the declared minimum of **950 × 620**, expanded sidebar child labels overlap and are clipped. Result content extends past the viewport, cutting off actions and cards. At 1200 × 760 the results are substantially more usable, although the expanded sidebar still needs adequate vertical space.

**Change:** put navigation in a scrollable container with non-overlapping row sizes. Let action bars and card rows wrap or switch to a compact layout. Verify 950 × 620, 1200 × 760, and native Windows scaling before release. Do not interpret offscreen missing glyphs as a confirmed installed-app font defect.

Evidence: [minimum-size results screenshot](C:/Projects/Auditor_Support_Tool/build/runtime-review/100000-csv-segoe/10-results-950.png), [default-size results screenshot](C:/Projects/Auditor_Support_Tool/build/runtime-review/100000-csv-segoe/10-results-1200.png).

### 6. Preserve results, then enable export and investigation

After saving and reopening, **three execution stamps remain but the Results page has no outcome**. This is a product gap, not evidence that the source data was lost. Export Result remains disabled; Previous Reports, Investigation, and broader report pages are placeholders.

**Change:** persist immutable completed-run results and their input/parameter references. Add a run browser, Excel export, then investigation notes/statuses associated with stable exception identities. Clearly indicate when displayed results need rerunning.

## Suggested delivery order

1. Excel dimension fallback and paging optimisation, with targeted regression checks.
2. Responsive import/execution/reopen and model-backed report details.
3. Minimum-size layout corrections, followed by native Windows checks at common display scales.
4. Saved run history and Excel export, then investigation workflow.
5. Additional procedures after these workflows are dependable.

## Evidence and reproduction

- [Harness](C:/Projects/Auditor_Support_Tool/build/runtime-review/probe.py)
- [Existing test results](C:/Projects/Auditor_Support_Tool/build/runtime-review/tests.txt)
- [10,000-row metrics and paging experiment](C:/Projects/Auditor_Support_Tool/build/runtime-review/10000-csv-segoe/metrics.json)
- [100,000-row final metrics](C:/Projects/Auditor_Support_Tool/build/runtime-review/100000-csv-segoe/metrics.json)
- [Conventional Excel metrics](C:/Projects/Auditor_Support_Tool/build/runtime-review/10000-xlsx-segoe-normal/metrics.json)
- [Paging CPU profile](C:/Projects/Auditor_Support_Tool/build/runtime-review/10000-csv-segoe/pagination-profile.txt)
- [Streaming Excel failure log](C:/Projects/Auditor_Support_Tool/build/runtime-review/probe-10000-xlsx-segoe.log)
- [Streaming Excel reproducer](C:/Projects/Auditor_Support_Tool/build/runtime-review/10000-xlsx-segoe/synthetic-10000.xlsx)

Run from the repository root:

```powershell
.venv/Scripts/python.exe build/runtime-review/probe.py 100000 csv
.venv/Scripts/python.exe build/runtime-review/probe.py 10000 xlsx
```

The harness writes only to its own review directory; repeat runs replace that workload's metrics/screenshots. For the paging experiment, set `REVIEW_DIAGNOSTICS=1` before the 10,000-row CSV run. Its fixed-width setting is confined to the test process.

Not covered: installed executable startup, native Windows interaction/DPI, live OpenWebUI traffic, update installation, real audit data, concurrent users, and datasets above 100,000 records. Native follow-up remains necessary to validate the visual findings in the packaged application.
