"""Timed PQI 9 and 10 screens, scores, notes, and completion."""

import json

import json

from app import app
from tests.test_support import AssessmentTestCase


class PqiNineTenTests(AssessmentTestCase):
    """Timed PQI 9 and 10 screens, scores, notes, and completion."""

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



