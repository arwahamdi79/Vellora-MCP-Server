-- =====================================================================
-- Vellora Therapeutics A — Seed Data
-- Run AFTER vellora_database_schema.sql
-- Explicit IDs are used throughout so FK references stay consistent
-- regardless of AUTO_INCREMENT behavior.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. EMPLOYEES (10)
-- ---------------------------------------------------------------------
INSERT INTO Employee (EmployeeID, FullName, Email, Department, Role, AccountStatus) VALUES
(1,  'Alice Mostafa',   'alice.mostafa@vellora.com',   'R&D',                'Researcher',         'Active'),
(2,  'Youssef Hassan',  'youssef.hassan@vellora.com',  'Manufacturing',      'Production Staff',   'Active'),
(3,  'Mona Adel',       'mona.adel@vellora.com',       'Manufacturing',      'Production Staff',   'Active'),
(4,  'Karim Fathy',     'karim.fathy@vellora.com',     'Quality Assurance',  'QA Staff',            'Active'),
(5,  'Nourhan Said',    'nourhan.said@vellora.com',    'Quality Assurance',  'QA Staff',            'Active'),
(6,  'Omar Nabil',      'omar.nabil@vellora.com',      'Quality Assurance',  'QA Staff',            'Active'),
(7,  'Dina Farouk',     'dina.farouk@vellora.com',     'Quality Assurance',  'QA Manager',          'Active'),
(8,  'Ahmed Salah',     'ahmed.salah@vellora.com',     'Operations',         'Operations Manager',  'Active'),
(9,  'Laila Tarek',     'laila.tarek@vellora.com',     'Manufacturing',      'Production Staff',   'Inactive'),
(10, 'Sherif Mahmoud',  'sherif.mahmoud@vellora.com',  'R&D',                'Researcher',         'Active');

-- ---------------------------------------------------------------------
-- 2. MEDICINES (8)
-- ---------------------------------------------------------------------
INSERT INTO Medicine (MedicineID, MedicineName, ActiveIngredient, DosageForm, Strength, ManufacturingStatus) VALUES
(1, 'Parazol 500',    'Paracetamol',              'Tablet',    '500mg',      'Active'),
(2, 'Amoxiclav 625',  'Amoxicillin/Clavulanate',  'Tablet',    '625mg',      'Active'),
(3, 'Insugen Rapid',  'Insulin',                  'Injection', '100IU/ml',   'Active'),
(4, 'Ibuprex 400',    'Ibuprofen',                'Tablet',    '400mg',      'Active'),
(5, 'Ceftrix 1g',     'Ceftriaxone',              'Injection', '1g',         'Active'),
(6, 'Loratadex',      'Loratadine',               'Tablet',    '10mg',       'Active'),
(7, 'Vitasyrup C',    'Vitamin C',                'Syrup',     '100mg/5ml',  'Active'),
(8, 'Metfor 850',     'Metformin',                'Tablet',    '850mg',      'Under Review');

-- ---------------------------------------------------------------------
-- 3. SUPPLIERS (5)
-- ---------------------------------------------------------------------
INSERT INTO Supplier (SupplierID, CompanyName, ContactPerson, Email, PhoneNumber, MaterialSupplied) VALUES
(1, 'PharmaRaw Egypt',        'Hassan Ibrahim',  'contact@pharmaraw-eg.com',    '+20-2-27351122', 'Active Pharmaceutical Ingredients'),
(2, 'ChemSource Ltd',         'Mariam Adel',     'sales@chemsource.com',        '+20-2-25671890', 'Excipients'),
(3, 'GlassPack Industries',   'Tarek Younes',    'orders@glasspack.com',        '+20-2-26654321', 'Packaging Materials'),
(4, 'BioSupply Co.',          'Rania Kamal',     'info@biosupply.com',          '+20-2-24439087', 'Biological Raw Materials'),
(5, 'PurePack Solutions',     'Sameh Fawzy',     'support@purepack.com',        '+20-2-23387765', 'Blister Packaging');

-- ---------------------------------------------------------------------
-- 4. PRODUCTION ORDERS (15)
-- ---------------------------------------------------------------------
INSERT INTO Production_Order (ProductionOrderID, MedicineID, SupplierID, PlannedQuantity, CreationDate, ProductionStatus, ResponsibleEmployeeID) VALUES
(1,  1, 1, 5000, '2026-01-05', 'Completed',   2),
(2,  1, 2, 3000, '2026-02-10', 'Completed',   3),
(3,  2, 1, 4000, '2026-01-15', 'Completed',   2),
(4,  3, 4, 2000, '2026-02-01', 'Completed',   9),
(5,  4, 2, 6000, '2026-03-01', 'In Progress', 2),
(6,  5, 4, 1500, '2026-03-10', 'Completed',   3),
(7,  6, 1, 5000, '2026-01-20', 'Completed',   2),
(8,  7, 2, 8000, '2026-02-15', 'Completed',   9),
(9,  8, 1, 2500, '2026-04-01', 'In Progress', 3),
(10, 1, 3, 4000, '2026-04-10', 'In Progress', 2),
(11, 2, 2, 3500, '2026-03-20', 'Completed',   9),
(12, 4, 1, 5000, '2026-05-01', 'Completed',   2),
(13, 6, 3, 3000, '2026-05-10', 'In Progress', 3),
(14, 3, 4, 1800, '2026-06-01', 'Completed',   9),
(15, 5, 2, 1200, '2026-06-15', 'Pending',     2);

