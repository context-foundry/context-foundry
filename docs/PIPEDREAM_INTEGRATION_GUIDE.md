# Pipedream + Context Foundry Integration Guide

**Last Updated:** 2025-11-20
**Status:** Research Complete, Implementation Ready

---

## Executive Summary

### TL;DR - The Verdict

**Can we ship Context Foundry with Pipedream pre-configured?**

✅ **YES** - For component-level integrations (OAuth, single actions)
❌ **NO** - For complete multi-step workflows (templates not exportable)
⚠️ **PARTIAL** - For workflow orchestration (requires SDK-driven approach)

### Strategic Recommendation

**Use Pipedream as an Authentication & Simple Action Layer**, not as the primary workflow engine.

**Best Fit:**
- Managed OAuth for 3,000+ apps (GitHub, Slack, Discord, Notion, etc.)
- Simple action execution (send message, create issue, post webhook)
- Event-driven triggers (GitHub webhooks, cron schedules)

**Poor Fit:**
- Shipping pre-configured multi-step workflows
- Custom workflow templates
- Self-hosted execution requirements
- White-label integration platform

### Quick Wins vs. Challenges

| Opportunity | Feasibility | Impact | Effort |
|------------|-------------|--------|--------|
| Managed OAuth for 3,000+ apps | ✅ High | 🔥 High | Low |
| GitHub webhook → CF build | ✅ High | 🔥 High | Medium |
| Multi-channel notifications | ✅ High | 🔥 High | Low |
| Event-driven automation | ✅ High | 🔥 High | Medium |
| Pre-configured workflows | ❌ Low | 🔥 High | N/A |
| Self-hosted execution | ❌ None | Medium | N/A |
| Custom private components | ❌ Low | Medium | N/A |

---

## Table of Contents

