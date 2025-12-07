import { useJobsStore } from '../../stores/jobs';
import type { JobFilter, JobSort } from '../../types';

const FILTER_OPTIONS: { value: JobFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'running', label: 'Running' },
  { value: 'queued', label: 'Queued' },
  { value: 'succeeded', label: 'Succeeded' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'waiting_approval', label: 'Waiting Approval' },
  { value: 'paused', label: 'Paused' },
];

const SORT_OPTIONS: { value: JobSort; label: string }[] = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'status', label: 'By Status' },
];

export function JobFilters() {
  const { filter, sort, searchQuery, setFilter, setSort, setSearchQuery } = useJobsStore();

  return (
    <div className="job-filters">
      <input
        type="text"
        className="search-input"
        placeholder="Search jobs..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
      />

      <div className="filter-row">
        <select
          className="config-select"
          value={filter}
          onChange={(e) => setFilter(e.target.value as JobFilter)}
        >
          {FILTER_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select
          className="config-select"
          value={sort}
          onChange={(e) => setSort(e.target.value as JobSort)}
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
