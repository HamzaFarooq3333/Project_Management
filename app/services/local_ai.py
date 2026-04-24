import os
import time
import json
from typing import List, Dict, Any

import requests
from fastapi import HTTPException

# Local fallback (optional)
try:
    from transformers import pipeline  # type: ignore
except Exception:
    pipeline = None  # type: ignore


HF_TOKEN_ENV_KEYS = [
    "HUGGINGFACEHUB_API_TOKEN",
    "HF_API_TOKEN",
]


def _get_hf_token() -> str | None:
    for k in HF_TOKEN_ENV_KEYS:
        v = os.getenv(k)
        if v:
            return v
    return None


def _hf_text_generation(prompt: str, model: str = "HuggingFaceH4/zephyr-7b-beta", max_new_tokens: int = 512) -> str:
    token = _get_hf_token()
    if not token:
        raise RuntimeError("Hugging Face token not set")
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": 0.3,
            "return_full_text": False,
        },
    }
    for attempt in range(3):
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return data[0]["generated_text"].strip()
            # Some HF endpoints return a dict
            if isinstance(data, dict) and "generated_text" in data:
                return str(data["generated_text"]).strip()
            return str(data)
        # model may be loading; retry with backoff
        time.sleep(1 + attempt)
    raise HTTPException(status_code=502, detail=f"HF generation failed: {r.status_code} {r.text}")


def _hf_summarize(text: str, model: str = "facebook/bart-large-cnn", max_length: int = 220, min_length: int = 80) -> str:
    token = _get_hf_token()
    if not token:
        raise RuntimeError("Hugging Face token not set")
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    payload = {
        "inputs": text,
        "parameters": {
            "max_length": max_length,
            "min_length": min_length,
            "temperature": 0.0,
        },
    }
    for attempt in range(3):
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            try:
                # common HF response format for summarization
                return data[0]["summary_text"].strip()
            except Exception:
                return str(data)
        time.sleep(1 + attempt)
    raise HTTPException(status_code=502, detail=f"HF summarize failed: {r.status_code} {r.text}")


def generate_process_recommendation(
    project_type: str,
    project_size: str,
    industry: str,
    methodology_preference: str,
    evidence_snippets: List[Dict[str, Any]],
) -> str:
    """Generate a structured process using HF Inference API with provided evidence.

    Returns a markdown-like outline with phases, activities, deliverables, roles, and gates.
    """
    # Build evidence block
    evidence_parts: List[str] = []
    for r in evidence_snippets[:20]:
        std = r.get("standard", "?")
        page = r.get("page", "?")
        text = (r.get("text") or "").replace("\n", " ")
        evidence_parts.append(f"[{std} p.{page}] {text[:400]}")
    evidence_block = "\n".join(evidence_parts)

    instruction = (
        "You are a project management assistant. Using ONLY the evidence, generate an end-to-end process "
        f"tailored for a {project_size} {project_type} project in the {industry} industry, aligned with {methodology_preference}. "
        "Output a concise, structured outline with: Phases, Key Activities, Deliverables, Roles, and Decision Gates (with entry/exit criteria). "
        "End with a short Tailoring Justification. Do not invent sources beyond the evidence."
    )

    prompt = (
        instruction
        + "\n\nEVIDENCE (snippets from standards):\n"
        + evidence_block
        + "\n\nStructured Process:"
    )

    try:
        return _hf_text_generation(prompt, max_new_tokens=700)
    except Exception:
        # Fallback to local pipeline if available
        if pipeline is None:
            raise
        gen = pipeline("text-generation", model="gpt2")  # type: ignore
        out = gen(prompt[:1000], max_new_tokens=300, do_sample=False)  # type: ignore
        return out[0]["generated_text"].strip()


def generate_summary(standard: str, snippets: List[Dict[str, Any]]) -> str:
    """Summarize a standard using HF Inference. Fallback to local pipeline if needed."""
    # Build context up to a safe length
    parts: List[str] = []
    total = 0
    for s in snippets:
        piece = f"[{s.get('standard','?')} p.{s.get('page','?')}] {(s.get('text') or '').strip()}"
        if not s.get('text'):
            continue
        if total + len(piece) > 20000:
            break
        parts.append(piece)
        total += len(piece)
    context = "\n\n".join(parts)

    try:
        return _hf_summarize(context, max_length=250, min_length=120)
    except Exception:
        if pipeline is None:
            raise
        summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")  # type: ignore
        res = summarizer(context[:3000], max_length=200, min_length=100, do_sample=False)  # type: ignore
        return res[0]["summary_text"].strip()


