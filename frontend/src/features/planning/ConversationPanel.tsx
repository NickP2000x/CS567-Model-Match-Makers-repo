import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { checkpoints } from '../../services/experiment.types';
import type { Task } from '../../services/experiment.types';

interface ConversationProps {
  task: Task;
  pending: boolean;
  routing: ReactNode;
  onSend: (text: string) => Promise<boolean>;
  onAdvance: () => void;
}

export function ConversationPanel({ task, pending, routing, onSend, onAdvance }: ConversationProps) {
  const [message, setMessage] = useState('');
  const checkpointTitle = useRef<HTMLHeadingElement>(null);
  const previousCheckpoint = useRef(task.checkpoint);
  const log = useRef<HTMLDivElement>(null);
  const currentIndex = checkpoints.indexOf(task.checkpoint);
  const next = checkpoints[currentIndex + 1];
  const model = task.decisions[task.checkpoint]?.finalModel;

  useEffect(() => {
    if (previousCheckpoint.current !== task.checkpoint) checkpointTitle.current?.focus();
    previousCheckpoint.current = task.checkpoint;
  }, [task.checkpoint]);

  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [task.messages.length]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (await onSend(message)) setMessage('');
  }

  return (
    <section className="workspace-panel conversation-panel" aria-labelledby="agent-title">
      <h3 id="agent-title">AI planning agent</h3>
      <ol className="checkpoint-list" aria-label="Planning checkpoints">
        {checkpoints.map((checkpoint, index) => (
          <li key={checkpoint} aria-current={checkpoint === task.checkpoint ? 'step' : undefined}
            className={checkpoint === task.checkpoint ? 'current-checkpoint' : undefined}>
            {checkpoint}{index < currentIndex ? ' — completed' : ''}
          </li>
        ))}
      </ol>
      <h4 id="checkpoint-title" ref={checkpointTitle} tabIndex={-1}>Current stage: {task.checkpoint}</h4>
      {routing}
      <h4>Conversation</h4>
      <div ref={log} className="conversation-log" role="log" aria-label="Simulated conversation" aria-live="polite" aria-relevant="additions">
        {task.messages.length === 0 && <p>Ask for help comparing catalog options. Use synthetic information only.</p>}
        {task.messages.map(entry => (
          <article key={entry.id} className={entry.role === 'assistant' ? 'message simulated-message' : 'message'}>
            <p className="message-label">{entry.role === 'assistant' ? `Simulated ${entry.model} model` : 'You'} · {entry.checkpoint}</p>
            <p>{entry.text}</p>
          </article>
        ))}
      </div>
      <form onSubmit={event => { void send(event); }} className="message-form">
        <label htmlFor="agent-message">Message to simulated agent</label>
        <textarea id="agent-message" rows={3} required value={message} disabled={pending || !model}
          onChange={event => setMessage(event.target.value)} />
        <button type="submit" disabled={pending || !model}>Send message</button>
      </form>
      <div className="stage-actions">
        {next ? (
          <button type="button" className="secondary" disabled={pending || !model} onClick={onAdvance}>Continue to {next}</button>
        ) : <p>Final checkpoint reached. Submit your current plan when ready.</p>}
      </div>
    </section>
  );
}
