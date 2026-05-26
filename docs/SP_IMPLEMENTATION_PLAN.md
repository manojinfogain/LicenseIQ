# LicenseIQ — Stored Procedure Implementation Plan

**Last Updated:** May 15, 2026  
**Status:** Implementation Starting — Phase 1  
**Scope:** Convert 31 ORM/inline DB queries to 25 optimized stored procedures

---

## Executive Summary

LicenseIQ currently uses SQLAlchemy ORM for all database operations. This plan migrates all **31 LicenseIQ-database transactions** to optimized stored procedures, reducing latency, improving atomicity, and centralizing business logic. Implementation spans 4 phases (6 weeks).

**Key improvements:**
- ✅ Eliminate N+1 query patterns (esp. dashboard bootstrap)
- ✅ Atomic transactions for complex workflows (approvals, queue execution)
- ✅ Reduce ORM overhead (20-30% latency improvement expected)
- ✅ Deduplicated queries (6 merged SPs, 31 → 25 total)
- ✅ Enhanced security (parameterized, prevents SQL injection)

---

## Current State Analysis

### Existing SPs (5)
| SP Name | Database | Purpose |
|---------|----------|---------|
| `usp_GetDashboardSummaryMetrics` | LicenseIQ | Dashboard metric aggregation |
| `usp_GetAspireExitEvents` | Aspire | Exit event detection |
| `usp_GetAspireProjectReleaseEvents` | Aspire | Project release detection |
| `usp_GetAspireReleaseReasons` | Aspire | Release reason lookup |
| `usp_GetAspireBenchEvents` | Aspire | Bench placement detection |

### ORM/Inline Queries (31)
| Category | Count | Notes |
|----------|-------|-------|
| Read-only SELECTs | 18 | Low risk, can batch |
| Platform CRUD | 3 | Medium risk, simple |
| Request lifecycle | 4 | High risk, multi-step |
| Queue execution | 6 | Highest risk, business logic |

---

## Optimization Strategy

### 1. Eliminate Duplicate Queries
**Consolidations:**
- Dashboard: 8 separate SELECTs → `usp_GetDashboardComplete` (1 call)
- Employee lookup: 2-step (resolve → find alloc) → `usp_FindActiveAllocationByCode` (1 call)
- Revoke + alert resolve: 2 calls → single SP with CTE

**Python-side caching:**
- Cache `(staffid, role)` in session after login → no re-querying role per request
- Pass role as parameter instead of querying EmployeeWiseRoleMapping again

### 2. Atomic Transactions
**Complex workflows moved to SP:**
- Request approval workflow: INSERT history + UPDATE stage + UPDATE queue → single transaction
- Queue execution (assign/revoke): INSERT allocation/audit + UPDATE status + resolve alerts → atomic
- Prevents race conditions and partial updates

### 3. Index Strategy
**Required indexes:**
```sql
CREATE INDEX idx_LicenseAllocation_EmployeeStatus ON LicenseAllocation (employee_id, status, revoked_date)
CREATE INDEX idx_Alert_EmployeeStatus ON Alert (employee_id, status, created_at DESC)
CREATE INDEX idx_EmployeeWiseRoleMapping_StaffId ON EmployeeWiseRoleMapping (emp_staffid, is_active)
CREATE INDEX idx_QueueItem_EmployeePlatformStatus ON QueueItem (employee_id, platform_id, action_type, status)
CREATE INDEX idx_LicenseRequest_EmployeeStatus ON LicenseRequest (employee_id, approval_status, created_at DESC)
```

### 4. Parameter Handling
**For large IN() lists (SQL Server 2100 param limit):**
- Use **Table-Valued Parameters (TVP)** instead of chunking in Python
- Define: `CREATE TYPE IntList AS TABLE (value INT PRIMARY KEY)`
- SP accepts `@EmployeeIds IntList READONLY`
- Query: `WHERE employee_id IN (SELECT value FROM @EmployeeIds)`

---

## Deduplicated SP Catalog (25 total)

### Phase 1 — Read-only SELECTs (12 SPs) · Low Risk

| # | SP Name | Replaces | Est. Dev |
|---|---------|----------|----------|
| 1 | `usp_GetDashboardComplete` | 8 queries | 3h |
| 2 | `usp_GetPlatformById` | `db.get(Platform, id)` | 0.5h |
| 3 | `usp_GetOpenAlerts` | Alert + alloc join | 1h |
| 4 | `usp_GetManualAlerts` | Pending LicenseRequest | 0.5h |
| 5 | `usp_GetLicenseRequests` | LicenseRequest list | 0.5h |
| 6 | `usp_GetLicenseRequestById` | Single request | 0.5h |
| 7 | `usp_GetApprovalHistory` | Approval history + role | 1h |
| 8 | `usp_GetPendingQueueItems` | Queue list | 0.5h |
| 9 | `usp_FindActiveAllocationByCode` | Merged: code→alloc | 1h |
| 10 | `usp_FindPendingRequest` | Pending request lookup | 0.5h |
| 11 | `usp_FindPendingQueueItem` | Pending queue lookup | 0.5h |
| 12 | `usp_CheckOpenAlertExists` | Alert exists check | 0.5h |

**Total:** 10h dev + 2h testing = 12h

### Phase 2 — Platform CRUD (3 SPs) · Medium Risk

