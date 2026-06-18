import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './views/Dashboard'
import { Agents } from './views/Agents'
import { AgentForm } from './views/AgentForm'
import { Providers } from './views/Providers'
import { ProviderForm } from './views/ProviderForm'
import { Workspaces } from './views/Workspaces'
import { WorkspaceForm } from './views/WorkspaceForm'
import { Executions } from './views/Executions'
import { ExecutionDetail } from './views/ExecutionDetail'
import { RunAgent } from './views/RunAgent'
import { Settings } from './views/Settings'

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />

          <Route path="agents" element={<Agents />} />
          <Route path="agents/new" element={<AgentForm />} />
          <Route path="agents/:id/edit" element={<AgentForm />} />

          <Route path="providers" element={<Providers />} />
          <Route path="providers/new" element={<ProviderForm />} />
          <Route path="providers/:id/edit" element={<ProviderForm />} />

          <Route path="workspaces" element={<Workspaces />} />
          <Route path="workspaces/new" element={<WorkspaceForm />} />
          <Route path="workspaces/:id/edit" element={<WorkspaceForm />} />

          <Route path="executions" element={<Executions />} />
          <Route path="executions/run" element={<RunAgent />} />
          <Route path="executions/:id" element={<ExecutionDetail />} />

          <Route path="settings" element={<Settings />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  )
}
