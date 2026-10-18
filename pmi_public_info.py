"""Public OAuth information only: no database, credentials, or research reads."""
from flask import Blueprint, Response

bp = Blueprint("pmi_public_info", __name__)
STYLE = """body{font-family:system-ui,sans-serif;max-width:760px;margin:3rem auto;padding:0 1.25rem;line-height:1.65;color:#18302e;background:#fafbf9}h1,h2{line-height:1.25}a{color:#145e58}nav{margin-bottom:2rem}footer{border-top:1px solid #ccd8d4;margin-top:2rem;padding-top:1rem}"""
HOME = """<h1>PMI research reports</h1>
<p>Private Market Intelligence (PMI) is a private property-research workspace.
It helps its operator review property information, notes, evidence and assessment
history. Research assessments support human review; they are not guarantees of
a listing opportunity.</p>
<h2>Google Drive backup integration</h2>
<p>The optional integration saves complete research backups and readable summaries
to a private <strong>PMI Research Reports</strong> folder in the authorizing
account's Google Drive. It requests access only to files the app creates or that
you explicitly make available to it, using Google's <code>drive.file</code> scope.
The exporter uses its own app-created folder; it does not request access to all
your Drive files.</p>
<p>Backups are not operational until authorization, configuration and an actual
upload/readback verification succeed.</p>
<p><a href="/privacy">Read the privacy policy</a> or
<a href="/review/">open the authenticated research workspace</a>.</p>"""
PRIVACY = """<h1>Privacy policy</h1>
<p>This policy describes the PMI research reports Google Drive integration and
the Private Market Intelligence research workspace.</p>
<h2>Information handled</h2>
<p>The workspace stores property research and its history, including original
versions, operator notes, supporting evidence, reviews, findings, assessments and
research activity. These records may include property addresses, ownership
information and personal information an operator includes in research.</p>
<h2>Purpose and Google access</h2>
<p>PMI uses these records to support property research, reassessment and retained
history. With the account owner's authorization, the exporter sends a complete
research JSON backup and a readable summary to Google Drive. It uses
<code>https://www.googleapis.com/auth/drive.file</code>, which permits access to
files created by the app or explicitly made available to it. It does not request
blanket access to your Drive. It checks the authorized Drive account and folder
ownership and permissions, and reads back its uploaded files to verify them.</p>
<h2>Storage and access</h2>
<p>The app and its research database are hosted on DigitalOcean. Authorized
backups are stored in the owner's Google Drive. The exporter requires the backup
folder and files to have owner-only permissions and does not add public links or
other recipients. Google and DigitalOcean process information as providers of
these services under their own terms and policies. Authorized workspace users
can access research through the app.</p>
<p>OAuth credentials and refresh tokens are held in protected runtime
configuration and process memory. The exporter excludes them from research
backups and reports. Public information pages do not display research records.
The workspace uses cookies for sign-in and request protection.</p>
<h2>Use restrictions</h2>
<p>The Drive integration uses Google account and file information for backup
delivery, ownership checks and verification. It does not use that information for
advertising, sell it, or use it to train generalized AI models.</p>
<h2>Retention, revocation and deletion</h2>
<p>Research history and backup files are retained; this exporter does not
automatically expire, overwrite or delete historical backups. You can revoke
PMI's access in your Google Account's third-party connections settings. Revocation
stops future authorized Drive access but does not delete existing Drive files or
the research database. The Drive owner can manage and delete backups in Drive.
Contact the operator about access to, correction of, or deletion of retained
research. Deleting a Drive backup alone does not delete the app's records.</p>
<h2>Contact and changes</h2>
<p>For privacy questions or requests, contact
<a href="mailto:4xpipaddict@gmail.com">4xpipaddict@gmail.com</a>.
This page will reflect changes to the integration's handling of information.</p>"""

def page(title, body):
    response = Response(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title><style>{STYLE}</style></head><body>'
        '<nav><a href="/about">PMI research reports</a> · '
        '<a href="/privacy">Privacy</a></nav>'
        + body + '<footer>Private Market Intelligence · PMI research reports</footer>'
        '</body></html>', mimetype="text/html")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'")
    return response

@bp.get("/about")
def about():
    return page("PMI research reports", HOME)

@bp.get("/privacy")
def privacy():
    return page("Privacy policy | PMI research reports", PRIVACY)
