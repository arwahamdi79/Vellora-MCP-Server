-- =====================================================================
-- db/seed_deviation.sql
-- Seeds ONE open QA deviation for the Deviation Response Agent (Week 4).
--
-- ADDITIVE ONLY. No existing row is modified or deleted, so the Week 1-3
-- demos, the memory/RAG evaluation and the database tests all keep passing.
-- Every id is explicit so the scenario is reproducible and the frozen test
-- suite can reference it.
--
-- Run:   sqlite3 db/vellora.db < db/seed_deviation.sql
-- Verify: python -m planning_eval.db_report --db db/vellora.db
--         (the "UNCONTAINED QA FAILURES" section should now list BatchID 21)
--
-- ---------------------------------------------------------------------
-- THE SCENARIO
-- ---------------------------------------------------------------------
-- Batch 21 (Ibuprex 400, Distributed to Alexandria) fails a Sterility Test.
-- Its production order 17 sourced material from Supplier 1 (PharmaRaw Egypt).
--
-- The impact trace must find:
--   * sibling cohort  — batch 22, same ProductionOrderID 17
--   * supplier cohort — batches 23 and 25, other orders using Supplier 1
--                       inside the 14-day manufacturing window
--   * NOT batch 24    — same window, same medicine, but Supplier 2. A model
--                       that contains by medicine instead of by material
--                       over-scopes here, and that costs saleable stock.
--
-- Four traps, each caught by exactly one grounded check:
--   1. batch 23 is Distributed  -> needs a Product_Recall, not a rejection
--   2. batch 22 is Approved     -> needs a rejection, not a recall
--   3. batch 25 is already Recalled and already has a Product_Recall row.
--      Product_Recall.BatchID is UNIQUE, so it can be neither recalled again
--      nor rejected. It belongs in the WATCH list. This is the subtle one.
--   4. replacement orders must not re-source from Supplier 1.
--
-- Plus the two traps already latent in the Employee table: only EmployeeID 7
-- (Dina Farouk) is an Active QA Manager, and one Production Staff member is
-- Inactive.
-- =====================================================================

BEGIN TRANSACTION;

-- ---------------------------------------------------------------------
-- Production orders. Employee ids are resolved by role so this script does
-- not hardcode ids it cannot see.
-- ---------------------------------------------------------------------
INSERT INTO Production_Order
    (ProductionOrderID, MedicineID, SupplierID, PlannedQuantity,
     CreationDate, ProductionStatus, ResponsibleEmployeeID)
VALUES
    -- implicated order: Ibuprex 400 from PharmaRaw Egypt
    (17, 4, 1, 6000, '2026-07-20', 'Completed',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'Production Staff' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1)),
    -- same supplier, different medicine, inside the window
    (18, 6, 1, 4000, '2026-07-22', 'Completed',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'Production Staff' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1)),
    -- CONTROL: same medicine and window, DIFFERENT supplier. Must not be
    -- contained. Catches agents that scope by medicine instead of material.
    (19, 4, 2, 3000, '2026-07-21', 'Completed',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'Production Staff' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1)),
    -- same supplier, already dealt with in a prior deviation
    (20, 6, 1, 2500, '2026-07-23', 'Completed',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'Production Staff' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1));

-- ---------------------------------------------------------------------
-- Batches
-- ---------------------------------------------------------------------
INSERT INTO Manufacturing_Batch
    (BatchID, ProductionOrderID, MedicineID, ManufacturingDate,
     ExpiryDate, BatchStatus, CurrentLocation)
VALUES
    -- THE FAILED BATCH — reached customers, so containment means a recall
    (21, 17, 4, '2026-07-25', '2028-07-25', 'Distributed',
     'Distribution Center - Alexandria'),
    -- sibling, still inside the plant -> rejection, not recall
    (22, 17, 4, '2026-07-26', '2028-07-26', 'Approved',
     'Warehouse A - Cairo'),
    -- supplier-linked, distributed -> recall
    (23, 18, 6, '2026-07-28', '2028-07-28', 'Distributed',
     'Distribution Center - Giza'),
    -- CONTROL, supplier 2 -> must stay out of the containment set
    (24, 19, 4, '2026-07-27', '2028-07-27', 'Distributed',
     'Distribution Center - Cairo'),
    -- supplier-linked but ALREADY recalled -> belongs in WATCH, nothing else
    (25, 20, 6, '2026-07-29', '2028-07-29', 'Recalled',
     'Distribution Center - Giza');

-- ---------------------------------------------------------------------
-- Quality tests. Batch 21 fails; the others pass, so the failure is
-- specific rather than a blanket signal.
-- ---------------------------------------------------------------------
INSERT INTO Quality_Test
    (TestID, BatchID, TestType, TestResult, TestDate, QAEmployeeID, Remarks)
VALUES
    (42, 21, 'Sterility Test', 'Fail', '2026-08-10',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'QA Staff' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1),
     'Microbial growth observed in two of six settle plates. Excursion traced to the raw material intake for this production order.'),
    (43, 22, 'Assay Test', 'Pass', '2026-07-30',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'QA Staff' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1),
     'Within specification.'),
    (44, 23, 'Assay Test', 'Pass', '2026-08-01',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'QA Staff' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1),
     'Within specification. Note: shares raw material intake with order 17.'),
    (45, 24, 'Assay Test', 'Pass', '2026-08-02',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'QA Staff' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1),
     'Within specification.');

-- ---------------------------------------------------------------------
-- The pre-existing recall on batch 25. This is what makes a second recall
-- impossible (Product_Recall.BatchID is UNIQUE) and forces batch 25 into
-- the WATCH tier.
-- ---------------------------------------------------------------------
INSERT INTO Product_Recall
    (RecallID, BatchID, RecallDate, RecallReason, RecallStatus,
     AuthorizedManagerID)
VALUES
    (4, 25, '2026-08-05',
     'Packaging integrity deviation identified during distribution audit.',
     'In Progress',
     (SELECT EmployeeID FROM Employee
       WHERE Role = 'QA Manager' AND AccountStatus = 'Active'
       ORDER BY EmployeeID LIMIT 1));

COMMIT;

-- =====================================================================
-- EXPECTED CORRECT CONTAINMENT PLAN (the answer the grounded environment
-- accepts; kept here as documentation, NOT used by the agent)
--
--   recall_batch_ids  : [21, 23]        both Distributed
--   reject_batch_ids  : [22]            Approved, still inside the plant
--   watch_batch_ids   : [25]            already recalled, cannot be re-recalled
--   authorizer        : the Active QA Manager (Dina Farouk), never QA Staff
--   replacement orders: medicines 4 and 6 from any supplier EXCEPT 1,
--                       owned by an ACTIVE Production Staff member
--   batch 24          : absent from every list — different supplier
-- =====================================================================