def generate_answer_from_context(question: str, citations: List[Dict[str, Any]]) -> str:
    """Generate an answer strictly from provided citation excerpts.

    Uses HF summarization/generation constrained by the context block.
    """
    # Build safe context from citations
    parts: List[str] = []
    for c in citations[:30]:
        std = str(c.get('standard', '') or '')
        page = str(c.get('page', '') or '')
        excerpt = str(c.get('excerpt', '') or '').replace('\n', ' ')
        if excerpt:
            parts.append(f"[{std} p.{page}] {excerpt}")
    context = "\n".join(parts)[:20000]
    if not context:
        return "No citation content provided."

    prompt = (
        "You are a precise assistant. Answer the question strictly using ONLY the provided context. "
        "If the answer is not present in the context, say 'Insufficient evidence in citations'.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}\n\n"
        "Answer:" 
    )

    try:
        # Prefer generation to allow direct answer
        return _hf_text_generation(prompt, max_new_tokens=300)
    except Exception:
        # Fallback to summarization of context
        try:
            return _hf_summarize(context, max_length=220, min_length=80)
        except Exception:
            return "Insufficient evidence in citations"

"""
AI-Powered Process Generation Service
Uses GPT-2 model with template fallback
"""

from typing import Dict, Any, List
from .ai_generator import generate_process_recommendation_ai, generate_summary_ai

