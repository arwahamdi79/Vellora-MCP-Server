# Manufacturing Standard Operating Procedure (SOP)

**Policy Category:** Manufacturing
**Applies to:** Production Orders and Manufacturing Batches
**Last Updated:** 2026-01-02

## 1. Purpose

This SOP defines the required steps and data that must be captured from the moment a medicine is requested for production through to the creation of a manufacturing batch, ensuring traceability from raw material to finished batch.

## 2. Creating a Production Order

Before any manufacturing activity begins, a Production Order must be created and must specify:

- The **Medicine** being produced (must already exist in the Medicine catalog)
- The **Supplier** providing the raw materials for this run
- The **Planned Quantity** (must be a positive number)
- The **Responsible Employee** overseeing the run — must be an active employee in the Production Staff role or higher
- A **Creation Date**

A Production Order starts in `Pending` status and moves to `In Progress` once manufacturing activity begins on the floor.

## 3. Generating a Manufacturing Batch

A single Production Order may generate one or more Manufacturing Batches, depending on production line capacity and quantity. Each batch generated from an order must record:

- The **originating Production Order**
- The **Medicine** being manufactured (must match the parent order's medicine)
- The **Manufacturing Date**
- The **Expiry Date**, which must always be later than the Manufacturing Date
- The **Current Location**, tracked from the point of manufacture through storage and distribution

A new batch always starts in `In Production` status.

## 4. Handoff to Quality Assurance

Once physical production of a batch is complete, its status moves to `Pending QA`, and it is handed to QA Staff for testing per the **Batch Approval Policy**. Production Staff may not skip this handoff step or move a batch directly to `Approved` or `Distributed`.

## 5. Location Tracking

The Current Location field on a batch must be updated at each major transition:

- Production floor (e.g. "Plant 1 - Production Floor")
- Quarantine, if awaiting QA disposition
- Warehouse, once Approved
- Distribution center, once shipped

Injections and other temperature-sensitive dosage forms must additionally follow the **Drug Storage Guidelines** during every stage of this handoff.

## 6. Order Completion

A Production Order is marked `Completed` once all batches generated from it have reached a final status (`Approved`, `Rejected`, `Distributed`, or `Recalled`). An order may be marked `Cancelled` only before any batch has entered `Pending QA`.

## 7. Related Policies

- Batch Approval Policy
- Drug Storage Guidelines