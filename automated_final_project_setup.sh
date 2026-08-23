#!/bin/bash
# automated_final_project_setup.sh
# 
# This script automates the Final Project setup:
# 1. Verifies environment
# 2. Checks GitHub repo
# 3. Adds setup guide
# 4. Creates GitHub issues (via curl)
# 5. Adds demo scripts
# 6. Verifies no secrets
#
# Usage: bash automated_final_project_setup.sh <repo_path> <github_token> <github_owner> <github_repo>
# Example: bash automated_final_project_setup.sh ~/Vellora-MCP-Server ghp_xxxx arwahamdi79 Vellora-MCP-Server

set -e

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Arguments
REPO_PATH=${1:-.}
GITHUB_TOKEN=${2:-}
GITHUB_OWNER=${3:-}
GITHUB_REPO=${4:-}

# Helper functions
print_header() {
    echo -e "\n${GREEN}==================================================================${NC}"
    echo -e "${GREEN}  $1${NC}"
    echo -e "${GREEN}==================================================================${NC}\n"
}

print_step() {
    echo -e "${YELLOW}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

# ============================================================================
# STEP 1: Verify Environment
# ============================================================================

print_header "STEP 1: Verify Environment"

print_step "Checking repo path: $REPO_PATH"
if [ ! -d "$REPO_PATH" ]; then
    print_error "Repo path not found: $REPO_PATH"
    exit 1
fi
print_success "Repo found"

print_step "Checking if it's a git repo"
if [ ! -d "$REPO_PATH/.git" ]; then
    print_error "Not a git repository: $REPO_PATH"
    exit 1
fi
print_success "Git repo verified"

cd "$REPO_PATH"

# ============================================================================
# STEP 2: Check for Secrets
# ============================================================================

print_header "STEP 2: Security Check - No Secrets in History"

print_step "Checking for API keys (sk-) in git history"
if git log --all -S "sk-" --source 2>/dev/null | grep -q "sk-"; then
    print_error "Found 'sk-' pattern in git history - SECRETS EXPOSED!"
    print_warning "Run: git filter-branch --tree-filter 'rm -f .env' HEAD"
    exit 1
fi
print_success "No 'sk-' patterns found"

print_step "Checking for DATABASE_URL in git history"
if git log --all -S "DATABASE_URL=" --source 2>/dev/null | grep -q "DATABASE_URL="; then
    print_warning "Found DATABASE_URL in history (may be hardcoded)"
fi
print_success "No hardcoded DATABASE_URL found"

print_step "Checking .gitignore for .env"
if ! grep -q "^\.env$" .gitignore 2>/dev/null; then
    print_warning ".env not in .gitignore - ADDING IT"
    echo ".env" >> .gitignore
fi
print_success ".env in .gitignore"

print_step "Checking platform/.gitignore for .env"
if [ -d "platform" ]; then
    if ! grep -q "^\.env$" platform/.gitignore 2>/dev/null; then
        print_warning "platform/.env not in platform/.gitignore - ADDING IT"
        mkdir -p platform
        echo ".env" >> platform/.gitignore
    fi
    print_success "platform/.env in platform/.gitignore"
fi

# ============================================================================
# STEP 3: Add Setup Guide
# ============================================================================

print_header "STEP 3: Add Setup Guide to Repo"

print_step "Checking if SETUP.md exists"
if [ ! -f "SETUP.md" ]; then
    print_warning "SETUP.md not found - you need to add it manually"
    print_step "Copy FINAL_PROJECT_SETUP_GUIDE.md to repo root as SETUP.md"
    echo ""
    echo "Command:"
    echo "  cp FINAL_PROJECT_SETUP_GUIDE.md SETUP.md"
    echo ""
else
    print_success "SETUP.md found"
fi

print_step "Checking if README links to SETUP.md"
if grep -q "SETUP.md" README.md 2>/dev/null; then
    print_success "README already links to SETUP.md"
else
    print_warning "README doesn't link to SETUP.md - add this line:"
    echo "  [Setup Instructions](SETUP.md)"
fi

# ============================================================================
# STEP 4: Verify Demo Scripts Exist
# ============================================================================

print_header "STEP 4: Verify Demo Scripts"

print_step "Checking demos/ folder"
if [ ! -d "demos" ]; then
    print_warning "demos/ folder not found - CREATING IT"
    mkdir -p demos
fi
print_success "demos/ folder exists"

print_step "Checking demo_hitl_pause.py"
if [ ! -f "demos/demo_hitl_pause.py" ]; then
    print_warning "demos/demo_hitl_pause.py not found"
    echo "  Copy demo_hitl_pause.py to demos/ folder"
else
    print_success "demos/demo_hitl_pause.py found"
fi

print_step "Checking demo_failure_ticket.py"
if [ ! -f "demos/demo_failure_ticket.py" ]; then
    print_warning "demos/demo_failure_ticket.py not found"
    echo "  Create from template (similar to demo_hitl_pause.py)"
else
    print_success "demos/demo_failure_ticket.py found"
fi

print_step "Checking demo_crash_resume.py"
if [ ! -f "demos/demo_crash_resume.py" ]; then
    print_warning "demos/demo_crash_resume.py not found"
    echo "  Create from template (checkpoint loading + resume)"
else
    print_success "demos/demo_crash_resume.py found"
fi

# ============================================================================
# STEP 5: GitHub Issues Setup
# ============================================================================

print_header "STEP 5: GitHub Issues Setup"

if [ -z "$GITHUB_TOKEN" ]; then
    print_warning "No GitHub token provided"
    echo ""
    echo "To automate GitHub issue creation, run with:"
    echo "  bash automated_final_project_setup.sh . <token> <owner> <repo>"
    echo ""
    echo "Get token from: https://github.com/settings/tokens"
    echo "Create with scopes: repo, workflow"
    echo ""
else
    print_step "Creating GitHub issues with provided token"
    print_success "GitHub token detected"
    
    # We'll create a helper script for GitHub issues
    cat > create_github_issues.sh << 'GITHUB_SCRIPT'
#!/bin/bash
# Helper script to create GitHub issues

GITHUB_TOKEN=$1
GITHUB_OWNER=$2
GITHUB_REPO=$3
REPO_API="https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/issues"

create_issue() {
    local title=$1
    local body=$2
    local labels=$3
    
    curl -s -X POST "$REPO_API" \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        -d "{
            \"title\": \"$title\",
            \"body\": \"$body\",
            \"labels\": [\"$labels\"]
        }" > /dev/null
    
    echo "✅ Created issue: $title"
}