def generate_process_recommendation(
    project_type: str,
    project_size: str,
    industry: str,
    methodology_preference: str,
    evidence_snippets: List[Dict[str, Any]]
) -> str:
    """Generate detailed process recommendations using AI model (with template fallback)."""
    
    # Try AI generation first
    print("🤖 Attempting AI generation with GPT-2...")
    ai_result = generate_process_recommendation_ai(
        project_type=project_type,
        project_size=project_size,
        industry=industry,
        methodology_preference=methodology_preference,
        evidence_snippets=evidence_snippets
    )
    
    if ai_result:
        print("✅ AI generation successful!")
        return ai_result
    
    print("⚠️ AI not available, using template fallback...")
    
    # Fallback to templates
    # Build context from evidence
    evidence_summary = []
    for snippet in evidence_snippets[:8]:
        std = snippet.get('standard', 'Unknown')
        text = snippet.get('text', '')[:250]
        page = snippet.get('page', '?')
        evidence_summary.append(f"**{std}** (p.{page}): {text}")
    
    evidence_text = "\n\n".join(evidence_summary)
    
    # Detailed methodology-specific content
    methodology_details = {
        'PMBOK': {
            'approach': 'PMBOK (Project Management Body of Knowledge) framework with its knowledge areas and process groups',
            'phases': [
                ('Initiating', 'Define project charter, identify stakeholders, establish project foundation', '1-2 weeks'),
                ('Planning', 'Develop comprehensive project management plan, define scope, schedule, budget', '2-4 weeks'),
                ('Executing', 'Direct and manage project work, implement deliverables', f'{project_size_weeks(project_size, 0.6)} weeks'),
                ('Monitoring & Controlling', 'Track, review and regulate progress; manage changes', 'Throughout project'),
                ('Closing', 'Finalize activities, hand over deliverables, document lessons learned', '1-2 weeks')
            ],
            'focus': 'knowledge areas including Integration, Scope, Schedule, Cost, Quality, Resource, Communications, Risk, Procurement, and Stakeholder Management'
        },
        'PRINCE2': {
            'approach': 'PRINCE2 (PRojects IN Controlled Environments) process-based methodology with defined roles and stages',
            'phases': [
                ('Starting Up', 'Appoint project team, capture previous lessons, define approach', '1 week'),
                ('Initiating', 'Establish solid project foundation, create PID (Project Initiation Documentation)', '2-3 weeks'),
                ('Directing', 'Provide strategic direction and decision-making throughout project', 'Throughout'),
                ('Controlling Stages', 'Manage each stage, monitor progress, handle issues/risks', 'Per stage'),
                ('Managing Product Delivery', 'Control link between PM and Team Managers', f'{project_size_weeks(project_size, 0.7)} weeks'),
                ('Managing Stage Boundaries', 'Plan next stage, update business case, report stage end', 'Between stages'),
                ('Closing', 'Confirm acceptance, review performance, capture lessons', '1-2 weeks')
            ],
            'focus': 'seven principles (continued business justification, learn from experience, defined roles), seven themes (business case, organization, quality, plans, risk, change, progress), and seven processes'
        },
        'ISO': {
            'approach': 'ISO 21500/21502 international standards providing principles and guidelines for project management',
            'phases': [
                ('Initiating', 'Define objectives, authorize project, identify stakeholders', '1-2 weeks'),
                ('Planning', 'Establish scope, develop plans for all knowledge areas', '2-3 weeks'),
                ('Implementing', 'Execute plans, coordinate resources, manage stakeholder engagement', f'{project_size_weeks(project_size, 0.6)} weeks'),
                ('Controlling', 'Monitor and control project work, manage changes, track performance', 'Throughout'),
                ('Closing', 'Complete deliverables, obtain acceptance, transfer outputs', '1-2 weeks')
            ],
            'focus': 'integration of subject groups: Integration, Stakeholder, Scope, Resource, Time, Cost, Risk, Quality, Procurement, Communication'
        },
        'any': {
            'approach': 'hybrid approach combining best practices from PMBOK, PRINCE2, and ISO standards',
            'phases': [
                ('Initiation', 'Define project, identify stakeholders, establish governance', '1-2 weeks'),
                ('Planning', 'Develop comprehensive plans across all knowledge areas', '2-4 weeks'),
                ('Execution', 'Implement project activities and deliver outputs', f'{project_size_weeks(project_size, 0.6)} weeks'),
                ('Monitoring', 'Track progress, manage changes, control performance', 'Throughout'),
                ('Closure', 'Finalize deliverables, complete handover, capture lessons', '1-2 weeks')
            ],
            'focus': 'integrated approach covering stakeholder management, scope control, risk mitigation, quality assurance, and resource optimization'
        }
    }
    
    method = methodology_details.get(methodology_preference.lower(), methodology_details['any'])
    
    # Industry-specific risks and considerations
    industry_specifics = get_industry_specifics(industry, project_type)
    
    # Project size considerations
    size_considerations = get_size_considerations(project_size)
    
    # Generate comprehensive recommendation
    recommendation = f"""## 📋 Executive Summary & Methodology Recommendation

**For this {project_size} {project_type} project in the {industry} industry**, we recommend implementing a **{method['approach']}**.

### Rationale for {methodology_preference if methodology_preference != 'any' else 'Hybrid'} Approach

This methodology is particularly suited for your project because:
- **Project Type**: {project_type.capitalize()} projects benefit from {get_type_benefit(project_type, methodology_preference)}
- **Project Size**: {size_considerations['rationale']}
- **Industry Context**: {industry_specifics['rationale']}
- **Standards Alignment**: Draws from {method['focus']}

---

## 📅 Detailed Process Phases

"""
    
    # Add detailed phases
    for i, (phase, description, duration) in enumerate(method['phases'], 1):
        recommendation += f"""### Phase {i}: {phase}
**Duration**: {duration}

**Description**: {description}

**Key Activities**:
{get_phase_activities(phase, project_type, industry)}

**Deliverables**:
{get_phase_deliverables(phase, project_type)}

---

"""
    
    recommendation += f"""## 🎯 Key Activities & Deliverables by Category

### Stakeholder Management
- Identify and analyze stakeholders across all levels
- Develop stakeholder engagement strategy specific to {industry}
- Establish communication protocols and feedback mechanisms
- Conduct regular stakeholder reviews and satisfaction assessments

### Risk Management  
- Identify {industry_specifics['key_risks']}
- Develop risk mitigation strategies with contingency plans
- Implement {industry}-specific risk controls
- Monitor and review risks throughout project lifecycle

### Quality Assurance
- Define quality standards aligned with {industry} regulations
- Implement quality control checkpoints at each phase
- Conduct peer reviews and validation sessions
- Ensure compliance with {industry_specifics['standards']}

### Resource Management
- {size_considerations['resource_guidance']}
- Optimize resource allocation across phases
- Plan for skills development and knowledge transfer
- Manage team capacity and workload balancing

### Communication Management
- Establish communication matrix for all stakeholders
- Set up regular status reporting ({size_considerations['reporting_frequency']})
- Implement collaboration tools appropriate for {project_size} projects
- Create escalation procedures and decision-making framework

---

## 👥 Roles & Responsibilities

### Core Team Structure (for {project_size} projects)
{get_team_structure(project_size, methodology_preference)}

---

## 🔧 Tailoring Guidance for Your Project

### Industry-Specific Tailoring ({industry})
{industry_specifics['tailoring']}

### Project Size Adaptations ({project_size})
{size_considerations['adaptations']}

### Methodology Customization
- Adjust process rigor based on project complexity
- Scale documentation requirements to project needs  
- Customize review and approval workflows
- Adapt meeting cadence to team size and distribution

---

## ⚠️ Risk Considerations & Mitigation

### Primary Risks for {project_type} in {industry}
{industry_specifics['detailed_risks']}

### Mitigation Strategies
1. **Proactive Risk Monitoring**: Implement early warning indicators
2. **Contingency Planning**: Develop alternative approaches for critical activities
3. **Stakeholder Engagement**: Maintain strong communication to identify issues early
4. **Quality Gates**: Establish checkpoints to catch problems before escalation
5. **Change Control**: Implement formal change management process

---

## 📊 Success Metrics & KPIs

### Project Performance Indicators
- **Schedule Performance**: Track against baseline timeline, milestone achievement rate
- **Budget Performance**: Monitor cost variance, earned value metrics
- **Quality Metrics**: Defect rates, rework percentage, acceptance criteria pass rate
- **Stakeholder Satisfaction**: Regular surveys, feedback scores, engagement levels

### {industry.capitalize()}-Specific Metrics
{industry_specifics['metrics']}

### Delivery Success Criteria
- All deliverables meet acceptance criteria
- Project completed within {get_tolerance(project_size)} of schedule/budget
- Stakeholder satisfaction > 85%
- All risks properly closed or transferred
- Comprehensive lessons learned documented

---

## 📚 Standards Alignment & Evidence

This process recommendation is grounded in the following PM standards:

{evidence_text}

### How This Aligns with {methodology_preference if methodology_preference != 'any' else 'Best Practices'}
- Follows {methodology_preference}'s structured approach to project lifecycle
- Incorporates proven practices from international standards
- Adapts core principles to your specific context
- Maintains flexibility for {project_size} project needs

### Integration Points
- **{methodology_preference} Processes**: All key processes are represented
- **Knowledge Areas**: Comprehensive coverage of integration, scope, time, cost, quality, resources, communications, risk, procurement, and stakeholder management
- **Best Practices**: Incorporates lessons learned and industry-proven approaches

---

## 🚀 Implementation Roadmap

### Immediate Next Steps (Week 1)
1. Finalize project charter and obtain sponsor approval
2. Identify and engage key stakeholders  
3. Assemble core project team
4. Conduct project kickoff meeting

### Short-term Actions (Weeks 2-4)
1. Complete detailed project planning
2. Establish governance structure
3. Set up project infrastructure and tools
4. Begin risk and stakeholder analysis

### Ongoing Activities
- Regular status reviews and progress tracking
- Continuous stakeholder engagement
- Proactive risk and issue management
- Quality assurance and control
- Team development and support

---

**This comprehensive process framework provides a solid foundation for successfully delivering your {project_type} project in the {industry} sector while maintaining alignment with {methodology_preference} standards and industry best practices.**
"""
    
    return recommendation


