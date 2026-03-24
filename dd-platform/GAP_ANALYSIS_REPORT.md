# Digital Direction — Comprehensive Gap Analysis Report
> Generated: 2026-03-24 | Reference: 7,290 rows | Extracted: 1,319 rows

---

## Executive Summary

The extraction pipeline currently captures **18.1% of the reference data** (1,319 / 7,290 rows). The gap breaks down into two distinct categories:

| Category | Missing Rows | % of Gap |
|----------|-------------|----------|
| **22 carriers not yet extracted** (only Charter is built) | 5,971 | **82%** |
| **Charter over-extraction** (1,319 vs 549 reference) | -770 excess | Charter needs row consolidation |
| **Charter missing T\S\OCC rows** | 39 | Taxes/surcharges from invoices |

**Root Cause**: The pipeline currently only has an extraction module for Charter Communications. The other 22 carriers need their own extraction modules or a generic multi-carrier extractor.

---

## Gap Breakdown by Carrier

| Carrier | Ref Rows | Extracted | Gap | Input Files Available | Priority |
|---------|----------|-----------|-----|----------------------|----------|
| Windstream | 3,286 | 0 | -3,286 | 5 inv, 27 con, 11 rep | 🔴 P1 (45% of total) |
| Granite | 2,152 | 0 | -2,152 | 1 inv, 2 rep | 🔴 P1 (30% of total) |
| **Charter** | **549** | **1,319** | **+770 excess** | 13 inv, 12 con, 2 rep | 🟡 Fix grouping |
| Peerless Network | 350 | 0 | -350 | 1 inv, 5 con, 3 rep | 🟠 P2 |
| Consolidated | 260 | 0 | -260 | 6 inv, 2 con, 4 rep | 🟠 P2 |
| Spectrotel | 190 | 0 | -190 | 2 inv, 1 con, 3 rep | 🟠 P2 |
| Frontier | 133 | 0 | -133 | 7 inv, 4 con, 1 rep | 🟠 P2 |
| Verizon | 58 | 0 | -58 | 3 inv, 7 con | 🟢 P3 |
| Delhi Telephone | 50 | 0 | -50 | 1 inv | 🟢 P3 |
| Champlain Tech | 45 | 0 | -45 | 1 inv | 🟢 P3 |
| Nextiva | 35 | 0 | -35 | 17 inv, 2 con, 1 rep | 🟢 P3 |
| Others (12) | 232 | 0 | -232 | Various | 🟢 P3 |

---

## Charter Deep Dive: Over-Extraction Problem

Charter has **549 reference rows** but we're extracting **1,319 rows** (240% over).

### Why?
The carrier report has **7,758 raw line items**. The reference groups these into:
- **175 S-rows** (one per unique service at a location)
- **335 C-rows** (component line items under each service)
- **39 T\S\OCC rows** (taxes, surcharges, one-time charges from invoices)

Our extractor creates 1,163 C-rows vs the reference's 335 — a **3.5x over-count**.

### Charter Account-Level Pattern

| Account | Ref Rows | Addresses | Service Types | S+C+T Pattern |
|---------|----------|-----------|---------------|---------------|
| 117931801 | 289 | 103 | DIA only | 103S + 184C + 2T |
| 145529301 | 178 | 50 | Biz Internet, TV, VOIP, EPL | 54S + 115C + 9T |
| 057778001 | 12 | 2 | DIA, Account Level, VOIP | 2S + 4C + 6T |
| 8358 21 114 0292263 | 14 | 1 | EPL, DIA | 4S + 8C + 2T |

### Key Fix: The C-row grouping logic needs to match **contract-level products** not carrier-report circuit types.

---

## Column Coverage Analysis (Charter Only)

| Column | Ref Populated | Ext Populated | Status |
|--------|--------------|---------------|--------|
| Status | 100% | 100% | ✅ |
| Carrier | 100% | 100% | ✅ |
| Service Address 1 | 100% | 100% | ✅ |
| Service Type | 100% | 100% | ✅ |
| **Monthly Recurring Cost** | **100%** | **27%** | ⚠️ Major gap |
| **Cost Per Unit** | **100%** | **27%** | ⚠️ Major gap |
| **Contract Term/Dates** | **54%** | **27%** | ⚠️ Needs contract parsing |
| **T\S\OCC rows** | **39 rows** | **0** | ❌ Missing entirely |
| Carrier Circuit Number | 56% | 27% | ⚠️ Low coverage |
| Access/Upload Speed | 82% | 32% | ⚠️ Low coverage |

