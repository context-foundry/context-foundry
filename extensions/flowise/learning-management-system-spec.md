# Learning Management System - Project Specification

## Project Overview
Build a comprehensive onboarding and learning management system consisting of two integrated applications:
1. **Content Library App** - Central repository for all learning content
2. **Transaction App** - Learning path creation, assignment, and execution

## Content Library App

### Purpose
Central repository for managing thousands of training activities with hierarchical organization and personalization capabilities.

### Data Model
- **Hierarchical Structure**: Programs → Modules → Topics → Tasks
- **Granular Content Organization**: Multi-level taxonomy for easy navigation and assignment

### Core Features

#### 1. Content Repository
- Store and organize all learning materials
- Support multiple content types (videos, documents, assessments, interactive activities)
- Version control for content updates
- Rich metadata (tags, difficulty levels, duration, prerequisites)

#### 2. Integrated Checklists
- Observation checklists for mentors and trainers
- Competency verification workflows
- Sign-off mechanisms for skill validation
- Configurable checklist templates per content type

#### 3. Tag-Based Personalization
- Multi-dimensional tagging system (role, department, skill level, compliance requirements)
- Recommendation engine based on learner profiles
- Smart content discovery and search
- Automated content suggestions

#### 4. Administrative Configuration
- "Final view" dashboard for admins to review all configurations
- Bulk content management and updates
- Content approval workflows
- Publishing controls (draft/published/archived states)

#### 5. Completion History Tracking
- Worker task completion database
- Prevent reassignment of completed tasks
- Historical learning records
- Competency achievement tracking
- Certification management

### Agents for Content Library App

1. **Agent.ContentCurator**
   - Manages content repository (CRUD operations)
   - Organizes hierarchical structure
   - Handles content versioning and metadata

2. **Agent.CompetencyValidator**
   - Processes checklist completions
   - Validates mentor/trainer observations
   - Tracks competency achievements
   - Issues certifications

3. **Agent.PersonalizationEngine**
   - Analyzes learner profiles and tags
   - Generates personalized recommendations
   - Powers content discovery
   - Manages recommendation algorithms

4. **Agent.AdminConfigurator**
   - Provides administrative oversight
   - Manages content approval workflows
   - Handles bulk operations
   - Generates configuration reports

---

## Transaction App

### Purpose
Learning path builder where customized learning journeys are created, assigned, tracked, and measured against goals.

### Core Features

#### 1. Learning Path Builder
- "A la carte" content selection from Content Library
- Drag-and-drop path creation
- Template-based pathways for common roles
- Prerequisite management
- Sequencing and dependencies

#### 2. Learner Profile-Based Customization
- Role-based automatic path generation
- Skill gap analysis and targeted assignments
- Career progression pathways
- Onboarding templates by position/department

#### 3. Learning Hours Management
- Allocated hours per learner/period
- Time tracking for activities
- Progress measurement against goals
- Capacity planning and scheduling
- Reporting on learning investment

#### 4. Multi-Role Dashboards

**Manager Dashboard**:
- Team learning progress overview
- Individual learner status
- At-risk learner identification
- Completion forecasts
- Approval workflows for time allocation

**Mentor Dashboard**:
- Assigned mentees tracking
- Observation checklist completion
- One-on-one session scheduling
- Mentee competency progress
- Feedback and coaching notes

**Trainer Dashboard**:
- Scheduled training sessions
- Participant tracking
- Skill validation checklists
- Session effectiveness metrics
- Learner engagement analytics

**Learner Dashboard**:
- Personalized learning path view
- Progress tracking
- Upcoming activities
- Achievements and certifications
- Time remaining vs. allocated

### Agents for Transaction App

5. **Agent.PathwayArchitect**
   - Builds and customizes learning paths
   - Analyzes learner profiles for recommendations
   - Manages prerequisites and dependencies
   - Creates role-based templates

6. **Agent.LearningScheduler**
   - Allocates learning hours
   - Schedules training activities
   - Manages capacity and conflicts
   - Sends reminders and notifications

7. **Agent.ProgressTracker**
   - Tracks completion status
   - Measures progress against goals
   - Identifies at-risk learners
   - Generates progress reports

8. **Agent.ManagerSupport**
   - Powers manager dashboard
   - Provides team analytics
   - Handles approval workflows
   - Generates management reports

9. **Agent.MentorCoordinator**
   - Powers mentor dashboard
   - Schedules mentoring sessions
   - Tracks observation checklists
   - Manages mentor-mentee relationships

10. **Agent.TrainerSupport**
    - Powers trainer dashboard
    - Manages training sessions
    - Tracks skill validations
    - Provides trainer analytics

---

## Integration Points

### Content Library ↔ Transaction App
- Transaction App pulls content from Content Library
- Completion data flows back to Content Library for history
- Tag-based recommendations inform path building
- Competency validations update learner profiles

### Data Flow
1. Admin configures content in Content Library
2. PathwayArchitect builds paths using Content Library items
3. LearningScheduler assigns paths to learners
4. Learners complete activities (tracked by ProgressTracker)
5. Mentors/Trainers validate competencies (CompetencyValidator)
6. Completion history prevents reassignment (ContentCurator)
7. Data informs future recommendations (PersonalizationEngine)

---

## Technical Requirements

### Flowise Workflow Structure
- **10 specialized agents** (4 for Content Library + 6 for Transaction App)
- **Conditional routing** based on request type (content management vs. learning path operations)
- **Start node** → **Router node** → **Agent nodes**
- **Self-contained agents** with inline configurations
- **No phantom tool references** (follow Pattern #5 prevention)

### External Integrations Required
- **HRIS/Workday** - Employee profiles, org structure, job roles
- **LMS/LXP APIs** - Content hosting, SCORM/xAPI tracking
- **Calendar APIs** (Google/Outlook) - Session scheduling
- **Notification services** (Email/Slack) - Reminders and alerts
- **Database** - Content metadata, completion history, learning paths

### Compliance & Security
- **Data Privacy**: GDPR, FERPA compliance for learner data
- **Access Control**: Role-based permissions (admin, manager, mentor, trainer, learner)
- **Audit Trail**: All content changes and completions logged
- **Authentication**: SSO integration (OAuth 2.0)

---

## Success Criteria

### Functional
- ✅ All 10 agents operational with clear responsibilities
- ✅ Hierarchical content model (programs → modules → topics → tasks)
- ✅ Competency checklists integrated with validation workflows
- ✅ Tag-based personalization engine functional
- ✅ Learning path builder with "a la carte" selection
- ✅ Learning hours tracking and goal measurement
- ✅ Multi-role dashboards (Manager, Mentor, Trainer, Learner)
- ✅ Completion history prevents task reassignment

### Technical
- ✅ Single Flowise workflow JSON file
- ✅ 10 scenarios = 10 agents (no disconnected nodes)
- ✅ Zero phantom tool references
- ✅ All pattern #1-5 prevention measures applied
- ✅ Comprehensive integration documentation

### Documentation
- ✅ README with architecture overview
- ✅ Integration guide for HRIS/LMS APIs
- ✅ Tool configuration recommendations
- ✅ Knowledge base setup guide
- ✅ User guides per role (admin, manager, mentor, trainer, learner)

---

## Build Configuration

**Project Name**: learning-management-system
**Workflow Complexity**: High (10 agents, hierarchical data model, multi-role dashboards)
**Estimated Build Time**: 25-35 minutes
**Test-Driven**: Yes (enable self-healing test loop)
**Pattern Prevention**: Apply all 5 documented Flowise patterns
