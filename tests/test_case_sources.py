import hashlib
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from pmi_case_sources import collect_case, _fetch_official_json, _NoRedirect, _valid_url, SourceError


PID = "0905002000200013000"
CASE = {"case_id": "case_real_shape", "parcel_id": PID, "property_address": "Fixture address"}
STAMP = "2026-10-10T01:00:00+00:00"
SPECS = {"TaxParcelPolygon": "parcel", "TaxParcelOwner": "owner",
         "TaxParcelTransferCurrent": "transfer_current", "TaxParcelTransferHistory": "transfer_history"}


class FixtureFetch:
    def __init__(self, records=None):
        self.records = records or {name: [{"OBJECTID": 1, "PARCELID": PID}] for name in SPECS}
        self.calls = []

    def __call__(self, url, *, timeout):
        self.calls.append((url, timeout))
        query = parse_qs(urlsplit(url).query)
        service = urlsplit(url).path.split("/")[-4]
        rows = self.records[service]
        if query.get("returnCountOnly") == ["true"]:
            return {"count": len(rows)}
        offset = int(query["resultOffset"][0])
        page = rows[offset:offset + 25]
        return {"features": [{"attributes": row} for row in page],
                "exceededTransferLimit": offset + 25 < len(rows)}


class CaseSourcesTests(unittest.TestCase):
    def run_collect(self, fetch=None, **kw):
        return collect_case(CASE, fetch_json=fetch or FixtureFetch(), observed_at=STAMP, **kw)

    def test_exact_parcel_queries_and_bounded_timeout(self):
        fetch = FixtureFetch()
        bundle = self.run_collect(fetch)
        self.assertEqual("SUCCESS", bundle["status"])
        self.assertEqual(12, len(fetch.calls))
        for url, timeout in fetch.calls:
            self.assertEqual("gis.suffolkcountyny.gov", urlsplit(url).hostname)
            self.assertEqual(["PARCELID = '%s'" % PID], parse_qs(urlsplit(url).query)["where"])
            self.assertLessEqual(timeout, 8)
        self.assertTrue(all(s["complete"] for s in bundle["sources"]))
        self.assertFalse(bundle["seller_intent_inferred"])

    def test_invalid_or_nonstring_parcels_never_fetch(self):
        for pid in (None, 905002000200013000, "090500200020001300", PID + "0", PID + "' OR 1=1", "9905002000200013000", " " + PID):
            fetch = FixtureFetch()
            result = collect_case(dict(CASE, parcel_id=pid), fetch_json=fetch)
            self.assertEqual("UNSUPPORTED", result["status"])
            self.assertEqual([], fetch.calls)

    def test_all_empty_complete_check_is_not_seller_disqualification(self):
        fetch = FixtureFetch({name: [] for name in SPECS})
        result = self.run_collect(fetch)
        self.assertEqual("SUCCESS", result["status"])
        self.assertTrue(all(s["status"] == "EMPTY" for s in result["sources"]))
        self.assertFalse(result["seller_intent_inferred"])

    def test_paging_and_hash_are_order_stable(self):
        rows = [{"OBJECTID": i, "PARCELID": PID} for i in range(31)]
        a = self.run_collect(FixtureFetch({name: rows for name in SPECS}))
        b = self.run_collect(FixtureFetch({name: list(reversed(rows)) for name in SPECS}))
        self.assertEqual("SUCCESS", a["status"])
        self.assertEqual(a["sources"][0]["content_hash"], b["sources"][0]["content_hash"])
        expected = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        self.assertEqual(expected, a["sources"][0]["content_hash"])

    def test_owner_content_change_same_objectid_detected(self):
        fetch = FixtureFetch()
        fetch.records["TaxParcelOwner"][0]["OWNERNAME"] = "First fixture entity"
        first = self.run_collect(fetch)
        prior = {s["source_key"]: s for s in first["sources"]}
        # Decouple snapshots from this mutable synthetic provider.
        prior = json.loads(json.dumps(prior))
        fetch.records["TaxParcelOwner"][0]["OWNERNAME"] = "Second fixture entity"
        second = self.run_collect(fetch, previous_sources=prior)
        owner = second["sources"][1]
        self.assertEqual(1, owner["change_summary"]["changed"])
        self.assertEqual("CHANGED", owner["change_summary"]["status"])
        self.assertEqual([{"object_id": 1, "fields": ["OWNERNAME"]}], owner["change_summary"]["changed_fields"])
        self.assertNotEqual(prior["owner"]["content_hash"], owner["content_hash"])

    def test_narratives_use_recorded_fields_without_inventing_motive(self):
        fetch = FixtureFetch()
        fetch.records["TaxParcelOwner"][0]["OWNERNAME"] = "Fixture Holding Company"
        fetch.records["TaxParcelPolygon"][0]["FULLADDRESS"] = "100 Example Street"
        fetch.records["TaxParcelTransferCurrent"][0]["RECORDDATE"] = 0
        findings = self.run_collect(fetch)["findings"]
        text = " ".join(findings)
        self.assertIn("county ownership source reports: Fixture Holding Company", text)
        self.assertIn("current authority to make a sale decision needs confirmation", text)
        self.assertIn("County parcel source address: 100 Example Street", text)
        self.assertIn("parcel ID matched exactly", text)
        self.assertIn("latest county recording date: 1970-01-01", text)
        self.assertIn("document type and parties require review", text)
        self.assertNotIn("motivated", text.lower())

    def test_owner_first_last_fallback_and_blank_name_keeps_investigation(self):
        fetch = FixtureFetch()
        fetch.records["TaxParcelOwner"][0].update(FIRSTNAME="Fixture", LASTNAME="Person")
        self.assertIn("reports: Fixture Person", " ".join(self.run_collect(fetch)["findings"]))
        fetch.records["TaxParcelOwner"][0].update(FIRSTNAME=None, LASTNAME="")
        result = self.run_collect(fetch)
        self.assertEqual("SUCCESS", result["status"])
        self.assertIn("property remains available for investigation", " ".join(result["findings"]))

    def test_hashes_and_change_state_ignore_observation_timestamp(self):
        fetch = FixtureFetch()
        first = self.run_collect(fetch)
        prior = {s["source_key"]: s for s in first["sources"]}
        second = collect_case(CASE, prior, fetch_json=fetch, observed_at="2026-10-11T02:00:00+00:00")
        for old, new in zip(first["sources"], second["sources"]):
            self.assertNotEqual(old["observed_at"], new["observed_at"])
            self.assertEqual(old["content_hash"], new["content_hash"])
            self.assertEqual("UNCHANGED", new["change_summary"]["status"])

    def test_narrative_and_changed_fields_are_bounded(self):
        fetch = FixtureFetch()
        fetch.records["TaxParcelOwner"] = [
            {"OBJECTID": i, "PARCELID": PID, "OWNERNAME": "Fixture %s " % i + "x" * 1000}
            for i in range(15)]
        first = self.run_collect(fetch)
        prior = json.loads(json.dumps({s["source_key"]: s for s in first["sources"]}))
        for row in fetch.records["TaxParcelOwner"]:
            row["OWNERNAME"] = "Corrected " + row["OWNERNAME"]
        second = self.run_collect(fetch, previous_sources=prior)
        owner = second["sources"][1]
        self.assertEqual(15, owner["change_summary"]["changed"])
        self.assertEqual(10, len(owner["change_summary"]["changed_fields"]))
        self.assertTrue(owner["change_summary"]["changed_fields_truncated"])
        narration = next(line for line in second["findings"] if "ownership source reports" in line)
        self.assertLess(len(narration), 900)

    def test_add_remove_only_from_complete_sources(self):
        first = self.run_collect()
        previous = {s["source_key"]: s for s in first["sources"]}
        rows = {name: [] for name in SPECS}
        result = self.run_collect(FixtureFetch(rows), previous_sources=previous)
        self.assertTrue(all(s["change_summary"]["removed"] == 1 for s in result["sources"]))

    def test_partial_failures_retain_prior_pointer_metadata(self):
        previous = {s["source_key"]: s for s in self.run_collect()["sources"]}
        fetch = FixtureFetch()
        def failed(url, *, timeout):
            if "TaxParcelOwner/" in url:
                raise TimeoutError("private upstream body must not appear")
            return fetch(url, timeout=timeout)
        result = self.run_collect(failed, previous_sources=previous)
        self.assertEqual("PARTIAL", result["status"])
        owner = result["sources"][1]
        self.assertFalse(owner["complete"])
        self.assertEqual(previous["owner"]["content_hash"], owner["previous_successful_content_hash"])
        self.assertIsNone(owner["change_summary"]["removed"])
        self.assertNotIn("private upstream body", str(result))

    def test_duplicate_ids_are_incomplete(self):
        fetch = FixtureFetch()
        fetch.records["TaxParcelOwner"] *= 2
        result = self.run_collect(fetch)
        self.assertEqual("INCOMPLETE", result["sources"][1]["status"])
        self.assertIsNone(result["sources"][1]["content_hash"])

    def test_mismatched_parcel_rejected_source_not_accepted(self):
        fetch = FixtureFetch()
        fetch.records["TaxParcelOwner"][0]["PARCELID"] = "0905002000200018000"
        result = self.run_collect(fetch)
        self.assertEqual("ERROR", result["sources"][1]["status"])
        self.assertFalse(result["sources"][1]["complete"])

    def test_record_cap_stops_before_page_fetch(self):
        fetch = FixtureFetch({name: [{"OBJECTID": n, "PARCELID": PID} for n in range(101)] for name in SPECS})
        result = self.run_collect(fetch)
        self.assertEqual(4, len(fetch.calls))
        self.assertTrue(all(s["status"] == "INCOMPLETE" for s in result["sources"]))

    def test_missing_page_and_truncation_are_incomplete(self):
        fetch = FixtureFetch()
        def empty_page(url, *, timeout):
            data = fetch(url, timeout=timeout)
            if "features" in data:
                data["features"] = []
            return data
        result = self.run_collect(empty_page)
        self.assertTrue(all(s["status"] == "INCOMPLETE" for s in result["sources"]))
        def truncated(url, *, timeout):
            data = fetch(url, timeout=timeout)
            if "features" in data:
                data["exceededTransferLimit"] = True
            return data
        result = self.run_collect(truncated)
        self.assertTrue(all(s["status"] == "INCOMPLETE" for s in result["sources"]))

    def test_count_change_is_incomplete(self):
        fetch = FixtureFetch()
        counts = {}
        def changed(url, *, timeout):
            result = fetch(url, timeout=timeout)
            if "count" in result:
                counts[url] = counts.get(url, 0) + 1
                if counts[url] == 2:
                    result["count"] += 1
            return result
        bundle = self.run_collect(changed)
        self.assertTrue(all(s["status"] == "INCOMPLETE" for s in bundle["sources"]))

    def test_upstream_error_does_not_expose_private_payload(self):
        result = self.run_collect(lambda url, **kwargs: {"error": {"details": "Private row data"}})
        self.assertEqual("ERROR", result["status"])
        self.assertNotIn("Private row data", str(result))

    def test_deadline_stops_without_starting_more_requests(self):
        fetch = FixtureFetch()
        with patch("pmi_case_sources.CASE_DEADLINE_SECONDS", 0):
            result = self.run_collect(fetch)
        self.assertEqual("ERROR", result["status"])
        self.assertEqual([], fetch.calls)

    def test_payload_cap_checks_injected_provider_too(self):
        result = self.run_collect(lambda url, **kwargs: {"count": 1, "oversized": "x" * (512 * 1024)})
        self.assertEqual("ERROR", result["status"])
        self.assertTrue(all("size limit" in s["error"] for s in result["sources"]))

    def test_dates_distinguish_recording_and_sale(self):
        fetch = FixtureFetch()
        fetch.records["TaxParcelTransferCurrent"][0].update(RECORDDATE=0, SALEDATE=86400000)
        source = self.run_collect(fetch)["sources"][2]
        self.assertEqual(["1970-01-01", "1970-01-02"], [d["value"] for d in source["recorded_dates"]])
        self.assertIn("county recording", source["recorded_dates"][0]["meaning"])
        self.assertIn("not present seller intent", source["recorded_dates"][1]["meaning"])

    def test_unsafe_urls_and_all_redirects_are_refused(self):
        for url in ("http://gis.suffolkcountyny.gov/", "https://evil.example/", "https://gis.suffolkcountyny.gov:8443/", "https://gis.suffolkcountyny.gov/server/rest/services/LocalGovernmentSQLData/TaxParcelOwner/FeatureServer/0/query?where=1%3D1"):
            self.assertFalse(_valid_url(url))
            with self.assertRaises(SourceError):
                _fetch_official_json(url)
        with self.assertRaises(SourceError):
            _NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example/")

    def test_timezone_required_and_Z_accepted(self):
        with self.assertRaises(ValueError):
            collect_case(CASE, fetch_json=FixtureFetch(), observed_at="2026-10-10T01:00:00")
        result = collect_case(CASE, fetch_json=FixtureFetch(), observed_at="2026-10-10T01:00:00Z")
        self.assertEqual(STAMP, result["observed_at"])


if __name__ == "__main__":
    unittest.main()
