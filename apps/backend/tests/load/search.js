// Targets from docs: keyword p95 under 200 ms, hybrid under 400 ms. Run once with AI off and once with it on.
import { check, sleep } from "k6";
import http from "k6/http";

const BASE = __ENV.BASE_URL || "http://localhost:8080";
const LIMIT = Number(__ENV.P95_MS || 200);
const QUERIES = ["sunset", "beach", "travel", "goa ki shaam", "mountains", "coffee", "monsoon", "old lanes", "pune", "weekend"];

export const options = {
  vus: Number(__ENV.VUS || 20),
  duration: "40s",
  thresholds: { "http_req_duration{name:search}": [`p(95)<${LIMIT}`], "http_req_failed{name:search}": ["rate<0.01"] },
};

export default function () {
  const q = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  // A unique IP per virtual user, as behind nginx, so the per-IP limit is not what gets measured.
  const res = http.get(`${BASE}/search?q=${encodeURIComponent(q)}&limit=24`, {
    tags: { name: "search" }, headers: { "x-real-ip": `10.77.0.${__VU}` },
  });
  check(res, { ok: (r) => r.status === 200 });
  sleep(0.5);
}
