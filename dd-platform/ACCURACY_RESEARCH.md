# Accuracy Research Report: Charter Communications Inventory Extraction

**Date:** 2026-03-24
**Scope:** Field-by-field accuracy analysis of Charter extraction vs reference NSS Inventory File
**Methodology Inspired By:** Karpathy's autoresearch autonomous improvement loop

---

## Part 1: Autoresearch Methodology Summary

### Core Concept

Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) is an autonomous AI research loop where an agent iteratively improves a codebase by:

1. **Making a change** to a single target file (`train.py`)
2. **Running the experiment** (fixed 5-minute training budget)
3. **Measuring a single metric** (`val_bpb` - validation bits per byte)
4. **Keeping or discarding** based on whether the metric improved
5. **Repeating indefinitely** without human intervention

### Key Design Principles

| Principle | Autoresearch Implementation | Our Analogy |
|-----------|---------------------------|-------------|
| **Single metric** | `val_bpb` (lower is better) | Overall field-match accuracy % |
| **Single file to modify** | `train.py` only | `charter.py` extractor logic |
| **Fixed evaluation** | `evaluate_bpb()` in `prepare.py` (read-only) | Reference file comparison script |
| **Git-based rollback** | Keep improvement, `git reset` on regression | Same approach |
| **Simplicity criterion** | Small accuracy gain + complexity = reject | Same trade-off |
| **Autonomous loop** | Agent runs ~12 experiments/hour overnight | Agent iterates extraction logic |

### The Iteration Protocol

```
LOOP FOREVER:
  1. Read current state (code + results.tsv)
  2. Propose a change to the extraction logic
  3. Commit the change
  4. Run extraction pipeline + accuracy evaluation
  5. Compare: did overall accuracy improve?
     - YES: keep commit, advance branch
     - NO: git reset, try another approach
  6. Log result to results.tsv
```

### What Makes This Work

- **Deterministic evaluation**: The reference file never changes, so accuracy is directly comparable across runs.
- **Fast feedback loop**: Each extraction run takes seconds (not 5 minutes like LLM training), so we can iterate much faster.
- **Granular metrics**: We can track per-field accuracy, not just a single number, allowing targeted improvements.

---

## Part 2: Current Accuracy Metrics

### 2.1 Row Count Comparison

| Metric | Reference | Extracted | Delta |
|--------|-----------|-----------|-------|
| **Total rows** | 549 | 1,370 | +821 (2.5x over-extraction) |
| S-rows (Service) | 175 | 156 | -19 |
| C-rows (Component) | 335 | 1,163 | +828 |
| T\S\OCC rows | 39 | 51 | +12 |

**Root cause of row explosion**: The extraction creates one C-row per distinct `circuit_type` or `tn_type` per site in the carrier report. Account 117931801 has 289 reference rows but generates 1,314 extracted rows because the carrier report contains many TN-level records with distinct circuit/TN types that each become a C-row, whereas the reference aggregates these differently.

### 2.2 Account-Level Analysis

| Account | Ref Rows | Ext Rows | Issue |
|---------|----------|----------|-------|
| 117931801 | 289 | 1,314 | **4.5x over-extraction** - carrier report has many per-TN records |
| 145529301 | 178 | 17 | **90% under-extraction** - only T\S\OCC rows extracted, no S/C rows |
| 8358 11 002 0022370 | 15 | 10* | Account number formatting (spaces stripped) |
| 8358 21 114 0292263 | 14 | 3* | Account number formatting (spaces stripped) |
| 8143 16 033 0055404 | 13 | 0 | **Completely missing** from extraction |
| 057778001 | 12 | 4 | Under-extraction |
| 057777701 | 9 | 4+7* | Split: 4 with leading zero, 7 without |
| 8358 21 170 0107125 | 6 | 2* | Account number formatting |
| 8358 21 062 0249975 | 4 | 0 | **Completely missing** |
| 8358 21 114 0215710 | 1 | 0 | **Completely missing** |

*Asterisk = account present in extracted but with reformatted number (spaces removed), so not matched directly.

**Three missing accounts** (8143 16 033 0055404, 8358 21 062 0249975, 8358 21 114 0215710) total 18 reference rows with no corresponding extraction.

### 2.3 Field-Level Population Rates

Comparing what percentage of rows have data populated for each field:

| Field | Ref % | Ext % | Gap | Severity |
|-------|-------|-------|-----|----------|
| **Monthly Recurring Cost** | 100% (549/549) | **6.7% (92/1370)** | -93.3% | **CRITICAL** |
| **Cost Per Unit** | 100% (549/549) | **3.0% (41/1370)** | -97.0% | **CRITICAL** |
| **MRC per Currency** | 100% (549/549) | **3.0% (41/1370)** | -97.0% | **CRITICAL** |
| **Quantity** | 100% (549/549) | 96.3% | -3.7% | Low |
| **Conversion Rate** | 100% (549/549) | 96.3% | -3.7% | Low |
| Carrier Circuit Number | 55.9% (307/549) | 26.0% (356/1370) | Variable | HIGH |
| Service Address 2 | 11.5% (63/549) | 0% (0/1370) | -11.5% | Medium |
| Sub-Account Number | 88.5% (486/549) | 96.3% | +7.8% | Low |
| Access Speed | 81.6% (448/549) | 30.3% (415/1370) | Variable | HIGH |
| Upload Speed | 81.6% (448/549) | 30.3% (415/1370) | Variable | HIGH |
| Service Type 2 | 4.7% (26/549) | 0% (0/1370) | -4.7% | Low |
| BTN | 0% (0/549) | 91.8% (1258/1370) | +91.8% | Medium* |
| Phone Number | 3.6% (20/549) | 91.8% (1258/1370) | +88.2% | Medium* |
| Master Account | 0% (0/549) | 96.3% (1319/1370) | +96.3% | Medium* |
| Billing Per Contract | 92.9% (510/549) | 26.0% (356/1370) | -66.9% | HIGH |
| Currently Month-to-Month | 92.9% (510/549) | 26.0% (356/1370) | -66.9% | HIGH |
| Month-to-Month/Year Remaining | 92.9% (510/549) | 0% (0/1370) | -92.9% | **CRITICAL** |
| Contract File Name | 92.9% (510/549) | 26.0% (356/1370) | -66.9% | HIGH |
| Auto Renew | 53.9% (296/549) | 26.0% (356/1370) | Variable | HIGH |
| Auto Renewal Notes | 53.9% (296/549) | 26.0% (356/1370) | Variable | HIGH |
| Contract Term Months | 53.9% (296/549) | 26.0% (356/1370) | Variable | HIGH |
| Z Address fields | 2.7% (15/549) | 0% (0/1370) | -2.7% | Low |

*Fields marked Medium* are cases where we OVER-populate vs reference (reference has them blank, we fill them). This is not necessarily wrong but diverges from reference convention.

### 2.4 Value-Level Match Analysis (on 6 matched rows)

Using loose matching on (Account + BTN + S/C + Feature Name):

| Field | Match % | Primary Issue |
|-------|---------|---------------|
| Carrier Account Number | 100% | -- |
| Carrier | 100% | -- |
| Service or Component | 100% | -- |
| Component or Feature Name | 100% | -- |
| Currency | 100% | -- |
| Status | 100% | -- |
| **Invoice File Name** | **0%** | Extracted adds `.pdf` extension; ref omits it |
| **Country** | **0%** | Ref uses "USA", extracted uses "US" |
| **Service Address 1** | **0%** | Ref has addresses, extracted has them blank (4/6) |
| **City** | **0%** | Same as above |
| **Cost Per Unit** | **0%** | Ref has values, extracted all blank |
| **MRC per Currency** | **0%** | Ref has values, extracted all blank |
| **Billing Name** | **17%** | Name differences: "TOP MARKETS LLC" vs "TOPPS MARKET LLC" |
| **State** | **17%** | Missing addresses → missing states |
| **Zip** | **17%** | Missing addresses → missing zips |
| **Sub-Account Number** | **17%** | Ref has sub-accounts, extracted missing 4/6 |
| **Quantity** | **17%** | Ref has 1, extracted blank |
| **Conversion Rate** | **17%** | Ref has 1, extracted blank |
| Monthly Recurring Cost | 50% | Values differ when present; often missing in extracted |
| Service Type | 50% | "EPL" in ref → "Account Level" in ext for T\S\OCC rows |
| Carrier Circuit Number | 50% | Ref has circuit IDs, extracted missing |

### 2.5 Column Ordering Issue

The reference file and extracted file have different column orderings in the Z Location Area and Contract Area:

**Reference order (cols 42-48):**
`Z Location Name | Z Address 1 | Z Address 2 | Z City | Z State | Z Zip | Z Country`

**Extracted order (cols 42-48):**
`Z Address 1 | Z Address 2 | Z City | Z State | Z Zip | Z Country | Z Location Name`

Similarly, Contract File Name and Contract Number are swapped:
- Reference: col 55 = Contract File Name, col 56 = Contract Number
- Extracted: col 55 = Contract Number, col 56 = Contract File Name

