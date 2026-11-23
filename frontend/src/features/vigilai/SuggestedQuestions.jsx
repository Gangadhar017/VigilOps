import React from 'react';

export const DEFAULT_SUGGESTIONS = [
  'Why is my application unhealthy?',
  'Show my authorized open incidents.',
  'What does SEC-001 mean?',
  'How does the remediation approval process work?',
];

export function SuggestedQuestions({ questions = DEFAULT_SUGGESTIONS, onSelect, disabled }) {
  if (!questions?.length) return null;
  return (
    <div>
      <p className="eyebrow mb-2">Suggested questions</p>
      <div className="flex flex-col gap-1.5">
        {questions.map((question) => (
          <button
            key={question}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(question)}
            className="group flex items-center justify-between gap-2 rounded-md border border-line bg-surface px-2.5 py-1.5 text-left text-xs text-content transition-colors hover:border-content/35 hover:bg-raised/60 disabled:opacity-50"
          >
            {question}
            <span className="font-mono text-muted transition-colors group-hover:text-brand" aria-hidden="true">
              →
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default SuggestedQuestions;
