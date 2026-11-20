import type { CatalogSummary, Category, Checkpoint, Constraints } from '../../services/experiment.types';

// Provisional, pending researcher approval: a stage is complete once the item it chooses meets
// that stage's constraints; the workspace then moves on automatically.
const stageConstraints: Record<Checkpoint, (keyof Constraints)[]> = {
  Venue: ['capacity', 'accessibility', 'location'],
  Catering: ['dietary'],
  Supplies: ['supplies'],
  'Final constraint check': [],
};

export function stageCategory(checkpoint: Checkpoint): Category | null {
  return checkpoint === 'Venue' ? 'venue' : checkpoint === 'Catering' ? 'catering'
    : checkpoint === 'Supplies' ? 'supplies' : null;
}

export function stageComplete(checkpoint: Checkpoint, constraints: Constraints) {
  const keys = stageConstraints[checkpoint];
  return keys.length > 0 && keys.every(key => constraints[key]);
}

// Same matching as the service's searchCatalog: name or summary text, then category.
export function catalogMatches(item: CatalogSummary, query: string, category: Category | '') {
  return (!category || item.category === category)
    && `${item.name} ${item.summary}`.toLowerCase().includes(query.trim().toLowerCase());
}
