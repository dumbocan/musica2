/**
 * Simple smoke test for genre filtering logic used in SearchPage.
 * Run with: node frontend/scripts/genreFilterTest.js
 */

const genreKeywords = (q) => {
  const ql = q.toLowerCase();
  if (ql.includes('hip hop') || ql.includes('hiphop') || ql.includes('rap')) {
    return ['hip hop', 'hip-hop', 'rap', 'trap', 'boom bap', 'gangsta'];
  }
  if (ql.includes('rock')) return ['rock', 'alt', 'indie'];
  if (ql.includes('metal')) return ['metal', 'heavy', 'death'];
  if (ql.includes('pop')) return ['pop', 'dance', 'k-pop'];
  return [];
};

const matchesGenre = (artist, genreKeys, extraTags = []) => {
  if (genreKeys.length === 0) return true;
  const disallow = ['tamil', 'kollywood', 'tollywood', 'telugu', 'k-pop', 'kpop'];
  const genresStr = (artist.genres || []).map((g) => g.toLowerCase());
  const tagsStr = extraTags.map((t) => t.toLowerCase());
  const pool = [...genresStr, ...tagsStr];
  if (pool.length === 0) return false;
  const hasBad = pool.some((g) => disallow.some((b) => g.includes(b)));
  if (hasBad) return false;
  return genreKeys.some((gk) => pool.some((g) => g.includes(gk)));
};

const q = 'hip hop';
const gkeys = genreKeywords(q);

const artists = [
  { name: 'Eminem', genres: ['rap', 'hip hop'] },
  { name: 'Dead Prez', genres: ['east coast hip hop', 'old school hip hop', 'hardcore hip hop'] },
  { name: 'Hiphop Tamizha', genres: ['tamil hip hop', 'tamil pop'] },
  { name: 'Anirudh Ravichander', genres: ['tamil pop', 'kollywood'] },
  { name: 'A.R. Rahman', genres: ['tamil pop', 'kollywood'] },
  { name: 'Sid Sriram', genres: ['tollywood', 'telugu pop'] },
  { name: 'MF DOOM', genres: ['hip hop', 'underground hip hop'] },
];

console.log(`Testing query "${q}" with keywords:`, gkeys);
artists.forEach((a) => {
  const ok = matchesGenre(a, gkeys);
  console.log(`${ok ? 'PASS ' : 'FAIL '}${a.name} -> ${a.genres.join(', ')}`);
});

// Stats
const passCount = artists.filter((a) => matchesGenre(a, gkeys)).length;
console.log(`\nSummary: ${passCount} of ${artists.length} artists matched hip hop filter.`);
