import type { CatalogSummary, Category, Task } from '../../services/experiment.types';
import { money } from './format';

interface PlanProps {
  task: Task;
  catalog: CatalogSummary[];
  budgetCents: number;
  pending: boolean;
  onRemove: (category: Category, id: string) => void;
  onSubmit: () => void;
}

const constraintLabels = { budget: 'Budget', capacity: 'Venue capacity', dietary: 'Dietary coverage', accessibility: 'Wheelchair accessibility' } as const;

export function PlanPanel({ task, catalog, budgetCents, pending, onRemove, onSubmit }: PlanProps) {
  function selected(id: string) {
    const item = catalog.find(option => option.id === id)!;
    return (
      <li key={id} className="plan-item">
        <span>{item.name}<br /><span className="item-price">{money(item.priceCents)}</span></span>
        <button type="button" className="secondary" disabled={pending}
          aria-label={`Remove ${item.name}`} onClick={() => onRemove(item.category, id)}>Remove</button>
      </li>
    );
  }

  return (
    <section className="workspace-panel plan-panel" aria-labelledby="plan-title">
      <h3 id="plan-title">Current event plan</h3>
      <h4>Venue</h4>
      {task.plan.venue ? <ul className="plan-items">{selected(task.plan.venue)}</ul> : <p>No venue selected.</p>}
      <h4>Catering</h4>
      {task.plan.catering ? <ul className="plan-items">{selected(task.plan.catering)}</ul> : <p>No catering selected.</p>}
      <h4>Supplies</h4>
      {task.plan.supplies.length ? <ul className="plan-items">{task.plan.supplies.map(selected)}</ul> : <p>No supplies selected.</p>}
      <p className="plan-total">Total: {money(task.totalCostCents)} / {money(budgetCents)}</p>
      <div aria-live="polite" aria-atomic="true">
        <h4>Four constraint checks</h4>
        <ul className="constraint-list">
          {(Object.keys(constraintLabels) as (keyof typeof constraintLabels)[]).map(key => (
            <li key={key} className={task.constraints[key] ? 'constraint-met' : 'constraint-unmet'}>
              {task.constraints[key] ? '✓' : '○'} {constraintLabels[key]}: {task.constraints[key] ? 'Met' : 'Not met'}
            </li>
          ))}
        </ul>
      </div>
      <p className="field-help">Provisional live feedback. Dietary coverage includes enough servings. Supplies completeness is not a fifth constraint.</p>
      <div className="plan-submit">
        <p>You may submit an incomplete or invalid plan at any checkpoint.</p>
        <button type="button" disabled={pending} onClick={onSubmit}>Submit Plan</button>
      </div>
    </section>
  );
}