1. [The Good: Integration Opportunities](#the-good-integration-opportunities)
2. [The Bad: Significant Limitations](#the-bad-significant-limitations)
3. [The Ugly: Deal-Breakers](#the-ugly-deal-breakers)
4. [Detailed Use Cases](#detailed-use-cases)
5. [Integration Architecture Options](#integration-architecture-options)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Technical Reference](#technical-reference)
8. [Alternatives Comparison](#alternatives-comparison)

---

## The Good: Integration Opportunities

### 1. Managed OAuth for 3,000+ Integrations

**What It Solves:**
- Building OAuth flows for every service (GitHub, Slack, Discord, Notion, Linear, etc.)
- Managing refresh tokens, scopes, and credential storage
- Handling OAuth app registration and maintenance

**How It Works:**

```typescript
// Backend: context-foundry/lib/integrations/pipedream-server.ts
import { PipedreamClient } from "@pipedream/sdk/server";

export const pdBackend = new PipedreamClient({
  projectId: process.env.PIPEDREAM_PROJECT_ID!,
  projectEnvironment: "production",
  clientId: process.env.PIPEDREAM_CLIENT_ID!,
  clientSecret: process.env.PIPEDREAM_CLIENT_SECRET!,
});

// Create secure token for frontend
export async function createUserToken(cfUserId: string) {
  return await pdBackend.tokens.create({
    externalUserId: cfUserId,
    allowedOrigins: [process.env.APP_URL!],
  });
}
```

```typescript
// Frontend: context-foundry/components/ConnectIntegrations.tsx
import { FrontendClientProvider } from "@pipedream/connect-react";
import { createFrontendClient } from "@pipedream/sdk/browser";

export function ConnectIntegrations({ userId }: { userId: string }) {
  const client = createFrontendClient({
    tokenCallback: async () => {
      const res = await fetch('/api/pipedream/token');
      return res.json();
    }
  });

  return (
    <FrontendClientProvider client={client}>
      <button onClick={() => {
        client.connectAccount({
          appSlug: 'github',
          onSuccess: (account) => {
            // Save account.id to CF database
            saveUserConnection(userId, 'github', account.id);
          }
        });
      }}>
        Connect GitHub
      </button>
    </FrontendClientProvider>
  );
}
```

**Benefits:**
- ✅ Zero OAuth implementation work
- ✅ Automatic token refresh handling
- ✅ 3,000+ apps supported out-of-the-box
- ✅ User-friendly connection UI
- ✅ Secure credential storage (on Pipedream)

**ROI:** 🔥🔥🔥🔥🔥 (5/5) - Saves weeks of OAuth implementation per service

---

### 2. GitHub Webhook → CF Build Pipeline

**What It Solves:**
- Automatic builds on every push to main
- Pull request validation builds
- Release deployment automation

**Architecture:**

```
GitHub Push Event
    ↓
Pipedream Webhook Trigger
    ↓
Parse repo, branch, commit info
    ↓
Call CF Daemon: cfd submit
    ↓
CF executes 8-phase build
    ↓
CF emits webhook events
    ↓
Pipedream receives progress updates
    ↓
Send notifications to Slack/Discord
    ↓
Deploy to staging (if tests pass)
```

**Implementation:**

```javascript
// Pipedream Workflow: GitHub Push → CF Build
import { axios } from "@pipedream/platform";

export default defineComponent({
  name: "github-push-to-cf-build",
  version: "0.0.1",
  props: {
    github: {
      type: "app",
      app: "github",
    },
    http: {
      type: "$.interface.http",
      customResponse: true,
    },
  },
  async run({ steps, $ }) {
    const { repository, ref, commits } = steps.trigger.event.body;
    const branch = ref.split('/').pop();

    // Only build on main branch pushes
    if (branch !== 'main') {
      $.respond({ status: 200, body: { message: "Skipped" } });
      return;
    }

    // Submit CF build
    const cfResult = await axios($, {
      method: "POST",
      url: `${process.env.CF_API_URL}/jobs`,
      data: {
        type: "autonomous_build",
        params: {
          task: `Build ${repository.name} from latest commit`,
          working_directory: `/tmp/builds/${repository.full_name}`,
          existing_repo: repository.clone_url,
          mode: "incremental",
        }
      }
    });

    $.respond({
      status: 200,
      body: {
        message: "Build started",
        job_id: cfResult.data.job_id
      }
    });

    // Return job_id to next steps
    return cfResult.data;
  }
});
```

**Benefits:**
- ✅ Fully automated CI/CD
- ✅ Self-healing builds (CF auto-fixes test failures)
- ✅ Incremental builds (10-40% faster)
- ✅ GitHub Checks integration potential

**ROI:** 🔥🔥🔥🔥🔥 (5/5) - Core automation use case

---

### 3. Discord Slash Commands → CF Builds

**What It Solves:**
- Natural language builds from Discord
- Team collaboration on builds
- Real-time progress updates in threads

**Architecture:**

```
User types: /build weather-app with React and OpenWeatherMap
    ↓
Discord webhook → Pipedream
    ↓
Pipedream parses command
    ↓
Validate user permissions (team member?)
    ↓
Submit CF job via API
    ↓
Create Discord thread for updates
    ↓
CF emits phase events → Pipedream webhook
    ↓
Pipedream posts updates to thread
    ↓
Build complete → Final summary with GitHub link
```

**Implementation:**

```javascript
// Pipedream Workflow: Discord Command → CF Build
export default defineComponent({
  name: "discord-slash-command-build",
  props: {
    discord: {
      type: "app",
      app: "discord_webhook",
    },
  },
  async run({ steps, $ }) {
    const { command, options, channel_id, user } = steps.trigger.event.body;

    // Parse /build command
    const task = options.find(opt => opt.name === 'description').value;
    const projectName = task.split(' ')[0].toLowerCase();

    // Submit CF build
    const cfJob = await axios($, {
      method: "POST",
      url: `${process.env.CF_API_URL}/jobs`,
      data: {
        type: "autonomous_build",
        params: {
          task: task,
          working_directory: `/tmp/builds/${projectName}`,
          github_repo_name: projectName,
        }
      }
    });

    // Create Discord thread
    const thread = await axios($, {
      method: "POST",
      url: `https://discord.com/api/v10/channels/${channel_id}/threads`,
      headers: {
        "Authorization": `Bot ${this.discord.$auth.bot_token}`,
      },
      data: {
        name: `Build: ${projectName}`,
        type: 11, // Public thread
        message: {
          content: `🔨 Building ${projectName}...\nJob ID: ${cfJob.data.job_id}`
        }
      }
    });

    // Store thread_id for later updates
    $.export("thread_id", thread.data.id);
    $.export("job_id", cfJob.data.job_id);

    return { thread_id: thread.data.id, job_id: cfJob.data.job_id };
  }
});
```

**Benefits:**
- ✅ Frictionless team builds
- ✅ Threaded conversation per build
- ✅ Real-time progress visibility
- ✅ No context switching

**ROI:** 🔥🔥🔥🔥 (4/5) - Excellent for team workflows

---

### 4. Multi-Channel Build Notifications

**What It Solves:**
- Send build status to multiple destinations
- Flexible notification routing (success → Slack, failure → PagerDuty)
- Rich formatting per channel

**Current CF Implementation:**

CF already has Discord webhooks in `tools/build_notifications.py`, but Pipedream can enhance:

```javascript
// Pipedream Workflow: CF Build Complete → Multi-Channel Notify
export default defineComponent({
  name: "cf-build-complete-notify",
  props: {
    http: {
      type: "$.interface.http",
      customResponse: true,
    },
  },
  async run({ steps, $ }) {
    const { event, job_id, status, project, duration_seconds } = steps.trigger.event.body;

    if (event !== "build_complete") return;

    // Parallel notifications
    const notifications = [];

    // 1. Slack notification
    if (status === "success") {
      notifications.push(
        $.send.slack({
          channel: "#builds",
          text: `:white_check_mark: ${project} built successfully in ${duration_seconds}s`,
          blocks: [
            {
              type: "section",
              text: {
                type: "mrkdwn",
                text: `*Build Complete: ${project}*\n:white_check_mark: Status: Success\n:stopwatch: Duration: ${duration_seconds}s\n:link: <https://github.com/user/${project}|View on GitHub>`
              }
            }
          ]
        })
      );
    } else {
      // Failure → PagerDuty
      notifications.push(
        $.send.http({
          url: "https://events.pagerduty.com/v2/enqueue",
          data: {
            routing_key: process.env.PAGERDUTY_KEY,
            event_action: "trigger",
            payload: {
              summary: `CF Build Failed: ${project}`,
              severity: "error",
              source: "context-foundry",
            }
          }
        })
      );
    }

    // 2. Email notification
    notifications.push(
      $.send.email({
        to: "team@example.com",
        subject: `Build ${status}: ${project}`,
        text: `Job ${job_id} completed with status ${status} in ${duration_seconds}s`
      })
    );

    // 3. GitHub status (if integrated)
    // ...

    await Promise.all(notifications);

    return { notified: notifications.length };
  }
});
```

**Benefits:**
- ✅ Centralized notification routing
- ✅ Conditional logic (success vs. failure)
- ✅ No code changes to CF
- ✅ Easy to add new channels

**ROI:** 🔥🔥🔥 (3/5) - Nice-to-have enhancement

---

### 5. Flowise Workflow Generation + Deployment

**What It Solves:**
- Generate Flowise AgentFlow v2 workflows with CF
- Automatically import into Flowise instance
- Validate and test workflows

**Architecture:**

```
User: "Build a customer support routing workflow with Flowise"
    ↓
Pipedream receives request (via form/API)
    ↓
Call CF: autonomous_build_and_deploy(task="Build Flowise workflow for...")
    ↓
CF uses Flowise extension (extensions/flowise/)
    ↓
CF generates JSON workflow (nodes + edges)
    ↓
CF saves to S3 or returns to Pipedream
    ↓
Pipedream imports into Flowise via API
    ↓
Pipedream tests workflow with sample data
    ↓
Pipedream reports results to user
```

**Implementation:**

```javascript
// Pipedream Workflow: Generate & Deploy Flowise Workflow
export default defineComponent({
  name: "cf-flowise-generator",
  props: {
    flowise_api_url: {
      type: "string",
      label: "Flowise API URL",
      default: "http://localhost:3000",
    },
    flowise_api_key: {
      type: "string",
      label: "Flowise API Key",
      secret: true,
    },
  },
  async run({ steps, $ }) {
    const workflowDescription = steps.trigger.event.body.description;

    // Step 1: Generate workflow with CF
    const cfResult = await axios($, {
      method: "POST",
      url: `${process.env.CF_API_URL}/jobs`,
      data: {
        type: "autonomous_build",
        params: {
          task: `Build Flowise AgentFlow v2 workflow: ${workflowDescription}`,
          working_directory: `/tmp/flowise-builds/${Date.now()}`,
          mode: "new_project",
        }
      }
    });

    // Step 2: Poll for completion
    let workflow = null;
    while (!workflow) {
      await new Promise(resolve => setTimeout(resolve, 10000)); // 10s
      const status = await axios($, {
        method: "GET",
        url: `${process.env.CF_API_URL}/jobs/${cfResult.data.job_id}`,
      });

      if (status.data.status === "completed") {
        // Read generated workflow JSON
        workflow = status.data.result.workflow;
        break;
      }
    }

    // Step 3: Import into Flowise
    const flowiseResult = await axios($, {
      method: "POST",
      url: `${this.flowise_api_url}/api/v1/chatflows`,
      headers: {
        "Authorization": `Bearer ${this.flowise_api_key}`,
      },
      data: {
        name: workflowDescription,
        flowData: workflow,
        deployed: true,
      }
    });

    // Step 4: Test workflow
    const testResult = await axios($, {
      method: "POST",
      url: `${this.flowise_api_url}/api/v1/prediction/${flowiseResult.data.id}`,
      data: {
        question: "Test message",
      }
    });

    return {
      workflow_id: flowiseResult.data.id,
      cf_job_id: cfResult.data.job_id,
      test_result: testResult.data,
    };
  }
});
```

**Benefits:**
- ✅ Automated Flowise workflow generation
- ✅ Validated deployments
- ✅ Integration with existing Flowise instances
- ✅ Leverages CF's Flowise extension

**ROI:** 🔥🔥🔥🔥 (4/5) - High value for Flowise users

---

### 6. Pattern Distribution & Validation

**What It Solves:**
- Community pattern validation before merging
- Analytics on pattern usage
- Automated pattern sync

**Architecture:**

```
CF uploads pattern to S3
    ↓
S3 event triggers Pipedream
    ↓
Pipedream validates pattern schema
    ↓
Pipedream checks for duplicates
    ↓
Pipedream runs quality checks
    ↓
If valid: Merge to global registry
    ↓
Send Discord notification to community
    ↓
Track downloads and effectiveness
```

**Implementation:**

```javascript
// Pipedream Workflow: S3 Pattern Upload → Validate & Publish
export default defineComponent({
  name: "s3-pattern-validator",
  props: {
    aws: {
      type: "app",
      app: "aws",
    },
  },
  async run({ steps, $ }) {
    const { object } = steps.trigger.event.Records[0].s3;
    const bucketName = steps.trigger.event.Records[0].s3.bucket.name;
    const patternKey = object.key;

    // Step 1: Download pattern from S3
    const s3Client = new AWS.S3({
      accessKeyId: this.aws.$auth.access_key_id,
      secretAccessKey: this.aws.$auth.secret_access_key,
    });

    const pattern = await s3Client.getObject({
      Bucket: bucketName,
      Key: patternKey,
    }).promise();

    const patternData = JSON.parse(pattern.Body.toString());

    // Step 2: Validate schema
    const validation = validatePatternSchema(patternData);
    if (!validation.valid) {
      $.export("error", validation.errors);
      throw new Error("Invalid pattern schema");
    }

    // Step 3: Check for duplicates
    const isDuplicate = await checkDuplicate(patternData);
    if (isDuplicate) {
      $.export("skipped", "Duplicate pattern");
      return;
    }

    // Step 4: Merge to global registry
    await mergeToRegistry(patternData);

    // Step 5: Notify community
    await $.send.discord({
      webhook_url: process.env.DISCORD_WEBHOOK,
      content: `📦 New pattern published: **${patternData.title}**\nCategory: ${patternData.category}\nDownload: \`cf pull-pattern ${patternData.id}\``
    });

    // Step 6: Track analytics
    await $.send.http({
      url: process.env.ANALYTICS_ENDPOINT,
      data: {
        event: "pattern_published",
        pattern_id: patternData.id,
        timestamp: new Date().toISOString(),
      }
    });

    return { pattern_id: patternData.id, status: "published" };
  }
});
```

**Benefits:**
- ✅ Automated quality control
- ✅ Community engagement
- ✅ Usage analytics
- ✅ Duplicate prevention

**ROI:** 🔥🔥🔥 (3/5) - Important for pattern ecosystem

---

### 7. Event-Driven Multi-Stage Deployments

**What It Solves:**
- Complex deployment pipelines
- Conditional logic (if tests pass → deploy staging, if approved → production)
- External service orchestration

**Architecture:**

```
CF builds project → Tests pass
    ↓
Pipedream deploys to Vercel (staging)
    ↓
Pipedream runs Playwright E2E tests
    ↓
Tests pass → Send approval request to Slack
    ↓
Team approves (via Slack reaction)
    ↓
Pipedream deploys to production
    ↓
Pipedream configures monitoring (Sentry, DataDog)
    ↓
Send summary to team
```

**Implementation:**

```javascript
// Pipedream Workflow: Multi-Stage Deployment
export default defineComponent({
  name: "cf-multi-stage-deploy",
  props: {
    vercel: {
      type: "app",
      app: "vercel",
    },
  },
  async run({ steps, $ }) {
    const { job_id, project, status } = steps.trigger.event.body;

    if (status !== "success") return;

    // Step 1: Deploy to Vercel staging
    const stagingDeploy = await axios($, {
      method: "POST",
      url: "https://api.vercel.com/v13/deployments",
      headers: {
        "Authorization": `Bearer ${this.vercel.$auth.token}`,
      },
      data: {
        name: project,
        project: process.env.VERCEL_PROJECT_ID,
        gitSource: {
          type: "github",
          ref: "main",
          repo: `user/${project}`,
        },
        target: "staging",
      }
    });

    $.export("staging_url", stagingDeploy.data.url);

    // Step 2: Run E2E tests
    const testResult = await axios($, {
      method: "POST",
      url: process.env.PLAYWRIGHT_API,
      data: {
        url: stagingDeploy.data.url,
        tests: ["smoke", "critical-path"],
      }
    });

    if (!testResult.data.passed) {
      throw new Error("E2E tests failed");
    }

    // Step 3: Request approval in Slack
    const approval = await $.send.slack({
      channel: "#deployments",
      text: `${project} ready for production. React with :white_check_mark: to approve.`,
      blocks: [
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `*Ready for Production*\nProject: ${project}\nStaging: ${stagingDeploy.data.url}\nTests: ✅ Passed`
          }
        }
      ]
    });

    // Step 4: Wait for approval (Pipedream workflow waits for event)
    // ... (requires separate workflow to listen for Slack reactions)

    // Step 5: Deploy to production (triggered by approval)
    const prodDeploy = await axios($, {
      method: "POST",
      url: "https://api.vercel.com/v13/deployments",
      headers: {
        "Authorization": `Bearer ${this.vercel.$auth.token}`,
      },
      data: {
        name: project,
        project: process.env.VERCEL_PROJECT_ID,
        target: "production",
      }
    });

    return {
      staging_url: stagingDeploy.data.url,
      production_url: prodDeploy.data.url,
    };
  }
});
```

**Benefits:**
- ✅ Automated testing gates
- ✅ Human approval step
- ✅ Multi-environment management
- ✅ Service orchestration

**ROI:** 🔥🔥🔥🔥 (4/5) - Critical for production workflows

---

## The Bad: Significant Limitations

### 1. No Workflow Template Export/Import

**The Problem:**

According to GitHub Issue #18505:
> "The API endpoint for exporting workflows **doesn't include configured prop values**"

**What This Means:**
- ❌ Cannot export a workflow with pre-filled values
- ❌ Cannot ship "Build Notification Template" as importable file
- ❌ Users cannot one-click install pre-configured workflows
- ❌ Secrets/credentials exported as placeholders only

**Example of What You CANNOT Do:**

```javascript
// ❌ This doesn't exist in Pipedream
const template = {
  name: "CF Build Notification Workflow",
  triggers: [{ type: "webhook", url: "{{CF_WEBHOOK}}" }],
  steps: [
    {
      component: "slack-send-message",
      props: {
        channel: "#builds",  // ❌ This value NOT included in export
        text: "Build complete"
      }
    }
  ]
};

