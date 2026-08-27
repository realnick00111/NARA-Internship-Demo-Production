"""Input snapshot export and import round trips."""

import io
import json
from app import app
from tests.test_support import AssessmentTestCase


class SnapshotImportExportTests(AssessmentTestCase):
    """Input snapshot export and import round trips."""

    def test_download_input_snapshot_excludes_calculation_result(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET contact_hours = ?, pqi_findings = ?, calculated_result = ? WHERE id = ?",
            (json.dumps({"calculated_ch": "8"}), json.dumps({"pqi1": {"score": 2}}), json.dumps({"score": 9}), assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.get("/assessments/input-snapshot")
        snapshot = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=assessment-input-snapshot-", response.headers["Content-Disposition"])
        self.assertNotIn("calculated_result", snapshot["assessment"])
        self.assertEqual(snapshot["assessment"]["contact_hours"], {"calculated_ch": "8"})
        self.assertEqual(snapshot["facility"]["identifier"], "FAC-008742")


    def test_download_input_snapshots_returns_an_array_for_the_assessment_list(self):
        first_id = self.insert_assessment(assessment_name="First assessment")
        second_id = self.insert_assessment(assessment_name="Second assessment")

        response = self.client.get("/assessments/input-snapshots")
        snapshots = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=assessment-input-snapshots.json", response.headers["Content-Disposition"])
        self.assertIsInstance(snapshots, list)
        self.assertEqual([snapshot["assessment"]["assessment_name"] for snapshot in snapshots], [
            "First assessment",
            "Second assessment",
        ])
        self.assertEqual(len({first_id, second_id}), 2)


    def test_import_input_snapshot_accepts_multiple_assessments(self):
        first_id = self.insert_assessment(assessment_name="First assessment")
        with self.client.session_transaction() as session:
            session["current_assessment_id"] = first_id
        first_snapshot = self.client.get(f"/assessments/input-snapshot").get_json()
        self.conn.execute("UPDATE assessments SET assessment_name = ? WHERE id = ?", ("Second assessment", first_id))
        self.conn.commit()
        second_snapshot = self.client.get("/assessments/input-snapshot").get_json()
        self.conn.execute("DELETE FROM assessments")
        self.conn.commit()

        response = self.client.post(
            "/api/assessments/import-input-snapshot",
            data={"snapshot": (io.BytesIO(json.dumps([first_snapshot, second_snapshot]).encode("utf-8")), "snapshots.json")},
            content_type="multipart/form-data",
        )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["imported_count"], 2)
        self.assertEqual(len(payload["assessment_ids"]), 2)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0], 2)


    def test_imported_snapshot_round_trips_input_and_ignores_calculation_result(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE facilities SET name = ? WHERE id = (SELECT facility_id FROM assessments WHERE id = ?)",
            ("Sunrise Learning Center Facility", assessment_id),
        )
        self.conn.execute(
            "UPDATE assessments SET contact_hours = ?, pqi_findings = ?, calculated_result = ? WHERE id = ?",
            (json.dumps({"calculated_ch": "8"}), json.dumps({"pqi1": {"score": 2}}), json.dumps({"score": 9}), assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        exported_snapshot = self.client.get("/assessments/input-snapshot").get_json()
        exported_snapshot["assessment"]["calculated_result"] = {"score": 999}
        response = self.client.post(
            "/api/assessments/import-input-snapshot",
            data={"snapshot": (io.BytesIO(json.dumps(exported_snapshot).encode("utf-8")), "snapshot.json")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        imported_id = response.get_json()["assessment_id"]
        imported_row = self.conn.execute(
            "SELECT a.*, f.* FROM assessments a JOIN facilities f ON f.id = a.facility_id WHERE a.id = ?",
            (imported_id,),
        ).fetchone()
        self.assertEqual(imported_row["assessment_name"], "Sunrise Learning Center - Annual 2026 test")
        self.assertEqual(imported_row["name"], "Sunrise Learning Center Facility")
        self.assertEqual(imported_row["facility_identifier"], "FAC-008742")
        self.assertEqual(imported_row["contact_hours"], json.dumps({"calculated_ch": "8"}))
        self.assertEqual(imported_row["pqi_findings"], json.dumps({"pqi1": {"score": 2}}))
        self.assertEqual(json.loads(imported_row["calculated_result"]), {})


    def test_import_accepts_optional_assessment_fields(self):
        assessment_id = self.insert_assessment()
        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        snapshot = self.client.get("/assessments/input-snapshot").get_json()
        for field_name in ("assessment_name", "assessment_date", "visit_date", "inspection_type"):
            snapshot["assessment"].pop(field_name)
        snapshot["facility"].pop("program_type")

        response = self.client.post(
            "/api/assessments/import-input-snapshot",
            data={"snapshot": (io.BytesIO(json.dumps(snapshot).encode("utf-8")), "snapshot.json")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)



