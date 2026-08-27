"""Hierarchical PQI 6 through 8 state, locking, and score modifiers."""

import json

from app import app
from tests.test_support import AssessmentTestCase


class PqiSixToEightTests(AssessmentTestCase):
    """Hierarchical PQI 6 through 8 state, locking, and score modifiers."""

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