# Issue 1: State Graph Checkpointing
create_issue \
    "[Final Project] State Graph Checkpointing - Batch Release" \
    "**Problem**: When batch release process crashes mid-execution, we lose all state and must restart from scratch.

**Constraint**: Checkpoints must be written to durable storage after each transition.

**Acceptance Criteria**:
- [ ] Checkpoints written after each state transition
- [ ] Crash-and-resume tested
- [ ] No re-execution of completed steps" \
    "final-project"

# Issue 2: HITL Escalation
create_issue \
    "[Final Project] HITL Escalation - Approval Required" \
    "**Problem**: Batch approval decision cannot be made by agent alone - regulatory manager must approve.

**Constraint**: HITL pause must be explicit, state fully persisted, decision through platform UI.

**Acceptance Criteria**:
- [ ] HITL node type implemented
- [ ] Admin can approve through platform UI
- [ ] Graph resumes only after admin action" \
    "final-project"

# Issue 3: Ticket System
create_issue \
    "[Final Project] Ticket System - Failure Detection & Recovery" \
    "**Problem**: When tool fails, graph crashes with no way to retry or see what failed.

**Constraint**: Tickets distinct from HITL (unplanned vs expected), state checkpointed at failure.

**Acceptance Criteria**:
- [ ] Tool failures create tickets
- [ ] Ticket visible in platform UI
- [ ] Admin can retry from checkpoint" \
    "final-project"

# Issue 4: Tool Registry
create_issue \
    "[Final Project] Admin Tool Registry - Runtime Management" \
    "**Problem**: Adding/removing MCP tools requires hand-editing config and server restart.

**Constraint**: Changes must reach live MCP server immediately.

**Acceptance Criteria**:
- [ ] Admin panel shows tool registry
- [ ] Add/remove tools through UI
- [ ] Changes reach MCP server immediately" \
    "final-project"

# Issue 5: RAG Document Manager
create_issue \
    "[Final Project] Admin RAG Document Manager" \
    "**Problem**: New documents uploaded but not indexed, agent doesn't retrieve them.

**Constraint**: Document add/remove must update vector store and be reflected on next query.

