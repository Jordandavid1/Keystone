"""
KEYSTONE Milestone M1 Retest: Dedicated Empirical Vulnerability Verification
Tests the 5 required verification targets:
1. Sibling directory traversal attempts rejected with ILLEGAL_STORAGE_PATH
2. user_id / asset_id traversal sequences sanitized
3. Dot-only filenames fall back safely to asset.bin
4. Arbitrary / cross-tenant storage keys in POST /v1/assets rejected with HTTP 400 ILLEGAL_STORAGE_KEY
5. Cross-tenant child_asset_id in POST /v1/assets/{asset_id}/relationships rejected with HTTP 404
"""

import os
import re
import sys
import uuid
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from apps.api.src.server import app
from apps.api.src.storage.service import (
    generate_storage_key,
    generate_signed_url,
    validate_signed_url,
    LocalStorageProvider,
)
from apps.api.src.auth.security import generate_token, hash_password
from apps.api.src.db.models import User, Project, Asset
from apps.api.src.db.session import async_session_factory, init_db


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    import asyncio
    asyncio.run(init_db())


class TestStorageSanitizationAndContainment:
    """Tests 1, 2, and 3: Sibling traversal, ID sanitization, dot fallback."""

    def test_sibling_directory_traversal_rejected_with_illegal_storage_path(self):
        provider = LocalStorageProvider()
        sibling_keys = [
            "../storage_evil/file.txt",
            "../../outside.txt",
            "../data/sibling.txt",
            "tenants/usr1/assets/ast1/../../../../../evil.txt",
            "tenants/../../evil.txt",
            "foo/../../bar",
            "..",
            "../",
            "..\\evil.txt",
            "..\\..\\evil.txt",
        ]
        for key in sibling_keys:
            with pytest.raises(ValueError) as excinfo:
                provider._resolve_path(key)
            assert "ILLEGAL_STORAGE_PATH" in str(excinfo.value), f"Failed for key: {key}, got: {excinfo.value}"

    @pytest.mark.asyncio
    async def test_storage_provider_methods_reject_sibling_traversal(self):
        provider = LocalStorageProvider()
        bad_key = "../storage_evil/payload.bin"

        with pytest.raises(ValueError, match="ILLEGAL_STORAGE_PATH"):
            await provider.put_object(bad_key, b"evil data")

        with pytest.raises(ValueError, match="ILLEGAL_STORAGE_PATH"):
            await provider.get_object(bad_key)

        with pytest.raises(ValueError, match="ILLEGAL_STORAGE_PATH"):
            await provider.delete_object(bad_key)

        with pytest.raises(ValueError, match="ILLEGAL_STORAGE_PATH"):
            await provider.exists(bad_key)

    def test_user_id_and_asset_id_traversal_sanitized(self):
        malicious_users = [
            "../../admin",
            "..\\..\\admin",
            "user/with/slashes",
            "user\\with\\backslashes",
            "user\x00with\x00nulls",
            "%2e%2e%2fadmin",
            "../tenant_victim",
            "....",
            "admin-1; DROP TABLE users;--",
        ]
        malicious_assets = [
            "../evil_asset",
            "..\\evil_asset",
            "ast/sub/dir",
            "ast\x00",
            "....",
            "../../..",
        ]

        pattern = re.compile(r"^tenants/([a-zA-Z0-9_-]+)/assets/([a-zA-Z0-9_-]+)/([a-zA-Z0-9._-]+)$")

        for u in malicious_users:
            for a in malicious_assets:
                key = generate_storage_key(u, a, "image.png")
                match = pattern.match(key)
                assert match is not None, f"Key '{key}' failed pattern matching"
                clean_user, clean_asset, clean_file = match.groups()
                assert ".." not in clean_user
                assert "/" not in clean_user
                assert "\\" not in clean_user
                assert ".." not in clean_asset
                assert "/" not in clean_asset
                assert "\\" not in clean_asset

    def test_dot_only_filenames_fallback_to_asset_bin(self):
        dot_filenames = [
            ".",
            "..",
            "...",
            "....",
            ".....",
            "." * 50,
            "",
            "../",
            r"..\..",
            r"....\....",
            "/....",
            "path/to/....",
            r"path\to\..",
        ]
        for name in dot_filenames:
            key = generate_storage_key("usr_test", "ast_test", name)
            assert key.endswith("/asset.bin"), f"Expected key ending in /asset.bin for input '{name}', got '{key}'"