---

## Hash Key Strategy for Matching

We tested composite key combinations across all 7,290 reference rows:

| Key Combination | Unique Keys | Uniqueness |
|-----------------|-------------|------------|
| Carrier + Account + Type + SCU + Address | 1,963 | 26.9% |
| + Component Name | 5,681 | 77.9% |
| + Component Name + MRC | 5,853 | **80.3%** |
| Full 8-column hash | 5,853 | **80.3%** |

**Recommended hash**: `MD5(Carrier|Account|ServiceType|SCU|Address|ComponentName|MRC|ChargeType)` gives 80.3% uniqueness. The remaining 19.7% duplicates are legitimate (e.g., POTS lines at same address with same cost).

### For Charter specifically:
- 533 unique hashes out of 549 rows (97% unique)
- Only 16 true duplicates (same service, same cost, same address)

---

## Autoresearch-Style Improvement Plan

Following Karpathy's methodology: **modify → measure → keep/discard → repeat**

### Phase 1: Fix Charter (Current → 549 rows, ~95% accuracy)
1. **Fix C-row consolidation** — group by contract product, not circuit type
2. **Add T\S\OCC extraction** — parse invoice PDFs for tax/surcharge lines
3. **Populate MRC** — extract from contract files and invoice line items
4. **Fix account 145529301** — add Business Internet/TV/VOIP rows from TOPS spreadsheet
5. **Apply hash matching** — compare extracted vs reference by composite key

### Phase 2: Add Windstream (3,286 rows = 45% of total)
- Input: 5 invoices, 27 contracts, 11 carrier reports
- The carrier report `Customer Inventory by COMMS` is **shared** between Charter and Windstream
- Build `src/extraction/windstream.py` using same patterns

### Phase 3: Add Granite (2,152 rows = 30% of total)
- Input: 1 invoice (Granite is contract-heavy), 2 reports
- Build `src/extraction/granite.py`

### Phase 4: Add Remaining Carriers (1,802 rows = 25% of total)
- Build generic extraction module that handles carriers with:
  - Only invoices (no carrier report) — PDF parsing required
  - Invoice + contract — cross-reference pricing
  - Standard carrier report formats

### Phase 5: Cross-Validation & Accuracy Scoring
- Run hash-based comparison against all 7,290 reference rows
- Field-level accuracy: match each of 60 columns individually
- Row-level accuracy: match by composite key
- Automated accuracy regression tests

---

## What Can Be Improved WITHOUT API Key

| Improvement | Impact | Rows Gained | Effort |
|-------------|--------|-------------|--------|
| Fix Charter C-row grouping | High | -770 (remove excess) | Medium |
| Parse Charter carrier report (TOPS spreadsheet) | High | +178 (acct 145529301) | Low |
| Build Windstream extractor (carrier reports) | Very High | +3,286 | Medium |
| Build Granite extractor (carrier reports) | Very High | +2,152 | Medium |
| Build generic carrier report parser | High | +1,802 | High |
| Parse structured Excel carrier reports | Medium | varies | Low |

## What API Key Enables (Anthropic Claude API)

| Improvement | Impact | Rows Gained |
|-------------|--------|-------------|
| Invoice OCR → T\S\OCC rows | Medium | +967 across all carriers |
| Invoice OCR → MRC validation | High | validates 100% of costs |
| Contract OCR → term dates | Medium | fills 54% of contract columns |
| Cross-validation (invoice vs report) | High | flags mismatches |
| Unstructured PDF parsing for carriers with no report | Critical | enables 12 carriers with invoice-only data |

---

## Next Steps (Recommended Priority)

1. **[NOW]** Fix Charter extraction accuracy (549 → match reference)
2. **[NOW]** Build Windstream extractor (adds 3,286 rows = 45% coverage)
3. **[NOW]** Build Granite extractor (adds 2,152 rows = 30% coverage)
4. **[SOON]** Build generic multi-carrier extractor for remaining 20 carriers
5. **[API KEY]** Enable invoice OCR for T\S\OCC and cost validation
6. **[API KEY]** Enable contract OCR for term/date fields
