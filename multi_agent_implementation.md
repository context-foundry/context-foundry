# Multi-Agent System Implementation for Context Foundry
## Based on Anthropic's Research System Architecture

**Source:** https://www.anthropic.com/engineering/multi-agent-research-system

---

## Executive Summary

Transform Context Foundry from a sequential 3-phase system (Scout→Architect→Builder) into a **parallel multi-agent orchestrator** that:
- Spawns multiple subagents to work simultaneously
- Uses extended thinking for planning and evaluation
- Implements self-healing through error feedback loops
- Achieves 90%+ performance gains through parallelization
- Scales token usage effectively across multiple context windows

**Key Insight from Anthropic:** Token usage explains 80% of performance variance. Multi-agent systems effectively scale token usage by distributing work across agents with separate context windows.

---

## Current vs. Target Architecture

### Current Architecture (Sequential)
```
User Request
    ↓
Scout Agent (sequential research)
    ↓
Architect Agent (sequential planning)
    ↓
Builder Agent (sequential task execution)
    ↓
Verification (sequential checks)
    ↓
Result
```

**Problems:**
- Sequential = slow
- Single context window = limited token budget
- No parallelization of independent tasks
- Builder executes tasks one-by-one
- No self-healing on failures

### Target Architecture (Parallel Multi-Agent)
```
User Request
    ↓
Lead Orchestrator (with extended thinking)
    ├─→ Scout Subagent 1 (research API patterns)    ──┐
    ├─→ Scout Subagent 2 (research auth strategies) ──┼─→ Compress & synthesize
    └─→ Scout Subagent 3 (research deployment)      ──┘
         ↓
    Planning Phase (Architect with extended thinking)
         ↓
    ├─→ Builder Subagent 1 (auth module)   ──┐
    ├─→ Builder Subagent 2 (API routes)    ──┼─→ Parallel execution
    ├─→ Builder Subagent 3 (database)      ──┤
    └─→ Builder Subagent 4 (tests)         ──┘
         ↓
    ├─→ Validator Subagent 1 (smoke test)  ──┐
    ├─→ Validator Subagent 2 (contract)    ──┼─→ Parallel validation
    └─→ Validator Subagent 3 (security)    ──┘
         ↓
    [Self-Healing Loop if failures]
         ↓
    Result
```

---

## Implementation Plan

### Phase 1: Lead Orchestrator with Extended Thinking (Week 1)

**Objective:** Create a Lead Orchestrator that uses extended thinking to plan the entire build workflow.

#### 1.1 Create Lead Orchestrator Agent

**File:** `ace/orchestrator/lead_orchestrator.py`