-- ---------------------------------------------------------------------
-- 5. MANUFACTURING BATCHES (20)
-- ---------------------------------------------------------------------
INSERT INTO Manufacturing_Batch (BatchID, ProductionOrderID, MedicineID, ManufacturingDate, ExpiryDate, BatchStatus, CurrentLocation) VALUES
(1,  1,  1, '2026-01-08', '2028-01-08', 'Distributed',    'Distribution Center - Alexandria'),
(2,  1,  1, '2026-01-09', '2028-01-09', 'Approved',       'Warehouse A - Cairo'),
(3,  2,  1, '2026-02-13', '2028-02-13', 'Distributed',    'Distribution Center - Cairo'),
(4,  3,  2, '2026-01-18', '2028-01-18', 'Recalled',       'Distribution Center - Alexandria'),
(5,  3,  2, '2026-01-19', '2028-01-19', 'Approved',       'Warehouse A - Cairo'),
(6,  4,  3, '2026-02-04', '2027-08-04', 'Pending QA',     'Plant 1 - Cold Storage'),
(7,  5,  4, '2026-03-05', '2028-03-05', 'In Production',  'Plant 2 - Production Floor'),
(8,  6,  5, '2026-03-13', '2027-09-13', 'Approved',       'Warehouse A - Cairo'),
(9,  7,  6, '2026-01-23', '2028-01-23', 'Distributed',    'Distribution Center - Giza'),
(10, 7,  6, '2026-01-24', '2028-01-24', 'Recalled',       'Distribution Center - Giza'),
(11, 8,  7, '2026-02-18', '2027-08-18', 'Distributed',    'Distribution Center - Cairo'),
(12, 8,  7, '2026-02-19', '2027-08-19', 'Approved',       'Warehouse B - Cairo'),
(13, 9,  8, '2026-04-04', '2028-04-04', 'Pending QA',     'Plant 1 - Production Floor'),
(14, 10, 1, '2026-04-13', '2028-04-13', 'In Production',  'Plant 2 - Production Floor'),
(15, 11, 2, '2026-03-23', '2028-03-23', 'Distributed',    'Distribution Center - Alexandria'),
(16, 11, 2, '2026-03-24', '2028-03-24', 'Recalled',       'Distribution Center - Alexandria'),
(17, 12, 4, '2026-05-04', '2028-05-04', 'Approved',       'Warehouse A - Cairo'),
(18, 12, 4, '2026-05-05', '2028-05-05', 'Pending QA',     'Plant 2 - Production Floor'),
(19, 13, 6, '2026-05-13', '2028-05-13', 'In Production',  'Plant 1 - Production Floor'),
(20, 14, 3, '2026-06-04', '2027-12-04', 'Rejected',       'Plant 1 - Quarantine');

