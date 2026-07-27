# Product Recall Procedure

**Policy Category:** Quality Assurance
**Applies to:** Manufacturing Batches that have left the `Pending QA` stage
**Last Updated:** 2026-01-02

## 1. Purpose

This procedure governs how Vellora Therapeutics A identifies, records, and manages the recall of a manufacturing batch after a quality or safety defect is discovered — including defects found after the batch has already been Approved or Distributed.

## 2. When a Recall Is Initiated

A recall may be initiated for any batch, regardless of its current status, when one or more of the following occurs:

- Post-market stability testing reveals degradation (e.g. potency loss) not detected during original release testing.
- A distributor, pharmacy, or patient reports a suspected defect, contamination, or packaging failure.
- A routine audit of a retained sample uncovers a result outside specification.
- A supplier issue is discovered that affects raw material integrity across one or more batches.

## 3. Authorization

Only the following roles may authorize a recall:

- **QA Manager**
- **Operations Manager**

A recall record cannot be created without one of these roles listed as the Authorized Manager. Production Staff, Researchers, and QA Staff may flag a suspected issue, but cannot open a recall themselves.

## 4. Procedure Steps

1. **Flag the issue.** Any employee who identifies a potential defect notifies a QA Manager or Operations Manager immediately.
2. **Investigate.** The QA Manager reviews the batch's Quality Test history, manufacturing records, and any supplier information linked to the originating Production Order.
3. **Open the recall record.** If the investigation confirms a defect, a Product Recall record is created, capturing:
   - The affected Batch ID
   - The Recall Date
   - A documented Recall Reason
   - The Authorized Manager
4. **Update batch status.** The batch's status is changed to `Recalled`. A recalled batch can never be moved back to `Approved` or `Distributed`.
5. **Track progress.** The Recall Status moves through three stages:
   - `Initiated` — the recall has been opened and notifications are going out.
   - `In Progress` — affected units are being retrieved or contained.
   - `Completed` — all affected units have been accounted for and the recall is closed.

## 5. Scope of a Recall

Each recall record applies to exactly one batch. If a defect is traced to a systemic issue (e.g. a faulty supplier shipment), a separate recall record must be opened for every affected batch, even if the root cause is shared.

## 6. Documentation Requirements

The Recall Reason must be specific and evidence-based — referencing the triggering event (e.g. a failed stability retest, a distributor complaint, a packaging audit finding) rather than a generic description. This record becomes part of the batch's permanent quality history.

## 7. Related Policies

- Batch Approval Policy
- Drug Storage Guidelines