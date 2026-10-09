export function Tutorial({ pending, onContinue }: { pending: boolean; onContinue: () => void }) {
  return (
    <>
      <p className="provisional-notice">Provisional tutorial and example — pending researcher approval.</p>
      <h3>Inspect, ask, and build a plan</h3>
      <p>The planning workspace has three panels: Catalog on the left, AI planning agent in the middle, and Current event plan on the right.</p>
      <ul>
        <li>Search the venue, catering, and supplies catalog. Open item details to check capacity, dietary coverage, and wheelchair access.</li>
        <li>Ask the simulated agent for help comparing options. Its responses are canned demonstration messages, not live model advice.</li>
        <li>Select items for your plan and review the combined cost. Check budget, venue capacity, dietary coverage, and wheelchair accessibility.</li>
      </ul>
      <table>
        <caption>Illustrative tutorial plan — fictional, not a practice or experimental task answer. Prices are provisional USD.</caption>
        <thead><tr><th scope="col">Item</th><th scope="col">Example details</th><th scope="col">Cost</th></tr></thead>
        <tbody>
          <tr><th scope="row">Example Hall</th><td>24 seats; step-free access</td><td>$90</td></tr>
          <tr><th scope="row">Example Meal</th><td>20 servings; vegetarian coverage</td><td>$160</td></tr>
          <tr><th scope="row">Example Supplies</th><td>Event essentials package</td><td>$40</td></tr>
        </tbody>
      </table>
      <p>
        For an example event with 20 attendees, vegetarian meals, wheelchair access,
        and a $350 budget, this $290 plan meets all four constraints. Inspect the
        details rather than assuming every catalog option meets the requirements.
      </p>
      <h3>Four checkpoints and two routing conditions</h3>
      <p>Work through Venue → Catering → Supplies → Final constraint check. The selected model stays fixed throughout each stage.</p>
      <ul>
        <li><strong>Automatic:</strong> a simulated router recommendation and reason are shown and applied directly. You do not choose or confirm a model.</li>
        <li><strong>Override:</strong> independently choose small or large and lock your initial choice. Only then see the recommendation and reason; retain or change your choice and confirm the final model.</li>
      </ul>
      <p>Task assignments are provided by the demo. You do not choose your scenario or condition.</p>
      <h3>Practice, submission, and workload questions</h3>
      <p>
        Practice uses a separate scenario and does not count toward experimental
        records. For now, practice is untimed and uses a fixed simulated small model;
        this treatment is provisional. No workload survey follows practice.
      </p>
      <p>
        Each experimental task lasts up to 15 minutes from when its requirements
        appear. You can submit an incomplete or invalid plan without being forced
        to repair it. At submission or timeout, your current work is retained and
        you proceed to that task’s six-question NASA-TLX workload survey.
      </p>
      <button type="button" disabled={pending} onClick={onContinue}>Continue to practice</button>
    </>
  );
}
