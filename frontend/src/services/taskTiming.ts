export const EXPERIMENTAL_TASK_MS = 15 * 60 * 1000;

export function remainingSeconds(deadline: number, at: number): number {
  return Math.max(0, Math.ceil((deadline - at) / 1000));
}
