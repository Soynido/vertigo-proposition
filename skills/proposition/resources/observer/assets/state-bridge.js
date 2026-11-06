/* Standalone draft persistence only. Never fakes a Codex submission or receipt. */
(() => {
  if (window.openai?.setWidgetState) return;
  const key = 'vertigo-front-copy/1:' + location.pathname;
  let state = null;
  try { state = JSON.parse(localStorage.getItem(key) || 'null'); } catch {}
  const query = new URLSearchParams(location.search);
  const screen = query.get('screen');
  if (screen) {
    const setup = !location.pathname.includes('/views/');
    const role = query.get('role') || 'proposition';
    const selected = screen === 'setup' || screen === 'advanced' || screen === 'review';
    const view = screen === 'advanced' ? 'advanced' : screen === 'review' ? 'review' : 'simple';
    state = {modelContent: {}, privateContent: {
      version: setup ? 4 : 3, instance: 'standalone-preview-seed',
      time: screen === 'done' ? 7680 : screen === 'waiting' ? 7080 : 2265,
      speed: 710, approved: screen === 'done', closed: [], selected: selected ? 'root' : null,
      feedback: '', setupView: {role, line: 'root', view}
    }};
  }
  window.openai = {
    widgetState: state,
    async setWidgetState(next) {
      const serialized = JSON.stringify(next);
      if (new TextEncoder().encode(serialized).length > 16 * 1024) throw new Error('Draft exceeds 16 KiB');
      const stored = JSON.parse(serialized);
      localStorage.setItem(key, serialized);
      this.widgetState = stored;
      window.dispatchEvent(new CustomEvent('openai:set_globals', {detail: {globals: {widgetState: stored}}}));
    }
  };
})();
