import { useCase } from "@/context/CaseContext"
import UploadScreen from "@/components/screens/UploadScreen"
import ReviewScreen from "@/components/screens/ReviewScreen"
import SummaryScreen from "@/components/screens/SummaryScreen"

function AppContent() {
  const { state } = useCase()

  switch (state.currentScreen) {
    case "upload":
      return <UploadScreen />
    case "review":
      return <ReviewScreen />
    case "summary":
      return <SummaryScreen />
  }
}

export default function App() {
  return (
    <div className="min-h-screen">
      {/* Nav bar */}
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">A</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900 leading-tight">Alkhidmat OFSP</h1>
            <p className="text-xs text-gray-400">Document Intake System</p>
          </div>
        </div>
        <div className="text-xs text-gray-400">Orphan Family Support Program</div>
      </nav>
      <AppContent />
    </div>
  )
}
