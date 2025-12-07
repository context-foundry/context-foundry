import { JobFilters } from './JobFilters';
import { JobList } from './JobList';

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title-row">
          <h2 className="sidebar-title">Jobs</h2>
        </div>
        <JobFilters />
      </div>
      <JobList />
    </aside>
  );
}
