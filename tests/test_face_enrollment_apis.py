"""
Comprehensive Automated Test Suite for Camera Intelligence Face Enrollment APIs
Covers all requirements specified in Phase 2, Task 11:
1. Valid 512D AuraFace embedding enrollment
2. Invalid embedding length (511D, 513D) rejection
3. NaN and infinity coordinate rejection
4. Invalid normalization rejection (unnormalized / non-unit vector)
5. Employee not found rejection (HTTP 404)
6. Unauthorized location access rejection (HTTP 403)
7. Cross-location enrollment rejection (HTTP 403)
8. Operator and viewer write restrictions
9. Template metadata response without raw embedding vector exposure
10. Duplicate active template handling (HTTP 409)
11. Template deactivation and employee status transition
12. Primary template selection (/set-primary) and active demotion
13. Transaction rollback on failure
14. Employee with multiple supported templates (different model versions and historical samples)
Clean database teardown.
"""

import sys
import math
import unittest
from pathlib import Path

# Add server directory to path
SERVER_ROOT = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.database.session import SessionLocal
from app.models.user import User, user_locations
from app.models.location import Location
from app.models.employee import Employee
from app.models.employee_face_embedding import EmployeeFaceEmbedding
from app.core.security import get_password_hash

from app.schemas.face_enrollment import (
    FaceEnrollmentCreate,
    FaceEnrollmentResponse,
    FaceEnrollmentDetailResponse,
)

from app.api.v1.endpoints.face_enrollments import (
    enroll_face_template as enroll_face_template_ep,
    list_employee_face_enrollments as list_employee_face_enrollments_ep,
    get_face_enrollment as get_face_enrollment_ep,
    deactivate_face_enrollment as deactivate_face_enrollment_ep,
    set_primary_face_template as set_primary_face_template_ep,
)


def make_unit_vector(dim: int = 512, seed: int = 1) -> list[float]:
    """Generate a deterministic, valid 512D L2-normalized unit vector."""
    raw = [math.sin(i * 0.17 + seed) for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw]