```python
"""
Lead Orchestrator Agent - Plans and coordinates all subagents.

Based on Anthropic's multi-agent research system architecture.
Uses extended thinking for planning and coordination.
"""

import anthropic
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
import json

@dataclass
class SubagentTask:
    """Task definition for a subagent."""
    id: str
    type: str  # 'scout', 'builder', 'validator'
    objective: str
    output_format: str
    tools: List[str]
    sources: List[str]
    boundaries: str
    priority: int = 1

@dataclass
class WorkflowPlan:
    """Complete workflow plan from Lead Orchestrator."""
    complexity_assessment: str
    scout_tasks: List[SubagentTask]
    architect_strategy: str
    builder_tasks: List[SubagentTask]
    validation_tasks: List[SubagentTask]
    estimated_duration: str
    parallelization_strategy: str

class LeadOrchestrator:
    """
    Lead agent that plans and coordinates all subagents.
    
    Uses extended thinking to:
    - Assess query complexity
    - Decompose into parallelizable tasks
    - Coordinate subagents
    - Synthesize results
    - Adapt based on findings
    """
    
    PLANNING_PROMPT = """
You are the Lead Orchestrator for Context Foundry, an AI development system.

Your role: Analyze the user's request and create a comprehensive workflow plan.

USER REQUEST:
{user_request}

PLANNING INSTRUCTIONS:

1. ASSESS COMPLEXITY
   - Simple: Basic CRUD app, single service (1-3 subagents)
   - Medium: Multiple services, auth, database (4-7 subagents)
   - Complex: Microservices, real-time, complex logic (8+ subagents)

2. DECOMPOSE RESEARCH (Scout Phase)
   Create 3-5 parallel research tasks:
   - Each explores a different aspect
   - Clear boundaries (no overlap)
   - Specific output format
   - Independent from each other
   
   Example for "Build e-commerce API":
   - Scout 1: Research product catalog patterns
   - Scout 2: Research payment integration best practices
   - Scout 3: Research order management systems
   - Scout 4: Research authentication for e-commerce
   - Scout 5: Research deployment strategies for Node.js APIs

3. PLAN ARCHITECTURE STRATEGY
   How should Architect approach this?
   - What patterns to prioritize
   - What trade-offs to consider
   - How to structure the codebase

4. DECOMPOSE IMPLEMENTATION (Builder Phase)
   Create 5-10 parallel build tasks:
   - Each is independent (can run simultaneously)
   - Clear interfaces between modules
   - Specific deliverables
   - Test requirements
   
   Example for "Build e-commerce API":
   - Builder 1: User authentication module + tests
   - Builder 2: Product catalog API + tests
   - Builder 3: Shopping cart logic + tests
   - Builder 4: Order processing + tests
   - Builder 5: Payment integration + tests
   - Builder 6: Database schema + migrations
   - Builder 7: API documentation
   - Builder 8: Deployment configuration

5. PLAN VALIDATION
   Create 3-5 parallel validation tasks:
   - Smoke tests (does it start?)
   - Contract tests (does API match spec?)
   - Security checks (basic vulnerabilities?)
   - Performance checks (acceptable response times?)

6. PARALLELIZATION STRATEGY
   - Which tasks can run in parallel?
   - What dependencies exist?
   - What's the critical path?

Use extended thinking to reason through your plan.
Output your plan as structured JSON.
"""

    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self.model = "claude-sonnet-4-20250514"
        
    def plan_workflow(self, user_request: str, project_context: Dict = None) -> WorkflowPlan:
        """
        Use extended thinking to create a comprehensive workflow plan.
        
        Returns a WorkflowPlan with all subagent tasks defined.
        """
        
        print("\n" + "="*80)
        print("🧠 LEAD ORCHESTRATOR - PLANNING WORKFLOW")
        print("="*80)
        print(f"\nRequest: {user_request}")
        print("\nUsing extended thinking to analyze and plan...")
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 10000
            },
            messages=[{
                "role": "user",
                "content": self.PLANNING_PROMPT.format(
                    user_request=user_request
                )
            }]
        )
        
        # Extract thinking and plan
        thinking_content = ""
        plan_content = ""
        
        for block in response.content:
            if block.type == "thinking":
                thinking_content = block.thinking
            elif block.type == "text":
                plan_content = block.text
        
        print("\n📋 Planning Complete")
        print(f"Thinking tokens used: {len(thinking_content.split())}")
        
        # Parse the plan
        try:
            plan_json = json.loads(plan_content)
            workflow_plan = self._parse_workflow_plan(plan_json)
            
            self._print_workflow_summary(workflow_plan)
            
            return workflow_plan
            
        except json.JSONDecodeError:
            raise ValueError("Lead Orchestrator failed to produce valid JSON plan")
    
    def _parse_workflow_plan(self, plan_json: Dict) -> WorkflowPlan:
        """Parse JSON plan into WorkflowPlan dataclass."""
        
        scout_tasks = [
            SubagentTask(**task) for task in plan_json.get('scout_tasks', [])
        ]
        
        builder_tasks = [
            SubagentTask(**task) for task in plan_json.get('builder_tasks', [])
        ]
        
        validation_tasks = [
            SubagentTask(**task) for task in plan_json.get('validation_tasks', [])
        ]
        
        return WorkflowPlan(
            complexity_assessment=plan_json.get('complexity_assessment'),
            scout_tasks=scout_tasks,
            architect_strategy=plan_json.get('architect_strategy'),
            builder_tasks=builder_tasks,
            validation_tasks=validation_tasks,
            estimated_duration=plan_json.get('estimated_duration'),
            parallelization_strategy=plan_json.get('parallelization_strategy')
        )
    
    def _print_workflow_summary(self, plan: WorkflowPlan):
        """Print human-readable workflow summary."""
        
        print(f"\n📊 Complexity: {plan.complexity_assessment}")
        print(f"⏱️  Estimated Duration: {plan.estimated_duration}")
        
        print(f"\n🔍 Scout Phase: {len(plan.scout_tasks)} parallel research tasks")
        for task in plan.scout_tasks:
            print(f"   └─ {task.id}: {task.objective[:60]}...")
        
        print(f"\n🔨 Builder Phase: {len(plan.builder_tasks)} parallel build tasks")
        for task in plan.builder_tasks:
            print(f"   └─ {task.id}: {task.objective[:60]}...")
        
        print(f"\n✅ Validation Phase: {len(plan.validation_tasks)} parallel checks")
        for task in plan.validation_tasks:
            print(f"   └─ {task.id}: {task.objective[:60]}...")
        
        print(f"\n🔀 Parallelization Strategy:")
        print(f"   {plan.parallelization_strategy}")
    
    def coordinate_subagents(self, plan: WorkflowPlan) -> Dict[str, Any]:
        """
        Execute the workflow plan by coordinating subagents.
        
        This method spawns subagents in parallel and manages their execution.
        """
        
        results = {
            'scout_results': None,
            'architect_result': None,
            'builder_results': None,
            'validation_results': None
        }
        
        # Execute Scout phase in parallel
        results['scout_results'] = self._execute_parallel_scouts(plan.scout_tasks)
        
        # Execute Architect phase (single agent with strategy)
        results['architect_result'] = self._execute_architect(
            plan.architect_strategy,
            results['scout_results']
        )
        
        # Execute Builder phase in parallel
        results['builder_results'] = self._execute_parallel_builders(
            plan.builder_tasks,
            results['architect_result']
        )
        
        # Execute Validation phase in parallel
        results['validation_results'] = self._execute_parallel_validators(
            plan.validation_tasks,
            results['builder_results']
        )
        
        return results
    
    def _execute_parallel_scouts(self, tasks: List[SubagentTask]) -> List[Dict]:
        """Execute Scout subagents in parallel."""
        # Implementation in Phase 2
        pass
    
    def _execute_architect(self, strategy: str, scout_results: List[Dict]) -> Dict:
        """Execute Architect with strategy and compressed Scout findings."""
        # Implementation in Phase 2
        pass
    
    def _execute_parallel_builders(self, tasks: List[SubagentTask], architect_result: Dict) -> List[Dict]:
        """Execute Builder subagents in parallel."""
        # Implementation in Phase 3
        pass
    
    def _execute_parallel_validators(self, tasks: List[SubagentTask], builder_results: List[Dict]) -> List[Dict]:
        """Execute Validator subagents in parallel."""
        # Implementation in Phase 4
        pass
```

#### 1.2 Update Main Orchestrator

**File:** `workflows/autonomous_orchestrator.py`

```python
from ace.orchestrator.lead_orchestrator import LeadOrchestrator

class AutonomousOrchestrator:
    """Main orchestrator - now uses Lead Orchestrator for planning."""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.lead_orchestrator = LeadOrchestrator(self.client)
    
    def run_autonomous_build(self, project_name: str, description: str):
        """
        Run autonomous build with multi-agent coordination.
        """
        
        # Phase 1: Lead Orchestrator plans the workflow
        workflow_plan = self.lead_orchestrator.plan_workflow(
            user_request=description,
            project_context={'name': project_name}
        )
        
        # Phase 2: Execute the plan with parallel subagents
        results = self.lead_orchestrator.coordinate_subagents(workflow_plan)
        
        # Phase 3: Synthesize and return
        return self._synthesize_results(results)
```

