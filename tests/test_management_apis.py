"""
Comprehensive Automated Test Suite for Camera Intelligence Management APIs
Covers all requirements specified in Phase 2, Task 8:
- Location APIs (Create, List, Get, Update, Deactivate, RBAC & Scoping)
- Department APIs (Create, List, Get, Update, Deactivate, Scoping, Cross-Location Rejection, Unique Constraints)
- Employee Role APIs (Create, List, Get, Uniqueness)
- Employee APIs (Create, List, Pagination, Filtering, Search, Details, Update, Deactivate, Roles Assign/Remove,
  Department/Location Consistency, Cross-Location Protection, Data Sanitization)
- Clean database teardown

Runs using standard Python unittest.
"""

import sys
import unittest
from pathlib import Path

# Add server directory to path
SERVER_ROOT = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from fastapi import HTTPException, status

from app.database.session import SessionLocal
from app.models.user import User, user_locations
from app.models.location import Location
from app.models.department import Department
from app.models.role import Role, employee_roles
from app.models.employee import Employee
from app.core.security import get_password_hash

from app.schemas.location import (
    LocationCreate,
    LocationUpdate,
    LocationResponse,
    LocationDetailResponse,
)
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
)
from app.schemas.role import RoleCreate, RoleResponse
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeDetailResponse,
    EmployeeRoleAssign,
)
from app.schemas.common import PaginatedResponse

from app.api.v1.endpoints.locations import (
    list_locations as list_locations_ep,
    create_location as create_location_ep,
    get_location as get_location_ep,
    update_location as update_location_ep,
    deactivate_location as deactivate_location_ep,
)
from app.api.v1.endpoints.departments import (
    list_departments as list_departments_ep,
    create_department as create_department_ep,
    get_department as get_department_ep,
    update_department as update_department_ep,
    deactivate_department as deactivate_department_ep,
)
from app.api.v1.endpoints.roles import (
    list_roles as list_roles_ep,
    create_role as create_role_ep,
    get_role as get_role_ep,
)
from app.api.v1.endpoints.employees import (
    list_employees as list_employees_ep,
    create_employee as create_employee_ep,
    get_employee as get_employee_ep,
    update_employee as update_employee_ep,
    deactivate_employee as deactivate_employee_ep,
    assign_role as assign_role_ep,
    remove_role as remove_role_ep,
)


class TestManagementAPIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up database connection and initial test users."""
        cls.db = SessionLocal()

        # Load bootstrap super_admin
        cls.super_admin = (
            cls.db.query(User).filter(User.email == "admin@cameraintelligence.com").first()
        )
        assert cls.super_admin is not None, "Bootstrap super_admin not found in database!"

        hashed_pw = get_password_hash("TestPassword123!")

        # Create test users for role & location scoping tests
        cls.loc_admin_a = User(
            email="admin.loca@test.internal",
            full_name="Location A Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.loc_admin_b = User(
            email="admin.locb@test.internal",
            full_name="Location B Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.operator_a = User(
            email="operator.loca@test.internal",
            full_name="Location A Operator",
            password_hash=hashed_pw,
            system_role="operator",
            is_active=True,
        )
        cls.viewer_a = User(
            email="viewer.loca@test.internal",
            full_name="Location A Viewer",
            password_hash=hashed_pw,
            system_role="viewer",
            is_active=True,
        )

        cls.db.add_all([cls.loc_admin_a, cls.loc_admin_b, cls.operator_a, cls.viewer_a])
        cls.db.commit()
        for u in [cls.loc_admin_a, cls.loc_admin_b, cls.operator_a, cls.viewer_a]:
            cls.db.refresh(u)

        # Track created entities for clean teardown
        cls.created_location_ids = []
        cls.created_department_ids = []
        cls.created_role_ids = []
        cls.created_employee_ids = []

    @classmethod
    def tearDownClass(cls):
        """Clean up all created test entities in reverse dependency order."""
        try:
            # 1. Clean up employee roles and employees
            cls.db.execute(employee_roles.delete())
            cls.db.query(Employee).delete(synchronize_session=False)

            # 2. Clean up departments
            cls.db.query(Department).delete(synchronize_session=False)

            # 3. Clean up user_locations and test users
            test_user_ids = [
                cls.loc_admin_a.id,
                cls.loc_admin_b.id,
                cls.operator_a.id,
                cls.viewer_a.id,
            ]
            cls.db.execute(
                user_locations.delete().where(user_locations.c.user_id.in_(test_user_ids))
            )
            cls.db.query(User).filter(User.id.in_(test_user_ids)).delete(
                synchronize_session=False
            )

            # 4. Clean up roles
            cls.db.query(Role).delete(synchronize_session=False)

            # 5. Clean up locations
            cls.db.query(Location).delete(synchronize_session=False)

            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
            print(f"Teardown error: {e}")
        finally:
            cls.db.close()

    # =========================================================================
    # 1. LOCATION TESTS
    # =========================================================================

    def test_01_create_location_success(self):
        """Super admin can create locations."""
        data_a = LocationCreate(
            name="HQ Campus",
            address="100 Tech Blvd, Silicon Valley, CA",
            timezone="America/Los_Angeles",
            is_active=True,
        )
        resp_a = create_location_ep(data=data_a, _=self.super_admin, db=self.db)
        self.assertIsInstance(resp_a, LocationResponse)
        self.assertEqual(resp_a.name, "HQ Campus")
        self.assertTrue(resp_a.is_active)
        self.__class__.loc_a_id = resp_a.id
        self.created_location_ids.append(resp_a.id)

        data_b = LocationCreate(
            name="East Coast Branch",
            address="500 Madison Ave, New York, NY",
            timezone="America/New_York",
            is_active=True,
        )
        resp_b = create_location_ep(data=data_b, _=self.super_admin, db=self.db)
        self.assertIsInstance(resp_b, LocationResponse)
        self.assertEqual(resp_b.name, "East Coast Branch")
        self.__class__.loc_b_id = resp_b.id
        self.created_location_ids.append(resp_b.id)

        # Assign loc_admin_a, operator_a, viewer_a to Location A
        # Assign loc_admin_b to Location B
        self.db.execute(
            user_locations.insert().values(
                [
                    {"user_id": self.loc_admin_a.id, "location_id": self.loc_a_id},
                    {"user_id": self.operator_a.id, "location_id": self.loc_a_id},
                    {"user_id": self.viewer_a.id, "location_id": self.loc_a_id},
                    {"user_id": self.loc_admin_b.id, "location_id": self.loc_b_id},
                ]
            )
        )
        self.db.commit()

    def test_02_create_duplicate_location_rejected(self):
        """Duplicate location name rejected with 409 Conflict."""
        data = LocationCreate(name="HQ Campus", timezone="UTC")
        with self.assertRaises(HTTPException) as ctx:
            create_location_ep(data=data, _=self.super_admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already exists", ctx.exception.detail)

    def test_03_list_locations_scoping(self):
        """Super admin sees all locations; location admin sees only assigned locations."""
        # Super admin sees both
        all_locs = list_locations_ep(current_user=self.super_admin, db=self.db)
        self.assertGreaterEqual(len(all_locs), 2)
        loc_ids = [l.id for l in all_locs]
        self.assertIn(self.loc_a_id, loc_ids)
        self.assertIn(self.loc_b_id, loc_ids)

        # loc_admin_a sees only loc_a
        locs_a = list_locations_ep(current_user=self.loc_admin_a, db=self.db)
        self.assertEqual(len(locs_a), 1)
        self.assertEqual(locs_a[0].id, self.loc_a_id)

        # loc_admin_b sees only loc_b
        locs_b = list_locations_ep(current_user=self.loc_admin_b, db=self.db)
        self.assertEqual(len(locs_b), 1)
        self.assertEqual(locs_b[0].id, self.loc_b_id)

    def test_04_get_location_details(self):
        """Get location details with counts and verify cross-location rejection."""
        # Viewer in Location A can get details for Location A
        details = get_location_ep(
            location_id=self.loc_a_id, current_user=self.viewer_a, db=self.db
        )
        self.assertIsInstance(details, LocationDetailResponse)
        self.assertEqual(details.id, self.loc_a_id)
        self.assertIsInstance(details.department_count, int)
        self.assertIsInstance(details.employee_count, int)

        # Viewer in Location A CANNOT get details for Location B (403)
        with self.assertRaises(HTTPException) as ctx:
            get_location_ep(
                location_id=self.loc_b_id, current_user=self.viewer_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_05_update_location(self):
        """Location admin updates assigned location; unauthorized admin rejected."""
        # loc_admin_a updates Location A
        update_data = LocationUpdate(address="100 Tech Blvd, Suite 400")
        updated = update_location_ep(
            location_id=self.loc_a_id,
            data=update_data,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertEqual(updated.address, "100 Tech Blvd, Suite 400")

        # loc_admin_a CANNOT update Location B (403)
        with self.assertRaises(HTTPException) as ctx:
            update_location_ep(
                location_id=self.loc_b_id,
                data=update_data,
                current_user=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_06_deactivate_location(self):
        """Location admin deactivates assigned location."""
        deactivated = deactivate_location_ep(
            location_id=self.loc_b_id,
            current_user=self.loc_admin_b,
            db=self.db,
        )
        self.assertFalse(deactivated.is_active)

        # Reactivate loc_b for subsequent tests
        update_location_ep(
            location_id=self.loc_b_id,
            data=LocationUpdate(is_active=True),
            current_user=self.loc_admin_b,
            db=self.db,
        )

    # =========================================================================
    # 2. DEPARTMENT TESTS
    # =========================================================================

    def test_07_create_department_success(self):
        """Create departments within authorized locations."""
        dept_data_1 = DepartmentCreate(
            location_id=self.loc_a_id,
            name="Engineering",
            code="ENG",
            is_active=True,
        )
        resp_1 = create_department_ep(
            data=dept_data_1, current_user=self.loc_admin_a, db=self.db
        )
        self.assertIsInstance(resp_1, DepartmentResponse)
        self.assertEqual(resp_1.name, "Engineering")
        self.assertEqual(resp_1.code, "ENG")
        self.__class__.dept_eng_a_id = resp_1.id
        self.created_department_ids.append(resp_1.id)

        dept_data_2 = DepartmentCreate(
            location_id=self.loc_a_id,
            name="Security Operations",
            code="SEC",
            is_active=True,
        )
        resp_2 = create_department_ep(
            data=dept_data_2, current_user=self.loc_admin_a, db=self.db
        )
        self.__class__.dept_sec_a_id = resp_2.id
        self.created_department_ids.append(resp_2.id)

    def test_08_department_uniqueness_within_location(self):
        """Duplicate department name or code in SAME location is rejected."""
        # Duplicate name
        data_dup_name = DepartmentCreate(
            location_id=self.loc_a_id,
            name="Engineering",
            code="ENG2",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_department_ep(
                data=data_dup_name, current_user=self.loc_admin_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already exists", ctx.exception.detail)

        # Duplicate code
        data_dup_code = DepartmentCreate(
            location_id=self.loc_a_id,
            name="Hardware R&D",
            code="ENG",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_department_ep(
                data=data_dup_code, current_user=self.loc_admin_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("code 'ENG' already exists", ctx.exception.detail)

    def test_09_same_department_name_in_different_location_allowed(self):
        """Same department name is allowed in a DIFFERENT location."""
        dept_data_b = DepartmentCreate(
            location_id=self.loc_b_id,
            name="Engineering",
            code="ENG",
            is_active=True,
        )
        resp_b = create_department_ep(
            data=dept_data_b, current_user=self.loc_admin_b, db=self.db
        )
        self.assertEqual(resp_b.location_id, self.loc_b_id)
        self.assertEqual(resp_b.name, "Engineering")
        self.__class__.dept_eng_b_id = resp_b.id
        self.created_department_ids.append(resp_b.id)

    def test_10_cross_location_department_protection(self):
        """Location admin cannot create or modify departments in other locations."""
        # loc_admin_a cannot create department in Location B
        unauth_create = DepartmentCreate(
            location_id=self.loc_b_id,
            name="Unauthorized Dept",
        )
        with self.assertRaises(HTTPException) as ctx:
            create_department_ep(
                data=unauth_create, current_user=self.loc_admin_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # loc_admin_a cannot update department in Location B
        with self.assertRaises(HTTPException) as ctx:
            update_department_ep(
                department_id=self.dept_eng_b_id,
                data=DepartmentUpdate(name="Hacked Dept"),
                current_user=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_11_list_departments_scoping(self):
        """List departments correctly filters by user access and location."""
        # loc_admin_a sees only departments in Location A
        depts_a = list_departments_ep(current_user=self.loc_admin_a, db=self.db)
        for d in depts_a:
            self.assertEqual(d.location_id, self.loc_a_id)

        # Super admin sees all departments
        all_depts = list_departments_ep(current_user=self.super_admin, db=self.db)
        all_ids = [d.id for d in all_depts]
        self.assertIn(self.dept_eng_a_id, all_ids)
        self.assertIn(self.dept_eng_b_id, all_ids)

    def test_12_update_and_deactivate_department(self):
        """Update department name/code and soft deactivation."""
        updated = update_department_ep(
            department_id=self.dept_sec_a_id,
            data=DepartmentUpdate(name="Security & Safety"),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertEqual(updated.name, "Security & Safety")

        # Soft deactivation
        deactivated = deactivate_department_ep(
            department_id=self.dept_sec_a_id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertFalse(deactivated.is_active)

    # =========================================================================
    # 3. ROLE TESTS
    # =========================================================================

    def test_13_create_and_list_roles(self):
        """Create job roles, enforce unique role name, and list roles."""
        role1 = create_role_ep(
            data=RoleCreate(name="Lead AI Engineer", description="Computer Vision Specialist"),
            _=self.loc_admin_a,
            db=self.db,
        )
        self.assertIsInstance(role1, RoleResponse)
        self.assertEqual(role1.name, "Lead AI Engineer")
        self.__class__.role_ai_id = role1.id
        self.created_role_ids.append(role1.id)

        role2 = create_role_ep(
            data=RoleCreate(name="Control Room Operator", description="Camera monitoring"),
            _=self.loc_admin_a,
            db=self.db,
        )
        self.__class__.role_op_id = role2.id
        self.created_role_ids.append(role2.id)

        # Duplicate role name rejected
        with self.assertRaises(HTTPException) as ctx:
            create_role_ep(
                data=RoleCreate(name="Lead AI Engineer"),
                _=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)

        # List roles
        all_roles = list_roles_ep(_=self.viewer_a, db=self.db)
        role_names = [r.name for r in all_roles]
        self.assertIn("Lead AI Engineer", role_names)
        self.assertIn("Control Room Operator", role_names)

        # Get role by ID
        fetched_role = get_role_ep(role_id=role1.id, _=self.viewer_a, db=self.db)
        self.assertEqual(fetched_role.id, role1.id)

    # =========================================================================
    # 4. EMPLOYEE TESTS
    # =========================================================================

    def test_14_create_employee_success(self):
        """Create employee with valid location, department, and role."""
        data = EmployeeCreate(
            employee_code="EMP-1001",
            full_name="Sarah Connor",
            email="sarah.connor@test.internal",
            department_id=self.dept_eng_a_id,
            location_id=self.loc_a_id,
            enrollment_status="pending",
            is_active=True,
            role_ids=[self.role_ai_id],
        )
        resp = create_employee_ep(
            data=data, current_user=self.loc_admin_a, db=self.db
        )
        self.assertIsInstance(resp, EmployeeDetailResponse)
        self.assertEqual(resp.employee_code, "EMP-1001")
        self.assertEqual(resp.full_name, "Sarah Connor")
        self.assertEqual(resp.department_name, "Engineering")
        self.assertEqual(resp.location_name, "HQ Campus")
        self.assertEqual(len(resp.roles), 1)
        self.assertEqual(resp.roles[0].name, "Lead AI Engineer")
        self.__class__.emp_1_id = resp.id
        self.created_employee_ids.append(resp.id)

    def test_15_employee_data_sanitization(self):
        """Verify employee responses NEVER expose password_hash or biometric vectors."""
        resp = get_employee_ep(
            employee_id=self.emp_1_id, current_user=self.viewer_a, db=self.db
        )
        dump = resp.model_dump()
        self.assertNotIn("password_hash", dump)
        self.assertNotIn("embedding", dump)
        self.assertNotIn("face_embeddings", dump)

    def test_16_duplicate_employee_code_rejected(self):
        """Duplicate employee_code rejected with 409 Conflict."""
        data = EmployeeCreate(
            employee_code="EMP-1001",
            full_name="Duplicate Employee",
            department_id=self.dept_eng_a_id,
            location_id=self.loc_a_id,
        )
        with self.assertRaises(HTTPException) as ctx:
            create_employee_ep(
                data=data, current_user=self.loc_admin_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already assigned", ctx.exception.detail)

    def test_17_duplicate_employee_email_rejected(self):
        """Duplicate email rejected with 409 Conflict."""
        data = EmployeeCreate(
            employee_code="EMP-1002",
            full_name="Another Employee",
            email="sarah.connor@test.internal",
            department_id=self.dept_eng_a_id,
            location_id=self.loc_a_id,
        )
        with self.assertRaises(HTTPException) as ctx:
            create_employee_ep(
                data=data, current_user=self.loc_admin_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already in use", ctx.exception.detail)

    def test_18_department_location_inconsistency_rejected(self):
        """Department location and employee location mismatch rejected with 400 Bad Request."""
        # dept_eng_a_id is in loc_a, but we pass loc_b_id
        data = EmployeeCreate(
            employee_code="EMP-MISMATCH",
            full_name="Mismatch User",
            department_id=self.dept_eng_a_id,
            location_id=self.loc_b_id,
        )
        with self.assertRaises(HTTPException) as ctx:
            create_employee_ep(
                data=data, current_user=self.super_admin, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not match", ctx.exception.detail)

    def test_19_create_employee_inherits_department_location(self):
        """When location_id is omitted, employee inherits location from department."""
        data = EmployeeCreate(
            employee_code="EMP-INHERIT",
            full_name="Inherited Location Employee",
            department_id=self.dept_eng_a_id,
            location_id=None,
        )
        resp = create_employee_ep(
            data=data, current_user=self.loc_admin_a, db=self.db
        )
        self.assertEqual(resp.location_id, self.loc_a_id)
        self.assertEqual(resp.location_name, "HQ Campus")
        self.created_employee_ids.append(resp.id)

    def test_20_cross_location_employee_creation_blocked(self):
        """Location admin cannot create employee in a location they are not assigned to."""
        data = EmployeeCreate(
            employee_code="EMP-UNAUTH",
            full_name="Unauth Employee",
            department_id=self.dept_eng_b_id,
            location_id=self.loc_b_id,
        )
        with self.assertRaises(HTTPException) as ctx:
            create_employee_ep(
                data=data, current_user=self.loc_admin_a, db=self.db
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_21_employee_role_assignment_and_removal(self):
        """Assign role to employee and remove role from employee."""
        # Assign role_op to emp_1
        assign_resp = assign_role_ep(
            employee_id=self.emp_1_id,
            data=EmployeeRoleAssign(role_id=self.role_op_id),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        role_ids = [r.id for r in assign_resp.roles]
        self.assertIn(self.role_op_id, role_ids)
        self.assertIn(self.role_ai_id, role_ids)

        # Remove role_ai from emp_1
        remove_resp = remove_role_ep(
            employee_id=self.emp_1_id,
            role_id=self.role_ai_id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        remaining_role_ids = [r.id for r in remove_resp.roles]
        self.assertNotIn(self.role_ai_id, remaining_role_ids)
        self.assertIn(self.role_op_id, remaining_role_ids)

    def test_22_list_employees_pagination_and_filtering(self):
        """List employees with pagination, location filter, search, and status filters."""
        # Create additional employees for pagination testing
        for i in range(2, 6):
            data = EmployeeCreate(
                employee_code=f"EMP-200{i}",
                full_name=f"Test Employee {i}",
                email=f"emp{i}@test.internal",
                department_id=self.dept_eng_a_id,
                location_id=self.loc_a_id,
                enrollment_status="enrolled" if i % 2 == 0 else "pending",
                is_active=(i != 5),
            )
            created = create_employee_ep(
                data=data, current_user=self.loc_admin_a, db=self.db
            )
            self.created_employee_ids.append(created.id)

        # Test pagination: page=1, size=2
        page1 = list_employees_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            page=1,
            size=2,
            location_id=self.loc_a_id,
        )
        self.assertIsInstance(page1, PaginatedResponse)
        self.assertEqual(len(page1.items), 2)
        self.assertEqual(page1.page, 1)
        self.assertEqual(page1.size, 2)
        self.assertGreaterEqual(page1.total, 5)
        self.assertGreaterEqual(page1.pages, 3)

        # Test search filter
        search_res = list_employees_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            search="Connor",
        )
        self.assertGreaterEqual(search_res.total, 1)
        self.assertEqual(search_res.items[0].full_name, "Sarah Connor")

        # Test status filter: enrollment_status=enrolled
        enrolled_res = list_employees_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            enrollment_status="enrolled",
        )
        for e in enrolled_res.items:
            self.assertEqual(e.enrollment_status, "enrolled")

        # Test inactive filter: is_active=False
        inactive_res = list_employees_ep(
            current_user=self.loc_admin_a,
            db=self.db,
            is_active=False,
        )
        self.assertGreaterEqual(inactive_res.total, 1)
        for e in inactive_res.items:
            self.assertFalse(e.is_active)

    def test_23_cross_location_employee_access_blocked(self):
        """Location B admin cannot read or modify employee in Location A."""
        with self.assertRaises(HTTPException) as ctx:
            get_employee_ep(
                employee_id=self.emp_1_id,
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        with self.assertRaises(HTTPException) as ctx:
            update_employee_ep(
                employee_id=self.emp_1_id,
                data=EmployeeUpdate(full_name="Hacked Name"),
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_24_update_and_deactivate_employee(self):
        """Update employee profile and soft deactivation."""
        # Update full name
        updated = update_employee_ep(
            employee_id=self.emp_1_id,
            data=EmployeeUpdate(full_name="Sarah Connor-Reese"),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertEqual(updated.full_name, "Sarah Connor-Reese")

        # Soft deactivation
        deactivated = deactivate_employee_ep(
            employee_id=self.emp_1_id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertFalse(deactivated.is_active)


if __name__ == "__main__":
    unittest.main()

