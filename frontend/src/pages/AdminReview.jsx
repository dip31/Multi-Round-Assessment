import React, { useCallback, useEffect, useMemo, useState } from 'react';
import AdminLayout from '../components/AdminLayout';
import { Toast } from '../components/Toast';
import {
    fetchAdminQuestionById,
    fetchAdminQuestions,
    saveAdminQuestionFeedback,
    updateAdminQuestionStatus,
} from '../services/adminQuestionService';

const PAGE_SIZE = 20;

const DEFAULT_SORTS = {
    difficulty: 'asc',
    attempts: 'desc',
    accuracy: 'asc',
    avg_time: 'desc',
};

const INSIGHT_BADGE_STYLES = {
    too_hard: 'bg-red-100 text-red-700',
    too_easy: 'bg-amber-100 text-amber-700',
    confusing: 'bg-amber-100 text-amber-700',
    balanced: 'bg-green-100 text-green-700',
};

const INSIGHT_LABELS = {
    too_hard: 'Too Hard',
    too_easy: 'Too Easy',
    confusing: 'Confusing',
    balanced: 'Balanced',
};

const SUGGESTION_TEMPLATES = {
    too_hard: 'Consider reducing difficulty or simplifying logic',
    too_easy: 'Increase difficulty to medium',
    confusing: 'Simplify wording or clarify options',
    balanced: '',
};

const shortQuestion = (value) => {
    if (!value) return '';
    return value.length > 95 ? `${value.slice(0, 95)}...` : value;
};

const formatPercent = (value) => `${Number(value || 0).toFixed(1)}%`;

const formatSeconds = (value) => `${Number(value || 0).toFixed(1)}s`;

const relativeTime = (input) => {
    if (!input) return 'Never';
    const timestamp = new Date(input).getTime();
    if (Number.isNaN(timestamp)) return 'Never';

    const delta = Date.now() - timestamp;
    const minute = 60 * 1000;
    const hour = 60 * minute;
    const day = 24 * hour;

    if (delta < minute) return 'just now';
    if (delta < hour) return `${Math.floor(delta / minute)}m ago`;
    if (delta < day) return `${Math.floor(delta / hour)}h ago`;
    return `${Math.floor(delta / day)}d ago`;
};

const transformQuestionList = (data) => ({
    total: data?.total ?? 0,
    page: data?.page ?? 1,
    page_size: data?.page_size ?? PAGE_SIZE,
    questions: (data?.questions || []).map((item) => ({
        id: item.id,
        question_text: item.question_text,
        question_preview: shortQuestion(item.question_text),
        difficulty: item.difficulty,
        attempts: Number(item.attempts || 0),
        accuracy: Number(item.accuracy || 0),
        avg_time: Number(item.avg_time || 0),
        status: item.status,
        needs_attention: Boolean(item.needs_attention),
    })),
});

const transformQuestionDetail = (data) => {
    const fallbackSuggestion = SUGGESTION_TEMPLATES[data?.insight_type] || '';
    return {
        ...data,
        attempts: Number(data?.attempts || 0),
        accuracy: Number(data?.accuracy || 0),
        avg_time: Number(data?.avg_time || 0),
        suggestion: data?.suggestion || fallbackSuggestion,
    };
};

const buildPageNumbers = (current, totalPages) => {
    const pages = [];
    const start = Math.max(1, current - 2);
    const end = Math.min(totalPages, start + 4);
    for (let value = start; value <= end; value += 1) {
        pages.push(value);
    }
    return pages;
};

const DifficultyPill = ({ value }) => {
    const styles = {
        easy: 'bg-green-100 text-green-700',
        medium: 'bg-amber-100 text-amber-700',
        hard: 'bg-red-100 text-red-700',
    };
    return (
        <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${styles[value] || 'bg-slate-100 text-slate-700'}`}>
            {value}
        </span>
    );
};

const StatusPill = ({ value }) => {
    const styles = {
        approved: 'bg-green-100 text-green-700',
        rejected: 'bg-slate-200 text-slate-700',
        needs_review: 'bg-amber-100 text-amber-700',
    };
    return (
        <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${styles[value] || 'bg-slate-100 text-slate-700'}`}>
            {value === 'needs_review' ? 'Needs Review' : value}
        </span>
    );
};