**Testing:**
```bash
foundry build test-multi "Build a REST API with authentication"

# Expected output:
# 🧠 LEAD ORCHESTRATOR - PLANNING WORKFLOW
# Request: Build a REST API with authentication
# Using extended thinking to analyze and plan...
#
# 📋 Planning Complete
# Thinking tokens used: 2847
#
# 📊 Complexity: Medium - Multiple services with auth
# ⏱️  Estimated Duration: 2-3 hours
#
# 🔍 Scout Phase: 4 parallel research tasks
#    └─ scout_1: Research REST API best practices...
#    └─ scout_2: Research JWT authentication patterns...
#    └─ scout_3: Research database schema for auth...
#    └─ scout_4: Research API documentation strategies...
```

---

### Phase 2: Parallel Scout Subagents (Week 2)

**Objective:** Implement parallel research through multiple Scout subagents.

#### 2.1 Create Scout Subagent System

**File:** `ace/scouts/scout_subagent.py`

```python
"""
Scout Subagent - Executes focused research tasks in parallel.

Each subagent:
- Has its own context window
- Explores a specific aspect independently
- Uses interleaved thinking after tool results
- Returns compressed findings to Lead Orchestrator
"""

import anthropic
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

class ScoutSubagent:
    """
    Individual Scout subagent that researches a specific topic.
    
    Based on Anthropic's pattern:
    - Independent context window
    - Interleaved thinking for evaluation
    - Compress findings before returning
    """
    
    SUBAGENT_PROMPT = """
You are a Scout subagent. Your objective is focused research on a specific topic.

TASK:
{objective}

OUTPUT FORMAT:
{output_format}

TOOLS AVAILABLE:
{tools}

SOURCES TO PRIORITIZE:
{sources}

TASK BOUNDARIES:
{boundaries}

INSTRUCTIONS:
1. Start with broad searches, then narrow down
2. Use interleaved thinking after each tool result to evaluate:
   - What did I learn?
   - What gaps remain?
   - What should I search next?
3. Gather information from 5-10 sources
4. Synthesize findings into the requested output format
5. Be concise - you're returning findings to a Lead Orchestrator

Important: Stay focused on YOUR specific task. Don't duplicate work from other subagents.

Begin your research now.
"""
    
    def __init__(self, client: anthropic.Anthropic, task: 'SubagentTask'):
        self.client = client
        self.task = task
        self.model = "claude-sonnet-4-20250514"
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the research task with interleaved thinking.
        
        Returns compressed findings for Lead Orchestrator.
        """
        
        print(f"\n   🔍 {self.task.id}: Starting research...")
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            thinking={
                "type": "enabled",
                "budget_tokens": 3000
            },
            messages=[{
                "role": "user",
                "content": self.SUBAGENT_PROMPT.format(
                    objective=self.task.objective,
                    output_format=self.task.output_format,
                    tools=", ".join(self.task.tools),
                    sources=", ".join(self.task.sources),
                    boundaries=self.task.boundaries
                )
            }],
            tools=self._get_tools()
        )
        
        # Process tool calls with interleaved thinking
        findings = self._process_with_tool_loop(response)
        
        print(f"   ✅ {self.task.id}: Research complete")
        
        return {
            'task_id': self.task.id,
            'findings': findings,
            'token_usage': response.usage.input_tokens + response.usage.output_tokens
        }
    
    def _get_tools(self) -> List[Dict]:
        """Return tool definitions for this subagent."""
        return [
            {
                "name": "web_search",
                "description": "Search the web for information",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "read_documentation",
                "description": "Read official documentation",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Documentation URL"}
                    },
                    "required": ["url"]
                }
            }
        ]
    
    def _process_with_tool_loop(self, initial_response) -> str:
        """
        Process tool calls with interleaved thinking.
        
        After each tool result, the agent thinks about what it learned
        and decides the next action.
        """
        
        conversation = []
        current_response = initial_response
        max_turns = 10
        turn = 0
        
        while turn < max_turns:
            turn += 1
            
            # Check if agent wants to use tools
            if current_response.stop_reason == "end_turn":
                # Agent is done
                final_text = ""
                for block in current_response.content:
                    if block.type == "text":
                        final_text += block.text
                return final_text
            
            elif current_response.stop_reason == "tool_use":
                # Execute tools
                tool_results = []
                for block in current_response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                # Continue conversation with tool results
                # Agent will use interleaved thinking to evaluate results
                conversation.append({
                    "role": "assistant",
                    "content": current_response.content
                })
                conversation.append({
                    "role": "user",
                    "content": tool_results
                })
                
                current_response = self.client.messages.create(
                    model=self.model,
                    max_tokens=8000,
                    thinking={
                        "type": "enabled",
                        "budget_tokens": 2000
                    },
                    messages=conversation,
                    tools=self._get_tools()
                )
        
        # Max turns reached
        return "Research incomplete - max turns reached"
    
    def _execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """Execute a tool and return results."""
        # Implement actual tool execution
        # For now, return placeholder
        return f"Tool {tool_name} executed with {tool_input}"

class ParallelScoutCoordinator:
    """Coordinates multiple Scout subagents running in parallel."""
    
    def __init__(self, client: anthropic.Anthropic):
        self.client = client
    
    def execute_parallel(self, tasks: List['SubagentTask']) -> List[Dict]:
        """
        Execute multiple Scout subagents in parallel.
        
        Key insight from Anthropic: Parallelization cuts research time by 90%.
        """
        
        print(f"\n🚀 Launching {len(tasks)} Scout subagents in parallel...")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=min(len(tasks), 5)) as executor:
            # Submit all subagent tasks
            future_to_task = {
                executor.submit(self._execute_subagent, task): task
                for task in tasks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"   ❌ {task.id} failed: {e}")
                    results.append({
                        'task_id': task.id,
                        'error': str(e)
                    })
        
        print(f"✅ All {len(tasks)} Scout subagents complete")
        
        return results
    
    def _execute_subagent(self, task: 'SubagentTask') -> Dict:
        """Execute a single subagent."""
        subagent = ScoutSubagent(self.client, task)
        return subagent.execute()
```

