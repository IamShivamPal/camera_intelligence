import React, { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

export const DashboardLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState<boolean>(false)

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090c10] text-[#e6edf3]">
      {/* Left Sidebar */}
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 bg-[#090c10]">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default DashboardLayout