**Root cause**: The schema in `schema.py` defines Z Location Area with `Z Address 1` first (col AQ) and `Z Location Name` last (col AW), while the reference file has `Z Location Name` first (col 42) and `Z Address 1` after. The `to_row_dict()` method in `InventoryRow` maps to the schema ordering, not the reference ordering.

---

## Part 3: Gap Analysis with Root Causes

### GAP 1: Row Count Explosion (CRITICAL)
- **Symptom**: 1,370 extracted vs 549 reference rows
- **Root cause**: The carrier report ("Customer Inventory by COMMS") contains one row per TN/circuit at each site. The extractor creates one C-row per distinct `circuit_type`/`tn_type` per site. For account 117931801, there are ~150 sites each generating ~8 component rows (Internet, VoIP, SD-WAN, Trunk Line, etc.) when the reference only has 1-2 components per site.
- **Reference pattern**: The reference groups components differently. For DIA sites, the reference typically has: 1 S-row (the service) + 1-2 C-rows (the specific product like "Dedicated Fiber Internet 50Mbps") + possibly a T\S\OCC row.
- **Impact**: 2.5x more rows than expected, inflating C-row count from 335 to 1,163.

### GAP 2: Account 145529301 Under-Extraction (CRITICAL)
- **Symptom**: 178 reference rows vs 17 extracted (90% missing)
- **Root cause**: The `_resolve_carrier_account()` method maps "TOPS" names to account 145529301, but the actual TOPS/Business Internet service rows are not being created. Only T\S\OCC tax/surcharge rows are generated (17 rows). The S-rows and C-rows for Business Internet, TV, and VOIP Line services at this account are completely missing.
- **Why**: The carrier report likely has TOPS sites under a different parent ID or naming pattern that doesn't trigger the TOPS mapping. The TOPS spreadsheet parsing produces records but they aren't being matched to create S/C rows for Business Internet services.

### GAP 3: MRC Almost Entirely Missing (CRITICAL)
- **Symptom**: 6.7% population rate (92/1370) vs 100% in reference
- **Root cause**: MRC values come only from contract data (address-matched) or invoice OCR. Without API key, OCR is skipped. Contract matching is by normalized address, which covers only the fiber/DIA contract file (~296 records). For the remaining ~253 reference rows (TOPS/Business Internet accounts), there is no MRC source.
- **Additionally**: Even for matched contract records, the MRC flows to the S-row but C-rows never get individual MRC values. The C-row `monthly_recurring_cost` field is always None in the current code (line 600 in charter.py: no MRC assignment for C-rows).
- **Impact**: Cost Per Unit and MRC per Currency are derived from MRC, so they cascade to 0% as well.

### GAP 4: Missing Addresses for Matched Rows
- **Symptom**: Service Address 1, City, State, Zip all show 0-17% match on matched rows
- **Root cause**: For T\S\OCC rows (the ones that actually matched), addresses come from `page.service_address` in OCR results. When OCR data is sparse or account-level, the address is not populated. The carrier report has addresses but they flow to S/C rows, not T\S\OCC rows.

### GAP 5: Account Number Formatting
- **Symptom**: Accounts like "8358 11 002 0022370" (ref) vs "8358110020022370" (ext)
- **Root cause**: The PDF filename extraction in `_parse_invoices()` calls `.replace(" ", "")` on the account number, stripping internal spaces. The reference preserves the spaced format.
- **Impact**: 3 accounts (totaling ~35 rows) have space-formatted numbers in ref that don't match the extracted format.

### GAP 6: Country Value Mismatch
- **Symptom**: Reference uses "USA", extraction uses "US"
- **Root cause**: Hardcoded `country="US"` in charter.py (lines 458, 586). Reference convention is "USA".

### GAP 7: Invoice File Name Includes Extension
- **Symptom**: Ref has "Charter Communications_145529301_08142025_BILL", ext has "...BILL.pdf"
- **Root cause**: The `_find_invoice_file()` returns the full filename including `.pdf` extension. Reference strips the extension.

### GAP 8: Missing Contract/Billing Fields
- **Symptom**: Billing Per Contract, Currently Month-to-Month, Month-to-Month remaining all at 0-26% in extracted
- **Root cause**: These fields are only populated when contract data matches by address. For the ~253 non-DIA rows (Business Internet, TV, VOIP), no contract data exists in the structured contract files, so these fields are blank. The reference shows these populated for 92.9% of rows, meaning the manual process had access to additional contract information we're not parsing.