#### 2.2 Integrate with Lead Orchestrator

**File:** `ace/orchestrator/lead_orchestrator.py`

```python
from ace.scouts.scout_subagent import ParallelScoutCoordinator

class LeadOrchestrator:
    
    def __init__(self, client):
        self.client = client
        self.scout_coordinator = ParallelScoutCoordinator(client)
    
    def _execute_parallel_scouts(self, tasks: List[SubagentTask]) -> List[Dict]:
        """Execute Scout subagents in parallel and compress findings."""
        
        # Launch parallel subagents
        raw_results = self.scout_coordinator.execute_parallel(tasks)
        
        # Compress findings for Architect
        compressed = self._compress_scout_findings(raw_results)
        
        return compressed
    
    def _compress_scout_findings(self, raw_results: List[Dict]) -> Dict:
        """
        Compress Scout findings from multiple subagents.
        
        Key insight from Anthropic: Subagents facilitate compression by 
        operating in parallel with their own context windows, then condensing 
        the most important tokens for the lead agent.
        """
        
        print("\n📦 Compressing Scout findings...")
        
        # Concatenate all findings
        all_findings = "\n\n".join([
            f"### {result['task_id']}\n{result.get('findings', result.get('error'))}"
            for result in raw_results
        ])
        
        # Use LLM to compress
        compression_prompt = f"""
Compress these research findings into a concise summary for the Architect.

FINDINGS FROM {len(raw_results)} SCOUT SUBAGENTS:
{all_findings}

Create a structured summary that:
1. Highlights key patterns and best practices
2. Identifies common themes across findings
3. Notes any conflicts or trade-offs
4. Provides actionable recommendations
5. Stays under 2000 tokens

Output the compressed summary now.
"""
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": compression_prompt
            }]
        )
        
        compressed_summary = response.content[0].text
        
        print(f"   Compressed {len(all_findings.split())} tokens → {len(compressed_summary.split())} tokens")
        print(f"   Compression ratio: {len(compressed_summary.split()) / len(all_findings.split()):.1%}")
        
        return {
            'compressed_summary': compressed_summary,
            'raw_results': raw_results,
            'compression_ratio': len(compressed_summary.split()) / len(all_findings.split())
        }
```

**Testing:**
```bash
foundry build test-parallel-scout "Build e-commerce API"

# Expected output:
# 🚀 Launching 5 Scout subagents in parallel...
#    🔍 scout_1: Starting research...
#    🔍 scout_2: Starting research...
#    🔍 scout_3: Starting research...
#    🔍 scout_4: Starting research...
#    🔍 scout_5: Starting research...
#    ✅ scout_1: Research complete
#    ✅ scout_3: Research complete
#    ✅ scout_2: Research complete
#    ✅ scout_5: Research complete
#    ✅ scout_4: Research complete
# ✅ All 5 Scout subagents complete
#
# 📦 Compressing Scout findings...
#    Compressed 4823 tokens → 1247 tokens
#    Compression ratio: 25.9%
```

---

### Phase 3: Parallel Builder Subagents (Week 3)

**Objective:** Implement parallel code generation through multiple Builder subagents.

#### 3.1 Create Builder Subagent System

**File:** `ace/builders/builder_subagent.py`

