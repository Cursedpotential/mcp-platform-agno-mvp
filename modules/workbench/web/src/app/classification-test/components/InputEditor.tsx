'use client';

import { useState, useCallback } from 'react';

interface InputEditorProps {
  texts: string[];
  onChange: (texts: string[]) => void;
  placeholder?: string;
}

function extractText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value !== 'object' || value === null) return JSON.stringify(value) ?? String(value);
  const record = value as Record<string, unknown>;
  const candidate = record.content ?? record.text ?? record.message ?? record.body;
  return typeof candidate === 'string' ? candidate : JSON.stringify(value) ?? String(value);
}

export function InputEditor({ texts, onChange, placeholder = 'Enter text to analyze...' }: InputEditorProps) {
  const [localTexts, setLocalTexts] = useState<string[]>(texts);

  // Sync with parent
  const handleChange = useCallback((index: number, value: string) => {
    const newTexts = [...localTexts];
    newTexts[index] = value;
    setLocalTexts(newTexts);
    onChange(newTexts);
  }, [localTexts, onChange]);

  const addText = useCallback(() => {
    const newTexts = [...localTexts, ''];
    setLocalTexts(newTexts);
    onChange(newTexts);
  }, [localTexts, onChange]);

  const removeText = useCallback((index: number) => {
    if (localTexts.length <= 1) return;
    const newTexts = localTexts.filter((_, i) => i !== index);
    setLocalTexts(newTexts);
    onChange(newTexts);
  }, [localTexts, onChange]);

  return (
    <div className="bg-white rounded-lg shadow h-full flex flex-col">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Input Texts</h3>
        <span className="text-sm text-gray-500">{localTexts.length} text(s)</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {localTexts.map((text, index) => (
          <div key={index} className="relative">
            <div className="flex items-start gap-2">
              <span className="text-sm text-gray-400 mt-2 w-6 text-right">{index + 1}.</span>
              <textarea
                value={text}
                onChange={(e) => handleChange(index, e.target.value)}
                placeholder={`${placeholder} (Text ${index + 1})`}
                rows={6}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm resize-y min-h-[100px]"
              />
              {localTexts.length > 1 && (
                <button
                  onClick={() => removeText(index)}
                  className="text-red-500 hover:text-red-700 p-1 mt-2"
                  title="Remove this text"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            <div className="text-right text-xs text-gray-500 mt-1">
              {text.length} characters
            </div>
          </div>
        ))}

        {localTexts.length < 10 && (
          <button
            onClick={addText}
            className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add another text
          </button>
        )}
      </div>

      <div className="p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <label className="flex items-center gap-2">
            <input type="checkbox" className="rounded border-gray-300 text-blue-600" />
            Load from file (JSON/JSONL)
          </label>
          <input
            type="file"
            accept=".json,.jsonl,.txt"
            className="text-sm"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              const text = await file.text();
              try {
                if (file.name.endsWith('.jsonl')) {
                  const lines = text.trim().split('\n').filter(Boolean);
                  const parsed: unknown[] = lines.map(l => JSON.parse(l));
                  // Try to extract text content from common formats
                  const extracted = parsed.map(extractText);
                  const newTexts = [...localTexts, ...extracted];
                  setLocalTexts(newTexts);
                  onChange(newTexts);
                } else if (file.name.endsWith('.json')) {
                  const parsed: unknown = JSON.parse(text);
                  // Handle arrays or objects with messages
                  const parsedRecord = typeof parsed === 'object' && parsed !== null
                    ? parsed as Record<string, unknown>
                    : null;
                  const nestedMessages = parsedRecord?.messages ?? parsedRecord?.chat_messages;
                  const messages: unknown[] = Array.isArray(parsed)
                    ? parsed
                    : Array.isArray(nestedMessages)
                      ? nestedMessages
                      : [parsed];
                  const extracted = messages.map(extractText);
                  const newTexts = [...localTexts, ...extracted];
                  setLocalTexts(newTexts);
                  onChange(newTexts);
                } else {
                  const newTexts = [...localTexts, text];
                  setLocalTexts(newTexts);
                  onChange(newTexts);
                }
              } catch {
                const newTexts = [...localTexts, text];
                setLocalTexts(newTexts);
                onChange(newTexts);
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}
