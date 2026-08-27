"""Facility identification forms, duplicate warnings, and draft persistence."""

import json

from app import app, save_assignment_draft, set_current_assessment
from tests.test_support import AssessmentTestCase


class FacilityIdentificationTests(AssessmentTestCase):

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


    def test_facility_screen_saves_inspector_identifier_and_assessment_notes(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/save-assignment-draft",
            json={
                "inspector_identifier": "EMP-10482",
                "assessment_notes": "Routine annual monitoring visit.",
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT inspector_identifier, assessment_notes FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        self.assertEqual(saved_row["inspector_identifier"], "EMP-10482")
        self.assertEqual(saved_row["assessment_notes"], "Routine annual monitoring visit.")

        rendered = self.client.get("/screens/facility-identification").data.decode("utf-8")
        self.assertIn('value="EMP-10482"', rendered)
        self.assertIn('value="Routine annual monitoring visit."', rendered)


    def test_duplicate_warning_ignores_empty_matching_fields(self):
        first_id = self.insert_assessment()
        second_id = self.insert_assessment()
        self.conn.execute(
            """
            UPDATE assessments
            SET assessment_name = '', assessment_date = '', visit_date = '',
                external_case_number = '', external_inspection_id = ''
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