// ❌ Cannot do this
await pipedream.importWorkflow(template);
```

**Workaround:**

You would need to programmatically create workflows via SDK for each user:

```typescript
// ✅ This works but requires more code
async function createBuildNotificationWorkflow(userId: string) {
  // Deploy trigger
  const trigger = await pdBackend.deployTrigger({
    componentId: "http-webhook",
    configuredProps: {},
    webhookUrl: `https://myapp.com/webhooks/cf-builds/${userId}`
  });

  // Create workflow steps (not yet documented in SDK)
  // ... Manual API calls required
}
```

**Impact:** 🔴 High - Core "ship pre-configured workflows" use case not possible

---

### 2. Public Components Only

**The Problem:**

All Pipedream components are public in the main GitHub repository:
- `github.com/PipedreamHQ/pipedream/tree/master/components`

**What This Means:**
- ❌ Cannot create Context Foundry-specific private components
- ❌ Cannot ship proprietary integrations
- ❌ Must contribute to public repo (subject to review)
- ❌ No private component registry

**Example:**

```javascript
// ❌ Cannot do this privately
export default {
  key: "context-foundry-build",  // ❌ Must be public
  name: "Context Foundry Build",
  app: "context_foundry",
  // ... CF-specific logic
};
```

**Workaround:**

Option 1: Contribute to public repo (good for open source)
Option 2: Use generic HTTP action to call CF API
Option 3: Build integrations directly in CF (bypass Pipedream)

**Impact:** 🟡 Medium - Can work around with HTTP actions

---

### 3. Infrastructure Dependency

**The Problem:**

All Pipedream workflows execute on Pipedream's infrastructure:
- No self-hosting option
- Subject to Pipedream's limits (execution time, memory, invocations)
- Vendor lock-in

**What This Means:**
- ❌ Cannot deploy Pipedream workflows to your own servers
- ❌ Cannot control execution environment
- ❌ Subject to Pipedream pricing tiers
- ❌ Data passes through Pipedream servers

**Execution Limits (Estimated):**
- Free tier: Limited invocations per month
- Execution timeout: Likely 5-15 minutes per workflow
- Memory: Likely 256-512MB per workflow
- Storage: Limited `/tmp` space

**Example Issue:**

```javascript
// If CF build takes 20 minutes...
const cfResult = await axios($, {
  url: `${CF_API}/jobs`,
  data: { task: "Build large project" }
});

// ❌ Pipedream workflow might timeout before CF completes
// Must use async pattern:
//   1. Submit job
//   2. Return immediately
//   3. Separate workflow listens for completion webhook
```

**Workaround:**

Use async pattern + webhooks:

```javascript
// Workflow 1: Submit Job
const job = await submitCFJob(task);
return { job_id: job.id };

