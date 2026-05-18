import { MCQOption } from "./MCQOption";

interface MCQQuestionProps {
  questionNumber: number;
  totalQuestions: number;
  questionText: string;
  options: { id: string; text: string }[];
  selectedOptionId?: string;
  onOptionSelect: (optionId: string) => void;
}

export function MCQQuestion({
  questionNumber,
  totalQuestions,
  questionText,
  options,
  selectedOptionId,
  onOptionSelect,
}: MCQQuestionProps) {
  return (
    <div className="flex flex-col gap-8 rounded-2xl bg-white p-8 shadow-sm border border-gray-100 h-full overflow-y-auto">
      
      <div className="flex flex-col gap-4">
        <span className="text-sm font-bold uppercase tracking-wider text-muted-foreground font-heading">
          Question {questionNumber} of {totalQuestions}
        </span>
        <h2 className="text-2xl font-semibold leading-relaxed text-heading font-sans">
          {questionText}
        </h2>
      </div>

      <div className="flex flex-col gap-3">
        {options.map((option) => (
          <MCQOption
            key={option.id}
            id={option.id}
            text={option.text}
            isSelected={selectedOptionId === option.id}
            onSelect={() => onOptionSelect(option.id)}
          />
        ))}
      </div>
    </div>
  );
}
