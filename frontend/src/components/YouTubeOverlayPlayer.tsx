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
  setPlaybackQuality?: (quality: string) => void;
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
      host?: string;
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
};

export function YouTubeOverlayPlayer({ videoId }: YouTubeOverlayPlayerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<PlayerApi | null>(null);
  const setVideoController = usePlayerStore((s) => s.setVideoController);
  const setStatusMessage = usePlayerStore((s) => s.setStatusMessage);

  useEffect(() => {
    let cancelled = false;

    const mount = async () => {
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
        fs: 0,
        iv_load_policy: 3,
        modestbranding: 1,
        rel: 0,
        playsinline: 1,
        origin: window.location.origin,
        vq: 'tiny',
      };

      const onReady = (event: { target: PlayerApi }) => {
        event.target.mute?.();
        event.target.setVolume?.(0);
        event.target.setPlaybackQuality?.('tiny');
      };

      const onStateChange = (_event: { data: number }) => {};

      const onError = () => {
        setStatusMessage('No se pudo cargar el video');
      };

      if (playerRef.current) {
        playerRef.current.loadVideoById?.(videoId);
        playerRef.current.mute?.();
        playerRef.current.setVolume?.(0);
      } else {
        playerRef.current = new yt.Player(containerRef.current, {
          videoId,
          host: 'https://www.youtube-nocookie.com',
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
  }, [setStatusMessage, setVideoController, videoId]);

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
    </div>
  );
}
