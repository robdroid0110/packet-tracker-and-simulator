import json
import tempfile
import unittest
from pathlib import Path

from netsim.cli import CommandProcessor
from netsim.model import LabError, NetworkLab


class FirstLabWebTests(unittest.TestCase):
    def setUp(self):
        self.lab = NetworkLab()
        self.lab.add_device("pc", "Client")
        self.lab.add_device("server", "WebServer")
        self.lab.set_ip("Client", "eth0", "192.168.0.110/24")
        self.lab.set_ip("WebServer", "eth0", "192.168.0.105/24")
        self.lab.connect("Client", "eth0", "WebServer", "eth0", "copper-cross")
        self.lab.set_dns_client("Client", "192.168.0.105")
        self.lab.dns_service("WebServer", True)
        self.lab.dns_record("WebServer", "www.firstlab.com", "192.168.0.105")

    def test_dns_and_web_browser_workflow(self):
        response = self.lab.http_request("Client", "www.firstlab.com")
        self.assertEqual(response["status"], 200)
        self.assertIn("simulated Web Server", response["html"])
        self.assertEqual(response["resolved_ip"], "192.168.0.105")
        self.assertEqual([event["protocol"] for event in self.lab.packet_events], ["DNS", "DNS", "TCP", "HTTP", "HTTP"])
        self.assertTrue(all(event["ok"] for event in self.lab.packet_events))

    def test_direct_ip_and_unresolved_hostname(self):
        self.lab.set_dns_client("Client", None)
        self.assertTrue(self.lab.http_request("Client", "192.168.0.105")["ok"])
        with self.assertRaisesRegex(LabError, "Host Name Unresolved"):
            self.lab.http_request("Client", "www.firstlab.com")
        with self.assertRaisesRegex(LabError, "Host Name Unresolved"):
            self.lab.http_request("Client", "www")

    def test_network_and_service_state_respected(self):
        self.lab.http_service("WebServer", False)
        with self.assertRaisesRegex(LabError, "HTTP Service Unavailable"):
            self.lab.http_request("Client", "192.168.0.105")
        self.lab.http_service("WebServer", True)
        self.lab.set_power("WebServer", False)
        with self.assertRaisesRegex(LabError, "Web Server Unreachable"):
            self.lab.http_request("Client", "192.168.0.105")
        self.lab.set_power("WebServer", True)
        self.lab.dns_service("WebServer", False)
        with self.assertRaisesRegex(LabError, "Host Name Unresolved"):
            self.lab.http_request("Client", "www.firstlab.com")

    def test_wrong_cable_and_missing_dns_record(self):
        self.lab.disconnect("Client", "eth0")
        self.lab.connect("Client", "eth0", "WebServer", "eth0", "copper-straight")
        with self.assertRaisesRegex(LabError, "Unresolved"):
            self.lab.http_request("Client", "www.firstlab.com")
        self.lab.disconnect("Client", "eth0")
        self.lab.connect("Client", "eth0", "WebServer", "eth0", "copper-cross")
        self.lab.dns_delete("WebServer", "www.firstlab.com")
        with self.assertRaisesRegex(LabError, "Unresolved"):
            self.lab.http_request("Client", "www.firstlab.com")

    def test_web_service_file_and_404(self):
        self.lab.set_http_page("WebServer", "/hello.html", "<h1>Lab</h1>")
        self.assertEqual(self.lab.http_request("Client", "http://www.firstlab.com/hello.html")["html"], "<h1>Lab</h1>")
        self.assertEqual(self.lab.http_request("Client", "http://www.firstlab.com/missing.html")["status"], 404)
        self.assertIn("404", self.lab.packet_events[-1]["detail"])

    def test_protocol_and_hostname_validation(self):
        for url in ("https://www.firstlab.com", "ftp://192.168.0.105", "http://192.168.0.105:8080"):
            with self.assertRaises(LabError):
                self.lab.http_request("Client", url)
        for name in ("a/b.com", "_nope", "bad name", "a..b"):
            with self.assertRaises(LabError):
                self.lab.dns_record("WebServer", name, "192.168.0.105")
        with self.assertRaises(LabError):
            self.lab.set_http_page("WebServer", "relative.html", "hello")

    def test_pdu_icmp_and_event_retention(self):
        result = self.lab.send_simple_pdu("Client", "WebServer")
        self.assertTrue(result["ok"], result)
        self.assertEqual([e["detail"] for e in self.lab.packet_events[-2:]], ["Echo Request", "Echo Reply"])
        self.lab.set_power("WebServer", False)
        result = self.lab.send_simple_pdu("Client", "WebServer")
        self.assertFalse(result["ok"])
        for n in range(280):
            self.lab._packet_event("ICMP", "Client", "WebServer", str(n))
        self.assertEqual(len(self.lab.packet_events), 256)
        self.assertGreater(self.lab.packet_counter, 280)

    def test_agent_commands(self):
        cp = CommandProcessor(self.lab)
        self.assertIn("www.firstlab.com", cp.execute("show dns WebServer"))
        self.assertIn("HTTP 200", cp.execute("web-get Client www.firstlab.com"))
        self.assertIn("Successful", cp.execute("pdu Client WebServer"))
        self.assertIn("DNS", cp.execute("show packet-events"))
        self.assertIn("off", cp.execute("dns-service WebServer off"))
        self.assertIn("disabled", cp.execute("show dns WebServer"))
        self.assertTrue(cp.execute("dns-add WebServer bad/name 192.168.0.105").startswith("ERROR:"))

    def test_power_cycle_resets_learned_state_not_ip_or_dns(self):
        self.lab.http_request("Client", "www.firstlab.com")
        self.assertTrue(self.lab.devices["Client"].arp_table)
        self.assertTrue(self.lab.packet_events)
        cp = CommandProcessor(self.lab)
        self.assertIn("restarted", cp.execute("power-cycle"))
        self.assertFalse(self.lab.devices["Client"].arp_table)
        self.assertEqual(self.lab.packet_events, [])
        self.assertEqual(self.lab.devices["Client"].interfaces["eth0"].ip, "192.168.0.110/24")
        self.assertEqual(self.lab.devices["WebServer"].dns_records["www.firstlab.com"], "192.168.0.105")
        self.assertTrue(self.lab.http_request("Client", "www.firstlab.com")["ok"])

    def test_persistence_and_legacy_default(self):
        self.lab.send_simple_pdu("Client", "WebServer")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "firstlab.json"
            self.lab.save(str(path))
            restored = NetworkLab()
            restored.load(str(path))
            self.assertEqual(restored.devices["Client"].dns_server, "192.168.0.105")
            self.assertEqual(restored.devices["WebServer"].dns_records["www.firstlab.com"], "192.168.0.105")
            self.assertTrue(restored.http_request("Client", "www.firstlab.com")["ok"])
            self.assertEqual(restored.packet_events[0], self.lab.packet_events[0])
            data = json.loads(path.read_text())
            for d in data["devices"].values():
                for field in ("dns_server", "dns_enabled", "dns_records", "http_enabled", "http_pages"):
                    d.pop(field, None)
            data.pop("packet_events", None)
            data.pop("packet_counter", None)
            path.write_text(json.dumps(data))
            restored.load(str(path))
            self.assertEqual(restored.packet_events, [])
            self.assertIsNone(restored.devices["Client"].dns_server)


if __name__ == "__main__":
    unittest.main()
