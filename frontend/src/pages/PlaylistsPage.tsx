import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { audio2Api } from '@/lib/api';
import type { ListsOverviewResponse, PlaylistSection } from '@/types/api';

type LoadState = 'idle' | 'loading' | 'error';

export function PlaylistsPage() {
  const [sections, setSections] = useState<PlaylistSection[]>([]);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [topGenres, setTopGenres] = useState<string[]>([]);
  const [anchorArtist, setAnchorArtist] = useState<ListsOverviewResponse['anchor_artist']>(null);

  useEffect(() => {
    setLoadState('loading');
    audio2Api
      .getListsOverview({ limit_per_list: 12 })
      .then((res) => {
        setSections(res.data.lists ?? []);
        setTopGenres(res.data.top_genres ?? []);
        setAnchorArtist(res.data.anchor_artist ?? null);
        setLoadState('idle');
      })
      .catch(() => setLoadState('error'));
  }, []);

  const heroCopy = useMemo(() => {
    if (anchorArtist?.name) {
      return `Explora la discografía de ${anchorArtist.name} y listas relacionadas basadas en tus favoritos.`;
    }
    if (topGenres.length) {
      return `Listas animadas por tus géneros preferidos: ${topGenres.join(', ')}.`;
    }
    return 'Playlists inteligentes generadas desde tu biblioteca local.';
  }, [anchorArtist, topGenres]);

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-muted-foreground">Playlists</p>
        <h1 className="text-3xl font-bold">Listas inteligentes</h1>
        <p className="text-sm text-muted-foreground">{heroCopy}</p>
      </header>

      {loadState === 'loading' && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Cargando listas curatoriales…
        </div>
      )}

      {loadState === 'error' && (
        <div className="rounded-2xl border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          No pudimos cargar las listas. Intenta recargar la página.
        </div>
      )}

      {loadState === 'idle' && !sections.length && (
        <div className="rounded-2xl border border-border/70 bg-panel-foreground/5 p-6 text-sm text-muted-foreground">
          Aún no hay listas generadas para tu biblioteca. Favoritos, reproducciones o artistas nuevos las activarán.
        </div>
      )}

      {sections.map((section) => (
        <section key={section.key} className="space-y-4 rounded-3xl border border-border bg-panel p-6 shadow-sm">
          <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-semibold">{section.title}</h2>
              <p className="text-sm text-muted-foreground">{section.description}</p>
            </div>
            <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              {section.meta?.genres ? section.meta.genres.join(' · ') : `${section.items.length} canciones`}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {section.items.map((track) => (
              <article
                key={`${section.key}-${track.id}`}
                className="flex flex-col gap-2 rounded-2xl border border-border/80 bg-background/50 p-4 transition hover:border-accent hover:bg-accent/5"
              >
                <p className="text-sm font-semibold text-foreground">{track.name}</p>
                <div className="text-xs text-muted-foreground">
                  {track.artists.map((artist) => artist.name).join(', ')}
                </div>
                {track.album?.name && (
                  <div className="text-xs text-muted-foreground">
                    {track.album.name} · {track.album.release_date}
                  </div>
                )}
                <div className="mt-auto flex items-center justify-between text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                  <span>{Math.round((track.popularity || 0) * 10) / 10} pop</span>
                  {track.download_status ? <span>{track.download_status}</span> : <span>&nbsp;</span>}
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