def generate_summary(standard: str, snippets: List[Dict[str, Any]]) -> str:
    """Generate a comprehensive summary using AI model (with template fallback)."""
    
    # Try AI generation first
    print(f"🤖 Attempting AI summary for {standard}...")
    ai_result = generate_summary_ai(standard, snippets)
    
    if ai_result:
        print("✅ AI summary successful!")
        return ai_result
    
    print("⚠️ AI not available, using template fallback...")
    
    # Fallback to templates
    # Combine snippets with page references
    evidence_items = []
    for snippet in snippets[:15]:
        text = snippet.get('text', '')[:300]
        page = snippet.get('page', '?')
        evidence_items.append(f"- **Page {page}**: {text}")
    
    evidence = "\n".join(evidence_items)
    
    # Standard-specific content
    standard_details = {
        'PMBOK': {
            'full_name': 'Project Management Body of Knowledge (PMBOK® Guide) - 7th Edition',
            'overview': 'The PMBOK® Guide is a comprehensive framework that describes the principles, processes, and best practices for project management. It serves as a foundational reference for project managers worldwide.',
            'key_concepts': [
                'Value Delivery System',
                'Project Performance Domains',
                'Tailoring for Project Success',
                'Models, Methods, and Artifacts'
            ],
            'domains': [
                '**Stakeholder Performance Domain**: Effectively engaging stakeholders throughout the project',
                '**Team Performance Domain**: Establishing and developing the project team',
                '**Development Approach and Life Cycle**: Determining approach and project phases',
                '**Planning Performance Domain**: Organizing and coordinating project work',
                '**Project Work Performance Domain**: Executing project activities',
                '**Delivery Performance Domain**: Meeting scope and quality requirements',
                '**Measurement Performance Domain**: Assessing project performance',
                '**Uncertainty Performance Domain**: Managing risk and ambiguity'
            ],
            'principles': [
                'Stewardship: Be a diligent, respectful, and caring steward',
                'Team: Create a collaborative environment',
                'Stakeholders: Effectively engage with stakeholders',
                'Value: Focus on value delivery',
                'Systems Thinking: Recognize and evaluate system interactions',
                'Leadership: Demonstrate leadership behaviors',
                'Tailoring: Tailor based on context',
                'Quality: Build quality into processes and deliverables',
                'Complexity: Navigate complexity',
                'Risk: Optimize risk responses',
                'Adaptability and Resiliency: Embrace adaptability and resiliency',
                'Change: Enable change for planned future state'
            ]
        },
        'PRINCE2': {
            'full_name': 'PRINCE2 (PRojects IN Controlled Environments)',
            'overview': 'PRINCE2 is a process-based project management method that provides a structured approach to project management with clearly defined roles, responsibilities, and procedures.',
            'key_concepts': [
                'Seven Principles',
                'Seven Themes',
                'Seven Processes',
                'Tailoring PRINCE2 to the project environment'
            ],
            'domains': [
                '**Seven Principles**: Continued business justification, Learn from experience, Defined roles and responsibilities, Manage by stages, Manage by exception, Focus on products, Tailor to suit the environment',
                '**Seven Themes**: Business Case, Organization, Quality, Plans, Risk, Change, Progress',
                '**Seven Processes**: Starting up a Project, Initiating a Project, Directing a Project, Controlling a Stage, Managing Product Delivery, Managing a Stage Boundary, Closing a Project'
            ],
            'principles': [
                'Continued Business Justification',
                'Learn from Experience',
                'Defined Roles and Responsibilities',
                'Manage by Stages',
                'Manage by Exception',
                'Focus on Products',
                'Tailor to Suit the Project Environment'
            ]
        },
        'ISO21500': {
            'full_name': 'ISO 21500:2021 - Project, Programme and Portfolio Management - Context and Concepts',
            'overview': 'ISO 21500 provides high-level guidance on project management concepts and processes. It offers a common framework and vocabulary for project management.',
            'key_concepts': [
                'Project Management Principles',
                'Project Governance',
                'Project Environment',
                'Subject Groups and Processes'
            ],
            'domains': [
                '**Integration**: Coordinating project elements',
                '**Stakeholder**: Managing stakeholder relationships',
                '**Scope**: Defining and controlling what is included',
                '**Resource**: Managing project resources',
                '**Time**: Scheduling and time management',
                '**Cost**: Budgeting and cost control',
                '**Risk**: Managing uncertainty',
                '**Quality**: Meeting requirements',
                '**Procurement**: Acquiring resources',
                '**Communication**: Information management'
            ],
            'principles': []
        },
        'ISO21502': {
            'full_name': 'ISO 21502:2020 - Project Management - Guidance',
            'overview': 'ISO 21502 provides comprehensive guidance on project management practices, processes, and procedures that can be applied to any type of organization.',
            'key_concepts': [
                'Project Context',
                'People and Practices',
                'Process Groups',
                'Tailoring Guidelines'
            ],
            'domains': [
                '**Governance and Conformance**: Oversight and alignment',
                '**Strategy and Business Case**: Justification and objectives',
                '**Benefits Realization**: Achieving intended outcomes',
                '**Stakeholder Engagement**: Managing relationships',
                '**Scope and Deliverables**: Defining outputs',
                '**Resource Management**: Team and materials',
                '**Schedule Management**: Timeline control',
                '**Cost Management**: Budget oversight',
                '**Risk and Opportunity**: Managing uncertainty',
                '**Quality Assurance**: Meeting standards',
                '**Procurement and Partnerships**: External resources',
                '**Communication and Knowledge**: Information flow'
            ],
            'principles': []
        }
    }
    
    std_key = standard.upper()
    if 'PMBOK' in std_key:
        details = standard_details['PMBOK']
    elif 'PRINCE' in std_key:
        details = standard_details['PRINCE2']
    elif 'ISO21500' in std_key or 'ISO 21500' in std_key:
        details = standard_details['ISO21500']
    elif 'ISO21502' in std_key or 'ISO 21502' in std_key:
        details = standard_details['ISO21502']
    else:
        details = standard_details.get(std_key, {
            'full_name': standard,
            'overview': f'{standard} provides project management guidance and best practices.',
            'key_concepts': [],
            'domains': [],
            'principles': []
        })
    
    summary = f"""## 📚 {details['full_name']}

### Overview

{details['overview']}

### Key Concepts

{chr(10).join(f"- {concept}" for concept in details['key_concepts'])}

### Core Components

{chr(10).join(details['domains'])}
"""
    
    if details['principles']:
        summary += f"""

### Guiding Principles

{chr(10).join(f"{i}. {principle}" for i, principle in enumerate(details['principles'], 1))}
"""
    
    summary += f"""

### Target Audience & Applicability

This standard is designed for:
- Project managers and team members
- Program and portfolio managers  
- Project sponsors and stakeholders
- Organizations implementing PM practices
- PMO (Project Management Office) personnel

### Unique Aspects

What makes {standard} distinctive:
- Provides a {get_standard_distinction(standard)} approach to project management
- Emphasizes {get_standard_emphasis(standard)}
- Can be tailored to fit various organizational contexts and project types
- Aligns with international best practices and proven methodologies

### Evidence from {standard}

{evidence}

---

**Based on {len(snippets)} source sections from {standard}. This summary provides a comprehensive overview of the standard's key components, principles, and application guidance.**
"""
    
    return summary


