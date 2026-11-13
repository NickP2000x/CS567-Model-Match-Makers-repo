// Timing for the agent activity indicator, kept free of React so it can be tested with fake timers.
export const AGENT_ACTIVITY_LABEL = 'Agent is working on your message...';
export const PHRASE_INTERVAL_MS = 4000;

interface Timers {
  setInterval: (callback: () => void, ms: number) => unknown;
  clearInterval: (id: never) => void;
}

/** Shows the first phrase now, rotates every interval, and returns a stop function. */
export function startPhraseRotation(phrases: readonly string[], onPhrase: (phrase: string) => void,
  timers: Timers = globalThis as unknown as Timers): () => void {
  if (phrases.length === 0) {
    onPhrase(AGENT_ACTIVITY_LABEL);
    return () => {};
  }
  onPhrase(phrases[0]);
  if (phrases.length === 1) return () => {};
  let index = 0;
  let stopped = false;
  const id = timers.setInterval(() => {
    if (stopped) return;
    index = (index + 1) % phrases.length;
    onPhrase(phrases[index]);
  }, PHRASE_INTERVAL_MS);
  return () => {
    stopped = true;
    timers.clearInterval(id as never);
  };
}
