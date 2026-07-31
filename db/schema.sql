-- =====================================================================
-- Vellora Therapeutics A — Database Schema
-- Based on ERD v1 
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. EMPLOYEE
-- ---------------------------------------------------------------------
CREATE TABLE Employee (
    EmployeeID      INTEGER PRIMARY KEY AUTOINCREMENT,
    FullName        VARCHAR(150) NOT NULL,
    Email           VARCHAR(150) NOT NULL UNIQUE,
    Department      VARCHAR(100) NOT NULL,
    Role            VARCHAR(50) NOT NULL
        CHECK (Role IN ('Researcher', 'Production Staff', 'QA Staff', 'QA Manager', 'Operations Manager')),
    AccountStatus   VARCHAR(20) NOT NULL DEFAULT 'Active'
        CHECK (AccountStatus IN ('Active', 'Inactive'))
);

-- ---------------------------------------------------------------------
-- 2. MEDICINE
-- ---------------------------------------------------------------------
CREATE TABLE Medicine (
    MedicineID          INTEGER PRIMARY KEY AUTOINCREMENT,
    MedicineName        VARCHAR(150) NOT NULL,
    ActiveIngredient     VARCHAR(150) NOT NULL,
    DosageForm           VARCHAR(50) NOT NULL
        CHECK (DosageForm IN ('Tablet', 'Capsule', 'Injection', 'Syrup', 'Ointment', 'Other')),
    Strength             VARCHAR(50) NOT NULL,
    ManufacturingStatus  VARCHAR(30) NOT NULL DEFAULT 'Active'
        CHECK (ManufacturingStatus IN ('Active', 'Discontinued', 'Under Review'))
);

-- ---------------------------------------------------------------------
-- 3. SUPPLIER
-- ---------------------------------------------------------------------
CREATE TABLE Supplier (
    SupplierID       INTEGER PRIMARY KEY AUTOINCREMENT,
    CompanyName      VARCHAR(150) NOT NULL,
    ContactPerson    VARCHAR(150) NOT NULL,
    Email            VARCHAR(150) NOT NULL UNIQUE,
    PhoneNumber      VARCHAR(20) NOT NULL,
    MaterialSupplied VARCHAR(150) NOT NULL
);

-- ---------------------------------------------------------------------
-- 4. PRODUCTION_ORDER
-- ---------------------------------------------------------------------
CREATE TABLE Production_Order (
    ProductionOrderID     INTEGER PRIMARY KEY AUTOINCREMENT,
    MedicineID            INT NOT NULL,
    SupplierID            INT NOT NULL,
    PlannedQuantity        INT NOT NULL CHECK (PlannedQuantity > 0),
    CreationDate           DATE NOT NULL DEFAULT (CURRENT_DATE),
    ProductionStatus       VARCHAR(30) NOT NULL DEFAULT 'Pending'
        CHECK (ProductionStatus IN ('Pending', 'In Progress', 'Completed', 'Cancelled')),
    ResponsibleEmployeeID  INT NOT NULL,

    CONSTRAINT fk_order_medicine
        FOREIGN KEY (MedicineID) REFERENCES Medicine(MedicineID),
    CONSTRAINT fk_order_supplier
        FOREIGN KEY (SupplierID) REFERENCES Supplier(SupplierID),
    CONSTRAINT fk_order_employee
        FOREIGN KEY (ResponsibleEmployeeID) REFERENCES Employee(EmployeeID)
);

-- ---------------------------------------------------------------------
-- 5. MANUFACTURING_BATCH
-- ---------------------------------------------------------------------
CREATE TABLE Manufacturing_Batch (
    BatchID            INTEGER PRIMARY KEY AUTOINCREMENT,
    ProductionOrderID  INT NOT NULL,
    MedicineID         INT NOT NULL,
    ManufacturingDate  DATE NOT NULL,
    ExpiryDate         DATE NOT NULL,
    BatchStatus        VARCHAR(30) NOT NULL DEFAULT 'In Production'
        CHECK (BatchStatus IN ('In Production', 'Pending QA', 'Approved', 'Rejected', 'Distributed', 'Recalled')),
    CurrentLocation    VARCHAR(150),

    CONSTRAINT fk_batch_order
        FOREIGN KEY (ProductionOrderID) REFERENCES Production_Order(ProductionOrderID),
    CONSTRAINT fk_batch_medicine
        FOREIGN KEY (MedicineID) REFERENCES Medicine(MedicineID),
    CONSTRAINT chk_batch_dates
        CHECK (ExpiryDate > ManufacturingDate)
);