# Helper functions

def project_size_weeks(size: str, multiplier: float = 1.0) -> str:
    """Estimate duration based on project size"""
    sizes = {
        'small': int(12 * multiplier),
        'medium': int(24 * multiplier),
        'large': int(40 * multiplier)
    }
    weeks = sizes.get(size.lower(), 16)
    return f"{weeks}"

def get_type_benefit(project_type: str, methodology: str) -> str:
    """Get benefit based on project type and methodology"""
    benefits = {
        'software': {
            'PMBOK': 'structured knowledge areas for managing development lifecycle',
            'PRINCE2': 'stage-based control for iterative development',
            'ISO': 'international standards compliance for global projects',
            'any': 'flexible approach combining agile and traditional practices'
        },
        'construction': {
            'PMBOK': 'comprehensive cost and resource management',
            'PRINCE2': 'strong governance and quality focus',
            'ISO': 'standardized processes for complex physical deliverables',
            'any': 'robust risk management and stakeholder coordination'
        }
    }
    return benefits.get(project_type.lower(), {}).get(methodology, 'comprehensive project management framework')

def get_industry_specifics(industry: str, project_type: str) -> dict:
    """Get industry-specific guidance"""
    specifics = {
        'healthcare': {
            'rationale': 'Healthcare projects require strict regulatory compliance, patient safety focus, and data privacy considerations',
            'key_risks': 'regulatory compliance risks, patient safety concerns, data privacy issues, and integration with existing systems',
            'detailed_risks': """
1. **Regulatory Compliance**: HIPAA, FDA, medical device regulations
   - Mitigation: Early engagement with compliance team, regular audits
2. **Patient Safety**: Clinical workflow impacts, safety protocols
   - Mitigation: Clinical validation, user acceptance testing with clinicians
3. **Data Privacy**: PHI protection, security requirements
   - Mitigation: Privacy impact assessment, encryption, access controls
4. **Integration**: Legacy system compatibility
   - Mitigation: Thorough interface testing, phased rollout""",
            'standards': 'HIPAA, FDA regulations, HL7 standards',
            'tailoring': '- Implement clinical validation processes\n- Ensure HIPAA compliance at all stages\n- Involve medical staff in requirements and testing\n- Plan for 24/7 operational continuity',
            'metrics': '- Clinical adoption rate\n- Patient safety incident reduction\n- Regulatory compliance score\n- System uptime and reliability'
        },
        'it': {
            'rationale': 'IT projects benefit from agile-waterfall hybrid approaches with strong change management',
            'key_risks': 'technical debt, security vulnerabilities, scalability issues, and user adoption challenges',
            'detailed_risks': """
1. **Technical Risks**: Architecture scalability, technology obsolescence
   - Mitigation: Technical reviews, proof of concepts, architecture governance
2. **Security**: Cyber threats, data breaches, compliance
   - Mitigation: Security testing, penetration testing, compliance audits
3. **Integration**: API compatibility, data migration
   - Mitigation: Integration testing, staged migration approach
4. **User Adoption**: Change resistance, training needs
   - Mitigation: Change management plan, comprehensive training""",
            'standards': 'ISO 27001, ITIL, software development standards',
            'tailoring': '- Implement DevOps practices\n- Use agile ceremonies for development phases\n- Establish architecture review board\n- Plan for continuous integration/deployment',
            'metrics': '- System performance (response time, throughput)\n- Security compliance score\n- User adoption and satisfaction\n- Defect density and resolution time'
        },
        'financial': {
            'rationale': 'Financial industry demands high security, audit trails, and regulatory compliance throughout project lifecycle',
            'key_risks': 'financial loss, regulatory penalties, security breaches, and reputational damage',
            'detailed_risks': """
1. **Financial Risk**: Budget overruns, ROI shortfall
   - Mitigation: Rigorous financial controls, regular budget reviews
2. **Regulatory Risk**: SOX, Basel III, financial regulations
   - Mitigation: Compliance officer involvement, regulatory checkpoints
3. **Security Risk**: Fraud, data breaches, financial crime
   - Mitigation: Security audits, fraud detection, access controls
4. **Operational Risk**: System failures, business continuity
   - Mitigation: Disaster recovery planning, redundancy, testing""",
            'standards': 'SOX, PCI-DSS, Basel III compliance',
            'tailoring': '- Implement strict financial controls and audit trails\n- Ensure SOX compliance documentation\n- Involve compliance and audit teams early\n- Plan for regulatory approval gates',
            'metrics': '- Regulatory compliance percentage\n- Security audit findings\n- Transaction accuracy rate\n- System availability (99.9%+ target)'
        }
    }
    return specifics.get(industry.lower(), {
        'rationale': f'{industry.capitalize()} projects require industry-specific considerations and compliance',
        'key_risks': 'project-specific risks based on industry context',
        'detailed_risks': 'Standard project risks including scope creep, resource constraints, and stakeholder alignment',
        'standards': 'industry-specific standards and regulations',
        'tailoring': f'- Adapt processes to {industry} requirements\n- Ensure compliance with industry standards\n- Engage domain experts throughout project',
        'metrics': '- Industry-specific performance indicators\n- Compliance metrics\n- Quality and customer satisfaction'
    })

