import { useEffect, useRef } from 'react';
import { loadYoutubeIframeApi } from '@/lib/youtubeIframe';
import { usePlayerStore } from '@/store/usePlayerStore';
import type { VideoController } from '@/store/usePlayerStore';

type PlayerApi = {
  playVideo?: () => void;
  pauseVideo?: () => void;
  stopVideo?: () => void;
  seekTo?: (seconds: number, allowSeekAhead: boolean) => void;
  getCurrentTime?: () => number;
  getDuration?: () => number;
  setVolume?: (value: number) => void;
  getVolume?: () => number;
  mute?: () => void;
  unMute?: () => void;
  isMuted?: () => boolean;
  loadVideoById?: (videoId: string) => void;
  destroy?: () => void;
};

type YT = {
  Player: new (
    el: HTMLElement,
    options: {
      videoId: string;
      playerVars: Record<string, unknown>;
      events: {
        onReady: (event: { target: PlayerApi }) => void;
        onStateChange: (event: { data: number }) => void;
        onError: () => void;
      };
    }
  ) => PlayerApi;
  PlayerState: {
    ENDED: number;
    PLAYING: number;
    PAUSED: number;
  };
};

const createController = (player: PlayerApi): VideoController => ({
  play: () => player.playVideo?.(),
  pause: () => player.pauseVideo?.(),
  stop: () => player.stopVideo?.(),
  seek: (value) => player.seekTo?.(value, true),
  setVolume: (value) => player.setVolume?.(value),
  getVolume: () => player.getVolume?.() ?? 0,
  getCurrentTime: () => player.getCurrentTime?.() ?? 0,
  getDuration: () => player.getDuration?.() ?? 0,
  isMuted: () => player.isMuted?.() ?? false,
  setMuted: (muted) => {
    if (muted) {
      player.mute?.();
    } else {
      player.unMute?.();
    }
  },
});

type YouTubeOverlayPlayerProps = {
  videoId: string;
  onClose?: () => void;
};

export function YouTubeOverlayPlayer({ videoId, onClose }: YouTubeOverlayPlayerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<PlayerApi | null>(null);
  const setVideoController = usePlayerStore((s) => s.setVideoController);
  const setIsPlaying = usePlayerStore((s) => s.setIsPlaying);
  const setCurrentTime = usePlayerStore((s) => s.setCurrentTime);
  const setDuration = usePlayerStore((s) => s.setDuration);
  const setStatusMessage = usePlayerStore((s) => s.setStatusMessage);

  useEffect(() => {
    let cancelled = false;

    const mount = async () => {
      setStatusMessage('Cargando video...');
      setCurrentTime(0);
      setDuration(0);
      await loadYoutubeIframeApi();
      if (cancelled || !containerRef.current) return;

      const yt = (window as Window & { YT?: YT }).YT;
      if (!yt?.Player) {
        setStatusMessage('No se pudo cargar el reproductor de YouTube');
        return;
      }
      const playerVars = {
        autoplay: 1,
        controls: 0,
        disablekb: 1,
        modestbranding: 1,
        rel: 0,
        playsinline: 1,
        origin: window.location.origin,
      };

      const onReady = (event: { target: PlayerApi }) => {
        const nextDuration = event.target.getDuration?.() ?? 0;
        if (Number.isFinite(nextDuration) && nextDuration > 0) {
          setDuration(nextDuration);
        }
        setStatusMessage('');
      };

      const onStateChange = (event: { data: number }) => {
        const states = yt.PlayerState || {};
        if (event.data === states.PLAYING) {
          setIsPlaying(true);
          setStatusMessage('');
          return;
        }
        if (event.data === states.PAUSED) {
          setIsPlaying(false);
          return;
        }
        if (event.data === states.ENDED) {
          setIsPlaying(false);
          setCurrentTime(0);
        }
      };

      const onError = () => {
        setStatusMessage('No se pudo cargar el video');
        setIsPlaying(false);
      };

      if (playerRef.current) {
        playerRef.current.loadVideoById?.(videoId);
      } else {
        playerRef.current = new yt.Player(containerRef.current, {
          videoId,
          playerVars,
          events: { onReady, onStateChange, onError },
        });
      }

      if (playerRef.current) {
        setVideoController(createController(playerRef.current));
      }
    };

    void mount();

    return () => {
      cancelled = true;
    };
  }, [setCurrentTime, setDuration, setIsPlaying, setStatusMessage, setVideoController, videoId]);

  useEffect(() => {
    return () => {
      setVideoController(null);
      if (playerRef.current?.destroy) {
        playerRef.current.destroy();
      }
      playerRef.current = null;
    };
  }, [setVideoController]);

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        borderRadius: 12,
        overflow: 'hidden',
        boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
        border: '2px solid rgba(255,255,255,0.06)',
      }}
    >
      <div ref={containerRef} style={{ width: '100%', height: '100%', pointerEvents: 'none' }} />
      <button
        onClick={onClose}
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          width: 26,
          height: 26,
          borderRadius: 999,
          border: 'none',
          background: 'rgba(0,0,0,0.65)',
          color: '#fff',
          cursor: 'pointer',
          fontSize: 16,
          lineHeight: '26px',
          textAlign: 'center',
          padding: 0,
        }}
        aria-label="Cerrar video"
      >
        x
      </button>
    </div>
  );
}
