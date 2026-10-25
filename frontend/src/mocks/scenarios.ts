import type { CatalogItem, Plan, Scenario, ScenarioId } from '../services/experiment.types.ts';

export const scenarios: Scenario[] = [
  { id: 'practice', title: 'Practice team lunch', requirements: { budgetCents: 50000, attendees: 15, dietaryNeeds: ['vegetarian'], wheelchairRequired: true }, provisional: true },
  { id: 'A', title: 'Company workshop', requirements: { budgetCents: 100000, attendees: 40, dietaryNeeds: ['vegetarian', 'gluten-free'], wheelchairRequired: true }, provisional: true },
  { id: 'B', title: 'Company celebration', requirements: { budgetCents: 140000, attendees: 60, dietaryNeeds: ['vegan', 'nut-free'], wheelchairRequired: true }, provisional: true },
];

// Synthetic, fixed-price packages; quantities are not editable in this demo.
const vendorNames: Record<ScenarioId, string[]> = {
  practice: ['Meadow Hall', 'Garden Room', 'Cedar Room', 'Harvest Kitchen', 'Classic Kitchen', 'Riverside Kitchen', 'Basic Supplies', 'Premium Supplies'],
  A: ['Willow Conference Hall', 'Birch Meeting Room', 'Maple Suite', 'Orchard Catering', 'Market Table', 'Lakeside Catering', 'Workshop Essentials', 'Workshop Plus'],
  B: ['Harbor Events Hall', 'Beacon Room', 'Seabreeze Suite', 'Coastline Catering', 'Bay Table', 'Pier Kitchen', 'Celebration Essentials', 'Celebration Plus'],
};

const additionalNames = {
  A: ['Aspen Community Hall', 'Juniper Centre', 'Elm Meeting House', 'Fieldstone Lunches', 'Grove Buffet', 'Copper Lunch Co.', 'Workshop Stationery', 'Presentation Kit', 'Table Service Set', 'Workshop Host Bundle'],
  B: ['Marina Community Hall', 'Lighthouse Centre', 'Driftwood Meeting House', 'Tidal Table', 'Shoreline Buffet', 'Coral Catering', 'Celebration Stationery', 'Welcome Display Kit', 'Reception Table Set', 'Celebration Host Bundle'],
};