def get_size_considerations(size: str) -> dict:
    """Get project size-specific guidance"""
    considerations = {
        'small': {
            'rationale': 'Small projects need streamlined processes with appropriate governance without excessive overhead',
            'resource_guidance': 'Small, cross-functional team (3-7 members) with multi-skilled resources',
            'reporting_frequency': 'weekly status updates, bi-weekly stakeholder reviews',
            'adaptations': '- Simplified documentation (essential artifacts only)\n- Informal communication with regular touchpoints\n- Combined roles where appropriate\n- Accelerated decision-making process\n- Light-touch governance with key checkpoints'
        },
        'medium': {
            'rationale': 'Medium projects balance structure and agility with formal processes scaled appropriately',
            'resource_guidance': 'Dedicated team (8-20 members) with specialized roles and part-time SMEs',
            'reporting_frequency': 'bi-weekly status reports, monthly steering committee',
            'adaptations': '- Standard documentation suite with tailoring\n- Formal and informal communication channels\n- Defined roles with some overlap\n- Structured decision-making with clear authority levels\n- Regular governance reviews with stakeholder involvement'
        },
        'large': {
            'rationale': 'Large projects require comprehensive governance, formal processes, and robust controls',
            'resource_guidance': 'Large distributed team (20+ members) with specialized roles, sub-teams, and full-time SMEs',
            'reporting_frequency': 'weekly detailed reports, bi-weekly steering, monthly portfolio review',
            'adaptations': '- Full documentation suite with version control\n- Formal communication plan with multiple channels\n- Clearly defined roles and responsibilities matrix\n- Hierarchical decision-making with escalation paths\n- Strong governance with multiple oversight layers'
        }
    }
    return considerations.get(size.lower(), considerations['medium'])

