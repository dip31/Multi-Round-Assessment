import {
  Brain,
  Code2,
  FileText,
  Mic,
  Sparkles,
  Upload,
  UserCheck,
} from 'lucide-react';
import { formatRelative, formatDateTime } from './formatters';

/**
 * ActivityTimeline — vertical feed of recent events.
 *
 * Consumes the `activity[]` shape: { id, type, title, detail, timestamp, status }.
 * Dates render relatively ("3 weeks ago") with the absolute timestamp in the
 * `title` attribute so hovering still gives the exact moment.
 */

const TYPE_META = {
  aptitude: { icon: Brain, tone: 'bg-accent/10 text-accent' },
  coding: { icon: Code2, tone: 'bg-blue-50 text-blue-600' },
  interview: { icon: Mic, tone: 'bg-amber-50 text-amber-600' },
  resume: { icon: FileText, tone: 'bg-emerald-50 text-emerald-600' },
  upload: { icon: Upload, tone: 'bg-emerald-50 text-emerald-600' },
  profile: { icon: UserCheck, tone: 'bg-slate-100 text-slate-600' },
  default: { icon: Sparkles, tone: 'bg-slate-100 text-slate-500' },
};

export default function ActivityTimeline({ items = [], className = '' }) {
  if (!items.length) {
    return (
      <p className={`px-1 py-6 text-center text-sm text-slate-500 ${className}`}>
        No recent activity to show.
      </p>
    );
  }

  return (
    <ol className={`relative space-y-5 ${className}`}>
      {/* Connecting rail, inset so it aligns under the icon centres. */}
      <span
        aria-hidden="true"
        className="absolute left-[15px] top-2 bottom-2 w-px bg-slate-200"
      />

      {items.map((item) => {
        const meta = TYPE_META[item.type] ?? TYPE_META.default;
        const Icon = meta.icon;
        const isTerminated = item.status === 'terminated';

        return (
          <li key={item.id} className="relative flex gap-3">
            <span
              className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-4 ring-white ${
                isTerminated ? 'bg-red-50 text-red-500' : meta.tone
              }`}
            >
              <Icon size={15} aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <p className="text-sm font-medium leading-snug text-slate-900">{item.title}</p>
              {item.detail && (
                <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{item.detail}</p>
              )}
              <time
                dateTime={item.timestamp}
                title={formatDateTime(item.timestamp)}
                className="mt-1 inline-block text-[11px] font-medium text-slate-400"
              >
                {formatRelative(item.timestamp)}
              </time>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
