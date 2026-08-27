"""Assessment list, creation, navigation, status, and progress behavior."""

import json
from unittest.mock import patch

from app import app, set_current_assessment
from tests.test_support import AssessmentTestCase


class AssessmentWorkflowTests(AssessmentTestCase):
    """Assessment list, creation, navigation, status, and progress behavior."""

    def test_assessment_list_shows_static_calculation_model(self):
        self.insert_assessment()

        response = self.client.get("/screens/assessment-list")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<td>CCEEHM v1.2</td>", rendered)


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


    def test_structural_entry_uses_configured_density_model_dropdown(self):
        response = self.client.get("/screens/ch-structural-entry")
        rendered = response.data.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<select class="select" id="density-model" name="density_model">', rendered)
        self.assertIn('<option value="Trapezoidal" selected>Trapezoidal</option>', rendered)
        self.assertEqual(rendered.count('<option value="Trapezoidal"'), 1)


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


    def test_assessment_progress_recommends_calculation_for_outdated_result(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET calculated_result = ? WHERE id = ?",
            (json.dumps({"CALCULATED_CH": 8, "RWCH_REFERENCE": 10}), assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        with patch(
            "services.screen_contexts.build_validation_context",
            return_value={"blocking_errors": [], "total_checks": 0, "warnings": []},
        ):
            rendered = self.client.get("/screens/assessment-progress").data.decode("utf-8")

        self.assertIn('<div class="next-num">6</div>', rendered)
        self.assertIn("Complete Calculation", rendered)
        self.assertIn('href="/screens/result-summary"', rendered)
        self.assertNotIn('class="progress-item done" href="/screens/calculation-review"', rendered)


    def test_needs_review_uses_needs_updates_danger_status_on_list_and_dashboard(self):
        assessment_id = self.insert_assessment()
        self.conn.execute("UPDATE assessments SET status = ? WHERE id = ?", ("needs review", assessment_id))
        self.conn.commit()

        list_rendered = self.client.get("/screens/assessment-list").data.decode("utf-8")
        dashboard_rendered = self.client.get("/screens/agency-dashboard").data.decode("utf-8")

        self.assertIn('class="chip danger">Needs updates</span>', list_rendered)
        self.assertIn('class="chip danger">Needs updates</span>', dashboard_rendered)


    def test_assessment_result_matches_on_list_and_dashboard(self):
        self.insert_assessment(assessment_name="Draft assessment")
        provisional_id = self.insert_assessment(assessment_name="Provisional assessment")
        warning_id = self.insert_assessment(assessment_name="Warning assessment")
        self.conn.execute(
            "UPDATE assessments SET status = ?, calculated_result = ? WHERE id = ?",
            ("provisional", json.dumps({"PROGRAM_QUALITY_OUTCOME": "High-Mid"}), provisional_id),
        )
        self.conn.execute("UPDATE assessments SET status = ? WHERE id = ?", ("needs review", warning_id))
        self.conn.commit()

        list_rendered = self.client.get("/screens/assessment-list").data.decode("utf-8")
        dashboard_rendered = self.client.get("/screens/agency-dashboard").data.decode("utf-8")

        for rendered in (list_rendered, dashboard_rendered):
            self.assertIn("Not calculated", rendered)
            self.assertIn("High-Mid Quality", rendered)
            self.assertIn("Structural warning", rendered)
        self.assertEqual(list_rendered.count("Not calculated"), dashboard_rendered.count("Not calculated"))



