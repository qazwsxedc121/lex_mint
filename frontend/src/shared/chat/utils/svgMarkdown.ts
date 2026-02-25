const SVG_START_PATTERN = /^\s*<svg\b/i;
const SVG_END_TAG = '</svg>';
const FENCE_PATTERN = /^ {0,3}(`{3,}|~{3,})/;

function getFenceMarker(line: string): string | null {
  const match = line.match(FENCE_PATTERN);
  return match ? match[1][0] : null;
}

function isFenceCloser(line: string, marker: string): boolean {
  const closerPattern = marker === '`' ? /^ {0,3}`{3,}/ : /^ {0,3}~{3,}/;
  return closerPattern.test(line);
}

export function extractSvgBlocks(markdown: string): string {
  if (!markdown || !/<svg/i.test(markdown)) {
    return markdown;
  }

  const normalized = markdown.replace(/\r\n/g, '\n');
  const hasTrailingNewline = normalized.endsWith('\n');
  const lines = normalized.split('\n');
  const outputLines: string[] = [];
  let activeFenceMarker: string | null = null;

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const currentLine = lines[lineIndex];
    const fenceMarker = getFenceMarker(currentLine);

    if (activeFenceMarker) {
      outputLines.push(currentLine);
      if (fenceMarker && isFenceCloser(currentLine, activeFenceMarker)) {
        activeFenceMarker = null;
      }
      continue;
    }

    if (fenceMarker) {
      activeFenceMarker = fenceMarker;
      outputLines.push(currentLine);
      continue;
    }

    if (!SVG_START_PATTERN.test(currentLine)) {
      outputLines.push(currentLine);
      continue;
    }

    const svgBlockLines: string[] = [];
    let closeLineIndex = -1;
    let closeTagOffset = -1;

    for (let scanIndex = lineIndex; scanIndex < lines.length; scanIndex += 1) {
      const scanLine = lines[scanIndex];
      svgBlockLines.push(scanLine);
      const closeOffset = scanLine.toLowerCase().indexOf(SVG_END_TAG);
      if (closeOffset >= 0) {
        closeLineIndex = scanIndex;
        closeTagOffset = closeOffset;
        break;
      }
    }

    if (closeLineIndex < 0) {
      outputLines.push(currentLine);
      continue;
    }

    const closeLine = lines[closeLineIndex];
    const trailingText = closeLine.slice(closeTagOffset + SVG_END_TAG.length);
    if (trailingText.trim()) {
      outputLines.push(currentLine);
      continue;
    }

    const svgText = svgBlockLines.join('\n').trim();
    outputLines.push('```svg');
    outputLines.push(svgText);
    outputLines.push('```');
    lineIndex = closeLineIndex;
  }

  const result = outputLines.join('\n');
  if (hasTrailingNewline && !result.endsWith('\n')) {
    return `${result}\n`;
  }
  return result;
}
