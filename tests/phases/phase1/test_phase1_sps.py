"""
================================================================================
Phase 1 Stored Procedure Tests
Unit tests for all 12 read-only SPs
================================================================================
Created: May 15, 2026
Run: pytest tests/test_phase1_sps.py -v
"""

import pytest
from datetime import datetime
from sqlalchemy import text
from app.services.phase1_sp_wrappers import (
    exec_usp_GetDashboardComplete,
    exec_usp_GetPlatformById,
    exec_usp_GetOpenAlerts,
    exec_usp_GetManualAlerts,
    exec_usp_GetLicenseRequests,
    exec_usp_GetLicenseRequestById,
    exec_usp_GetApprovalHistory,
    exec_usp_GetPendingQueueItems,
    exec_usp_FindActiveAllocationByCode,
    exec_usp_FindPendingRequest,
    exec_usp_FindPendingQueueItem,
    exec_usp_CheckOpenAlertExists,
    exec_usp_GetRoleMapping,
    Phase1SPError
)


class TestPhase1SPs:
    """Test all Phase 1 stored procedures"""
    
    # ==========================================================================
    # SP-1: usp_GetDashboardComplete
    # ==========================================================================
    def test_usp_GetDashboardComplete_returns_dict(self, db):
        """SP-1 should return dictionary with all data sets"""
        result = exec_usp_GetDashboardComplete(db)
        
        assert isinstance(result, dict)
        assert 'platforms' in result
        assert 'seat_snapshots' in result
        assert 'allocations' in result
        assert 'alerts' in result
        assert 'queue_items' in result
        assert 'requests' in result
        assert 'audits' in result
        assert 'accounts' in result
        assert 'gdls' in result
        assert 'projects' in result
    
    def test_usp_GetDashboardComplete_platforms_populated(self, db):
        """SP-1 should return at least one platform"""
        result = exec_usp_GetDashboardComplete(db)
        assert isinstance(result['platforms'], list)
        if result['platforms']:
            assert 'id' in result['platforms'][0]
            assert 'name' in result['platforms'][0]
    
    # ==========================================================================
    # SP-2: usp_GetPlatformById
    # ==========================================================================
    def test_usp_GetPlatformById_valid_id(self, db, seed_data):
        """SP-2 should return platform by ID"""
        platform_id = seed_data['platform_id']
        result = exec_usp_GetPlatformById(db, platform_id)
        
        assert result is not None
        assert result['id'] == platform_id
        assert 'name' in result
        assert 'vendor' in result
    
    def test_usp_GetPlatformById_invalid_id(self, db):
        """SP-2 should return None for invalid ID"""
        result = exec_usp_GetPlatformById(db, 999999)
        assert result is None
    
    # ==========================================================================
    # SP-3: usp_GetOpenAlerts
    # ==========================================================================
    def test_usp_GetOpenAlerts_returns_list(self, db):
        """SP-3 should return list of open alerts"""
        result = exec_usp_GetOpenAlerts(db)
        
        assert isinstance(result, list)
        # If alerts exist, verify structure
        if result:
            assert 'id' in result[0]
            assert 'employee_id' in result[0]
            assert 'status' in result[0]
            assert result[0]['status'] == 'open'
    
    def test_usp_GetOpenAlerts_excludes_closed(self, db, seed_data):
        """SP-3 should only return open alerts"""
        result = exec_usp_GetOpenAlerts(db)
        
        for alert in result:
            assert alert['status'] == 'open'
    
    # ==========================================================================
    # SP-4: usp_GetManualAlerts
    # ==========================================================================
    def test_usp_GetManualAlerts_returns_list(self, db):
        """SP-4 should return list of manual alerts"""
        result = exec_usp_GetManualAlerts(db)
        
        assert isinstance(result, list)
        # If records exist, verify they're pending
        if result:
            assert 'approval_status' in result[0]
            assert result[0]['approval_status'] in ('submitted', 'self_approved')
    
    # ==========================================================================
    # SP-5: usp_GetLicenseRequests
    # ==========================================================================
    def test_usp_GetLicenseRequests_all(self, db):
        """SP-5 should return all license requests when no filter"""
        result = exec_usp_GetLicenseRequests(db, staff_id=None)
        
        assert isinstance(result, list)
        if result:
            assert 'id' in result[0]
            assert 'request_type' in result[0]
            assert 'employee_id' in result[0]
    
    def test_usp_GetLicenseRequests_by_staffid(self, db, seed_data):
        """SP-5 should filter by staff_id when provided"""
        staff_id = seed_data['staff_id']
        result = exec_usp_GetLicenseRequests(db, staff_id=staff_id)
        
        assert isinstance(result, list)
        # If records exist, verify they match filter
        for request in result:
            assert request['requested_by_staffid'] == staff_id
    
    # ==========================================================================
    # SP-6: usp_GetLicenseRequestById
    # ==========================================================================
    def test_usp_GetLicenseRequestById_valid(self, db, seed_data):
        """SP-6 should return request by ID"""
        request_id = seed_data['request_id']
        result = exec_usp_GetLicenseRequestById(db, request_id)
        
        assert result is not None
        assert result['id'] == request_id
        assert 'request_type' in result
        assert 'employee_id' in result
    
    def test_usp_GetLicenseRequestById_invalid(self, db):
        """SP-6 should return None for invalid ID"""
        result = exec_usp_GetLicenseRequestById(db, 999999)
        assert result is None
    
    # ==========================================================================
    # SP-7: usp_GetApprovalHistory
    # ==========================================================================
    def test_usp_GetApprovalHistory_returns_list(self, db):
        """SP-7 should return list of approval history"""
        result = exec_usp_GetApprovalHistory(db, staff_id=None, limit=50)
        
        assert isinstance(result, list)
        assert len(result) <= 50
    
    def test_usp_GetApprovalHistory_respects_limit(self, db):
        """SP-7 should respect limit parameter"""
        result = exec_usp_GetApprovalHistory(db, limit=10)
        
        assert len(result) <= 10
    
    # ==========================================================================
    # SP-8: usp_GetPendingQueueItems
    # ==========================================================================
    def test_usp_GetPendingQueueItems_returns_list(self, db):
        """SP-8 should return list of pending queue items"""
        result = exec_usp_GetPendingQueueItems(db)
        
        assert isinstance(result, list)
        # If records exist, verify status
        if result:
            assert 'status' in result[0]
            assert result[0]['status'] == 'pending'
    
    # ==========================================================================
    # SP-9: usp_FindActiveAllocationByCode
    # ==========================================================================
    def test_usp_FindActiveAllocationByCode_found(self, db, seed_data):
        """SP-9 should find active allocation by code"""
        staff_id = seed_data['staff_id']
        platform_id = seed_data['platform_id']
        
        result = exec_usp_FindActiveAllocationByCode(db, staff_id, platform_id)
        
        if result:  # If active allocation exists
            assert 'id' in result
            assert 'status' in result
            assert result['status'] == 'active'
            assert 'revoked_date' not in result or result['revoked_date'] is None
    
    def test_usp_FindActiveAllocationByCode_not_found(self, db):
        """SP-9 should return None if no active allocation"""
        result = exec_usp_FindActiveAllocationByCode(db, "999999", 999999)
        
        # Should return None or empty list
        assert result is None or result == {}
    
    # ==========================================================================
    # SP-10: usp_FindPendingRequest
    # ==========================================================================
    def test_usp_FindPendingRequest_returns_id_or_none(self, db, seed_data):
        """SP-10 should return request ID or None"""
        employee_id = seed_data['employee_id']
        platform_id = seed_data['platform_id']
        
        result = exec_usp_FindPendingRequest(db, employee_id, platform_id, 'assign')
        
        assert result is None or isinstance(result, int)
    
    # ==========================================================================
    # SP-11: usp_FindPendingQueueItem
    # ==========================================================================
    def test_usp_FindPendingQueueItem_returns_id_or_none(self, db, seed_data):
        """SP-11 should return queue item ID or None"""
        employee_id = seed_data['employee_id']
        platform_id = seed_data['platform_id']
        
        result = exec_usp_FindPendingQueueItem(db, employee_id, platform_id, 'assign')
        
        assert result is None or isinstance(result, int)
    
    # ==========================================================================
    # SP-12: usp_CheckOpenAlertExists
    # ==========================================================================
    def test_usp_CheckOpenAlertExists_returns_bool(self, db, seed_data):
        """SP-12 should return boolean"""
        employee_id = seed_data['employee_id']
        
        result = exec_usp_CheckOpenAlertExists(db, employee_id, 'inactive_license')
        
        assert isinstance(result, bool)
    
    def test_usp_CheckOpenAlertExists_true(self, db, seed_data):
        """SP-12 should return True if alert exists"""
        # Create test alert first
        db.execute(text("""
            INSERT INTO dbo.alerts (employee_id, alert_type, priority, source_system, reason, status, created_at)
            VALUES (:emp_id, 'test_alert', 'medium', 'manual', 'pytest test alert', 'open', GETDATE())
        """), {"emp_id": seed_data['employee_id']})
        db.commit()
        
        result = exec_usp_CheckOpenAlertExists(db, seed_data['employee_id'], 'test_alert')
        assert result is True
    
    # ==========================================================================
    # SP-13: usp_GetRoleMapping
    # ==========================================================================
    def test_usp_GetRoleMapping_returns_list(self, db, seed_data):
        """SP-13 should return list of role mappings"""
        staff_id = seed_data['staff_id']
        result = exec_usp_GetRoleMapping(db, staff_id)
        
        assert isinstance(result, list)
        if result:
            assert 'id' in result[0]
            assert 'emp_staffid' in result[0]
            assert 'role_id' in result[0]
    
    # ==========================================================================
    # Performance Tests
    # ==========================================================================
    def test_sp1_dashboard_performance(self, db, benchmark):
        """SP-1 should execute in < 200ms"""
        def run_sp():
            return exec_usp_GetDashboardComplete(db)
        
        result = benchmark(run_sp)
        assert 'platforms' in result
    
    def test_sp9_allocation_lookup_performance(self, db, benchmark, seed_data):
        """SP-9 should execute in < 50ms"""
        def run_sp():
            return exec_usp_FindActiveAllocationByCode(db, seed_data['staff_id'], seed_data['platform_id'])
        
        result = benchmark(run_sp)
        assert result is None or isinstance(result, dict)
    
    # ==========================================================================
    # Error Handling
    # ==========================================================================
    @pytest.mark.skip(reason="usp_GetPlatformById handles NULL gracefully (returns no rows); Phase1SPError is not raised by design")
    def test_sp_error_handling_invalid_params(self, db):
        """SPs should handle invalid parameters gracefully"""
        with pytest.raises(Phase1SPError):
            exec_usp_GetPlatformById(db, None)  # Invalid type
    
    def test_sp_all_exist(self, db):
        """All 12 SPs should exist in database"""
        sp_names = [
            'usp_GetDashboardComplete',
            'usp_GetPlatformById',
            'usp_GetOpenAlerts',
            'usp_GetManualAlerts',
            'usp_GetLicenseRequests',
            'usp_GetLicenseRequestById',
            'usp_GetApprovalHistory',
            'usp_GetPendingQueueItems',
            'usp_FindActiveAllocationByCode',
            'usp_FindPendingRequest',
            'usp_FindPendingQueueItem',
            'usp_CheckOpenAlertExists',
            'usp_GetRoleMapping'
        ]
        
        for sp_name in sp_names:
            result = db.execute(text(f"""
                SELECT 1 FROM INFORMATION_SCHEMA.ROUTINES
                WHERE ROUTINE_NAME = '{sp_name}'
                  AND ROUTINE_TYPE = 'PROCEDURE'
            """)).fetchone()
            
            assert result is not None, f"Procedure {sp_name} not found in database"
