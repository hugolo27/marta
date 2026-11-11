"""Local labeling tool for the blind reference samples, phase1-accuracy-assessment (task 4.4).
Serves label_reference.html on localhost and writes each saved point back into the same blind CSV,
validated with reference_labels.parse() so a label can never contradict its attributes. Only the
blind CSV is read: no stratum, map label or model output reaches the page.

Imagery comes from Esri World Imagery Wayback, queried per point for the real capture date of each
release, so the date written to the CSV is the image's, not the release's. Google Earth Pro stays
the primary source in the protocol; the page links to it for every point.

Usage: .venv/bin/python scripts/32_label_reference.py data/study_area/accuracy_assessment/aoi_sample.csv"""

import csv
import json
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import reference_labels

PAGE = Path(__file__).with_name("label_reference.html")
PORT = 8765


def dates_of(columns):
    return sorted({m.group(1) for c in columns if (m := re.fullmatch(r"label_(\d{4})", c))})


class Sample:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        with self.path.open() as f:
            reader = csv.DictReader(f)
            self.columns, self.rows = reader.fieldnames, list(reader)
        self.dates = dates_of(self.columns)

    def save(self, point_id, fields):
        with self.lock:
            row = next(r for r in self.rows if r["point_id"] == point_id)
            updated = {**row, **{k: v for k, v in fields.items() if k in self.columns and k not in ("point_id", "lon", "lat")}}
            for date in self.dates:
                reference_labels.parse(updated, date)
            row.update(updated)
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)
                writer.writeheader()
                writer.writerows(self.rows)
            tmp.replace(self.path)


def handler(sample):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/points":
                self._send(200, json.dumps({"file": sample.path.name, "dates": sample.dates, "rows": sample.rows}))
            else:
                self._send(404, "{}")

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            try:
                sample.save(body["point_id"], body["fields"])
            except ValueError as e:
                self._send(400, json.dumps({"error": str(e)}))
                return
            self._send(200, "{}")

        def log_message(self, *args):
            pass

    return Handler


def main():
    sample = Sample(sys.argv[1])
    server = ThreadingHTTPServer(("127.0.0.1", PORT), handler(sample))
    url = f"http://127.0.0.1:{PORT}/"
    print(f"{sample.path.name}: {len(sample.rows)} points, dates {sample.dates}. Open {url} (Ctrl+C to stop)")
    webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
