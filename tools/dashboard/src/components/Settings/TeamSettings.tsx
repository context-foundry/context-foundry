import { useState, useEffect } from 'react';
import { useSettingsStore } from '../../stores/settings';

export function TeamSettings() {
  const { teamSettings, updateTeamSettings, isSaving, isLoading } = useSettingsStore();

  const [formData, setFormData] = useState({
    team_id: '',
    sync_mode: 'local-only' as 'team' | 'local-only',
  });

  useEffect(() => {
    if (teamSettings) {
      setFormData({
        team_id: teamSettings.team_id ?? '',
        sync_mode: teamSettings.sync_mode,
      });
    }
  }, [teamSettings]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateTeamSettings({
      team_id: formData.team_id || null,
      sync_mode: formData.sync_mode,
    });
  };

  if (isLoading) {
    return <div className="settings-loading">Loading settings...</div>;
  }

  return (
    <div className="settings-section">
      <h3>Team Configuration</h3>
      <p className="settings-hint">
        Configure your team to share patterns with colleagues using the same S3 bucket.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="team_id">Team ID</label>
          <input
            type="text"
            id="team_id"
            className="form-input"
            placeholder="e.g., acme-corp"
            value={formData.team_id}
            onChange={(e) => setFormData({ ...formData, team_id: e.target.value })}
          />
          <span className="form-help">
            A unique identifier for your team. Used as a namespace in S3.
          </span>
        </div>

        <div className="form-group">
          <label htmlFor="sync_mode">Sync Mode</label>
          <select
            id="sync_mode"
            className="config-select"
            value={formData.sync_mode}
            onChange={(e) =>
              setFormData({
                ...formData,
                sync_mode: e.target.value as typeof formData.sync_mode,
              })
            }
          >
            <option value="local-only">Local Only (no sync)</option>
            <option value="team">Team (shared S3 bucket)</option>
          </select>
          <span className="form-help">
            {formData.sync_mode === 'local-only' &&
              'Patterns are stored locally only. No cloud sync.'}
            {formData.sync_mode === 'team' &&
              'Patterns sync to your team\'s private S3 bucket.'}
          </span>
        </div>

        <button type="submit" className="btn btn-primary" disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save Team Settings'}
        </button>
      </form>
    </div>
  );
}
