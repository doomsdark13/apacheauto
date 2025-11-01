import unittest
from apache_monitor.log_monitor import LogMonitor

class TestLogParsing(unittest.TestCase):
    def setUp(self):
        self.config = {
            "suspicious_extensions": [".php"],
            "dangerous_patterns": []
        }
        self.monitor = LogMonitor(self.config, None)

    def test_parse_valid_line(self):
        line = '192.168.1.1 - - [01/Nov/2025:02:34:12 +0000] "GET /index.php HTTP/1.1" 200 1234 "-" "Mozilla/5.0"'
        result = self.monitor.parse_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")
        self.assertEqual(result["path"], "/index.php")

    def test_suspicious_path(self):
        self.assertTrue(self.monitor.is_suspicious_path("/test.php"))
        self.assertFalse(self.monitor.is_suspicious_path("/style.css"))

if __name__ == "__main__":
    unittest.main()