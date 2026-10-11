import copy
import io
import json
import unittest
import urllib.error
import urllib.parse

from pmi_google_drive import (
    DRIVE_SCOPE, ENV_NAMES, FOLDER_MARKER, MAX_ARTIFACT_BYTES,
    MAX_JSON_BYTES, DriveError, GoogleDriveClient,
)


class Response:
    def __init__(self, data, status=200, headers=None):
        self.data = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.status = status
        self.headers = headers or {}
        self.closed = False
        self.read_sizes = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self, size):
        self.read_sizes.append(size)
        return self.data[:size]


def folder(file_id="folder1", **overrides):
    result = {
        "id": file_id, "name": "PMI Research Reports",
        "mimeType": "application/vnd.google-apps.folder", "trashed": False,
        "owners": [{"permissionId": "principal123"}],
        "appProperties": {FOLDER_MARKER: "1"},
    }
    result.update(overrides)
    return result


class FakeGoogle:
    """Independent in-memory HTTP service; never opens a network connection."""
    def __init__(self):
        self.requests = []
        self.files = {}
        self.contents = {}
        self.permissions = {}
        self.token_response = {
            "access_token": "test-access", "token_type": "Bearer",
            "expires_in": 3600, "scope": DRIVE_SCOPE,
        }
        self.failure = None
        self.list_response = None
        self.media_response = None
        self.permission_response = None

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.failure:
            raise self.failure
        parts = urllib.parse.urlsplit(request.full_url)
        query = urllib.parse.parse_qs(parts.query)
        if parts.netloc == "oauth2.googleapis.com":
            return Response(self.token_response)
        if parts.path.endswith("/about"):
            return Response({"user": {"permissionId": "principal123"}})
        if parts.path.startswith("/upload/drive/v3/files"):
            boundary = request.get_header("Content-type").split("boundary=", 1)[1]
            chunks = request.data.split(("--" + boundary).encode())
            metadata = json.loads(chunks[1].split(b"\r\n\r\n", 1)[1].strip())
            content = chunks[2].split(b"\r\n\r\n", 1)[1][:-2]
            file_id = "file" + str(len(self.files) + 1)
            metadata.update({"id": file_id, "trashed": False, "size": str(len(content)),
                             "owners": [{"permissionId": "principal123"}]})
            self.files[file_id] = metadata
            self.contents[file_id] = content
            return Response({"id": file_id})
        if parts.path.endswith("/files") and request.get_method() == "POST":
            metadata = json.loads(request.data)
            file_id = "folder" + str(len(self.files) + 1)
            metadata.update({"id": file_id, "trashed": False,
                             "owners": [{"permissionId": "principal123"}]})
            self.files[file_id] = metadata
            return Response({"id": file_id})
        if parts.path.endswith("/files"):
            if self.list_response is not None:
                return Response(self.list_response)
            q = query["q"][0]
            if "mimeType = 'application/vnd.google-apps.folder'" in q:
                matches = [value for value in self.files.values()
                           if value.get("mimeType") == "application/vnd.google-apps.folder"
                           and value.get("appProperties", {}).get(FOLDER_MARKER) == "1"
                           and not value.get("trashed")]
            else:
                matches = []
                for value in self.files.values():
                    properties = value.get("appProperties", {})
                    if (all("'" + key + "'" in q and "'" + item + "'" in q
                            for key, item in properties.items())
                            and properties.get("export_id") and not value.get("trashed")
                            and any("'" + parent + "' in parents" in q
                                    for parent in value.get("parents", []))):
                        matches.append(value)
            return Response({"files": copy.deepcopy(matches)})
        file_id = parts.path.split("/")[4]
        if parts.path.endswith("/permissions"):
            if self.permission_response is not None:
                return Response(self.permission_response)
            return Response({"permissions": self.permissions.get(file_id, [
                {"id": "principal123", "role": "owner", "type": "user"}
            ])})
        if query.get("alt") == ["media"]:
            return self.media_response or Response(self.contents[file_id])
        if file_id not in self.files:
            raise urllib.error.HTTPError(request.full_url, 404, "private error", {}, io.BytesIO(b"private body"))
        return Response(copy.deepcopy(self.files[file_id]))

    def mutations(self):
        return [request for request, _ in self.requests
                if request.get_method() == "POST" and "googleapis.com/token" not in request.full_url]


class GoogleDriveClientTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeGoogle()
        self.client = GoogleDriveClient("client-id", "client-secret", "refresh-token", opener=self.server)

    def install_folder(self):
        self.server.files["folder1"] = folder()

    def test_environment_requires_all_three_values_before_any_request(self):
        for absent in ENV_NAMES:
            environment = {name: "configured" for name in ENV_NAMES if name != absent}
            with self.assertRaisesRegex(DriveError, "drive_credentials_missing"):
                GoogleDriveClient.from_environment(environ=environment, opener=self.server)
        self.assertEqual(self.server.requests, [])

    def test_identity_is_stable_dict_and_refreshes_only_once(self):
        self.assertEqual(self.client.identity(), {"principal_id": "google-drive:principal123"})
        self.assertEqual(self.client.identity(), {"principal_id": "google-drive:principal123"})
        self.assertEqual(len(self.server.requests), 2)
        self.assertTrue(all(timeout == 10 for _, timeout in self.server.requests))
        self.assertNotIn("emailAddress", self.server.requests[1][0].full_url)

    def test_token_form_preserves_special_characters(self):
        client = GoogleDriveClient("id+one", "secret&a=b", "refresh+&=%", opener=self.server)
        client.identity()
        form = urllib.parse.parse_qs(self.server.requests[0][0].data.decode())
        self.assertEqual(form["client_secret"], ["secret&a=b"])
        self.assertEqual(form["refresh_token"], ["refresh+&=%"])

    def test_expired_access_token_refreshes_in_memory(self):
        now = [0.0]
        client = GoogleDriveClient("id", "secret", "refresh", opener=self.server, clock=lambda: now[0])
        client.identity()
        self.install_folder()
        now[0] = 3600
        client.verify_private_folder("folder1")
        self.assertEqual(sum("oauth2.googleapis.com" in req.full_url for req, _ in self.server.requests), 2)

    def test_folder_creation_is_private_and_reused(self):
        created = self.client.ensure_private_folder()
        self.assertEqual(created["id"], "folder1")
        self.assertEqual(created["webViewLink"], "https://drive.google.com/drive/folders/folder1")
        self.assertEqual(self.client.ensure_private_folder(), created)
        self.assertEqual(len(self.server.mutations()), 1)
        request = self.server.mutations()[0]
        metadata = json.loads(request.data)
        self.assertNotIn("parents", metadata)
        self.assertNotIn("permissions", metadata)

    def test_existing_folder_id_must_be_created_by_this_app(self):
        self.server.files["folder1"] = folder(appProperties={})
        with self.assertRaisesRegex(DriveError, "folder_not_app_managed"):
            self.client.ensure_private_folder(folder_id="folder1")
        self.assertEqual(self.server.mutations(), [])

    def test_supplied_missing_folder_does_not_create_another(self):
        with self.assertRaises(DriveError) as caught:
            self.client.ensure_private_folder(folder_id="missing")
        self.assertEqual(caught.exception.http_status, 404)
        self.assertEqual(self.server.mutations(), [])

    def test_folder_rejects_trashed_nonfolder_other_owner_or_shared_drive(self):
        for changes, code in [({"trashed": True}, "invalid_report_folder"),
                              ({"mimeType": "application/json"}, "invalid_report_folder"),
                              ({"owners": [{"permissionId": "different"}]}, "drive_not_owner"),
                              ({"driveId": "shared1"}, "drive_not_owner")]:
            with self.subTest(changes=changes):
                self.server.files["folder1"] = folder(**changes)
                with self.assertRaisesRegex(DriveError, code):
                    self.client.verify_private_folder("folder1")

    def test_public_domain_group_and_other_user_permissions_rejected(self):
        self.install_folder()
        for permission_type in ("anyone", "domain", "group", "user"):
            with self.subTest(permission_type=permission_type):
                self.server.permissions["folder1"] = [
                    {"id": "principal123", "role": "owner", "type": "user"},
                    {"id": "other", "role": "reader", "type": permission_type},
                ]
                with self.assertRaisesRegex(DriveError, "drive_not_private"):
                    self.client.verify_private_folder("folder1")

    def test_empty_and_looping_permissions_fail_closed(self):
        self.install_folder()
        for response in ({"permissions": []},
                         {"permissions": [], "nextPageToken": "loop"}):
            with self.subTest(response=response):
                self.server.permission_response = response
                with self.assertRaisesRegex(DriveError, "privacy_verification_failed"):
                    self.client.verify_private_folder("folder1")

    def test_incomplete_listing_cannot_trigger_duplicate_creation(self):
        self.server.list_response = {"files": [], "nextPageToken": "remaining"}
        with self.assertRaisesRegex(DriveError, "drive_lookup_incomplete"):
            self.client.ensure_private_folder()
        self.assertEqual(self.server.mutations(), [])

    def test_duplicate_managed_folders_require_resolution(self):
        self.server.files.update({"folder1": folder(), "folder2": folder("folder2")})
        with self.assertRaisesRegex(DriveError, "ambiguous_report_folder"):
            self.client.ensure_private_folder()

    def test_upload_roundtrip_and_partial_retry_does_not_overwrite(self):
        self.install_folder()
        content = b'{"review_count":30,"unicode":"\xe2\x98\x83"}\n'
        arguments = ("folder1", "research.json", "application/json", content, "export-123", "full_research")
        first = self.client.upload(*arguments)
        self.assertEqual(self.client.download(first["id"]), content)
        second = self.client.upload(*arguments)
        self.assertEqual(second, first)
        self.assertEqual(len(self.server.mutations()), 1)
        stored = self.server.files[first["id"]]
        self.assertEqual(stored["appProperties"], {"export_id": "export-123", "artifact_kind": "full_research"})

    def test_different_artifact_kind_gets_separate_file(self):
        self.install_folder()
        json_file = self.client.upload("folder1", "research.json", "application/json", b"{}", "same", "full")
        text_file = self.client.upload("folder1", "summary.txt", "text/plain", b"30 reviews", "same", "summary")
        self.assertNotEqual(json_file["id"], text_file["id"])
        self.assertEqual(len(self.server.mutations()), 2)

    def test_existing_artifact_collision_or_added_sharing_rejected(self):
        self.install_folder()
        arguments = ("folder1", "research.json", "application/json", b"{}", "same", "full")
        uploaded = self.client.upload(*arguments)
        with self.assertRaisesRegex(DriveError, "artifact_metadata_mismatch"):
            self.client.upload("folder1", "research.json", "application/json", b"larger", "same", "full")
        self.server.permissions[uploaded["id"]] = [{"id": "public", "type": "anyone", "role": "reader"}]
        with self.assertRaisesRegex(DriveError, "drive_not_private"):
            self.client.upload(*arguments)
        with self.assertRaisesRegex(DriveError, "drive_not_private"):
            self.client.download(uploaded["id"])
        self.assertEqual(len(self.server.mutations()), 1)

    def test_full_download_bounded_with_and_without_length_header(self):
        self.install_folder()
        uploaded = self.client.upload("folder1", "research.json", "application/json", b"{}", "same", "full")
        for response in (Response(b"x" * (MAX_ARTIFACT_BYTES + 1)),
                         Response(b"", headers={"Content-Length": str(MAX_ARTIFACT_BYTES + 1)})):
            with self.subTest(headers=response.headers):
                self.server.media_response = response
                with self.assertRaisesRegex(DriveError, "response_too_large"):
                    self.client.download(uploaded["id"])
                self.assertTrue(response.closed)
                self.assertTrue(all(size == MAX_ARTIFACT_BYTES + 1 for size in response.read_sizes))

    def test_oversized_upload_rejected_before_network(self):
        with self.assertRaisesRegex(DriveError, "artifact_too_large"):
            self.client.upload("folder1", "research.json", "application/json", b"x" * (MAX_ARTIFACT_BYTES + 1), "same", "full")
        self.assertEqual(self.server.requests, [])

    def test_invalid_path_or_mime_cannot_change_destination(self):
        with self.assertRaisesRegex(DriveError, "invalid_file_id"):
            self.client.download("../other?token=secret")
        with self.assertRaisesRegex(DriveError, "invalid_artifact"):
            self.client.upload("folder1", "file", "text/plain\r\nX: leak", b"x", "same", "full")
        self.assertEqual(self.server.requests, [])

    def test_token_and_remote_error_details_never_enter_error(self):
        leaked = "client-secret refresh-token test-access private-body"
        for failure in (OSError(leaked), urllib.error.HTTPError(
                "https://oauth2.googleapis.com/token?" + leaked, 401, leaked, {}, io.BytesIO(leaked.encode()))):
            with self.subTest(failure_type=type(failure).__name__):
                self.server.failure = failure
                with self.assertRaises(DriveError) as caught:
                    self.client.identity()
                self.assertNotIn("secret", str(caught.exception))
                self.assertNotIn("private", str(caught.exception))
                self.assertEqual(caught.exception.__suppress_context__, True)

    def test_oauth_response_rejects_broad_scope_and_malformed_types(self):
        for changes, code in [({"scope": "https://www.googleapis.com/auth/drive"}, "unexpected_oauth_scope"),
                              ({"scope": {}}, "invalid_oauth_response"),
                              ({"token_type": 1}, "invalid_oauth_response"),
                              ({"expires_in": -1}, "invalid_oauth_response"),
                              ({"access_token": None}, "invalid_oauth_response")]:
            with self.subTest(changes=changes):
                self.server.token_response = {"access_token": "test", **changes}
                with self.assertRaisesRegex(DriveError, code):
                    self.client.identity()

    def test_json_response_cap_and_redirect_denial(self):
        class FixedOpener:
            def __init__(self, response):
                self.response = response

            def open(self, request, timeout):
                return self.response

        client = GoogleDriveClient("id", "secret", "refresh", opener=FixedOpener(Response(b"x" * (MAX_JSON_BYTES + 1))))
        with self.assertRaisesRegex(DriveError, "response_too_large"):
            client.identity()
        self.server.failure = urllib.error.HTTPError("https://example.invalid", 302, "redirect", {}, io.BytesIO())
        with self.assertRaisesRegex(DriveError, "redirect_not_allowed") as caught:
            self.client.identity()
        self.assertEqual(caught.exception.http_status, 302)


if __name__ == "__main__":
    unittest.main()
