'use client';

import React, { useState } from 'react';
import { ComparisonResponse, ComparisonResult } from '@/lib/classification-api';

interface ResultsTableProps {
  results: ComparisonResponse | null;
  isLoading: boolean;
}

const SENTIMENT_COLORS: Record<string, string> = {
  positive: 'bg-green-100 text-green-800',
  negative: 'bg-red-100 text-red-800',
  neutral: 'bg-gray-100 text-gray-800',
  mixed: 'bg-yellow-100 text-yellow-800',
};

const SENTIMENT_ICONS: Record<string, string> = {
  positive: '���',
  negative: '���',
  neutral: '→',
  mixed: '���',
};

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const color = confidence >= 0.8 ? 'bg-green-500' : confidence >= 0.6 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
      <div className={`${color} h-full rounded-full transition-all`} style={{ width: `${confidence * 100}%` }} />
    </div>
  );
}

function EmotionTags({ emotions }: { emotions: Record<string, number> }) {
  if (!emotions || Object.keys(emotions).length === 0) return null;
  const topEmotions = Object.entries(emotions)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {topEmotions.map(([emotion, score]) => (
        <span key={emotion} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
          {emotion}: {(score * 100).toFixed(0)}%
        </span>
      ))}
    </div>
  );
}

export function ResultsTable({ results, isLoading }: ResultsTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4" />
        <p className="text-gray-600">Running comparison across providers...</p>
      </div>
    );
  }

  if (!results || results.results.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        <p>No results yet. Configure providers and texts, then click &quot;Run Analysis&quot;.</p>
      </div>
    );
  }

  // Group results by text index
  const textGroups = new Map<number, ComparisonResult[]>();
  results.results.forEach(r => {
    const group = textGroups.get(r.text_index) || [];
    group.push(r);
    textGroups.set(r.text_index, group);
  });

  const sortedIndices = Array.from(textGroups.keys()).sort((a, b) => a - b);

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {/* Summary Cards */}
      <div className="p-4 border-b border-gray-200 bg-gray-50 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-600">{results.summary.total_texts}</div>
          <div className="text-xs text-gray-500">Texts Analyzed</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-purple-600">{results.summary.total_providers}</div>
          <div className="text-xs text-gray-500">Providers</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-600">{formatLatency(results.summary.avg_latency_ms)}</div>
          <div className="text-xs text-gray-500">Avg Latency</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-orange-600">{results.summary.category_agreement_rate.toFixed(0)}%</div>
          <div className="text-xs text-gray-500">Category Agreement</div>
        </div>
      </div>

      {/* Results Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-8">#</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Text Preview</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Provider / Model</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Confidence</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sentiment</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Latency</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {sortedIndices.map((textIndex) => {
              const group = textGroups.get(textIndex)!;
              const firstResult = group[0];

              return (
                <React.Fragment key={textIndex}>
                  {/* Main row - first provider result */}
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{textIndex + 1}</td>
                    <td className="px-4 py-3 text-sm text-gray-600 max-w-xs truncate" title={firstResult.text_preview}>
                      {firstResult.text_preview}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <div className="font-medium text-gray-900 capitalize">{firstResult.provider}</div>
                      <div className="text-xs text-gray-500">{firstResult.model_id}</div>
                    </td>
                    <td className="px-4 py-3">
                      {firstResult.classification && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {firstResult.classification.category}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {firstResult.classification && (
                        <ConfidenceBar confidence={firstResult.classification.confidence} />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {firstResult.sentiment && (
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${SENTIMENT_COLORS[firstResult.sentiment.sentiment]}`}>
                          {SENTIMENT_ICONS[firstResult.sentiment.sentiment]} {firstResult.sentiment.sentiment}
                          <span className="ml-1 text-xs opacity-75">({firstResult.sentiment.score.toFixed(2)})</span>
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">{formatLatency(firstResult.latency_ms)}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => {
                          setExpandedRows(prev => {
                            const next = new Set(prev);
                            if (next.has(textIndex)) next.delete(textIndex);
                            else next.add(textIndex);
                            return next;
                          });
                        }}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        {expandedRows.has(textIndex) ? '��' : '��'}
                      </button>
                    </td>
                  </tr>

                  {/* Additional provider rows for same text */}
                  {group.slice(1).map((result, i) => (
                    <tr key={`${textIndex}-${i}`} className="hover:bg-gray-50 bg-gray-25">
                      <td className="px-4 py-3 text-sm text-gray-400">—</td>
                      <td className="px-4 py-3 text-sm text-gray-400">—</td>
                      <td className="px-4 py-3 text-sm">
                        <div className="font-medium text-gray-900 capitalize">{result.provider}</div>
                        <div className="text-xs text-gray-500">{result.model_id}</div>
                      </td>
                      <td className="px-4 py-3">
                        {result.classification && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {result.classification.category}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {result.classification && (
                          <ConfidenceBar confidence={result.classification.confidence} />
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {result.sentiment && (
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${SENTIMENT_COLORS[result.sentiment.sentiment]}`}>
                            {SENTIMENT_ICONS[result.sentiment.sentiment]} {result.sentiment.sentiment}
                            <span className="ml-1 text-xs opacity-75">({result.sentiment.score.toFixed(2)})</span>
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">{formatLatency(result.latency_ms)}</td>
                      <td className="px-4 py-3"></td>
                    </tr>
                  ))}

                  {/* Expanded detail row */}
                  {expandedRows.has(textIndex) && (
                    <tr className="bg-gray-50">
                      <td colSpan={8} className="px-4 py-4">
                        <div className="space-y-4">
                          {group.map((result, i) => (
                            <div key={i} className="border border-gray-200 rounded-lg p-4 bg-white">
                              <div className="flex items-center justify-between mb-3">
                                <div className="font-medium text-gray-900 capitalize">{result.provider} / {result.model_id}</div>
                                <span className="text-xs text-gray-500">{formatLatency(result.latency_ms)}</span>
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {result.classification && (
                                  <div>
                                    <div className="text-xs font-medium text-gray-500 mb-1">Classification</div>
                                    <div className="space-y-2">
                                      <div className="flex items-center gap-3">
                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 min-w-[120px]">
                                          {result.classification.category}
                                        </span>
                                        <ConfidenceBar confidence={result.classification.confidence} />
                                        <span className="text-xs text-gray-500">{result.classification.confidence.toFixed(2)}</span>
                                      </div>
                                      <div className="text-sm text-gray-600 bg-gray-50 p-2 rounded">
                                        {result.classification.reasoning}
                                      </div>
                                    </div>
                                  </div>
                                )}

                                {result.sentiment && (
                                  <div>
                                    <div className="text-xs font-medium text-gray-500 mb-1">Sentiment</div>
                                    <div className="space-y-2">
                                      <div className="flex items-center gap-3">
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${SENTIMENT_COLORS[result.sentiment.sentiment]} min-w-[120px]`}>
                                          {SENTIMENT_ICONS[result.sentiment.sentiment]} {result.sentiment.sentiment}
                                        </span>
                                        <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
                                          <div
                                            className="bg-blue-500 h-full rounded-full"
                                            style={{ width: `${((result.sentiment.score + 1) / 2) * 100}%` }}
                                          />
                                        </div>
                                        <span className="text-xs text-gray-500">{result.sentiment.score.toFixed(2)}</span>
                                      </div>
                                      <div className="text-sm text-gray-600 bg-gray-50 p-2 rounded">
                                        {result.sentiment.reasoning}
                                      </div>
                                      <EmotionTags emotions={result.sentiment.emotions} />
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