```python
"""
Builder Subagent - Executes focused implementation tasks in parallel.

Key principles from Anthropic:
- Each subagent has clear boundaries
- Independent execution with own context
- Tests written first (TDD)
- Results stored in filesystem to avoid "game of telephone"
"""

import anthropic
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any

class BuilderSubagent:
    """
    Individual Builder subagent that implements a specific module.
    
    Implements one module/feature independently with tests.
    """
    
    SUBAGENT_PROMPT = """
You are a Builder subagent implementing a specific module.

TASK:
{objective}

OUTPUT FORMAT:
{output_format}

MODULE BOUNDARIES:
{boundaries}

INTERFACES WITH OTHER MODULES:
{interfaces}

ARCHITECT'S GUIDANCE:
{architect_guidance}

INSTRUCTIONS:
1. Write tests FIRST (test-driven development)
2. Implement the module to pass those tests
3. Keep code focused on YOUR module only
4. Document interfaces clearly for other modules
5. Write all files to the filesystem using tools
6. Don't duplicate code from other modules

CRITICAL: Use the write_file tool for each file you create.
This prevents information loss and the "game of telephone" problem.

Begin implementation now.
"""
    
    def __init__(self, client: anthropic.Anthropic, task: 'SubagentTask', 
                 project_dir: Path, architect_result: Dict):
        self.client = client
        self.task = task
        self.project_dir = project_dir
        self.architect_result = architect_result
        self.model = "claude-sonnet-4-20250514"
        self.files_written = []
    
    def execute(self) -> Dict[str, Any]:
        """Execute the build task with TDD approach."""
        
        print(f"\n   🔨 {self.task.id}: Starting implementation...")
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 5000
            },
            messages=[{
                "role": "user",
                "content": self.SUBAGENT_PROMPT.format(
                    objective=self.task.objective,
                    output_format=self.task.output_format,
                    boundaries=self.task.boundaries,
                    interfaces=self._format_interfaces(),
                    architect_guidance=self.architect_result.get('plan_summary', '')
                )
            }],
            tools=self._get_tools()
        )
        
        # Process tool calls (file writes)
        self._process_tool_loop(response)
        
        print(f"   ✅ {self.task.id}: Implementation complete ({len(self.files_written)} files)")
        
        return {
            'task_id': self.task.id,
            'files_written': self.files_written,
            'success': True
        }
    
    def _get_tools(self) -> List[Dict]:
        """Return tool definitions for Builder subagent."""
        return [
            {
                "name": "write_file",
                "description": "Write a file to the project directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path relative to project root"},
                        "content": {"type": "string", "description": "File content"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "read_file",
                "description": "Read an existing file (to check interfaces)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"}
                    },
                    "required": ["path"]
                }
            }
        ]
    
    def _execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """Execute tool and track file writes."""
        
        if tool_name == "write_file":
            file_path = self.project_dir / tool_input['path']
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w') as f:
                f.write(tool_input['content'])
            
            self.files_written.append(str(file_path))
            return f"File written: {tool_input['path']}"
        
        elif tool_name == "read_file":
            file_path = self.project_dir / tool_input['path']
            if file_path.exists():
                return file_path.read_text()
            return f"File not found: {tool_input['path']}"
        
        return "Unknown tool"
    
    def _process_tool_loop(self, initial_response):
        """Process tool calls until agent is done."""
        
        conversation = []
        current_response = initial_response
        max_turns = 20
        turn = 0
        
        while turn < max_turns:
            turn += 1
            
            if current_response.stop_reason == "end_turn":
                return
            
            elif current_response.stop_reason == "tool_use":
                tool_results = []
                for block in current_response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                conversation.append({
                    "role": "assistant",
                    "content": current_response.content
                })
                conversation.append({
                    "role": "user",
                    "content": tool_results
                })
                
                current_response = self.client.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    messages=conversation,
                    tools=self._get_tools()
                )
    
    def _format_interfaces(self) -> str:
        """Format interface documentation from architect."""
        # Extract relevant interfaces from architect result
        return "See architect plan for module interfaces"

class ParallelBuilderCoordinator:
    """Coordinates multiple Builder subagents running in parallel."""
    
    def __init__(self, client: anthropic.Anthropic):
        self.client = client
    
    def execute_parallel(self, tasks: List['SubagentTask'], 
                        project_dir: Path, 
                        architect_result: Dict) -> List[Dict]:
        """
        Execute multiple Builder subagents in parallel.
        
        Each subagent writes directly to filesystem to avoid "game of telephone."
        """
        
        print(f"\n🚀 Launching {len(tasks)} Builder subagents in parallel...")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
            future_to_task = {
                executor.submit(
                    self._execute_subagent, 
                    task, 
                    project_dir,
                    architect_result
                ): task
                for task in tasks
            }
            
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"   ❌ {task.id} failed: {e}")
                    results.append({
                        'task_id': task.id,
                        'error': str(e),
                        'success': False
                    })
        
        total_files = sum(len(r.get('files_written', [])) for r in results)
        print(f"✅ All {len(tasks)} Builder subagents complete ({total_files} files)")
        
        return results
    
    def _execute_subagent(self, task: 'SubagentTask', 
                         project_dir: Path,
                         architect_result: Dict) -> Dict:
        """Execute a single Builder subagent."""
        subagent = BuilderSubagent(self.client, task, project_dir, architect_result)
        return subagent.execute()
```

#### 3.2 Integrate with Lead Orchestrator

**File:** `ace/orchestrator/lead_orchestrator.py`

```python
from ace.builders.builder_subagent import ParallelBuilderCoordinator

class LeadOrchestrator:
    
    def __init__(self, client):
        self.client = client
        self.builder_coordinator = ParallelBuilderCoordinator(client)
    
    def _execute_parallel_builders(self, tasks: List[SubagentTask], 
                                   architect_result: Dict) -> List[Dict]:
        """Execute Builder subagents in parallel."""
        
        # Launch parallel builders
        results = self.builder_coordinator.execute_parallel(
            tasks=tasks,
            project_dir=self.project_dir,
            architect_result=architect_result
        )
        
        # Check for failures
        failed = [r for r in results if not r.get('success')]
        if failed:
            print(f"\n⚠️  {len(failed)} Builder subagents failed")
            # Trigger self-healing (Phase 5)
        
        return results
```

---

### Phase 4: Self-Healing with LLM-as-Judge (Week 4)

**Objective:** Implement automatic error detection, validation, and fixing.

#### 4.1 Create LLM-as-Judge Validator

**File:** `ace/validators/llm_judge.py`

```python
"""
LLM-as-Judge Validator

Based on Anthropic's approach:
- Evaluate outputs against rubric
- Check: accuracy, completeness, quality, efficiency
- Return scores 0.0-1.0 with pass/fail
"""

import anthropic
from typing import Dict, List

class LLMJudge:
    """
    LLM-as-judge for evaluating agent outputs.
    
    Evaluates against criteria:
    - Functionality (does it work?)
    - Completeness (all requirements met?)
    - Code quality (maintainable?)
    - Test coverage (adequate tests?)
    - Documentation (clear?)
    """
    
    JUDGE_PROMPT = """
You are evaluating code generated by Builder subagents.

PROJECT REQUIREMENTS:
{requirements}

GENERATED CODE:
{code_summary}

EVALUATION CRITERIA:

1. FUNCTIONALITY (0.0-1.0)
   - Does the code compile/run?
   - Are there obvious bugs?
   - Does it match the requirements?

2. COMPLETENESS (0.0-1.0)
   - All required features implemented?
   - All files present?
   - Dependencies properly defined?

3. CODE QUALITY (0.0-1.0)
   - Well-structured and readable?
   - Proper error handling?
   - Follows best practices?

4. TEST COVERAGE (0.0-1.0)
   - Tests exist for main functionality?
   - Tests are meaningful (not trivial)?
   - Edge cases considered?

5. DOCUMENTATION (0.0-1.0)
   - Clear README?
   - API documented?
   - Setup instructions clear?

For each criterion, provide:
- Score (0.0-1.0)
- Reasoning (1-2 sentences)
- Critical issues (if score < 0.7)

Then provide overall PASS/FAIL (pass requires all scores >= 0.7)

Output as JSON:
{{
  "functionality": {{"score": 0.0-1.0, "reasoning": "...", "issues": []}},
  "completeness": {{"score": 0.0-1.0, "reasoning": "...", "issues": []}},
  "code_quality": {{"score": 0.0-1.0, "reasoning": "...", "issues": []}},
  "test_coverage": {{"score": 0.0-1.0, "reasoning": "...", "issues": []}},
  "documentation": {{"score": 0.0-1.0, "reasoning": "...", "issues": []}},
  "overall": {{"pass": true/false, "critical_issues": []}}
}}
"""
    
    def __init__(self, client: anthropic.Anthropic):
        self.client = client
        self.model = "claude-sonnet-4-20250514"
    
    def evaluate(self, requirements: str, code_summary: Dict) -> Dict:
        """
        Evaluate generated code against requirements.
        
        Returns evaluation with scores and pass/fail.
        """
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": self.JUDGE_PROMPT.format(
                    requirements=requirements,
                    code_summary=self._format_code_summary(code_summary)
                )
            }]
        )
        
        evaluation = json.loads(response.content[0].text)
        return evaluation
    
    def _format_code_summary(self, code_summary: Dict) -> str:
        """Format code summary for evaluation."""
        
        files = code_summary.get('files', [])
        
        summary = f"Total files: {len(files)}\n\n"
        summary += "Files:\n"
        for file in files:
            summary += f"- {file['path']} ({file['lines']} lines)\n"
        
        return summary
```

