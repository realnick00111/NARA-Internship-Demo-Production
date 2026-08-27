"""Calculation readiness, result status, finalization, and component scoring."""

import json
from unittest.mock import patch

from app import app
from constants import INCLUDED_COMPONENTS, REGULATION_SET_NAME, REGULATION_SET_VERSION
from tests.test_support import AssessmentTestCase


class CalculationResultsTests(AssessmentTestCase):
    """Calculation readiness, result status, finalization, and component scoring."""

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


    def test_calculation_review_warns_for_draft_with_existing_result(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET calculated_result = ? WHERE id = ?",
            (json.dumps({"score": 9}), assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/calculation-review").data.decode("utf-8")

        self.assertIn('class="pqi-complete-card danger"', rendered)
        self.assertIn("Results are outdated", rendered)

        self.conn.execute("UPDATE assessments SET status = ? WHERE id = ?", ("final", assessment_id))
        self.conn.commit()

        rendered = self.client.get("/screens/calculation-review").data.decode("utf-8")

        self.assertNotIn("Results are outdated", rendered)


    def test_result_summary_warns_for_draft_with_existing_result(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET calculated_result = ? WHERE id = ?",
            (json.dumps({"score": 9}), assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/result-summary").data.decode("utf-8")

        self.assertIn('class="pqi-complete-card danger"', rendered)
        self.assertIn("Results are outdated", rendered)


    def test_provisional_result_can_be_finalized(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET calculated_result = ?, status = ? WHERE id = ?",
            (json.dumps({"CALCULATED_CH": 8, "RWCH_REFERENCE": 10}), "provisional", assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/result-summary").data.decode("utf-8")
        self.assertNotIn('disabled aria-disabled="true"', rendered)

        response = self.client.post("/assessments/finalize")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conn.execute("SELECT status FROM assessments WHERE id = ?", (assessment_id,)).fetchone()[0], "final")


    def test_result_summary_disables_finalize_for_needs_review_result(self):
        assessment_id = self.insert_assessment()
        self.conn.execute(
            "UPDATE assessments SET calculated_result = ?, status = ? WHERE id = ?",
            (json.dumps({"CALCULATED_CH": 12, "RWCH_REFERENCE": 10}), "needs review", assessment_id),
        )
        self.conn.commit()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/result-summary").data.decode("utf-8")

        self.assertIn('disabled aria-disabled="true"', rendered)

        response = self.client.post("/assessments/finalize")

        self.assertEqual(response.status_code, 400)


    def test_calculation_marks_result_needs_review_when_ch_exceeds_reference(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        with patch("routes.build_validation_context", return_value={"assessment_id": assessment_id, "blocking_errors": []}), patch(
            "routes.build_calculation_result",
            return_value={"CALCULATED_CH": 12, "RWCH_REFERENCE": 10},
        ):
            response = self.client.post("/assessments/calculate")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.conn.execute("SELECT status FROM assessments WHERE id = ?", (assessment_id,)).fetchone()[0], "needs review")


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



