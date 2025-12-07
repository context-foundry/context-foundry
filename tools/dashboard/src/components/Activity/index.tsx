import { useJobsStore } from '../../stores/jobs';

export function ActivityPanel() {
  const { activityMetrics } = useJobsStore();

  if (!activityMetrics) {
    return (
      <aside className="activity-panel">
        <div className="activity-header">
          <h3>Activity</h3>
        </div>
        <div className="activity-empty">
          Select a running job to see activity
        </div>
      </aside>
    );
  }

  const { input_tokens, output_tokens, context_percent, current_action, tool_calls, thoughts } =
    activityMetrics;

  return (
    <aside className="activity-panel">
      <div className="activity-header">
        <h3>Activity</h3>
      </div>

      <div className="activity-content">
        <div className="activity-section">
          <h4>Token Usage</h4>
          <div className="token-stats">
            <div className="token-stat">
              <span className="token-label">Input</span>
              <span className="token-value">{input_tokens.toLocaleString()}</span>
            </div>
            <div className="token-stat">
              <span className="token-label">Output</span>
              <span className="token-value">{output_tokens.toLocaleString()}</span>
            </div>
            <div className="token-stat">
              <span className="token-label">Context</span>
              <span className="token-value">{context_percent.toFixed(1)}%</span>
            </div>
          </div>
          <div className="context-bar">
            <div
              className="context-fill"
              style={{ width: `${Math.min(context_percent, 100)}%` }}
            />
          </div>
        </div>

        {current_action && (
          <div className="activity-section">
            <h4>Current Action</h4>
            <div className="current-action">{current_action}</div>
          </div>
        )}

        {tool_calls.length > 0 && (
          <div className="activity-section">
            <h4>Recent Tool Calls</h4>
            <div className="tool-call-list">
              {tool_calls.slice(-5).map((call, index) => (
                <div key={index} className="tool-call-item">
                  <span className="tool-call-name">{call.name}</span>
                  <span className="tool-call-time">
                    {new Date(call.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {thoughts.length > 0 && (
          <div className="activity-section">
            <h4>Agent Thoughts</h4>
            <div className="thoughts-list">
              {thoughts.slice(-3).map((thought, index) => (
                <div key={index} className="thought-item">
                  {thought}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