#### 4.2 Create Self-Healing Loop

**File:** `ace/orchestrator/self_healing.py`

```python
"""
Self-Healing Loop

When validation fails:
1. Capture complete error context
2. Feed to Builder subagents
3. Retry validation
4. Repeat until success (max 3 attempts)
"""

from typing import Dict, List, Callable
import time

class SelfHealingLoop:
    """
    Self-healing mechanism that iterates until validation passes.
    
    Based on Anthropic's error handling:
    - Agents are stateful and errors compound
    - Use model intelligence to handle issues gracefully
    - Combine adaptability with deterministic safeguards
    """
    
    def __init__(self, client, builder_coordinator, llm_judge):
        self.client = client
        self.builder_coordinator = builder_coordinator
        self.llm_judge = llm_judge
    
    def retry_until_success(self, 
                          validation_fn: Callable,
                          fix_context: Dict,
                          max_attempts: int = 3) -> bool:
        """
        Run validation, and if it fails, fix and retry.
        
        Args:
            validation_fn: Function that returns (success, error_details)
            fix_context: Context for fixing (requirements, current state, etc.)
            max_attempts: Maximum retry attempts
        
        Returns:
            True if eventually successful, False otherwise
        """
        
        for attempt in range(1, max_attempts + 1):
            print(f"\n🔄 Validation attempt {attempt}/{max_attempts}")
            
            # Run validation
            success, error_details = validation_fn()
            
            if success:
                print(f"✅ Validation PASSED")
                return True
            
            print(f"❌ Validation FAILED: {error_details.get('message')}")
            
            if attempt < max_attempts:
                print(f"   Analyzing failure and generating fix...")
                
                # Get LLM judge evaluation
                evaluation = self.llm_judge.evaluate(
                    requirements=fix_context['requirements'],
                    code_summary=fix_context['code_summary']
                )
                
                # Create fix tasks based on evaluation
                fix_tasks = self._create_fix_tasks(evaluation, error_details)
                
                # Execute fixes in parallel
                self.builder_coordinator.execute_parallel(
                    tasks=fix_tasks,
                    project_dir=fix_context['project_dir'],
                    architect_result=fix_context['architect_result']
                )
                
                # Wait for filesystem to settle
                time.sleep(2)
            else:
                print(f"❌ Max attempts reached. Manual intervention required.")
                return False
        
        return False
    
    def _create_fix_tasks(self, evaluation: Dict, error_details: Dict) -> List:
        """
        Create fix tasks based on evaluation and errors.
        
        Each critical issue becomes a focused fix task.
        """
        
        fix_tasks = []
        
        # Extract critical issues from evaluation
        for criterion, details in evaluation.items():
            if criterion == 'overall':
                continue
            
            if details['score'] < 0.7:
                # Create fix task for this issue
                fix_task = SubagentTask(
                    id=f"fix_{criterion}",
                    type="builder",
                    objective=f"Fix {criterion} issues: {'; '.join(details.get('issues', []))}",
                    output_format="Fixed code files",
                    tools=["write_file", "read_file"],
                    sources=[],
                    boundaries=f"Only fix {criterion} issues, don't rewrite everything",
                    priority=1 if details['score'] < 0.5 else 2
                )
                fix_tasks.append(fix_task)
        
        # Also create task for specific error
        if error_details.get('stderr'):
            error_task = SubagentTask(
                id="fix_error",
                type="builder",
                objective=f"Fix runtime error: {error_details['message']}",
                output_format="Fixed code",
                tools=["write_file", "read_file"],
                sources=[],
                boundaries="Fix only the error, minimal changes",
                priority=0  # Highest priority
            )
            fix_tasks.insert(0, error_task)
        
        return sorted(fix_tasks, key=lambda t: t.priority)
```

---

### Phase 5: Production Reliability (Week 5)

**Objective:** Add checkpointing, error recovery, observability.

#### 5.1 Implement Checkpointing

**File:** `ace/orchestrator/checkpointing.py`

