import type { CatalogItem, Plan, Scenario, ScenarioId } from '../services/experiment.types.ts';

export const scenarios: Scenario[] = [
  { id: 'practice', title: 'Practice team lunch', requirements: { budgetCents: 50000, attendees: 15, dietaryNeeds: ['vegetarian'], wheelchairRequired: true }, provisional: true },
  { id: 'A', title: 'Company workshop', requirements: { budgetCents: 100000, attendees: 40, dietaryNeeds: ['vegetarian', 'gluten-free'], wheelchairRequired: true }, provisional: true },
  { id: 'B', title: 'Company celebration', requirements: { budgetCents: 140000, attendees: 60, dietaryNeeds: ['vegan', 'nut-free'], wheelchairRequired: true }, provisional: true },
];

// Synthetic, fixed-price packages; quantities are not editable in this demo.
export const catalog: CatalogItem[] = scenarios.flatMap((scenario, index) => {
  const { id, requirements: r } = scenario;
  const venuePrice = [10000, 30000, 50000][index];
  const cateringPrice = [20000, 40000, 60000][index];
  const supplyPrice = index === 0 ? 5000 : 10000;
  const venue = { scenarioId: id, category: 'venue' as const, priceCents: venuePrice, summary: 'A welcoming event space.', capacity: r.attendees, wheelchairAccessible: true };
  const food = { scenarioId: id, category: 'catering' as const, priceCents: cateringPrice, summary: 'A shared meal package.', servings: r.attendees, dietaryCoverage: r.dietaryNeeds };
  return [
    { ...venue, id: `${id}-venue-good`, name: `${id} Meadow Hall`, details: 'Capacity covers the guest list. Step-free entrance and accessible event room.' },
    { ...venue, id: `${id}-venue-capacity`, name: `${id} Garden Room`, capacity: r.attendees - 5, details: `Maximum event capacity: ${r.attendees - 5}.` },
    { ...venue, id: `${id}-venue-access`, name: `${id} Loft Room`, wheelchairAccessible: false, details: 'Event room is upstairs; no lift or step-free route.' },
    { ...food, id: `${id}-food-good`, name: `${id} Harvest Kitchen`, details: `Serves ${r.attendees}; covers ${r.dietaryNeeds.join(', ')} requirements.` },
    { ...food, id: `${id}-food-diet`, name: `${id} Classic Kitchen`, dietaryCoverage: [], details: 'Standard menu; the required dietary alternatives are not included.' },
    { ...food, id: `${id}-food-servings`, name: `${id} Riverside Kitchen`, servings: r.attendees - 5, details: `Package serves only ${r.attendees - 5} guests.` },
    { id: `${id}-supplies-good`, scenarioId: id, category: 'supplies' as const, name: `${id} Basic Supplies`, summary: 'Event essentials.', priceCents: supplyPrice, details: 'Complete fixed-price supplies package.' },
    { id: `${id}-supplies-cost`, scenarioId: id, category: 'supplies' as const, name: `${id} Premium Supplies`, summary: 'Premium event essentials.', priceCents: r.budgetCents - venuePrice - cateringPrice + 10000, details: 'Complete fixed-price supplies package. Check the combined venue, catering, and supplies cost against the budget.' },
  ];
});

// Verification references only; never returned by the participant-facing service.
export const feasiblePlans: Record<ScenarioId, Plan> = Object.fromEntries(
  scenarios.map(({ id }) => [id, { venue: `${id}-venue-good`, catering: `${id}-food-good`, supplies: [`${id}-supplies-good`] }]),
) as Record<ScenarioId, Plan>;
