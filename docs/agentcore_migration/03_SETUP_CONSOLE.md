# AWS Bedrock AgentCore Setup: Console Guide (UI)

This guide walks you through setting up your first Context Foundry agent using the **AWS Management Console**. This is great for learning the concepts visually.

## 1. Access Bedrock Agents
1.  Log in to the **AWS Console**.
2.  Navigate to **Amazon Bedrock**.
3.  In the left sidebar, under **Orchestration**, click **Agents**.
4.  Click the orange **Create Agent** button.

## 2. Configure Agent Details
*   **Name:** `ContextFoundry-Builder`
*   **Description:** "Autonomous software builder agent."
*   **User Input:** Select "Yes" (The agent interacts with a user).
*   **IAM Role:** Select "Create and use a new service role". AWS will handle permissions for you.
*   **Model:** Choose **Anthropic Claude 3 Sonnet** (or Opus if available/preferred).
*   **Instructions:** Paste the following system prompt:
    > You are an expert software architect and builder. Your goal is to plan and write code for software projects based on user specifications. You have access to tools for writing files and reading documentation. Always verify your plan before writing code.

Click **Next**.

## 3. Add Action Groups (Tools)
This is where we define the "Hands".

1.  Click **Add** in the "Action groups" section.
2.  **Action Group Name:** `LocalFileTools`
3.  **Action Group Type:** "Define with API schemas".
4.  **Action Group Invocation:**
    *   *Option A (Lambda):* Select an existing Lambda function if you have the Bridge set up.
    *   *Option B (Return Control):* Select **"Return Control"**. This is useful for local development! It means the Agent will pause and send the tool request back to your local script, which executes it and sends the result back. **Recommended for initial testing.**
5.  **API Schema:**
    *   You can upload an OpenAPI JSON file defining `write_file`, `read_file`, etc.
    *   Or use the visual Schema Editor to define functions like `write_file(path, content)`.

Click **Next**.

## 4. Knowledge Bases (Memory)
(Optional) If you have a vector database with documentation, you can attach it here. For now, we will rely on the built-in **Session Memory**.

Click **Next**.

## 5. Review and Create
Review your settings and click **Create Agent**.

## 6. Test in the Playground
Once created, you will see a **Test Agent** panel on the right.

1.  Click **Prepare** (this packages the agent).
2.  Type: "Create a plan for a simple calculator."
3.  Watch the "Trace" to see the agent's thought process (Pre-processing, Orchestration, Post-processing).
4.  If it calls a tool (and you chose "Return Control"), the playground will show the tool request JSON.

## 🎓 Success!
You have manually created a Cloud Brain! You can now copy the **Agent ID** and **Alias ID** to use in your `ContextFoundry` configuration.