| # | SP Name | Est. Dev |
|---|---------|----------|
| 13 | `usp_CreatePlatform` | 1h |
| 14 | `usp_UpdatePlatform` | 1h |
| 15 | `usp_DeletePlatform` | 1.5h |

**Total:** 3.5h dev + 1h testing = 4.5h

### Phase 3 — Request Lifecycle (4 SPs) · High Risk

| # | SP Name | Est. Dev |
|---|---------|----------|
| 16 | `usp_CreateLicenseRequest` | 2h |
| 17 | `usp_ApproveLicenseRequest` | 1.5h |
| 18 | `usp_FinalApproveLicenseRequest` | 2h |
| 19 | `usp_RejectLicenseRequest` | 1h |

**Total:** 6.5h dev + 2h testing = 8.5h

### Phase 4 — Queue Execution + Alerts (6 SPs) · Very High Risk

| # | SP Name | Est. Dev |
|---|---------|----------|
| 20 | `usp_CreateManualQueueItem` | 1h |
| 21 | `usp_ExecuteAssignQueueItem` | 2.5h |
| 22 | `usp_ExecuteRevokeQueueItem` | 2.5h |
| 23 | `usp_RejectQueueItem` | 0.5h |
| 24 | `usp_CreateSmartAlert` | 0.5h |
| 25 | `usp_GetRoleMapping` | 0.5h |

**Total:** 7.5h dev + 2.5h testing = 10h

---

## Implementation Timeline

### Week 1 — Phase 1 (Read-only)
- **Mon-Tue:** Create all 12 SP definitions
- **Wed:** Peer review
- **Thu:** Deploy to SQL Server, verify execution plans
- **Fri:** Write Python wrappers, run pytest

### Week 2 — Phase 2 + 3 Start
- **Mon-Tue:** Phase 2 (CRUD) — 3 SPs
- **Wed-Thu:** Phase 3 start (requests)
- **Fri:** Integration test: raise → approve workflow

### Week 3-4 — Phase 4 (Queue)
- **Mon-Tue:** `usp_ExecuteAssignQueueItem` (most critical)
- **Wed-Thu:** `usp_ExecuteRevokeQueueItem` (alert resolution)
- **Fri:** End-to-end pipeline test

### Week 5-6 — Testing + Rollout
- **Mon-Tue:** Load test
- **Wed:** Performance baseline
- **Thu:** Staging + UAT
- **Fri:** Production rollout

---

## File Structure

### SQL Definitions
```
sql/
├── phase1_selects.sql          — 12 read-only SPs
├── phase2_platform_crud.sql    — 3 CRUD SPs
├── phase3_request_lifecycle.sql — 4 request SPs
├── phase4_queue_execution.sql  — 6 queue/alert SPs
└── indexes_and_types.sql       — TVPs + indexes
```

### Python Wrappers
| Module | SPs |
|--------|-----|
| `app/services/dashboard.py` | `_exec_usp_GetDashboardComplete`, etc. |
| `app/api/routes/platforms.py` | Platform CRUD wrappers |
| `app/api/routes/alerts.py` | Alert wrappers |
| `app/api/routes/requests.py` | Request workflow wrappers |
| `app/api/routes/queue.py` | Queue execution wrappers |
| `app/api/query_helpers.py` | Lookup + check wrappers |
| `app/services/approval_workflow.py` | Role mapping wrappers |
| `app/services/license_execution.py` | Execution wrappers |
| `app/services/aspire_events.py` | Alert creation wrappers |

---

## Wrapper Function Pattern

```python
def _exec_usp_GetDashboardComplete(db: Session, user_id=None, staffid=None, org_level=False):
    """Call usp_GetDashboardComplete and return parsed results."""
    result = db.execute(
        text("""
            EXEC dbo.usp_GetDashboardComplete
                @UserId = :user_id,
                @StaffId = :staffid,
                @OrgLevel = :org_level
        """),
        {"user_id": user_id, "staffid": staffid, "org_level": org_level}
    ).fetchall()
    
    # Parse result rows into DTO objects
    return _parse_bootstrap_response(result)
```

---

## Testing Strategy

### Unit Tests (Per Phase)
```bash
pytest tests/test_phase1_sps.py -v
pytest tests/test_phase2_platform_sps.py -v
pytest tests/test_phase3_request_sps.py -v
pytest tests/test_phase4_queue_sps.py -v
```

### Integration Tests
```bash
pytest tests/test_approval_workflow_integration.py -v
pytest tests/test_queue_workflow_integration.py -v
```

### Performance Baseline
- Dashboard bootstrap: target 40% reduction (2s → 1.2s)
- Queue execution: target atomic with < 100ms
- Approval workflow: target < 50ms per step

---

## Success Criteria

✅ All 25 SPs deployed and passing tests  
✅ Dashboard bootstrap < 1.5s (from 2s)  
✅ Queue execution atomic (no partial updates)  
✅ Zero data integrity issues  
✅ UAT approval  
✅ Performance improvement documented  

---

## Rollback Plan

1. **Emergency rollback:** `DROP PROCEDURE IF EXISTS dbo.usp_*`
2. Revert Python code to ORM calls
3. Redeploy from git
4. Verify tests pass

---

*Implementation begins with Phase 1 SPs.*
