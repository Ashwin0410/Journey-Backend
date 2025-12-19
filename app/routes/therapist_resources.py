"""
Therapist Resources Routes

Provides educational resources for therapists:
- Behavioral Activation (BA) resources
- Clinical training materials
- Treatment manuals
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from pathlib import Path

from app import schemas
from app.auth_utils import get_current_therapist
from app import models


# Router with prefix for all therapist resources endpoints
r = APIRouter(prefix="/api/therapist/resources", tags=["therapist-resources"])


# Path to resources folder
RESOURCES_DIR = Path(__file__).parent.parent / "assets" / "resources"


# =============================================================================
# STATIC RESOURCE DATA
# =============================================================================

# Behavioral Activation Resources - Actual files from clinical team
BA_RESOURCES = [
    {
        "id": "ba-transd-bespoke",
        "title": "Behavioral Activation Transdiagnostic Training",
        "description": "Comprehensive BA training presentation covering core principles, implementation strategies, and clinical applications for transdiagnostic use.",
        "read_time": "45 min presentation",
        "category": "Training",
        "section": "ba",
        "file_name": "BA_TransD_Bespoke_091625_Final_NoVideo.pptx",
        "file_type": "pptx",
        "has_file": True,
        "content": """
## Behavioral Activation Transdiagnostic Training

This presentation provides comprehensive training on Behavioral Activation (BA) therapy, covering:

### Core Concepts
- Understanding the activity-mood connection
- The role of avoidance in maintaining depression
- Outside-in vs inside-out approaches

### Clinical Implementation
- Activity monitoring techniques
- Values-based activity selection
- Working with barriers and resistance

### Transdiagnostic Applications
- Adapting BA for anxiety comorbidity
- BA in substance use contexts
- Modifications for different populations

**Download the full presentation for detailed slides and clinical examples.**
""",
    },
    {
        "id": "batd-tips",
        "title": "BATD-R Therapist Tips",
        "description": "Practical wisdom and clinical nuance for implementing the Brief Behavioral Activation Treatment for Depression (BATD-R). Based on expert training and real-world clinical experience.",
        "read_time": "20 min read",
        "category": "Clinical Guide",
        "section": "ba",
        "file_name": "BATD_Tips.pdf",
        "file_type": "pdf",
        "has_file": True,
        "content": """
## BATD-R Therapist Tips: Practical Wisdom & Clinical Nuance

This guide supplements the BATD-R manual with practical guidance from expert clinicians.

### Key Themes Covered

**1. Flexibility in Providing Treatment Rationale**
- Personalizing the rationale using client's own language
- Tailoring to unique presentations (withdrawn vs. active-but-unsatisfied)

**2. Therapeutic Alliance & Self-Disclosure**
- Strategic self-disclosure to build rapport
- Sharing experiences with monitoring challenges

**3. Building Motivation for Monitoring**
- Framing monitoring as "telling your story" not "homework"
- Troubleshooting incomplete forms

**4. Working with Values**
- Separating personal vs. societal values
- Managing emotional content in values discussions
- Allowing time to adjust to values concepts

**5. Angles and Steps**
- Breaking activities into manageable components
- Angles: Multiple paths to the same value
- Steps: Hierarchy of sub-activities

**6. Contracts as "Assists"**
- Moving away from formal contract language
- Culturally sensitive approaches to support

**7. Drawing from Other Approaches**
- Using functional analysis to understand barriers
- Maintaining protocol fidelity while enhancing delivery

**Download the full PDF for detailed clinical examples and scripts.**
""",
    },
    {
        "id": "batd-manual",
        "title": "Brief Behavioral Activation Treatment Manual",
        "description": "The complete BATD clinical manual published in Behavior Modification. Provides session-by-session guidance for implementing brief BA treatment.",
        "read_time": "60 min read",
        "category": "Treatment Manual",
        "section": "ba",
        "file_name": "Current_Brief_Behavioral_Activation_Manual_Published_in_BehMod.doc",
        "file_type": "doc",
        "has_file": True,
        "content": """
## Brief Behavioral Activation Treatment for Depression (BATD)

### Treatment Manual Overview

This is the complete clinical manual for Brief Behavioral Activation Treatment for Depression, providing:

### Session Structure
- **Session 1**: Introduction, rationale, and activity monitoring
- **Session 2**: Values assessment across life areas
- **Session 3-4**: Activity selection and scheduling
- **Sessions 5-8**: Implementation, troubleshooting, and maintenance
- **Final Sessions**: Relapse prevention and termination

### Core Components
1. Daily activity monitoring
2. Values clarification
3. Activity scheduling based on values
4. Behavioral contracts
5. Progress monitoring

### Life Areas Assessed
- Relationships (family, social, intimate)
- Education/Career
- Recreation/Hobbies
- Mind/Body/Spirituality
- Daily responsibilities

### Forms Included
- Daily Monitoring Form
- Life Areas, Values, and Activities Inventory
- Activity Selection and Ranking Form
- Behavioral Contracts

**Download the full manual for complete session guides and reproducible forms.**
""",
    },
]

# Motivational Interviewing Resources
MI_RESOURCES = [
    {
        "id": "mi-spirit",
        "title": "The Spirit of MI",
        "description": "Understanding the core spirit of Motivational Interviewing: partnership, acceptance, compassion, and evocation.",
        "read_time": "6 min read",
        "category": "Foundational",
        "section": "mi",
        "file_name": None,
        "file_type": None,
        "has_file": False,
        "content": """
## The Spirit of Motivational Interviewing

### Partnership
MI is done "with" and "for" the client, not "to" them. The therapist is a collaborative partner, not an expert prescribing solutions. The client is the expert on their own life.

### Acceptance
Four components of acceptance:
1. **Absolute worth**: Unconditional positive regard
2. **Accurate empathy**: Deep understanding of perspective
3. **Autonomy support**: Honoring client's right to choose
4. **Affirmation**: Recognizing strengths and efforts

### Compassion
Acting in the client's best interest, not serving our own agenda. Prioritizing the client's welfare and needs.

### Evocation
Drawing out the client's own motivations, values, and wisdom rather than installing them. The answers are within the client; our job is to evoke them.

### The Righting Reflex
Therapists naturally want to fix problems. But when we push for change, clients often push back. MI channels this energy by having clients voice their own arguments for change.
""",
    },
    {
        "id": "mi-oars",
        "title": "OARS Techniques",
        "description": "The four core communication skills in MI: Open questions, Affirmations, Reflections, and Summaries.",
        "read_time": "7 min read",
        "category": "Clinical",
        "section": "mi",
        "file_name": None,
        "file_type": None,
        "has_file": False,
        "content": """
## OARS: Core MI Skills

### Open Questions
Questions that invite elaboration rather than yes/no answers.
- "What brings you here today?"
- "How would you like things to be different?"
- "What concerns you about your current situation?"

Avoid: "Don't you think you should...?" (closed, leading)

### Affirmations
Genuine statements recognizing client strengths, efforts, and values.
- "You showed real courage in coming here today"
- "Despite the challenges, you've kept trying"
- "Your family clearly matters a lot to you"

Avoid: Praise ("Good job!") vs. Affirmation (recognizing character)

### Reflections
The primary tool in MI. Types include:
- **Simple**: Repeating/rephrasing content
- **Complex**: Adding meaning, feeling, or emphasis
- **Double-sided**: Capturing ambivalence ("Part of you wants X, and part of you worries about Y")

Aim for 2:1 reflection-to-question ratio.

### Summaries
Collecting what the client has shared:
- **Collecting summaries**: Gathering related points
- **Linking summaries**: Connecting themes
- **Transitional summaries**: Moving to a new topic

End summaries with: "What else?" or "What did I miss?"
""",
    },
    {
        "id": "mi-change-talk",
        "title": "Eliciting Change Talk",
        "description": "Strategies for evoking and reinforcing client language that favors change.",
        "read_time": "6 min read",
        "category": "Clinical",
        "section": "mi",
        "file_name": None,
        "file_type": None,
        "has_file": False,
        "content": """
## Eliciting Change Talk

### What is Change Talk?
Client language that favors change. The more clients voice their own reasons for change, the more likely change becomes.

