'use client';

// Byline: Codex · GPT-5 · 2026-08-16

import { useState, useCallback } from 'react';
import { ModelSelector } from './components/ModelSelector';
import { InputEditor } from './components/InputEditor';
import { ResultsTable } from './components/ResultsTable';
import { ExportButton } from './components/ExportButton';
import { comparisonApi, ComparisonResponse, ProviderConfig } from '@/lib/classification-api';

const DEFAULT_CATEGORIES = ['platform', 'legal', 'personal_history', 'context'];
const DEFAULT_PROVIDERS: ProviderConfig[] = [
  { provider: 'portkey', temperature: 0, max_tokens: 1024 },
];

export default function ClassificationTestPage() {
  const [providers, setProviders] = useState<ProviderConfig[]>(DEFAULT_PROVIDERS);
  const [categories, setCategories] = useState<string[]>(DEFAULT_CATEGORIES);
  const [texts, setTexts] = useState<string[]>(['']);
  const [includeSentiment, setIncludeSentiment] = useState(true);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [results, setResults] = useState<ComparisonResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const handleProvidersChange = useCallback((newProviders: ProviderConfig[]) => {
    setProviders(newProviders);
  }, []);

  const handleCategoriesChange = useCallback((newCategories: string[]) => {
    setCategories(newCategories);
  }, []);

  const handleTextsChange = useCallback((newTexts: string[]) => {
    setTexts(newTexts);
  }, []);

  const handleClear = useCallback(() => {
    setResults(null);
    setRunError(null);
  }, []);

  const handleRun = useCallback(async () => {
    const runnableTexts = texts.map((text) => text.trim()).filter(Boolean);
    if (runnableTexts.length === 0) {
      setRunError('Add at least one non-empty text before running the comparison.');
      return;
    }
    if (categories.length === 0) {
      setRunError('Add at least one classification category.');
      return;
    }
    if (providers.length === 0) {
      setRunError('Select at least one provider.');
      return;
    }

    setIsLoading(true);
    setRunError(null);
    try {
      const response = await comparisonApi.run({
        texts: runnableTexts,
        categories,
        providers,
        include_sentiment: includeSentiment,
        system_prompt: systemPrompt.trim() || undefined,
      });
      setResults(response);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : 'Comparison failed');
    } finally {
      setIsLoading(false);
    }
  }, [categories, includeSentiment, providers, systemPrompt, texts]);

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Classification & Sentiment Test Lab</h1>
            <p className="text-gray-600 mt-1">
              Compare classification and sentiment analysis across multiple LLM providers
            </p>
          </div>
          <ExportButton
            results={results}
            onClear={handleClear}
            disabled={!results}
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel - Configuration */}
          <div className="lg:col-span-1 space-y-6">
            <ModelSelector
              providers={providers}
              onChange={handleProvidersChange}
            />

            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-900 mb-3">Categories</h3>
              <div className="flex flex-wrap gap-2">
                {categories.map((cat, i) => (
                  <span key={cat} className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm flex items-center gap-1">
                    {cat}
                    <button
                      onClick={() => handleCategoriesChange(categories.filter((_, idx) => idx !== i))}
                      className="hover:text-blue-600"
                    >
                      ×
                    </button>
                  </span>
                ))}
                <CategoryInput onAdd={handleCategoriesChange} existing={categories} />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                System Prompt (optional)
              </label>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                placeholder="Custom system prompt for classification..."
              />
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={includeSentiment}
                onChange={(e) => setIncludeSentiment(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              Include Sentiment Analysis
            </label>
          </div>

          {/* Center Panel - Input */}
          <div className="lg:col-span-1">
            <InputEditor
              texts={texts}
              onChange={handleTextsChange}
              placeholder="Enter conversation chunk or AI chat text..."
            />
          </div>

          {/* Right Panel - Results */}
          <div className="lg:col-span-1">
            <ResultsTable
              results={results}
              isLoading={isLoading}
            />
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          {runError && (
            <div role="alert" className="w-full rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {runError}
            </div>
          )}
          <button
            type="button"
            onClick={() => void handleRun()}
            disabled={isLoading}
            className="rounded-md bg-blue-600 px-5 py-2.5 font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
          >
            {isLoading
              ? 'Running comparison…'
              : `Run ${providers.length} model${providers.length === 1 ? '' : 's'} across ${texts.filter((text) => text.trim()).length} text${texts.filter((text) => text.trim()).length === 1 ? '' : 's'}`}
          </button>
        </div>

        {/* Full-width Results Table (when results exist) */}
        {results && (
          <div className="mt-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Detailed Comparison</h2>
            <ResultsTable
              results={results}
              isLoading={false}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function CategoryInput({ onAdd, existing }: { onAdd: (cats: string[]) => void; existing: string[] }) {
  const [value, setValue] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim().toLowerCase();
    if (trimmed && !existing.includes(trimmed)) {
      onAdd([...existing, trimmed]);
      setValue('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Add category..."
        className="flex-1 px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <button
        type="submit"
        className="px-3 py-1 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
      >
        Add
      </button>
    </form>
  );
}
