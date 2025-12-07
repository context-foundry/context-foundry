import { useSettingsStore } from '../../stores/settings';
import { TeamSettings } from './TeamSettings';
import { S3Config } from './S3Config';
import versionInfo from '../../version.json';

export function SettingsPanel() {
  const { closeSettings, activeTab, setActiveTab, error, successMessage } = useSettingsStore();

  return (
    <div className="modal-overlay" onClick={closeSettings}>
      <div className="modal settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="modal-close" onClick={closeSettings}>
            &times;
          </button>
        </div>

        <div className="settings-tabs">
          <button
            className={`settings-tab ${activeTab === 'team' ? 'active' : ''}`}
            onClick={() => setActiveTab('team')}
          >
            Team Sync
          </button>
          <button
            className={`settings-tab ${activeTab === 'daemon' ? 'active' : ''}`}
            onClick={() => setActiveTab('daemon')}
          >
            Daemon
          </button>
          <button
            className={`settings-tab ${activeTab === 'about' ? 'active' : ''}`}
            onClick={() => setActiveTab('about')}
          >
            About
          </button>
        </div>

        {(error || successMessage) && (
          <div className={`settings-message ${error ? 'error' : 'success'}`}>
            {error || successMessage}
          </div>
        )}

        <div className="settings-content">
          {activeTab === 'team' && (
            <>
              <TeamSettings />
              <S3Config />
            </>
          )}

          {activeTab === 'daemon' && (
            <div className="settings-section">
              <h3>Daemon Configuration</h3>
              <p className="settings-hint">
                Daemon settings are configured via the config file at
                <code>~/.context-foundry/cfd/config.json</code>
              </p>
            </div>
          )}

          {activeTab === 'about' && (
            <div className="settings-section about-section">
              <h3>Context Foundry</h3>
              <p>
                A pattern-learning system that helps AI agents improve over time
                by capturing and sharing solutions to common problems.
              </p>

              <div className="version-info">
                <div className="version-row">
                  <span className="version-label">Version</span>
                  <span className="version-value">{versionInfo.displayVersion}</span>
                </div>
                <div className="version-row">
                  <span className="version-label">Commit</span>
                  <a
                    href={`${versionInfo.githubUrl}/commit/${versionInfo.commitHash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="version-link"
                  >
                    {versionInfo.commitHash}
                  </a>
                </div>
                <div className="version-row">
                  <span className="version-label">Built</span>
                  <span className="version-value">
                    {new Date(versionInfo.buildTime).toLocaleDateString()}
                  </span>
                </div>
              </div>

              <div className="about-links">
                <a
                  href={versionInfo.githubUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn"
                >
                  GitHub Repository
                </a>
                <a
                  href={`${versionInfo.githubUrl}/releases`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn"
                >
                  Release Notes
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
