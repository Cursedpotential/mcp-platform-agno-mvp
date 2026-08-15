'use client';

import { toast } from 'sonner';

import { ComparisonResponse } from '@/lib/classification-api';

interface ExportButtonProps {
  results: ComparisonResponse | null;
  onClear: () => void;
  disabled?: boolean;
}

export function ExportButton({ results, onClear, disabled = false }: ExportButtonProps) {
  const handleExport = async (format: 'json' | 'csv') => {
    if (!results) return;

    try {
      const response = await fetch(`/api/comparison/export?format=${format}&include_raw=true`, {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `classification-comparison-${Date.now()}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Export failed:', err);
      toast.error(err instanceof Error ? err.message : 'Export failed');
    }
  };

  return (
    <div className="flex items-center gap-2">
      {results && !disabled && (
        <>
          <button
            onClick={() => handleExport('json')}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Export JSON
          </button>
          <button
            onClick={() => handleExport('csv')}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Export CSV
          </button>
        </>
      )}
      <button
        onClick={onClear}
        className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        disabled={disabled}
      >
        Clear Results
      </button>
    </div>
  );
}
