import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { audio2Api, API_BASE_URL } from '@/lib/api';
import type { Artist as LocalArtist } from '@/types/api';

type AlbumImage = { url: string };
type Album = {
  id: string;
  name: string;
  release_date?: string;
  total_tracks?: number;
  images?: AlbumImage[];
  youtube_links_available?: number;
  album_group?: string;
  album_type?: string;
};
type ArtistInfo = {
  spotify?: {
    id?: string;
    name?: string;
    images?: AlbumImage[];
    followers?: { total?: number };
    popularity?: number;
    genres?: string[];
  };
  lastfm?: {
    summary?: string;
    content?: string;
    stats?: { listeners?: string | number; playcount?: string | number };
    tags?: Array<{ name?: string }>;
  };
};

export function ArtistDiscographyPage() {
  const { spotifyId } = useParams<{ spotifyId: string }>();
  const navigate = useNavigate();
  const [artist, setArtist] = useState<ArtistInfo | null>(null);
  const [albums, setAlbums] = useState<Album[]>([]);
  const [localArtist, setLocalArtist] = useState<LocalArtist | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFullBio, setShowFullBio] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!spotifyId) return;
      setLoading(true);
      setError(null);
      try {
        const [artistRes, albumsRes, localRes] = await Promise.all([
          audio2Api.getArtistInfo(spotifyId),
          audio2Api.getArtistAlbums(spotifyId, { refresh: true }),
          audio2Api.getLocalArtistBySpotifyId(spotifyId).catch(() => ({ data: null })),
        ]);
        setArtist(artistRes.data);
        setAlbums(albumsRes.data || []);
        setLocalArtist(localRes.data || null);
      } catch (err: unknown) {
        const message =
          err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
            ? (err.response.data as { detail: string }).detail
            : err instanceof Error
              ? err.message
              : 'Error cargando discografía';
        setError(message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [spotifyId]);

  const bioHtml = artist?.lastfm?.content || artist?.lastfm?.summary || '';
  const artistName = artist?.spotify?.name || 'Artista';
  const bioParagraphs = useMemo(() => {
    if (!bioHtml) return [];
    const text = bioHtml
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/p>/gi, '\n')
      .replace(/<[^>]+>/g, '');
    return text
      .split(/\n\s*\n+/)
      .map((p) => p.trim())
      .filter(Boolean);
  }, [bioHtml]);
  const bioToShow = showFullBio ? bioParagraphs : bioParagraphs.slice(0, 3);

  const sortedAlbums = useMemo(() => {
    return [...albums].sort((a, b) => {
      const left = a.release_date || '';
      const right = b.release_date || '';
      if (left === right) return 0;
      return left < right ? 1 : -1;
    });
  }, [albums]);

  const { studioAlbums, singles, compilations } = useMemo(() => {
    const items = {
      studioAlbums: [] as Album[],
      singles: [] as Album[],
      compilations: [] as Album[],
    };
    for (const album of sortedAlbums) {
      const group = album.album_group || album.album_type;
      if (group === 'single') {
        items.singles.push(album);
        continue;
      }
      if (group === 'compilation') {
        items.compilations.push(album);
        continue;
      }
      if (group === 'album') {
        items.studioAlbums.push(album);
        continue;
      }
      const totalTracks = typeof album.total_tracks === 'number' ? album.total_tracks : null;
      if (totalTracks !== null && totalTracks <= 6) {
        items.singles.push(album);
      } else {
        items.studioAlbums.push(album);
      }
    }
    return items;
  }, [sortedAlbums]);

  if (!spotifyId) return <div className="card">Artista no especificado.</div>;
  if (loading) return <div className="card">Cargando discografía...</div>;
  if (error) return <div className="card">Error: {error}</div>;

  return (
    <div className="space-y-4">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 14px',
            borderRadius: 12,
            background: 'transparent',
            border: '1px solid var(--accent)',
            color: 'var(--accent)',
            cursor: 'pointer'
          }}
        >
          <span style={{ marginRight: 5 }}>←</span>
          <span>ATRAS</span>
        </button>
      </div>

      <div className="card" style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 16 }}>
        <div>
          <ArtistPhoto
            name={artistName}
            artistId={localArtist?.id}
            imagePathId={localArtist?.image_path_id}
            remoteUrl={artist?.spotify?.images?.[0]?.url}
            localImage={localArtist?.images}
          />
        </div>
        <div className="space-y-3">
          <div>
            <div style={{ fontWeight: 700, fontSize: 20 }}>{artistName}</div>
            <div style={{ color: 'var(--muted)', fontSize: 13 }}>Biografía completa y discografía</div>
          </div>
          <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
            {artist?.spotify?.followers?.total && (
              <span>{artist.spotify.followers.total.toLocaleString()} followers (Spotify)</span>
            )}
            {artist?.spotify?.popularity !== undefined && (
              <span>Popularidad: {artist.spotify.popularity}/100</span>
            )}
            {artist?.lastfm?.stats?.listeners && (
              <span>{Number(artist.lastfm.stats.listeners).toLocaleString()} oyentes (Last.fm)</span>
            )}
            {artist?.lastfm?.stats?.playcount && (
              <span>{Number(artist.lastfm.stats.playcount).toLocaleString()} reproducciones (Last.fm)</span>
            )}
          </div>
          {Array.isArray(artist?.spotify?.genres) && artist.spotify.genres.length > 0 && (
            <div className="flex flex-wrap gap-2 text-xs">
              {artist.spotify.genres.slice(0, 8).map((g) => (
                <span
                  key={g}
                  style={{ padding: '4px 8px', borderRadius: 8, background: 'var(--panel)', border: `1px solid var(--border)` }}
                >
                  {g}
                </span>
              ))}
            </div>
          )}
          {Array.isArray(artist?.lastfm?.tags) && artist.lastfm.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 text-xs">
              {artist.lastfm.tags.slice(0, 8).map((t: { name?: string } | string, idx) => {
                const tagLabel = typeof t === 'string' ? t : t.name || `tag-${idx}`;
                return (
                  <span
                    key={`tag-${idx}-${tagLabel}`}
                    style={{ padding: '4px 8px', borderRadius: 8, background: 'var(--panel)', border: `1px solid var(--border)` }}
                  >
                    {tagLabel}
                  </span>
                );
              })}
            </div>
          )}
          {bioToShow.length > 0 && (
            <div className="text-sm text-muted-foreground space-y-2" style={{ maxHeight: showFullBio ? 360 : 240, overflowY: 'auto' }}>
              {bioToShow.map((p, idx) => (
                <p key={idx} style={{ margin: 0 }}>
                  {p}
                </p>
              ))}
            </div>
          )}
          {bioParagraphs.length > 3 && (
            <button
              onClick={() => setShowFullBio((v) => !v)}
              style={{
                padding: '8px 12px',
                borderRadius: 10,
                border: '1px solid var(--border)',
                background: 'var(--panel)',
                cursor: 'pointer',
                fontSize: 12
              }}
            >
              {showFullBio ? 'Mostrar resumen' : 'Ver bio completa'}
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 18 }}>{artistName} · Discografía</div>
        <div style={{ color: 'var(--muted)', fontSize: 13 }}>Haz clic en un álbum o sencillo para ver detalles.</div>
      </div>

      <DiscographySection
        title="Álbumes"
        subtitle={`${studioAlbums.length} lanzamientos`}
        items={studioAlbums}
        onSelect={(albumId) => navigate(`/albums/${albumId}`)}
      />

      <DiscographySection
        title="Sencillos"
        subtitle={`${singles.length} lanzamientos`}
        items={singles}
        onSelect={(albumId) => navigate(`/albums/${albumId}`)}
      />

      {compilations.length > 0 && (
        <DiscographySection
          title="Compilaciones"
          subtitle={`${compilations.length} lanzamientos`}
          items={compilations}
          onSelect={(albumId) => navigate(`/albums/${albumId}`)}
        />
      )}
    </div>
  );
}

