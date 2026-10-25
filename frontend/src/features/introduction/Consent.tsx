interface ConsentProps {
  declined: boolean;
  pending: boolean;
  simulated: boolean;
  refreshRestartsDemo: boolean;
  onDecision: (accepted: boolean) => void;
}

export function Consent({ declined, pending, simulated, refreshRestartsDemo, onDecision }: ConsentProps) {
  if (declined) {
    return <p>You declined the demonstration. You have not entered the study. You may close this tab.</p>;
  }

  return (
    <>
      <p className="provisional-notice">
        Draft demonstration consent — pending researcher approval.
        This is not an approved research consent form.
      </p>
      <p>
        Explore an event-planning interface with {simulated ? 'simulated' : 'live'} AI assistance.
        You will review instructions, complete a practice task, and plan two fictional
        events with workload questions after each task and optional feedback at the end.
      </p>
      <p>
        Exploring the demonstration is voluntary. Use invented demographic answers,
        and do not enter personal or sensitive information.
        {refreshRestartsDemo
          ? ' Responses stay in this page’s memory and are lost when you refresh.'
          : ' Responses and interaction records are saved on the study server. Refreshing in the same browser tab normally resumes the session; unsent text may be lost. Closing the tab does not delete saved records.'}
        {simulated
          ? ' Agent replies are simulated; no live model requests are made for those replies.'
          : ' Messages and planning context are sent to the configured AI services to generate replies.'}
        {' '}You can stop exploring by closing the tab.
      </p>
      <p>Accept to explore the demo, or decline to stop before entering it.</p>
      <div className="actions">
        <button type="button" disabled={pending} onClick={() => onDecision(true)}>Accept and continue</button>
        <button type="button" className="secondary" disabled={pending} onClick={() => onDecision(false)}>Decline</button>
      </div>
    </>
  );
}
