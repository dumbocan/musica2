let youtubeIframePromise: Promise<void> | null = null;

export const loadYoutubeIframeApi = () => {
  if (youtubeIframePromise) {
    return youtubeIframePromise;
  }

  youtubeIframePromise = new Promise((resolve) => {
    let resolved = false;
    let poller = 0;
    const finish = () => {
      if (resolved) return;
      resolved = true;
      if (poller) window.clearInterval(poller);
      resolve();
    };

    const windowWithYT = window as Window & { YT?: { Player?: unknown }; onYouTubeIframeAPIReady?: () => void };
    if (windowWithYT.YT && windowWithYT.YT.Player) {
      finish();
      return;
    }

    const previous = windowWithYT.onYouTubeIframeAPIReady;
    windowWithYT.onYouTubeIframeAPIReady = () => {
      if (typeof previous === 'function') {
        try {
          previous();
        } catch {
          // ignore errors from prior handlers
        }
      }
      finish();
    };

    poller = window.setInterval(() => {
      const yt = windowWithYT.YT;
      if (yt && yt.Player) {
        finish();
      }
    }, 50);

    const existing = document.querySelector('script[src*="youtube.com/iframe_api"]');
    if (!existing) {
      const tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      document.head.appendChild(tag);
    }
  });

  return youtubeIframePromise;
};