// Workflow 2: Listen for Completion Webhook
// Triggered when CF calls back
export default defineComponent({
  props: {
    http: { type: "$.interface.http" }
  },
  async run({ steps }) {
    const { job_id, status } = steps.trigger.event.body;
    // Continue workflow...
  }
});
```

**Impact:** 🟡 Medium - Requires architectural adjustments

---

### 4. Limited Workflow Embedding

**The Problem:**

The `@pipedream/connect-react` library only supports embedding:
- ✅ Single component forms (ComponentFormContainer)
- ✅ Account connection UI
- ❌ Full workflow builder
- ❌ Multi-step workflow editor

**What This Means:**

```typescript
// ✅ This works - single component
<ComponentFormContainer
  componentKey="slack-send-message"
  userId="user-123"
/>

// ❌ This doesn't exist - multi-step workflow
<WorkflowBuilderContainer
  steps={[
    { component: "github-new-commit" },
    { component: "slack-send-message" }
  ]}
/>
```

**Impact:** 🟡 Medium - Can only embed individual actions

---

### 5. OAuth App Configuration Required

**The Problem:**

To use your own branding for OAuth, you must:
1. Create OAuth apps with each service (GitHub, Slack, etc.)
2. Register them with Pipedream
3. Map them in your integration

**What This Means:**

```typescript
// To use YOUR GitHub OAuth app (not Pipedream's)
client.connectAccount({
  appSlug: 'github',
  oauthAppConfig: {
    github: 'oa_YOUR_OAUTH_APP_ID'  // Must register with Pipedream first
  }
});
```

**Steps Required:**
1. Create OAuth app at github.com/settings/apps
2. Submit to Pipedream for registration
3. Receive `oa_YOUR_OAUTH_APP_ID`
4. Configure in your app

**Impact:** 🟢 Low - Standard OAuth setup, manageable

---

## The Ugly: Deal-Breakers

### 1. Cannot Ship Pre-Configured Multi-Step Workflows

**The Reality Check:**

If your goal is to ship Context Foundry with workflows like:

> "GitHub Push → CF Build → Run Tests → Deploy to Vercel → Notify Slack"

Pre-configured and ready to use...

**This is NOT possible** with Pipedream's current export/import capabilities.

**Why:**
- Workflow exports don't include configured prop values
- No template import mechanism
- No variable substitution system
- Must manually recreate workflows or use SDK

**Alternative Approaches:**

1. **SDK-Driven Workflow Creation:**
   - Write code to programmatically create workflows for each user
   - Requires maintaining workflow definitions in your codebase
   - More complex than importing a template

2. **Component-Level Integration:**
   - Embed individual actions (not full workflows)
   - Users configure their own workflows in Pipedream UI
   - Your app triggers workflows via API

3. **Hybrid Approach:**
   - Use Pipedream for authentication + simple actions
   - Build complex workflow logic in Context Foundry
   - Call Pipedream components when needed

---

### 2. No White-Label / OEM Program

**What's Missing:**
- ❌ No white-label option found
- ❌ No custom domain support documented
- ❌ Pipedream branding likely required in embedded UI
- ❌ No evidence of OEM partnerships

**Impact for Context Foundry:**
- Users will see "Powered by Pipedream"
- OAuth popups show Pipedream branding
- May confuse users ("Why am I connecting to Pipedream?")

**Competitive Alternative:**

Platforms with white-label options:
- Merge.dev (unified API with white-label)
- Workato (OEM program)
- Tray.io (embedded platform)

---

### 3. All Data Passes Through Pipedream

**Security / Compliance Consideration:**

When users connect accounts via Pipedream:
- ✅ Pipedream stores OAuth tokens
- ✅ Your app receives account IDs (not tokens)
- ⚠️ Action execution data passes through Pipedream
- ⚠️ Logs stored on Pipedream infrastructure

**For CF Use Case:**
- Build logs might contain sensitive information
- Source code passes through Pipedream (if using CF via Pipedream)
- Customer data from integrations stored on Pipedream

**Mitigation:**
- Use Pipedream only for authentication
- Execute sensitive operations directly from CF
- Review Pipedream's security/compliance docs

---

## Detailed Use Cases

### Use Case 1: Managed OAuth Layer

**Goal:** Let users connect 3,000+ apps without building OAuth flows

**Implementation Complexity:** 🟢 Low
**Estimated Effort:** 2-3 days
**ROI:** 🔥🔥🔥🔥🔥

**Architecture:**

```
┌─────────────────────────────────────────────┐
│  Context Foundry UI                         │
│  ┌───────────────────────────────────────┐ │
│  │ Settings → Integrations               │ │
│  │                                       │ │
│  │ [Connect GitHub]  [Connect Slack]    │ │
│  │ [Connect Discord] [Connect Notion]   │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
                     │
                     ↓
         @pipedream/connect-react
         (FrontendClientProvider)
                     │
                     ↓
         ┌───────────────────────┐
         │ Pipedream OAuth Popup │
         │ [Authorize GitHub]    │
         └───────────────────────┘
                     │
                     ↓
         Success → account.id returned
                     │
                     ↓
         CF saves to database:
         user_integrations table
         (user_id, service, account_id)
                     │
                     ↓
         CF can now execute actions:
         pdBackend.actions.execute({
           componentKey: "github-create-issue",
           accountId: saved_account_id,
           props: { ... }
         })
```

**Database Schema:**

```sql
CREATE TABLE user_integrations (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  service VARCHAR(50) NOT NULL,  -- 'github', 'slack', 'discord'
  account_id VARCHAR(100) NOT NULL,  -- Pipedream account ID
  account_name VARCHAR(255),  -- User's account name
  connected_at TIMESTAMP DEFAULT NOW(),
  last_used_at TIMESTAMP,
  UNIQUE(user_id, service)
);
```

**Code Implementation:**

```typescript
// lib/integrations/pipedream.ts
import { PipedreamClient } from "@pipedream/sdk/server";
import { createFrontendClient } from "@pipedream/sdk/browser";

export const pdBackend = new PipedreamClient({
  projectId: process.env.PIPEDREAM_PROJECT_ID!,
  projectEnvironment: "production",
  clientId: process.env.PIPEDREAM_CLIENT_ID!,
  clientSecret: process.env.PIPEDREAM_CLIENT_SECRET!,
});

export async function createUserToken(cfUserId: string) {
  return await pdBackend.tokens.create({
    externalUserId: cfUserId,
    allowedOrigins: [process.env.APP_URL!],
  });
}

export async function executeAction(
  accountId: string,
  componentKey: string,
  props: Record<string, any>
) {
  return await pdBackend.actions.execute({
    componentKey,
    accountId,
    props,
  });
}
```

```typescript
// components/IntegrationSettings.tsx
"use client"
import { useEffect, useState } from "react";
import { FrontendClientProvider } from "@pipedream/connect-react";
import { createFrontendClient } from "@pipedream/sdk/browser";

export function IntegrationSettings({ userId }: { userId: string }) {
  const [client, setClient] = useState(null);
  const [connections, setConnections] = useState([]);

  useEffect(() => {
    async function initClient() {
      const res = await fetch('/api/pipedream/token');
      const { token } = await res.json();

      const pdClient = createFrontendClient({
        tokenCallback: async () => token,
      });

      setClient(pdClient);
    }
    initClient();
  }, []);

  const connectService = async (service: string) => {
    if (!client) return;

    client.connectAccount({
      appSlug: service,
      onSuccess: async (account) => {
        // Save to CF database
        await fetch('/api/integrations/connect', {
          method: 'POST',
          body: JSON.stringify({
            service,
            account_id: account.id,
            account_name: account.name,
          })
        });

        // Refresh connections list
        loadConnections();
      },
      onError: (error) => {
        console.error('Connection failed:', error);
      }
    });
  };

  return (
    <FrontendClientProvider client={client}>
      <div className="integrations-settings">
        <h2>Connected Services</h2>

        <div className="service-grid">
          <button onClick={() => connectService('github')}>
            Connect GitHub
          </button>
          <button onClick={() => connectService('slack')}>
            Connect Slack
          </button>
          <button onClick={() => connectService('discord')}>
            Connect Discord
          </button>
          <button onClick={() => connectService('notion')}>
            Connect Notion
          </button>
        </div>

        <h3>Active Connections</h3>
        <ul>
          {connections.map(conn => (
            <li key={conn.service}>
              {conn.service}: {conn.account_name}
            </li>
          ))}
        </ul>
      </div>
    </FrontendClientProvider>
  );
}
```

```typescript
// app/api/integrations/connect/route.ts
import { NextResponse } from 'next/server';
import { db } from '@/lib/database';

