type NormalizeImageUrlOptions = {
  candidate: string;
  size: number;
  token?: string | null;
  apiBaseUrl: string;
};

const applySizeAndToken = (path: string, size: number, token?: string | null) => {
  const [base, qs] = path.split('?');
  const params = new URLSearchParams(qs ?? '');
  params.set('size', String(size));
  if (token) {
    params.set('token', token);
  }
  const query = params.toString();
  return query ? `${base}?${query}` : base;
};

export const normalizeImageUrl = ({ candidate, size, token, apiBaseUrl }: NormalizeImageUrlOptions) => {
  if (!candidate) return '';
  if (candidate.startsWith('/images/proxy') || candidate.startsWith('/images/entity')) {
    return `${apiBaseUrl}${applySizeAndToken(candidate, size, token)}`;
  }
  if (candidate.startsWith('/')) {
    return `${apiBaseUrl}${candidate}`;
  }
  const params = new URLSearchParams({ url: candidate, size: String(size) });
  if (token) {
    params.set('token', token);
  }
  return `${apiBaseUrl}/images/proxy?${params.toString()}`;
};