function DiscographySection({
  title,
  subtitle,
  items,
  onSelect,
}: {
  title: string;
  subtitle: string;
  items: Album[];
  onSelect: (albumId: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className="space-y-3">
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{title}</div>
        <div style={{ color: 'var(--muted)', fontSize: 12 }}>{subtitle}</div>
      </div>
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
        {items.map((album) => (
          <div
            key={album.id}
            className="card"
            style={{ padding: 12, background: 'var(--panel-2)', cursor: 'pointer', minWidth: 220, maxWidth: 260, margin: '0 auto' }}
            onClick={() => onSelect(album.id)}
          >
            {album.images?.[0]?.url && (
              <img
                src={resolveImageUrl(album.images[0].url)}
                alt={album.name}
                style={{ width: '100%', borderRadius: 8, marginBottom: 8 }}
              />
            )}
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{album.name}</div>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>
              {album.release_date || 'Fecha desconocida'}
            </div>
            {album.youtube_links_available !== undefined && (
              <div style={{ color: 'var(--muted)', fontSize: 12, marginTop: 6 }}>
                Links YouTube listos: {album.youtube_links_available}
                {typeof album.total_tracks === 'number' ? ` / ${album.total_tracks}` : ''}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function parseStoredImages(raw?: string | null): string[] {
  if (!raw) return [];
  const trimmed = raw.trim();
  if (!trimmed) return [];
  const tryParse = (value: string) => {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) {
        return parsed
          .map((item) => (typeof item === 'string' ? item : item?.url))
          .filter(Boolean);
      }
    } catch {
      return [];
    }
    return [];
  };

  const first = tryParse(trimmed);
  if (first.length) return first;
  const normalized = trimmed
    .replace(/'/g, '"')
    .replace(/None/g, 'null')
    .replace(/True/g, 'true')
    .replace(/False/g, 'false');
  return tryParse(normalized);
}

function resolveImageUrl(url?: string) {
  if (!url) return '';
  return url.startsWith('/') ? `${API_BASE_URL}${url}` : url;
}

function ArtistPhoto({ name, artistId, imagePathId, remoteUrl, localImage }: {
  name: string;
  artistId?: number;
  imagePathId?: number | null;
  remoteUrl?: string;
  localImage?: string | null
}) {
  // Use local cached image if available
  let imageUrl: string | null = null;

  if (imagePathId && artistId) {
    imageUrl = `${API_BASE_URL}/images/entity/artist/${artistId}?size=512`;
  } else {
    // Fallback to proxy for external URLs
    const localImages = parseStoredImages(localImage);
    const candidate = remoteUrl || localImages[0] || '';
    if (candidate.startsWith('/images/proxy')) {
      imageUrl = `${API_BASE_URL}${candidate}`;
    } else if (candidate) {
      imageUrl = `${API_BASE_URL}/images/proxy?url=${encodeURIComponent(candidate)}&size=512`;
    }
  }

  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={name}
        style={{ width: '100%', borderRadius: 12, objectFit: 'cover' }}
      />
    );
  }
  return (
    <div
      style={{
        width: '100%',
        height: 200,
        borderRadius: 12,
        background: 'var(--panel)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      {name}
    </div>
  );
}