export async function POST(request: Request) {
  const { service, account_id, account_name } = await request.json();
  const userId = request.headers.get('x-user-id'); // From auth middleware

  await db.userIntegrations.upsert({
    where: {
      userId_service: { userId, service }
    },
    update: {
      account_id,
      account_name,
      last_used_at: new Date(),
    },
    create: {
      userId,
      service,
      account_id,
      account_name,
    }
  });

  return NextResponse.json({ success: true });
}
```

**Benefits:**
- 3,000+ integrations instantly available
- Zero OAuth implementation work
- Secure token management
- User-friendly connection flow
- Automatic token refresh

**Challenges:**
- Requires Pipedream account setup
- Monthly cost based on usage
- Data passes through Pipedream

---

### Use Case 2: GitHub CI/CD Pipeline

**Goal:** Automatic builds on every push to main

**Implementation Complexity:** 🟡 Medium
**Estimated Effort:** 3-5 days
**ROI:** 🔥🔥🔥🔥🔥

**Architecture:**

```
GitHub Repository
       │
       │ (push to main)
       │
       ↓
GitHub Webhook
       │
       ↓
Pipedream HTTP Trigger
       │
       ↓
Parse webhook payload
(extract: repo, branch, commit, files changed)
       │
       ↓
Check if .context-foundry/ exists
(determines if CF-managed project)
       │
       ↓
Call CF Daemon HTTP API:
POST /jobs
{
  "type": "autonomous_build",
  "params": {
    "task": "Build from latest commit",
    "working_directory": "/tmp/builds/{repo}",
    "existing_repo": "{clone_url}",
    "mode": "incremental"
  }
}
       │
       ↓
Receive job_id immediately
       │
       ↓
Update GitHub Commit Status:
"CF Build: In Progress"
       │
       ↓
Subscribe to CF webhook events
(phase_complete, build_complete)
       │
       ↓
On build_complete:
  - Update GitHub Commit Status
  - Add comment to PR (if applicable)
  - Deploy to staging (if tests passed)
  - Send Slack notification
```

**Prerequisites:**

1. **CF Daemon HTTP API** (needs to be built - see Technical Reference)
2. **CF Webhook Publisher** (needs to be built)
3. **GitHub App** (for commit statuses)

**Pipedream Workflow 1: GitHub Push → CF Build**

```javascript
// Workflow: github-push-to-cf-build
export default defineComponent({
  name: "GitHub Push to CF Build",
  version: "0.0.1",
  props: {
    github: {
      type: "app",
      app: "github",
    },
    http: {
      type: "$.interface.http",
      customResponse: true,
    },
  },
  async run({ steps, $ }) {
    const payload = steps.trigger.event.body;
    const { repository, ref, commits, head_commit } = payload;

    // Only process main branch
    const branch = ref.split('/').pop();
    if (branch !== 'main') {
      $.respond({ status: 200, body: { skipped: true } });
      return;
    }

    // Check if CF-managed project
    const hasContextFoundry = commits.some(commit =>
      commit.added.includes('.context-foundry/') ||
      commit.modified.includes('.context-foundry/')
    );

    if (!hasContextFoundry) {
      $.respond({ status: 200, body: { skipped: true, reason: "Not a CF project" } });
      return;
    }

    // Create GitHub commit status
    await axios($, {
      method: "POST",
      url: `https://api.github.com/repos/${repository.full_name}/statuses/${head_commit.id}`,
      headers: {
        "Authorization": `Bearer ${this.github.$auth.oauth_access_token}`,
      },
      data: {
        state: "pending",
        description: "Context Foundry build in progress",
        context: "context-foundry/build",
      }
    });

    // Submit CF build
    const cfJob = await axios($, {
      method: "POST",
      url: `${process.env.CF_API_URL}/jobs`,
      headers: {
        "Authorization": `Bearer ${process.env.CF_API_KEY}`,
      },
      data: {
        type: "autonomous_build",
        params: {
          task: `Build ${repository.name} from commit ${head_commit.id.substring(0, 7)}`,
          working_directory: `/tmp/builds/${repository.full_name}`,
          existing_repo: repository.clone_url,
          mode: "incremental",
          github_context: {
            repo: repository.full_name,
            commit: head_commit.id,
            branch: branch,
          }
        }
      }
    });

    $.respond({
      status: 200,
      body: {
        message: "CF build started",
        job_id: cfJob.data.job_id
      }
    });

    // Store for webhook listener
    $.export("job_id", cfJob.data.job_id);
    $.export("commit_sha", head_commit.id);
    $.export("repo", repository.full_name);

    return cfJob.data;
  }
});
```

**Pipedream Workflow 2: CF Build Complete → Update GitHub**

```javascript
// Workflow: cf-build-complete-github-status
export default defineComponent({
  name: "CF Build Complete - Update GitHub",
  version: "0.0.1",
  props: {
    github: {
      type: "app",
      app: "github",
    },
    http: {
      type: "$.interface.http",
      customResponse: true,
    },
  },
  async run({ steps, $ }) {
    const { event, job_id, status, github_context, result } = steps.trigger.event.body;

    if (event !== "build_complete") return;

    const { repo, commit } = github_context;

    // Update commit status
    const state = status === "success" ? "success" : "failure";
    await axios($, {
      method: "POST",
      url: `https://api.github.com/repos/${repo}/statuses/${commit}`,
      headers: {
        "Authorization": `Bearer ${this.github.$auth.oauth_access_token}`,
      },
      data: {
        state: state,
        description: status === "success"
          ? `Build completed in ${result.duration_seconds}s`
          : `Build failed: ${result.error}`,
        context: "context-foundry/build",
        target_url: `${process.env.CF_DASHBOARD_URL}/jobs/${job_id}`
      }
    });

    // Add comment to PR if applicable
    // ... (check if commit is part of open PR)

    $.respond({ status: 200, body: { updated: true } });

    return { state, commit, repo };
  }
});
```

**Benefits:**
- Fully automated CI/CD
- Self-healing builds (CF auto-fixes failures)
- GitHub integration (commit statuses)
- Incremental builds (10-40% faster)

**Challenges:**
- Requires CF HTTP API
- GitHub App setup
- Webhook configuration

---

### Use Case 3: Discord Command Interface

**Goal:** Natural language builds from Discord

**Implementation Complexity:** 🟡 Medium
**Estimated Effort:** 2-3 days
**ROI:** 🔥🔥🔥🔥

**Architecture:**

```
Discord Server
       │
       │ User: /build weather-app with React
       │
       ↓
Discord Slash Command Webhook
       │
       ↓
Pipedream HTTP Trigger
       │
       ↓
Parse command options
(extract: description, working_dir, flags)
       │
       ↓
Validate user permissions
(check if user is team member)
       │
       ↓
Submit CF build via API
       │
       ↓
Create Discord thread for updates
       │
       ↓
Post initial message:
"🔨 Building weather-app..."
       │
       ↓
Listen for CF webhook events
       │
       ↓
On phase_complete:
  Post update to thread:
  "✅ Scout phase complete"
       │
       ↓
On build_complete:
  Post final summary with GitHub link
