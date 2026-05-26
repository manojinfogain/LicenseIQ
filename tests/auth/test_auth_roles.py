"""Tests for dual-database role resolution (LicenseIQ + Aspire)."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.access import EmployeeWiseRoleMapping
from app.services.auth_roles import (
    ResolvedRole,
    detect_aspire_org_role,
    resolve_user_role,
)


class TestDetectAspireOrgRole:
    def test_gdl_priority_over_account_and_pm(self):
        adb = MagicMock()
        with (
            patch("app.services.auth_roles.aspire_svc.is_aspire_delivery_head", return_value=True),
            patch("app.services.auth_roles.aspire_svc.is_aspire_account_owner", return_value=True),
            patch("app.services.auth_roles.aspire_svc.is_aspire_project_manager", return_value=True),
        ):
            resolved = detect_aspire_org_role(adb, "122034")
        assert resolved is not None
        assert resolved.code == "gdl"
        assert resolved.source == "aspire_auto"

    def test_account_when_not_gdl(self):
        adb = MagicMock()
        with (
            patch("app.services.auth_roles.aspire_svc.is_aspire_delivery_head", return_value=False),
            patch("app.services.auth_roles.aspire_svc.is_aspire_account_owner", return_value=True),
        ):
            resolved = detect_aspire_org_role(adb, "107348")
        assert resolved is not None
        assert resolved.code == "account"

    def test_pm_when_only_pm(self):
        adb = MagicMock()
        with (
            patch("app.services.auth_roles.aspire_svc.is_aspire_delivery_head", return_value=False),
            patch("app.services.auth_roles.aspire_svc.is_aspire_account_owner", return_value=False),
            patch("app.services.auth_roles.aspire_svc.is_aspire_project_manager", return_value=True),
        ):
            resolved = detect_aspire_org_role(adb, "106949")
        assert resolved is not None
        assert resolved.code == "pm"

    def test_none_when_no_org_role(self):
        adb = MagicMock()
        with (
            patch("app.services.auth_roles.aspire_svc.is_aspire_delivery_head", return_value=False),
            patch("app.services.auth_roles.aspire_svc.is_aspire_account_owner", return_value=False),
            patch("app.services.auth_roles.aspire_svc.is_aspire_project_manager", return_value=False),
        ):
            assert detect_aspire_org_role(adb, "999999") is None


class TestResolveUserRoleManualWins:
    def test_manual_mapping_used_when_present(self, db, gdl_staffid):
        resolved = resolve_user_role(db, gdl_staffid, allow_aspire_auto=True)
        assert resolved is not None
        assert resolved.code == "gdl"
        assert resolved.source == "manual"

    def test_aspire_auto_disabled_without_mapping(self, db):
        """Without mapping and auto off, resolution fails."""
        with patch("app.services.auth_roles.settings.auth_aspire_auto_role", False):
            resolved = resolve_user_role(db, "999999999", allow_aspire_auto=False)
        assert resolved is None


class TestLookupAspireEmployeeByEmail:
    def test_prefers_active_when_duplicate_email(self, adb):
        from app.api.routes.auth import _lookup_aspire_employee_by_email

        employee = _lookup_aspire_employee_by_email(adb, "Dhananjay.Kumar@infogain.com")
        assert employee is not None
        assert employee.emp_staffid.strip() == "109220"
        assert employee.is_active is True


@pytest.mark.integration
class TestResolveUserRoleAspireIntegration:
    """Live DB: known GDL head in Aspire should resolve when auto enabled and no mapping."""

    def test_delivery_head_can_resolve_without_manual_row(self, db, adb):
        from app.models.aspire import AspireDeliveryUnit

        du = adb.scalar(
            select(AspireDeliveryUnit)
            .where(AspireDeliveryUnit.deliveryhead.isnot(None))
            .limit(1)
        )
        if not du or not du.deliveryhead:
            pytest.skip("No delivery head in Aspire sample")

        sid = du.deliveryhead.strip()
        existing = db.scalar(
            select(EmployeeWiseRoleMapping).where(EmployeeWiseRoleMapping.emp_staffid == sid)
        )
        if existing:
            pytest.skip(f"Staffid {sid} already has manual mapping")

        resolved = resolve_user_role(db, sid, aspire_db=adb, allow_aspire_auto=True)
        assert resolved is not None
        assert resolved.code == "gdl"
        assert resolved.source == "aspire_auto"