const accuracyCellClass = (accuracy) => {
    if (accuracy < 40) return 'text-red-600';
    if (accuracy > 85) return 'text-green-600';
    return 'text-amber-600';
};

const SortHeader = ({ label, active, direction, onClick }) => (
    <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center gap-1 ${active ? 'text-blue-600' : 'text-slate-500'} hover:text-blue-600 transition-colors`}
    >
        <span>{label}</span>
        <span className="text-xs">{active ? (direction === 'asc' ? '▲' : '▼') : '↕'}</span>
    </button>
);

export default function AdminReview() {
    const [filters, setFilters] = useState({
        difficulty: 'all',
        accuracy_range: 'all',
        status: 'all',
        search: '',
    });
    const [pagination, setPagination] = useState({ page: 1, page_size: PAGE_SIZE, total: 0 });
    const [sortConfig, setSortConfig] = useState({ sort_by: 'accuracy', sort_order: 'asc' });
    const [questions, setQuestions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedQuestionId, setSelectedQuestionId] = useState(null);
    const [drawerLoading, setDrawerLoading] = useState(false);
    const [drawerData, setDrawerData] = useState(null);
    const [feedbackText, setFeedbackText] = useState('');
    const [feedbackAction, setFeedbackAction] = useState('review');
    const [saveFeedbackLoading, setSaveFeedbackLoading] = useState(false);
    const [statusActionLoading, setStatusActionLoading] = useState(false);
    const [toast, setToast] = useState(null);

    const hasActiveFilters = useMemo(() => (
        filters.difficulty !== 'all'
        || filters.accuracy_range !== 'all'
        || filters.status !== 'all'
        || Boolean(filters.search.trim())
    ), [filters]);

    const totalPages = Math.max(1, Math.ceil(pagination.total / PAGE_SIZE));
    const pageNumbers = useMemo(() => buildPageNumbers(pagination.page, totalPages), [pagination.page, totalPages]);

    const fetchQuestions = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchAdminQuestions({
                page: pagination.page,
                page_size: PAGE_SIZE,
                difficulty: filters.difficulty,
                accuracy_range: filters.accuracy_range,
                status: filters.status,
                search: filters.search.trim(),
                sort_by: sortConfig.sort_by,
                sort_order: sortConfig.sort_order,
            });

            const transformed = transformQuestionList(data);
            setQuestions(transformed.questions);
            setPagination((prev) => ({ ...prev, total: transformed.total, page_size: transformed.page_size }));
        } catch (requestError) {
            console.error('Failed to fetch admin questions', requestError);
            setError('Failed to load questions. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [filters, pagination.page, sortConfig]);

    const fetchQuestionDetail = useCallback(async (questionId) => {
        setDrawerLoading(true);
        try {
            const data = await fetchAdminQuestionById(questionId);
            const transformed = transformQuestionDetail(data);
            setDrawerData(transformed);
            setFeedbackText(transformed.suggestion || '');
            setFeedbackAction('review');
        } catch {
            setToast({ type: 'error', message: 'Failed to load question details' });
            setSelectedQuestionId(null);
            setDrawerData(null);
        } finally {
            setDrawerLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchQuestions();
    }, [fetchQuestions]);

    useEffect(() => {
        if (!selectedQuestionId) return undefined;

        fetchQuestionDetail(selectedQuestionId);

        const onEscape = (event) => {
            if (event.key === 'Escape') {
                setSelectedQuestionId(null);
                setDrawerData(null);
            }
        };

        window.addEventListener('keydown', onEscape);
        return () => window.removeEventListener('keydown', onEscape);
    }, [selectedQuestionId, fetchQuestionDetail]);

    const handleFilterChange = (key, value) => {
        setPagination((prev) => ({ ...prev, page: 1 }));
        setFilters((prev) => ({ ...prev, [key]: value }));
    };

    const clearFilters = () => {
        setPagination((prev) => ({ ...prev, page: 1 }));
        setFilters({
            difficulty: 'all',
            accuracy_range: 'all',
            status: 'all',
            search: '',
        });
    };

    const handleSort = (column) => {
        setPagination((prev) => ({ ...prev, page: 1 }));
        setSortConfig((prev) => {
            if (prev.sort_by === column) {
                return {
                    ...prev,
                    sort_order: prev.sort_order === 'asc' ? 'desc' : 'asc',
                };
            }
            return {
                sort_by: column,
                sort_order: DEFAULT_SORTS[column] || 'asc',
            };
        });
    };

    const openDrawer = (questionId) => {
        setSelectedQuestionId(questionId);
    };

    const closeDrawer = () => {
        setSelectedQuestionId(null);
        setDrawerData(null);
    };

    const handleStatusUpdate = async (status) => {
        if (!selectedQuestionId) return;
        if (status === 'rejected') {
            const confirmed = window.confirm('Reject this question? It will be removed from active adaptive use.');
            if (!confirmed) return;
        }

        setStatusActionLoading(true);
        try {
            await updateAdminQuestionStatus(selectedQuestionId, status);
            setToast({
                type: 'success',
                message: status === 'approved'
                    ? 'Question is now included in adaptive test pool'
                    : 'Question removed from adaptive test pool',
            });
            await fetchQuestions();
            await fetchQuestionDetail(selectedQuestionId);
        } catch {
            setToast({ type: 'error', message: 'Failed to update status. Try again.' });
        } finally {
            setStatusActionLoading(false);
        }
    };

    const handleSaveFeedback = async () => {
        if (!selectedQuestionId) return;
        if (!feedbackText.trim()) {
            setToast({ type: 'error', message: 'Suggestion cannot be empty' });
            return;
        }

        setSaveFeedbackLoading(true);
        try {
            await saveAdminQuestionFeedback(selectedQuestionId, {
                suggestion: feedbackText.trim(),
                action: feedbackAction,
            });
            setToast({ type: 'success', message: 'Saved ✓' });
            await fetchQuestions();
            await fetchQuestionDetail(selectedQuestionId);
        } catch {
            setToast({ type: 'error', message: 'Failed. Try again' });
        } finally {
            setSaveFeedbackLoading(false);
        }
    };

    const showingStart = questions.length === 0 ? 0 : ((pagination.page - 1) * PAGE_SIZE) + 1;
    const showingEnd = Math.min(pagination.page * PAGE_SIZE, pagination.total);

    return (
        <AdminLayout>
            <div className="max-w-7xl mx-auto space-y-6 pr-0 lg:pr-[500px]">
                {toast && <Toast {...toast} onClose={() => setToast(null)} />}

                <div className="flex items-end justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Question Quality Review</h1>
                        <p className="text-slate-500 text-sm">Performance-driven controls for adaptive RL question pool</p>
                    </div>
                    <p className="text-sm text-slate-500">
                        Showing <span className="font-semibold text-slate-700">{questions.length}</span> of <span className="font-semibold text-slate-700">{pagination.total}</span> questions
                    </p>
                </div>

                <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                        <select
                            value={filters.difficulty}
                            onChange={(event) => handleFilterChange('difficulty', event.target.value)}
                            className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
                        >
                            <option value="all">Difficulty: All</option>
                            <option value="easy">Easy</option>
                            <option value="medium">Medium</option>
                            <option value="hard">Hard</option>
                        </select>

                        <select
                            value={filters.accuracy_range}
                            onChange={(event) => handleFilterChange('accuracy_range', event.target.value)}
                            className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
                        >
                            <option value="all">Accuracy: All</option>
                            <option value="too_easy">Too Easy (&gt;85%)</option>
                            <option value="balanced">Balanced (40-85%)</option>
                            <option value="too_hard">Too Hard (&lt;40%)</option>
                        </select>

                        <select
                            value={filters.status}
                            onChange={(event) => handleFilterChange('status', event.target.value)}
                            className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700"
                        >
                            <option value="all">Status: All</option>
                            <option value="approved">Approved</option>
                            <option value="rejected">Rejected</option>
                            <option value="needs_review">Needs Review</option>
                        </select>

                        <input
                            type="text"
                            value={filters.search}
                            onChange={(event) => handleFilterChange('search', event.target.value)}
                            placeholder="Search questions..."
                            className="h-10 rounded-xl border border-slate-200 px-3 text-sm text-slate-700 lg:col-span-2"
                        />
                    </div>
                    {/* Role badge will be shown per pool card in pool listing (admin table) */}
                    {hasActiveFilters && (
                        <button
                            type="button"
                            onClick={clearFilters}
                            className="mt-3 text-sm font-semibold text-blue-600 hover:text-blue-700"
                        >
                            Clear filters
                        </button>
                    )}
                </div>

                <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden text-sm">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider">
                                <th className="px-4 py-3">Question</th>
                                <th className="px-4 py-3">
                                    <SortHeader
                                        label="Difficulty"
                                        active={sortConfig.sort_by === 'difficulty'}
                                        direction={sortConfig.sort_order}
                                        onClick={() => handleSort('difficulty')}
                                    />
                                </th>
                                <th className="px-4 py-3">
                                    <SortHeader
                                        label="Attempts"
                                        active={sortConfig.sort_by === 'attempts'}
                                        direction={sortConfig.sort_order}
                                        onClick={() => handleSort('attempts')}
                                    />
                                </th>
                                <th className="px-4 py-3">
                                    <SortHeader
                                        label="Accuracy"
                                        active={sortConfig.sort_by === 'accuracy'}
                                        direction={sortConfig.sort_order}
                                        onClick={() => handleSort('accuracy')}
                                    />
                                </th>
                                <th className="px-4 py-3">
                                    <SortHeader
                                        label="Avg Time"
                                        active={sortConfig.sort_by === 'avg_time'}
                                        direction={sortConfig.sort_order}
                                        onClick={() => handleSort('avg_time')}
                                    />
                                </th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {loading && (
                                Array.from({ length: 6 }).map((_, index) => (
                                    <tr key={`skeleton-${index}`}>
                                        <td colSpan="7" className="px-4 py-4">
                                            <div className="h-7 rounded-lg bg-slate-100 animate-pulse" />
                                        </td>
                                    </tr>
                                ))
                            )}

                            {!loading && error && (
                                <tr>
                                    <td colSpan="7" className="px-6 py-10 text-center text-red-600">
                                        <p className="font-semibold">{error}</p>
                                        <button
                                            type="button"
                                            onClick={fetchQuestions}
                                            className="mt-2 text-sm font-semibold text-blue-600"
                                        >
                                            Retry
                                        </button>
                                    </td>
                                </tr>
                            )}

                            {!loading && !error && questions.length === 0 && !hasActiveFilters && (
                                <tr>
                                    <td colSpan="7" className="px-6 py-10 text-center text-slate-500">Add questions to get started</td>
                                </tr>
                            )}

                            {!loading && !error && questions.length === 0 && hasActiveFilters && (
                                <tr>
                                    <td colSpan="7" className="px-6 py-10 text-center text-slate-500">
                                        <p>No questions match your filters</p>
                                        <button
                                            type="button"
                                            onClick={clearFilters}
                                            className="mt-2 text-sm font-semibold text-blue-600"
                                        >
                                            Clear filters
                                        </button>
                                    </td>
                                </tr>
                            )}

                            {!loading && !error && questions.map((question) => (
                                <tr key={question.id} className="hover:bg-slate-50/70 transition-colors">
                                    <td className="px-4 py-4 text-slate-700 font-medium">
                                        <div className="flex items-center gap-2">
                                            <span>{question.question_preview}</span>
                                            {question.needs_attention && (
                                                <span className="text-[10px] font-semibold text-amber-700 bg-amber-100 rounded-full px-2 py-1">⚠ Needs Attention</span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-4 py-4"><DifficultyPill value={question.difficulty} /></td>
                                    <td className="px-4 py-4 text-slate-700">{question.attempts}</td>
                                    <td className={`px-4 py-4 font-semibold ${question.attempts === 0 ? 'text-slate-700' : accuracyCellClass(question.accuracy)}`}>{question.attempts === 0 ? '-' : formatPercent(question.accuracy)}</td>
                                    <td className="px-4 py-4 text-slate-700">{question.attempts === 0 ? '-' : formatSeconds(question.avg_time)}</td>
                                    <td className="px-4 py-4"><StatusPill value={question.status} /></td>
                                    <td className="px-4 py-4 text-right">
                                        <button
                                            type="button"
                                            onClick={() => openDrawer(question.id)}
                                            className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700"
                                        >
                                            Review
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {pagination.total >= PAGE_SIZE && (
                    <div className="flex items-center justify-between bg-white border border-slate-200 rounded-xl p-3">
                        <p className="text-sm text-slate-500">Showing {showingStart}-{showingEnd} of {pagination.total} questions</p>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setPagination((prev) => ({ ...prev, page: Math.max(1, prev.page - 1) }))}
                                disabled={pagination.page === 1}
                                className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 disabled:opacity-50"
                            >
                                Previous
                            </button>
                            {pageNumbers.map((pageNum) => (
                                <button
                                    key={pageNum}
                                    type="button"
                                    onClick={() => setPagination((prev) => ({ ...prev, page: pageNum }))}
                                    className={`w-8 h-8 rounded-lg text-sm font-semibold ${pagination.page === pageNum ? 'bg-blue-600 text-white' : 'border border-slate-200 text-slate-700'}`}
                                >
                                    {pageNum}
                                </button>
                            ))}
                            <button
                                type="button"
                                onClick={() => setPagination((prev) => ({ ...prev, page: Math.min(totalPages, prev.page + 1) }))}
                                disabled={pagination.page >= totalPages}
                                className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 disabled:opacity-50"
                            >
                                Next
                            </button>
                        </div>
                    </div>
                )}

                {selectedQuestionId && (
                    <div className="fixed inset-0 z-40 pointer-events-none">
                        <div className="absolute inset-0 bg-black/10" onClick={closeDrawer} />
                        <aside className="absolute right-0 top-0 h-full w-full max-w-[480px] bg-white border-l border-slate-200 shadow-2xl pointer-events-auto overflow-y-auto">
                            <div className="sticky top-0 bg-white border-b border-slate-200 px-5 py-4 flex items-center justify-between">
                                <h2 className="text-lg font-bold text-slate-900">Question Review</h2>
                                <button type="button" onClick={closeDrawer} className="text-slate-500 hover:text-slate-700 text-xl">×</button>
                            </div>

                            {drawerLoading || !drawerData ? (
                                <div className="p-5 space-y-4">
                                    {Array.from({ length: 7 }).map((_, index) => (
                                        <div key={`drawer-skeleton-${index}`} className="h-10 rounded-lg bg-slate-100 animate-pulse" />
                                    ))}
                                </div>
                            ) : (
                                <div className="p-5 space-y-6 text-sm">
                                    <section className="space-y-3">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Question</h3>
                                        <p className="text-slate-800 leading-relaxed">{drawerData.question_text}</p>
                                        <ul className="space-y-1 text-slate-700">
                                            {drawerData.options?.map((option, index) => (
                                                <li key={`${option}-${index}`}>{String.fromCharCode(65 + index)}. {option}</li>
                                            ))}
                                        </ul>
                                        <div className="flex items-center gap-2 text-slate-700">
                                            <span className="font-semibold">Correct:</span>
                                            <span>{drawerData.correct_option}</span>
                                            <DifficultyPill value={drawerData.difficulty} />
                                        </div>
                                    </section>

                                    <section className="space-y-2">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Performance</h3>
                                        {drawerData.attempts === 0 ? (
                                            <p className="text-slate-500">This question hasn't been attempted yet</p>
                                        ) : (
                                            <div className="grid grid-cols-3 gap-2">
                                                <div className="rounded-lg border border-slate-200 p-2">
                                                    <p className="text-slate-500 text-xs">Attempts</p>
                                                    <p className="font-bold text-slate-800">{drawerData.attempts}</p>
                                                </div>
                                                <div className="rounded-lg border border-slate-200 p-2">
                                                    <p className="text-slate-500 text-xs">Accuracy</p>
                                                    <p className="font-bold text-slate-800">{formatPercent(drawerData.accuracy)}</p>
                                                </div>
                                                <div className="rounded-lg border border-slate-200 p-2">
                                                    <p className="text-slate-500 text-xs">Avg Time</p>
                                                    <p className="font-bold text-slate-800">{formatSeconds(drawerData.avg_time)}</p>
                                                </div>
                                            </div>
                                        )}
                                    </section>

                                    <section className="space-y-2">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">System Insight</h3>
                                        <div className="flex items-center gap-2">
                                            <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${INSIGHT_BADGE_STYLES[drawerData.insight_type]}`}>
                                                {INSIGHT_LABELS[drawerData.insight_type]}
                                            </span>
                                            <p className="text-slate-700">{drawerData.insight}</p>
                                        </div>
                                    </section>

                                    <section className="space-y-2">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">System Recommendation</h3>
                                        <p className="text-slate-700 font-semibold">
                                            {drawerData.recommendation === 'approve' ? 'Approve this question' : 'Review this question'}
                                        </p>
                                    </section>

                                    <section className="space-y-2">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">RL Engine Usage</h3>
                                        <div className="space-y-1 text-slate-700">
                                            <p>Used in adaptive testing: <span className="font-semibold">{drawerData.rl_data?.in_active_pool ? 'Yes' : 'No'}</span></p>
                                            <p>Times Served: <span className="font-semibold">{drawerData.rl_data?.times_served ?? 0}</span></p>
                                            <p>Last Used: <span className="font-semibold">{relativeTime(drawerData.rl_data?.last_served)}</span></p>
                                            <p>Avg accuracy when served: <span className="font-semibold">{formatPercent(drawerData.rl_data?.avg_accuracy_when_served ?? 0)}</span></p>
                                        </div>
                                    </section>

                                    <section className="space-y-2" id="suggestion-box">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Suggestion Box</h3>
                                        <textarea
                                            rows={3}
                                            value={feedbackText}
                                            onChange={(event) => setFeedbackText(event.target.value)}
                                            className="w-full rounded-xl border border-slate-200 p-3 text-sm text-slate-700 resize-none"
                                        />
                                        <div className="flex flex-wrap gap-2">
                                            <button
                                                type="button"
                                                onClick={() => setFeedbackText(SUGGESTION_TEMPLATES.too_easy)}
                                                className="px-2 py-1 rounded-full border border-slate-200 text-xs font-semibold text-slate-600"
                                            >
                                                Too Easy
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => setFeedbackText(SUGGESTION_TEMPLATES.too_hard)}
                                                className="px-2 py-1 rounded-full border border-slate-200 text-xs font-semibold text-slate-600"
                                            >
                                                Too Hard
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => setFeedbackText(SUGGESTION_TEMPLATES.confusing)}
                                                className="px-2 py-1 rounded-full border border-slate-200 text-xs font-semibold text-slate-600"
                                            >
                                                Confusing
                                            </button>
                                        </div>
                                        <button
                                            type="button"
                                            disabled={saveFeedbackLoading}
                                            onClick={handleSaveFeedback}
                                            className="px-4 py-2 rounded-lg bg-blue-600 text-white font-semibold text-sm disabled:opacity-60"
                                        >
                                            {saveFeedbackLoading ? 'Saving...' : 'Save Feedback'}
                                        </button>
                                    </section>

                                    <section className="space-y-2 pb-4">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Actions</h3>
                                        <div className="flex flex-wrap gap-2">
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setFeedbackAction('approve');
                                                    handleStatusUpdate('approved');
                                                }}
                                                disabled={statusActionLoading || drawerData.status === 'approved'}
                                                className="px-3 py-2 rounded-lg bg-green-600 text-white text-xs font-semibold disabled:opacity-50"
                                            >
                                                Approve
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setFeedbackAction('reject');
                                                    handleStatusUpdate('rejected');
                                                }}
                                                disabled={statusActionLoading || drawerData.status === 'rejected'}
                                                className="px-3 py-2 rounded-lg bg-red-600 text-white text-xs font-semibold disabled:opacity-50"
                                            >
                                                Reject
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setFeedbackAction('review');
                                                    document.getElementById('suggestion-box')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                                }}
                                                className="px-3 py-2 rounded-lg border border-amber-300 text-amber-700 text-xs font-semibold"
                                            >
                                                Suggest Improvement
                                            </button>
                                        </div>
                                    </section>
                                </div>
                            )}
                        </aside>
                    </div>
                )}
            </div>
        </AdminLayout>
    );
}
