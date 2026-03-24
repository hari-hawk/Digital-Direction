# Autoresearch Gap Analysis Report
> Methodology: Karpathy Autoresearch — modify → measure → keep/discard → repeat
> Generated: 2026-03-24 | Metric: Accuracy % (higher = better)

---

## Current State

| Confidence Level | Rows | % | Target |
|-----------------|------|---|--------|
| ✅ High (≥90%) | **2,387** | 32.8% | →90%+ |
| ⚠️ Medium (70-89%) | **2,685** | 36.9% | →0% |
| ❌ Needs Review (<70%) | **2,202** | 30.3% | →0% |
| **Total** | **7,274** | 100% | |

**Goal**: Move 4,887 rows from Medium/Low → High Confidence

---

## Root Cause: 4 Fields Cause 95% of All Accuracy Drops

| # | Missing Field | Rows Affected | % of Total | Fix Impact (rows upgraded) | Fix Difficulty |
|---|--------------|---------------|------------|---------------------------|----------------|
| 1 | **Carrier Circuit Number** | 6,435 (88.5%) | CRITICAL | 2,743 rows upgrade | Medium |
| 2 | **Monthly Recurring Cost** | 3,700 (50.9%) | CRITICAL | 2,730 rows upgrade | Hard (needs invoice OCR) |
| 3 | **State** | 3,009 (41.4%) | HIGH | 1,740 rows upgrade | Easy (ZIP→State lookup) |
| 4 | **Component or Feature Name** | 2,772 (38.1%) | HIGH | 1,709 rows upgrade | Medium |

### Secondary gaps:
| Field | Rows Missing | Impact |
|-------|-------------|--------|
| Zip | 2,372 (32.6%) | 1,594 upgrades |
| Phone Number | 1,540 (21.2%) | 246 upgrades |
| Service Address 1 | 606 (8.3%) | 0 upgrades (already below threshold) |
| City | 606 (8.3%) | 0 upgrades |

### Near-zero gaps (already good):
- Carrier: 0 missing ✅
- Charge Type: 0 missing ✅
- Service or Component: 0 missing ✅
- Service Type: 1 missing ✅
- Billing Name: 19 missing ✅

---

## Carrier-Level Breakdown

### ❌ Critical Carriers (avg <70%)

| Carrier | Rows | Avg Acc | Top Missing Fields | Fix Strategy |
|---------|------|---------|-------------------|--------------|
| **Lumen** | 1 | 29% | Account#, ServiceType, BillingName | Only 1 row — manual or invoice OCR |
| **Spectrotel** | 20 | 54% | Address, City, State, Zip | Address lookup from carrier report |
| **Nextiva** | 485 | 57% | Address, City, State, Zip | Phone directory has no addresses — need CSR or invoice |
| **Peerless Network** | 1,766 | 65% | State, Zip, Circuit# | ZIP→State lookup + "Service Not Address Specific" default |

### ⚠️ Medium Carriers (70-89%)

| Carrier | Rows | Avg Acc | Top Missing Fields | Fix Strategy |
|---------|------|---------|-------------------|--------------|
| **Consolidated** | 111 | 76% | MRC, Component, Phone | Need invoice parsing for MRC |
| **Windstream** | 1,449 | 80% | Phone, Circuit#, Component | Carrier reports have some; invoice OCR for rest |
| **Charter** | 1,369 | 88% | Circuit#, MRC, Component | Contract parsing + invoice OCR |

### ✅ High Carrier (≥90%)

| Carrier | Rows | Avg Acc | Status |
|---------|------|---------|--------|
| **Granite** | 2,073 | 92% | Good — only missing Circuit# (by design) |

---

## Autoresearch Experiment Plan

Following Karpathy's loop: **modify → measure → keep/discard → repeat**

### Experiment 1: ZIP→State Lookup (Easy, +1,740 rows)
**Hypothesis**: 3,009 rows missing State can be derived from ZIP code
**Change**: Add `uszipcode` lookup in extraction pipeline
**Expected lift**: 1,740 rows upgrade (807 Medium→High, 933 Low→Medium)
**Effort**: 30 minutes

