import type { ProcessStep } from '#/lib/expert-api'

const HIDDEN_PHASES = new Set(['started', 'saving'])

export function compressProcessTrace(steps: ProcessStep[]): ProcessStep[] {
  const compressed: ProcessStep[] = []
  for (const step of steps) {
    if (step.kind === 'status' && HIDDEN_PHASES.has(step.phase)) continue
    const last = compressed[compressed.length - 1]
    if (
      step.kind === 'status' &&
      last?.kind === 'status' &&
      last.phase === step.phase
    ) {
      compressed[compressed.length - 1] = step
      continue
    }
    compressed.push(step)
  }
  return compressed
}

export function formatDurationMs(ms: number): string {
  const seconds = Math.max(1, Math.round(ms / 1000))
  return `${seconds}s`
}

export function liveActivityLabel(steps: ProcessStep[]): string {
  const runningTool = [...steps].reverse().find(
    (step) => step.kind === 'tool' && step.status === 'running',
  )
  if (runningTool?.kind === 'tool') {
    return runningTool.detail
      ? `${runningTool.label} · ${runningTool.detail}`
      : runningTool.label
  }
  const lastStatus = [...steps].reverse().find((step) => step.kind === 'status')
  if (lastStatus?.kind === 'status') return lastStatus.label
  return '正在思考…'
}

export function stepDisplayText(step: ProcessStep): string {
  if (step.kind === 'tool') {
    return step.detail ? `${step.label} · ${step.detail}` : step.label
  }
  return step.label
}
