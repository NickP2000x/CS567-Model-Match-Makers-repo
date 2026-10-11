import { useEffect, useRef, useState } from 'react';
import type { CatalogItem, CatalogSummary, Category, ExperimentService, Scenario, TaskId } from '../../services/experiment.types';
import { useExperiment } from '../../services/useExperiment';
import { RoutingPanel } from '../routing/RoutingPanel';
import { TaskCountdown } from '../study/TaskCountdown';
import { CatalogPanel } from './CatalogPanel';
import { ConversationPanel } from './ConversationPanel';
import { PlanPanel } from './PlanPanel';
import { money } from './format';

interface WorkspaceProps {
  service: ExperimentService;
  taskId: TaskId;
  pending: boolean;
  perform: (operation: () => Promise<void>) => Promise<boolean>;
  onFinish: (taskId: TaskId, reason?: 'submitted' | 'timed-out') => Promise<boolean>;
}

export function PlanningWorkspace({ service, taskId, pending: actionPending, perform, onFinish }: WorkspaceProps) {
  const state = useExperiment(service);
  const scenarioId = taskId === 'practice' ? 'practice' : state.assignments[taskId === 'task-1' ? 0 : 1].scenarioId;
  const [data, setData] = useState<{ scenario: Scenario; catalog: CatalogSummary[] } | null>(null);
  const [results, setResults] = useState<CatalogSummary[]>([]);
  const [details, setDetails] = useState<Record<string, CatalogItem>>({});
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const starting = useRef(false);
  const task = state.tasks[taskId];
  const pending = actionPending || state.pendingOperations > 0;

  useEffect(() => {
    let cancelled = false;
    setLoadFailed(false);
    async function load() {
      try {
        const scenario = await service.getScenario(scenarioId);
        if (cancelled) return;
        const catalog = await service.searchCatalog(scenarioId);
        if (cancelled) return;
        setData({ scenario, catalog });
        setResults(catalog);
      } catch {
        if (!cancelled) setLoadFailed(true);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [service, scenarioId, taskId, attempt]);

  useEffect(() => {
    // Start only after the requirements header has been committed to the screen.
    if (!data || task || starting.current || service.getSnapshot().step !== taskId) return;
    starting.current = true;
    void service.beginTask().catch(() => setLoadFailed(true)).finally(() => { starting.current = false; });
  }, [data, task, service, taskId, attempt]);

  if (!data || (loadFailed && !task)) {
    return loadFailed ? (
      <>
        <p>Could not load the workspace. Your current demo state is retained.</p>
        <button type="button" disabled={pending} onClick={() => setAttempt(value => value + 1)}>Retry loading workspace</button>
      </>
    ) : <p role="status">Loading the planning workspace…</p>;
  }

  function selectItem(item: CatalogSummary) {
    void perform(async () => {
      const current = service.getSnapshot().tasks[taskId]!;
      const plan = { ...current.plan, supplies: [...current.plan.supplies] };
      if (item.category === 'supplies') plan.supplies.push(item.id);
      else plan[item.category] = item.id;
      await service.updatePlan(plan);
    });
  }

  function removeItem(category: Category, id: string) {
    void perform(async () => {
      const current = service.getSnapshot().tasks[taskId]!;
      const plan = { ...current.plan, supplies: [...current.plan.supplies] };
      if (category === 'supplies') plan.supplies = plan.supplies.filter(itemId => itemId !== id);
      else plan[category] = null;
      await service.updatePlan(plan);
    });
  }

  function inspectItem(id: string) {
    if (expandedItem === id) { setExpandedItem(null); return; }
    if (details[id]) { setExpandedItem(id); return; }
    void perform(async () => {
      const item = await service.inspectItem(id);
      setDetails(current => ({ ...current, [id]: item }));
      setExpandedItem(id);
    });
  }

  const { requirements } = data.scenario;
  return (
    <>
      <header className="task-requirements" aria-labelledby="requirements-title">
        <div>
          <h3 id="requirements-title">{data.scenario.title}</h3>
          <p>
            {requirements.attendees} guests · Budget {money(requirements.budgetCents)} ·
            {' '}Dietary needs: {requirements.dietaryNeeds.join(', ')} ·
            {' '}Wheelchair access {requirements.wheelchairRequired ? 'required' : 'not required'}
          </p>
        </div>
        {task ? <TaskCountdown task={task} onTimeout={() => onFinish(taskId, 'timed-out')} />
          : <p className="time-remaining">{taskId === 'practice' ? 'Time: untimed practice' : 'Time remaining: 15:00'}</p>}
      </header>
      <p className="workspace-notice">
        Provisional demonstration: fictional catalog and prices (USD), live constraint feedback.
        {taskId === 'practice' ? ' Practice is excluded from experimental records and uses a fixed simulated small model. No survey follows practice.'
          : ` Scenario ${scenarioId} · ${state.assignments[taskId === 'task-1' ? 0 : 1].condition === 'automatic' ? 'Automatic' : 'Override'} routing.`}
      </p>
      {!task ? <p role="status">Preparing the planning task…</p> : <div className="workspace-panels">
        <CatalogPanel results={results} details={details} expandedItem={expandedItem}
          plan={task.plan} pending={pending} onInspect={inspectItem} onSelect={selectItem}
          onSearch={(query, category) => perform(async () => {
            const found = await service.searchCatalog(scenarioId, query, category || undefined);
            setResults(found);
            setExpandedItem(null);
          })} />
        <ConversationPanel task={task} pending={pending} simulated={state.simulated}
          routing={<RoutingPanel key={`${task.id}-${task.checkpoint}`} task={task}
            service={service} pending={pending} perform={perform} />}
          onSend={text => perform(() => service.sendMessage(text))}
          onAdvance={() => { void perform(() => service.advanceCheckpoint()); }} />
        <PlanPanel task={task} catalog={data.catalog} pending={pending}
          budgetCents={requirements.budgetCents} onRemove={removeItem}
          onSubmit={() => { void onFinish(taskId); }} />
      </div>}
    </>
  );
}
