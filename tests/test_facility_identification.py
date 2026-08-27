import io
import json
import unittest
from unittest.mock import patch

from app import app, get_db_connection, save_assignment_draft, set_current_assessment
from constants import INCLUDED_COMPONENTS, REGULATION_SET_NAME, REGULATION_SET_VERSION
from services.formatters import round_percentage_half_up


class FacilityIdentificationTests(unittest.TestCase):
    def setUp(self):
        self.conn = get_db_connection()
        self.conn.execute("DELETE FROM assessments")
        self.conn.execute("DELETE FROM facilities")
        self.conn.commit()
        self.client = app.test_client()

    def tearDown(self):
        self.conn.execute("DELETE FROM assessments")
        self.conn.execute("DELETE FROM facilities")
        self.conn.commit()
        self.conn.close()

    def insert_assessment(
        self,
        assessment_name: str = "Sunrise Learning Center - Annual 2026 test",
        assessment_date: str = "2026-07-17",
        visit_date: str = "2026-07-14",
    ) -> int:
        facility_id = self.conn.execute(
            """
            INSERT INTO facilities (
                identifier,
                name,
                license_number,
                physical_address,
                city_state_postal_code,
                type,
                provider_name,
                provider_id,
                region,
                program_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "FAC-008742",
                assessment_name,
                "LIC-CC-21884",
                "1250 Cedar Avenue",
                "Olympia, WA 98501",
                "Mixed Age Center",
                "Sunrise Learning LLC",
                "PRV-004198",
                "Region 3 - South Sound",
                "Child Care Center",
            ),
        ).lastrowid

        assessment_id = self.conn.execute(
            """
            INSERT INTO assessments (
                assessment_name,
                facility_id,
                facility_identifier,
                external_system,
                assessment_date,
                visit_date,
                inspection_type,
                assessor,
                status,
                external_case_number,
                external_inspection_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_name,
                facility_id,
                "FAC-008742",
                "Compass",
                assessment_date,
                visit_date,
                "Annual Monitoring Visit",
                "Ada Lovelace",
                "draft",
                "CMP-2026-00418211111",
                "INS-2026-0714-22",
            ),
        ).lastrowid
        self.conn.commit()
        return assessment_id

    def test_facility_screen_uses_default_inspector_name(self):
        response = self.client.get("/screens/facility-identification")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="Jordan Davis"', rendered)

    def test_facility_screen_uses_date_input_and_database_values(self):
        assessment_id = self.insert_assessment(
            assessment_name="Sunrise Learning Center",
            assessment_date="2026-04-10",
            visit_date="2026-04-12",
        )

        with app.test_request_context("/"):
            set_current_assessment(assessment_id)
            html = app.jinja_env.from_string("{{ content }}")
            rendered = app.view_functions["screen"]("facility-identification")

        self.assertIn('type="date"', rendered)
        self.assertIn('<select class="select" id="facility-type" name="facility_type">', rendered)
        self.assertIn('<option value="Mixed Age" selected>Mixed Age</option>', rendered)
        self.assertIn('<option value="Preschool">Preschool</option>', rendered)
        self.assertIn('<option value="Infant-Toddler">Infant-Toddler</option>', rendered)
        self.assertIn('value="2026-04-12"', rendered)
        self.assertIn('Ada Lovelace', rendered)
        self.assertIn('Sunrise Learning Center', rendered)

    def test_duplicate_warning_ignores_empty_matching_fields(self):
        first_id = self.insert_assessment()
        second_id = self.insert_assessment()
        self.conn.execute(
            """
            UPDATE assessments
            SET assessment_name = '', assessment_date = '', visit_date = '',
                external_case_number = 'None', external_inspection_id = 'None'
            WHERE id IN (?, ?)
            """,
            (first_id, second_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = first_id

        rendered = self.client.get("/screens/facility-identification").data.decode("utf-8")

        self.assertNotIn("possible duplicate", rendered.lower())

        self.conn.execute(
            "UPDATE assessments SET external_case_number = ? WHERE id IN (?, ?)",
            ("CASE-123", first_id, second_id),
        )
        self.conn.commit()

        rendered = self.client.get("/screens/facility-identification").data.decode("utf-8")

        self.assertIn("same external case number", rendered)

        review_link = f'href="/assessments/{second_id}/create-assessment"'
        self.assertIn(review_link, rendered)

    def test_new_assessment_uses_facility_type_dropdown(self):
        response = self.client.get("/screens/new-assessment")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<div class="eyebrow">Create assessment</div>', rendered)

        assessment_id = self.insert_assessment()
        with app.test_request_context("/"):
            set_current_assessment(assessment_id)
            rendered = app.view_functions["screen"]("new-assessment")

        self.assertIn('<div class="eyebrow">Assessment ASMT-', rendered)
        self.assertNotIn('<div class="eyebrow">Create assessment</div>', rendered)
        self.assertIn('<select class="select" id="facility-type" name="facility_type">', rendered)
        self.assertIn('<option value="Mixed Age" selected>Mixed Age</option>', rendered)
        self.assertIn('<option value="Preschool">Preschool</option>', rendered)
        self.assertIn('<option value="Infant-Toddler">Infant-Toddler</option>', rendered)

    def test_opening_an_existing_assessment_redirects_to_progress(self):
        assessment_id = self.insert_assessment()

        response = self.client.get(f"/assessments/{assessment_id}/create-assessment", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/screens/assessment-progress", response.headers["Location"])

    def test_assessment_progress_uses_current_assessment_data_and_links(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.get("/screens/assessment-progress")
        rendered = response.data.decode("utf-8")

        self.assertIn("Assessment Progress", rendered)
        self.assertIn("Sunrise Learning Center - Annual 2026 test", rendered)
        self.assertIn("CMP-2026-00418211111", rendered)
        self.assertIn('href="/screens/ch-structural-entry"', rendered)
        self.assertIn('href="/screens/validation-summary"', rendered)
        self.assertEqual(rendered.count('class="issue-row danger"'), 3)
        self.assertNotIn("Validation summary has not been reviewed", rendered)
        self.assertIn('href="/screens/audit-history"', rendered)

    def test_pqi_entry_has_continue_to_validation_button(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")

        self.assertIn(">Continue to Validation</a>", rendered)
        self.assertIn('href="/screens/validation-summary">Continue to Validation</a>', rendered)

    def test_calculation_review_matches_prototype_structure(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE facilities SET type = ? WHERE id = (SELECT facility_id FROM assessments WHERE id = ?)",
            ("Preschool", assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.get("/screens/calculation-review")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Calculation Review", rendered)
        self.assertIn("Frozen calculation assets", rendered)
        self.assertIn("Calculation readiness", rendered)
        self.assertIn("Create a reproducible result", rendered)
        self.assertIn(f"{REGULATION_SET_NAME} {REGULATION_SET_VERSION}", rendered)
        self.assertIn(f"Assessment ASMT-{assessment_id:05d}", rendered)
        self.assertIn("<small>Preschool bands</small>", rendered)
        self.assertNotIn("No assessment selected", rendered)
        self.assertIn("Not ready to calculate", rendered)

    def test_calculation_review_without_selection_is_not_ready(self):
        rendered = self.client.get("/screens/calculation-review").data.decode("utf-8")

        self.assertIn("readiness-score warning", rendered)
        self.assertIn("No assessment selected", rendered)
        self.assertNotIn("Ready to calculate", rendered)
        self.assertIn('disabled aria-disabled="true"', rendered)

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

    def test_calculation_review_component_statuses_follow_included_components(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        original_components = dict(INCLUDED_COMPONENTS)
        INCLUDED_COMPONENTS.update(
            {
                "CONTACT_HOURS": False,
                "ATTACHMENTS_AND_NARRATIVE_NOTES": True,
            }
        )
        try:
            rendered = self.client.get("/screens/calculation-review").data.decode("utf-8")
        finally:
            INCLUDED_COMPONENTS.clear()
            INCLUDED_COMPONENTS.update(original_components)

        self.assertIn(
            'Contact Hour Structural Quality</td><td><span class="chip neutral">Excluded</span>',
            rendered,
        )
        self.assertIn(
            'Attachments and narrative notes</td><td><span class="chip success">Included</span>',
            rendered,
        )

    def test_calculation_review_sums_pqi_scores_and_hides_blocking_groups(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (
                json.dumps({
                    "pqi1": {"score": 1},
                    "pqi2": {"score": 2},
                    "pqi3": {"score": 3},
                    "pqi4": {"score": 4},
                    "pqi5": {"score": 4},
                    "pqi6": {"score": 2},
                    "pqi7": {"score": 3},
                    "pqi8": {"score": 4},
                    "pqi9": {"score": 1},
                    "pqi10": {"score": 2},
                }),
                assessment_id,
            ),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        ready_validation = {"blocking_errors": [], "warnings": []}
        with patch("services.screen_contexts.build_validation_context", return_value=ready_validation):
            rendered = self.client.get("/screens/calculation-review").data.decode("utf-8")

        self.assertIn("PQI 1-5</td><td><span class=\"chip success\">Included</span></td><td>Applicable and complete</td><td>14 points", rendered)
        self.assertIn("PQI 6-8</td><td><span class=\"chip success\">Included</span></td><td>All hierarchical indicators applicable</td><td>9 points", rendered)
        self.assertIn("PQI 9-10</td><td><span class=\"chip success\">Included</span></td><td>All timed observations complete</td><td>3 points", rendered)

        blocked_validation = {
            "blocking_errors": [
                {"kind": "pqi", "title": "PQI 3 is incomplete"},
                {"kind": "pqi", "title": "PQI 9 is incomplete"},
            ],
            "warnings": [],
        }
        with patch("services.screen_contexts.build_validation_context", return_value=blocked_validation):
            rendered = self.client.get("/screens/calculation-review").data.decode("utf-8")

        self.assertIn("PQI 1-5</td><td><span class=\"chip danger\">Blocking</span></td><td>One or more applicable indicators are incomplete</td><td>--", rendered)
        self.assertIn("PQI 6-8</td><td><span class=\"chip success\">Included</span></td><td>All hierarchical indicators applicable</td><td>9 points", rendered)
        self.assertIn("PQI 9-10</td><td><span class=\"chip danger\">Blocking</span></td><td>One or more timed observations are incomplete</td><td>--", rendered)

    def test_assessment_label_uses_current_selection_or_placeholder(self):
        response = self.client.get("/screens/facility-identification")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<div class="eyebrow">No assessment selected</div>', rendered)

        assessment_id = self.insert_assessment()
        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.get("/screens/facility-identification")
        rendered = response.data.decode("utf-8")

        self.assertIn('<div class="eyebrow">Assessment ASMT-', rendered)
        self.assertNotIn('<div class="eyebrow">No assessment selected</div>', rendered)

    def test_pqi9_screen_uses_current_assessment_label(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.get("/screens/pqi9-10-timed")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<div class="eyebrow">Assessment ASMT-', rendered)
        self.assertNotIn('Assessment DM-2026-00184', rendered)

    def test_pqi9_average_preview_calculates_from_selected_scores(self):
        response = self.client.get("/screens/pqi9-10-timed")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="pqi910-average-preview"', rendered)
        self.assertIn('id="pqi910-provisional-score"', rendered)
        self.assertIn('const averagePreview = document.getElementById(\'pqi910-average-preview\');', rendered)
        self.assertIn('const provisionalScore = document.getElementById(\'pqi910-provisional-score\');', rendered)
        self.assertIn('selectedScores.reduce', rendered)

    def test_save_pqi9_persists_nested_json_and_complete_flag(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi9",
            json={
                "complete": True,
                "responses": {
                    "1": 4,
                    "2": 3,
                    "3": 2,
                    "4": 4,
                    "5": 3,
                    "6": 2,
                    "7": 4,
                    "8": 3,
                    "9": 2,
                    "10": 3,
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        self.assertIsNotNone(saved_row)
        saved_findings = json.loads(saved_row[0])
        self.assertTrue(saved_findings["pqi9"]["complete"])
        self.assertEqual(saved_findings["pqi9"]["responses"]["1"], 4)
        self.assertEqual(saved_findings["pqi9"]["responses"]["10"], 3)
        self.assertEqual(saved_findings["pqi9"]["score"], 3)

    def test_save_pqi10_persists_independently_from_pqi9(self):
        assessment_id = self.insert_assessment()
        responses = {str(index): (index % 4) + 1 for index in range(1, 11)}

        response = self.client.post(
            "/api/assessments/pqi10",
            json={"assessment_id": assessment_id, "complete": True, "responses": responses},
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertTrue(saved_findings["pqi10"]["complete"])
        self.assertEqual(saved_findings["pqi10"]["responses"]["1"], 2)
        self.assertEqual(saved_findings["pqi10"]["responses"]["10"], 3)
        self.assertNotIn("pqi9", saved_findings)

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi9-10-timed").get_data(as_text=True)
        self.assertIn('data-pqi910-tab="pqi10"', rendered)
        self.assertIn('const saveUrl = "/api/assessments/pqi10";', rendered)
        self.assertIn('const initialSavedScores = {', rendered)
        self.assertIn('id="pqi10-complete-card"', rendered)

    def test_save_pqi9_persists_and_reloads_trial_notes(self):
        assessment_id = self.insert_assessment()
        responses = {str(index): (index % 4) + 1 for index in range(1, 11)}
        notes = {str(index): f"Trial note {index}" for index in range(1, 11)}

        response = self.client.post(
            "/api/assessments/pqi9",
            json={"assessment_id": assessment_id, "responses": responses, "notes": notes},
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi9"]["notes"]["1"], "Trial note 1")
        self.assertEqual(saved_findings["pqi9"]["notes"]["10"], "Trial note 10")

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi9-10-timed").get_data(as_text=True)
        self.assertIn('const initialSavedNotes = {', rendered)
        self.assertIn('"1": "Trial note 1"', rendered)
        self.assertIn('"10": "Trial note 10"', rendered)
        self.assertIn('class="input pqi910-notes"', rendered)

    def test_pqi9_screen_loads_saved_scores_from_db(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (
                json.dumps({
                    "pqi9": {
                        "complete": True,
                        "score": 3,
                        "responses": {"1": 4, "2": 3, "3": 2, "4": 4, "5": 3, "6": 2, "7": 4, "8": 3, "9": 2, "10": 3},
                    },
                }),
                assessment_id,
            ),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.get("/screens/pqi9-10-timed")
        rendered = response.data.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn('const initialSavedScores = {', rendered)
        self.assertIn('"1": 4', rendered)
        self.assertIn('"10": 3', rendered)

    def test_pqi9_completion_banner_shows_when_complete(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (
                json.dumps({
                    "pqi9": {
                        "complete": True,
                        "score": 3,
                        "responses": {"1": 4, "2": 3, "3": 2, "4": 4, "5": 3, "6": 2, "7": 4, "8": 3, "9": 2, "10": 3},
                    },
                }),
                assessment_id,
            ),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.get("/screens/pqi9-10-timed")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="pqi910-complete-card"', rendered)
        self.assertIn('PQI 9 marked as complete', rendered)
        self.assertFalse('Trials Completed' in rendered, 'completed page should not show the trials summary')

    def test_pqi3_screen_uses_single_current_layout(self):
        response = self.client.get("/screens/pqi3-sample")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rendered.count("Ten-record Curriculum &amp; Assessment sample"), 1)
        self.assertNotIn("Sample size", rendered)
        self.assertNotIn("Review the sampled items used to compute the section three result and verify the evidence count.", rendered)

    def test_pqi1_screen_renders_calculation_controls(self):
        response = self.client.get("/screens/pqi1")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("PQI 1", rendered)
        self.assertIn("Number of ECE III Educators", rendered)
        self.assertIn('id="ece-iii-certified-count"', rendered)
        self.assertIn('id="total-teaching-staff-count"', rendered)
        self.assertIn('More ECE III-certified teaching staff than total staff.', rendered)
        self.assertIn('id="pqi1-draft-save-button"', rendered)
        self.assertIn('Save Draft', rendered)
        self.assertIn('id="pqi1-save-button"', rendered)
        self.assertIn("const hasAnyInput = certifiedInput.value !== '' || totalInput.value !== '';", rendered)
        self.assertIn('disabled', rendered)

    def test_pqi_progress_requires_saved_state(self):
        response = self.client.get("/api/assessments/pqi-progress")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["assessment_id"])

        findings_response = self.client.get("/screens/pqi-findings-entry")
        findings_rendered = findings_response.data.decode("utf-8")
        self.assertNotIn("findingsEntry?.addEventListener('input', syncPqiProgress)", findings_rendered)

    def test_pqi_findings_entry_embeds_pqi1_controls(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.get("/screens/pqi-findings-entry")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="pqi1-card"', rendered)
        self.assertIn('href="#pqi-1"', rendered)
        self.assertIn('id="pqi1-draft-save-button"', rendered)
        self.assertIn('id="pqi1-save-button"', rendered)
        self.assertIn('href="#pqi-2"', rendered)
        self.assertIn('id="pqi2-draft-save-button"', rendered)
        self.assertIn('id="pqi2-save-button"', rendered)
        self.assertIn('Co-teaching is evident.', rendered)
        self.assertIn('Unawnsered', rendered)
        self.assertIn('href="#pqi-5"', rendered)
        self.assertIn('id="pqi5-draft-save-button"', rendered)
        self.assertIn('id="pqi5-save-button"', rendered)
        self.assertIn('qualifying conferences with families at least twice yearly.', rendered)

    def test_pqi_findings_entry_progress_counts_input_units(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")

        self.assertIn("0 of 52 complete", rendered)
        self.assertIn('<span id="pqi-progress-percentage">0%</span>', rendered)
        self.assertIn('style="width:0%"', rendered)

    def test_pqi_findings_entry_progress_sums_fields_records_and_completions(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (
                json.dumps({
                    "pqi1": {"certified_teaching_staff": 1, "total_teaching_staff": 2},
                    "pqi2": {"responses": {"2.1": "yes", "2.2": "no"}},
                    "pqi3": {"records": {"record 1": {"emergent_curriculum": "yes", "co_learning": "yes", "documented_learning_future_planning": "yes"}}},
                    "pqi4": {"responses": {"4.1": "yes"}},
                    "pqi5": {"responses": {"5.1": "yes"}},
                    "pqi6": {"complete": True},
                    "pqi8": {"complete": True},
                    "pqi9": {"responses": {"1": 1, "2": 2}},
                    "pqi10": {"responses": {"1": 3}},
                }),
                assessment_id,
            ),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")

        self.assertIn("12 of 52 complete", rendered)
        self.assertIn('<span id="pqi-progress-percentage">23%</span>', rendered)

    def test_pqi_findings_entry_progress_excludes_deactivated_pqi(self):
        assessment_id = self.insert_assessment()
        self.conn.execute("UPDATE facilities SET type = ? WHERE identifier = ?", ("Preschool", "FAC-008742"))
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (json.dumps({"pqi7": {"complete": True}}), assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")

        self.assertIn("0 of 51 complete", rendered)
        self.assertIn('<span id="pqi-progress-percentage">0%</span>', rendered)

    def test_pqi_completion_cards_follow_saved_db_flags(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (
                json.dumps({
                    "pqi2": {"complete": True, "responses": {"2.1": "yes", "2.2": "yes", "2.3": "yes", "2.4": "yes", "2.5": "yes", "2.6": "yes", "2.7": "yes", "2.8": "yes", "2.9": "yes", "2.10": "no", "2.11": "no"}},
                    "pqi3": {"completed": True, "records": {"record 1": {"emergent_curriculum": "yes", "co_learning": "yes", "documented_learning_future_planning": "yes"}, "record 2": {"emergent_curriculum": "yes", "co_learning": "yes", "documented_learning_future_planning": "yes"}}},
                    "pqi4": {"complete": True, "responses": {"4.1": "yes", "4.2": "yes", "4.3": "yes", "4.4": "yes"}},
                    "pqi5": {"complete": True, "responses": {"5.1": "yes", "5.2": "yes", "5.3": "no", "5.4": "yes"}},
                }),
                assessment_id,
            ),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('id="pqi2-complete-card"', rendered)
        self.assertIn('id="pqi3-complete-card"', rendered)
        self.assertIn('id="pqi4-complete-card"', rendered)
        self.assertIn('id="pqi5-complete-card"', rendered)
        self.assertNotIn('id="pqi2-summary-card"', rendered)
        self.assertNotIn('id="pqi3-summary-card"', rendered)
        self.assertNotIn('id="pqi4-summary-card"', rendered)
        self.assertNotIn('id="pqi5-summary-card"', rendered)

    def test_pqi68_cards_show_empty_draft_and_complete_statuses(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (
                json.dumps({
                    "pqi7": {"responses": {"1": [True, False, False]}},
                    "pqi8": {"complete": True, "responses": {"1": [True, True]}},
                }),
                assessment_id,
            ),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('class="pqi68-card status-empty"', rendered)
        self.assertIn('class="pqi68-card status-draft"', rendered)
        self.assertIn('class="pqi68-card status-complete"', rendered)
        self.assertIn('0 of 3 complete', rendered)
        self.assertIn('id="pqi68-complete-card"', rendered)
        self.assertIn('<strong>1</strong>', rendered)
        self.assertIn('<strong>--</strong>', rendered)
        self.assertIn('<strong>1</strong>', rendered)

    def test_pqi68_completion_banner_shows_when_all_three_are_complete(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (
                json.dumps({
                    "pqi6": {"complete": True, "responses": {"1": [True] * 3, "2": [True] * 4, "3": [True] * 4, "4": [True] * 4}},
                    "pqi7": {"complete": True, "responses": {"1": [True] * 3, "2": [True] * 3, "3": [True] * 4, "4": [True] * 2}},
                    "pqi8": {"complete": True, "responses": {"1": [True] * 2, "2": [True] * 2, "3": [True] * 2, "4": [True] * 2}},
                }),
                assessment_id,
            ),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('3 of 3 complete', rendered)
        self.assertIn('id="pqi68-complete-card" role="status" aria-live="polite">', rendered)
        self.assertIn("PQI 6-8 marked as complete", rendered)

    def test_pqi910_cards_show_data_and_shared_timed_page_link(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET pqi_findings = ? WHERE id = ?",
            (
                json.dumps({
                    "pqi9": {"responses": {"1": 3, "2": 4}},
                    "pqi10": {"complete": True, "score": 2, "responses": {str(index): 2 for index in range(1, 11)}},
                }),
                assessment_id,
            ),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('class="pqi68-card status-draft"', rendered)
        self.assertIn('class="pqi68-card status-complete"', rendered)
        self.assertIn("1 of 2 complete", rendered)
        self.assertIn("0 of 10 observations complete", rendered)
        self.assertIn('<strong>2</strong>', rendered)
        self.assertIn('href="/screens/pqi9-10-timed">Open PQI 9-10</a>', rendered)
        self.assertNotIn('href="/screens/pqi9-10-timed#pqi9"', rendered)
        self.assertNotIn('href="/screens/pqi9-10-timed#pqi10"', rendered)

        timed_rendered = self.client.get("/screens/pqi9-10-timed").data.decode("utf-8")
        self.assertIn("setActiveTab(location.hash === '#pqi10' ? 'pqi10' : 'pqi9')", timed_rendered)

    def test_save_pqi1_persists_nested_json(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi1",
            json={
                "certified_teaching_staff": 6,
                "total_teaching_staff": 12,
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()

        self.assertIsNotNone(saved_row)
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi1"]["score"], 2)
        self.assertEqual(saved_findings["pqi1"]["certified_teaching_staff"], 6)
        self.assertEqual(saved_findings["pqi1"]["total_teaching_staff"], 12)

    def test_complete_pqi1_marks_entry_complete(self):
        assessment_id = self.insert_assessment()

        response = self.client.post(
            "/api/assessments/pqi1",
            json={
                "assessment_id": assessment_id,
                "certified_teaching_staff": 6,
                "total_teaching_staff": 12,
                "complete": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        self.assertTrue(json.loads(saved_row[0])["pqi1"]["complete"])

    def test_save_pqi2_persists_nested_json(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi2",
            json={
                "complete": True,
                "responses": {
                    "2.1": "yes",
                    "2.2": "yes",
                    "2.3": "yes",
                    "2.4": "yes",
                    "2.5": "yes",
                    "2.6": "yes",
                    "2.7": "yes",
                    "2.8": "yes",
                    "2.9": "yes",
                    "2.10": "no",
                    "2.11": "no",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()

        self.assertIsNotNone(saved_row)
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi2"]["score"], 4)
        self.assertEqual(saved_findings["pqi2"]["yes_count"], 9)
        self.assertEqual(saved_findings["pqi2"]["question_count"], 11)
        self.assertEqual(saved_findings["pqi2"]["responses"]["2.10"], "no")

    def test_save_pqi2_persists_optional_note(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi2",
            json={
                "complete": True,
                "responses": {
                    "2.1": "yes",
                    "2.2": "yes",
                    "2.3": "yes",
                    "2.4": "yes",
                    "2.5": "yes",
                    "2.6": "yes",
                    "2.7": "yes",
                    "2.8": "yes",
                    "2.9": "yes",
                    "2.10": "no",
                    "2.11": "no",
                },
                "optional_note": "Classroom materials were refreshed to support the new environmental goals.",
            },
        )

        self.assertEqual(response.status_code, 200)

        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi2"]["optional_note"], "Classroom materials were refreshed to support the new environmental goals.")

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('id="pqi2-optional-note"', rendered)
        self.assertIn("Classroom materials were refreshed to support the new environmental goals.", rendered)

    def test_save_pqi2_complete_requires_all_answers(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi2",
            json={
                "complete": True,
                "responses": {
                    "2.1": "yes",
                    "2.2": "no",
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["message"], "Answer all PQI 2 questions before completing")

    def test_save_pqi5_persists_nested_json(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi5",
            json={
                "complete": True,
                "responses": {
                    "5.1": "yes",
                    "5.2": "yes",
                    "5.3": "no",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()

        self.assertIsNotNone(saved_row)
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi5"]["base_points"], 3)
        self.assertEqual(saved_findings["pqi5"]["bonus_point"], 0)
        self.assertEqual(saved_findings["pqi5"]["score"], 3)
        self.assertEqual(saved_findings["pqi5"]["responses"]["5.3"], "no")

    def test_save_pqi5_complete_requires_all_answers(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi5",
            json={
                "complete": True,
                "responses": {
                    "5.1": "yes",
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["message"], "Answer all PQI 5 questions before completing")

    def test_displayed_percentages_round_half_up_to_whole_number(self):
        self.assertEqual(round_percentage_half_up(66.5), 67)
        self.assertEqual(round_percentage_half_up(66.49), 66)
        self.assertEqual(round_percentage_half_up(33.3333333333), 33)
        self.assertEqual(round_percentage_half_up(66.6666666667), 67)

    def test_pqi4_renders_and_uses_static_percentage_bands(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('id="pqi4-card"', rendered)
        self.assertIn("Opportunities for Staff and Families to Get to Know Each Other", rendered)
        self.assertIn("meets their diverse needs", rendered)

        cases = [
            ({"4.1": "no", "4.2": "no", "4.3": "no"}, 1),
            ({"4.1": "yes", "4.2": "no", "4.3": "no"}, 2),
            ({"4.1": "yes", "4.2": "yes", "4.3": "no"}, 3),
            ({"4.1": "yes", "4.2": "yes", "4.3": "yes"}, 4),
        ]
        for responses, expected_score in cases:
            response = self.client.post(
                "/api/assessments/pqi4",
                json={"complete": True, "responses": responses},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["score"], expected_score)

        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi4"]["score"], 4)
        self.assertEqual(saved_findings["pqi4"]["responses"]["4.3"], "yes")

    def test_save_pqi4_persists_optional_note(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi4",
            json={
                "assessment_id": assessment_id,
                "complete": True,
                "responses": {"4.1": "yes", "4.2": "yes", "4.3": "yes"},
                "optional_note": "Staff were introduced to family support resources during orientation.",
            },
        )

        self.assertEqual(response.status_code, 200)

        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi4"]["optional_note"], "Staff were introduced to family support resources during orientation.")

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('id="pqi4-optional-note"', rendered)
        self.assertIn("Staff were introduced to family support resources during orientation.", rendered)

    def test_save_pqi3_persists_and_reloads_records_and_notes(self):
        assessment_id = self.insert_assessment()

        records = {
            f"record {index}": {
                "emergent_curriculum": "yes" if index == 1 else "no",
                "co_learning": "yes",
                "documented_learning_future_planning": "yes",
                "notes": f"Evidence note {index}",
            }
            for index in range(1, 11)
        }
        response = self.client.post(
            "/api/assessments/pqi3",
            json={"assessment_id": assessment_id, "records": records, "completed": True},
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertTrue(saved_findings["pqi3"]["completed"])
        self.assertEqual(saved_findings["pqi3"]["record 1"]["emergent_curriculum"], "yes")
        self.assertEqual(saved_findings["pqi3"]["record 1"]["notes"], "Evidence note 1")

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi3").get_data(as_text=True)
        self.assertIn('value="Evidence note 1"', rendered)
        self.assertIn('data-emergent_curriculum="yes"', rendered)
        self.assertIn("PQI 3 marked as complete", rendered)

    def test_save_pqi3_accepts_numeric_record_keys(self):
        assessment_id = self.insert_assessment()
        records = {
            str(index): {
                "emergent_curriculum": "yes" if index == 1 else "no",
                "co_learning": "yes",
                "documented_learning_future_planning": "yes",
                "notes": f"Numeric-key note {index}",
            }
            for index in range(1, 11)
        }

        response = self.client.post(
            "/api/assessments/pqi3",
            json={"assessment_id": assessment_id, "records": records, "completed": True},
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi3"]["record 1"]["notes"], "Numeric-key note 1")
        self.assertTrue(saved_findings["pqi3"]["completed"])

    def test_save_pqi6_persists_hierarchy_state_and_locks_later_levels(self):
        assessment_id = self.insert_assessment()
        response = self.client.post(
            "/api/assessments/pqi6",
            json={
                "assessment_id": assessment_id,
                "complete": True,
                "responses": {
                    "1": [True, True, True],
                    "2": [True, True, False, False],
                    "3": [True, True, True, True],
                    "4": [False, False, False, False],
                },
                "partial_descriptor": "Level 2 was observed inconsistently.",
                "observation_notes": "Observed during the afternoon classroom visit.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["calculated_level"], 1)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        pqi6 = saved_findings["pqi6"]
        self.assertTrue(pqi6["complete"])
        self.assertEqual(pqi6["calculated_level"], 1)
        self.assertEqual(pqi6["responses"]["2"], [True, True, False, False])
        self.assertEqual(pqi6["responses"]["3"], [False, False, False, False])
        self.assertEqual(pqi6["partial_descriptor"], "Level 2 was observed inconsistently.")
        self.assertEqual(pqi6["observation_notes"], "Observed during the afternoon classroom visit.")

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi6-8-hierarchy").get_data(as_text=True)
        self.assertIn("Level 2 was observed inconsistently.", rendered)
        self.assertEqual(rendered.count("Partial descriptor"), 1)
        self.assertIn("Observed during the afternoon classroom visit.", rendered)
        self.assertIn('id="pqi6-save-button" type="button" disabled', rendered)

    def test_save_pqi6_records_visual_plus_modifier_for_partial_next_level(self):
        assessment_id = self.insert_assessment()
        response = self.client.post(
            "/api/assessments/pqi6",
            json={
                "assessment_id": assessment_id,
                "complete": True,
                "responses": {
                    "1": [True, True, True],
                    "2": [True, True, False, False],
                    "3": [False, False, False, False],
                    "4": [False, False, False, False],
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["calculated_level"], 1)
        self.assertEqual(response.get_json()["score_modifier"], "+")
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi6"]["score_modifier"], "+")

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi6-8-hierarchy").get_data(as_text=True)
        self.assertIn("1+", rendered)

    def test_save_pqi7_persists_separate_hierarchy_state_and_applies_two_of_four_modifier(self):
        assessment_id = self.insert_assessment()
        response = self.client.post(
            "/api/assessments/pqi7",
            json={
                "assessment_id": assessment_id,
                "complete": True,
                "responses": {
                    "1": [True, True, True],
                    "2": [True, True, True],
                    "3": [True, True, False, False],
                    "4": [False, False],
                },
                "partial_descriptor": "Two level 3 indicators were observed.",
                "observation_notes": "Observed during circle time.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["calculated_level"], 2)
        self.assertEqual(response.get_json()["score_modifier"], "+")
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertIn("pqi7", saved_findings)
        self.assertNotIn("pqi6", saved_findings)
        self.assertEqual(saved_findings["pqi7"]["responses"]["3"], [True, True, False, False])

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi7").get_data(as_text=True)
        self.assertIn("Two level 3 indicators were observed.", rendered)
        self.assertIn('id="pqi7-save-button" type="button" disabled', rendered)

    def test_save_assignment_draft_populates_facility_name(self):
        draft_payload = {
            "local_record_name": "North Harbor Child Care",
            "external_system": "Compass",
            "program": "Child Care Center",
            "facility_type": "Mixed Age Center",
            "assessment_date": "2026-07-17",
            "visit_date": "2026-07-14",
            "inspection_type": "Annual Monitoring Visit",
        }

        with self.client.session_transaction() as session:
            session.pop("current_assessment_id", None)

        with app.test_request_context("/"):
            save_assignment_draft(draft_payload)

        saved_row = self.conn.execute(
            """
            SELECT facilities.name, assessments.external_system
            FROM assessments
            JOIN facilities ON facilities.id = assessments.facility_id
            WHERE assessments.assessment_name = ?
            """,
            ("North Harbor Child Care",),
        ).fetchone()

        self.assertIsNotNone(saved_row)
        self.assertEqual(saved_row[0], "North Harbor Child Care")
        self.assertEqual(saved_row[1], "Compass")


if __name__ == "__main__":
    unittest.main()
