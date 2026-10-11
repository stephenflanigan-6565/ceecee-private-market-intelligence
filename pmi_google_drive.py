"""Small, private Google Drive export client using user-owned OAuth credentials.

Only environment configuration and in-memory state contain credentials.  Public
errors contain fixed codes, never remote response bodies or request details.
The default urllib opener preserves the runtime's proxy and certificate trust.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
TOKEN_URL = "https://oauth2.googleapis.com/token"
MAX_JSON_BYTES = 1024 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
FOLDER_MARKER = "pmi_report_folder"
ENV_NAMES = (
    "PMI_GOOGLE_DRIVE_CLIENT_ID",
    "PMI_GOOGLE_DRIVE_CLIENT_SECRET",
    "PMI_GOOGLE_DRIVE_REFRESH_TOKEN",
)
_FILE_ID = re.compile(r"[A-Za-z0-9_-]{1,256}\Z")
_MIME_TYPE = re.compile(r"[A-Za-z0-9!#$&^_.+\-]+/[A-Za-z0-9!#$&^_.+\-]+\Z")


class DriveError(RuntimeError):
    """Safe error suitable for application status and logs."""

    def __init__(self, code: str, http_status: int | None = None):
        self.code = code
        self.http_status = http_status
        super().__init__(code)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward OAuth credentials or artifact contents to a redirect.
        return None


def _q_value(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _valid_id(value: Any) -> str:
    if not isinstance(value, str) or not _FILE_ID.fullmatch(value):
        raise DriveError("invalid_file_id")
    return value


class GoogleDriveClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        *,
        opener=None,
        timeout: float = 10.0,
        clock=time.monotonic,
    ):
        if any(not isinstance(value, str) or not value for value in
               (client_id, client_secret, refresh_token)):
            raise DriveError("drive_credentials_missing")
        if not 0 < timeout <= 30:
            raise DriveError("invalid_timeout")
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._opener = opener or urllib.request.build_opener(_NoRedirect())
        self._timeout = timeout
        self._clock = clock
        self._access_token = None
        self._token_expires = 0.0
        self._permission_id = None

    @classmethod
    def from_environment(cls, *, environ=None, opener=None, **kwargs):
        configured = os.environ if environ is None else environ
        return cls(*(configured.get(name, "") for name in ENV_NAMES),
                   opener=opener, **kwargs)

    def _request(self, request, *, limit: int) -> bytes:
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                status = getattr(response, "status", 200)
                if not 200 <= status < 300:
                    raise DriveError("drive_http_error", status)
                length = response.headers.get("Content-Length")
                if length is not None:
                    try:
                        too_large = int(length) > limit
                    except (ValueError, TypeError):
                        raise DriveError("invalid_content_length") from None
                    if too_large:
                        raise DriveError("response_too_large")
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise DriveError("response_too_large")
                return data
        except DriveError:
            raise
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            code = "redirect_not_allowed" if 300 <= status < 400 else "drive_http_error"
            raise DriveError(code, status) from None
        except Exception:
            # Transport exceptions can contain tokens, request URLs, or bodies.
            raise DriveError("drive_transport_error") from None

    def _json(self, request) -> dict:
        raw = self._request(request, limit=MAX_JSON_BYTES)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise DriveError("invalid_drive_response") from None
        if not isinstance(result, dict):
            raise DriveError("invalid_drive_response")
        return result

    def _token(self) -> str:
        if self._access_token and self._clock() < self._token_expires:
            return self._access_token
        form = urllib.parse.urlencode({
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }).encode("ascii")
        result = self._json(urllib.request.Request(
            TOKEN_URL, data=form, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ))
        token = result.get("access_token")
        token_type = result.get("token_type", "Bearer")
        if (not isinstance(token, str) or not token or
                not isinstance(token_type, str) or token_type.lower() != "bearer"):
            raise DriveError("invalid_oauth_response")
        if "scope" in result:
            if not isinstance(result["scope"], str):
                raise DriveError("invalid_oauth_response")
            if set(result["scope"].split()) != {DRIVE_SCOPE}:
                raise DriveError("unexpected_oauth_scope")
        try:
            lifetime = float(result.get("expires_in", 3600))
        except (ValueError, TypeError):
            raise DriveError("invalid_oauth_response") from None
        if not 0 < lifetime <= 86400:
            raise DriveError("invalid_oauth_response")
        self._access_token = token
        self._token_expires = self._clock() + max(0, lifetime - 60)
        return token

    def _api(self, path: str, *, query=None, body=None, method="GET") -> dict:
        url = DRIVE_API + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = None if body is None else json.dumps(body).encode("utf-8")
        return self._json(urllib.request.Request(
            url, data=data, method=method, headers={
                "Authorization": "Bearer " + self._token(),
                "Content-Type": "application/json; charset=UTF-8",
            },
        ))

    def identity(self) -> dict:
        if self._permission_id is None:
            result = self._api("/about", query={"fields": "user(permissionId)"})
            user = result.get("user")
            permission_id = user.get("permissionId") if isinstance(user, dict) else None
            if not isinstance(permission_id, str) or not permission_id:
                raise DriveError("drive_identity_unavailable")
            self._permission_id = permission_id
        return {"principal_id": "google-drive:" + self._permission_id}

    def _metadata(self, file_id: str) -> dict:
        result = self._api("/files/" + _valid_id(file_id), query={
            "fields": "id,name,mimeType,trashed,driveId,owners(permissionId),"
                      "appProperties,parents,size,webViewLink",
        })
        if result.get("id") != file_id:
            raise DriveError("invalid_drive_response")
        return result

    def _private_owned(self, metadata: dict) -> None:
        self.identity()
        owners = metadata.get("owners")
        if (metadata.get("driveId") or not isinstance(owners, list) or
                len(owners) != 1 or not isinstance(owners[0], dict) or
                owners[0].get("permissionId") != self._permission_id):
            raise DriveError("drive_not_owner")
        file_id = _valid_id(metadata.get("id"))
        page = None
        permissions_seen = 0
        seen_pages = set()
        for _ in range(10):
            query = {"fields": "permissions(id,type,role,deleted),nextPageToken", "pageSize": 100}
            if page:
                query["pageToken"] = page
            result = self._api("/files/" + file_id + "/permissions", query=query)
            permissions = result.get("permissions")
            if not isinstance(permissions, list):
                raise DriveError("privacy_verification_failed")
            for permission in permissions:
                if not isinstance(permission, dict):
                    raise DriveError("privacy_verification_failed")
                if permission.get("deleted"):
                    continue
                if (permission.get("id") != self._permission_id or
                        permission.get("type") != "user" or
                        permission.get("role") != "owner"):
                    raise DriveError("drive_not_private")
                permissions_seen += 1
            page = result.get("nextPageToken")
            if not page:
                if permissions_seen != 1:
                    raise DriveError("privacy_verification_failed")
                return
            if not isinstance(page, str) or page in seen_pages:
                raise DriveError("privacy_verification_failed")
            seen_pages.add(page)
        raise DriveError("privacy_verification_failed")

    @staticmethod
    def _result(metadata: dict, *, folder=False) -> dict:
        file_id = _valid_id(metadata.get("id"))
        link = ("https://drive.google.com/drive/folders/" + file_id if folder else
                "https://drive.google.com/file/d/" + file_id + "/view")
        return {"id": file_id, "webViewLink": link}

    def verify_private_folder(self, folder_id: str) -> dict:
        metadata = self._metadata(folder_id)
        if (metadata.get("trashed") is not False or
                metadata.get("mimeType") != "application/vnd.google-apps.folder"):
            raise DriveError("invalid_report_folder")
        properties = metadata.get("appProperties")
        if not isinstance(properties, dict) or properties.get(FOLDER_MARKER) != "1":
            raise DriveError("folder_not_app_managed")
        self._private_owned(metadata)
        return self._result(metadata, folder=True)

    def _list(self, query: str) -> list[dict]:
        result = self._api("/files", query={
            "q": query, "spaces": "drive", "pageSize": 100,
            "fields": "files(id,name,mimeType,size,appProperties),nextPageToken",
        })
        files = result.get("files")
        if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
            raise DriveError("invalid_drive_response")
        # No truncated lookup may be treated as proof that an artifact is absent.
        if result.get("nextPageToken"):
            raise DriveError("drive_lookup_incomplete")
        return files

    def ensure_private_folder(self, name="PMI Research Reports", folder_id=None) -> dict:
        if folder_id is not None:
            return self.verify_private_folder(folder_id)
        if not isinstance(name, str) or not name or len(name) > 200:
            raise DriveError("invalid_folder_name")
        files = self._list(
            "trashed = false and mimeType = 'application/vnd.google-apps.folder' "
            "and appProperties has { key = '" + FOLDER_MARKER + "' and value = '1' }"
        )
        if len(files) > 1:
            raise DriveError("ambiguous_report_folder")
        if files:
            return self.verify_private_folder(_valid_id(files[0].get("id")))
        created = self._api("/files", method="POST", query={"fields": "id"}, body={
            "name": name, "mimeType": "application/vnd.google-apps.folder",
            "appProperties": {FOLDER_MARKER: "1"},
        })
        return self.verify_private_folder(_valid_id(created.get("id")))

    def upload(self, folder_id, name, mime_type, content: bytes, export_id, artifact_kind) -> dict:
        folder_id = _valid_id(folder_id)
        if (not isinstance(name, str) or not name or len(name) > 200 or
                not isinstance(mime_type, str) or not _MIME_TYPE.fullmatch(mime_type) or
                not isinstance(content, bytes)):
            raise DriveError("invalid_artifact")
        if len(content) > MAX_ARTIFACT_BYTES:
            raise DriveError("artifact_too_large")
        for value in (export_id, artifact_kind):
            if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 100:
                raise DriveError("invalid_artifact_identity")
        self.verify_private_folder(folder_id)
        files = self._list(
            "trashed = false and " + _q_value(folder_id) + " in parents "
            "and appProperties has { key = 'export_id' and value = " + _q_value(export_id) + " } "
            "and appProperties has { key = 'artifact_kind' and value = " + _q_value(artifact_kind) + " }"
        )
        if len(files) > 1:
            raise DriveError("ambiguous_artifact")
        if files:
            metadata = self._metadata(_valid_id(files[0].get("id")))
            try:
                same_size = int(metadata.get("size", -1)) == len(content)
            except (TypeError, ValueError):
                same_size = False
            if (metadata.get("trashed") is not False or metadata.get("name") != name or
                    metadata.get("mimeType") != mime_type or not same_size):
                raise DriveError("artifact_metadata_mismatch")
            self._private_owned(metadata)
            return self._result(metadata)
        metadata = {
            "name": name, "mimeType": mime_type, "parents": [folder_id],
            "appProperties": {"export_id": export_id, "artifact_kind": artifact_kind},
        }
        boundary = "pmi_" + uuid.uuid4().hex
        body = (
            ("--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n").encode("ascii")
            + json.dumps(metadata).encode("utf-8")
            + ("\r\n--" + boundary + "\r\nContent-Type: " + mime_type + "\r\n\r\n").encode("ascii")
            + content + ("\r\n--" + boundary + "--\r\n").encode("ascii")
        )
        request = urllib.request.Request(
            DRIVE_UPLOAD + "?uploadType=multipart&fields=id,webViewLink",
            data=body, method="POST", headers={
                "Authorization": "Bearer " + self._token(),
                "Content-Type": "multipart/related; boundary=" + boundary,
            },
        )
        return self._result(self._json(request))

    def download(self, file_id: str) -> bytes:
        file_id = _valid_id(file_id)
        metadata = self._metadata(file_id)
        if metadata.get("trashed") is not False:
            raise DriveError("artifact_unavailable")
        self._private_owned(metadata)
        request = urllib.request.Request(
            DRIVE_API + "/files/" + file_id + "?alt=media",
            headers={"Authorization": "Bearer " + self._token()},
        )
        return self._request(request, limit=MAX_ARTIFACT_BYTES)
