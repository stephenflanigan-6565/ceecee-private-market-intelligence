# Private PMI research reports in Google Drive

PMI runs the export inside the existing SeaLion application, using its existing
PostgreSQL connection. It sends a complete research JSON file and a readable
summary to a private folder in Stephen's Google Drive. Cece continues working
in the same review workspace. This integration does not need another server,
database, paid AI provider, or a separate credential for reading PostgreSQL.

The Google Drive authorization connected to ChatGPT is available to ChatGPT's
connector. It cannot be extracted and installed in the deployed PMI application.
The app needs its own one-time Google authorization, described below.

## One-time Google setup

Use the Google account that owns the intended reports. Do not send credentials,
authorization codes, or tokens through chat, GitHub, or a Drive document.

1. Open the [Google Cloud Console](https://console.cloud.google.com/). Select a
   project owned by that account, or create a small project for PMI's Drive
   integration. A project here is configuration for Google's API; it does not
   require deploying another application or buying another virtual machine.
2. Enable the [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com).
3. Configure **Google Auth Platform** with an application name such as **PMI
   research reports**, a support email, and the owner's contact email. For a
   personal Gmail account, use an **External** audience. Set its publishing
   status to **Production** before generating the final refresh token. Leaving
   an External app in **Testing** makes a Drive refresh token expire after
   seven days.
4. Under **Google Auth Platform → Clients**, create a **Web application** OAuth
   client. Add this exact authorized redirect URI:

   ```text
   https://developers.google.com/oauthplayground
   ```

   Save the client ID and client secret securely. Google may show the secret
   only when it is created. These values identify PMI's own integration.
5. Open [Google's OAuth Playground](https://developers.google.com/oauthplayground/).
   In its configuration panel, select **Use your own OAuth credentials** and
   enter the client ID and client secret from step 4. Keep **Server-side** flow,
   **Offline** access, and **Consent Screen** prompt.
6. In Step 1, enter only this scope and select **Authorize APIs**:

   ```text
   https://www.googleapis.com/auth/drive.file
   ```

   Sign in as the account that will own PMI's reports and approve that scope.
7. In Step 2, select **Exchange authorization code for tokens**. Retain the
   **refresh token**, together with the client ID and secret. The short-lived
   access token is not an application setting. Do not share a Playground URL
   containing credentials or tokens.

Using Playground's built-in OAuth credentials would cause its refresh token to
be revoked after 24 hours. **Use your own OAuth credentials** is essential for
the recurring integration. Changing a Testing app to Production does not make
an already-issued seven-day token reliable; authorize again after publishing.

Google documents a verification exemption for a small personal-use application
with fewer than 100 users. Production publishing and Google's brand/scope
verification are different controls. PMI requests the non-sensitive `drive.file`
scope; it does not request access to all of the owner's Drive files.

## Configure the existing DigitalOcean application

In the SeaLion application's environment-variable settings, add these values as
**encrypted runtime variables**. Configure them on the component running PMI,
or at app level if that is where its current runtime settings are managed.

| Variable | Value |
| --- | --- |
| `PMI_GOOGLE_DRIVE_CLIENT_ID` | The user-owned OAuth web client's ID |
| `PMI_GOOGLE_DRIVE_CLIENT_SECRET` | That client's secret |
| `PMI_GOOGLE_DRIVE_REFRESH_TOKEN` | The offline refresh token issued in step 7 |

Save the settings and allow the application to redeploy. Keep the existing
database and review-login configuration. These Google values are needed by the
running app and should not be limited to the build phase. The application keeps
tokens in protected environment configuration and memory, never in its database,
research export, summary, or status logs.

Missing credentials leave Drive export unavailable. They do not change Cece's
review data. Expired or revoked authorization produces a safe error code without
exposing Google's response body or any token.

## Folder access and ownership

On the first successful export, PMI itself creates **PMI Research Reports** in
the authorized user's My Drive. It marks the folder as belonging to this OAuth
application, then verifies that the same user owns it and that its permissions
contain only that owner. Subsequent exports reuse this folder. No public-link,
domain, group, or other-user permission is added.

The `drive.file` scope does not authorize arbitrary existing folders merely
because their IDs are known. A folder created by ChatGPT's separate connector
does not automatically become accessible to PMI's OAuth client. This version
uses its own app-created folder; it does not require Google Picker or broader
Drive scopes. Do not manually substitute another folder ID or add sharing to the
reports folder. The user's separately connected ChatGPT Drive account can read
the resulting reports as that Drive owner.

Do not use a service account shared into a personal My Drive folder. Google says
service accounts have no Drive storage quota and cannot own files. A personal
Gmail account cannot create an organizational shared drive. User OAuth is the
supported fit here.

## First export and daily activation

The first export is an end-to-end check, not proof supplied by unit tests. The
application reads a complete consistent research snapshot through its existing
PostgreSQL connection and publishes both artifacts. An export ID and artifact
kind make partial retries reuse their original files; the client never overwrites
or deletes an artifact. The export service must serialize exports with its
database lease to avoid simultaneous duplicate creation.

Before enabling the daily run, verify all of the following against the actual
production export:

- The authenticated Drive principal and private destination folder are verified.
- Both JSON and summary have Drive file IDs and view links.
- Downloaded bytes match the expected hashes, with complete downloads capped at
  32 MiB per file. Metadata responses are separately capped at 1 MiB.
- The JSON parses completely and its recorded counts match the original research
  snapshot. A reported count of 30 must come from saved data, not an assumption.
- The exported content includes the required research records, operator feedback,
  evidence, and memory, and its summary matches that same snapshot.
- The reports are readable through the owner's Google Drive connection.

The app unlocks the daily schedule automatically only after a successful actual
upload/readback verification. The next run is due 24 hours after that verification;
the existing worker checks whether it is due every two minutes. An incomplete upload, authentication error, private-folder failure,
hash mismatch, or truncated response must leave daily activation blocked and
preserve previous successful reports. Until the three Google runtime values are
configured and a production receipt is verified, an actual production end-to-end
export cannot be claimed.

The authenticated status endpoint is `/review/research-exports.json`. It reads
the existing delivery ledger and returns the last verified file links, source and
export counts, export time, next due time, and safe failure details. Opening this
endpoint does not start an export or change data. Public `/health` includes only
operational export status, never property records, Drive links, or credentials.

Files use UTC names such as `PMI-Research-2026-10-12-<revision12>.json` and the
matching `.md` summary. The source revision is the SHA-256 digest of saved research
content, not a claim about the deployed Git commit. Historical reports are never
overwritten or deleted. App credentials and operational delivery receipts are
excluded from the research snapshot.

The refresh token is reusable rather than guaranteed permanent. Google can
invalidate it if access is revoked, it remains unused for six months, a token
limit is exceeded, or applicable account policies change. Retain safe failure
status and require reauthorization when necessary.

## Official references

- [Google Drive scopes and secure refresh-token storage](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [OAuth web-server flow and credential setup](https://developers.google.com/identity/protocols/oauth2/web-server)
- [OAuth Playground and its 24-hour default-token rule](https://developers.google.com/oauthplayground/)
- [Google's refresh-token expiration rules](https://developers.google.com/identity/protocols/oauth2)
- [Personal-use verification exemption](https://support.google.com/cloud/answer/13464323)
- [Folder creation and upload parents](https://developers.google.com/workspace/drive/api/guides/folder)
- [Service-account ownership and shared-drive availability](https://developers.google.com/workspace/drive/api/guides/about-shareddrives)
