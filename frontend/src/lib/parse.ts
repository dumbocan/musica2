import { API_BASE_URL } from '@/lib/api';

const normalizeSerializedArray = (raw: string) =>
  raw
    .replace(/\bNone\b/g, 'null')
    .replace(/\bTrue\b/g, 'true')
    .replace(/\bFalse\b/g, 'false')
    .replace(/'/g, '"');

const tryParseArray = (value: string): unknown[] => {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

export const parseStoredJsonArray = (raw?: string | null): unknown[] => {
  if (!raw) return [];
  const trimmed = raw.trim();
  if (!trimmed) return [];
  const first = tryParseArray(trimmed);
  if (first.length) return first;
  const normalized = normalizeSerializedArray(trimmed);
  if (normalized === trimmed) return [];
  return tryParseArray(normalized);
};

export const parseStoredStringArray = (raw?: string | null): string[] =>
  parseStoredJsonArray(raw)
    .map((entry) => (typeof entry === 'string' ? entry.trim() : ''))
    .filter((entry) => entry.length > 0);

export const parseStoredImageUrls = (raw?: string | null): string[] =>
  parseStoredJsonArray(raw)
    .map((entry) => {
      if (typeof entry === 'string') return entry.trim();
      if (entry && typeof entry === 'object') {
        const typed = entry as { url?: unknown; '#text'?: unknown };
        const value =
          typeof typed.url === 'string'
            ? typed.url
            : typeof typed['#text'] === 'string'
              ? typed['#text']
              : '';
        return value.trim();
      }
      return '';
    })
    .filter((entry) => entry.length > 0);

export const resolveProxyImageUrl = (candidate: string, size: number): string | null => {
  const trimmed = candidate.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('/images/proxy')) {
    return `${API_BASE_URL}${trimmed}`;
  }
  return `${API_BASE_URL}/images/proxy?url=${encodeURIComponent(trimmed)}&size=${size}`;
};
