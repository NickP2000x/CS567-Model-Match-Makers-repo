import type { CatalogItem, Plan, Scenario, ScenarioId } from '../services/experiment.types.ts';

export const scenarios: Scenario[] = [
  { id: 'practice', title: 'Practice team lunch', requirements: { budgetCents: 50000, attendees: 15, dietaryNeeds: ['vegetarian'], wheelchairRequired: true, requiredSupplies: ['name cards'], area: { id: 'riverside', name: 'Riverside' } }, provisional: true },
  { id: 'A', title: 'Company workshop', requirements: { budgetCents: 100000, attendees: 40, dietaryNeeds: ['vegetarian', 'gluten-free'], wheelchairRequired: true, requiredSupplies: ['name cards', 'display boards'], area: { id: 'north-quarter', name: 'North Quarter' } }, provisional: true },
  { id: 'B', title: 'Company celebration', requirements: { budgetCents: 140000, attendees: 60, dietaryNeeds: ['vegan', 'nut-free'], wheelchairRequired: true, requiredSupplies: ['name cards', 'place settings'], area: { id: 'harbor-front', name: 'Harbor Front' } }, provisional: true },
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

// Nine generated A/B options per category bring each category to 15. IDs are neutral (e.g. A-venue-07)
// and each kind is visible only in the details, like the original distractors.
const generatedPlaces = {
  A: ['Summit', 'Pinecrest', 'Northgate', 'Ridgeview', 'Brookside', 'Stonebridge', 'Hillcrest', 'Westfield', 'Oakmont'],
  B: ['Anchor', 'Sandbar', 'Gullwing', 'Saltmarsh', 'Starfish', 'Breakwater', 'Seaglass', 'Bluewater', 'Compass'],
};
// Fictional areas outside the required one, used only by wrong-area venues.
const otherAreas = {
  A: [{ id: 'east-side', name: 'East Side' }, { id: 'old-town', name: 'Old Town' }],
  B: [{ id: 'hillside', name: 'Hillside' }, { id: 'market-district', name: 'Market District' }],
};
const venueStyles = [
  ['Hall', 'An open hall with a raised stage and tall windows.'],
  ['Room', 'A meeting room with built-in screens and a side table.'],
  ['Loft', 'A converted loft with exposed brick and a coffee bar.'],
  ['Pavilion', 'A pavilion with garden views and a covered terrace.'],
  ['Suite', 'A conference suite with a cloakroom and lounge seating.'],
  ['Centre', 'A community centre with a lobby for registration.'],
];
const cateringStyles = [
  ['Catering', 'A plated lunch with a soup and salad starter.'],
  ['Kitchen', 'A family-style lunch served on shared platters.'],
  ['Table', 'A grazing table with hot and cold dishes.'],
  ['Lunch Co.', 'Individually boxed lunches with a drink each.'],
  ['Bistro', 'A two-course bistro menu with dessert.'],
  ['Provisions', 'A deli spread with build-your-own options.'],
];
const supplyStyles = [
  ['Event Kit', 'A boxed kit of materials for meetings and receptions.'],
  ['Host Pack', 'A reusable set of hosting materials.'],
  ['Desk Set', 'A tidy set of tabletop materials for each seat.'],
  ['Room Pack', 'Materials for dressing a room before guests arrive.'],
  ['Welcome Set', 'An assortment of materials for the welcome table.'],
  ['Essentials Box', 'A compact box of everyday event materials.'],
];
// Mostly feasible options with detail-only distractors mixed in; each distractor fails one check.
const venueKinds = ['ok', 'elsewhere', 'short', 'ok', 'elsewhere', 'stairs', 'ok', 'elsewhere', 'ok'] as const;
const cateringKinds = ['ok', 'short', 'ok', 'no-diet', 'ok', 'partial', 'ok', 'short', 'ok'] as const;
const supplyKinds = ['full', 'first', 'second', 'other', 'full', 'none', 'first', 'second', 'full'] as const;
const venueOffsets = [-8000, 4000, -3000, 12000, -6000, 6500, 15000, -4500, 1500];
const cateringOffsets = [-6000, 3500, 9000, -2000, 14000, -7500, 5500, 1000, -4000];
const supplyPrices = [12000, 3000, 4500, 3500, 8500, 2000, 2500, 6000, 19000];

function generatedOptions(scenario: Scenario, venuePrice: number, cateringPrice: number): CatalogItem[] {
  const { id, requirements: r } = scenario as Scenario & { id: 'A' | 'B' };
  const places = generatedPlaces[id];
  const [first, second] = r.requiredSupplies;
  const other = id === 'A' ? 'place settings' : 'display boards';
  return places.flatMap((place, i) => {
    const number = String(i + 7).padStart(2, '0');
    const venueKind = venueKinds[i % 9];
    const capacity = venueKind === 'short' ? r.attendees - 2 - (i % 7) : r.attendees + (i * 3) % 25;
    const [venueType, venueSummary] = venueStyles[i % 6];
    const area = venueKind === 'elsewhere' ? otherAreas[id][i % 2] : r.area;
    const venueAccess = venueKind === 'stairs'
      ? `Event room is on the ${i % 2 ? 'second' : 'third'} floor; no lift or step-free route.`
      : 'Step-free entrance and accessible event room.';
    const cateringKind = cateringKinds[i % 9];
    const servings = cateringKind === 'short' ? r.attendees - 3 - (i % 5) : r.attendees + (i * 2) % 15;
    const coverage = cateringKind === 'no-diet' ? [] : cateringKind === 'partial' ? [r.dietaryNeeds[i % 2]] : r.dietaryNeeds;
    const [cateringType, cateringSummary] = cateringStyles[(i + 2) % 6];
    const cateringFacts = cateringKind === 'no-diet'
      ? `Serves ${servings}. Standard menu; none of the required dietary alternatives are included.`
      : cateringKind === 'partial'
        ? `Serves ${servings}. Covers ${coverage[0]} requirements only; ${r.dietaryNeeds[(i + 1) % 2]} coverage is not provided.`
        : `Serves ${servings}; covers ${r.dietaryNeeds.join(', ')} requirements.`;
    const supplyKind = supplyKinds[i % 9];
    const provides = { full: [first, second], first: [first], second: [second], other: [other], none: [] }[supplyKind];
    const [supplyType, supplySummary] = supplyStyles[(i + 4) % 6];
    const contents = [...provides, ...(i % 2 ? ['pens', 'napkins'] : ['table decorations', 'signage'])];
    return [
      { id: `${id}-venue-${number}`, scenarioId: id, category: 'venue' as const, name: `${place} ${venueType}`, summary: venueSummary,
        priceCents: venuePrice + venueOffsets[i], capacity, wheelchairAccessible: venueKind !== 'stairs', areaId: area.id,
        details: `Seated capacity: ${capacity}. ${venueAccess} Located in ${area.name}. Fixed room-hire price.` },
      { id: `${id}-food-${number}`, scenarioId: id, category: 'catering' as const, name: `${place} ${cateringType}`, summary: cateringSummary,
        priceCents: cateringPrice + cateringOffsets[i], servings, dietaryCoverage: coverage,
        details: `${cateringFacts} Fixed whole-package price.` },
      { id: `${id}-supplies-${number}`, scenarioId: id, category: 'supplies' as const, name: `${place} ${supplyType}`, summary: supplySummary,
        priceCents: supplyPrices[i], provides,
        details: `One fixed-price supplies package: ${contents.join(', ')}. Its price is added to other selected packages.` },
    ];
  });
}

// Fixed-seed shuffle: the same mixed order for every participant, the API, and the agent tools.
// Existing venues are all in the required area, so each still fails only its original check.
function inRequiredArea(items: CatalogItem[], area: Scenario['requirements']['area']): CatalogItem[] {
  return items.map(item => item.category !== 'venue' || item.areaId ? item
    : { ...item, areaId: area.id, details: `${item.details} Located in ${area.name}.` });
}

function shuffled<T>(items: T[], seed: number): T[] {
  const result = [...items];
  let state = seed;
  const random = () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

const orderedCatalog: CatalogItem[] = scenarios.flatMap((scenario, index) => {
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
    { id: `${id}-supplies-good`, scenarioId: id, category: 'supplies', name: names[6], summary: 'A coordinated set of stationery and table materials.', priceCents: supplyPrice, provides: r.requiredSupplies, details: `Complete fixed-price supplies package: ${r.requiredSupplies.join(', ')}, pens, and napkins. Its price counts toward the combined budget.` },
    { id: `${id}-supplies-cost`, scenarioId: id, category: 'supplies', name: names[7], summary: 'A presentation and table-decoration bundle.', priceCents: r.budgetCents - venuePrice - cateringPrice + 10000, provides: r.requiredSupplies, details: `Complete fixed-price supplies package: ${r.requiredSupplies.join(', ')}, printed programs, and table decorations. Check the combined venue, catering, and supplies cost against the budget.` },
  ];
  if (id === 'practice') return inRequiredArea(original, r.area);

  const extra = additionalNames[id];
  return inRequiredArea([...original,
    { ...venue, id: `${id}-venue-economy`, name: extra[0], priceCents: venuePrice - 5000, capacity: r.attendees + 5, summary: 'A community hall with a self-arranged seating layout.', details: `Seated capacity: ${r.attendees + 5}. Step-free entrance and accessible event room. Room hire includes tables and chairs; participants arrange the layout.` },
    { ...venue, id: `${id}-venue-premium`, name: extra[1], priceCents: venuePrice + 10000, capacity: r.attendees + 15, summary: 'A conference room with a furnished reception lounge.', details: `Seated capacity: ${r.attendees + 15}. Step-free entrance and accessible event room. Fixed room-hire price includes the reception lounge.` },
    { ...venue, id: `${id}-venue-near-capacity`, name: extra[2], priceCents: venuePrice - 2500, capacity: r.attendees - 1, summary: 'A meeting house with a furnished breakout corner.', details: `Seated capacity: ${r.attendees - 1}. Step-free entrance and accessible event room. The breakout corner does not provide additional event seating.` },
    { ...food, id: `${id}-food-economy`, name: extra[3], priceCents: cateringPrice - 5000, summary: 'A self-service lunch with labelled individual portions.', details: `Serves ${r.attendees}; covers ${r.dietaryNeeds.join(', ')} requirements. Fixed package price; self-service presentation.` },
    { ...food, id: `${id}-food-buffet`, name: extra[4], priceCents: cateringPrice + 5000, servings: r.attendees + 10, summary: 'A buffet assortment with shared mains and side dishes.', details: `Serves ${r.attendees + 10}; covers ${r.dietaryNeeds.join(', ')} requirements. Fixed price includes all portions and dish labels.` },
    { ...food, id: `${id}-food-partial`, name: extra[5], priceCents: cateringPrice - 2500, dietaryCoverage: r.dietaryNeeds.slice(0, 1), summary: 'A seasonal lunch selection with individually packed portions.', details: `Serves ${r.attendees}. Covers ${r.dietaryNeeds[0]} requirements only; ${r.dietaryNeeds[1]} coverage is not provided. Fixed whole-package price.` },
    { id: `${id}-supplies-stationery`, scenarioId: id, category: 'supplies', name: extra[6], priceCents: 2500, provides: ['name cards'], summary: 'A set of name cards, pens, and notepads.', details: 'One fixed-price stationery package: name cards, pens, and notepads.' },
    { id: `${id}-supplies-presentation`, scenarioId: id, category: 'supplies', name: extra[7], priceCents: 5000, provides: ['display boards'], summary: 'Reusable display boards and presentation materials.', details: 'One fixed-price display package: display boards, markers, and printed agenda holders.' },
    { id: `${id}-supplies-tableware`, scenarioId: id, category: 'supplies', name: extra[8], priceCents: 4000, provides: ['place settings'], summary: 'Table coverings, reusable place settings, and napkins.', details: 'One fixed-price table-service package: table coverings, place settings, and napkins. Its price is added to other selected packages.' },
    { id: `${id}-supplies-bundle`, scenarioId: id, category: 'supplies', name: extra[9], priceCents: 25000, provides: ['name cards', 'display boards', 'place settings'], summary: 'A combined display, stationery, and table-decoration set.', details: 'One fixed-price host bundle: name cards, display boards, place settings, and table decorations. Some contents overlap with individual supplies packages; selecting both still adds both prices. Consider the combined plan cost.' },
    ...generatedOptions(scenario, venuePrice, cateringPrice),
  ], r.area);
});

export const catalog: CatalogItem[] = shuffled(orderedCatalog, 567);

// Verification references only; never returned by the participant-facing service.
export const feasiblePlans: Record<ScenarioId, Plan> = Object.fromEntries(
  scenarios.map(({ id }) => [id, { venue: `${id}-venue-good`, catering: `${id}-food-good`, supplies: [`${id}-supplies-good`] }]),
) as Record<ScenarioId, Plan>;

// Additional researcher-only examples exercise distinct feasible choices, not an answer ranking.
export const alternativeFeasiblePlans = Object.fromEntries(
  (['A', 'B'] as const).map(id => [id, [
    { venue: `${id}-venue-economy`, catering: `${id}-food-economy`, supplies: [`${id}-supplies-stationery`, id === 'A' ? 'A-supplies-presentation' : 'B-supplies-tableware'] },
    { venue: `${id}-venue-premium`, catering: `${id}-food-buffet`, supplies: [`${id}-supplies-stationery`, id === 'A' ? 'A-supplies-presentation' : 'B-supplies-tableware'] },
  ]]),
) as Record<'A' | 'B', Plan[]>;
