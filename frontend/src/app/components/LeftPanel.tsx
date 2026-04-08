import { X } from 'lucide-react';

interface LeftPanelProps {
  children: React.ReactNode;
}

export function LeftPanel({ children }: LeftPanelProps) {
  return (
    <div className="fixed left-0 top-0 h-full w-64 bg-gray-50 overflow-y-auto">
      <div className="p-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-6">Insights</h2>
        {children}
      </div>
    </div>
  );
}