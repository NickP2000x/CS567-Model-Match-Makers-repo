// Phrases shown under "Agent is working on your message..." while the agent replies.
// Add or remove plain-text sentences below; no other code needs to change. The list rotates
// every four seconds and starts from the first phrase for each message. These are presentation
// text only, not model reasoning or tool progress. Keep the wording fixed during a study and
// record any change in docs/experiment-service-contract.md ("Agent activity phrases").
export const AGENT_STATUS_MESSAGES = [
  'Thinking...',
  'Contemplating...',
  'Working on your message...',
  // Add custom sentences here.
];