```

**Discord Bot Setup:**

1. Create Discord app at discord.com/developers
2. Add slash command: `/build`
3. Configure command options:
   - `description` (required, string): "What to build"
   - `working_dir` (optional, string): "Working directory"
4. Set interaction endpoint to Pipedream webhook URL

**Pipedream Workflow 1: Discord Command → CF Build**

```javascript
// Workflow: discord-slash-command-build
export default defineComponent({
  name: "Discord Slash Command - Build",
  version: "0.0.1",
  props: {
    discord: {
      type: "app",
      app: "discord_webhook",
    },
    http: {
      type: "$.interface.http",
      customResponse: true,
    },
  },
  async run({ steps, $ }) {
    const interaction = steps.trigger.event.body;
    const { type, data, channel_id, member } = interaction;

    // Verify it's a slash command
    if (type !== 2) { // APPLICATION_COMMAND
      $.respond({ status: 200, body: { type: 1 } }); // PONG
      return;
    }

    const options = data.options || [];
    const description = options.find(opt => opt.name === 'description')?.value;
    const workingDir = options.find(opt => opt.name === 'working_dir')?.value;

    if (!description) {
      $.respond({
        status: 200,
        body: {
          type: 4, // CHANNEL_MESSAGE_WITH_SOURCE
          data: {
            content: "❌ Please provide a description of what to build",
            flags: 64 // EPHEMERAL
          }
        }
      });
      return;
    }

    // Extract project name from description
    const projectName = description.split(' ')[0].toLowerCase().replace(/[^a-z0-9-]/g, '-');
    const finalWorkingDir = workingDir || `/tmp/builds/${projectName}`;

    // Respond immediately (Discord requires response within 3 seconds)
    $.respond({
      status: 200,
      body: {
        type: 4,
        data: {
          content: `🔨 Starting build: ${description}`,
        }
      }
    });

    // Submit CF build
    const cfJob = await axios($, {
      method: "POST",
      url: `${process.env.CF_API_URL}/jobs`,
      headers: {
        "Authorization": `Bearer ${process.env.CF_API_KEY}`,
      },
      data: {
        type: "autonomous_build",
        params: {
          task: description,
          working_directory: finalWorkingDir,
          github_repo_name: projectName,
          mode: "new_project",
        }
      }
    });

    // Create Discord thread for updates
    const thread = await axios($, {
      method: "POST",
      url: `https://discord.com/api/v10/channels/${channel_id}/threads`,
      headers: {
        "Authorization": `Bot ${this.discord.$auth.bot_token}`,
      },
      data: {
        name: `Build: ${projectName}`,
        type: 11, // PUBLIC_THREAD
        auto_archive_duration: 1440, // 24 hours
      }
    });

    // Send initial message to thread
    await axios($, {
      method: "POST",
      url: `https://discord.com/api/v10/channels/${thread.data.id}/messages`,
      headers: {
        "Authorization": `Bot ${this.discord.$auth.bot_token}`,
      },
      data: {
        content: `🔨 **Building ${projectName}**\n\n` +
                 `Task: ${description}\n` +
                 `Job ID: \`${cfJob.data.job_id}\`\n\n` +
                 `I'll post updates here as the build progresses...`
      }
    });

    // Store for webhook listener
    $.export("thread_id", thread.data.id);
    $.export("job_id", cfJob.data.job_id);
    $.export("project_name", projectName);

    return {
      thread_id: thread.data.id,
      job_id: cfJob.data.job_id
    };
  }
});
```

**Pipedream Workflow 2: CF Webhook → Discord Updates**

```javascript
// Workflow: cf-webhook-discord-updates
export default defineComponent({
  name: "CF Webhook - Discord Updates",
  version: "0.0.1",
  props: {
    discord: {
      type: "app",
      app: "discord_webhook",
    },
    http: {
      type: "$.interface.http",
      customResponse: true,
    },
  },
  async run({ steps, $ }) {
    const { event, job_id, phase, status, data } = steps.trigger.event.body;

    // Look up thread_id from stored data (use data store or database)
    const threadId = await getThreadIdForJob(job_id);
    if (!threadId) {
      return { skipped: true, reason: "No thread found" };
    }

    let message = "";
    let emoji = "";

    if (event === "phase_complete") {
      emoji = "✅";
      message = `${emoji} **${phase} phase complete**\n${data.summary || ''}`;
    } else if (event === "build_complete") {
      if (status === "success") {
        emoji = "🎉";
        message = `${emoji} **Build Complete!**\n\n` +
                  `Duration: ${data.duration_seconds}s\n` +
                  `Tests: ${data.tests_passed}/${data.tests_total}\n` +
                  `GitHub: ${data.github_url}`;
      } else {
        emoji = "❌";
        message = `${emoji} **Build Failed**\n\n` +
                  `Error: ${data.error}\n` +
                  `Phase: ${data.failed_phase}`;
      }
    }

    if (message) {
      await axios($, {
        method: "POST",
        url: `https://discord.com/api/v10/channels/${threadId}/messages`,
        headers: {
          "Authorization": `Bot ${this.discord.$auth.bot_token}`,
        },
        data: { content: message }
      });
    }

    $.respond({ status: 200, body: { updated: true } });

    return { event, thread_id: threadId };
  }
});
```

**Benefits:**
- Natural language interface
- Team collaboration
- Real-time progress updates
- No context switching

**Challenges:**
- Discord bot setup
- Thread management
- State storage for job → thread mapping

---

### Use Case 4: Pattern Marketplace

**Goal:** Validated pattern distribution with analytics

**Implementation Complexity:** 🟡 Medium
**Estimated Effort:** 5-7 days
**ROI:** 🔥🔥🔥

**Architecture:**

```
CF uploads pattern to S3
       ↓
S3 Event Notification
       ↓
Pipedream S3 Trigger
       ↓
Download pattern JSON
       ↓
Validate schema:
- Required fields present?
- Valid JSON structure?
- Reasonable frequency values?
       ↓
Check for duplicates:
- Query pattern registry
- Compare signatures
       ↓
If valid and unique:
  - Merge to global registry
  - Update pattern database
  - Increment pattern count
       ↓
Send Discord notification:
"📦 New pattern: JWT Auth for FastAPI"
       ↓
Track analytics:
- Pattern published event
- Contributor attribution
- Category metrics
```

**Benefits:**
- Automated quality control
- Community engagement
- Usage tracking
- Duplicate prevention

---

## Integration Architecture Options

### Option A: Component-Level Integration (Recommended)

**Approach:** Use Pipedream for OAuth + simple actions only

**Pros:**
- ✅ Quick to implement
- ✅ Leverages Pipedream's strengths
- ✅ Minimal vendor lock-in
- ✅ Clear separation of concerns

**Cons:**
- ❌ Cannot ship pre-configured workflows
- ❌ Limited workflow automation capabilities

**Best For:**
- Getting started quickly
- Adding OAuth to existing integrations
- Simple notification workflows

**Implementation:**

```typescript
// CF uses Pipedream for:
1. OAuth connection management
2. Simple action execution (send message, create issue)

// CF implements directly:
1. Complex workflow logic
2. Build orchestration
3. Pattern management
```

---

### Option B: SDK-Driven Workflow Creation

**Approach:** Programmatically create workflows via Pipedream SDK

**Pros:**
- ✅ Can create custom workflows per user
- ✅ Full control over workflow structure
- ✅ Workflows run on Pipedream infrastructure

**Cons:**
- ❌ More complex to implement
- ❌ Must maintain workflow definitions in code
- ❌ SDK may not support all workflow features

**Best For:**
- Shipping template-like workflows
- Advanced users who want custom automation

**Implementation:**

```typescript
// Create workflow programmatically
async function createBuildNotificationWorkflow(userId: string) {
  // Deploy HTTP trigger
  const trigger = await pdBackend.deployTrigger({
    componentId: "http-webhook",
    configuredProps: {},
    webhookUrl: `https://app.com/webhooks/cf/${userId}`
  });

  // Create action steps (via API)
  // Note: This API is not well-documented
  // May require custom API calls
}
```

---

### Option C: Hybrid Approach (Recommended for Production)

**Approach:** Use Pipedream where it excels, build custom for the rest

**What Pipedream Handles:**
- ✅ OAuth for 3,000+ apps
- ✅ Simple action execution
- ✅ Event-driven triggers (webhooks, cron)

**What CF Handles:**
- ✅ Complex workflow orchestration
- ✅ Build management
- ✅ Pattern learning
- ✅ Multi-phase execution

**Benefits:**
- Best of both worlds
- Flexibility to migrate away from Pipedream if needed
- Clear boundaries

**Architecture:**

```
┌──────────────────────────────────────────────┐
│  Context Foundry (Core)                      │
│  ┌─────────────────────────────────────────┐ │
│  │ Daemon (Job Queue)                      │ │
│  │ 8-Phase Build Workflow                  │ │
│  │ Pattern Management                      │ │
│  │ MCP Server                              │ │
│  └─────────────────────────────────────────┘ │
│                    │                          │
│                    ↓                          │
│  ┌─────────────────────────────────────────┐ │
│  │ Integration Layer                       │ │
│  │ - Direct integrations (GitHub API)      │ │
│  │ - Pipedream client (OAuth + actions)    │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
                     │
                     ↓
         ┌──────────────────────┐
         │ Pipedream (External) │
         │ - OAuth management   │
         │ - Simple actions     │
         │ - Webhooks           │
         └──────────────────────┘
