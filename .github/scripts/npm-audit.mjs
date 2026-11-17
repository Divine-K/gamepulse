// Runs `npm audit` and fails on any high or critical advisory, except advisories listed in
// ACCEPTED below. Each exception needs a reason and must be removed once a fix exists.
//
//   node ../.github/scripts/npm-audit.mjs   (run from the frontend directory)
import { spawnSync } from "node:child_process";

const ACCEPTED = {
  // picomatch <= 4.0.7: ReDoS in extglob matching. No patched release exists (4.0.7 is the latest),
  // and it is reached only through build tooling (vite, tinyglobby, eslint) that matches file
  // globs from this repository's own config, never from user input. Not shipped to browsers.
  "https://github.com/advisories/GHSA-fc5q-39xc-vjpf": "no patched version exists; build-time only",
};

const run = spawnSync("npm", ["audit", "--json"], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
let report;
try {
  report = JSON.parse(run.stdout);
} catch {
  console.error("Could not read npm audit output:\n", run.stdout, run.stderr);
  process.exit(2);
}

const found = new Map(); // advisory url -> { name, severity, title }
for (const vuln of Object.values(report.vulnerabilities ?? {})) {
  for (const via of vuln.via) {
    if (typeof via === "object" && via.url) {
      found.set(via.url, { name: via.name, severity: via.severity, title: via.title });
    }
  }
}

let failed = false;
for (const [url, adv] of found) {
  const blocking = adv.severity === "high" || adv.severity === "critical";
  if (!blocking) continue;
  if (ACCEPTED[url]) {
    console.log(`accepted (${ACCEPTED[url]}): ${adv.name} ${adv.severity} ${url}`);
  } else {
    failed = true;
    console.error(`FAIL: ${adv.name} ${adv.severity}: ${adv.title}\n  ${url}`);
  }
}
console.log(failed ? "npm audit: unaccepted high/critical advisories found" : "npm audit: OK");
process.exit(failed ? 1 : 0);
