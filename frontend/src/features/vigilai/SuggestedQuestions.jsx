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
      <p className="mb-1.5 text-xs font-medium text-muted">Suggested questions</p>
      <div className="flex flex-wrap gap-1.5">
        {questions.map((question) => (
          <button
            key={question}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(question)}
            className="rounded-full border border-line bg-surface px-2.5 py-1 text-left text-xs text-content transition-colors hover:border-brand hover:text-brand disabled:opacity-50"
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}

export default SuggestedQuestions;
