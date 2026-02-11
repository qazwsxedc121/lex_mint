const CODE_PLACEHOLDER_PREFIX = '@@CODE_BLOCK_';

interface ProtectedCodeResult {
  text: string;
  blocks: string[];
}

const protectCodeSegments = (markdown: string): ProtectedCodeResult => {
  const blocks: string[] = [];
  const text = markdown.replace(/```[\s\S]*?```|`[^`\n]*`/g, (match) => {
    const token = `${CODE_PLACEHOLDER_PREFIX}${blocks.length}@@`;
    blocks.push(match);
    return token;
  });

  return { text, blocks };
};

const restoreCodeSegments = (markdown: string, blocks: string[]): string => {
  return markdown.replace(/@@CODE_BLOCK_(\d+)@@/g, (_match, indexText: string) => {
    const index = Number.parseInt(indexText, 10);
    return blocks[index] ?? _match;
  });
};

export const normalizeMathDelimiters = (markdown: string): string => {
  if (!markdown || !/\\\(|\\\[/.test(markdown)) {
    return markdown;
  }

  const { text, blocks } = protectCodeSegments(markdown);
  const normalized = text
    .replace(/\\\(([\s\S]+?)\\\)/g, (_match, inner: string) => `$${inner}$`)
    .replace(/\\\[([\s\S]+?)\\\]/g, (_match, inner: string) => `\n$$\n${inner.trim()}\n$$\n`);

  return restoreCodeSegments(normalized, blocks);
};