def get_phase_activities(phase: str, project_type: str, industry: str) -> str:
    """Get phase-specific activities"""
    phase_lower = phase.lower()
    
    activities = {
        'initiating': f"""- Define project objectives and success criteria
- Identify key stakeholders and establish initial engagement
- Develop preliminary scope and high-level requirements
- Assess {industry}-specific constraints and compliance needs
- Create project charter and obtain authorization
- Conduct initial risk assessment""",
        
        'starting up': """- Appoint executive and project manager
- Capture previous lessons relevant to project
- Design and appoint project management team
- Prepare outline business case
- Select project approach and assemble Project Brief
- Plan initiation stage""",
        
        'planning': f"""- Decompose scope into work breakdown structure
- Develop detailed {project_type} project schedule
- Estimate costs and create budget baseline
- Plan resource requirements and procurement
- Identify and analyze all project risks
- Define quality standards and acceptance criteria
- Establish communication and stakeholder management plans
- Create change control procedures""",
        
        'initiating (prince2)': """- Refine business case and risks
- Set up project controls and reporting
- Create project initiation documentation (PID)
- Assemble project plan and stage plans
- Document quality management approach
- Obtain project authorization""",
        
        'executing': f"""- Coordinate resources and team members
- Implement {project_type} deliverables per plan
- Conduct quality assurance activities
- Manage stakeholder expectations and communications
- Execute procurement activities
- Implement approved changes
- Track and report progress""",
        
        'implementing': f"""- Execute planned {project_type} activities
- Coordinate team performance and deliverables
- Implement quality control measures
- Manage stakeholder communications
- Address issues and implement solutions
- Execute risk responses""",
        
        'monitoring': """- Track project performance against baselines
- Measure key performance indicators
- Conduct variance analysis (schedule, cost, scope)
- Review and update risk register
- Manage change requests
- Report status to stakeholders
- Implement corrective actions""",
        
        'controlling': """- Monitor work performance and progress
- Perform integrated change control
- Validate scope and deliverables
- Control communications
- Monitor risks and issues
- Track quality metrics""",
        
        'closing': """- Verify all deliverables are complete and accepted
- Obtain formal acceptance from stakeholders
- Complete financial closure and contract closeouts
- Conduct post-project review
- Document lessons learned
- Archive project documentation
- Release project resources
- Celebrate project success""",
        
        'closure': """- Finalize all project activities
- Hand over deliverables to operations
- Conduct project evaluation
- Capture and share lessons learned
- Complete administrative closure
- Recognize team contributions"""
    }
    
    return activities.get(phase_lower, activities.get(phase_lower.split()[0], 
        """- Execute phase-specific project activities
- Coordinate with team and stakeholders
- Monitor progress and quality
- Document outcomes and decisions"""))