### Types of Change Talk (DARN-CAT)
**Preparatory:**
- **D**esire: "I want to..."
- **A**bility: "I could..."
- **R**easons: "I would feel better if..."
- **N**eed: "I have to..."

**Mobilizing:**
- **C**ommitment: "I will..."
- **A**ctivation: "I'm ready to..."
- **T**aking steps: "I already started..."

### Evoking Change Talk
1. **Evocative questions**: "What would be better if you made this change?"
2. **Importance ruler**: "On a scale of 0-10, how important is this?"
3. **Looking back**: "What was it like before this problem?"
4. **Looking forward**: "How would you like things to be in a year?"
5. **Exploring values**: "What matters most to you?"
6. **Query extremes**: "What's the worst that could happen if nothing changes?"

### Responding to Change Talk
- Reflect it back (amplify)
- Ask for elaboration
- Affirm the statement
- Summarize change talk together
""",
    },
    {
        "id": "mi-ambivalence",
        "title": "Working with Ambivalence",
        "description": "Understanding and navigating the natural ambivalence clients feel about change.",
        "read_time": "5 min read",
        "category": "Clinical",
        "section": "mi",
        "file_name": None,
        "file_type": None,
        "has_file": False,
        "content": """
## Working with Ambivalence

### Understanding Ambivalence
Ambivalence is normal and expected. Clients simultaneously want to change and want to stay the same. This isn't resistance—it's a natural part of the change process.

### The Ambivalence See-Saw
Imagine a see-saw with:
- Reasons for change on one side
- Reasons to stay the same on the other

When we argue for change, clients often argue the other side. MI avoids this trap.

### Exploring Both Sides
Use double-sided reflections:
- "On one hand, you enjoy the relief it brings. On the other hand, you're worried about the long-term effects."
- "Part of you wants to make changes, and part of you isn't sure it's worth the effort."

### Developing Discrepancy
Gently help clients see the gap between their current behavior and their deeper values:
- "You mentioned being a good parent is important to you. How does this fit with that?"
- "Where do you see yourself in five years if things continue as they are?"

### Avoiding the Trap
When clients express sustain talk (reasons not to change):
- Don't argue against it
- Reflect it, then ask about the other side
- Trust the client's own ambivalence to resolve
""",
    },
]

# ReWire Usage Resources
REWIRE_RESOURCES = [
    {
        "id": "rewire-integrating-data",
        "title": "Integrating App Data in Sessions",
        "description": "How to use patient activity data, mood trends, and journal entries to inform therapy sessions.",
        "read_time": "5 min read",
        "category": "Platform",
        "section": "rewire",
        "file_name": None,
        "file_type": None,
        "has_file": False,
        "content": """
## Integrating ReWire Data in Sessions

### Before the Session
Review your patient's dashboard to note:
- Activity heatmap patterns
- AI-generated weekly summary
- Recent journal entries
- Areas flagged for attention

### Opening the Session
Use app data as a collaborative starting point:
- "I noticed your activity picked up mid-week. What was different?"
- "The app showed you completed your first social activity. How was that?"
- "I saw some journaling about [theme]. Would you like to talk about that?"

### During the Session
The patient detail view provides:
- **Weekly summary**: Quick overview of engagement
- **What's working**: Patterns to reinforce
- **Focus areas**: Topics to explore
- **Journal insight**: Direct quotes for reflection

### Tracking Progress Over Time
- Compare week-to-week activity trends
- Note which activity types are consistent/avoided
- Celebrate streaks and milestones
- Discuss patterns openly

### Session Notes
Use the session notes feature to:
- Document observations and plans
- Auto-save notes for continuity
- Track homework assignments
- Note items for next session

### Caution
- Data supplements but doesn't replace clinical conversation
- Avoid surveillance framing—keep it collaborative
- Some patients may feel monitored; discuss openly
""",
    },
    {
        "id": "rewire-guiding-ai",
        "title": "Guiding the AI Companion",
        "description": "How to use the AI guidance feature to shape the AI companion's interactions with your patient.",
        "read_time": "4 min read",
        "category": "Platform",
        "section": "rewire",
        "file_name": None,
        "file_type": None,
        "has_file": False,
        "content": """
## Guiding the AI Companion