-- ---------------------------------------------------------------------
-- 6. QUALITY_TEST
-- ---------------------------------------------------------------------
CREATE TABLE Quality_Test (
    TestID        INTEGER PRIMARY KEY AUTOINCREMENT,
    BatchID       INT NOT NULL,
    TestType      VARCHAR(100) NOT NULL,
    TestResult    VARCHAR(10) NOT NULL
        CHECK (TestResult IN ('Pass', 'Fail')),
    TestDate      DATE NOT NULL DEFAULT (CURRENT_DATE),
    QAEmployeeID  INT NOT NULL,
    Remarks       VARCHAR(500),

    CONSTRAINT fk_test_batch
        FOREIGN KEY (BatchID) REFERENCES Manufacturing_Batch(BatchID),
    CONSTRAINT fk_test_employee
        FOREIGN KEY (QAEmployeeID) REFERENCES Employee(EmployeeID)
);

-- ---------------------------------------------------------------------
-- 7. PRODUCT_RECALL
-- ---------------------------------------------------------------------
CREATE TABLE Product_Recall (
    RecallID            INTEGER PRIMARY KEY AUTOINCREMENT,
    BatchID             INT NOT NULL UNIQUE,   -- one-to-zero/one with Manufacturing_Batch
    RecallDate          DATE NOT NULL DEFAULT (CURRENT_DATE),
    RecallReason        VARCHAR(500) NOT NULL,
    RecallStatus        VARCHAR(30) NOT NULL DEFAULT 'Initiated'
        CHECK (RecallStatus IN ('Initiated', 'In Progress', 'Completed')),
    AuthorizedManagerID INT NOT NULL,

    CONSTRAINT fk_recall_batch
        FOREIGN KEY (BatchID) REFERENCES Manufacturing_Batch(BatchID),
    CONSTRAINT fk_recall_manager
        FOREIGN KEY (AuthorizedManagerID) REFERENCES Employee(EmployeeID)
);

-- ---------------------------------------------------------------------
-- 8. COMPANY_POLICY  (exposed as MCP Resources, not tools — standalone)
-- ---------------------------------------------------------------------
CREATE TABLE Company_Policy (
    PolicyID         INTEGER PRIMARY KEY AUTOINCREMENT,
    PolicyTitle      VARCHAR(200) NOT NULL,
    PolicyCategory   VARCHAR(100) NOT NULL,
    DocumentContent  TEXT NOT NULL,
    LastUpdatedDate  DATE NOT NULL DEFAULT (CURRENT_DATE)
);

-- =====================================================================
-- Indexes to support common lookups (batches by status, tests by batch,
-- orders by employee, etc.)
-- =====================================================================
CREATE INDEX idx_order_medicine       ON Production_Order(MedicineID);
CREATE INDEX idx_order_supplier       ON Production_Order(SupplierID);
CREATE INDEX idx_order_employee       ON Production_Order(ResponsibleEmployeeID);
CREATE INDEX idx_batch_order          ON Manufacturing_Batch(ProductionOrderID);
CREATE INDEX idx_batch_medicine       ON Manufacturing_Batch(MedicineID);
CREATE INDEX idx_batch_status         ON Manufacturing_Batch(BatchStatus);
CREATE INDEX idx_test_batch           ON Quality_Test(BatchID);
CREATE INDEX idx_test_employee        ON Quality_Test(QAEmployeeID);
CREATE INDEX idx_recall_manager       ON Product_Recall(AuthorizedManagerID);