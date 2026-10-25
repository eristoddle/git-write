import type { PluginApi } from '@veneer/api'

export const FEEDBACK_BRANCH_SETTING = 'gitwrite:feedback-branch'
export const DEFAULT_FEEDBACK_BRANCH = 'feedback'

/** The branch that holds readers' comments: the writer's setting, else GitWrite's `feedback`. */
export async function feedbackBranch(api: PluginApi): Promise<string> {
  const value = await api.settings.get(FEEDBACK_BRANCH_SETTING)
  const name = typeof value === 'string' ? value.trim() : ''
  return name === '' ? DEFAULT_FEEDBACK_BRANCH : name
}
