import React from "react"
import ReactDOM from "react-dom/client"
import "./index.css"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import AuthGate from "@/components/AuthGate"

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthGate />
    </QueryClientProvider>
  </React.StrictMode>,
)