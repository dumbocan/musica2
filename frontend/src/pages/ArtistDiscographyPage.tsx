import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { audio2Api } from '@/lib/api';

type AlbumImage = { url: string };
type Album = { id: string; name: string; release_date?: string; images?: AlbumImage[] };
type Artist = { id: string; name: string };

export function ArtistDiscographyPage() {
  const { spotifyId } = useParams<{ spotifyId: string }>();
  const navigate = useNavigate();
  const [artist, setArtist] = useState<Artist | null>(null);
  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!spotifyId) return;
      setLoading(true);
      setError(null);
      try {
        const [artistRes, albumsRes] = await Promise.all([
          audio2Api.getArtistInfo(spotifyId),
          audio2Api.getArtistAlbums(spotifyId),
        ]);
        setArtist(artistRes.data);
        setAlbums(albumsRes.data || []);
      } catch (err: any) {
        setError(err?.response?.data?.detail || err?.message || 'Error cargando discografía');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [spotifyId]);

  if (!spotifyId) return <div className="card">Artista no especificado.</div>;
  if (loading) return <div className="card">Cargando discografía...</div>;
  if (error) return <div className="card">Error: {error}</div>;

  return (
    <div className="space-y-4">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button className="btn-ghost" onClick={() => navigate(-1)}>
          ← Volver a búsqueda
        </button>
      </div>

      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 18 }}>{artist?.name || 'Artista'}</div>
        <div style={{ color: 'var(--muted)', fontSize: 13 }}>Haz clic en un álbum para ver detalles.</div>
      </div>

      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
        {albums.map((album) => (
          <div
            key={album.id}
            className="card"
            style={{ padding: 12, background: 'var(--panel-2)', cursor: 'pointer', minWidth: 220, maxWidth: 260, margin: '0 auto' }}
            onClick={() => navigate(`/albums/${album.id}`)}
          >
            {album.images?.[0]?.url && (
              <img
                src={album.images[0].url}
                alt={album.name}
                style={{ width: '100%', borderRadius: 8, marginBottom: 8 }}
              />
            )}
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{album.name}</div>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>
              {album.release_date || 'Fecha desconocida'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