```python
"""
Checkpointing system for long-running agent workflows.

Based on Anthropic's approach:
- Regular checkpoints during execution
- Resume from checkpoint on failure
- Combine with retry logic
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

class CheckpointManager:
    """
    Manages checkpoints for long-running workflows.
    
    Allows resuming from failures without starting over.
    """
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.checkpoint_dir = session_dir / 'checkpoints'
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save_checkpoint(self, phase: str, state: Dict[str, Any]):
        """Save checkpoint after completing a phase."""
        
        checkpoint_file = self.checkpoint_dir / f"{phase}_{datetime.now().isoformat()}.json"
        
        checkpoint_data = {
            'phase': phase,
            'timestamp': datetime.now().isoformat(),
            'state': state
        }
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        print(f"💾 Checkpoint saved: {phase}")
    
    def load_latest_checkpoint(self) -> Dict[str, Any]:
        """Load the most recent checkpoint."""
        
        checkpoints = sorted(self.checkpoint_dir.glob("*.json"))
        
        if not checkpoints:
            return None
        
        latest = checkpoints[-1]
        
        with open(latest) as f:
            checkpoint_data = json.load(f)
        
        print(f"📂 Loaded checkpoint: {checkpoint_data['phase']} from {checkpoint_data['timestamp']}")
        
        return checkpoint_data
    
    def resume_from_checkpoint(self, checkpoint_data: Dict) -> str:
        """Determine which phase to resume from."""
        
        phase = checkpoint_data['phase']
        
        # Map completed phases to next phase
        next_phase = {
            'scout': 'architect',
            'architect': 'builder',
            'builder': 'validation',
            'validation': 'complete'
        }
        
        return next_phase.get(phase, 'scout')
```

#### 5.2 Add Observability

**File:** `ace/orchestrator/observability.py`

```python
"""
Observability for multi-agent workflows.

Track:
- Agent decision patterns
- Token usage per phase
- Success/failure rates
- Performance metrics
"""

import json
from datetime import datetime
from typing import Dict, List
from pathlib import Path

class WorkflowObserver:
    """
    Tracks metrics and patterns across agent workflows.
    
    Based on Anthropic: "Adding full production tracing let us 
    diagnose why agents failed and fix issues systematically."
    """
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.metrics_file = session_dir / 'metrics.jsonl'
        self.events = []
    
    def log_event(self, event_type: str, data: Dict):
        """Log an event with timestamp."""
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'data': data
        }
        
        self.events.append(event)
        
        # Append to JSONL file
        with open(self.metrics_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    def log_phase_start(self, phase: str, details: Dict):
        """Log phase start."""
        self.log_event('phase_start', {
            'phase': phase,
            **details
        })
    
    def log_phase_complete(self, phase: str, metrics: Dict):
        """Log phase completion with metrics."""
        self.log_event('phase_complete', {
            'phase': phase,
            'duration_seconds': metrics.get('duration'),
            'token_usage': metrics.get('tokens'),
            'subagent_count': metrics.get('subagents'),
            'success': metrics.get('success')
        })
    
    def log_validation_result(self, validation_type: str, result: Dict):
        """Log validation attempt."""
        self.log_event('validation', {
            'type': validation_type,
            'passed': result.get('passed'),
            'error': result.get('error'),
            'attempt': result.get('attempt')
        })
    
    def generate_summary(self) -> Dict:
        """Generate summary of workflow metrics."""
        
        summary = {
            'total_events': len(self.events),
            'phases': {},
            'validations': {
                'total': 0,
                'passed': 0,
                'failed': 0
            },
            'token_usage': {
                'scout': 0,
                'architect': 0,
                'builder': 0,
                'total': 0
            }
        }
        
        for event in self.events:
            if event['type'] == 'phase_complete':
                phase = event['data']['phase']
                summary['phases'][phase] = event['data']
                
                tokens = event['data'].get('token_usage', 0)
                summary['token_usage'][phase] = tokens
                summary['token_usage']['total'] += tokens
            
            elif event['type'] == 'validation':
                summary['validations']['total'] += 1
                if event['data']['passed']:
                    summary['validations']['passed'] += 1
                else:
                    summary['validations']['failed'] += 1
        
        return summary
```

---

### Phase 6: Integration & Testing (Week 6)

**Objective:** Integrate all components and test end-to-end.

#### 6.1 Complete Main Orchestrator

**File:** `workflows/autonomous_orchestrator.py`

