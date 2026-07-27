# Database Testing

## Purpose

The purpose of these tests is to verify that the Vellora Therapeutics A database behaves correctly, enforces business rules, and maintains data integrity through constraints and foreign keys.

---

# Test 1 – Insert a New Employee

### SQL

```sql
INSERT INTO Employee
(FullName, Email, Department, Role, AccountStatus)
VALUES
(
'John Smith',
'john.smith@vellora.com',
'Research',
'Researcher',
'Active'
);
```

### Expected Result

- Employee is inserted successfully.
- A new EmployeeID is generated.

**Status:** ✅ Passed

---

# Test 2 – Invalid Employee Role

### SQL

```sql
INSERT INTO Employee
(FullName, Email, Department, Role, AccountStatus)
VALUES
(
'John Smith',
'john.smith@vellora.com',
'Research',
'CEO',
'Active'
);
```

### Expected Result

The database rejects the insertion because "CEO" is not an allowed role.

**Status:** ✅ Passed

---

# Test 3 – Create Production Order

### SQL

```sql
INSERT INTO Production_Order
(
MedicineID,
SupplierID,
PlannedQuantity,
ResponsibleEmployeeID
)
VALUES
(
1,
1,
5000,
3
);
```

### Expected Result

Production order is created successfully.

**Status:** ✅ Passed

---

# Test 4 – Invalid Medicine ID

### SQL

```sql
INSERT INTO Production_Order
(
MedicineID,
SupplierID,
PlannedQuantity,
ResponsibleEmployeeID
)
VALUES
(
999,
1,
5000,
3
);
```

### Expected Result

Foreign key constraint prevents insertion because the medicine does not exist.

**Status:** ✅ Passed

---

# Test 5 – Invalid Batch Dates

### SQL

```sql
INSERT INTO Manufacturing_Batch
(
ProductionOrderID,
MedicineID,
ManufacturingDate,
ExpiryDate,
BatchStatus
)
VALUES
(
1,
1,
'2026-12-01',
'2025-12-01',
'Pending QA'
);
```

### Expected Result

Database rejects the record because ExpiryDate must be after ManufacturingDate.

**Status:** ✅ Passed

---

# Test 6 – Invalid Quality Test Result

### SQL

```sql
INSERT INTO Quality_Test
(
BatchID,
TestType,
TestResult,
QAEmployeeID
)
VALUES
(
1,
'Purity Test',
'Excellent',
4
);
```

### Expected Result

Database rejects the record because TestResult must be either 'Pass' or 'Fail'.

**Status:** ✅ Passed

---

# Test 7 – Product Recall

### SQL

```sql
INSERT INTO Product_Recall
(
BatchID,
RecallReason,
AuthorizedManagerID
)
VALUES
(
5,
'Packaging defect',
8
);
```

### Expected Result

Recall is successfully created.

**Status:** ✅ Passed

---

# Test 8 – Duplicate Recall

### SQL

```sql
INSERT INTO Product_Recall
(
BatchID,
RecallReason,
AuthorizedManagerID
)
VALUES
(
5,
'Labeling issue',
8
);
```

### Expected Result

Database rejects the insertion because each batch can only have one recall.

**Status:** ✅ Passed

---

# Summary

All database constraints, primary keys, foreign keys, and validation rules were tested successfully. The database correctly prevents invalid data while allowing valid pharmaceutical manufacturing records to be stored.