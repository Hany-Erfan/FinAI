/**
 * Utility functions for processing and normalizing markdown content
 */

/**
 * Normalizes markdown content by fixing common formatting issues
 * @param markdown - Raw markdown string
 * @returns Cleaned and properly formatted markdown
 */
export const normalizeMarkdown = (markdown: string): string => {
  if (!markdown) return '';

  let normalized = markdown;

  // Strip unsafe or styling-only HTML (react-markdown escapes it by default, but we want clean text)
  // Remove <span ...> and </span> while preserving inner text
  normalized = normalized.replace(/<\s*span[^>]*>/gi, '').replace(/<\s*\/\s*span\s*>/gi, '');
  // Convert simple <br> and <br/> to newlines
  normalized = normalized.replace(/<\s*br\s*\/?\s*>/gi, '\n');
  // Remove other unsafe inline styles/tags commonly emitted by LLMs (keep content)
  normalized = normalized.replace(/<\s*\/?\s*(font|b|i|u)\b[^>]*>/gi, '');

  // Remove excessive leading whitespace that causes code block issues
  normalized = normalized.replace(/^[ \t]+/gm, '');

  // Fix list items that might have been indented incorrectly
  normalized = normalized.replace(/^[ \t]*-[ \t]+/gm, '- ');
  normalized = normalized.replace(/^[ \t]*\*[ \t]+/gm, '- ');

  // Fix numbered lists
  normalized = normalized.replace(/^[ \t]*(\d+)\.[ \t]+/gm, '$1. ');

  // Fix headers that might have extra spaces
  normalized = normalized.replace(/^[ \t]*(#{1,6})[ \t]+/gm, '$1 ');

  // Fix table formatting - ensure proper spacing
  normalized = normalized.replace(/\|[ \t]*([^|]+)[ \t]*\|/g, '| $1 |');

  // Remove excessive blank lines (more than 2 consecutive)
  normalized = normalized.replace(/\n{3,}/g, '\n\n');

  // Trim leading and trailing whitespace
  normalized = normalized.trim();

  return normalized;
};

/**
 * Extracts and cleans the main content from a tender response
 * @param tenderResponse - The full tender response object
 * @returns Cleaned markdown content
 */
export const extractTenderContent = (tenderResponse: any): string => {
  if (!tenderResponse?.data?.response) {
    return 'No tender analysis content available.';
  }

  const rawContent = tenderResponse.data.response;
  return normalizeMarkdown(rawContent);
};

/**
 * Try to parse a structured tender payload from a stringified response.
 */
const parseStructuredTender = (response: string) => {
  if (typeof response !== 'string') return null;
  try {
    const parsed = JSON.parse(response);
    if (parsed && typeof parsed === 'object' && parsed.tender && Array.isArray(parsed.vendors)) {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
};

/**
 * Processes tender data to ensure consistent formatting
 * - Normalizes markdown
 * - Extracts structured tender data when the response is a JSON string
 * @param tenderData - Raw tender data from any source
 * @returns Processed tender data with normalized markdown and optional structured payload
 */
export const processTenderData = (tenderData: any): any => {
  if (!tenderData) return tenderData;

  // Create a deep copy to avoid mutating the original
  const processed = JSON.parse(JSON.stringify(tenderData));

  const rawResponse = processed.data?.response;

  // Attempt to parse structured tender JSON if the response is JSON-encoded
  if (!processed.data?.structured && typeof rawResponse === 'string') {
    const parsed = parseStructuredTender(rawResponse);
    if (parsed) {
      processed.data.structured = parsed;
      processed.data.response = parsed.tender ? normalizeMarkdown(parsed.tender) : normalizeMarkdown(rawResponse);
      return processed;
    }
  }

  // Normalize the main response content
  if (processed.data?.response) {
    processed.data.response = normalizeMarkdown(processed.data.response);
  }

  return processed;
};