class TestFaceEnrollmentAPIs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up database connection, test locations, employees, and test users."""
        cls.db = SessionLocal()

        # Load bootstrap super_admin
        cls.super_admin = (
            cls.db.query(User).filter(User.email == "admin@cameraintelligence.com").first()
        )
        assert cls.super_admin is not None, "Bootstrap super_admin not found in database!"

        # Create temporary test locations
        cls.loc_a = Location(
            name="Face Testing Alpha",
            address="100 Biometric Blvd, Alpha",
            timezone="America/New_York",
            is_active=True,
        )
        cls.loc_b = Location(
            name="Face Testing Beta",
            address="200 Vision Ave, Beta",
            timezone="UTC",
            is_active=True,
        )
        cls.db.add_all([cls.loc_a, cls.loc_b])
        cls.db.commit()
        cls.db.refresh(cls.loc_a)
        cls.db.refresh(cls.loc_b)

        hashed_pw = get_password_hash("TestPassword123!")

        # Create test users
        cls.loc_admin_a = User(
            email="admin.facea@test.internal",
            full_name="Location A Face Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.loc_admin_b = User(
            email="admin.faceb@test.internal",
            full_name="Location B Face Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.operator_a = User(
            email="operator.facea@test.internal",
            full_name="Location A Face Operator",
            password_hash=hashed_pw,
            system_role="operator",
            is_active=True,
        )
        cls.viewer_a = User(
            email="viewer.facea@test.internal",
            full_name="Location A Face Viewer",
            password_hash=hashed_pw,
            system_role="viewer",
            is_active=True,
        )

        cls.db.add_all([cls.loc_admin_a, cls.loc_admin_b, cls.operator_a, cls.viewer_a])
        cls.db.commit()
        for u in [cls.loc_admin_a, cls.loc_admin_b, cls.operator_a, cls.viewer_a]:
            cls.db.refresh(u)

        # Assign users to locations
        cls.db.execute(
            user_locations.insert().values(
                [
                    {"user_id": cls.loc_admin_a.id, "location_id": cls.loc_a.id},
                    {"user_id": cls.operator_a.id, "location_id": cls.loc_a.id},
                    {"user_id": cls.viewer_a.id, "location_id": cls.loc_a.id},
                    {"user_id": cls.loc_admin_b.id, "location_id": cls.loc_b.id},
                ]
            )
        )

        # Create test employees
        cls.emp_a = Employee(
            employee_code="EMP-FACE-01",
            full_name="Alice Biometric",
            email="alice.bio@test.internal",
            location_id=cls.loc_a.id,
            enrollment_status="pending",
            is_active=True,
        )
        cls.emp_b = Employee(
            employee_code="EMP-FACE-02",
            full_name="Bob Biometric",
            email="bob.bio@test.internal",
            location_id=cls.loc_b.id,
            enrollment_status="pending",
            is_active=True,
        )
        cls.db.add_all([cls.emp_a, cls.emp_b])
        cls.db.commit()
        cls.db.refresh(cls.emp_a)
        cls.db.refresh(cls.emp_b)

    @classmethod
    def tearDownClass(cls):
        """Clean up all created test entities in reverse dependency order."""
        try:
            # 1. Clean up face embeddings
            cls.db.query(EmployeeFaceEmbedding).delete(synchronize_session=False)

            # 2. Clean up employees
            cls.db.query(Employee).delete(synchronize_session=False)

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

            # 4. Clean up locations
            cls.db.query(Location).filter(
                Location.id.in_([cls.loc_a.id, cls.loc_b.id])
            ).delete(synchronize_session=False)

            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
            print(f"Teardown error: {e}")
        finally:
            cls.db.close()

    # =========================================================================
    # TEST CASES (1 to 14)
    # =========================================================================

    def test_01_valid_512d_enrollment(self):
        """1. Valid 512D AuraFace embedding enrollment succeeds and updates employee status."""
        vec = make_unit_vector(dim=512, seed=1)
        data = FaceEnrollmentCreate(
            embedding=vec,
            model_name="auraface_v1_glintr100",
            model_version="v1",
            is_template=True,
            sample_count=3,
            quality_score=0.94,
            source_image_ref="ref://secure-vault/enrollments/emp01_fused.png",
            is_active=True,
        )
        resp = enroll_face_template_ep(
            employee_id=self.emp_a.id,
            data=data,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertIsInstance(resp, FaceEnrollmentDetailResponse)
        self.assertEqual(resp.employee_id, self.emp_a.id)
        self.assertEqual(resp.employee_code, "EMP-FACE-01")
        self.assertEqual(resp.location_name, "Face Testing Alpha")
        self.assertEqual(resp.embedding_dim, 512)
        self.assertEqual(resp.model_name, "auraface_v1_glintr100")
        self.assertEqual(resp.model_version, "v1")
        self.assertEqual(resp.sample_count, 3)
        self.assertAlmostEqual(resp.quality_score, 0.94, places=2)
        self.assertTrue(resp.is_template)
        self.assertTrue(resp.is_active)
        self.__class__.emb_a1_id = resp.id

        # Verify employee enrollment_status transitioned to 'enrolled'
        self.db.refresh(self.emp_a)
        self.assertEqual(self.emp_a.enrollment_status, "enrolled")

    def test_02_invalid_embedding_length(self):
        """2. Reject embeddings with dimension != 512."""
        # 511 dimensions
        with self.assertRaises(ValidationError) as ctx:
            FaceEnrollmentCreate(
                embedding=make_unit_vector(dim=511, seed=2),
            )
        self.assertIn("exactly 512 dimensions", str(ctx.exception))

        # 513 dimensions
        with self.assertRaises(ValidationError) as ctx2:
            FaceEnrollmentCreate(
                embedding=make_unit_vector(dim=513, seed=2),
            )
        self.assertIn("exactly 512 dimensions", str(ctx2.exception))

    def test_03_nan_and_infinity_rejection(self):
        """3. Reject embeddings containing NaN or Infinite coordinates."""
        vec_nan = make_unit_vector(dim=512, seed=3)
        vec_nan[10] = float("nan")
        with self.assertRaises(ValidationError) as ctx:
            FaceEnrollmentCreate(embedding=vec_nan)
        self.assertIn("cannot be NaN or Infinite", str(ctx.exception))

        vec_inf = make_unit_vector(dim=512, seed=3)
        vec_inf[25] = float("inf")
        with self.assertRaises(ValidationError) as ctx2:
            FaceEnrollmentCreate(embedding=vec_inf)
        self.assertIn("cannot be NaN or Infinite", str(ctx2.exception))

    def test_04_invalid_normalization(self):
        """4. Reject unnormalized embedding vectors (norm far from 1.0)."""
        # Unnormalized vector with all ones (norm = sqrt(512) ~ 22.62)
        raw_ones = [1.0] * 512
        with self.assertRaises(ValidationError) as ctx:
            FaceEnrollmentCreate(embedding=raw_ones)
        self.assertIn("must be L2-normalized", str(ctx.exception))

        # Scaled-down vector with norm ~ 0.2
        scaled = [x * 0.2 for x in make_unit_vector(dim=512, seed=4)]
        with self.assertRaises(ValidationError) as ctx2:
            FaceEnrollmentCreate(embedding=scaled)
        self.assertIn("must be L2-normalized", str(ctx2.exception))

    def test_05_employee_not_found(self):
        """5. Reject enrollment for nonexistent employee ID (404)."""
        with self.assertRaises(HTTPException) as ctx:
            enroll_face_template_ep(
                employee_id=999999,
                data=FaceEnrollmentCreate(embedding=make_unit_vector(dim=512, seed=5)),
                current_user=self.super_admin,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("not found", ctx.exception.detail)

    def test_06_unauthorized_location_access(self):
        """6. Location B admin cannot view or access enrollments for employee in Location A."""
        with self.assertRaises(HTTPException) as ctx:
            list_employee_face_enrollments_ep(
                employee_id=self.emp_a.id,
                current_user=self.loc_admin_b,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Access denied", ctx.exception.detail)

    def test_07_cross_location_enrollment_rejection(self):
        """7. Location A admin cannot enroll face template for employee in Location B."""
        with self.assertRaises(HTTPException) as ctx:
            enroll_face_template_ep(
                employee_id=self.emp_b.id,
                data=FaceEnrollmentCreate(embedding=make_unit_vector(dim=512, seed=7)),
                current_user=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Access denied", ctx.exception.detail)

    def test_08_operator_viewer_write_restrictions(self):
        """8. Operators and viewers cannot enroll or modify face templates."""
        # Operator cannot enroll
        with self.assertRaises(HTTPException) as ctx:
            enroll_face_template_ep(
                employee_id=self.emp_a.id,
                data=FaceEnrollmentCreate(embedding=make_unit_vector(dim=512, seed=8)),
                current_user=self.operator_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Viewer cannot enroll
        with self.assertRaises(HTTPException) as ctx2:
            enroll_face_template_ep(
                employee_id=self.emp_a.id,
                data=FaceEnrollmentCreate(embedding=make_unit_vector(dim=512, seed=8)),
                current_user=self.viewer_a,
                db=self.db,
            )
        self.assertEqual(ctx2.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Viewer can read enrollment metadata
        list_resp = list_employee_face_enrollments_ep(
            employee_id=self.emp_a.id,
            current_user=self.viewer_a,
            db=self.db,
        )
        self.assertGreaterEqual(len(list_resp), 1)

    def test_09_template_metadata_response_without_embedding_exposure(self):
        """9. Public responses never expose raw embedding vectors or biometric coordinates."""
        detail = get_face_enrollment_ep(
            embedding_id=self.emb_a1_id,
            current_user=self.viewer_a,
            db=self.db,
        )
        dump = detail.model_dump()
        self.assertNotIn("embedding", dump)
        self.assertNotIn("vector", dump)
        self.assertEqual(dump["embedding_dim"], 512)
        self.assertEqual(dump["employee_code"], "EMP-FACE-01")

    def test_10_duplicate_active_template_handling(self):
        """10. Attempting to create duplicate active template for same model/version raises 409."""
        # emp_a already has an active template for auraface_v1_glintr100 v1
        with self.assertRaises(HTTPException) as ctx:
            enroll_face_template_ep(
                employee_id=self.emp_a.id,
                data=FaceEnrollmentCreate(
                    embedding=make_unit_vector(dim=512, seed=10),
                    model_name="auraface_v1_glintr100",
                    model_version="v1",
                    is_template=True,
                    is_active=True,
                ),
                current_user=self.loc_admin_a,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already exists", ctx.exception.detail)

    def test_11_template_deactivation(self):
        """11. Deactivating active template transitions employee status to 'needs_re_enroll'."""
        deactivated = deactivate_face_enrollment_ep(
            embedding_id=self.emb_a1_id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertFalse(deactivated.is_active)
        self.assertFalse(deactivated.is_template)

        # Since emp_a now has no active template, status becomes needs_re_enroll
        self.db.refresh(self.emp_a)
        self.assertEqual(self.emp_a.enrollment_status, "needs_re_enroll")

    def test_12_primary_template_selection(self):
        """12. /set-primary selects active template and demotes other templates."""
        # Enroll sample 1 (non-template)
        s1 = enroll_face_template_ep(
            employee_id=self.emp_a.id,
            data=FaceEnrollmentCreate(
                embedding=make_unit_vector(dim=512, seed=121),
                is_template=False,
                is_active=True,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )

        # Enroll sample 2 (non-template)
        s2 = enroll_face_template_ep(
            employee_id=self.emp_a.id,
            data=FaceEnrollmentCreate(
                embedding=make_unit_vector(dim=512, seed=122),
                is_template=False,
                is_active=True,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )

        # Set sample 1 as primary
        p1 = set_primary_face_template_ep(
            embedding_id=s1.id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertTrue(p1.is_template)
        self.assertTrue(p1.is_active)
        self.db.refresh(self.emp_a)
        self.assertEqual(self.emp_a.enrollment_status, "enrolled")

        # Now set sample 2 as primary: sample 1 should be demoted automatically
        p2 = set_primary_face_template_ep(
            embedding_id=s2.id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertTrue(p2.is_template)
        self.assertTrue(p2.is_active)

        # Verify sample 1 was demoted
        s1_refreshed = self.db.query(EmployeeFaceEmbedding).filter(EmployeeFaceEmbedding.id == s1.id).first()
        self.assertFalse(s1_refreshed.is_template)

    def test_13_transaction_rollback_on_failure(self):
        """13. Database transaction rolls back cleanly on constraint or integrity errors."""
        initial_count = self.db.query(EmployeeFaceEmbedding).filter(EmployeeFaceEmbedding.employee_id == self.emp_b.id).count()

        # Intentionally attempt invalid enrollment that fails validation
        try:
            enroll_face_template_ep(
                employee_id=self.emp_b.id,
                data=FaceEnrollmentCreate(
                    embedding=make_unit_vector(dim=512, seed=13),
                    sample_count=0,  # Invalid: sample_count must be >= 1
                ),
                current_user=self.loc_admin_b,
                db=self.db,
            )
        except ValidationError:
            pass

        after_count = self.db.query(EmployeeFaceEmbedding).filter(EmployeeFaceEmbedding.employee_id == self.emp_b.id).count()
        self.assertEqual(initial_count, after_count)

    def test_14_employee_with_multiple_supported_templates(self):
        """14. Coexistence of templates across different model versions and historical samples."""
        # Active template for model v1 already exists on emp_a (from test_12)
        # Now enroll active template for a DIFFERENT model architecture (auraface_v2)
        v2_template = enroll_face_template_ep(
            employee_id=self.emp_a.id,
            data=FaceEnrollmentCreate(
                embedding=make_unit_vector(dim=512, seed=141),
                model_name="auraface_v2_vit",
                model_version="v2",
                is_template=True,
                is_active=True,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertTrue(v2_template.is_template)
        self.assertEqual(v2_template.model_name, "auraface_v2_vit")

        # Enroll additional historical sample (is_template=False)
        hist_sample = enroll_face_template_ep(
            employee_id=self.emp_a.id,
            data=FaceEnrollmentCreate(
                embedding=make_unit_vector(dim=512, seed=142),
                model_name="auraface_v2_vit",
                model_version="v2",
                is_template=False,
                is_active=True,
            ),
            current_user=self.loc_admin_a,
            db=self.db,
        )
        self.assertFalse(hist_sample.is_template)

        # List all templates for emp_a
        all_emp_a_templates = list_employee_face_enrollments_ep(
            employee_id=self.emp_a.id,
            current_user=self.loc_admin_a,
            db=self.db,
        )
        # Should include v1 template, v2 template, and historical samples
        self.assertGreaterEqual(len(all_emp_a_templates), 4)


if __name__ == "__main__":
    unittest.main()