### What is AI Guidance?
The AI Companion provides personalized audio journeys and reflections for patients between sessions. Your guidance helps shape how the AI interacts with each specific patient.

### Writing Effective Guidance
Good guidance is:
- **Specific**: Reference particular patterns or needs
- **Therapeutic**: Based on your clinical understanding
- **Actionable**: Things the AI can actually do

### Example Guidance

**For avoidance patterns:**
"When Sarah expresses hesitation about social activities, gently explore what she's afraid might happen. Use reflective listening. Don't push—instead, help her notice the cost of avoidance on her own."

**For schema work:**
"James has a strong defectiveness schema. When he expresses self-criticism, acknowledge the feeling while gently offering alternative perspectives. Highlight his concrete accomplishments."

**For motivation:**
"Maria responds well to connecting activities to her value of being a good mother. When suggesting activities, frame them in terms of modeling healthy behavior for her children."

### What Guidance Doesn't Do
- Override clinical judgment
- Replace therapy sessions
- Make diagnostic decisions
- Access patient data you haven't shared

### Updating Guidance
Review and update guidance:
- After significant sessions
- When patterns shift
- When treatment focus changes
- At least monthly
""",
    },
]

# Combine all resources
ALL_RESOURCES = BA_RESOURCES + MI_RESOURCES + REWIRE_RESOURCES


# =============================================================================
# EXTENDED SCHEMA FOR FILE INFO
# =============================================================================


class ResourceItemExtendedOut(schemas.BaseModel):
    """Resource item with file information."""
    id: str
    title: str
    description: str
    read_time: str
    category: str
    section: str
    has_file: bool = False
    file_type: Optional[str] = None
    download_url: Optional[str] = None


class ResourceSectionExtendedOut(schemas.BaseModel):
    """Resource section with extended items."""
    section_id: str
    section_title: str
    items: List[ResourceItemExtendedOut]


class ResourceListExtendedOut(schemas.BaseModel):
    """Full resource library with file info."""
    sections: List[ResourceSectionExtendedOut]


class ResourceFullOut(schemas.BaseModel):
    """Full resource with content."""
    id: str
    title: str
    description: str
    read_time: str
    category: str
    section: str
    content: str
    has_file: bool = False
    file_type: Optional[str] = None
    download_url: Optional[str] = None


class ResourceSearchOut(schemas.BaseModel):
    """Search results."""
    query: str
    results: List[ResourceItemExtendedOut]
    total: int


# =============================================================================
# HELPER FUNCTION
# =============================================================================


def _build_resource_item(resource: dict) -> ResourceItemExtendedOut:
    """Build a resource item with download URL if applicable."""
    download_url = None
    if resource.get("has_file") and resource.get("file_name"):
        download_url = f"/api/therapist/resources/download/{resource['id']}"
    
    return ResourceItemExtendedOut(
        id=resource["id"],
        title=resource["title"],
        description=resource["description"],
        read_time=resource["read_time"],
        category=resource["category"],
        section=resource["section"],
        has_file=resource.get("has_file", False),
        file_type=resource.get("file_type"),
        download_url=download_url,
    )


def _find_resource_by_id(resource_id: str) -> Optional[dict]:
    """Find a resource by its ID."""
    for resource in ALL_RESOURCES:
        if resource["id"] == resource_id:
            return resource
    return None


# =============================================================================
# GET ALL RESOURCES
# =============================================================================


@r.get("", response_model=ResourceListExtendedOut)
def get_all_resources(
    current_therapist: models.Therapists = Depends(get_current_therapist),
):
    """
    Get all resources organized by section.
    
    Sections:
    - ba: Behavioral Activation
    - mi: Motivational Interviewing
    - rewire: Using ReWire platform
    """
    try:
        ba_items = [_build_resource_item(res) for res in BA_RESOURCES]
        mi_items = [_build_resource_item(res) for res in MI_RESOURCES]
        rewire_items = [_build_resource_item(res) for res in REWIRE_RESOURCES]
        
        return ResourceListExtendedOut(
            sections=[
                ResourceSectionExtendedOut(
                    section_id="ba",
                    section_title="Behavioral Activation",
                    items=ba_items,
                ),
                ResourceSectionExtendedOut(
                    section_id="mi",
                    section_title="Motivational Interviewing",
                    items=mi_items,
                ),
                ResourceSectionExtendedOut(
                    section_id="rewire",
                    section_title="Using ReWire",
                    items=rewire_items,
                ),
            ]
        )
    except Exception as e:
        print(f"Error getting all resources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading resources: {str(e)}",
        )


# =============================================================================
# GET RESOURCES BY SECTION
# =============================================================================


@r.get("/section/{section_id}", response_model=ResourceSectionExtendedOut)
def get_resources_by_section(
    section_id: str,
    current_therapist: models.Therapists = Depends(get_current_therapist),
):
    """
    Get resources for a specific section.
    
    Section IDs:
    - ba: Behavioral Activation
    - mi: Motivational Interviewing
    - rewire: Using ReWire platform
    """
    section_map = {
        "ba": ("Behavioral Activation", BA_RESOURCES),
        "mi": ("Motivational Interviewing", MI_RESOURCES),
        "rewire": ("Using ReWire", REWIRE_RESOURCES),
    }
    
    if section_id not in section_map:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section not found. Valid sections: {', '.join(section_map.keys())}",
        )
    
    try:
        title, resources = section_map[section_id]
        items = [_build_resource_item(res) for res in resources]
        
        return ResourceSectionExtendedOut(
            section_id=section_id,
            section_title=title,
            items=items,
        )
    except Exception as e:
        print(f"Error getting section {section_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading section: {str(e)}",
        )


# =============================================================================
# GET SINGLE RESOURCE WITH FULL CONTENT
# =============================================================================


@r.get("/item/{resource_id}", response_model=ResourceFullOut)
def get_resource(
    resource_id: str,
    current_therapist: models.Therapists = Depends(get_current_therapist),
):
    """
    Get a single resource with full content.
    """
    try:
        # Find resource
        resource = _find_resource_by_id(resource_id)
        
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resource not found: {resource_id}",
            )
        
        download_url = None
        if resource.get("has_file") and resource.get("file_name"):
            download_url = f"/api/therapist/resources/download/{resource['id']}"
        
        return ResourceFullOut(
            id=resource["id"],
            title=resource["title"],
            description=resource["description"],
            read_time=resource["read_time"],
            category=resource["category"],
            section=resource["section"],
            content=resource.get("content", "").strip(),
            has_file=resource.get("has_file", False),
            file_type=resource.get("file_type"),
            download_url=download_url,
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting resource {resource_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading resource: {str(e)}",
        )


# =============================================================================
# DOWNLOAD RESOURCE FILE
# =============================================================================


@r.get("/download/{resource_id}")
def download_resource(
    resource_id: str,
    current_therapist: models.Therapists = Depends(get_current_therapist),
):
    """
    Download the file associated with a resource.
    
    Only available for resources that have attached files.
    """
    # Find resource
    resource = _find_resource_by_id(resource_id)
    
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
    
    if not resource.get("has_file") or not resource.get("file_name"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This resource does not have a downloadable file",
        )
    
    # Check if file exists
    file_path = RESOURCES_DIR / resource["file_name"]
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on server. Please contact support.",
        )
    
    # Determine media type
    media_types = {
        "pdf": "application/pdf",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    
    media_type = media_types.get(resource["file_type"], "application/octet-stream")
    
    return FileResponse(
        path=file_path,
        filename=resource["file_name"],
        media_type=media_type,
    )


# =============================================================================
# SEARCH RESOURCES
# =============================================================================


@r.get("/search", response_model=ResourceSearchOut)
def search_resources(
    q: str = Query(..., min_length=2, description="Search query"),
    current_therapist: models.Therapists = Depends(get_current_therapist),
):
    """
    Search resources by title, description, or content.
    """
    try:
        query = q.lower().strip()
        
        results = []
        for resource in ALL_RESOURCES:
            # Search in title, description, and content
            if (query in resource["title"].lower() or
                query in resource["description"].lower() or
                query in resource.get("content", "").lower()):
                results.append(_build_resource_item(resource))
        
        return ResourceSearchOut(
            query=q,
            results=results,
            total=len(results),
        )
    except Exception as e:
        print(f"Error searching resources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching resources: {str(e)}",
        )
