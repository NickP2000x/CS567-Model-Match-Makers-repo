import { useEffect, useState } from 'react';
import { AGENT_ACTIVITY_LABEL, startPhraseRotation } from './phraseRotation';
import { AGENT_STATUS_MESSAGES } from './agentStatusMessages';

// Mounted once per message request; unmounting stops the rotation.
export function AgentActivity() {
  const [phrase, setPhrase] = useState('');
  useEffect(() => startPhraseRotation(AGENT_STATUS_MESSAGES, setPhrase), []);

  return (
    <div className="agent-activity">
      <p role="status">{AGENT_ACTIVITY_LABEL}</p>
      {/* The rotating phrase is decorative; only the stable label is announced. */}
      {phrase !== AGENT_ACTIVITY_LABEL && <p className="agent-activity-phrase" aria-hidden="true">{phrase}</p>}
    </div>
  );
}
