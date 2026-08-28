# General Ledger Regression Baseline

This fixture freezes the clean General Ledger demonstration case used to
validate the Auditor Support Tool's executable GL procedures.

## Audit period

- Start: 2023-04-01
- End: 2024-03-31

## Source population

- Workbook: `gl_regression_baseline.xlsx`
- General_Ledger records: 2,000
- SHA-256: `874f53f56e59c57f919450875a82907c9822e8079b0306be9aea3963a0f03a34`

## Current known-good procedure results

| Procedure | Evaluated | Exceptions | Key result |
| --- | ---: | ---: | --- |
| GL-001 Duplicate Invoice Detection | 1,329 | 8 | 4 duplicate invoice groups |
| GL-003 Weekend Transactions | 2,000 | 586 | 290 Saturday + 296 Sunday |
| GL-006 Segregation of Duties | 2,000 | 57 | 4 self-approving users; top user finance.manager with 28 |

`expected_results.json` contains the complete expected counts, important
metrics, and source-row identities for regression testing.

## Important distinction

The workbook's own `Expected_Results` and `Embedded_Exceptions` worksheets
identify deliberately embedded examples for a broader future GL test bank.
They are not the complete expected result set for the three currently
implemented procedures. The JSON manifest therefore records the full
known-good outputs produced by the current procedure rules.

## Canonical mappings

See `mapping_manifest.json`. The current baseline maps source fields needed
by GL-001, GL-003 and GL-006, including:

- Invoice Number -> invoice_number
- Transaction Date -> transaction_date
- Prepared By -> entry_user
- Approved By -> approval_user
- Net Amount -> transaction_amount
- Journal Number -> journal_number
- Account Code -> account_code
- Description -> transaction_description
- Vendor Number -> vendor_code
- Source Module -> journal_source

The next step is to add an automated regression test that builds the prepared
dataset from this workbook, applies these mappings, runs GL-001 / GL-003 /
GL-006 through the generic Test Engine, and compares results with
`expected_results.json`.
