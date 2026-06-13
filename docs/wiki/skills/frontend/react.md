# React 19 + Vite + Tailwind — Skill Reference

## Overview
- **What**: Modern web framework stack for analyst dashboard. Fast build, styling, and interactivity.
- **Version**: React 19, Vite 5+, Tailwind CSS 3+
- **Category**: Frontend/Stack
- **Installed In**: SPA served by Caddy

## Configuration

### Vite Config
```javascript
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080'
    }
  },
  build: {
    minify: 'terser',
    sourcemap: process.env.DEBUG ? true : false
  }
});
```

### Tailwind Setup
```javascript
// tailwind.config.js
export default {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        dial: "#0066cc"
      }
    }
  }
};
```

## Component Patterns

- **Hooks**: `useState`, `useEffect`, `useCallback` for state and side effects
- **Suspense**: `<Suspense>` for code splitting and lazy loading
- **Server Components**: Mark heavy data-fetching logic for server-side rendering (if applicable)
- **CSS Modules**: `import styles from './Component.module.css'` for scoped styles
- **Tailwind Utilities**: `className="flex items-center gap-4 p-6"`

## Integration Points

- **API Calls**: Fetch to DIAL Core `/chat/completions`
- **CopilotKit**: Sidebar for multi-step workflows
- **Data Display**: Tables for facts, relations, and conflicts
- **State Management**: Context API or Zustand for global state
- **Authentication**: Keycloak OAuth2 integration for user login

## Common Pitfalls

- **React.StrictMode**: Development-only double-rendering can confuse side-effect logic
- **Key Prop**: Missing or incorrect keys in lists cause rendering bugs
- **Dependency Arrays**: `useEffect` dependencies incomplete; leads to stale closures
- **Tailwind Purging**: Generated classes not in templates are stripped; use safe list if needed
- **Vite Optimization**: Large chunks may slow first load; configure `build.rollupOptions.output.manualChunks`

## References
- [React 19 Documentation](https://react.dev/)
- [Vite Guide](https://vitejs.dev/guide/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [React Query (optional)](https://tanstack.com/query/latest) — for server state management