class TestHttpCrossTenantStorageAndLineageIsolation:
    """Tests 4 and 5: Cross-tenant storage key rejection and Lineage 404."""

    @pytest.fixture(autouse=True)
    def setup_users(self):
        self.client = TestClient(app)
        self.user_a_id = str(uuid.uuid4())
        self.user_b_id = str(uuid.uuid4())
        self.token_a = generate_token(self.user_a_id, role="creator")
        self.token_b = generate_token(self.user_b_id, role="creator")
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}
        self.headers_b = {"Authorization": f"Bearer {self.token_b}"}

        # Seed projects in DB
        import asyncio
        async def _seed():
            async with async_session_factory() as session:
                u_a = User(id=self.user_a_id, email=f"a_{self.user_a_id[:8]}@ex.com", password_hash=hash_password("Pass1!"), status="active")
                u_b = User(id=self.user_b_id, email=f"b_{self.user_b_id[:8]}@ex.com", password_hash=hash_password("Pass1!"), status="active")
                session.add_all([u_a, u_b])
                await session.commit()
        asyncio.run(_seed())

    def test_arbitrary_and_cross_tenant_storage_keys_in_post_assets_rejected_with_400(self):
        # 1. Cross-tenant storage key belonging to tenant B submitted by tenant A
        cross_tenant_key = f"tenants/{self.user_b_id}/assets/ast_1/photo.png"
        res = self.client.post("/v1/assets", headers=self.headers_a, json={
            "filename": "photo.png",
            "mime_type": "image/png",
            "byte_size": 1024,
            "storage_key": cross_tenant_key
        })
        assert res.status_code == 400
        assert "ILLEGAL_STORAGE_KEY" in res.json().get("detail", "")
        assert f"Key belongs to tenant '{self.user_b_id}'" in res.json().get("detail", "")

        # 2. Directory traversal in storage key
        traversal_keys = [
            f"tenants/{self.user_a_id}/assets/ast_1/../../evil.png",
            f"tenants/../../admin/assets/ast_1/img.png",
            "../evil_storage/asset.bin",
            "/etc/passwd",
            f"tenants/{self.user_a_id}/assets/ast_1/....",
            f"tenants/{self.user_a_id}/assets/ast_1/..",
            f"tenants/{self.user_a_id}/assets/ast_1/.",
            "random_malformed_key",
        ]
        for bad_key in traversal_keys:
            res = self.client.post("/v1/assets", headers=self.headers_a, json={
                "filename": "test.png",
                "mime_type": "image/png",
                "byte_size": 1024,
                "storage_key": bad_key
            })
            assert res.status_code == 400, f"Expected 400 for bad storage_key '{bad_key}', got {res.status_code}"
            assert "ILLEGAL_STORAGE_KEY" in res.json().get("detail", "")

        # 3. Legitimate storage key belonging to tenant A passes
        legit_key = f"tenants/{self.user_a_id}/assets/ast_valid/valid.png"
        res_ok = self.client.post("/v1/assets", headers=self.headers_a, json={
            "filename": "valid.png",
            "mime_type": "image/png",
            "byte_size": 1024,
            "storage_key": legit_key
        })
        assert res_ok.status_code == 200
        assert res_ok.json().get("storage_key") == legit_key

        # 4. Auto-generated key (omitted storage_key) passes and is scoped to tenant A
        res_auto = self.client.post("/v1/assets", headers=self.headers_a, json={
            "filename": "auto.png",
            "mime_type": "image/png",
            "byte_size": 2048
        })
        assert res_auto.status_code == 200
        auto_key = res_auto.json().get("storage_key")
        assert auto_key.startswith(f"tenants/{self.user_a_id}/assets/")
        assert auto_key.endswith("/auto.png")

    def test_cross_tenant_child_asset_id_in_relationships_rejected_with_404(self):
        # 1. Tenant A creates an asset
        res_a = self.client.post("/v1/assets", headers=self.headers_a, json={
            "filename": "parent_a.png",
            "mime_type": "image/png",
            "byte_size": 1024
        })
        assert res_a.status_code == 200
        asset_a_id = res_a.json()["id"]

        # 2. Tenant B creates an asset
        res_b = self.client.post("/v1/assets", headers=self.headers_b, json={
            "filename": "child_b.png",
            "mime_type": "image/png",
            "byte_size": 2048
        })
        assert res_b.status_code == 200
        asset_b_id = res_b.json()["id"]

        # 3. Tenant A attempts to link child_asset_id = asset_b_id (cross-tenant)
        # Expected: HTTP 404 Not Found ("Child asset not found or access denied")
        res_rel = self.client.post(f"/v1/assets/{asset_a_id}/relationships", headers=self.headers_a, json={
            "child_asset_id": asset_b_id,
            "relationship_type": "edit"
        })
        assert res_rel.status_code == 404
        assert "Child asset not found or access denied" in res_rel.json().get("detail", "")

        # 4. Tenant B attempts to use Tenant A's asset as parent
        # Expected: HTTP 404 Not Found ("Parent asset not found")
        res_rel_rev = self.client.post(f"/v1/assets/{asset_a_id}/relationships", headers=self.headers_b, json={
            "child_asset_id": asset_b_id,
            "relationship_type": "edit"
        })
        assert res_rel_rev.status_code == 404
        assert "Parent asset not found" in res_rel_rev.json().get("detail", "")

        # 5. Legitimate intra-tenant relationship succeeds
        res_a2 = self.client.post("/v1/assets", headers=self.headers_a, json={
            "filename": "child_a.png",
            "mime_type": "image/png",
            "byte_size": 1024
        })
        assert res_a2.status_code == 200
        asset_a2_id = res_a2.json()["id"]

        res_ok_rel = self.client.post(f"/v1/assets/{asset_a_id}/relationships", headers=self.headers_a, json={
            "child_asset_id": asset_a2_id,
            "relationship_type": "edit"
        })
        assert res_ok_rel.status_code == 200
        assert res_ok_rel.json()["relationship"]["parent_asset_id"] == asset_a_id
        assert res_ok_rel.json()["relationship"]["child_asset_id"] == asset_a2_id
