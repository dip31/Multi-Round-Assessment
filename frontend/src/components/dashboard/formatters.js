/**
 * Formatting helpers shared by the dashboard components.
 * Kept dependency-free — the repo has no date library.
 */

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** "12 Sep 2026" */
export function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** "12 Sep, 2:30 PM" */
export function formatDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  let hours = d.getHours();
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const meridiem = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12 || 12;
  return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${hours}:${minutes} ${meridiem}`;
}

/** "3 days ago" / "in 4 days" */
export function formatRelative(iso, now = new Date()) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';

  const diffMs = d.getTime() - now.getTime();
  const future = diffMs > 0;
  const abs = Math.abs(diffMs);

  const minutes = Math.round(abs / 60000);
  const hours = Math.round(abs / 3600000);
  const days = Math.round(abs / 86400000);

  let value;
  if (minutes < 1) return 'just now';
  if (minutes < 60) value = `${minutes} min`;
  else if (hours < 24) value = `${hours} hr${hours === 1 ? '' : 's'}`;
  else if (days < 30) value = `${days} day${days === 1 ? '' : 's'}`;
  else {
    const months = Math.round(days / 30);
    value = `${months} month${months === 1 ? '' : 's'}`;
  }

  return future ? `in ${value}` : `${value} ago`;
}

/** "1h 30m" from minutes */
export function formatDuration(minutes) {
  if (minutes === null || minutes === undefined) return '—';
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

/** Score with a graceful dash for null. */
export function formatScore(score, suffix = '%') {
  if (score === null || score === undefined) return '—';
  return `${Math.round(score)}${suffix}`;
}

/** "1,240" */
export function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('en-IN');
}
