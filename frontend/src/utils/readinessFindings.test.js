import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { readinessFindings } from "./readinessFindings.js";

const pageSource = await readFile(new URL("../pages/TPOReadinessPage.jsx", import.meta.url), "utf8");
const finding = (id, category, extra = {}) => ({
    id, category, title: id, summary: `${id} summary`, evidence: `${id} evidence`,
    sample_size: 4, denominator: 8, metric: "readiness score", period: "30",
    action: { label: "Review", route: "/tpo/analytics" }, ...extra,
});

test("maps backend-selected Readiness Intelligence findings without reselecting them", () => {
    const result = readinessFindings({ insights: [
        finding("overall-readiness", "overall"),
        finding("competency-patterns", "competency"),
        finding("department-readiness-pattern", "cohort"),
        finding("evidence-reliability", "evidence"),
        finding("readiness-trend", "trend"),
        finding("lowest-competency", "legacy"),
    ] });
    assert.deepEqual(result.map((x) => x.id), [
        "overall-readiness", "competency-patterns", "department-readiness-pattern",
        "evidence-reliability", "readiness-trend",
    ]);
    assert.equal(result[0].heading, "overall-readiness");
    assert.equal(result[0].result, "overall-readiness summary");
    assert.match(result[0].evidence, /4 of 8/);
    assert.equal(result[0].action.route, "/tpo/analytics");
    assert.equal(result[0].period, "Last 30 days");
});

test("legacy insight IDs and legacy metric blocks never construct UI findings", () => {
    assert.deepEqual(readinessFindings({
        insights: [finding("lowest-competency", "legacy")],
        skill_gaps: { competencies: [{ competency_name: "SQL", avg_score: 1 }] },
        assessment_performance: { summary: { improving_candidates: {} } },
    }), []);
});

test("malformed payloads and unsupported action routes are handled safely", () => {
    assert.deepEqual(readinessFindings({ insights: [] }), []);
    assert.deepEqual(readinessFindings(undefined), []);
    assert.deepEqual(readinessFindings({ insights: [finding("bad", "overall", { denominator: null })] }), []);
    const [item] = readinessFindings({ insights: [finding("ok", "overall", {
        action: { label: "No", route: "/not-an-existing-route" },
    })] });
    assert.equal(item.action, null);
});

test("active Readiness page renders the replacement intelligence contract", () => {
    const section = pageSource.split('data-testid="readiness-insights"')[1]?.split('data-testid="readiness-footer"')[0];
    assert.ok(section);
    assert.match(section, /Readiness Intelligence/);
    assert.match(section, /A summary of scored preparedness, competency patterns, and evidence quality/);
    assert.match(pageSource, /readinessFindings\(data\)/);
    assert.match(section, /finding\.action\.route/);
    assert.doesNotMatch(section, /lowest-competency|drive-completion-gap|aptitude-repeat-attempts/);
});
