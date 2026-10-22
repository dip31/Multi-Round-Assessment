const ALLOWED_ROUTES = new Set(["/tpo/analytics", "/tpo/students"]);
const ALLOWED_CATEGORIES = new Set(["overall", "competency", "cohort", "evidence", "trend"]);

/** Map only backend-selected, evidence-backed insights; selection stays server-side. */
export function readinessFindings(data) {
    if (!Array.isArray(data?.insights)) return [];
    return data.insights
        .filter((item) => item && typeof item.id === "string"
            && ALLOWED_CATEGORIES.has(item.category)
            && typeof item.title === "string"
            && typeof item.summary === "string"
            && typeof item.evidence === "string"
            && Number.isFinite(item.sample_size)
            && Number.isFinite(item.denominator)
            && typeof item.metric === "string")
        .map((item) => ({
            id: item.id,
            category: item.category,
            heading: item.title,
            result: item.summary,
            supporting: item.evidence,
            evidence: `${item.sample_size} of ${item.denominator} ? ${item.metric}`,
            period: item.period === "all" || item.period == null ? "All time" : `Last ${item.period} days`,
            action: item.action && typeof item.action.label === "string"
                && ALLOWED_ROUTES.has(item.action.route)
                ? item.action : null,
        }));
}
