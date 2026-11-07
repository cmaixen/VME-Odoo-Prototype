import base64
from datetime import date

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import format_date

from ..models.vme_compliance import certificate_applies, region_from_zip

TODAY = date(2026, 11, 5)
PDF = base64.b64encode(b"%PDF-1.4 test")


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestCompliance(TransactionCase):
    """Building insurance and mandatory certificates (vme_compliance.py, docs/dev/verzekeringen-attesten.md)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({
            "name": "Residentie Attest", "zip": "2000", "construction_year": 1980})
        cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": n, "lot_type": "apartment"} for n in ("A1", "A2", "A3")])
        cls.insurer = cls.env["res.partner"].create({"name": "Verzekeraar Test", "is_company": True})
        cls.electrical = cls.env["vme.installation"].create({
            "association_id": cls.vme.id, "name": "Elektriciteit gemene delen", "installation_type": "electrical"})
        cls.env["vme.inspection"].create({"installation_id": cls.electrical.id, "date": date(2024, 1, 10)})

    def _certificate(self, certificate_type, when, vme=None):
        folder = "vme_belgie.folder_pid" if certificate_type == "pid" else "vme_belgie.folder_certificates"
        return self.env["vme.document"].create({
            "name": f"Attest {certificate_type}", "association_id": (vme or self.vme).id,
            "folder_id": self.env.ref(folder).id, "certificate_type": certificate_type,
            "date": when, "datas": PDF,
        })

    def _policy(self, date_end, **vals):
        return self.env["vme.insurance.policy"].create({
            "association_id": self.vme.id, "name": "Brandverzekering gebouw", "policy_type": "building",
            "insurer_id": self.insurer.id, "policy_number": "BR-TEST-1", "date_end": date_end,
            "insured_value": 2500000, **vals,
        })

    def _status(self):
        return {entry["type"]: entry["state"] for entry in self.vme._get_certificate_status(TODAY)}

    def _signals(self):
        return {signal["code"]: signal["message"] for signal in self.vme._get_signals(TODAY)}

    # Rules

    def test_region_from_zip(self):
        self.assertEqual(region_from_zip("2000"), "flanders")
        self.assertEqual(region_from_zip("1000"), "brussels")
        self.assertEqual(region_from_zip("1300"), "wallonia")
        self.assertEqual(region_from_zip("4000"), "wallonia")
        self.assertEqual(region_from_zip("9000"), "flanders")
        self.assertFalse(region_from_zip("NL-1234"))
        self.assertEqual(self.vme.region, "flanders")

    def test_which_certificates_apply(self):
        self.assertTrue(certificate_applies("asbestos", "flanders", 2000, 3))
        self.assertFalse(certificate_applies("asbestos", "flanders", 2001, 3))
        self.assertFalse(certificate_applies("asbestos", "wallonia", 1980, 3))
        self.assertIsNone(certificate_applies("asbestos", "flanders", 0, 3))
        self.assertTrue(certificate_applies("pid", "brussels", 2001, 3))
        self.assertFalse(certificate_applies("pid", "flanders", 2000, 3))
        self.assertTrue(certificate_applies("epc_common", "flanders", 0, 2))
        self.assertFalse(certificate_applies("epc_common", "flanders", 0, 1))
        self.assertTrue(certificate_applies("electrical", "wallonia", 0, 0))

    def test_status_per_certificate(self):
        # Built in 1980 in Flanders: asbestos and EPC, no PID; the electrical inspection is valid until 2029.
        self.assertEqual(self._status(), {"asbestos": "missing", "epc_common": "missing", "electrical": "ok"})
        asbestos = self._certificate("asbestos", date(2020, 3, 1))
        self.assertEqual(asbestos.valid_until, date(2030, 3, 1))
        self._certificate("epc_common", date(2016, 12, 1))  # valid until 1 December 2026
        self.assertEqual(self._status(), {"asbestos": "ok", "epc_common": "expiring", "electrical": "ok"})
        self._certificate("epc_common", date(2016, 10, 1))  # an older one does not count
        self.assertEqual(self._status()["epc_common"], "expiring")
        self.vme.construction_year = 2005
        self.assertEqual(self._status(), {"pid": "missing", "epc_common": "expiring", "electrical": "ok"})
        self._certificate("pid", date(2005, 6, 1))
        status = {e["type"]: e for e in self.vme._get_certificate_status(TODAY)}
        self.assertEqual(status["pid"]["state"], "ok")
        self.assertFalse(status["pid"]["valid_until"])
        self.vme.construction_year = 0
        self.assertEqual(self._status()["asbestos"], "unknown")

    def test_electrical_from_installation(self):
        self.env["vme.inspection"].search([("installation_id", "=", self.electrical.id)]).date = date(2021, 1, 10)
        self.assertEqual(self._status()["electrical"], "expired")
        # An overdue inspection is the signal "inspection", not a second signal "certificate".
        self.assertIn("inspection", self._signals())
        self._certificate("asbestos", date(2020, 3, 1))
        self._certificate("epc_common", date(2020, 3, 1))
        self.assertNotIn("certificate", self._signals())
        self.electrical.active = False
        self.assertEqual(self._status()["electrical"], "missing")
        self.assertIn("Elektrische keuring gemene delen ontbreekt", self._signals()["certificate"])

    # Signals

    def test_certificate_signal_and_search(self):
        Vme = self.env["vme.association"]
        self.assertIn("Asbestattest gemene delen ontbreekt", self._signals()["certificate"])
        self.assertTrue(self.vme.signal_certificate)
        self.assertIn(self.vme, Vme.search([("signal_certificate", "=", True)]))
        self._certificate("asbestos", date(2020, 3, 1))
        self._certificate("epc_common", date(2020, 3, 1))
        self.assertNotIn("certificate", self._signals())
        self.assertNotIn(self.vme, Vme.search([("signal_certificate", "=", True)]))
        # The portfolio reads everything at once and gives the same signals.
        figures = self.vme._get_portfolio_figures(TODAY)[self.vme.id]["signals"]
        self.assertEqual({s["code"] for s in figures}, set(self._signals()))

    def test_insurance_signal(self):
        self.assertEqual(self._signals()["insurance"], "Geen brandverzekering van het gebouw geregistreerd.")
        policy = self._policy(date(2027, 3, 31))
        self.assertNotIn("insurance", self._signals())
        policy.date_end = date(2026, 12, 1)
        self.assertIn(f"vervalt op {format_date(self.env, date(2026, 12, 1))}", self._signals()["insurance"])
        self.assertTrue(self.vme.signal_insurance)
        policy.date_end = date(2026, 10, 31)
        self.assertIn(f"vervallen sinds {format_date(self.env, date(2026, 10, 31))}", self._signals()["insurance"])
        # A liability policy is not a fire insurance of the building.
        policy.policy_type = "liability"
        self.assertIn("Geen brandverzekering", self._signals()["insurance"])

    # Insurance policy

    def test_policy_notice_deadline_and_renewal(self):
        policy = self._policy(date(2026, 12, 1), date_start=date(2025, 12, 2))
        self.assertEqual(policy.notice_deadline, date(2026, 9, 1))
        self.assertEqual(policy.due_state, "due_30")
        policy._cron_schedule_policy_activities()
        self.assertEqual(len(policy.activity_ids), 1)
        # The notice deadline has passed: the task is due on the due date itself.
        self.assertEqual(policy.activity_ids.date_deadline, date(2026, 12, 1))
        policy._cron_schedule_policy_activities()
        self.assertEqual(len(policy.activity_ids), 1)
        policy.action_renewed()
        self.assertEqual((policy.date_start, policy.date_end), (date(2026, 12, 2), date(2027, 12, 1)))
        self.assertFalse(policy.activity_ids)
        self.assertEqual(policy.due_state, "ok")
        self.assertIn(f"nieuwe vervaldag {format_date(self.env, date(2027, 12, 1))}", policy.message_ids[0].body)
        with self.assertRaises(UserError):
            self._policy(False).action_renewed()

    def test_policy_task_before_notice_deadline(self):
        policy = self._policy(date(2027, 2, 15))
        policy._cron_schedule_policy_activities()
        self.assertEqual(policy.activity_ids.date_deadline, date(2026, 11, 15))
        self.assertFalse(self._policy(date(2027, 6, 1), policy_number="BR-TEST-2").activity_ids)

    def test_policy_claims(self):
        policy = self._policy(date(2027, 3, 31))
        claim = self.env["vme.damage.claim"].create({
            "association_id": self.vme.id, "name": "Waterschade test", "event_date": date(2026, 11, 1)})
        self.assertEqual(claim.policy_id, policy)
        self.assertEqual(policy.claim_count, 1)
        self.assertEqual(policy.action_open_claims()["domain"], [("policy_id", "=", policy.id)])

    def test_cron_tasks_go_to_the_case_manager(self):
        """The crons run as OdooBot: their tasks go to the case manager of the VME (B-D4)."""
        manager = self.env["res.users"].create({"name": "Dossierbeheerder Attest", "login": "beheerder.attest"})
        self.vme.manager_user_id = manager
        policy = self._policy(date(2026, 12, 1), user_id=False)
        self.assertEqual(self.env.user, self.env.ref("base.user_root"))
        policy._cron_schedule_policy_activities()
        self.env["vme.association"]._cron_schedule_certificate_activities()
        self.assertEqual(policy.activity_ids.user_id, manager)
        self.assertEqual(self.vme.activity_ids.user_id, manager)

    # Tasks for certificates

    def test_certificate_tasks(self):
        Vme = self.env["vme.association"]
        Vme._cron_schedule_certificate_activities()
        summaries = sorted(self.vme.activity_ids.mapped("summary"))
        self.assertEqual(summaries, ["Asbestattest gemene delen laten opmaken",
                                     "EPC gemeenschappelijke delen laten opmaken"])
        Vme._cron_schedule_certificate_activities()
        self.assertEqual(len(self.vme.activity_ids), 2)
        # A new certificate closes its task; nothing is sent.
        self._certificate("asbestos", date(2026, 11, 4))
        self.assertEqual(self.vme.activity_ids.mapped("summary"), ["EPC gemeenschappelijke delen laten opmaken"])
        # An almost expired certificate does not close the task.
        self._certificate("epc_common", date(2016, 12, 1))
        self.assertEqual(len(self.vme.activity_ids), 1)

    def test_compliance_html(self):
        self._policy(date(2026, 12, 1))
        html = str(self.vme.compliance_html)
        self.assertIn("BR-TEST-1", html)
        self.assertIn("Asbestattest gemene delen", html)
        self.assertIn("Ontbreekt", html)
        action = self.vme.with_context(certificate_type="asbestos").action_add_certificate()
        self.assertEqual(action["context"]["default_certificate_type"], "asbestos")
        self.assertEqual(action["context"]["default_folder_id"], self.env.ref("vme_belgie.folder_certificates").id)
        card = str(self.vme.building_card_html)
        self.assertIn("Verzekering en attesten", card)

    # Sale of a lot

    def test_notary_information(self):
        self._policy(date(2027, 3, 31))
        self._certificate("epc_common", date(2020, 3, 1))
        sale = self.env["vme.sale.file"].create({
            "association_id": self.vme.id, "lot_ids": self.vme.lot_ids[:1].ids,
            "first_request_date": date(2026, 11, 2)})
        info = sale._get_notary_information()
        states = {e["type"]: e["state"] for e in info["certificates"]}
        self.assertEqual(states["asbestos"], "missing")
        self.assertEqual(states["epc_common"], "ok")
        self.assertEqual(info["insurance"].policy_number, "BR-TEST-1")
        html = str(sale.information_html)
        self.assertIn("9. Verplichte attesten van de gemene delen", html)
        self.assertIn("Ontbreekt", html)
        self.assertIn("BR-TEST-1", html)
