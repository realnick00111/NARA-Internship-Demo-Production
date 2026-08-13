import json
import unittest

from app import app, get_db_connection, save_assignment_draft, set_current_assessment


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

    def test_new_assessment_uses_facility_type_dropdown(self):
        assessment_id = self.insert_assessment()

        with app.test_request_context("/"):
            set_current_assessment(assessment_id)
            rendered = app.view_functions["screen"]("new-assessment")

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
        self.assertIn('href="/screens/pqi3-sample"', rendered)
        self.assertIn('href="/screens/audit-history"', rendered)

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
        self.assertIn('disabled', rendered)

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
