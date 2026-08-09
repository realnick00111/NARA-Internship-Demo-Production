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
        self.assertIn('value="2026-04-12"', rendered)
        self.assertIn('Ada Lovelace', rendered)
        self.assertIn('Sunrise Learning Center', rendered)

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
