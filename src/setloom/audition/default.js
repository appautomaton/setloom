/* SPDX-License-Identifier: AGPL-3.0-only */
'use strict';
(() => {
  const payload = SetloomAudition.read();
  const transport = new SetloomAudition.Transport(
    payload.session, document.getElementById('audition-audio')
  );
  for (const option of payload.session.options) {
    const button = document.createElement('button');
    button.textContent = option.label;
    button.dataset.option = option.id;
    button.addEventListener('click', () => transport.select(option.id));
    document.getElementById('options').appendChild(button);
  }
  transport.subscribe(state => {
    for (const button of document.querySelectorAll('[data-option]')) {
      button.setAttribute('aria-pressed', String(button.dataset.option === state.option));
    }
    document.getElementById('status').textContent = state.error ||
      `${state.loading ? 'Loading' : state.playing ? 'Playing' : 'Paused'} · ${state.label}`;
  });
})();
