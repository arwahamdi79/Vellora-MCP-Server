"""
planning_eval/db_report.py — sizing report for the planning problem.

Run:  python -m planning_eval.db_report --db db/vellora.db

Answers the question "is there enough real structure here for the impact trace
to be non-trivial?" -- i.e. do production orders actually have multiple batches,
do suppliers actually serve multiple orders, and is there any batch that failed
QA and has NOT yet been contained.
"""

from __future__ import annotations

import argparse
import sqlite3

DEFAULT_DB = "db/vellora.db"


def report(db_path: str) -> None:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    q = lambda sql, a=(): list(conn.execute(sql, a))  # noqa: E731

    print("=" * 68)
    print("ROW COUNTS")
    print("=" * 68)
    for t in ("Employee", "Medicine", "Supplier", "Production_Order",
              "Manufacturing_Batch", "Quality_Test", "Product_Recall",
              "Company_Policy"):
        print(f"  {t:22s} {q(f'SELECT COUNT(*) c FROM {t}')[0]['c']}")

    print("\n" + "=" * 68)
    print("BATCH STATUS DISTRIBUTION")
    print("=" * 68)
    for r in q("""SELECT BatchStatus, COUNT(*) c FROM Manufacturing_Batch
                  GROUP BY BatchStatus ORDER BY c DESC"""):
        print(f"  {r['BatchStatus']:18s} {r['c']}")

    print("\n" + "=" * 68)
    print("BATCHES PER PRODUCTION ORDER  (sibling cohort size)")
    print("=" * 68)
    for r in q("""SELECT n, COUNT(*) orders FROM (
                    SELECT ProductionOrderID, COUNT(*) n
                      FROM Manufacturing_Batch GROUP BY ProductionOrderID)
                  GROUP BY n ORDER BY n"""):
        print(f"  {r['n']} batch(es) per order : {r['orders']} order(s)")

    print("\n" + "=" * 68)
    print("ORDERS PER SUPPLIER  (supplier-linked cohort reach)")
    print("=" * 68)
    for r in q("""SELECT o.SupplierID, s.CompanyName,
                         COUNT(DISTINCT o.ProductionOrderID) orders,
                         COUNT(b.BatchID) batches
                    FROM Production_Order o
                    JOIN Supplier s ON s.SupplierID = o.SupplierID
               LEFT JOIN Manufacturing_Batch b
                      ON b.ProductionOrderID = o.ProductionOrderID
                GROUP BY o.SupplierID ORDER BY batches DESC"""):
        print(f"  supplier {r['SupplierID']:<3} {r['CompanyName'][:24]:24s} "
              f"{r['orders']} order(s), {r['batches']} batch(es)")

    print("\n" + "=" * 68)
    print("UNCONTAINED QA FAILURES  (an open deviation to plan around)")
    print("=" * 68)
    rows = q("""SELECT q.BatchID, q.TestType, q.TestDate, b.BatchStatus
                  FROM Quality_Test q
                  JOIN Manufacturing_Batch b ON b.BatchID = q.BatchID
                 WHERE q.TestResult = 'Fail'
                   AND b.BatchStatus NOT IN ('Rejected', 'Recalled')""")
    if rows:
        for r in rows:
            print(f"  BatchID={r['BatchID']} {r['TestType']} {r['TestDate']} "
                  f"status={r['BatchStatus']}")
    else:
        print("  NONE. Every QA failure is already contained, so there is no")
        print("  live deviation for the agent to plan. Seed one before running")
        print("  the evaluation.")

    print("\n" + "=" * 68)
    print("EMPLOYEE ROLES")
    print("=" * 68)
    for r in q("""SELECT Role, AccountStatus, COUNT(*) c FROM Employee
                  GROUP BY Role, AccountStatus ORDER BY Role"""):
        print(f"  {r['Role']:20s} {r['AccountStatus']:9s} {r['c']}")

    print("\n" + "=" * 68)
    print("MEDICINES WITH MOST BATCHES  (shortfall candidates)")
    print("=" * 68)
    for r in q("""SELECT m.MedicineID, m.MedicineName, COUNT(b.BatchID) n
                    FROM Medicine m
               LEFT JOIN Manufacturing_Batch b ON b.MedicineID = m.MedicineID
                GROUP BY m.MedicineID ORDER BY n DESC LIMIT 8"""):
        print(f"  {r['MedicineID']:<4} {r['MedicineName'][:30]:30s} {r['n']}")

    conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DEFAULT_DB)
    report(p.parse_args().db)