-- ---------------------------------------------------------------------
-- 6. QUALITY TESTS (40 — 2 per batch)
-- ---------------------------------------------------------------------
INSERT INTO Quality_Test (TestID, BatchID, TestType, TestResult, TestDate, QAEmployeeID, Remarks) VALUES
(1,  1,  'Dissolution Test',     'Pass', '2026-01-10', 4, 'Within acceptable dissolution range'),
(2,  1,  'Assay Test',           'Pass', '2026-01-10', 5, 'Active ingredient content confirmed'),
(3,  2,  'Visual Inspection',    'Pass', '2026-01-11', 6, 'No physical defects observed'),
(4,  2,  'Assay Test',           'Pass', '2026-01-11', 4, 'Within specification'),
(5,  3,  'Dissolution Test',     'Pass', '2026-02-14', 5, 'Meets USP dissolution criteria'),
(6,  3,  'Microbial Limit Test', 'Pass', '2026-02-15', 6, 'No microbial growth detected'),
(7,  4,  'Assay Test',           'Pass', '2026-01-20', 4, 'Initial release test passed'),
(8,  4,  'Stability Test',       'Fail', '2026-01-21', 7, 'Potency degradation found in retained sample post-release'),
(9,  5,  'Assay Test',           'Pass', '2026-01-20', 5, 'Content uniformity confirmed'),
(10, 5,  'Dissolution Test',     'Pass', '2026-01-21', 6, 'Within acceptable range'),
(11, 6,  'Sterility Test',       'Pass', '2026-02-06', 4, 'No microbial contamination'),
(12, 6,  'pH Test',              'Pass', '2026-02-06', 5, 'pH within target range'),
(13, 7,  'Visual Inspection',    'Pass', '2026-03-07', 6, 'Tablets uniform in appearance'),
(14, 7,  'Assay Test',           'Pass', '2026-03-08', 4, 'Awaiting final confirmation'),
(15, 8,  'Sterility Test',       'Pass', '2026-03-15', 5, 'Sterility confirmed'),
(16, 8,  'Potency Test',         'Pass', '2026-03-15', 7, 'Potency within acceptable limits'),
(17, 9,  'Dissolution Test',     'Pass', '2026-01-25', 6, 'Meets dissolution requirements'),
(18, 9,  'Assay Test',           'Pass', '2026-01-25', 4, 'Active ingredient confirmed'),
(19, 10, 'Assay Test',           'Pass', '2026-01-26', 5, 'Initial release passed'),
(20, 10, 'Stability Test',       'Fail', '2026-01-27', 7, 'Impurity levels exceeded limit on stability check'),
(21, 11, 'Visual Inspection',    'Pass', '2026-02-20', 6, 'Syrup clarity acceptable'),
(22, 11, 'pH Test',              'Pass', '2026-02-20', 4, 'pH within specification'),
(23, 12, 'Microbial Limit Test', 'Pass', '2026-02-21', 5, 'No contamination detected'),
(24, 12, 'Assay Test',           'Pass', '2026-02-21', 6, 'Vitamin C content confirmed'),
(25, 13, 'Assay Test',           'Pass', '2026-04-06', 4, 'Content uniformity confirmed'),
(26, 13, 'Dissolution Test',     'Pass', '2026-04-07', 7, 'Awaiting QA manager sign-off'),
(27, 14, 'Visual Inspection',    'Pass', '2026-04-15', 5, 'No visible defects'),
(28, 14, 'Assay Test',           'Pass', '2026-04-16', 6, 'Preliminary result within range'),
(29, 15, 'Dissolution Test',     'Pass', '2026-03-25', 4, 'Meets dissolution criteria'),
(30, 15, 'Microbial Limit Test', 'Pass', '2026-03-26', 5, 'No microbial growth'),
(31, 16, 'Assay Test',           'Pass', '2026-03-26', 6, 'Initial release passed'),
(32, 16, 'Stability Test',       'Fail', '2026-03-27', 7, 'Packaging seal integrity failure identified post-distribution'),
(33, 17, 'Visual Inspection',    'Pass', '2026-05-06', 4, 'Tablets uniform, no chipping'),
(34, 17, 'Assay Test',           'Pass', '2026-05-06', 5, 'Active ingredient content confirmed'),
(35, 18, 'Dissolution Test',     'Pass', '2026-05-07', 6, 'Within range, pending final review'),
(36, 18, 'Assay Test',           'Pass', '2026-05-07', 4, 'Content uniformity confirmed'),
(37, 19, 'Visual Inspection',    'Pass', '2026-05-15', 5, 'No physical defects'),
(38, 19, 'Assay Test',           'Pass', '2026-05-16', 6, 'Preliminary result acceptable'),
(39, 20, 'Sterility Test',       'Fail', '2026-06-06', 7, 'Contamination detected during sterility screening'),
(40, 20, 'Assay Test',           'Fail', '2026-06-06', 4, 'Active ingredient below specification limit');

-- ---------------------------------------------------------------------
-- 7. PRODUCT RECALLS (3)
-- ---------------------------------------------------------------------
INSERT INTO Product_Recall (RecallID, BatchID, RecallDate, RecallReason, RecallStatus, AuthorizedManagerID) VALUES
(1, 4,  '2026-01-30', 'Post-market stability testing revealed potency degradation ahead of labeled expiry.', 'Completed',   7),
(2, 10, '2026-02-05', 'Distributor-reported impurity levels exceeded acceptable limits on stability retest.', 'Completed',   7),
(3, 16, '2026-04-01', 'Packaging seal integrity failure identified after distribution, risking contamination.', 'In Progress', 8);

-- ---------------------------------------------------------------------
-- 8. COMPANY POLICIES (resources, not tools)
-- ---------------------------------------------------------------------
INSERT INTO Company_Policy (PolicyID, PolicyTitle, PolicyCategory, DocumentContent, LastUpdatedDate) VALUES
(1, 'Batch Approval Policy', 'Quality Assurance',
   'A manufacturing batch may only be marked Approved after all required quality tests for its dosage form have returned a Pass result and a QA Manager has countersigned the batch record. Any single Fail result places the batch in Rejected status pending investigation.',
   '2026-01-02'),
(2, 'Product Recall Procedure', 'Quality Assurance',
   'Recalls may be initiated by a QA Manager or Operations Manager upon confirmed evidence of a quality defect, whether identified internally or reported by a distributor. Each recall must record the affected batch, the reason, and be tracked through Initiated, In Progress, and Completed stages.',
   '2026-01-02'),
(3, 'Manufacturing Standard Operating Procedure (SOP)', 'Manufacturing',
   'All production orders must specify the responsible employee, source supplier, and planned quantity before manufacturing begins. Batches generated from an order inherit the parent medicine specification and must be logged with manufacturing and expiry dates at the time of production.',
   '2026-01-02'),
(4, 'Drug Storage Guidelines', 'Operations',
   'Temperature-sensitive products such as injections must be stored in designated cold storage locations at all times, including during quality testing. Tablets and syrups may be stored in standard warehouse conditions unless otherwise specified on the medicine record.',
   '2026-01-02');