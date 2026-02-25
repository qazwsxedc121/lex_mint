interface SanitizeSvgResult {
  sanitized: string;
  error?: string;
}

const JAVASCRIPT_PROTOCOL_PATTERN = /^\s*javascript:/i;
const XLINK_NAMESPACE = 'http://www.w3.org/1999/xlink';

function stripDangerousAttributes(element: Element): void {
  const attributes = Array.from(element.attributes);
  for (const attribute of attributes) {
    const attrName = attribute.name.toLowerCase();
    if (attrName.startsWith('on')) {
      element.removeAttribute(attribute.name);
      continue;
    }

    if ((attrName === 'href' || attrName === 'xlink:href') && JAVASCRIPT_PROTOCOL_PATTERN.test(attribute.value)) {
      element.removeAttribute(attribute.name);
    }
  }

  const hrefValue = element.getAttribute('href');
  if (hrefValue && JAVASCRIPT_PROTOCOL_PATTERN.test(hrefValue)) {
    element.removeAttribute('href');
  }

  const xlinkHrefValue = element.getAttributeNS(XLINK_NAMESPACE, 'href');
  if (xlinkHrefValue && JAVASCRIPT_PROTOCOL_PATTERN.test(xlinkHrefValue)) {
    element.removeAttributeNS(XLINK_NAMESPACE, 'href');
  }
}

export function sanitizeSvg(svgText: string): SanitizeSvgResult {
  const source = svgText.trim();
  if (!source) {
    return { sanitized: '', error: 'Empty SVG content' };
  }

  if (typeof DOMParser === 'undefined' || typeof XMLSerializer === 'undefined') {
    return { sanitized: '', error: 'SVG rendering is not available in this environment' };
  }

  const parser = new DOMParser();
  const parsedDocument = parser.parseFromString(source, 'image/svg+xml');
  if (parsedDocument.querySelector('parsererror')) {
    return { sanitized: '', error: 'Invalid SVG markup' };
  }

  const svgRoot = parsedDocument.documentElement;
  if (!svgRoot || svgRoot.tagName.toLowerCase() !== 'svg') {
    return { sanitized: '', error: 'Missing SVG root element' };
  }

  const scriptNodes = Array.from(svgRoot.getElementsByTagName('script'));
  for (const scriptNode of scriptNodes) {
    scriptNode.remove();
  }

  const allElements = [svgRoot, ...Array.from(svgRoot.querySelectorAll('*'))];
  for (const element of allElements) {
    stripDangerousAttributes(element);
  }

  const serializer = new XMLSerializer();
  return { sanitized: serializer.serializeToString(svgRoot) };
}
