/* SPDX-License-Identifier: AGPL-3.0-only */
/* A file-local media transport. Presentation and musical meaning stay with the song. */
'use strict';
globalThis.SetloomAudition = (() => {
  class Transport {
    constructor(session, media, {timeoutMs = 15000} = {}) {
      this.options = new Map(session.options.map(option => [option.id, option]));
      this.option = this.options.get(session.default);
      if (!this.option) throw new Error('The default listening view is unavailable.');
      this.media = media;
      this.timeoutMs = timeoutMs;
      this.position = this.option.offset;
      this.wanted = false;
      this.loading = false;
      this.error = '';
      this.loop = null;
      this.volume = media.volume;
      this.muted = media.muted;
      this.generation = 0;
      this.pendingPlay = null;
      this.listeners = new Set();
      this.cancelReady = null;
      this.frame = null;
      this.bindMedia();
      this.setVolume(this.volume);
      // Cached pages retain their controller when the listener returns.
      this.onPageHide = event => event.persisted ? this.pause() : this.destroy();
      globalThis.addEventListener?.('pagehide', this.onPageHide);
    }

    bounds() {
      const duration = this.media.readyState >= 1 && Number.isFinite(this.media.duration)
        ? Math.min(this.option.duration, this.media.duration) : this.option.duration;
      return [this.option.offset, this.option.offset + duration];
    }

    clamp(time) {
      const [start, end] = this.bounds();
      return Math.max(start, Math.min(end, time));
    }

    now() {
      return this.loading || this.media.seeking || this.media.readyState < 1 ? this.position
        : this.clamp(this.option.offset + this.media.currentTime);
    }

    state() {
      return {
        option: this.option.id, label: this.option.label, position: this.now(),
        playing: this.wanted && !this.media.paused && !this.loading,
        wanted: this.wanted, loading: this.loading, error: this.error,
        volume: this.volume, muted: this.muted,
        loop: this.loop ? {...this.loop} : null, bounds: this.bounds(),
        source: this.media.currentSrc || this.option.path,
      };
    }

    subscribe(listener) {
      this.listeners.add(listener);
      listener(this.state());
      return () => this.listeners.delete(listener);
    }

    emit() {
      const state = this.state();
      for (const listener of this.listeners) listener(state);
    }

    bindMedia() {
      const media = this.media;
      const events = {
        play: () => {
          if (this.loading || (this.pendingPlay && !this.wanted)) {
            media.pause();
            return;
          }
          this.wanted = true;
          this.error = '';
          this.tick();
        },
        pause: () => {
          // At end-of-file, pause precedes ended; preserve the loop's intent.
          if (!this.loading && !media.ended) this.wanted = false;
          this.position = this.now();
          this.emit();
        },
        volumechange: () => {
          this.volume = Math.min(1, media.volume / this.option.gain);
          this.muted = media.muted;
          // Native controls must respect the prepared view's attenuation too.
          if (media.volume > this.option.gain) media.volume = this.option.gain;
          this.emit();
        },
        timeupdate: () => this.advance(),
        loadedmetadata: () => {
          if (!this.loading) {
            this.media.currentTime = this.clamp(this.position) - this.option.offset;
            this.emit();
          }
        },
        seeked: () => { this.position = this.now(); this.emit(); },
        ended: () => {
          if (this.wanted && this.loop) {
            this.seek(this.loop.start);
            void this.play();
          } else {
            this.wanted = false;
            this.position = this.bounds()[1];
            this.emit();
          }
        },
        error: () => {
          this.cancelReady?.(new Error('This audio could not open. Keep its folder together.'));
          this.loading = false;
          this.wanted = false;
          this.error = 'This audio could not open. Keep its folder together.';
          this.emit();
        },
      };
      for (const [name, listener] of Object.entries(events)) media.addEventListener(name, listener);
      this.unbindMedia = () => {
        for (const [name, listener] of Object.entries(events)) {
          media.removeEventListener(name, listener);
        }
      };
    }

    ready(media) {
      if (media.readyState >= 1) return Promise.resolve(true);
      return new Promise((resolve, reject) => {
        const finish = (error, ready = true) => {
          clearTimeout(timer);
          media.removeEventListener('loadedmetadata', loaded);
          media.removeEventListener('error', failed);
          if (this.cancelReady === cancel) this.cancelReady = null;
          if (error) reject(error); else resolve(ready);
        };
        const loaded = () => finish();
        const failed = () => finish(new Error('This audio could not open.'));
        const cancel = error => finish(error, false);
        const timer = setTimeout(
          () => finish(new Error('Audio preparation timed out. Choose Play to retry.')),
          this.timeoutMs
        );
        this.cancelReady = cancel;
        media.addEventListener('loadedmetadata', loaded);
        media.addEventListener('error', failed);
        media.load();
      });
    }

    async select(id) {
      const option = this.options.get(id);
      if (!option) throw new Error('This listening view is unavailable.');
      if (id === this.option.id && !this.error) return true;
      const position = this.now();
      const wanted = this.wanted;
      const request = ++this.generation;
      this.cancelReady?.();
      this.unbindMedia();
      const previous = this.media;
      previous.pause();
      // Separate elements isolate late play promises from the new selection.
      this.media = previous.cloneNode(false);
      this.media.src = option.path;
      this.media.muted = this.muted;
      previous.replaceWith(this.media);
      previous.removeAttribute('src');
      previous.load();
      this.option = option;
      this.position = this.clamp(position);
      this.wanted = wanted;
      this.loading = true;
      this.pendingPlay = null;
      this.error = '';
      this.bindMedia();
      this.setVolume(this.volume);
      if (this.loop) this.setLoop(this.loop);
      const media = this.media;
      this.emit();
      try {
        if (!await this.ready(media) || request !== this.generation) return false;
        this.position = this.clamp(this.position);
        media.currentTime = this.position - option.offset;
        this.loading = false;
        this.emit();
        if (this.wanted) await this.start(media, request);
        return !this.error;
      } catch (error) {
        this.fail(error, media, request);
        return false;
      }
    }

    async start(media, request) {
      if (media !== this.media || request !== this.generation || !this.wanted) return;
      const attempt = {};
      this.pendingPlay = attempt;
      try {
        await media.play();
        if (media !== this.media || request !== this.generation || !this.wanted) media.pause();
      } catch (error) {
        if (this.pendingPlay === attempt && this.wanted) this.fail(error, media, request);
      } finally {
        if (media === this.media && request === this.generation && this.pendingPlay === attempt) {
          this.pendingPlay = null;
          this.emit();
        }
      }
    }

    fail(error, media, request) {
      if (media !== this.media || request !== this.generation) return;
      this.loading = false;
      this.wanted = false;
      media.pause();
      this.error = error.message || 'Playback could not start. Choose Play to retry.';
      this.emit();
    }

    async play() {
      this.wanted = true;
      this.error = '';
      if (this.loading) { this.emit(); return; }
      const media = this.media;
      const request = this.generation;
      if (this.now() >= this.bounds()[1] - .01) this.seek(this.bounds()[0]);
      try {
        if (media.readyState < 1) {
          this.loading = true;
          this.emit();
          if (!await this.ready(media) || request !== this.generation) return;
          this.position = this.clamp(this.position);
          media.currentTime = this.position - this.option.offset;
          this.loading = false;
        }
        await this.start(media, request);
      } catch (error) { this.fail(error, media, request); }
    }

    pause() {
      this.position = this.now();
      this.wanted = false;
      this.media.pause();
      this.emit();
    }

    toggle() { return this.wanted ? this.pause() : this.play(); }

    seek(time) {
      if (!Number.isFinite(time)) throw new Error('Seek time must be finite.');
      this.position = this.clamp(time);
      if (!this.loading && this.media.readyState >= 1) {
        this.media.currentTime = this.position - this.option.offset;
      }
      this.emit();
    }

    setVolume(volume) {
      if (!Number.isFinite(volume) || volume < 0 || volume > 1) {
        throw new Error('Volume must be between zero and one.');
      }
      this.volume = volume;
      this.media.volume = volume * this.option.gain;
      this.emit();
    }

    setLoop(range) {
      if (range && (!Number.isFinite(range.start) || !Number.isFinite(range.end))) {
        throw new Error('Loop boundaries must be finite.');
      }
      if (range && range.end <= range.start) throw new Error('Loop end must follow its start.');
      const start = range ? this.clamp(range.start) : 0;
      const end = range ? this.clamp(range.end) : 0;
      this.loop = range && end > start ? {start, end} : null;
      this.emit();
    }

    advance() {
      this.position = this.now();
      if (this.wanted && this.loop && this.position >= this.loop.end) {
        this.seek(this.loop.start);
      } else this.emit();
    }

    tick() {
      if (this.frame !== null) return;
      const next = () => {
        this.frame = null;
        if (!this.media.paused && !this.loading) {
          this.advance();
          this.frame = requestAnimationFrame(next);
        }
      };
      this.frame = requestAnimationFrame(next);
      this.emit();
    }

    destroy() {
      ++this.generation;
      this.cancelReady?.();
      this.unbindMedia();
      this.pause();
      if (this.frame !== null) cancelAnimationFrame(this.frame);
      this.frame = null;
      globalThis.removeEventListener?.('pagehide', this.onPageHide);
      this.listeners.clear();
    }
  }

  function read() {
    return JSON.parse(document.getElementById('setloom-audition-data').textContent);
  }

  function bindDownloads(exports, root = document) {
    root.addEventListener('click', event => {
      const link = event.target.closest?.('a[download]');
      if (!link) return;
      const href = link.getAttribute('href') || '';
      let entry = exports[href];
      if (!entry) {
        try { entry = exports[decodeURIComponent(href)]; } catch { return; }
      }
      if (!entry) return;
      event.preventDefault();
      const bytes = Uint8Array.from(atob(entry.base64), character => character.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], {type: entry.mime}));
      const download = document.createElement('a');
      download.href = url;
      download.download = link.download || decodeURIComponent(link.getAttribute('href')).split('/').at(-1);
      document.body.appendChild(download);
      download.click();
      download.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  return {Transport, read, bindDownloads};
})();
