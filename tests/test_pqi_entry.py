"""PQI entry screen layout, progress totals, and completion cards."""

import json

import json

from app import app
from tests.test_support import AssessmentTestCase


class PqiEntryTests(AssessmentTestCase):
    """PQI entry screen layout, progress totals, and completion cards."""

    def test_pqi_entry_has_continue_to_validation_button(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")

        self.assertIn(">Continue to Validation</a>", rendered)
        self.assertIn('href="/screens/validation-summary">Continue to Validation</a>', rendered)


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



