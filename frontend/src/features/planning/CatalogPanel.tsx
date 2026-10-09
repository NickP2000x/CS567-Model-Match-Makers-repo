import { useState } from 'react';
import type { FormEvent } from 'react';
import type { CatalogItem, CatalogSummary, Category, Plan } from '../../services/experiment.types';
import { money } from './format';

interface CatalogProps {
  results: CatalogSummary[];
  details: Record<string, CatalogItem>;
  expandedItem: string | null;
  plan: Plan;
  pending: boolean;
  onSearch: (query: string, category: Category | '') => Promise<boolean>;
  onInspect: (id: string) => void;
  onSelect: (item: CatalogSummary) => void;
}

export function CatalogPanel({ results, details, expandedItem, plan, pending, onSearch, onInspect, onSelect }: CatalogProps) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<Category | ''>('');

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSearch(query, category);
  }

  return (
    <section className="workspace-panel" aria-labelledby="catalog-title">
      <h3 id="catalog-title">Catalog</h3>
      <form onSubmit={search} className="catalog-search">
        <label htmlFor="catalog-query">Search catalog</label>
        <input id="catalog-query" type="search" value={query} disabled={pending}
          onChange={event => setQuery(event.target.value)} />
        <label htmlFor="catalog-category">Category</label>
        <select id="catalog-category" value={category} disabled={pending}
          onChange={event => setCategory(event.target.value as Category | '')}>
          <option value="">All categories</option>
          <option value="venue">Venues</option>
          <option value="catering">Catering</option>
          <option value="supplies">Supplies</option>
        </select>
        <button type="submit" disabled={pending}>Search</button>
      </form>
      <p role="status" className="catalog-count">{results.length} catalog {results.length === 1 ? 'option' : 'options'}</p>
      <div className="catalog-results">
        {results.length === 0 && <p>No matching options. Change the search or category and try again.</p>}
        {results.map(item => {
          const selected = item.category === 'supplies' ? plan.supplies.includes(item.id) : plan[item.category] === item.id;
          const expanded = expandedItem === item.id;
          const detail = expanded ? details[item.id] : null;
          return (
            <article key={item.id} className={`catalog-card${selected ? ' selected-card' : ''}`} aria-label={item.name}>
              <h4>{item.name}</h4>
              <p className="catalog-summary">{item.category} · {money(item.priceCents)}<br />{item.summary}</p>
              <div className="card-actions">
                <button type="button" className="secondary" disabled={pending} aria-expanded={expanded}
                  aria-controls={expanded ? `details-${item.id}` : undefined}
                  onClick={() => onInspect(item.id)}>{expanded ? 'Hide details' : 'Inspect details'}</button>
                <button type="button" disabled={pending || selected} onClick={() => onSelect(item)}>
                  {selected ? 'Selected in plan' : 'Add to plan'}
                </button>
              </div>
              {detail && (
                <div id={`details-${item.id}`} className="item-details">
                  <p>{detail.details}</p>
                  <dl>
                    {detail.capacity !== undefined && <><dt>Capacity</dt><dd>{detail.capacity} guests</dd></>}
                    {detail.wheelchairAccessible !== undefined && <><dt>Wheelchair access</dt><dd>{detail.wheelchairAccessible ? 'Available' : 'Not available'}</dd></>}
                    {detail.servings !== undefined && <><dt>Servings</dt><dd>{detail.servings}</dd></>}
                    {detail.dietaryCoverage !== undefined && <><dt>Dietary coverage</dt><dd>{detail.dietaryCoverage.length ? detail.dietaryCoverage.join(', ') : 'No required alternatives'}</dd></>}
                  </dl>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
