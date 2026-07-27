# Batch Approval Policy

**Policy Category:** Quality Assurance
**Applies to:** All Manufacturing Batches produced at Vellora Therapeutics A
**Last Updated:** 2026-01-02

## 1. Purpose

This policy defines the conditions under which a Manufacturing Batch may move from production into an Approved state, making it eligible for distribution. It exists to guarantee that no batch reaches a patient without documented evidence that it meets Vellora's quality standards.

## 2. Scope

This policy applies to every batch generated from a Production Order, regardless of dosage form, medicine, or production line. It governs the transition between the following Batch Status values: `In Production`, `Pending QA`, `Approved`, and `Rejected`.

## 3. Policy Statement

A batch may only be marked **Approved** when all of the following conditions are met:

1. The batch has completed every Quality Test required for its dosage form (see Section 4).
2. Every recorded Quality Test for the batch shows a **Pass** result.
3. A QA Manager has reviewed the full test record and countersigned the batch approval.
4. The batch's Expiry Date has been confirmed and is later than its Manufacturing Date.

If any Quality Test returns a **Fail** result, the batch must be moved to **Rejected** status. A Rejected batch may not be distributed, and may not be re-tested into an Approved state — a new batch must be produced.

## 4. Minimum Required Tests by Dosage Form

| Dosage Form | Minimum Required Tests |
|---|---|
| Tablet / Capsule | Assay Test, Dissolution Test, Visual Inspection |
| Injection | Assay Test, Sterility Test, pH Test |
| Syrup | Assay Test, Microbial Limit Test, Visual Inspection |

Additional tests (e.g. Stability Test, Potency Test) may be requested by QA Staff at their discretion and, once recorded, are subject to the same Pass/Fail rule above.

## 5. Roles and Responsibilities

- **QA Staff** perform individual Quality Tests and record results, including remarks explaining any anomaly.
- **QA Manager** reviews the complete set of test results for a batch and issues final approval or rejection. Only a QA Manager may transition a batch into `Approved` status.
- **Production Staff** may not approve, reject, or alter the status of a batch under any circumstance.

## 6. Escalation

If a batch already marked `Approved` is later found to have a quality issue (via post-market surveillance, a distributor report, or a retained-sample retest), it does not revert to `Rejected`. Instead, the **Product Recall Procedure** governs the next steps.

## 7. Related Policies

- Product Recall Procedure
- Manufacturing Standard Operating Procedure (SOP)