```python
"""
Complete Multi-Agent Orchestrator

Integrates:
- Lead Orchestrator with extended thinking
- Parallel Scout subagents
- Parallel Builder subagents
- Self-healing loop
- Checkpointing & observability
"""

import anthropic
from pathlib import Path
from ace.orchestrator.lead_orchestrator import LeadOrchestrator
from ace.orchestrator.self_healing import SelfHealingLoop
from ace.orchestrator.checkpointing import CheckpointManager
from ace.orchestrator.observability import WorkflowObserver
from ace.validators.llm_judge import LLMJudge

class MultiAgentOrchestrator:
    """
    Complete multi-agent orchestration system.
    
    Based on Anthropic's production system:
    - Orchestrator-worker pattern
    - Parallel execution
    - Self-healing
    - Checkpointing
    - Observability
    """
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.lead_orchestrator = LeadOrchestrator(self.client)
        self.llm_judge = LLMJudge(self.client)
        
    def build(self, project_name: str, description: str, 
             resume_from: str = None) -> Dict:
        """
        Execute full multi-agent build workflow.
        
        Args:
            project_name: Name of project to build
            description: User's request
            resume_from: Optional checkpoint to resume from
        
        Returns:
            Build result with metrics
        """
        
        # Setup session
        session_dir = Path(f".foundry/sessions/{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        session_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_mgr = CheckpointManager(session_dir)
        observer = WorkflowObserver(session_dir)
        
        # Check for resume
        if resume_from or (checkpoint := checkpoint_mgr.load_latest_checkpoint()):
            return self._resume_build(checkpoint, checkpoint_mgr, observer)
        
        # Phase 1: Planning with Lead Orchestrator
        print("\n" + "="*80)
        print("PHASE 1: WORKFLOW PLANNING")
        print("="*80)
        
        observer.log_phase_start('planning', {'description': description})
        
        workflow_plan = self.lead_orchestrator.plan_workflow(
            user_request=description,
            project_context={'name': project_name}
        )
        
        checkpoint_mgr.save_checkpoint('planning', {
            'workflow_plan': workflow_plan.__dict__
        })
        observer.log_phase_complete('planning', {'success': True})
        
        # Phase 2: Parallel Scout Research
        print("\n" + "="*80)
        print("PHASE 2: PARALLEL RESEARCH")
        print("="*80)
        
        observer.log_phase_start('scout', {
            'subagent_count': len(workflow_plan.scout_tasks)
        })
        
        scout_results = self.lead_orchestrator._execute_parallel_scouts(
            workflow_plan.scout_tasks
        )
        
        checkpoint_mgr.save_checkpoint('scout', {
            'scout_results': scout_results
        })
        observer.log_phase_complete('scout', {
            'success': True,
            'subagents': len(workflow_plan.scout_tasks)
        })
        
        # Phase 3: Architecture Planning
        print("\n" + "="*80)
        print("PHASE 3: ARCHITECTURE PLANNING")
        print("="*80)
        
        observer.log_phase_start('architect', {})
        
        architect_result = self.lead_orchestrator._execute_architect(
            workflow_plan.architect_strategy,
            scout_results
        )
        
        checkpoint_mgr.save_checkpoint('architect', {
            'architect_result': architect_result
        })
        observer.log_phase_complete('architect', {'success': True})
        
        # Phase 4: Parallel Builder Implementation
        print("\n" + "="*80)
        print("PHASE 4: PARALLEL IMPLEMENTATION")
        print("="*80)
        
        observer.log_phase_start('builder', {
            'subagent_count': len(workflow_plan.builder_tasks)
        })
        
        builder_results = self.lead_orchestrator._execute_parallel_builders(
            workflow_plan.builder_tasks,
            architect_result
        )
        
        checkpoint_mgr.save_checkpoint('builder', {
            'builder_results': builder_results
        })
        observer.log_phase_complete('builder', {
            'success': True,
            'subagents': len(workflow_plan.builder_tasks)
        })
        
        # Phase 5: Validation with Self-Healing
        print("\n" + "="*80)
        print("PHASE 5: VALIDATION & SELF-HEALING")
        print("="*80)
        
        healing_loop = SelfHealingLoop(
            self.client,
            self.lead_orchestrator.builder_coordinator,
            self.llm_judge
        )
        
        # Run validation with self-healing
        validation_passed = healing_loop.retry_until_success(
            validation_fn=lambda: self._run_full_validation(),
            fix_context={
                'requirements': description,
                'code_summary': self._summarize_code(builder_results),
                'project_dir': self.project_dir,
                'architect_result': architect_result
            },
            max_attempts=3
        )
        
        observer.log_validation_result('full_validation', {
            'passed': validation_passed
        })
        
        # Generate summary
        metrics = observer.generate_summary()
        
        print("\n" + "="*80)
        if validation_passed:
            print("✅ BUILD COMPLETE - All validations passed")
        else:
            print("❌ BUILD FAILED - Validation failed after retries")
        print("="*80)
        
        print(f"\n📊 Metrics:")
        print(f"   Total token usage: {metrics['token_usage']['total']:,}")
        print(f"   Scout tokens: {metrics['token_usage']['scout']:,}")
        print(f"   Builder tokens: {metrics['token_usage']['builder']:,}")
        print(f"   Validations: {metrics['validations']['passed']}/{metrics['validations']['total']}")
        
        return {
            'success': validation_passed,
            'metrics': metrics,
            'session_dir': str(session_dir)
        }
```

---

## Key Metrics & Expected Improvements

Based on Anthropic's findings:

### Performance Gains
- **90% faster** for complex queries (parallel vs sequential)
- **Token usage explains 80%** of performance variance
- **Multi-agent uses 15× more tokens** than chat, but solves problems chat cannot

### Context Foundry Specific:
- **Current:** Sequential execution, ~30-60 min for medium project
- **Target:** Parallel execution, ~5-10 min for medium project (83% faster)

### Token Usage:
- **Scout Phase:** 3-5 parallel subagents × 8K tokens = ~40K tokens (vs 15K sequential)
- **Builder Phase:** 5-10 parallel subagents × 16K tokens = ~160K tokens (vs 50K sequential)
- **Total:** ~200K tokens (vs 65K), but **6× faster** and **higher quality**

### Success Rate:
- **Current:** ~60% work first time
- **Target:** ~90% work first time (self-healing + validation)

---

## Testing Strategy

### Week 1: Test Lead Orchestrator
```bash
foundry build test-planning "Simple REST API"
# Verify: Planning output shows parallel tasks
```

### Week 2: Test Parallel Scouts
```bash
foundry build test-research "Complex e-commerce system"
# Verify: 5 scouts run in parallel, compress findings
```

### Week 3: Test Parallel Builders
```bash
foundry build test-parallel-build "Microservices app"
# Verify: 8 builders run in parallel, write to filesystem
```

### Week 4: Test Self-Healing
```bash
# Inject intentional error
foundry build test-healing "API with broken dependency"
# Verify: Catches error, fixes automatically, passes on retry
```

### Week 5: Test Production Features
```bash
# Test checkpoint resume
foundry build test-resume "Large app" --resume-from <checkpoint>

# Test observability
foundry analyze test-resume --metrics
```

### Week 6: End-to-End
```bash
# Full 12 Days of Apps campaign
for day in {1..12}; do
  foundry build "day-$day" "<app description>"
done
```

---

## Critical Success Factors

1. **Extended thinking for planning** - Lead Orchestrator must reason well
2. **Clear task boundaries** - No overlap between subagents
3. **Filesystem communication** - Avoid "game of telephone"
4. **Self-healing loop** - Automatic error recovery
5. **Checkpointing** - Resume from failures
6. **Observability** - Debug production issues

---

## Implementation Priority

1. **Week 1-2:** Core multi-agent architecture (Planning + Scouts)
2. **Week 3:** Parallel builders
3. **Week 4:** Self-healing (CRITICAL for "12 Days")
4. **Week 5:** Production reliability
5. **Week 6:** Testing & polish

**Target:** Complete by Dec 1 to prepare for Dec 14-25 campaign.
