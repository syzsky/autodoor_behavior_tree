import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestNoopAuthService(unittest.TestCase):
    def setUp(self):
        from bt_services.auth_service import NoopAuthService
        self.svc = NoopAuthService()

    def test_verify_token_returns_anonymous(self):
        from bt_services.auth_service import AuthPrincipal
        principal = self.svc.verify_token("any_token")
        self.assertIsInstance(principal, AuthPrincipal)
        self.assertEqual(principal.user_id, "anonymous")

    def test_authenticate_returns_anonymous(self):
        principal = self.svc.authenticate({"username": "x"})
        self.assertEqual(principal.user_id, "anonymous")

    def test_is_authenticated_always_true(self):
        self.assertTrue(self.svc.is_authenticated())

    def test_get_current_principal(self):
        principal = self.svc.get_current_principal()
        self.assertIsNotNone(principal)

    def test_has_role_always_true(self):
        self.assertTrue(self.svc.has_role("admin"))
        self.assertTrue(self.svc.has_role("any_role"))

    def test_has_permission_always_true(self):
        self.assertTrue(self.svc.has_permission("tree:start"))
        self.assertTrue(self.svc.has_permission("any:permission"))

    def test_logout_no_exception(self):
        self.svc.logout()


class TestPermissionMatrix(unittest.TestCase):
    def test_permissions_defined(self):
        from bt_services.auth_service import PERMISSIONS
        self.assertGreater(len(PERMISSIONS), 0)
        self.assertIn("tree:start", PERMISSIONS)
        self.assertIn("blackboard:read", PERMISSIONS)

    def test_role_permissions_defined(self):
        from bt_services.auth_service import ROLE_PERMISSIONS
        self.assertIn("admin", ROLE_PERMISSIONS)
        self.assertIn("operator", ROLE_PERMISSIONS)
        self.assertIn("viewer", ROLE_PERMISSIONS)
        self.assertIn("anonymous", ROLE_PERMISSIONS)
        # admin 拥有全部权限
        from bt_services.auth_service import PERMISSIONS
        self.assertEqual(len(ROLE_PERMISSIONS["admin"]), len(PERMISSIONS))

    def test_public_endpoints(self):
        from bt_services.auth_service import PUBLIC_ENDPOINTS
        self.assertIn("/api/v1/auth/login", PUBLIC_ENDPOINTS)
        self.assertIn("/api/v1/health", PUBLIC_ENDPOINTS)


if __name__ == '__main__':
    unittest.main()