```

---

### Option D: Alternative Platforms

**If Pipedream limitations are blockers, consider:**

| Platform | Pros | Cons | Best For |
|----------|------|------|----------|
| **Temporal** | Self-hostable, durable workflows, unlimited execution time | No OAuth management, must build integrations | Complex orchestration |
| **Inngest** | Event-driven, durable functions, generous free tier | Limited pre-built integrations | Event-driven automation |
| **Merge.dev** | Unified API, white-label option, single integration for many apps | Higher cost, API-focused (not workflow) | OAuth + API calls |
| **Workato** | OEM program, enterprise features, extensive connectors | Enterprise pricing, complex setup | Large teams/orgs |
| **Zapier** | Most popular, extensive integrations, workflow templates | Expensive, limited customization | Non-technical users |
| **n8n** | Self-hostable, workflow editor, fair code license | Must manage infrastructure, fewer integrations | Self-hosted requirement |

**Recommendation for CF:**

1. **Start with Pipedream (Option A)** for quick OAuth + simple actions
2. **Evaluate Temporal or Inngest** if complex orchestration becomes critical
3. **Consider Merge.dev** if white-label is required
4. **Build direct integrations** for critical services (GitHub, Slack, Discord)

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

**Goal:** Enable basic Pipedream integration

**Tasks:**

1. **CF HTTP API Wrapper** (3 days)
   - Create FastAPI wrapper around MCP server
   - Endpoints: POST /jobs, GET /jobs/:id, GET /jobs/:id/logs
   - Add authentication (API keys)
   - Deploy to Railway/Fly.io

2. **Webhook Event Publisher** (2 days)
   - Add webhook publisher to CF Daemon Runner
   - Emit events: build_started, phase_complete, build_complete
   - Configure via environment variable: CF_WEBHOOK_URL

3. **Pipedream Account Setup** (1 day)
   - Create Pipedream account
   - Create project for Context Foundry
   - Get client credentials
   - Test basic workflow

**Deliverables:**
- CF HTTP API running and accessible
- Webhook events being emitted
- Sample Pipedream workflow: "CF webhook → Log to console"

**Success Criteria:**
- Can submit CF build via HTTP POST
- Can receive webhook events in Pipedream
- API is documented with examples

---

### Phase 2: OAuth Integration (Week 3-4)

**Goal:** Let users connect GitHub, Slack, Discord

**Tasks:**

1. **Backend Pipedream Client** (2 days)
   - Install `@pipedream/sdk`
   - Create backend client with credentials
   - Implement token creation endpoint
   - Add account management endpoints

2. **Frontend Integration UI** (3 days)
   - Install `@pipedream/connect-react`
   - Create IntegrationSettings component
   - Add "Connect Service" buttons
   - Handle OAuth callbacks
   - Display connected accounts

3. **Database Schema** (1 day)
   - Create `user_integrations` table
   - Add API routes for saving connections
   - Implement account lookup by service

4. **Action Execution** (2 days)
   - Create helper functions for common actions
   - Test GitHub issue creation
   - Test Slack message sending
   - Handle errors gracefully

**Deliverables:**
- Users can connect GitHub, Slack, Discord
- CF can create GitHub issues using connected account
- CF can send Slack messages using connected account
- Connection status visible in UI

**Success Criteria:**
- OAuth flow works smoothly
- Connected accounts persist in database
- Actions execute successfully

---

### Phase 3: CI/CD Automation (Week 5-6)

**Goal:** Automatic builds on GitHub push

**Tasks:**

1. **GitHub Webhook → CF Build** (2 days)
   - Create Pipedream workflow
   - Parse GitHub webhook payload
   - Submit CF build via API
   - Store job_id for later

2. **CF Build → GitHub Status** (2 days)
   - Listen for CF webhooks in Pipedream
   - Update GitHub commit status
   - Add PR comments
   - Link to CF dashboard

3. **Deployment Pipeline** (3 days)
   - Deploy to staging on success
   - Run E2E tests
   - Request approval in Slack
   - Deploy to production on approval

**Deliverables:**
- GitHub push triggers CF build automatically
- Commit status updated in real-time
- Deployment to staging on success
- Slack approval workflow

**Success Criteria:**
- End-to-end automation works
- No manual intervention required
- Failures handled gracefully

---

### Phase 4: Advanced Features (Week 7-8)

**Goal:** Multi-channel notifications, pattern marketplace

**Tasks:**

1. **Discord Command Interface** (3 days)
   - Set up Discord bot
   - Create slash command
   - Implement Pipedream workflow
   - Thread management

2. **Pattern Validation Pipeline** (2 days)
   - S3 trigger in Pipedream
   - Schema validation
   - Duplicate checking
   - Community notifications

3. **Analytics Dashboard** (3 days)
   - Track pattern downloads
   - Build success rates
   - Integration usage metrics
   - Display in Glass Pane

**Deliverables:**
- Discord slash commands work
- Pattern marketplace with validation
- Analytics dashboard

**Success Criteria:**
- Discord commands trigger builds
- Patterns validated before publishing
- Metrics visible and actionable

---

## Technical Reference

### Environment Variables Required

```bash
# Pipedream Configuration
PIPEDREAM_PROJECT_ID=proj_abc123
PIPEDREAM_PROJECT_ENVIRONMENT=production
PIPEDREAM_CLIENT_ID=pd_client_xyz
PIPEDREAM_CLIENT_SECRET=pd_secret_abc
PIPEDREAM_ALLOWED_ORIGINS=["https://context-foundry.app"]

# Context Foundry Configuration
CF_API_URL=https://api.context-foundry.app
CF_API_KEY=cf_secret_key_here
CF_WEBHOOK_URL=https://pipedream.com/api/webhooks/abc123
CF_DASHBOARD_URL=https://dashboard.context-foundry.app

# Integration Configuration (examples only—use your own secrets, never commit real keys)
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY=<your_github_app_private_key_here>
DISCORD_BOT_TOKEN=<your_discord_bot_token_here>
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...

# AWS Configuration (for S3 pattern sync)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
S3_PATTERN_BUCKET=bedrock-builder-kb-898587418237
```

---

### CF HTTP API Specification

**Base URL:** `https://api.context-foundry.app/v1`

**Authentication:** Bearer token in Authorization header

#### POST /jobs

Submit a new CF job.

**Request:**
```json
{
  "type": "autonomous_build",
  "params": {
    "task": "Build weather app with React",
    "working_directory": "/tmp/builds/weather-app",
    "github_repo_name": "weather-app",
    "mode": "new_project"
  }
}
```

**Response:**
```json
{
  "job_id": "abc-123-def-456",
  "status": "started",
  "created_at": "2025-11-20T10:00:00Z"
}
```

---

#### GET /jobs/:id

Get job status and details.

**Response:**
```json
{
  "id": "abc-123-def-456",
  "type": "autonomous_build",
  "status": "running",
  "current_phase": "Builder",
  "progress": 0.45,
  "created_at": "2025-11-20T10:00:00Z",
  "started_at": "2025-11-20T10:00:05Z",
  "params": {
    "task": "Build weather app with React",
    "working_directory": "/tmp/builds/weather-app"
  }
}
```