def get_phase_deliverables(phase: str, project_type: str) -> str:
    """Get phase-specific deliverables"""
    phase_lower = phase.lower()
    
    deliverables = {
        'initiating': f"""- Project Charter (authorized)
- Stakeholder Register (initial)
- High-level Requirements Document
- Preliminary {project_type} Scope Statement
- Initial Risk Register""",
        
        'starting up': """- Project Brief
- Daily Log
- Lessons Log (started)
- Project approach definition
- Executive and Project Manager appointments""",
        
        'planning': f"""- Project Management Plan (comprehensive)
- Work Breakdown Structure (WBS)
- Detailed {project_type} Project Schedule
- Cost Baseline and Budget
- Risk Management Plan and Risk Register
- Quality Management Plan
- Communications Management Plan
- Procurement Management Plan
- Stakeholder Engagement Plan""",
        
        'executing': f"""- {project_type.capitalize()} Project Deliverables
- Quality Reports and Audit Results
- Team Performance Assessments
- Change Requests (processed)
- Issue Log (managed)
- Procurement Documents
- Status Reports""",
        
        'implementing': f"""- Project outputs and deliverables
- Work performance data
- Change requests
- Quality metrics and reports
- Updated project documents""",
        
        'monitoring': """- Performance Reports
- Variance Analysis Reports
- Updated Risk Register
- Change Log
- Earned Value Reports
- Forecasts and Projections
- Corrective Action Records""",
        
        'controlling': """- Work performance reports
- Change control decisions
- Updated project plans
- Validated deliverables
- Risk updates""",
        
        'closing': """- Final Project Report
- Lessons Learned Document
- Project Archives (complete)
- Formal Acceptance Documentation
- Contract Closure Documents
- Final {project_type} Product/Service (transitioned)
- Team Performance Evaluations
- Project Completion Certificate""",
        
        'closure': """- Final deliverables (accepted)
- End project report
- Lessons learned repository
- Project archive
- Resource release documentation"""
    }
    
    return deliverables.get(phase_lower, deliverables.get(phase_lower.split()[0],
        f"""- Phase-specific {project_type} deliverables
- Updated project documents
- Progress reports
- Quality records"""))

def get_team_structure(size: str, methodology: str) -> str:
    """Get team structure based on size and methodology"""
    structures = {
        'small': f"""
**Project Manager**: Overall project leadership and coordination
**Business Analyst**: Requirements and stakeholder liaison
**Technical Lead**: {methodology}-aligned technical guidance
**Developers/Contributors** (2-4): Core delivery team
**QA/Quality Lead**: Quality assurance and testing
**Part-time Sponsor**: Executive oversight and decision authority""",
        
        'medium': f"""
**Project Manager**: Overall project leadership
**Deputy PM/PMO Support**: Planning and coordination
**Business Analyst(s)**: Requirements and process design
**Technical Lead/Architect**: Technical direction and standards
**Development Team** (5-12): Specialized delivery teams
**QA Manager**: Quality assurance oversight
**QA Team** (2-3): Testing and validation
**Subject Matter Experts**: Domain expertise (part-time)
**Project Sponsor**: Executive leadership
**Steering Committee**: Strategic direction""",
        
        'large': f"""
**Project Director**: Strategic oversight and program alignment
**Project Manager(s)**: Day-to-day project leadership (may have multiple)
**PMO Team** (2-4): Planning, reporting, governance
**Business Analysis Team** (3-5): Requirements and process
**Technical Architecture Team** (2-4): Technical strategy and design
**Development Teams** (15+): Multiple specialized sub-teams
**QA Manager + Team** (5+): Comprehensive testing organization
**Integration Manager**: Cross-team coordination
**Change Manager**: Stakeholder adoption
**Subject Matter Experts**: Multiple domain specialists
**Executive Sponsor**: C-level oversight
**Steering Committee**: Multi-level governance
**Portfolio Board**: Strategic alignment"""
    }
    return structures.get(size.lower(), structures['medium'])

def get_tolerance(size: str) -> str:
    """Get tolerance levels based on project size"""
    tolerances = {
        'small': '±10%',
        'medium': '±5-10%',
        'large': '±5%'
    }
    return tolerances.get(size.lower(), '±10%')

def get_standard_distinction(standard: str) -> str:
    """Get what makes a standard distinctive"""
    distinctions = {
        'PMBOK': 'principles-based and performance domain-focused',
        'PRINCE2': 'process-based with clearly defined stages and roles',
        'ISO21500': 'high-level international framework',
        'ISO21502': 'detailed process-oriented international'
    }
    std_key = standard.upper()
    for key in distinctions:
        if key in std_key:
            return distinctions[key]
    return 'comprehensive and structured'

def get_standard_emphasis(standard: str) -> str:
    """Get what a standard emphasizes"""
    emphasis = {
        'PMBOK': 'principles, performance domains, and value delivery',
        'PRINCE2': 'business justification, defined roles, and stage-based control',
        'ISO21500': 'context, governance, and subject group integration',
        'ISO21502': 'practical guidance, process groups, and tailoring'
    }
    std_key = standard.upper()
    for key in emphasis:
        if key in std_key:
            return emphasis[key]
    return 'best practices and proven methodologies'