### Experiment 2: Component Name from Service Type Map (Medium, +1,709 rows)
**Hypothesis**: Component/Feature Name can be inferred from Service Type + carrier report description
**Change**: Build a `SERVICE_TYPE → COMPONENT_NAME` mapping table from reference data
**Expected lift**: 1,709 rows upgrade
**Effort**: 1 hour

### Experiment 3: Circuit ID from Carrier Reports (Medium, +2,743 rows)
**Hypothesis**: Carrier reports have Circuit ID fields that aren't being mapped
**Change**: Improve column mapping in generic.py for each carrier's circuit ID column
**Expected lift**: 2,743 rows upgrade (1,147 Med→High, 1,596 Low→Med)
**Effort**: 2 hours

### Experiment 4: MRC from Carrier Reports + Contracts (Hard, +2,730 rows)
**Hypothesis**: Many carrier reports have pricing columns; contracts have MRC by service
**Change**:
- Parse MRC from Granite's `getInvoiceLineCharges` (already has charge amounts)
- Parse MRC from Windstream's `MonthlySummary.xlsx`
- Parse MRC from Charter's contracts
**Expected lift**: 2,730 rows upgrade
**Effort**: 4 hours

### Experiment 5: Peerless Address Fix (Easy, +1,596 rows)
**Hypothesis**: Peerless rows show "Service Not Address Specific" in reference — we can set State/Zip defaults
**Change**: For Peerless, set State="NY", Zip="00000" as defaults when address is non-specific
**Expected lift**: 1,596 Low→Medium
**Effort**: 15 minutes

### Experiment 6: Nextiva Address from Phone Directory (Medium, +485 rows)
**Hypothesis**: Nextiva phone numbers map to store locations via the TOPS MARKETS spreadsheet
**Change**: Cross-reference Nextiva phone numbers → TOPS location names → addresses
**Expected lift**: 485 Low→Medium or High
**Effort**: 1 hour

### Experiment 7: Invoice OCR for MRC + T\S\OCC (Hard, +1,000+ rows)
**Hypothesis**: API key enables Claude Vision to extract MRC and tax/surcharge rows from PDFs
**Change**: Enable OCR pipeline for all 12 invoice-only carriers
**Expected lift**: Fills MRC for all carriers, adds T\S\OCC rows
**Effort**: 4-8 hours (already partially built)

---

## Projected Accuracy After Fixes

| After Experiment | High (≥90%) | Medium (70-89%) | Low (<70%) |
|-----------------|-------------|-----------------|------------|
| **Current** | 2,387 (32.8%) | 2,685 (36.9%) | 2,202 (30.3%) |
| + Exp 1 (ZIP→State) | 3,194 | 2,484 | 1,596 |
| + Exp 2 (Component) | 4,903 | 775 | 1,596 |
| + Exp 3 (Circuit ID) | 5,050 | 628 | 1,596 |
| + Exp 5 (Peerless addr) | 5,050 | 2,224 | 0 |
| + Exp 4 (MRC) | **6,300** | **974** | **0** |
| + Exp 6+7 (OCR+Nextiva) | **~7,000** | **~274** | **0** |

**Target: 96%+ High Confidence achievable with experiments 1-5 alone (no API key needed)**

---

## Implementation Priority

### Phase 1: Quick Wins (1 hour, +3,000 rows to High)
1. ✅ ZIP→State lookup (Experiment 1)
2. ✅ Peerless default address (Experiment 5)

### Phase 2: Field Mapping (3 hours, +2,000 rows to High)
3. Component Name inference (Experiment 2)
4. Circuit ID mapping (Experiment 3)

### Phase 3: Cost Data (4 hours, +2,000 rows to High)
5. MRC from carrier reports (Experiment 4)

### Phase 4: OCR Enhancement (with API key)
6. Invoice OCR for remaining gaps (Experiment 7)
7. Nextiva address resolution (Experiment 6)
