"""
Comprehensive Automated Test Suite for Camera Intelligence Authentication & Authorization APIs
Covers all 15 requirements specified in Phase 2, Task 7.

Runs using standard Python unittest (without requiring third-party test runners).
"""

import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from jose import jwt

# Add server directory to path
SERVER_ROOT = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.database.session import SessionLocal
from app.models.user import User, user_locations
from app.models.location import Location
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth import authenticate_user, create_user_token_response
from app.api.deps import (
    get_current_user,
    require_super_admin,
    require_location_admin,
    require_operator,
    require_viewer,
    require_location_access,
)
from app.api.v1.endpoints.auth import (
    login as login_endpoint,
    get_me as get_me_endpoint,
    logout as logout_endpoint,
    probe_super_admin,
    probe_location_admin,
    probe_operator,
    probe_viewer,
    probe_location_access,
)


class TestAuthAndAuthorization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up database session and test fixtures."""
        cls.db = SessionLocal()

        # Target existing bootstrap super_admin
        cls.admin_email = "admin@cameraintelligence.com"
        cls.admin_password = "SuperSecureAdminPassword2026!"
        cls.admin_user = (
            cls.db.query(User).filter(User.email == cls.admin_email).first()
        )
        assert cls.admin_user is not None, "Bootstrap super_admin not found in database!"
        cls.admin_user.password_hash = get_password_hash(cls.admin_password)
        cls.db.commit()

        # Create temporary test locations
        cls.loc_a = Location(
            name="Test Branch Alpha",
            timezone="UTC",
            is_active=True,
        )
        cls.loc_b = Location(
            name="Test Branch Beta",
            timezone="UTC",
            is_active=True,
        )
        cls.db.add_all([cls.loc_a, cls.loc_b])
        cls.db.commit()
        cls.db.refresh(cls.loc_a)
        cls.db.refresh(cls.loc_b)

        # Common test password
        cls.test_password = "TestUserPassword123!"
        hashed_pw = get_password_hash(cls.test_password)

        # Create temporary test users for role & location tests
        cls.loc_admin_user = User(
            email="test.locadmin@test.internal",
            full_name="Test Location Admin",
            password_hash=hashed_pw,
            system_role="location_admin",
            is_active=True,
        )
        cls.operator_user = User(
            email="test.operator@test.internal",
            full_name="Test Operator",
            password_hash=hashed_pw,
            system_role="operator",
            is_active=True,
        )
        cls.viewer_user = User(
            email="test.viewer@test.internal",
            full_name="Test Viewer",
            password_hash=hashed_pw,
            system_role="viewer",
            is_active=True,
        )
        cls.inactive_user = User(
            email="test.inactive@test.internal",
            full_name="Test Inactive",
            password_hash=hashed_pw,
            system_role="viewer",
            is_active=False,
        )

        cls.db.add_all([
            cls.loc_admin_user,
            cls.operator_user,
            cls.viewer_user,
            cls.inactive_user,
        ])
        cls.db.commit()
        for u in [cls.loc_admin_user, cls.operator_user, cls.viewer_user, cls.inactive_user]:
            cls.db.refresh(u)

        # Assign test.locadmin to Location Alpha only
        cls.db.execute(
            user_locations.insert().values(
                user_id=cls.loc_admin_user.id,
                location_id=cls.loc_a.id,
            )
        )
        # Assign test.operator to Location Alpha only
        cls.db.execute(
            user_locations.insert().values(
                user_id=cls.operator_user.id,
                location_id=cls.loc_a.id,
            )
        )
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary test users and locations, leaving only super_admin."""
        try:
            # Delete assignments
            test_user_ids = [
                cls.loc_admin_user.id,
                cls.operator_user.id,
                cls.viewer_user.id,
                cls.inactive_user.id,
            ]
            cls.db.execute(
                user_locations.delete().where(user_locations.c.user_id.in_(test_user_ids))
            )
            # Delete test users
            cls.db.query(User).filter(User.id.in_(test_user_ids)).delete(
                synchronize_session=False
            )
            # Delete test locations
            cls.db.query(Location).filter(
                Location.id.in_([cls.loc_a.id, cls.loc_b.id])
            ).delete(synchronize_session=False)
            cls.db.commit()
        except Exception as e:
            cls.db.rollback()
            print(f"Cleanup warning: {e}")
        finally:
            cls.db.close()

    # -------------------------------------------------------------------------
    # TEST CASES (1 to 15)
    # -------------------------------------------------------------------------

    def test_01_successful_login(self):
        """1. Successful login returns access token and valid expiration info."""
        req = LoginRequest(email=self.admin_email, password=self.admin_password)
        resp = login_endpoint(login_data=req, db=self.db)

        self.assertIsInstance(resp, TokenResponse)
        self.assertTrue(len(resp.access_token) > 20)
        self.assertEqual(resp.token_type, "bearer")
        self.assertGreater(resp.expires_in, 0)
        self.assertIsInstance(resp.expires_at, datetime)
        self.assertEqual(resp.user.email, self.admin_email)
        self.assertEqual(resp.user.system_role, "super_admin")

    def test_02_incorrect_password(self):
        """2. Incorrect password raises HTTP 401 with generic error."""
        req = LoginRequest(email=self.admin_email, password="WrongPassword999!")
        with self.assertRaises(HTTPException) as ctx:
            login_endpoint(login_data=req, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(ctx.exception.detail, "Invalid email or password.")

    def test_03_unknown_email(self):
        """3. Unknown email raises HTTP 401 with generic error."""
        req = LoginRequest(email="nonexistent.user@nowhere.com", password="AnyPassword123!")
        with self.assertRaises(HTTPException) as ctx:
            login_endpoint(login_data=req, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(ctx.exception.detail, "Invalid email or password.")

    def test_04_inactive_user_login_rejection(self):
        """4. Inactive user login is rejected with HTTP 403."""
        req = LoginRequest(email=self.inactive_user.email, password=self.test_password)
        with self.assertRaises(HTTPException) as ctx:
            login_endpoint(login_data=req, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("inactive", ctx.exception.detail.lower())

    def test_05_valid_jwt_authentication(self):
        """5. Valid JWT authentication loads correct SQLAlchemy user from DB."""
        token, _, _ = create_access_token(subject=str(self.admin_user.id))
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = get_current_user(credentials=creds, db=self.db)

        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.admin_user.id)
        self.assertEqual(user.email, self.admin_email)

    def test_06_invalid_jwt_rejection(self):
        """6. Invalid or tampered JWT raises HTTP 401."""
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalidpayload.invalidsig"
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=invalid_token)
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(credentials=creds, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_07_expired_jwt_rejection(self):
        """7. Expired JWT raises HTTP 401."""
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": str(self.admin_user.id),
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(credentials=creds, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_08_missing_bearer_token(self):
        """8. Missing or empty Bearer token fails validation."""
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(credentials=creds, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_09_super_admin_global_access(self):
        """9. Super-admin has global access to all locations without user_locations rows."""
        # Location A
        loc_a = require_location_access(
            location_id=self.loc_a.id,
            current_user=self.admin_user,
            db=self.db,
        )
        self.assertEqual(loc_a.id, self.loc_a.id)

        # Location B (admin has 0 user_locations entries, still succeeds)
        loc_b = require_location_access(
            location_id=self.loc_b.id,
            current_user=self.admin_user,
            db=self.db,
        )
        self.assertEqual(loc_b.id, self.loc_b.id)

        # Probe super-admin endpoint
        probe_res = probe_super_admin(admin=self.admin_user)
        self.assertEqual(probe_res["user_id"], self.admin_user.id)

    def test_10_location_admin_assigned_location(self):
        """10. Location-admin can access their explicitly assigned location."""
        loc = require_location_access(
            location_id=self.loc_a.id,
            current_user=self.loc_admin_user,
            db=self.db,
        )
        self.assertEqual(loc.id, self.loc_a.id)

        probe_res = probe_location_admin(admin=self.loc_admin_user)
        self.assertEqual(probe_res["user_id"], self.loc_admin_user.id)

    def test_11_location_admin_unassigned_location_rejection(self):
        """11. Location-admin is rejected with HTTP 403 when accessing unassigned location."""
        with self.assertRaises(HTTPException) as ctx:
            require_location_access(
                location_id=self.loc_b.id,
                current_user=self.loc_admin_user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("not authorized", ctx.exception.detail.lower())

    def test_12_operator_access_restrictions(self):
        """12. Operator can access operator endpoints but is rejected from admin-only endpoints."""
        # Operator succeeds on operator endpoint
        op_res = probe_operator(operator=self.operator_user)
        self.assertEqual(op_res["user_id"], self.operator_user.id)

        # Operator is rejected from location_admin endpoint
        with self.assertRaises(HTTPException) as ctx:
            require_location_admin(current_user=self.operator_user)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Operator is rejected from super_admin endpoint
        with self.assertRaises(HTTPException) as ctx:
            require_super_admin(current_user=self.operator_user)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_13_viewer_read_only_permissions(self):
        """13. Viewer has viewer access but is rejected from operator and admin endpoints."""
        # Viewer succeeds on viewer endpoint
        v_res = probe_viewer(viewer=self.viewer_user)
        self.assertEqual(v_res["user_id"], self.viewer_user.id)

        # Viewer is rejected from operator endpoint
        with self.assertRaises(HTTPException) as ctx:
            require_operator(current_user=self.viewer_user)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

        # Viewer is rejected from location_admin endpoint
        with self.assertRaises(HTTPException) as ctx:
            require_location_admin(current_user=self.viewer_user)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_14_inactive_user_token_rejection(self):
        """14. A valid token for an inactive/deactivated user is rejected with HTTP 403."""
        # Generate valid token for inactive user
        token, _, _ = create_access_token(subject=str(self.inactive_user.id))
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(credentials=creds, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("inactive", ctx.exception.detail.lower())

    def test_15_password_hash_never_exposed(self):
        """15. Password hash is never exposed in user schemas or API responses."""
        req = LoginRequest(email=self.admin_email, password=self.admin_password)
        login_resp = login_endpoint(login_data=req, db=self.db)
        user_dict = login_resp.user.model_dump()
        self.assertNotIn("password", user_dict)
        self.assertNotIn("password_hash", user_dict)

        me_resp = get_me_endpoint(current_user=self.admin_user)
        me_dict = me_resp.model_dump()
        self.assertNotIn("password", me_dict)
        self.assertNotIn("password_hash", me_dict)


if __name__ == "__main__":
    unittest.main()

