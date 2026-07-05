import type { OpportunityTheme } from '../types';

interface ThemeSelectorProps {
  themes: OpportunityTheme[];
  value: string;
  onChange: (value: string) => void;
}

export function ThemeSelector({ themes, value, onChange }: ThemeSelectorProps) {
  return (
    <label className="field-stack">
      <span>Industry theme</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} aria-label="Industry theme">
        {themes.map((theme) => (
          <option key={theme.id} value={theme.id}>{theme.name}</option>
        ))}
      </select>
    </label>
  );
}
