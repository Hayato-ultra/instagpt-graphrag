import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import GraphPage from './pages/GraphPage'
import SearchPage from './pages/SearchPage'
import NotebookPage from './pages/NotebookPage'
import AnalyzePage from './pages/AnalyzePage'
import EntitiesPage from './pages/EntitiesPage'
import SourcesPage from './pages/SourcesPage'
import AIResearchPage from './pages/AIResearchPage'
import ReviewPage from './pages/ReviewPage'
import SettingsPage from './pages/SettingsPage'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/analyze" element={<AnalyzePage />} />
            <Route path="/graph" element={<GraphPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/entities" element={<EntitiesPage />} />
            <Route path="/sources" element={<SourcesPage />} />
            <Route path="/notebook" element={<NotebookPage />} />
            <Route path="/ai-research" element={<AIResearchPage />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
