const DIFFICULTY_STYLES = {
    easy: 'bg-[var(--color-success)]/10 text-[var(--color-success)] border-[var(--color-success)]/20',
    medium: 'bg-[var(--color-warning)]/10 text-[var(--color-warning)] border-[var(--color-warning)]/20',
    hard: 'bg-[var(--color-danger)]/10 text-[var(--color-danger)] border-[var(--color-danger)]/20',
};

export default function QuestionCard({
    question,
    selectedOption,
    onOptionSelect,
    disabled,
}) {
    if (!question) return null;

    const diffStyle = DIFFICULTY_STYLES[question.difficulty] || DIFFICULTY_STYLES.medium;

    const optionKeys = ['A', 'B', 'C', 'D'];

    return (
        <div className="rounded-[12px] border border-[var(--color-border)] bg-white p-8 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.05)]">
            {/* Header */}
            <div className="mb-6 flex items-center justify-between">
                <span className="text-sm font-medium tracking-wide text-[var(--color-text-secondary)]">
                    Question {question.question_id}
                </span>
                <span
                    aria-label={`Question difficulty: ${question.difficulty}`}
                    className={`rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wider ${diffStyle}`}
                >
                    {question.difficulty}
                </span>
            </div>

            {/* Question text */}
            <h2 className="mb-8 text-xl font-semibold leading-relaxed text-[var(--color-text-primary)]">
                {question.question_text}
            </h2>

            {/* Options */}
            <div className="space-y-3">
                {optionKeys.map((key) => {
                    const optionText = question.options?.[key];
                    if (!optionText) return null;

                    const isSelected = selectedOption === key;

                    return (
                        <button
                            key={key}
                            aria-label={`Option ${key}: ${optionText}`}
                            onClick={() => !disabled && onOptionSelect(key)}
                            disabled={disabled}
                            className={`flex w-full items-center gap-4 rounded-[8px] border p-4 text-left transition-all duration-200 ${isSelected
                                ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/5 text-[var(--color-accent)] shadow-[0_2px_8px_-2px_rgba(108,99,255,0.2)]'
                                : 'border-[#E5E7EB] bg-white text-[var(--color-text-secondary)] hover:border-[#D1D5DB] hover:shadow-sm hover:-translate-y-[1px]'
                                } ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                        >
                            <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-[1.5px] transition-colors ${isSelected
                                ? 'border-[var(--color-accent)] bg-[var(--color-accent)]'
                                : 'border-[#9CA3AF] bg-transparent'
                                }`}>
                                {isSelected && <div className="h-2 w-2 rounded-full bg-white" />}
                            </span>
                            <span className="text-[15px] font-semibold tracking-wide w-4">{key}</span>
                            <span className="text-[15px] ml-2">{optionText}</span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
