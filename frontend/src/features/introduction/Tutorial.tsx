import { useEffect, useRef, useState } from 'react';

const guide = [
  { title: 'Requirements and time', text: 'Read the guest count, budget, dietary needs, and access requirements. Each study task has up to 15 minutes.', area: [12, 12, 676, 54] },
  { title: 'Catalog', text: 'Search venues, catering, and supplies. Inspect details before choosing; summaries may leave out important facts.', area: [12, 76, 218, 220] },
  { title: 'AI planning agent', text: 'Ask for simulated help. Automatic applies the recommendation directly. Override: choose independently, lock, then see the recommendation and retain/change before confirming.', area: [240, 76, 218, 220] },
  { title: 'Current event plan', text: 'Add or remove items and review the combined cost and four constraint checks. You can revise plan items at any stage.', area: [468, 76, 220, 220] },
  { title: 'Checkpoints', text: 'Venue → Catering → Supplies → Final constraint check. Move forward through stages; each chosen model stays fixed throughout its stage.', area: [250, 113, 198, 39] },
  { title: 'Submit plan', text: 'Submit at any checkpoint, even with an incomplete or invalid plan. Submission or timeout leads to the task’s workload survey. Practice is untimed and has no survey.', area: [548, 305, 140, 32] },
];

export function Tutorial({ pending, onContinue }: { pending: boolean; onContinue: () => void }) {
  const [index, setIndex] = useState(0);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => { title.current?.focus(); }, [index]);
  const current = guide[index];
  return (
    <>
      <p className="field-help">Illustration only — a separate fictional example, not a study-task answer.</p>
      <svg className="interface-guide" viewBox="0 0 700 350" role="img" aria-labelledby="guide-image-title guide-image-description">
        <title id="guide-image-title">Planning interface: {current.title} highlighted</title>
        <desc id="guide-image-description">Three-panel example with catalog left, agent center, plan right, requirements above and Submit below. {current.text}</desc>
        <rect width="700" height="350" fill="#202326" />
        {[ [12,12,676,54], [12,76,218,220], [240,76,218,220], [468,76,220,220], [548,305,140,32] ].map((area, key) =>
          <rect key={key} x={area[0]} y={area[1]} width={area[2]} height={area[3]} fill="#2b3036" stroke="#818b96" />)}
        <g fill="#f1f3f5" fontSize="15" fontFamily="system-ui, sans-serif">
          <text x="24" y="35">Event requirements</text><text x="24" y="55" fontSize="12">Example: 20 guests · $350 budget · Vegetarian · Wheelchair access</text>
          <text x="554" y="35">Time remaining</text>
          <text x="24" y="103">Catalog</text><text x="24" y="140">Search and inspect</text><text x="24" y="176">Example Hall · $90</text><text x="24" y="206">Example Meal · $160</text><text x="24" y="236">Example Supplies · $40</text>
          <text x="252" y="103">AI planning agent</text><text x="252" y="132" fontSize="12">Venue → Catering → Supplies</text><text x="252" y="147" fontSize="12">→ Final constraint check</text>
          <text x="252" y="183">Model choice at checkpoint</text><text x="252" y="224">Conversation</text><text x="252" y="260">Ask for help…</text>
          <text x="480" y="103">Current event plan</text><text x="480" y="142">Venue / Catering / Supplies</text><text x="480" y="179">Example total: $290 / $350</text>
          <text x="480" y="216">Budget · Capacity</text><text x="480" y="242">Dietary · Accessibility</text><text x="566" y="327">Submit plan</text>
        </g>
        <rect x={current.area[0]} y={current.area[1]} width={current.area[2]} height={current.area[3]} fill="none" stroke="#9dc8ff" strokeWidth="4" />
      </svg>
      <p className="field-help">Guide {index + 1} of {guide.length}</p>
      <h2 ref={title} tabIndex={-1}>{current.title}</h2>
      <p>{current.text}</p>
      <div className="actions">
        <button type="button" className="secondary" disabled={pending || index === 0} onClick={() => setIndex(value => value - 1)}>Back</button>
        <button type="button" disabled={pending} onClick={() => index === guide.length - 1 ? onContinue() : setIndex(value => value + 1)}>
          {index === guide.length - 1 ? 'Finish instructions' : 'Next'}
        </button>
      </div>
    </>
  );
}