### GAP 9: Quantity/Conversion Rate Not Set for C-Rows
- **Symptom**: Ref has Quantity=1 and Conversion Rate=1 for all rows; extracted has them blank for C-rows
- **Root cause**: S-rows set `quantity=1.0` and `conversion_rate=1.0` (charter.py lines 468-470), but C-rows only set `quantity=1.0` and `conversion_rate=1.0` (lines 598-599) -- actually they DO set these. But for T\S\OCC rows (lines 660-678), neither quantity nor conversion_rate is set. Since the matched rows in our comparison are disproportionately T\S\OCC rows, this explains the low match rate.

### GAP 10: Schema Column Order Mismatch
- **Symptom**: Z Location and Contract columns in different positions
- **Root cause**: `INVENTORY_SCHEMA` in `schema.py` defines Z Location Area as AQ=Z Address 1 through AW=Z Location Name. But the reference file has Z Location Name before Z Address 1. Similarly, Contract Number and Contract File Name are swapped.

---

## Part 4: Prioritized Improvement Plan

### Priority 1: Fix Row Grouping Logic (Impact: ~800 excess rows eliminated)
**Effort: HIGH | Accuracy Impact: HIGHEST**

The single biggest issue. The extractor must replicate the reference's grouping logic:

1. **Change**: Instead of creating one C-row per distinct circuit_type at a site, examine how the reference groups. The reference pattern for account 117931801 (DIA) is:
   - 1 S-row per unique Sub-Account Number (Customer #)
   - 1-3 C-rows per S-row (the specific product descriptions, not every TN type)
   - Feature names in ref: "Dedicated Fiber Internet 50Mbps", "Ethernet Access", "EPL 1 Gbps" etc. (contract-level descriptions, not carrier-report circuit_type values)

2. **Specific code change needed in `charter.py`**:
   - `_build_c_rows_from_site()` should NOT create one C-row per circuit_type
   - Instead, match to contract records to get the actual product descriptions
   - Use contract `Product` and `Description` fields as `Component or Feature Name`
   - Only create C-rows for components that exist in contracts or invoices

3. **For account 145529301 (TOPS/Business Internet)**:
   - Create S-rows from TOPS spreadsheet data (each location = 1 S-row)
   - Create C-rows from invoice line items (Spectrum Business Internet, Spectrum TV, etc.)
   - Currently these rows are completely missing

### Priority 2: Populate MRC from Invoices (Impact: +93% MRC population)
**Effort: MEDIUM | Accuracy Impact: VERY HIGH**

1. **Without OCR (text-based PDFs)**: Many Charter invoices are text-based PDFs. The code currently stores `pdf_result` but never extracts MRC from text PDFs (line 273: "Store raw text for text-based extraction (future enhancement)").

2. **With structured contract data**: The contract file has MRC values. Currently matched by address only. Add matching by circuit ID (more reliable).

3. **For C-rows**: Pass MRC down from contract data to C-rows. Currently C-rows get `None` for MRC.

4. **Derived fields**: Once MRC is populated:
   - `cost_per_unit = mrc` (when quantity=1)
   - `mrc_per_currency = mrc` (when conversion_rate=1 for USD)
   - `billing_per_contract = mrc` (when contract exists)

### Priority 3: Fix Easy Value Mismatches (Impact: +5-10% across many fields)
**Effort: LOW | Accuracy Impact: MEDIUM**

Quick fixes with high ROI:

1. **Country**: Change `country="US"` to `country="USA"` in charter.py (2 lines)
2. **Invoice File Name**: Strip `.pdf` extension from `inv_file` before storing
3. **Account Number Formatting**: Preserve spaces in account numbers from PDF filenames
4. **Quantity/Conversion Rate for T\S\OCC rows**: Add `quantity=1.0`, `conversion_rate=1.0`
5. **Contract Info Received**: Set to "Yes" when contract data found, "-" otherwise (ref uses "-" not "No")

### Priority 4: Fix Column Ordering (Impact: Structural correctness)
**Effort: LOW | Accuracy Impact: MEDIUM**

1. In `schema.py`, reorder Z Location Area: Move `Z Location Name` from AW to before AQ (or adjust `to_row_dict` mapping)
2. Swap Contract Number and Contract File Name in the schema to match reference

Note: The `to_row_dict()` already maps fields to column names correctly. The issue is the column ordering in `INVENTORY_SCHEMA` which controls the Excel output order. The fix is to reorder:
```
Current: AQ=Z Address 1, AR=Z Address 2, ..., AW=Z Location Name
Fix to:  AQ=Z Location Name, AR=Z Address 1, ..., AW=Z Country
```

### Priority 5: Fix Address Population (Impact: +50% for address fields)
**Effort: MEDIUM | Accuracy Impact: MEDIUM**

1. For T\S\OCC rows, inherit address from the parent S-row or the carrier report
2. Implement linkage_key based parent-child inheritance for address fields
3. Ensure TOPS sites get proper addresses from the TOPS spreadsheet

### Priority 6: Contract Field Population (Impact: +60% for contract fields)
**Effort: HIGH | Accuracy Impact: MEDIUM**

1. Parse additional contract PDFs (not just structured XLSX)
2. Extract term dates, auto-renew clauses from contract text
3. Populate `Month to Month or Less Than a Year Remaining` field (currently always blank in extraction)
4. Set `Billing Per Contract` = MRC when contract exists and billing matches

### Priority 7: Missing Accounts (Impact: 18 missing rows)
**Effort: MEDIUM | Accuracy Impact: LOW**

1. Account `8143 16 033 0055404` (13 rows) - likely a different format in carrier report
2. Accounts `8358 21 062 0249975` (4 rows) and `8358 21 114 0215710` (1 row) - also missing
3. Debug why these don't appear in extracted output; likely missing from carrier report files or naming mismatch

---

## Part 5: Applying the Autoresearch Loop

### Proposed Evaluation Harness

Create an `evaluate_accuracy.py` (analogous to `prepare.py evaluate_bpb()`) that:

1. Loads the reference file (Charter rows only, 549 rows)
2. Loads the latest extracted file
3. Normalizes account numbers (strip spaces, preserve leading zeros)
4. Matches rows using composite key (account + sub-account + S/C + feature)
5. Computes:
   - **Row-level recall**: % of reference rows matched in extraction
   - **Row-level precision**: % of extracted rows that exist in reference
   - **Field-level accuracy**: Per-column match rate on matched rows
   - **Overall score** = weighted average (MRC fields 3x weight, address fields 2x weight)

### Iteration Targets

| Iteration | Focus | Expected Score Improvement |
|-----------|-------|---------------------------|
| 1 | Fix country, invoice extension, quantity defaults | +3% |
| 2 | Fix C-row grouping logic (biggest win) | +25% |
| 3 | Populate MRC from contracts properly | +15% |
| 4 | Fix account 145529301 extraction | +10% |
| 5 | Fix column ordering in schema | +5% (structural) |
| 6 | Add text-based PDF MRC extraction | +10% |
| 7 | Contract field population | +5% |

### Success Criteria

- **Phase 1 target**: Row count within 10% of reference (495-605 rows)
- **Phase 2 target**: Field-level accuracy > 80% on required fields
- **Phase 3 target**: Field-level accuracy > 95% on required fields, > 70% on all fields

---

## Appendix A: Files Analyzed

### Reference File
`/Users/harivershan/.../Digital Direction_NSS_ Inventory File_01.22.2026_WIP_v3 BF- Sent to Techjays.xlsx`
- Sheet: Baseline, Header Row: 3
- Charter Communications rows: 549 (filtered by Carrier column = "Charter Communications")

### Extracted File
`/Users/harivershan/.../dd-extraction/outputs/charter_inventory_output.xlsx`
- Sheet: Baseline, Header Row: 3
- Total rows: 1,370

### Extraction Code
- `/Users/harivershan/.../dd-extraction/src/extraction/charter.py` - Main extractor
- `/Users/harivershan/.../dd-extraction/src/mapping/schema.py` - Column schema and row model
- `/Users/harivershan/.../dd-extraction/src/output/generator.py` - Excel output generator
- `/Users/harivershan/.../dd-extraction/main.py` - Pipeline orchestrator

## Appendix B: Reference Service Type Distribution (Account 117931801)

| Service Type | Reference | Extracted |
|-------------|-----------|-----------|
| DIA | 289 | 1,174 |
| VOIP Line | 0 | 21 |
| SDWAN | 0 | 113 |
| Account Level | 0 | 6 |

The reference classifies ALL 117931801 rows as "DIA". The extraction splits them into DIA/VOIP/SDWAN/Account Level based on TN types, which does not match the reference convention.

## Appendix C: Reference Service Type Distribution (Account 145529301)

| Service Type | Reference | Extracted |
|-------------|-----------|-----------|
| Business Internet | 137 | 0 |
| TV | 27 | 0 |
| Account Level | 7 | 17 |
| VOIP Line | 7 | 0 |

The extraction only produces Account Level (tax) rows for this account. All Business Internet (137), TV (27), and VOIP Line (7) rows are completely missing.