export const catalog: CatalogItem[] = scenarios.flatMap((scenario, index) => {
  const { id, requirements: r } = scenario;
  const names = vendorNames[id];
  const venuePrice = [10000, 30000, 50000][index];
  const cateringPrice = [20000, 40000, 60000][index];
  const supplyPrice = index === 0 ? 5000 : 10000;
  const venue = { scenarioId: id, category: 'venue' as const, priceCents: venuePrice, capacity: r.attendees, wheelchairAccessible: true };
  const food = { scenarioId: id, category: 'catering' as const, priceCents: cateringPrice, servings: r.attendees, dietaryCoverage: r.dietaryNeeds };
  // Keep existing IDs, prices, and scored facts stable for saved demonstration runs.
  const original: CatalogItem[] = [
    { ...venue, id: `${id}-venue-good`, name: names[0], summary: 'An event hall with an adjoining reception area.', details: `Seated capacity: ${r.attendees}. Step-free entrance and accessible event room. Fixed room-hire price.` },
    { ...venue, id: `${id}-venue-capacity`, name: names[1], summary: 'A meeting room with a central presentation area.', capacity: r.attendees - 5, details: `Seated capacity: ${r.attendees - 5}. Step-free entrance and accessible event room. Fixed room-hire price.` },
    { ...venue, id: `${id}-venue-access`, name: names[2], summary: 'An event suite with a separate welcome area.', wheelchairAccessible: false, details: `Seated capacity: ${r.attendees}. Event room is upstairs; no lift or step-free route. Fixed room-hire price.` },
    { ...food, id: `${id}-food-good`, name: names[3], summary: 'A shared lunch menu with individually labelled dishes.', details: `Serves ${r.attendees}; covers ${r.dietaryNeeds.join(', ')} requirements. The listed price is for the whole package.` },
    { ...food, id: `${id}-food-diet`, name: names[4], summary: 'A fixed-menu lunch with a selection of main dishes.', dietaryCoverage: [], details: `Serves ${r.attendees}. Standard menu; none of the required dietary alternatives are included. The listed price is for the whole package.` },
    { ...food, id: `${id}-food-servings`, name: names[5], summary: 'A boxed lunch collection with a shared dessert tray.', servings: r.attendees - 5, details: `Serves ${r.attendees - 5}; covers ${r.dietaryNeeds.join(', ')} requirements. The listed price is for the whole package.` },
    { id: `${id}-supplies-good`, scenarioId: id, category: 'supplies', name: names[6], summary: 'A coordinated set of stationery and table materials.', priceCents: supplyPrice, details: 'Complete fixed-price supplies package: name cards, pens, table signs, and napkins. Optional; supplies contribute to the combined budget, not an additional scored requirement.' },
    { id: `${id}-supplies-cost`, scenarioId: id, category: 'supplies', name: names[7], summary: 'A presentation and table-decoration bundle.', priceCents: r.budgetCents - venuePrice - cateringPrice + 10000, details: 'Complete fixed-price supplies package: display materials, printed programs, and table decorations. Optional; check the combined venue, catering, and supplies cost against the budget.' },
  ];
  if (id === 'practice') return original;

  const extra = additionalNames[id];
  return [...original,
    { ...venue, id: `${id}-venue-economy`, name: extra[0], priceCents: venuePrice - 5000, capacity: r.attendees + 5, summary: 'A community hall with a self-arranged seating layout.', details: `Seated capacity: ${r.attendees + 5}. Step-free entrance and accessible event room. Room hire includes tables and chairs; participants arrange the layout.` },
    { ...venue, id: `${id}-venue-premium`, name: extra[1], priceCents: venuePrice + 10000, capacity: r.attendees + 15, summary: 'A conference room with a furnished reception lounge.', details: `Seated capacity: ${r.attendees + 15}. Step-free entrance and accessible event room. Fixed room-hire price includes the reception lounge.` },
    { ...venue, id: `${id}-venue-near-capacity`, name: extra[2], priceCents: venuePrice - 2500, capacity: r.attendees - 1, summary: 'A meeting house with a furnished breakout corner.', details: `Seated capacity: ${r.attendees - 1}. Step-free entrance and accessible event room. The breakout corner does not provide additional event seating.` },
    { ...food, id: `${id}-food-economy`, name: extra[3], priceCents: cateringPrice - 5000, summary: 'A self-service lunch with labelled individual portions.', details: `Serves ${r.attendees}; covers ${r.dietaryNeeds.join(', ')} requirements. Fixed package price; self-service presentation.` },
    { ...food, id: `${id}-food-buffet`, name: extra[4], priceCents: cateringPrice + 5000, servings: r.attendees + 10, summary: 'A buffet assortment with shared mains and side dishes.', details: `Serves ${r.attendees + 10}; covers ${r.dietaryNeeds.join(', ')} requirements. Fixed price includes all portions and dish labels.` },
    { ...food, id: `${id}-food-partial`, name: extra[5], priceCents: cateringPrice - 2500, dietaryCoverage: r.dietaryNeeds.slice(0, 1), summary: 'A seasonal lunch selection with individually packed portions.', details: `Serves ${r.attendees}. Covers ${r.dietaryNeeds[0]} requirements only; ${r.dietaryNeeds[1]} coverage is not provided. Fixed whole-package price.` },
    { id: `${id}-supplies-stationery`, scenarioId: id, category: 'supplies', name: extra[6], priceCents: 2500, summary: 'A set of name cards, pens, and notepads.', details: 'One fixed-price stationery package. Optional; no minimum supply quantity is scored.' },
    { id: `${id}-supplies-presentation`, scenarioId: id, category: 'supplies', name: extra[7], priceCents: 5000, summary: 'Reusable display boards and presentation materials.', details: 'One fixed-price display package with boards, markers, and printed agenda holders. Optional; equipment coverage is not a scored requirement.' },
    { id: `${id}-supplies-tableware`, scenarioId: id, category: 'supplies', name: extra[8], priceCents: 4000, summary: 'Table coverings, reusable place settings, and napkins.', details: 'One fixed-price table-service package. Optional; its price is added to other selected packages.' },
    { id: `${id}-supplies-bundle`, scenarioId: id, category: 'supplies', name: extra[9], priceCents: 25000, summary: 'A combined display, stationery, and table-decoration set.', details: 'One fixed-price host bundle. Some contents overlap with individual supplies packages; selecting both still adds both prices. Optional; consider the combined plan cost.' },
  ];
});

// Verification references only; never returned by the participant-facing service.
export const feasiblePlans: Record<ScenarioId, Plan> = Object.fromEntries(
  scenarios.map(({ id }) => [id, { venue: `${id}-venue-good`, catering: `${id}-food-good`, supplies: [`${id}-supplies-good`] }]),
) as Record<ScenarioId, Plan>;

// Additional researcher-only examples exercise distinct feasible choices, not an answer ranking.
export const alternativeFeasiblePlans = Object.fromEntries(
  (['A', 'B'] as const).map(id => [id, [
    { venue: `${id}-venue-economy`, catering: `${id}-food-economy`, supplies: [`${id}-supplies-stationery`] },
    { venue: `${id}-venue-premium`, catering: `${id}-food-buffet`, supplies: [`${id}-supplies-tableware`] },
  ]]),
) as Record<'A' | 'B', Plan[]>;
