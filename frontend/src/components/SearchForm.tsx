import { FormEvent, useState } from 'react';

interface SearchFormProps {
  onSubmit: (ticker: string) => void;
  loading: boolean;
}

export function SearchForm({ onSubmit, loading }: SearchFormProps) {
  const [value, setValue] = useState('AAPL');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed) {
      onSubmit(trimmed);
    }
  }

  return (
    <form className="search-form" onSubmit={handleSubmit} aria-label="Analyze stock">
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Enter ticker or company name"
        aria-label="Ticker or company name"
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Analyzing' : 'Analyze'}
      </button>
    </form>
  );
}
