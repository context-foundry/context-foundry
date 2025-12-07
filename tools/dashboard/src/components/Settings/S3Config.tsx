import { useState, useEffect } from 'react';
import { useSettingsStore, useSyncMode } from '../../stores/settings';

export function S3Config() {
  const { teamSettings, updateTeamSettings, testS3Connection, isSaving, isTestingS3, s3TestResult } =
    useSettingsStore();
  const syncMode = useSyncMode();

  const [formData, setFormData] = useState({
    s3_bucket: '',
    s3_prefix: 'shared-patterns/',
    s3_region: 'us-east-1',
    aws_profile: '',
  });

  useEffect(() => {
    if (teamSettings) {
      setFormData({
        s3_bucket: teamSettings.s3_bucket ?? '',
        s3_prefix: teamSettings.s3_prefix,
        s3_region: teamSettings.s3_region,
        aws_profile: teamSettings.aws_profile ?? '',
      });
    }
  }, [teamSettings]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateTeamSettings({
      s3_bucket: formData.s3_bucket || null,
      s3_prefix: formData.s3_prefix,
      s3_region: formData.s3_region,
      aws_profile: formData.aws_profile || null,
    });
  };

  // Only show S3 config when sync mode is team
  if (syncMode !== 'team') {
    return null;
  }

  return (
    <div className="settings-section">
      <h3>S3 Configuration</h3>
      <p className="settings-hint">
        Configure the S3 bucket where your team's patterns will be stored.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="s3_bucket">S3 Bucket</label>
          <input
            type="text"
            id="s3_bucket"
            className="form-input"
            placeholder="e.g., acme-patterns"
            value={formData.s3_bucket}
            onChange={(e) => setFormData({ ...formData, s3_bucket: e.target.value })}
          />
          <span className="form-help">
            The S3 bucket name (without s3:// prefix)
          </span>
        </div>

        <div className="form-group">
          <label htmlFor="s3_prefix">S3 Prefix</label>
          <input
            type="text"
            id="s3_prefix"
            className="form-input"
            placeholder="shared-patterns/"
            value={formData.s3_prefix}
            onChange={(e) => setFormData({ ...formData, s3_prefix: e.target.value })}
          />
          <span className="form-help">
            Optional prefix (folder) within the bucket
          </span>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="s3_region">AWS Region</label>
            <select
              id="s3_region"
              className="config-select"
              value={formData.s3_region}
              onChange={(e) => setFormData({ ...formData, s3_region: e.target.value })}
            >
              <option value="us-east-1">us-east-1</option>
              <option value="us-west-2">us-west-2</option>
              <option value="eu-west-1">eu-west-1</option>
              <option value="ap-northeast-1">ap-northeast-1</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="aws_profile">AWS Profile (optional)</label>
            <input
              type="text"
              id="aws_profile"
              className="form-input"
              placeholder="default"
              value={formData.aws_profile}
              onChange={(e) => setFormData({ ...formData, aws_profile: e.target.value })}
            />
          </div>
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save S3 Config'}
          </button>
          <button
            type="button"
            className="btn"
            onClick={testS3Connection}
            disabled={isTestingS3 || !formData.s3_bucket}
          >
            {isTestingS3 ? 'Testing...' : 'Test Connection'}
          </button>
        </div>

        {s3TestResult && (
          <div className={`test-result ${s3TestResult.success ? 'success' : 'error'}`}>
            {s3TestResult.success ? '✓' : '✗'} {s3TestResult.message}
          </div>
        )}
      </form>

      <div className="env-hint">
        <h4>Environment Variables</h4>
        <p>You can also configure S3 via environment variables:</p>
        <pre>
          {`CONTEXT_FOUNDRY_S3_BUCKET=${formData.s3_bucket || 'your-bucket'}
CONTEXT_FOUNDRY_S3_PREFIX=${formData.s3_prefix}
AWS_PROFILE=${formData.aws_profile || 'your-profile'}`}
        </pre>
      </div>
    </div>
  );
}