---

#### GET /jobs/:id/logs

Get job logs.

**Query Parameters:**
- `offset` (int): Line offset
- `limit` (int): Max lines to return

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-11-20T10:00:10Z",
      "level": "info",
      "phase": "Scout",
      "message": "Researching weather APIs..."
    }
  ],
  "has_more": true,
  "total": 1523
}
```

---

#### POST /jobs/:id/cancel

Cancel a running job.

**Response:**
```json
{
  "success": true,
  "job_id": "abc-123-def-456",
  "status": "cancelled"
}
```

---

### CF Webhook Event Payloads

**Event: build_started**
```json
{
  "event": "build_started",
  "timestamp": "2025-11-20T10:00:00Z",
  "job_id": "abc-123-def-456",
  "project": "weather-app",
  "task": "Build weather app with React"
}
```

**Event: phase_complete**
```json
{
  "event": "phase_complete",
  "timestamp": "2025-11-20T10:05:00Z",
  "job_id": "abc-123-def-456",
  "phase": "Scout",
  "data": {
    "summary": "Researched OpenWeatherMap API, identified React + TypeScript stack",
    "tokens_used": 15234,
    "duration_seconds": 45
  }
}
```

**Event: build_complete**
```json
{
  "event": "build_complete",
  "timestamp": "2025-11-20T10:15:00Z",
  "job_id": "abc-123-def-456",
  "status": "success",
  "data": {
    "duration_seconds": 754,
    "tests_passed": 142,
    "tests_total": 142,
    "phases_completed": ["Scout", "Architect", "Builder", "Test", "Screenshot", "Docs", "Deploy", "Feedback"],
    "github_url": "https://github.com/user/weather-app",
    "deployed_url": "https://user.github.io/weather-app"
  }
}
```

---

### Common Code Patterns

**Execute GitHub Action:**

```typescript
import { pdBackend } from '@/lib/integrations/pipedream';

async function createGitHubIssue(
  userAccountId: string,
  repo: string,
  title: string,
  body: string
) {
  const result = await pdBackend.actions.execute({
    componentKey: "github-create-issue",
    accountId: userAccountId,
    props: {
      repoFullname: repo,
      title: title,
      body: body,
      labels: ["context-foundry", "automated"],
    }
  });

  return result;
}
```

**Execute Slack Action:**

```typescript
async function sendSlackNotification(
  userAccountId: string,
  channel: string,
  message: string
) {
  const result = await pdBackend.actions.execute({
    componentKey: "slack-send-message",
    accountId: userAccountId,
    props: {
      channel: channel,
      text: message,
      mrkdwn: true,
    }
  });

  return result;
}
```

**Handle OAuth Connection:**

```typescript
// Frontend component
const client = createFrontendClient({
  tokenCallback: async () => {
    const res = await fetch('/api/pipedream/token');
    return res.json();
  }
});

client.connectAccount({
  appSlug: 'github',
  onSuccess: async (account) => {
    await fetch('/api/integrations/connect', {
      method: 'POST',
      body: JSON.stringify({
        service: 'github',
        account_id: account.id,
        account_name: account.name,
      })
    });
  },
  onError: (error) => {
    console.error('Connection failed:', error);
  }
});
```

---

## Alternatives Comparison

### Pipedream vs. Temporal

| Feature | Pipedream | Temporal |
|---------|-----------|----------|
| **Self-Hosting** | ❌ No | ✅ Yes |
| **Execution Time** | ⚠️ Limited (~15min?) | ✅ Unlimited |
| **OAuth Management** | ✅ 3,000+ apps | ❌ Build yourself |
| **Workflow Templates** | ❌ No export | ✅ Full code control |
| **Pre-Built Integrations** | ✅ 10,000+ | ❌ None |
| **Learning Curve** | 🟢 Low | 🔴 High |
| **Cost** | Pay per invocation | Infrastructure + hosting |

**Verdict:** Pipedream for OAuth + simple actions, Temporal for complex orchestration

---

### Pipedream vs. Inngest

| Feature | Pipedream | Inngest |
|---------|-----------|----------|
| **Self-Hosting** | ❌ No | ✅ Yes (OSS) |
| **Event-Driven** | ✅ Yes | ✅ Yes (core strength) |
| **OAuth Management** | ✅ 3,000+ apps | ❌ Build yourself |
| **Durable Functions** | ⚠️ Limited | ✅ First-class |
| **Pre-Built Integrations** | ✅ 10,000+ | ❌ None |
| **Free Tier** | Limited invocations | Generous (25k events/month) |

**Verdict:** Inngest better for event-driven architecture, Pipedream better for integrations

---

### Pipedream vs. Merge.dev

| Feature | Pipedream | Merge.dev |
|---------|-----------|----------|
| **White-Label** | ❌ No | ✅ Yes |
| **OAuth Management** | ✅ 3,000+ apps | ✅ Unified API |
| **Workflow Automation** | ✅ Full workflows | ❌ API calls only |
| **Pre-Built Integrations** | ✅ 10,000+ | ✅ 200+ (unified) |
| **Cost** | Per invocation | Per linked account |
| **Integration Model** | Component-based | Unified API |

**Verdict:** Merge.dev if you need white-label + unified API, Pipedream for workflows

---

## Conclusion

### The Bottom Line

**Pipedream is EXCELLENT for:**
- ✅ Managed OAuth (3,000+ apps)
- ✅ Simple action execution
- ✅ Event-driven triggers
- ✅ Rapid prototyping

**Pipedream is POOR for:**
- ❌ Shipping pre-configured workflows
- ❌ Self-hosted execution
- ❌ Custom private components
- ❌ White-label requirements

### Recommended Integration Strategy

**For Context Foundry:**

1. **Phase 1 (Immediate):** Use Pipedream for OAuth
   - Quick win: Connect GitHub, Slack, Discord
   - Low effort, high value
   - Clear boundaries

2. **Phase 2 (Short-term):** Add GitHub CI/CD automation
   - GitHub webhook → CF build
   - Build status → GitHub
   - Proven use case

3. **Phase 3 (Medium-term):** Multi-channel notifications
   - CF webhooks → Pipedream → Slack/Discord/Email
   - Flexible routing
   - Easy to extend

4. **Phase 4 (Long-term):** Evaluate alternatives
   - As CF scales, re-evaluate Temporal/Inngest
   - Consider white-label requirements
   - Assess vendor lock-in risk

### Final Recommendation

**Use Pipedream as a complementary layer, not the core workflow engine.**

Build the critical path (build orchestration, pattern learning) in Context Foundry, and leverage Pipedream for the periphery (OAuth, notifications, simple integrations).

This gives you flexibility to migrate away from Pipedream if needed, while still benefiting from its strengths today.

---

## Next Steps

1. **Set up Pipedream account** and create project
2. **Implement CF HTTP API** wrapper (Priority 1)
3. **Add webhook event publisher** to CF Daemon (Priority 1)
4. **Test OAuth integration** with GitHub (Priority 2)
5. **Build GitHub CI/CD workflow** (Priority 2)
6. **Document integration patterns** for community

---

## Appendix

### Resources

- **Pipedream Docs:** https://pipedream.com/docs
- **Pipedream SDK:** https://github.com/PipedreamHQ/pipedream/tree/master/packages/sdk
- **Pipedream Connect Examples:** https://github.com/PipedreamHQ/pipedream-connect-examples
- **Context Foundry MCP Server:** `/Users/name/homelab/context-foundry/tools/mcp_server.py`
- **Context Foundry Daemon:** `/Users/name/homelab/context-foundry/context_foundry/daemon/`

### Contact

For questions about this integration guide, contact the Context Foundry team or open an issue in the repository.

---

**Document Version:** 1.0
**Last Updated:** 2025-11-20
**Maintained By:** Context Foundry Team
