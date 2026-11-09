// SPDX-License-Identifier: AGPL-3.0-only
// Deterministic media failure sequences. No browser, network, or sound output.
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('../src/setloom/audition/transport.js', import.meta.url), 'utf8');
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
};

function setup({ready = true, timeoutMs = 1000} = {}) {
  const media = [];
  const raf = new Map();
  const pageEvents = new Map();
  let sequence = 0;
  class Media {
    constructor() {
      this.events = new Map();
      this.readyState = ready ? 1 : 0;
      this.duration = 100;
      this.currentTime = 0;
      this.paused = true;
      this.ended = false;
      this.muted = false;
      this.seeking = false;
      this.volume = .7;
      this.playCalls = 0;
      this.src = 'one.wav';
      media.push(this);
    }
    addEventListener(name, listener) {
      if (!this.events.has(name)) this.events.set(name, new Set());
      this.events.get(name).add(listener);
    }
    removeEventListener(name, listener) { this.events.get(name)?.delete(listener); }
    emit(name) { for (const listener of [...(this.events.get(name) || [])]) listener(); }
    load() {}
    replaceWith() {}
    removeAttribute(name) { if (name === 'src') this.src = ''; }
    cloneNode() { return new Media(); }
    pause() { const wasPlaying = !this.paused; this.paused = true; if (wasPlaying) this.emit('pause'); }
    async play() {
      this.playCalls++;
      if (this.playGate) await this.playGate.promise;
      this.paused = false;
      this.emit('play');
    }
    metadata() { this.readyState = 1; this.emit('loadedmetadata'); }
  }
  const context = vm.createContext({
    console, setTimeout, clearTimeout,
    requestAnimationFrame: callback => { raf.set(++sequence, callback); return sequence; },
    cancelAnimationFrame: id => raf.delete(id),
    addEventListener: (name, listener) => pageEvents.set(name, listener),
    removeEventListener: name => pageEvents.delete(name),
  });
  vm.runInContext(source, context);
  const options = [
    {id:'one', label:'One', path:'one.wav', duration:100, offset:0, gain:1},
    {id:'two', label:'Two', path:'two.wav', duration:100, offset:0, gain:1},
    {id:'excerpt', label:'Excerpt', path:'excerpt.wav', duration:10, offset:40, gain:.5},
  ];
  const transport = new context.SetloomAudition.Transport({options, default:'one'}, new Media(), {timeoutMs});
  return {transport, media, raf, pageEvents};
}

test('initialization and paused switching never play; positions survive', async () => {
  const {transport, media} = setup();
  transport.seek(12.5);
  await transport.select('two');
  assert.equal(transport.now(), 12.5);
  assert.equal(media.reduce((count, item) => count + item.playCalls, 0), 0);
  await transport.play();
  assert.equal(transport.state().playing, true);
  await transport.select('one');
  assert.equal(transport.now(), 12.5);
  assert.equal(media[1].paused, true);
  assert.equal(transport.state().playing, true);
  transport.destroy();
});

test('rapid selection cancels old metadata waits and applies pending seek', async () => {
  const {transport, media} = setup({ready:false});
  const first = transport.select('two');
  transport.seek(18);
  const second = transport.select('excerpt');
  transport.seek(46);
  assert.equal(await first, false);
  assert.equal(media[1].events.get('loadedmetadata').size, 0);
  media[1].metadata();
  assert.equal(transport.state().option, 'excerpt');
  media[2].metadata();
  assert.equal(await second, true);
  assert.equal(media[2].currentTime, 6);
  assert.equal(transport.now(), 46);
  assert.equal(media[2].volume, .35);
  transport.destroy();
});

test('a stale play promise cannot sound after a new paused selection', async () => {
  const {transport, media} = setup();
  const old = media[0];
  old.playGate = deferred();
  const starting = transport.play();
  await transport.select('two');
  transport.pause();
  old.playGate.resolve();
  await starting;
  assert.equal(old.paused, true);
  assert.equal(transport.media.paused, true);
  assert.equal(transport.state().wanted, false);
  transport.destroy();
});

test('pause during a pending play promise remains paused', async () => {
  const {transport, media} = setup();
  media[0].playGate = deferred();
  const starting = transport.play();
  transport.pause();
  media[0].playGate.resolve();
  await starting;
  assert.equal(media[0].paused, true);
  assert.equal(transport.state().wanted, false);
  transport.destroy();
});

test('seeking before metadata preserves the requested position', async () => {
  const {transport, media} = setup({ready:false});
  transport.seek(21);
  assert.equal(transport.now(), 21);
  const starting = transport.play();
  transport.seek(32);
  media[0].metadata();
  await starting;
  assert.equal(transport.now(), 32);
  assert.equal(transport.state().playing, true);
  transport.destroy();
});