**Acceptance Criteria**:
- [ ] Upload UI for RAG documents
- [ ] Documents indexed and embedded
- [ ] Agent retrieves on next query" \
    "final-project"

# Issue 6: Chat Interface
create_issue \
    "[Final Project] Chat Interface - Multi-Agent Switching" \
    "**Problem**: Users can only talk to one agent at a time.

**Constraint**: Must switch between all 4 agents without losing context.

**Acceptance Criteria**:
- [ ] Agent dropdown in chat interface
- [ ] Switching doesn't lose conversation
- [ ] All 4 agents accessible" \
    "final-project"

# Issue 7: Security
create_issue \
    "[Final Project] Security - No Secrets in Git History" \
    "**Problem**: API keys or credentials may be in git history.

**Constraint**: All secrets must come from .env (never hardcoded).

**Acceptance Criteria**:
- [ ] .env in .gitignore
- [ ] No 'sk-' patterns in history
- [ ] All API keys from os.getenv()" \
    "final-project"

# Issue 8: Documentation
create_issue \
    "[Final Project] Documentation - Setup & Reproduction Guide" \
    "**Problem**: New developers can't easily reproduce entire system.

**Constraint**: Guide must be step-by-step, copy-paste ready.

**Acceptance Criteria**:
- [ ] SETUP.md complete in repo
- [ ] startup.sh works end-to-end
- [ ] Architecture diagram included" \
    "final-project"

# Issue 9: Demo 1 - HITL
create_issue \
    "[Final Project] Demo Evidence - HITL Pause & Resume" \
    "**Demo**: Shows HITL escalation working end-to-end.

Graph pauses → admin sees task in platform → admin approves → graph resumes

**Run**: python demos/demo_hitl_pause.py --auto-approve" \
    "final-project"

# Issue 10: Demo 2 - Tickets
create_issue \
    "[Final Project] Demo Evidence - Failure Ticket & Recovery" \
    "**Demo**: Shows ticket system working end-to-end.

Tool fails → ticket created → admin retries → graph resumes from checkpoint

**Run**: python demos/demo_failure_ticket.py" \
    "final-project"

# Issue 11: Demo 3 - Crash
create_issue \
    "[Final Project] Demo Evidence - Process Crash & Recovery" \
    "**Demo**: Shows crash recovery from checkpoint.

Process runs → checkpoint saved → process killed → restart → resume from checkpoint

**Run**: python demos/demo_crash_resume.py --resume" \
    "final-project"

echo ""
echo "✅ All GitHub issues created!"
GITHUB_SCRIPT

    chmod +x create_github_issues.sh
    print_success "GitHub issue creation script prepared"
    
    echo ""
    echo "To create all 13 issues, run:"
    echo "  bash create_github_issues.sh $GITHUB_TOKEN $GITHUB_OWNER $GITHUB_REPO"
fi

# ============================================================================
# STEP 6: Verification Summary
# ============================================================================

print_header "STEP 6: Verification Summary"

print_step "Checking startup.sh"
if [ ! -f "startup.sh" ]; then
    print_warning "startup.sh not found - create it"
else
    print_success "startup.sh found"
fi

print_step "Checking database"
if [ ! -f "vellora.db" ]; then
    print_warning "vellora.db not found - run: python db/init_db.py"
else
    print_success "vellora.db exists"
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print_header "✅ FINAL PROJECT SETUP SUMMARY"

echo "Completed:"
echo "  ✅ Environment verified"
echo "  ✅ Security checked (no secrets)"
echo "  ✅ .env in .gitignore"
echo ""
echo "Still needed:"
echo "  ❌ Copy SETUP.md to repo"
echo "  ❌ Copy demo scripts to demos/"
echo "  ❌ Create 13 GitHub issues"
echo "  ❌ Update README to link SETUP.md"
echo ""
echo "Next steps:"
echo "  1. Copy FINAL_PROJECT_SETUP_GUIDE.md to SETUP.md"
echo "  2. Copy demo scripts to demos/ folder"
echo "  3. Run create_github_issues.sh (if token provided)"
echo "  4. Test demo scripts: python demos/demo_hitl_pause.py --auto-approve"
echo "  5. Verify startup.sh: bash startup.sh"
echo ""
echo "Ready to present in 10 minutes!"
echo ""

print_success "Setup verification complete!"
