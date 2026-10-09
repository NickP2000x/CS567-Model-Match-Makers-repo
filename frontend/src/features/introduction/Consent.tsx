interface ConsentProps {
  declined: boolean;
  pending: boolean;
  onDecision: (accepted: boolean) => void;
}

export function Consent({ declined, pending, onDecision }: ConsentProps) {
  if (declined) {
    return <p>You declined the demonstration. You have not entered the study. You may close this tab.</p>;
  }

  return (
    <>
      <p className="provisional-notice">
        Draft consent — pending researcher approval. This is placeholder copy,
        not an approved research consent form.
      </p>
      <p>
        This demonstration introduces an event-planning interface with simulated
        AI assistance. It includes a short introduction, practice, and a planned
        two-task workflow with workload questions after each experimental task.
      </p>
      <p>
        Exploring the demonstration is voluntary. Use invented demographic answers,
        and do not enter personal or sensitive information. Demo responses stay in
        this browser session’s memory and are lost when you refresh. No real model
        calls are made. You can stop exploring by closing the tab.
      </p>
      <p>Accept to explore the demo, or decline to stop before entering it.</p>
      <div className="actions">
        <button type="button" disabled={pending} onClick={() => onDecision(true)}>Accept and continue</button>
        <button type="button" className="secondary" disabled={pending} onClick={() => onDecision(false)}>Decline</button>
      </div>
    </>
  );
}
