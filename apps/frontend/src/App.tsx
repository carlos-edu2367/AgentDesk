import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { StartupScreen } from './components/StartupScreen'
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
import { Conversations } from './views/Conversations'
import { ConversationView } from './views/ConversationView'
import { Settings } from './views/Settings'
import { Tools } from './views/Tools'
import { Memory } from './views/Memory'
import { Teams } from './views/Teams'
import { Skills } from './views/Skills'
import { Plugins } from './views/Plugins'
import { McpServers } from './views/McpServers'
import { AuditLogs } from './views/AuditLogs'

export function App() {
  return (
    <StartupScreen>
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />

          <Route path="agents" element={<Agents />} />
          <Route path="agents/new" element={<AgentForm />} />
          <Route path="agents/:id/edit" element={<AgentForm />} />

          <Route path="teams" element={<Teams />} />

          <Route path="providers" element={<Providers />} />
          <Route path="providers/new" element={<ProviderForm />} />
          <Route path="providers/:id/edit" element={<ProviderForm />} />

          <Route path="workspaces" element={<Workspaces />} />
          <Route path="workspaces/new" element={<WorkspaceForm />} />
          <Route path="workspaces/:id/edit" element={<WorkspaceForm />} />

          <Route path="executions" element={<Executions />} />
          <Route path="executions/run" element={<RunAgent />} />
          <Route path="executions/:id" element={<ExecutionDetail />} />

          <Route path="conversations" element={<Conversations />} />
          <Route path="conversations/:id" element={<ConversationView />} />

          <Route path="tools" element={<Tools />} />
          <Route path="mcp" element={<McpServers />} />
          <Route path="memory" element={<Memory />} />
          <Route path="skills" element={<Skills />} />
          <Route path="plugins" element={<Plugins />} />
          <Route path="audit" element={<AuditLogs />} />
          <Route path="settings" element={<Settings />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
    </StartupScreen>
  )
}
