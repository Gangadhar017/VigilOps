import React from 'react';

/**
 * Renders assistant text safely.
 *
 * Model output is untrusted, so it is NEVER inserted as HTML. The text is
 * split into plain React nodes; only three inline patterns are recognised:
 * **bold**, `code` and "- " bullet lines. Anything that looks like markup is
 * displayed literally.
 */
function renderInline(text, keyPrefix) {
  const nodes = [];
  const pattern = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/g;
  let last = 0;
  let match;
  let index = 0;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith('**')) {
      nodes.push(<strong key={`${keyPrefix}-b${index}`}>{token.slice(2, -2)}</strong>);
    } else {
      nodes.push(
        <code key={`${keyPrefix}-c${index}`} className="rounded bg-raised px-1 py-0.5 text-[0.85em]">
          {token.slice(1, -1)}
        </code>,
      );
    }
    last = match.index + token.length;
    index += 1;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function SafeText({ text }) {
  const blocks = [];
  let bullets = [];
  const flush = () => {
    if (bullets.length) {
      blocks.push({ type: 'list', items: bullets });
      bullets = [];
    }
  };
  String(text ?? '')
    .split('\n')
    .forEach((line) => {
      const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
      if (bullet) {
        bullets.push({ text: bullet[1], nested: /^\s{2,}/.test(line) });
      } else {
        flush();
        if (line.trim()) blocks.push({ type: 'paragraph', text: line });
      }
    });
  flush();

  return (
    <div className="space-y-2 break-words">
      {blocks.map((block, blockIndex) =>
        block.type === 'list' ? (
          <ul key={blockIndex} className="list-disc space-y-1 pl-5">
            {block.items.map((item, itemIndex) => (
              <li key={itemIndex} className={item.nested ? 'ml-4' : ''}>
                {renderInline(item.text, `${blockIndex}-${itemIndex}`)}
              </li>
            ))}
          </ul>
        ) : (
          <p key={blockIndex}>{renderInline(block.text, `${blockIndex}`)}</p>
        ),
      )}
    </div>
  );
}

export default SafeText;
