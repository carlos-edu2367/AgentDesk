import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { StartupScreen } from './components/StartupScreen'
import { RootRedirect } from './components/RootRedirect'
import { Agents } from './views/Agents'
import { AgentForm } from './views/AgentForm'
import { Teams } from './views/Teams'
import { ProviderForm } from './views/ProviderForm'
import { WorkspaceForm } from './views/WorkspaceForm'
import { ExecutionDetail } from './views/ExecutionDetail'
import { ConversationView } from './views/ConversationView'
import { Config } from './views/Config'

export function App() {
  return (
    <StartupScreen>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<RootRedirect />} />

            <Route path="agents" element={<Agents />} />
            <Route path="agents/new" element={<AgentForm />} />
            <Route path="agents/:id/edit" element={<AgentForm />} />

            <Route path="teams" element={<Teams />} />

            <Route path="providers/new" element={<ProviderForm />} />
            <Route path="providers/:id/edit" element={<ProviderForm />} />
            <Route path="workspaces/new" element={<WorkspaceForm />} />
            <Route path="workspaces/:id/edit" element={<WorkspaceForm />} />

            <Route path="conversations/:id" element={<ConversationView />} />
            <Route path="executions/:id" element={<ExecutionDetail />} />

            <Route path="config" element={<Navigate to="/config/providers" replace />} />
            <Route path="config/:section" element={<Config />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </HashRouter>
    </StartupScreen>
  )
}
