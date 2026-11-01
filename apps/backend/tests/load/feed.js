// Baseline: every release candidate must keep the feed p95 under 200 ms and errors under 1%.
import { check, sleep } from "k6";
import http from "k6/http";

const BASE = __ENV.BASE_URL || "http://localhost:8080";
const USERS = ["demo", "asha", "kabir", "meera", "rohan"];
const PASSWORD = __ENV.SEED_PASSWORD || "RedStarDemo#2026";

export const options = {
  scenarios: {
    feed: {
      executor: "ramping-vus",
      stages: [
        { duration: "20s", target: Number(__ENV.VUS || 20) },
        { duration: "40s", target: Number(__ENV.VUS || 20) },
        { duration: "10s", target: 0 },
      ],
    },
  },
  thresholds: {
    "http_req_duration{name:feed}": ["p(95)<200"],
    "http_req_failed{name:feed}": ["rate<0.01"],
  },
};

export function setup() {
  return USERS.map((identifier) => {
    const res = http.post(`${BASE}/api/v1/auth/login`, JSON.stringify({ identifier, password: PASSWORD }), {
      headers: { "content-type": "application/json" },
      jar: new http.CookieJar(), // each login is a separate browser, otherwise the CSRF check rejects it
    });
    check(res, { "logged in": (r) => r.status === 200 });
    return res.cookies.rsv_access[0].value;
  });
}

export default function (tokens) {
  const token = tokens[__VU % tokens.length];
  const res = http.get(`${BASE}/api/v1/feed`, {
    headers: { Cookie: `rsv_access=${token}` },
    tags: { name: "feed" },
    jar: new http.CookieJar(),
  });
  check(res, { "feed ok": (r) => r.status === 200 });
  sleep(0.2);
}