test('loops respect excerpt bounds and continue across end-of-file', async () => {
  const {transport} = setup();
  await transport.select('excerpt');
  transport.setLoop({start:39,end:45});
  assert.equal(transport.state().loop.start, 40);
  await transport.play();
  transport.media.currentTime = 5;
  transport.media.emit('timeupdate');
  assert.equal(transport.media.currentTime, 0);
  transport.media.currentTime = 10;
  transport.media.paused = true;
  transport.media.emit('ended');
  await Promise.resolve();
  assert.equal(transport.state().wanted, true);
  transport.setLoop(null);
  transport.media.currentTime = 10;
  transport.media.paused = true;
  transport.media.emit('ended');
  assert.equal(transport.state().wanted, false);
  assert.equal(transport.now(), 50);
  transport.destroy();
});

test('missing options do not substitute another audible selection', async () => {
  const {transport} = setup();
  await assert.rejects(transport.select('missing'), /unavailable/);
  assert.equal(transport.state().option, 'one');
  assert.equal(transport.state().wanted, false);
  transport.destroy();
});

test('timeout cleans metadata listeners; retry can succeed', async () => {
  const {transport} = setup({ready:false,timeoutMs:5});
  assert.equal(await transport.select('two'), false);
  assert.match(transport.state().error, /timed out/);
  assert.equal(transport.media.events.get('loadedmetadata').size, 1); // Transport's native listener only.
  transport.media.metadata();
  await transport.play();
  assert.equal(transport.state().error, '');
  assert.equal(transport.state().playing, true);
  transport.destroy();
});

test('native audio controls update the same transport state', async () => {
  const {transport} = setup();
  await transport.media.play();
  assert.equal(transport.state().playing, true);
  transport.media.pause();
  assert.equal(transport.state().wanted, false);
  transport.destroy();
});

test('the native pause event at end-of-file does not cancel a loop', async () => {
  const {transport} = setup();
  transport.setLoop({start:90, end:100});
  await transport.play();
  transport.media.currentTime = 100;
  transport.media.ended = true;
  transport.media.paused = true;
  transport.media.emit('pause');
  transport.media.emit('ended');
  await Promise.resolve();
  assert.equal(transport.state().wanted, true);
  assert.equal(transport.media.currentTime, 90);
  assert.equal(transport.media.playCalls, 2);
  transport.destroy();
});

test('an earlier play rejection cannot stop a newer play on the same element', async () => {
  const {transport, media} = setup();
  const first = deferred();
  const second = deferred();
  media[0].playGate = first;
  const starting = transport.play();
  transport.pause();
  media[0].playGate = second;
  const restarting = transport.play();
  first.reject(new Error('The earlier play request was interrupted.'));
  await starting;
  assert.equal(transport.state().wanted, true);
  assert.equal(transport.state().error, '');
  second.resolve();
  await restarting;
  assert.equal(transport.state().playing, true);
  transport.destroy();
});

test('native volume and mute survive selection without bypassing option gain', async () => {
  const {transport} = setup();
  transport.media.volume = .2;
  transport.media.muted = true;
  transport.media.emit('volumechange');
  assert.equal(transport.state().volume, .2);
  assert.equal(transport.state().muted, true);
  await transport.select('excerpt');
  assert.equal(transport.media.volume, .1);
  assert.equal(transport.media.muted, true);
  transport.media.volume = .8;
  transport.media.emit('volumechange');
  assert.equal(transport.media.volume, .5);
  assert.equal(transport.state().volume, 1);
  transport.destroy();
});

test('metadata clamps a pending initial seek to the actual resource duration', async () => {
  const {transport, media} = setup({ready:false});
  transport.seek(80);
  const starting = transport.play();
  media[0].duration = 60;
  media[0].metadata();
  await starting;
  assert.equal(media[0].currentTime, 60);
  transport.destroy();
});

test('back-forward cache suspension pauses without destroying the controller', async () => {
  const {transport, pageEvents, raf} = setup();
  await transport.play();
  transport.seek(12);
  pageEvents.get('pagehide')({persisted:true});
  assert.equal(transport.state().playing, false);
  assert.equal(pageEvents.has('pagehide'), true);
  await transport.media.play();
  assert.equal(transport.state().playing, true);
  assert.equal(transport.now(), 12);
  pageEvents.get('pagehide')({persisted:false});
  assert.equal(transport.state().playing, false);
  assert.equal(pageEvents.has('pagehide'), false);
  assert.equal(raf.size, 0);
});
