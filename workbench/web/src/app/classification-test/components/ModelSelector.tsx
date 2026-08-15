'use client';

import { ProviderConfig, ProviderName } from '@/lib/classification-api';

const PROVIDER_MODELS: Record<ProviderName, string[]> = {
  ollama: ['glm-5.1', 'llama3.2', 'mistral', 'codellama'],
  nvidia: ['nvidia/nemotron-3-super-120b-a12b', 'nvidia/nemotron-3-ultra-550b-a55b'],
  openrouter: ['deepseek/deepseek-chat', 'anthropic/claude-3.5-sonnet', 'openai/gpt-4o'],
  anthropic: ['claude-sonnet-4-6', 'claude-opus-4-8'],
  openai: ['gpt-4o', 'gpt-4o-mini'],
  google: ['gemini-2.0-flash', 'gemini-1.5-pro'],
  groq: ['llama-3.3-70b-versatile', 'mixtral-8x7b-32768'],
  portkey: ['gpt-4o', 'gpt-4o-mini', 'claude-3.5-sonnet', 'gemini-1.5-pro'],
};

const PROVIDER_LABELS: Record<ProviderName, string> = {
  ollama: 'Ollama (Local/Cloud)',
  nvidia: 'NVIDIA NIM',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google',
  groq: 'Groq',
  portkey: 'Portkey Gateway',
};

interface ModelSelectorProps {
  providers: ProviderConfig[];
  onChange: (providers: ProviderConfig[]) => void;
}

export function ModelSelector({ providers, onChange }: ModelSelectorProps) {
  const handleProviderChange = (index: number, provider: ProviderName) => {
    const newProviders = [...providers];
    newProviders[index] = { ...newProviders[index], provider, model_id: PROVIDER_MODELS[provider][0] };
    onChange(newProviders);
  };

  const handleModelChange = (index: number, model: string) => {
    const newProviders = [...providers];
    newProviders[index] = { ...newProviders[index], model_id: model };
    onChange(newProviders);
  };

  const handleTemperatureChange = (index: number, temperature: number) => {
    const newProviders = [...providers];
    newProviders[index] = { ...newProviders[index], temperature };
    onChange(newProviders);
  };

  const handleMaxTokensChange = (index: number, max_tokens: number) => {
    const newProviders = [...providers];
    newProviders[index] = { ...newProviders[index], max_tokens };
    onChange(newProviders);
  };

  const addProvider = () => {
    onChange([...providers, { provider: 'ollama', temperature: 0, max_tokens: 1024 }]);
  };

  const removeProvider = (index: number) => {
    if (providers.length <= 1) return;
    onChange(providers.filter((_, i) => i !== index));
  };

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Model Providers</h3>
        <button
          onClick={addProvider}
          className="text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          + Add Provider
        </button>
      </div>

      <div className="space-y-4">
        {providers.map((providerConfig, index) => (
          <div key={index} className="border border-gray-200 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <select
                value={providerConfig.provider}
                onChange={(e) => handleProviderChange(index, e.target.value as ProviderName)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {Object.entries(PROVIDER_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>

              {providers.length > 1 && (
                <button
                  onClick={() => removeProvider(index)}
                  className="text-red-500 hover:text-red-700 text-sm font-medium"
                >
                  Remove
                </button>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Model</label>
                <select
                  value={providerConfig.model_id || PROVIDER_MODELS[providerConfig.provider][0]}
                  onChange={(e) => handleModelChange(index, e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {PROVIDER_MODELS[providerConfig.provider].map((model) => (
                    <option key={model} value={model}>{model}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Temperature</label>
                <input
                  type="number"
                  value={providerConfig.temperature ?? 0}
                  onChange={(e) => handleTemperatureChange(index, parseFloat(e.target.value))}
                  min={0}
                  max={2}
                  step={0.1}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-500 mb-1">Max Tokens</label>
                <input
                  type="number"
                  value={providerConfig.max_tokens ?? 1024}
                  onChange={(e) => handleMaxTokensChange(index, parseInt(e.target.value))}
                  min={1}
                  max={8192}
                  step={1}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
