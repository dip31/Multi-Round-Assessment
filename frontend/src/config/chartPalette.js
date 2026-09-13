/**
 * Shared chart theming for the role dashboards.
 *
 * The repo had no shared chart palette before this module — the dark
 * `components/result-dashboard/*` charts each hardcode their own hexes.
 * Those are intentionally left alone; this palette is for the LIGHT
 * `components/dashboard/*` charts only.
 */

/** Named colours. `accent` matches the `--color-accent` design token. */
export const chartPalette = {
  accent: '#6C63FF',
  good: '#22c55e',
  mid: '#60a5fa',
  warn: '#f59e0b',
  bad: '#ef4444',
  muted: '#94a3b8',
};

/** Ordered series colours for multi-line / multi-bar charts. */
export const chartSeries = [
  chartPalette.accent,
  chartPalette.mid,
  chartPalette.warn,
  chartPalette.good,
  chartPalette.bad,
];

/** Axis tick styling — slate-500, matches the light card surface. */
export const chartAxisTick = { fill: '#64748b', fontSize: 12 };

/** Cartesian grid stroke — slate-200. */
export const chartGridStroke = '#e2e8f0';

/** Light tooltip surface. */
export const chartTooltipStyle = {
  background: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: '12px',
  boxShadow: '0 8px 24px rgba(15, 23, 42, 0.08)',
  color: '#0f172a',
  fontSize: '12px',
};

export const chartTooltipLabelStyle = {
  color: '#64748b',
  fontWeight: 600,
  marginBottom: 4,
};

/** Hover highlight for bar/area cursors — slate-50. */
export const chartCursorFill = { fill: '#f8fafc' };

/**
 * Maps a 0-100 score to a semantic colour.
 * Used by donuts, progress bars and score badges so the whole dashboard
 * agrees on what "good" looks like.
 */
export function scoreColor(score) {
  if (score === null || score === undefined) return chartPalette.muted;
  if (score >= 75) return chartPalette.good;
  if (score >= 60) return chartPalette.accent;
  if (score >= 45) return chartPalette.warn;
  return chartPalette.bad;
}

export default chartPalette;
