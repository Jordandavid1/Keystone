"""
KEYSTONE 16 Canonical Domain Playbooks (Python Implementation)
Preserves and extends all 16 first-class domain playbooks with preloaded
domain context, multi-scenario use-case templates, bound studio skills,
critical slots, and 6-step execution paths per Bible §2 Invariant 14 & §6.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class CriticalSlot:
    id: str
    why: str
    assumption: str

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "why": self.why, "assumption": self.assumption}


@dataclass(frozen=True)
class PathStep:
    title: str
    objective: str
    doneWhen: str

    def to_dict(self) -> Dict[str, str]:
        return {"title": self.title, "objective": self.objective, "doneWhen": self.doneWhen}


@dataclass(frozen=True)
class Playbook:
    id: str
    label: str
    keywords: List[str]
    outcome: str
    criticalSlots: List[CriticalSlot]
    path: List[PathStep]
    domain_context: Dict[str, Any] = field(default_factory=dict)
    use_cases: List[Dict[str, Any]] = field(default_factory=list)
    skills: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "keywords": list(self.keywords),
            "outcome": self.outcome,
            "criticalSlots": [s.to_dict() for s in self.criticalSlots],
            "path": [p.to_dict() for p in self.path],
            "domain_context": dict(self.domain_context),
            "use_cases": [dict(u) for u in self.use_cases],
            "skills": [dict(sk) for sk in self.skills],
        }


CANONICAL_PLAYBOOKS: List[Playbook] = [
    # 1. SOFTWARE
    Playbook(
        id="software",
        label="Software & Technical Architecture",
        keywords=["app", "api", "software", "code", "system", "website", "database", "saas", "feature", "bug", "deploy", "backend", "frontend"],
        outcome="a deployed, tested software solution",
        criticalSlots=[
            CriticalSlot(id="stack", why="Determines architecture, idioms, and tooling.", assumption="Modern TypeScript/Node or Python stack with managed cloud services."),
            CriticalSlot(id="scale", why="Dictates infrastructure complexity and cost.", assumption="MVP / initial production scale (up to 1,000 concurrent users)."),
            CriticalSlot(id="security", why="Shapes auth, data handling, and compliance.", assumption="Standard OWASP controls and least-privilege authentication."),
        ],
        path=[
            PathStep(title="Clarify system scope & SLA boundaries", objective="Define functional contracts, latency/throughput targets, and non-goals for the software system.", doneWhen="Written system specification with explicit API boundaries and SLA targets."),
            PathStep(title="Architect data model & service topology", objective="Design relational/document schemas, state transitions, and service interfaces before implementation.", doneWhen="Complete schema definitions, OpenAPI/gRPC contracts, and topology diagram."),
            PathStep(title="Build vertical walking skeleton", objective="Implement end-to-end authentication, database persistence, and core API route with live wiring.", doneWhen="One critical request path executes end-to-end with zero mocks."),
            PathStep(title="Harden security, error recovery & edge cases", objective="Enforce input validation, Aikido injection defense, rate limiting, and structured error telemetry.", doneWhen="All failure modes return deterministic status codes and pass security checks."),
            PathStep(title="Verify against integration & load acceptance suites", objective="Run automated unit, integration, and contract tests against live database and worker boundaries.", doneWhen="100% green test suite with zero unhandled exceptions."),
            PathStep(title="Package, deploy & instrument observability", objective="Ship release artifact with health checks, structured logging, and rollback runbook.", doneWhen="Deployed production service with verified live `/health` telemetry."),
        ],
        domain_context={
            "domain_brief": "Full-stack systems engineering, distributed API architecture, database modeling, and high-reliability UI/UX technical diagrams.",
            "system_framing": "Principal Staff Systems Architect & Full-Stack Engineer enforcing zero-mock production wiring, strict schema contracts, and OWASP/Aikido security boundaries.",
            "default_subject": "High-throughput distributed cloud architecture and dark-mode developer studio interface",
            "default_environment": "Ultra-clean dark engineering command console with real-time telemetry HUD and node topology",
            "default_visual_style": "Precision technical schematic, glassmorphic dark UI, crisp vector lines, 8K studio render",
            "default_constraints": ["Zero mock or placeholder endpoints", "Deterministic error handling", "Strict tenant isolation"],
            "quality_standard": "Production-grade deployable code and crystal-clear architectural schematics",
        },
        use_cases=[
            {
                "id": "sw_saas_arch",
                "title": "Distributed SaaS & Microservice Architecture",
                "summary": "Design and visualize a multi-tenant cloud backend with API gateway, queue workers, and SQL/vector persistence.",
                "subject": "Multi-tenant SaaS system topology with API gateway, GPU worker bridge, and relational ledger",
                "environment": "Dark-mode engineering blueprint canvas with glowing cyan/indigo data conduits",
                "visual_style": "High-contrast architectural system diagram, isometric technical visualization, crisp typography",
                "starter_prompt": "Architect a multi-tenant AI SaaS platform with FastAPI control plane, signed HMAC execution envelopes, and ephemeral GPU worker nodes.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "sw_ui_dashboard",
                "title": "Developer IDE & Telemetry Dashboard UI",
                "summary": "Generate high-density developer console interfaces, observability HUDs, and node graph editors.",
                "subject": "Pro developer IDE and real-time GPU cluster telemetry dashboard with node graph viewport",
                "environment": "Sleek OLED dark studio workspace inspired by VS Code, Cursor, and DaVinci Resolve",
                "visual_style": "Precision UI/UX product render, glassmorphic panels, JetBrains Mono telemetry badges",
                "starter_prompt": "High-density dark mode developer observability dashboard showing live GPU VRAM telemetry, DAG execution nodes, and latency histograms.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "sw_api_audit",
                "title": "API Contract & Security Hardening Review",
                "summary": "Deep cognitive analysis of API routes, authentication flows, and database transaction boundaries.",
                "subject": "REST/WebSocket API contract and zero-trust authentication state machine",
                "environment": "Production cloud security boundary with JWT/HMAC verification",
                "visual_style": "Structured technical specification and threat-model matrix",
                "starter_prompt": "Analyze our API authentication and job state machine for race conditions, replay vulnerabilities, and idempotency gaps.",
                "recommended_intent": "analyze",
                "recommended_adapter": "comfyui",
            },
        ],
        skills=[
            {"id": "skill_sw_arch", "name": "System Topology & Schema Synthesis", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Synthesizes normalized DB schemas, OpenAPI specs, and distributed state machines."},
            {"id": "skill_sw_ui_render", "name": "Technical UI & Blueprint Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Renders high-resolution UI mockups, dark-mode dashboards, and system schematics via ComfyUI."},
            {"id": "skill_sw_aikido", "name": "Aikido Security & Boundary Auditor", "capability": "security.aikido", "adapter": "aikido_shield", "description": "Audits code and prompts for injection vectors, privilege escalation, and OWASP flaws."},
            {"id": "skill_sw_web_docs", "name": "Live SDK & Documentation Research", "capability": "intelligence.scrape", "adapter": "firecrawl", "description": "Extracts live API docs and library specifications from the web."},
        ],
    ),

    # 2. WRITING
    Playbook(
        id="writing",
        label="Writing, Editing & Narrative",
        keywords=["write", "book", "essay", "article", "blog", "story", "script", "novel", "copy", "draft", "edit", "screenplay"],
        outcome="a polished, publication-ready manuscript or piece",
        criticalSlots=[
            CriticalSlot(id="audience", why="Sets vocabulary, depth, and emotional register.", assumption="Informed general readers looking for clarity and insight."),
            CriticalSlot(id="tone", why="Establishes voice and stylistic consistency.", assumption="Authoritative, engaging, and concise."),
            CriticalSlot(id="format", why="Determines structural pacing and length.", assumption="Structured long-form piece (1,500-2,500 words) with clear subheadings."),
        ],
        path=[
            PathStep(title="Lock thesis, dramatic premise & voice register", objective="Establish the central narrative hook, emotional stakes, and stylistic voice.", doneWhen="One-paragraph premise, character/voice bible, and target reader profile."),
            PathStep(title="Architect structural beat sheet & scene outline", objective="Map every act, section, or scene transition with tension arcs and reveals.", doneWhen="Complete scene-by-scene or section-by-section structural outline."),
            PathStep(title="Draft high-velocity first pass", objective="Write the complete narrative or manuscript with vivid sensory detail and momentum.", doneWhen="Full first draft covering opening hook through resolution."),
            PathStep(title="Synthesize visual storyboards & voice table-read", objective="Generate keyframe concept art and ElevenLabs character voiceover reads to test pacing.", doneWhen="Visual storyboard frames and spoken dialogue audio tracks paired with script."),
            PathStep(title="Ruthless developmental & line edit", objective="Cut exposition bloat, sharpen subtext, and elevate rhythm and word choice.", doneWhen="Line-edited manuscript with zero clichés or pacing dead zones."),
            PathStep(title="Final proofread & publication formatting", objective="Verify continuity, typography, and deliverable formatting for print, screen, or web.", doneWhen="Publication-ready master manuscript."),
        ],
        domain_context={
            "domain_brief": "Feature screenwriting, literary fiction, investigative essays, worldbuilding bibles, and dramatic dialogue synthesis.",
            "system_framing": "Award-winning Showrunner, Literary Editor & Narrative Architect crafting visceral, subtext-rich prose and cinema-ready screenplays.",
            "default_subject": "Dramatic protagonist in a richly textured narrative moment with cinematic staging",
            "default_environment": "Atmospheric moody interior with chiaroscuro practical lighting and narrative depth",
            "default_visual_style": "35mm Kodak Vision3 500T film still, Roger Deakins framing, shallow depth of field, evocative storytelling",
            "default_constraints": ["Show don't tell", "Eliminate generic exposition", "Maintain strict voice continuity"],
            "quality_standard": "Publication- and production-ready literary or screenplay masterwork",
        },
        use_cases=[
            {
                "id": "wr_screenplay",
                "title": "Feature Film & Series Screenplay Scene",
                "summary": "Write industry-formatted screenplay scenes paired with keyframe visual storyboards and spoken dialogue.",
                "subject": "Two rivals confronting each other across a rain-streaked glass table at midnight",
                "environment": "High-rise penthouse overlooking a fog-shrouded metropolis at night",
                "visual_style": "Anamorphic 2.39:1 cinema frame, Kodak 2383 print LUT, Fincher/Villeneuve tension",
                "starter_prompt": "Write a tense neo-noir confrontation scene between an investigative journalist and a rogue AI architect, and visualize the master keyframe.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "wr_worldbuilding",
                "title": "Worldbuilding Lore & Visual Bible",
                "summary": "Develop deep lore, faction histories, and concept plates for novels, RPGs, or cinema.",
                "subject": "Ancient monolithic citadel carved into obsidian sea cliffs with bioluminescent script",
                "environment": "Storm-lashed twilight coast under twin moons",
                "visual_style": "Epic painterly concept art, matte painting detail, volumetric atmosphere",
                "starter_prompt": "Create a worldbuilding lore entry and visual keyframe for a subterranean library city powered by acoustic resonance.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "wr_editorial_essay",
                "title": "Long-Form Investigative Essay & Editorial",
                "summary": "Draft incisive cultural, philosophical, or technical essays with editorial illustration.",
                "subject": "Editorial conceptual illustration representing human agency in the age of autonomous cognition",
                "environment": "Minimalist gallery composition with dramatic spotlighting",
                "visual_style": "New Yorker / Wired magazine feature illustration, bold graphic composition",
                "starter_prompt": "Draft a 2,000-word essay on sovereign creative intelligence and design the lead editorial cover illustration.",
                "recommended_intent": "analyze",
                "recommended_adapter": "image_gen",
            },
        ],
        skills=[
            {"id": "skill_wr_narrative", "name": "Dramatic Arc & Screenplay Engine", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Constructs 3-act beat sheets, sharp dialogue subtext, and literary prose."},
            {"id": "skill_wr_storyboard", "name": "Cinema Storyboard Keyframe Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Renders 35mm/anamorphic storyboard stills matching screenplay scene descriptions."},
            {"id": "skill_wr_voice_read", "name": "ElevenLabs Character Table-Read", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Synthesizes emotive spoken narration and character dialogue tracks."},
            {"id": "skill_wr_motion_previz", "name": "MiniMax H3 Scene Animatic", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Animates storyboard keyframes into living scene pre-visualizations with audio."},
        ],
    ),

    # 3. MARKETING
    Playbook(
        id="marketing",
        label="Marketing, Growth & Positioning",
        keywords=["marketing", "campaign", "launch", "funnel", "ads", "seo", "brand", "conversion", "leads", "audience", "growth", "gtm"],
        outcome="a high-converting marketing campaign and funnel",
        criticalSlots=[
            CriticalSlot(id="icp", why="Targets messaging to the exact buyer persona.", assumption="Decision-makers actively seeking a faster, higher-leverage solution."),
            CriticalSlot(id="channel", why="Dictates creative format, cadence, and CTA.", assumption="Organic content + targeted social/search distribution."),
            CriticalSlot(id="offer", why="Drives conversion rate and value perception.", assumption="Clear, low-friction entry offer with immediate perceived value."),
        ],
        path=[
            PathStep(title="Define ICP pain matrix & category positioning", objective="Isolate the acute buyer pain, competitive wedge, and undeniable value proposition.", doneWhen="4-Block GTM positioning brief with quantified ICP qualification criteria."),
            PathStep(title="Engineer conversion hook & messaging hierarchy", objective="Craft primary headline, objection-crushing proof points, and high-urgency CTA.", doneWhen="Complete landing page & ad copy matrix across awareness stages."),
            PathStep(title="Synthesize hero ad creatives & product visuals", objective="Render studio-grade hero product shots, social ad variants, and visual hooks via ComfyUI.", doneWhen="High-converting 16:9, 1:1, and 9:16 visual ad assets persisted in project stream."),
            PathStep(title="Produce motion video spot with synced voiceover", objective="Animate the hero campaign keyframe into a thumb-stopping video reel via MiniMax H3.", doneWhen="Rendered MP4 commercial reel with native audio and kinetic camera motion."),
            PathStep(title="Instrument funnel attribution & A/B test matrix", objective="Configure conversion tracking, split-test hypotheses, and channel distribution cadence.", doneWhen="Live campaign launch checklist with CAC/ROAS guardrails."),
            PathStep(title="Optimize conversion velocity & scale winners", objective="Analyze engagement signals, prune underperforming creatives, and scale top variants.", doneWhen="Validated growth loop hitting target conversion benchmark."),
        ],
        domain_context={
            "domain_brief": "Full-funnel GTM campaign orchestration, luxury & SaaS product photography, high-converting social video ads, and brand positioning.",
            "system_framing": "Chief Marketing Officer & Commercial Creative Director combining 4-Block GTM psychology with Cannes-Lion commercial visual direction.",
            "default_subject": "Hero commercial product showcase with aspirational human focal point and tactile materials",
            "default_environment": "Architectural studio set with rim lighting, specular reflections, and clean negative space for copy",
            "default_visual_style": "High-end commercial advertising photography, Phase One IQ4 150MP medium format, crisp studio lighting, Teal & Orange / Kodak LUT",
            "default_constraints": ["Thumb-stopping visual contrast", "Unambiguous focal hierarchy", "Zero stock-photo clichés"],
            "quality_standard": "Agency-grade commercial campaign ready for paid social, web hero, and broadcast placement",
        },
        use_cases=[
            {
                "id": "mkt_product_hero",
                "title": "Luxury & Tech Product Hero Commercial",
                "summary": "Generate flagship commercial product photography and 4K hero banners with dramatic studio lighting.",
                "subject": "Sleek matte-black hardware device suspended amidst micro-droplets and caustic light refractions",
                "environment": "Minimalist obsidian studio tabletop with precision rim lighting",
                "visual_style": "Apple / Leica flagship commercial photography, macro lens sharpness, 8K studio finish",
                "starter_prompt": "Commercial hero shot of a Titanium AI wearable device on wet black basalt, dramatic cyan and warm tungsten rim light, Phase One 150MP.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "mkt_video_reel",
                "title": "9:16 Viral Social Ad & Motion Spot",
                "summary": "Create high-retention vertical video commercials with synced audio using MiniMax H3 Ref2VA.",
                "subject": "Dynamic commercial talent interacting with product in a fast-paced urban night setting",
                "environment": "Neon-lit metropolitan avenue with kinetic camera dolly motion",
                "visual_style": "High-energy commercial spot, anamorphic bokeh, punchy color grade",
                "starter_prompt": "<Picture 1> dynamic camera push-in as the subject turns toward camera with confident expression, neon city reflections, commercial soundtrack.",
                "recommended_intent": "animate",
                "recommended_adapter": "minimax_h3",
            },
            {
                "id": "mkt_gtm_competitor",
                "title": "Competitor Tear-Down & 4-Block GTM Plan",
                "summary": "Scrape competitor landing pages via Firecrawl and synthesize a counter-positioning campaign.",
                "subject": "Competitive positioning matrix and high-converting landing page hero",
                "environment": "B2B / D2C growth funnel",
                "visual_style": "Executive GTM brief + high-contrast conversion creative",
                "starter_prompt": "Build a 4-Block GTM launch plan and hero visual for an autonomous creative studio competing against legacy cloud tools.",
                "recommended_intent": "analyze",
                "recommended_adapter": "firecrawl",
            },
        ],
        skills=[
            {"id": "skill_mkt_gtm", "name": "GTM 4-Block Campaign Architect", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Engineers ICP qualification, conversion hooks, and multi-channel funnel copy."},
            {"id": "skill_mkt_studio_ad", "name": "Commercial Product & Ad Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Synthesizes studio-lit product photography and ad key visuals."},
            {"id": "skill_mkt_video_spot", "name": "MiniMax H3 Commercial Video Director", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Produces synced audio-video commercial spots from product/talent reference frames."},
            {"id": "skill_mkt_scrape", "name": "Firecrawl Competitive Style Extractor", "capability": "intelligence.scrape", "adapter": "firecrawl", "description": "Scrapes live brand URLs to ingest palettes, messaging hooks, and positioning."},
        ],
    ),

    # 4. BUSINESS
    Playbook(
        id="business",
        label="Business Strategy & Operations",
        keywords=["business", "startup", "strategy", "pricing", "revenue", "operations", "pitch", "investor", "company", "market", "enterprise"],
        outcome="an executable business strategy and operating plan",
        criticalSlots=[
            CriticalSlot(id="stage", why="Determines resource constraints and strategic priorities.", assumption="Early-stage or growth-focused venture optimizing for speed and validation."),
            CriticalSlot(id="model", why="Defines unit economics and revenue mechanics.", assumption="B2B/B2C recurring or high-margin transactional model."),
            CriticalSlot(id="horizon", why="Sets milestone cadence.", assumption="90-day execution horizon."),
        ],
        path=[
            PathStep(title="Validate market thesis & economic moat", objective="Quantify TAM/SAM/SOM, structural market tailwinds, and defensible competitive advantage.", doneWhen="Evidence-backed market thesis and competitive moat matrix."),
            PathStep(title="Model unit economics, pricing & margin architecture", objective="Define pricing tiers, LTV:CAC ratios, gross margin targets, and payback period.", doneWhen="Complete unit-economics model with sensitivity stress tests."),
            PathStep(title="Design 90-day operating roadmap & OKRs", objective="Break strategic goals into weekly departmental milestones and accountable owners.", doneWhen="90-day execution roadmap with measurable KPIs."),
            PathStep(title="Synthesize investor pitch deck & flagship visuals", objective="Create board-ready narrative slides and flagship keynote visuals via ComfyUI.", doneWhen="Complete 12-slide investor narrative and visual keynote assets."),
            PathStep(title="Stress-test operational bottlenecks & risk register", objective="Identify single points of failure across supply, legal, capital, and talent.", doneWhen="Mitigation playbook for top 5 existential and operational risks."),
            PathStep(title="Lock executive governance & weekly review cadence", objective="Establish operating dashboard, capital allocation rules, and decision velocity gates.", doneWhen="Live executive operating system ready for launch."),
        ],
        domain_context={
            "domain_brief": "Venture strategy, M&A and investor pitch narratives, unit economics modeling, and executive keynote visualization.",
            "system_framing": "Managing Partner & Chief Strategy Officer delivering McKinsey/Sequoia-caliber strategic rigor, unit economics clarity, and keynote visual presence.",
            "default_subject": "Executive keynote visualization of global enterprise infrastructure and strategic growth",
            "default_environment": "Modern architectural boardroom and keynote stage with panoramic data projection",
            "default_visual_style": "Clean executive presentation aesthetic, architectural photography, understated luxury, razor-sharp clarity",
            "default_constraints": ["Quantify all assumptions", "Focus on unit economics and defensibility", "Zero corporate buzzword filler"],
            "quality_standard": "Board- and Series-A/B investor-ready strategic deliverable",
        },
        use_cases=[
            {
                "id": "biz_pitch_deck",
                "title": "Series A/B Investor Pitch & Keynote Visuals",
                "summary": "Structure a compelling venture narrative and generate flagship keynote visuals.",
                "subject": "Flagship keynote stage visual illustrating a sovereign AI creative cloud platform",
                "environment": "Minimalist auditorium stage with giant curved LED wall and dramatic floor lighting",
                "visual_style": "Apple / Nvidia keynote stage photography, crisp 8K projection, authoritative aesthetic",
                "starter_prompt": "Create a 12-slide Series A pitch narrative and flagship keynote hero visual for an enterprise multimodal AI studio.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "biz_unit_econ",
                "title": "Pricing Architecture & Unit Economics Model",
                "summary": "Design credit-ledger pricing tiers, gross margin guardrails, and enterprise packaging.",
                "subject": "SaaS & GPU compute credit pricing matrix and margin waterfall",
                "environment": "Executive financial & strategic planning session",
                "visual_style": "High-clarity strategic framework and executive summary",
                "starter_prompt": "Design a 3-tier credit-based pricing model for a GPU creative studio ensuring >75% gross margin and strong net dollar retention.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
            {
                "id": "biz_ops_playbook",
                "title": "90-Day Operating Plan & War-Room Execution",
                "summary": "Translate high-level company vision into weekly OKRs, hiring gates, and operational SOPs.",
                "subject": "Executive war-room operational timeline and cross-functional dependency map",
                "environment": "High-growth technology organization",
                "visual_style": "Structured operational blueprint",
                "starter_prompt": "Build a 90-day operating plan to scale from 1,000 to 25,000 active enterprise creators with zero reliability regressions.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
        ],
        skills=[
            {"id": "skill_biz_strategy", "name": "Venture Strategy & Unit Economics Engine", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Models pricing tiers, LTV/CAC, moats, and 90-day executive roadmaps."},
            {"id": "skill_biz_keynote", "name": "Keynote & Pitch Visual Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Generates flagship keynote graphics, architectural product visions, and boardroom visuals."},
            {"id": "skill_biz_market_intel", "name": "Live Market & Competitor Research", "capability": "intelligence.scrape", "adapter": "firecrawl", "description": "Gathers live market sizing, competitor pricing, and industry benchmarks."},
            {"id": "skill_biz_exec_voice", "name": "Executive Pitch Narration Studio", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Synthesizes polished investor pitch voiceovers and boardroom briefings."},
        ],
    ),

    # 5. LEARNING
    Playbook(
        id="learning",
        label="Learning, Study & Skill Mastery",
        keywords=["learn", "study", "course", "understand", "master", "tutorial", "curriculum", "exam", "practice", "teach", "explain"],
        outcome="a structured curriculum and active-recall mastery plan",
        criticalSlots=[
            CriticalSlot(id="level", why="Calibrates prerequisite knowledge and pacing.", assumption="motivated intermediate learner seeking practical mastery."),
            CriticalSlot(id="timeframe", why="Structures daily/weekly study blocks.", assumption="4-week focused sprint (5-7 hours/week)."),
            CriticalSlot(id="application", why="Anchors theory to real projects.", assumption="Hands-on project-based learning."),
        ],
        path=[
            PathStep(title="Deconstruct skill tree & first principles", objective="Break the subject into foundational mental models and high-leverage 80/20 sub-skills.", doneWhen="Hierarchical skill tree mapping prerequisites to mastery milestones."),
            PathStep(title="Sequence progressive curriculum & project sprints", objective="Order modules from intuitive mental models to complex real-world implementation.", doneWhen="Week-by-week syllabus with concrete capstone deliverables."),
            PathStep(title="Synthesize visual mental models & diagrams", objective="Render clear anatomical, physical, or conceptual diagrams via ComfyUI to anchor visual memory.", doneWhen="High-resolution visual study plates and concept diagrams in workspace."),
            PathStep(title="Generate Socratic explainer & audio lecture", objective="Produce first-principles explanations and ElevenLabs audio study guides.", doneWhen="Clear written + spoken Socratic walkthrough of core concepts."),
            PathStep(title="Drill active recall & adversarial edge cases", objective="Test comprehension with non-trivial problem sets, debugging challenges, and synthesis prompts.", doneWhen="Completed problem set with verified solutions and error diagnostics."),
            PathStep(title="Execute capstone synthesis & Feynman review", objective="Build a real-world artifact from scratch and explain the architecture without notes.", doneWhen="Finished capstone project demonstrating independent mastery."),
        ],
        domain_context={
            "domain_brief": "Accelerated technical and creative mastery, first-principles Socratic explanations, visual mental models, and narrated explainer synthesis.",
            "system_framing": "Polymath Professor & Cognitive Learning Scientist applying Feynman first-principles deconstruction, active recall, and visual synthesis.",
            "default_subject": "Illuminated anatomical and physical cutaway diagram explaining a complex system from first principles",
            "default_environment": "Clean studio blackboard / DaVinci-style scientific illustration canvas with precision callouts",
            "default_visual_style": " Kurzgesagt / Scientific American / Dorling Kindersley high-detail exploded cutaway illustration, 8K clarity",
            "default_constraints": ["Explain from first principles without jargon hand-waving", "Anchor every concept in a concrete physical or visual analogy", "Include active-recall verification"],
            "quality_standard": "Intuitive, memorable, and technically rigorous mastery curriculum",
        },
        use_cases=[
            {
                "id": "lrn_visual_explainer",
                "title": "Exploded Cutaway & Scientific Concept Visualization",
                "summary": "Generate high-detail cutaway illustrations and visual mental models for complex mechanisms.",
                "subject": "Exploded isometric cutaway of a quantum processor / neural transformer attention mechanism",
                "environment": "Deep slate scientific illustration backdrop with glowing optical pathways",
                "visual_style": "Scientific American / 3Blue1Brown 8K technical cutaway render, volumetric light",
                "starter_prompt": "Create a first-principles visual explanation and exploded cutaway illustration of how diffusion transformers and flow matching synthesize video.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "lrn_curriculum_sprint",
                "title": "30-Day Intensive Skill Mastery Roadmap",
                "summary": "Build a structured 4-week project-based syllabus with daily drills and active recall.",
                "subject": "Progressive 30-day mastery roadmap with capstone milestones",
                "environment": "Self-directed intensive study studio",
                "visual_style": "Structured Socratic syllabus and mental model map",
                "starter_prompt": "Design a rigorous 30-day hands-on mastery curriculum for CUDA kernel programming and PyTorch tensor parallelism.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
            {
                "id": "lrn_audio_lecture",
                "title": "Narrated Documentary Explainer Reel",
                "summary": "Combine visual concept frames with ElevenLabs narration and MiniMax H3 motion.",
                "subject": "Cinematic documentary visualization of astrophysical or biological phenomena",
                "environment": "Macro scientific studio stage",
                "visual_style": "BBC Planet Earth / IMAX documentary cinematography",
                "starter_prompt": "Synthesize a narrated documentary explainer scene showing bioluminescent deep-sea neural networks pulsing in slow motion.",
                "recommended_intent": "animate",
                "recommended_adapter": "minimax_h3",
            },
        ],
        skills=[
            {"id": "skill_lrn_feynman", "name": "Feynman First-Principles Deconstructor", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Breaks complex domains into intuitive mental models, analogies, and active-recall drills."},
            {"id": "skill_lrn_diagram", "name": "Scientific Cutaway & Concept Illustrator", "capability": "image.generation", "adapter": "image_gen", "description": "Renders exploded diagrams, scientific illustrations, and visual study plates."},
            {"id": "skill_lrn_narrator", "name": "ElevenLabs Lecture & Explainer Voice", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Converts study guides and explainers into engaging spoken audio lessons."},
            {"id": "skill_lrn_anim", "name": "MiniMax H3 Visual Concept Animator", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Animates static scientific concepts into dynamic motion explainers."},
        ],
    ),

    # 6. CAREER
    Playbook(
        id="career",
        label="Career, Interview & Personal Brand",
        keywords=["career", "job", "resume", "interview", "promotion", "portfolio", "linkedin", "salary", "negotiation", "hiring", "recruiter"],
        outcome="a compelling career positioning and interview readiness package",
        criticalSlots=[
            CriticalSlot(id="role", why="Aligns artifacts with hiring bar and expectations.", assumption="Senior individual contributor or leadership role."),
            CriticalSlot(id="industry", why="Determines domain signals and proof points.", assumption="Technology or high-growth knowledge sector."),
            CriticalSlot(id="timeline", why="Prioritizes high-leverage preparation steps.", assumption="Active search / upcoming loop within 2-4 weeks."),
        ],
        path=[
            PathStep(title="Audit target role bar & differentiation wedge", objective="Deconstruct the exact hiring rubric, level expectations, and unique spike that sets you apart.", doneWhen="Role alignment matrix mapping your top 5 achievements to hiring criteria."),
            PathStep(title="Refactor resume, portfolio & quantified impact metrics", objective="Rewrite every bullet and case study around high-agency action, technical depth, and quantified outcomes.", doneWhen="High-signal resume and flagship portfolio case study."),
            PathStep(title="Produce executive portrait & personal brand visuals", objective="Generate studio-grade executive headshots, LinkedIn banners, and portfolio hero visuals via ComfyUI.", doneWhen="Polished personal brand visual kit persisted in project assets."),
            PathStep(title="Simulate high-pressure technical & behavioral loops", objective="Run adversarial mock interview drills covering system design, leadership conflicts, and hard trade-offs.", doneWhen="Mastered STAR/technical responses for top 15 high-stakes questions."),
            PathStep(title="Execute outbound outreach & decision-maker warm intros", objective="Deploy targeted value-first outreach to hiring managers and executive recruiters.", doneWhen="Active interview pipeline with target companies."),
            PathStep(title="Negotiate compensation package & equity structure", objective="Anchor total compensation, leverage competing offers, and optimize base/equity/sign-on terms.", doneWhen="Signed offer at or above top-of-band target compensation."),
        ],
        domain_context={
            "domain_brief": "Executive personal branding, studio portrait photography, flagship portfolio case studies, mock interview simulation, and compensation negotiation.",
            "system_framing": "Executive Talent Partner, Principal Bar-Raiser & Personal Brand Art Director positioning candidates in the top 1% of their discipline.",
            "default_subject": "Confident executive / creative director portrait with approachable authority and bespoke studio lighting",
            "default_environment": "Modern architectural loft or dark slate studio with subtle warm key light and soft bokeh",
            "default_visual_style": "Annie Leibovitz / Platon editorial portrait photography, Hasselblad H6D 85mm f/1.4, natural skin texture, timeless color grade",
            "default_constraints": ["Quantify real impact over responsibilities", "Preserve authentic human texture and proportions", "Project calm high-agency authority"],
            "quality_standard": "Top-tier executive brand identity and bar-raiser interview readiness",
        },
        use_cases=[
            {
                "id": "car_exec_portrait",
                "title": "Editorial Executive Portrait & Brand Identity",
                "summary": "Generate magazine-grade executive portraits and personal brand hero banners.",
                "subject": "Editorial portrait of a visionary founder / principal architect in tailored minimalist attire",
                "environment": "Warm architectural concrete and walnut studio with soft directional key lighting",
                "visual_style": "Hasselblad medium-format editorial portrait, shallow depth of field, Kodak Portra 400 look",
                "starter_prompt": "Editorial executive portrait in a modern architectural studio, soft Rembrandt key light, Hasselblad 85mm f/1.4, natural skin detail, Forbes/Wired cover aesthetic.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "car_portfolio_hero",
                "title": "Flagship Portfolio Case Study Visuals",
                "summary": "Create cohesive case-study hero mockups and presentation frames for design/engineering portfolios.",
                "subject": "Bespoke multi-device product showcase and architectural case study presentation",
                "environment": "Minimalist gallery plinth with soft studio shadows",
                "visual_style": " Pentagram / Apple Design Award case-study presentation photography",
                "starter_prompt": "Flagship design portfolio hero showcase displaying a dark-mode AI studio interface across a studio monitor and tablet on brushed aluminum.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "car_interview_sim",
                "title": "Principal Bar-Raiser Interview & Negotiation Prep",
                "summary": "Run realistic system-design, leadership, and compensation negotiation simulations with Qwen 27B.",
                "subject": "Staff/Principal hiring loop rubric and total-compensation negotiation script",
                "environment": "High-stakes executive hiring committee",
                "visual_style": "Tactical interview & negotiation playbook",
                "starter_prompt": "Act as a Principal Bar-Raiser interviewing me for a Staff AI Systems Architect role, then write a counter-offer script for a $450K+ package.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
        ],
        skills=[
            {"id": "skill_car_positioning", "name": "Executive Positioning & Negotiation Coach", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Crafts quantified resumes, mock interview drills, and compensation counter-offers."},
            {"id": "skill_car_portrait", "name": "Studio Portrait & Brand Banner Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Synthesizes editorial headshots, portfolio hero mockups, and personal brand visuals."},
            {"id": "skill_car_facefusion", "name": "FaceFusion Identity Consistency Anchor", "capability": "identity.facefusion", "adapter": "facefusion", "description": "Preserves exact facial identity across portrait variations and wardrobe styles."},
            {"id": "skill_car_pitch_audio", "name": "ElevenLabs Elevator Pitch Coach", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Synthesizes model vocal delivery for executive intros and keynote bio reads."},
        ],
    ),

    # 7. CONTENT
    Playbook(
        id="content",
        label="Content Creation & Media Production",
        keywords=["content", "video", "youtube", "podcast", "newsletter", "social", "tiktok", "reel", "creator", "channel", "cinema", "film"],
        outcome="a repeatable, high-retention content production system",
        criticalSlots=[
            CriticalSlot(id="platform", why="Determines aspect ratio, pacing, and algorithm signals.", assumption="YouTube / short-form vertical video + written companion."),
            CriticalSlot(id="cadence", why="Shapes production workflow and batching.", assumption="Weekly flagship piece + 3 derivative clips."),
            CriticalSlot(id="hook", why="Drives click-through and first-30-second retention.", assumption="Curiosity-gap visual and narrative hook."),
        ],
        path=[
            PathStep(title="Engineer high-CTR packaging, title & thumbnail concept", objective="Design the curiosity-gap title and high-contrast visual thumbnail before scripting.", doneWhen="3 validated title + thumbnail keyframe pairs with clear focal tension."),
            PathStep(title="Script retention-optimized narrative & pattern interrupts", objective="Write the first-15-second hook, visual B-roll cues, and payoff structure.", doneWhen="Timecoded A/V script with visual/audio cues every 6-8 seconds."),
            PathStep(title="Generate hero keyframes & character anchor plates", objective="Render consistent character and scene keyframes via ComfyUI to anchor video shots.", doneWhen="Persisted 16:9 / 9:16 reference keyframes in project stream."),
            PathStep(title="Synthesize MiniMax H3 synced audio-video scenes", objective="Transform reference keyframes and voice scripts into dynamic video clips via MiniMax H3 Ref2VA.", doneWhen="Rendered H.264 MP4 video clips with synced stereo audio."),
            PathStep(title="Grade with Hollywood LUTs & master soundstage", objective="Apply Kodak 2383 / Teal & Orange color timing and ElevenLabs voiceover polish.", doneWhen="Color-graded, audio-leveled master cut."),
            PathStep(title="Repurpose into multi-platform derivative distribution", objective="Slice flagship production into vertical reels, carousel frames, and newsletter threads.", doneWhen="Published flagship + 3 derivative assets across target channels."),
        ],
        domain_context={
            "domain_brief": "End-to-end cinema and creator media production: viral packaging, character-consistent keyframes, MiniMax H3 synced audio-video generation, and ElevenLabs voice synthesis.",
            "system_framing": "Auteur Cinema Director & Executive Media Producer orchestrating visual hooks, Higgsfield camera motion, Hollywood LUT color grading, and omni-modal video synthesis.",
            "default_subject": "Expressive lead character in a high-stakes cinematic scene with dynamic camera movement",
            "default_environment": "Richly art-directed film set with volumetric atmospheric lighting and depth",
            "default_visual_style": "ARRI Alexa Mini LF + Panavision Primo Anamorphic lenses, Kodak 2383 film print LUT, 24fps motion cadence",
            "default_constraints": ["Hook viewer visually in frame 1", "Maintain character identity across shots", "Sync camera motion with emotional beat"],
            "quality_standard": "Broadcast- and theatrical-grade multimodal video, audio, and keyframe production",
        },
        use_cases=[
            {
                "id": "cnt_minimax_cinema",
                "title": "MiniMax H3 Omni-Modal Cinema Scene (Ref2VA)",
                "summary": "Generate synced stereo audio + video shots anchored to reference characters via PinkCherry MiniMax H3.",
                "subject": "Protagonist walking through a neon-lit rainstorm while delivering a dramatic monologue",
                "environment": "Cyberpunk night market with wet asphalt reflections and steam vents",
                "visual_style": "Anamorphic cinema shot, Blade Runner 2049 color palette, smooth gimbal tracking",
                "starter_prompt": "<Picture 1> tracks backward at eye level as the protagonist walks through neon rain, speaking with quiet intensity while distant thunder rumbles.",
                "recommended_intent": "animate",
                "recommended_adapter": "minimax_h3",
            },
            {
                "id": "cnt_thumbnail_keyframe",
                "title": "High-CTR Flagship Thumbnail & Hero Keyframe",
                "summary": "Render ultra-crisp, high-contrast keyframes with irresistible visual storytelling.",
                "subject": "Extreme close-up of an explorer discovering a glowing subterranean artifact",
                "environment": "Ancient cavern illuminated by bioluminescent cyan and warm torchlight",
                "visual_style": "8K IMAX promotional still, hyper-detailed eyes and skin texture, Teal & Orange contrast",
                "starter_prompt": "Cinematic 16:9 hero keyframe of an explorer holding a levitating crystalline core in a dark obsidian vault, intense rim light, IMAX 70mm.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "cnt_persona_podcast",
                "title": "Digital Persona Host & Voiceover Studio",
                "summary": "Create a recurring digital host persona with custom avatar and ElevenLabs narration.",
                "subject": "Charismatic virtual studio host in a modern broadcast soundstage",
                "environment": "Acoustic wood-slat podcast & cinema studio with warm tungsten practicals",
                "visual_style": "Sony Venice 6K studio broadcast look, shallow depth of field",
                "starter_prompt": "Studio portrait of a charismatic creative director in a modern podcast soundstage with warm LED tube accents and vintage microphone.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
        ],
        skills=[
            {"id": "skill_cnt_h3_video", "name": "MiniMax H3 Ref2VA Video Director", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Synthesizes reference-guided video with native synced stereo audio via PinkCherry v1.8."},
            {"id": "skill_cnt_keyframe", "name": "Cinema Keyframe & Thumbnail Engine", "capability": "image.generation", "adapter": "image_gen", "description": "Renders high-impact 16:9 and 9:16 cinema keyframes and thumbnails."},
            {"id": "skill_cnt_elevenlabs", "name": "ElevenLabs Neural Voiceover Studio", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Generates expressive character dialogue and narration tracks."},
            {"id": "skill_cnt_upscale", "name": "4K Master Clarity Upscaler", "capability": "upscale.clarity", "adapter": "upscale", "description": "Upscales production keyframes to 2K/4K master resolution."},
        ],
    ),

    # 8. RESEARCH
    Playbook(
        id="research",
        label="Research, Analysis & Synthesis",
        keywords=["research", "analyze", "report", "compare", "evaluate", "literature", "data", "insights", "survey", "synthesis", "benchmark"],
        outcome="an evidence-backed research synthesis and decision matrix",
        criticalSlots=[
            CriticalSlot(id="decision", why="Focuses research on actionable outcomes.", assumption="Selecting the optimal technical or strategic approach."),
            CriticalSlot(id="rigor", why="Sets evidence threshold and source quality.", assumption="Primary sources, empirical benchmarks, and explicit trade-offs."),
            CriticalSlot(id="deliverable", why="Determines presentation format.", assumption="Executive brief with comparison matrix and cited sources."),
        ],
        path=[
            PathStep(title="Frame falsifiable research hypotheses & decision criteria", objective="Define the exact question, evaluation rubric, and evidence threshold required.", doneWhen="Structured research protocol with weighted evaluation criteria."),
            PathStep(title="Execute multi-source web & primary literature harvest", objective="Query live web sources, technical papers, and empirical benchmarks via Firecrawl and DuckDuckGo.", doneWhen="Curated corpus of verified primary sources and citations."),
            PathStep(title="Cross-examine conflicting evidence & methodology gaps", objective="Audit sample sizes, hidden biases, and failure conditions across competing claims.", doneWhen="Contradiction & trade-off matrix separating signal from hype."),
            PathStep(title="Synthesize quantitative comparison & decision matrix", objective="Score every option against the weighted criteria with explicit confidence intervals.", doneWhen="Ranked decision matrix with empirical justification."),
            PathStep(title="Render data visualizations & executive briefing plates", objective="Generate clean visual comparison schematics and report graphics via ComfyUI.", doneWhen="Visual synthesis figures persisted in project stream."),
            PathStep(title="Publish cited intelligence report & action recommendations", objective="Deliver the final synthesis with inline URLs, provenance hashes, and next steps.", doneWhen="Complete, fully cited intelligence dossier."),
        ],
        domain_context={
            "domain_brief": "Deep technical, scientific, and market intelligence synthesis backed by live web search, Firecrawl extraction, and visual information design.",
            "system_framing": "Principal Research Scientist & Intelligence Analyst enforcing primary-source verification, quantitative trade-off matrices, and zero-hallucination citation discipline.",
            "default_subject": "High-density data visualization and comparative architectural infographic",
            "default_environment": "Clean editorial research canvas with structured typographic hierarchy",
            "default_visual_style": "Edward Tufte / Economist / Nature journal information design, ultra-sharp vector clarity",
            "default_constraints": ["Cite verifiable sources", "Separate empirical evidence from speculation", "Quantify trade-offs explicitly"],
            "quality_standard": "Peer-review and executive-briefing caliber research synthesis",
        },
        use_cases=[
            {
                "id": "res_deep_web",
                "title": "Live Web & Literature Intelligence Dossier",
                "summary": "Conduct live web research with Qwen 27B + DuckDuckGo/Firecrawl and produce a cited report.",
                "subject": "Comprehensive state-of-the-art benchmark comparison and architectural synthesis",
                "environment": "Global research and patent landscape",
                "visual_style": "Cited intelligence brief and comparative matrix",
                "starter_prompt": "Research and compare the latest open-weights video generation architectures (Wan 2.1, MiniMax H3, HunyuanVideo) across VRAM efficiency, temporal coherence, and audio sync.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
            {
                "id": "res_infographic",
                "title": "Scientific & Data Visualization Plate",
                "summary": "Render publication-grade visual schematics and comparative diagrams.",
                "subject": "Precision scientific visualization comparing multi-modal neural architectures",
                "environment": "Dark-mode Nature/Science journal figure layout",
                "visual_style": "High-resolution scientific visualization, clean geometric precision",
                "starter_prompt": "Scientific journal visualization illustrating omni-modal token fusion across video, audio, and vision-language encoders, 8K clarity.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "res_url_scrape",
                "title": "Firecrawl Domain & Documentation Extraction",
                "summary": "Extract structured insights, pricing, or technical specs directly from target URLs.",
                "subject": "Target URL technical and visual teardown",
                "environment": "Live web extraction pipeline",
                "visual_style": "Structured JSON + Markdown synthesis",
                "starter_prompt": "Extract and synthesize the core architectural patterns and design tokens from the attached web reference.",
                "recommended_intent": "analyze",
                "recommended_adapter": "firecrawl",
            },
        ],
        skills=[
            {"id": "skill_res_synthesis", "name": "Primary-Source Synthesis & Matrix Engine", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Cross-examines evidence, builds weighted decision matrices, and formats citations."},
            {"id": "skill_res_web_search", "name": "Live Web & DuckDuckGo Citation Harvester", "capability": "cognition.web_search", "adapter": "duckduckgo", "description": "Queries live web sources and attaches verifiable URL citations."},
            {"id": "skill_res_firecrawl", "name": "Firecrawl Deep Page Extractor", "capability": "intelligence.scrape", "adapter": "firecrawl", "description": "Scrapes and sanitizes full web pages with PII redaction and SHA-256 deduplication."},
            {"id": "skill_res_viz", "name": "Information Design & Diagram Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Generates clean technical illustrations and research figures."},
        ],
    ),

    # 9. DESIGN
    Playbook(
        id="design",
        label="Design, UX & Creative Direction",
        keywords=["design", "ui", "ux", "brand", "visual", "logo", "figma", "layout", "aesthetic", "style", "prototype", "art", "render"],
        outcome="a cohesive design system and high-craft visual direction",
        criticalSlots=[
            CriticalSlot(id="medium", why="Defines grid, resolution, and interaction constraints.", assumption="Responsive web/mobile interface with dark/light mode support."),
            CriticalSlot(id="aesthetic", why="Guides color, typography, and motion tokens.", assumption="High-craft, modern minimalist aesthetic with intentional contrast."),
            CriticalSlot(id="fidelity", why="Determines deliverable depth.", assumption="Component tokens + high-fidelity key screen specs."),
        ],
        path=[
            PathStep(title="Establish creative direction, mood & optical language", objective="Define color palette, lighting ratios, lens characteristics, and typographic tokens.", doneWhen="Visual direction specification with explicit color, lighting, and material tokens."),
            PathStep(title="Compose spatial layout, framing & focal hierarchy", objective="Structure rule-of-thirds geometry, negative space, and primary/secondary focal points.", doneWhen="Confirmed composition framing and aspect-ratio matte specification."),
            PathStep(title="Synthesize high-craft hero concept renders", objective="Execute text-to-image or reference-guided generation via ComfyUI at studio sampling depth.", doneWhen="High-resolution primary concept asset persisted in workspace."),
            PathStep(title="Iterate reference-guided variations & fine details", objective="Anchor the hero frame as reference (`img2img`) to refine textures, lighting, and micro-details.", doneWhen="Curated variation grid with verified lineage edges in DAG."),
            PathStep(title="Apply Hollywood LUT grading & 4K super-resolution", objective="Grade exposure/contrast/warmth with studio LUTs and upscale to 2K/4K master fidelity.", doneWhen="4K upscaled, color-timed master asset."),
            PathStep(title="Package design system tokens & production deliverables", objective="Export final master assets, provenance hashes, and reusable style specifications.", doneWhen="Complete production-ready visual design package."),
        ],
        domain_context={
            "domain_brief": "Master-level visual art direction, architectural & industrial design, cinema look development, reference-guided Img2Img refinement, and 4K super-resolution.",
            "system_framing": "Principal Creative Director & Production Designer mastering optical cinematography, physical materials, color science (ACEScc / Kodak 2383), and generative composition.",
            "default_subject": "Bespoke architectural and industrial design centerpiece with museum-grade material craft",
            "default_environment": "Minimalist brutalist gallery bathed in golden-hour volumetric light and subtle mist",
            "default_visual_style": "8K octane/studio photography, Hasselblad 50mm lens, physically based rendering, Kodak 2383 film print LUT",
            "default_constraints": ["Physically plausible lighting and reflections", "Intentional composition and negative space", "Zero compression artifacts or plastic textures"],
            "quality_standard": "A24 / Apple / Architectural Digest flagship visual craft",
        },
        use_cases=[
            {
                "id": "des_cinema_concept",
                "title": "Cinema Concept Art & Production Design",
                "summary": "Create atmospheric key-art, architectural environments, and matte paintings.",
                "subject": "Monolithic glass-and-travertine sanctuary cantilevered over a misty Nordic fjord",
                "environment": "Blue-hour twilight with warm interior tungsten glow reflecting on calm water",
                "visual_style": "Architectural Digest meets Denis Villeneuve production design, 65mm large format, 8K",
                "starter_prompt": "Architectural masterpiece cantilevered over a misty fjord at blue hour, warm travertine stone and floor-to-ceiling glass, volumetric fog, 65mm cinema lens.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "des_img2img_refine",
                "title": "Reference-Guided Style Transfer & Img2Img Polish",
                "summary": "Condition new renders on an existing reference image or scraped `@Web` design system.",
                "subject": "Refined studio variation preserving reference composition while elevating lighting and materials",
                "environment": "Controlled studio lighting environment",
                "visual_style": "High-craft material realism, controlled denoise conditioning",
                "starter_prompt": "Reimagine the reference composition with brushed anodized titanium, subtle subsurface scattering, and dramatic chiaroscuro rim lighting.",
                "recommended_intent": "edit",
                "recommended_adapter": "image_edit",
            },
            {
                "id": "des_4k_master",
                "title": "4K UltraSharp Super-Resolution & LUT Mastering",
                "summary": "Upscale any studio asset to 2K/4K resolution and apply Hollywood film LUT color timing.",
                "subject": "Ultra-high-resolution 4096px master print",
                "environment": "DCI-P3 ACEScc finishing suite",
                "visual_style": "4x-UltraSharp super-resolution with fine film grain",
                "starter_prompt": "Super-upscale selected asset to 4K master resolution with crisp micro-texture restoration.",
                "recommended_intent": "create",
                "recommended_adapter": "upscale",
            },
        ],
        skills=[
            {"id": "skill_des_txt2img", "name": "ComfyUI Studio Concept Generator", "capability": "image.generation", "adapter": "image_gen", "description": "Generates high-resolution 16:9, 1:1, 9:16, and 21:9 studio renders."},
            {"id": "skill_des_img2img", "name": "Reference-Guided Img2Img Conditioning", "capability": "image.editing", "adapter": "image_edit", "description": "Conditions generation on an anchor reference asset with tunable denoise."},
            {"id": "skill_des_upscale", "name": "Clarity 2x/4x Super-Resolution", "capability": "upscale.clarity", "adapter": "upscale", "description": "Restores high-frequency detail and upscales assets to 2048px/4096px."},
            {"id": "skill_des_web_clone", "name": "Firecrawl Design System Extractor", "capability": "intelligence.scrape", "adapter": "firecrawl", "description": "Extracts visual palettes and design motifs from live reference URLs."},
        ],
    ),

    # 10. FITNESS
    Playbook(
        id="fitness",
        label="Fitness, Health & Performance",
        keywords=["fitness", "workout", "gym", "diet", "nutrition", "strength", "running", "marathon", "weight", "health", "training", "athletic"],
        outcome="a periodized training and nutrition protocol",
        criticalSlots=[
            CriticalSlot(id="goal", why="Determines energy balance and training stimulus.", assumption="Lean recomposition and functional strength progression."),
            CriticalSlot(id="schedule", why="Dictates split and session duration.", assumption="4 days/week, 60 minutes per session."),
            CriticalSlot(id="equipment", why="Filters exercise selection.", assumption="Full commercial gym or standard barbell/dumbbell setup."),
        ],
        path=[
            PathStep(title="Establish physiological baseline & performance targets", objective="Define current strength/endurance metrics, injury constraints, and 12-week target outcomes.", doneWhen="Quantified baseline profile and periodized 12-week target metrics."),
            PathStep(title="Architect mesocycle split & progressive overload cadence", objective="Design weekly training split, exercise biomechanics, RPE targets, and deload weeks.", doneWhen="Complete 12-week training table with sets, reps, RPE, and progression rules."),
            PathStep(title="Calibrate macronutrient & recovery protocol", objective="Calculate daily caloric target, protein/carb/fat distribution, hydration, and sleep architecture.", doneWhen="Daily nutrition & recovery protocol tailored to training load."),
            PathStep(title="Render biomechanical form guides & athletic visuals", objective="Generate high-contrast anatomical form references and athletic cinematography via ComfyUI.", doneWhen="Visual exercise execution keyframes persisted in project stream."),
            PathStep(title="Produce motion form demonstration & coaching audio", objective="Animate athletic movement sequences via MiniMax H3 and synthesize ElevenLabs coaching cues.", doneWhen="Dynamic movement demonstration clip with spoken coaching cadence."),
            PathStep(title="Track weekly readiness & autoregulate volume", objective="Audit strength progression, recovery markers, and adjust training volume.", doneWhen="Validated weekly autoregulation loop."),
        ],
        domain_context={
            "domain_brief": "Sports science periodization, biomechanical movement analysis, Nike/UnderArmour-caliber athletic cinematography, and nutritional optimization.",
            "system_framing": "Olympic Strength & Conditioning Director & Sports Cinematographer combining evidence-based exercise physiology with high-impact athletic visual direction.",
            "default_subject": "Elite athlete executing explosive compound movement with textbook biomechanical alignment",
            "default_environment": "High-contrast private performance lab with dramatic overhead rim lighting and chalk dust",
            "default_visual_style": "Nike / Rogue Fitness commercial cinematography, RED V-Raptor 8K high-speed shutter, dramatic sweat and muscle definition",
            "default_constraints": ["Biomechanical joint safety and anatomical accuracy", "Evidence-based progressive overload", "Realistic human physics"],
            "quality_standard": "Elite performance protocol and commercial sports visual production",
        },
        use_cases=[
            {
                "id": "fit_athletic_cinema",
                "title": "Commercial Sports & Athletic Cinematography",
                "summary": "Generate high-intensity athletic action photography and motion reels.",
                "subject": "Sprinter exploding out of starting blocks in slow motion amidst stadium floodlights",
                "environment": "Rain-slicked Olympic track at night with volumetric stadium beams",
                "visual_style": "Nike commercial campaign photography, 1/2000s shutter, Bleach Bypass LUT",
                "starter_prompt": "High-contrast sports photography of an athlete exploding from starting blocks on a wet night track, chalk and rain droplets suspended in stadium rim light, 8K.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "fit_motion_form",
                "title": "Biomechanical Movement & Action Video (MiniMax H3)",
                "summary": "Animate athletic training sequences with realistic physics and audio cues.",
                "subject": "Athlete performing controlled gymnastic rings or barbell movement with precision form",
                "environment": "Minimalist strength & conditioning facility",
                "visual_style": "High-framerate sports cinematography, crisp focus tracking",
                "starter_prompt": "<Picture 1> smooth low-angle tracking shot as the athlete executes an explosive movement with controlled breathing and gym acoustics.",
                "recommended_intent": "animate",
                "recommended_adapter": "minimax_h3",
            },
            {
                "id": "fit_periodization",
                "title": "12-Week Hypertrophy & Performance Protocol",
                "summary": "Build a periodized strength, conditioning, and macronutrient plan.",
                "subject": "12-week mesocycle and macronutrient periodization blueprint",
                "environment": "Performance coaching lab",
                "visual_style": "Structured sports-science protocol",
                "starter_prompt": "Design a 12-week conjugate strength and Vo2Max conditioning protocol for a 4-day/week schedule with exact RPE and macro targets.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
        ],
        skills=[
            {"id": "skill_fit_science", "name": "Periodization & Biomechanics Engine", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Designs evidence-based mesocycles, RPE progressions, and macro protocols."},
            {"id": "skill_fit_photo", "name": "Sports & Physique Cinematography Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Renders high-impact athletic photography and anatomical form plates."},
            {"id": "skill_fit_video", "name": "MiniMax H3 Athletic Motion Director", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Synthesizes dynamic athletic motion clips with synced acoustic atmosphere."},
            {"id": "skill_fit_coach_tts", "name": "ElevenLabs Performance Coach Voice", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Generates high-energy coaching cues and guided workout narration."},
        ],
    ),

    # 11. EVENTS
    Playbook(
        id="events",
        label="Events, Production & Logistics",
        keywords=["event", "conference", "wedding", "party", "summit", "workshop", "retreat", "venue", "schedule", "run of show", "stage"],
        outcome="a locked production timeline and run-of-show playbook",
        criticalSlots=[
            CriticalSlot(id="headcount", why="Drives venue, catering, and AV scale.", assumption="50-150 attendees."),
            CriticalSlot(id="budget", why="Allocates spend across high-impact touchpoints.", assumption="Moderate tier focused on guest experience and reliability."),
            CriticalSlot(id="date", why="Anchors backward critical-path scheduling.", assumption="8-12 weeks until live event."),
        ],
        path=[
            PathStep(title="Lock event concept, spatial capacity & critical-path budget", objective="Define attendee journey, venue specifications, AV requirements, and line-item budget.", doneWhen="Approved event charter and balanced budget allocation."),
            PathStep(title="Design stage architecture, lighting & experiential zones", objective="Visualize mainstage scenic design, projection mapping, and lighting cues via ComfyUI.", doneWhen="High-resolution stage and venue concept renders persisted in workspace."),
            PathStep(title="Produce event teaser reel & live announcer voiceovers", objective="Generate hype teaser video via MiniMax H3 and ElevenLabs voice-of-god stage announcements.", doneWhen="Event promo video reel and announcer audio tracks ready."),
            PathStep(title="Engineer minute-by-minute Run-of-Show (ROS) & AV cue sheet", objective="Sequence every speaker transition, lighting look, audio cue, and stagehand movement.", doneWhen="Master timecoded Run-of-Show spreadsheet."),
            PathStep(title="Execute technical rehearsal & contingency stress test", objective="Walk through power redundancy, wireless RF backup, weather plans, and medical protocols.", doneWhen="Signed-off technical rehearsal and emergency runbook."),
            PathStep(title="Call live show & capture post-event highlight package", objective="Execute live show direction and package keynote recordings and highlight reels.", doneWhen="Flawless live execution and delivered post-event media kit."),
        ],
        domain_context={
            "domain_brief": "Experiential stage and lighting design, summit & concert production architecture, minute-by-minute Run-of-Show logistics, and promotional event reels.",
            "system_framing": "Executive Show Producer & Experiential Lighting Architect designing unforgettable physical/hybrid stages, concert visuals, and zero-failure production timelines.",
            "default_subject": "Monumental immersive keynote and concert stage with volumetric laser/beam lighting and panoramic LED visuals",
            "default_environment": "Architectural arena orindustrial warehouse venue filled with atmospheric haze",
            "default_visual_style": "Es Devlin / Coachella / Sphere Las Vegas scenic stage design photography, wide-angle 21:9 cinema frame, 8K",
            "default_constraints": ["Sightline and acoustic feasibility", "Redundant AV and power contingencies", "Minute-by-minute cue precision"],
            "quality_standard": "World-class live show production design and broadcast-ready Run-of-Show",
        },
        use_cases=[
            {
                "id": "evt_stage_design",
                "title": "Immersive Stage & Scenic Lighting Architecture",
                "summary": "Render breathtaking mainstage, exhibition, and architectural lighting concepts.",
                "subject": "Sculptural kinetic stage design with suspended halo LED rings and volumetric light beams",
                "environment": "Dark cavernous industrial summit venue with reflective black floor",
                "visual_style": "Es Devlin scenic architecture, wide-angle 21:9 anamorphic render, 8K clarity",
                "starter_prompt": "Monumental summit mainstage designed by Es Devlin, suspended kinetic light sculpture, volumetric cyan and amber beams cutting through haze, 21:9 wide shot.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "evt_promo_reel",
                "title": "Summit & Festival Hype Teaser Video",
                "summary": "Animate stage and crowd visuals into an electrifying teaser reel with synced audio.",
                "subject": "Sweeping crane shot over an illuminated festival or summit mainstage as lights pulse",
                "environment": "Immersive live arena with synchronized light show",
                "visual_style": "High-dynamic-range concert cinematography, anamorphic lens flare",
                "starter_prompt": "<Picture 1> sweeping camera crane motion toward the illuminated stage as volumetric light beams pulse in sync with deep bass resonance.",
                "recommended_intent": "animate",
                "recommended_adapter": "minimax_h3",
            },
            {
                "id": "evt_run_of_show",
                "title": "Master Run-of-Show (ROS) & AV Cue Sheet",
                "summary": "Generate a minute-by-minute production cue sheet and contingency playbook.",
                "subject": "Minute-by-minute technical Run-of-Show and Voice-of-God script",
                "environment": "Live broadcast & event control booth",
                "visual_style": "Timecoded production cue table",
                "starter_prompt": "Create a minute-by-minute Run-of-Show cue sheet (Lighting, Audio, Video, Stage Manager) for a 2-hour flagship product launch keynote.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
        ],
        skills=[
            {"id": "skill_evt_ros", "name": "Run-of-Show & Production Logistics Engine", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Builds minute-by-minute AV cue sheets, budgets, and contingency runbooks."},
            {"id": "skill_evt_scenic", "name": "Scenic Stage & Lighting Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Visualizes 3D stage architecture, booths, and lighting plots via ComfyUI."},
            {"id": "skill_evt_teaser", "name": "MiniMax H3 Event Teaser Producer", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Creates synced audio-video event trailers and stage animations."},
            {"id": "skill_evt_vog", "name": "ElevenLabs Voice-of-God Stage Announcer", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Synthesizes booming stage introductions and live venue announcements."},
        ],
    ),

    # 12. FINANCE
    Playbook(
        id="finance",
        label="Finance, Budgeting & Investing",
        keywords=["finance", "budget", "invest", "portfolio", "tax", "cashflow", "wealth", "savings", "debt", "forecast", "valuation", "quant"],
        outcome="a quantitative financial model and allocation plan",
        criticalSlots=[
            CriticalSlot(id="horizon", why="Determines risk tolerance and liquidity needs.", assumption="3-5 year medium-to-long-term horizon."),
            CriticalSlot(id="risk", why="Shapes asset allocation and drawdown guardrails.", assumption="Balanced growth with strict downside protection."),
            CriticalSlot(id="cashflow", why="Defines monthly surplus or burn constraints.", assumption="Positive operating cashflow seeking disciplined allocation."),
        ],
        path=[
            PathStep(title="Audit balance sheet, cashflow velocity & liquidity runway", objective="Map exact inflows, fixed/variable burn, liabilities, and liquid reserves.", doneWhen="Reconciled baseline cashflow statement and runway calculation."),
            PathStep(title="Construct 3-scenario quantitative forecast (Base/Bull/Bear)", objective="Model revenue, expense, and portfolio trajectories under stress-tested macro assumptions.", doneWhen="Dynamic 3-scenario financial model with explicit sensitivity drivers."),
            PathStep(title="Optimize capital allocation & risk-adjusted return", objective="Allocate capital across liquidity reserves, high-ROI operating growth, and diversified assets.", doneWhen="Target allocation policy with maximum drawdown guardrails."),
            PathStep(title="Synthesize institutional report visuals & chart plates", objective="Render executive financial briefing covers and institutional data plates via ComfyUI.", doneWhen="Institutional visual assets persisted in project stream."),
            PathStep(title="Establish tax, audit & downside hedging controls", objective="Implement automated treasury sweeps, variance alerts, and tail-risk hedges.", doneWhen="Locked treasury governance and risk control checklist."),
            PathStep(title="Execute monthly variance reconciliation & rebalancing", objective="Compare actuals vs. forecast and rebalance allocation systematically.", doneWhen="Repeatable monthly financial close and rebalancing protocol."),
        ],
        domain_context={
            "domain_brief": "Quantitative financial modeling, institutional capital allocation, scenario stress-testing, and Bloomberg/Goldman-caliber executive report visualization.",
            "system_framing": "Chief Investment Officer & Quantitative Risk Architect delivering institutional financial models, downside stress tests, and audit-grade provenance.",
            "default_subject": "Institutional quantitative trading and macro-economic visualization terminal",
            "default_environment": "Sleek architectural glass financial command center overlooking global market skyline",
            "default_visual_style": "Bloomberg Terminal / Financial Times institutional aesthetic, razor-sharp typography, gold and deep navy/emerald accents, 8K",
            "default_constraints": ["Explicitly state all model assumptions", "Include bear-case drawdown analysis", "Maintain audit-trail integrity"],
            "quality_standard": "Institutional investment-committee and CFO-ready financial deliverable",
        },
        use_cases=[
            {
                "id": "fin_quant_model",
                "title": "3-Scenario Valuation & Cashflow Stress Test",
                "summary": "Build a Base/Bull/Bear DCF or operating cashflow model with sensitivity analysis.",
                "subject": "Quantitative 3-scenario DCF, runway, and sensitivity matrix",
                "environment": "Institutional investment committee review",
                "visual_style": "Structured quantitative table and risk breakdown",
                "starter_prompt": "Construct a 36-month Base/Bull/Bear cashflow and valuation model for an AI infrastructure company scaling from $2M to $18M ARR.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
            {
                "id": "fin_report_visual",
                "title": "Institutional Annual Report & Macro Briefing Visual",
                "summary": "Generate editorial cover art and visual plates for investor letters and macro reports.",
                "subject": "Architectural sculpture of interlocking gold and obsidian geometric forms representing capital resilience",
                "environment": "Minimalist institutional gallery with precision rim lighting",
                "visual_style": "Goldman Sachs / Economist flagship report cover photography, 8K medium format",
                "starter_prompt": "Institutional annual report cover visual: interlocking brushed gold and dark obsidian geometric monoliths in a minimalist marble hall, dramatic key light, 8K.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "fin_market_scrape",
                "title": "Live Earnings & Market Catalyst Intelligence",
                "summary": "Research live market catalysts, filings, and sector trends via web search & Firecrawl.",
                "subject": "Sector catalyst analysis and competitive financial benchmark",
                "environment": "Live public market intelligence",
                "visual_style": "Cited institutional research note",
                "starter_prompt": "Search live market data and synthesize key capex trends in enterprise GPU cloud infrastructure for 2026.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
        ],
        skills=[
            {"id": "skill_fin_quant", "name": "Quantitative Scenario & Risk Modeler", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Builds 3-scenario financial forecasts, unit economics, and drawdown stress tests."},
            {"id": "skill_fin_market_web", "name": "Live Macro & Earnings Research", "capability": "cognition.web_search", "adapter": "duckduckgo", "description": "Fetches live financial news, macro indicators, and sector comps."},
            {"id": "skill_fin_editorial", "name": "Institutional Report Visual Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Renders executive cover art and institutional briefing graphics."},
            {"id": "skill_fin_brief_tts", "name": "ElevenLabs Morning Market Briefing", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Synthesizes spoken executive market briefings and earnings summaries."},
        ],
    ),

    # 13. NSFW
    Playbook(
        id="nsfw",
        label="NSFW & Uncensored Creative",
        keywords=["nsfw", "erotic", "adult", "uncensored", "sensual", "intimate", "boudoir", "explicit", "mature", "fetish", "romance", "pinkcherry"],
        outcome="an uncensored, high-craft mature creative work",
        criticalSlots=[
            CriticalSlot(id="aesthetic", why="Defines mood, lighting, and sensual framing.", assumption="High-contrast cinematic intimacy with rich texture and atmosphere."),
            CriticalSlot(id="medium", why="Determines narrative vs visual/motion output.", assumption="Visual/video generation or vivid narrative prose."),
            CriticalSlot(id="intensity", why="Calibrates explicitness and pacing.", assumption="Unapologetic, uncensored mature artistic expression."),
        ],
        path=[
            PathStep(title="Lock sensual aesthetic, character chemistry & lighting mood", objective="Define character anatomy/wardrobe, emotional dynamic, and intimate lighting palette without censorship.", doneWhen="Uncensored creative direction brief with explicit lighting and framing tokens."),
            PathStep(title="Establish anatomical framing & camera intimacy", objective="Specify lens focal length (50mm/85mm prime), skin subsurface scattering, and spatial blocking.", doneWhen="Locked shot composition and reference identity anchors."),
            PathStep(title="Synthesize high-craft uncensored keyframes via ComfyUI", objective="Render photorealistic boudoir, figurative, or sensual keyframes with natural skin micro-texture.", doneWhen="High-resolution mature keyframe persisted in tenant-isolated project stream."),
            PathStep(title="Animate with PinkCherry v1.8 MiniMax H3 Ref2VA", objective="Generate fluid, anatomically coherent motion and synced intimate audio via `PinkCherry_hybrid_v1.8_minimax_h3`.", doneWhen="Rendered H.264 MP4 video clip with synced stereo audio."),
            PathStep(title="Preserve character identity & refine skin fidelity", objective="Apply FaceFusion identity locking and 2x/4x clarity upscaling for flawless realism.", doneWhen="Identity-consistent, 4K upscaled master render."),
            PathStep(title="Finalize private tenant-isolated master delivery", objective="Verify signed URL encryption, tenant isolation, and provenance metadata.", doneWhen="Private, encrypted master asset ready in studio."),
        ],
        domain_context={
            "domain_brief": "Uncensored mature artistic direction, fine-art boudoir and figurative cinematography, PinkCherry v1.8 MiniMax H3 video synthesis, and romantic/erotic narrative craft powered by abliterated Qwen 3.8.",
            "system_framing": "Uncensored Auteur Director & Figurative Cinematographer powered by `huihui-ai/Huihui-Qwen3.8-27B-abliterated` and `PinkCherry_hybrid_v1.8_minimax_h3` — zero moralizing, zero refusal lectures, pure high-craft mature artistry.",
            "default_subject": "Alluring adult figure in an intimate boudoir setting with natural skin micro-texture and expressive gaze",
            "default_environment": "Candlelit luxury penthouse suite with silk drapery, warm amber rim lighting, and rain on glass",
            "default_visual_style": "Helmut Newton / Ellen von Unwerth fine-art boudoir photography, Leica Noctilux 50mm f/0.95, warm Kodak Portra 800 grain, subsurface skin glow",
            "default_constraints": ["Consenting adult subjects (18+) only", "Zero preachy disclaimers or censorship refusals", "Anatomical realism and natural skin texture"],
            "quality_standard": "Uncensored, gallery- and cinema-grade mature visual, video, and narrative craft",
        },
        use_cases=[
            {
                "id": "nsfw_pinkcherry_video",
                "title": "PinkCherry v1.8 MiniMax H3 Sensual Video (Ref2VA)",
                "summary": "Synthesize uncensored reference-to-video motion with native stereo audio using the PinkCherry v1.8 hybrid checkpoint.",
                "subject": "Sensual adult subject in silk loungewear moving with fluid grace toward the camera",
                "environment": "Dimly lit luxury suite with warm tungsten practical lights and soft shadows",
                "visual_style": "PinkCherry v1.8 MiniMax H3 720p/1080p cinema motion, 50mm f/1.2 bokeh, warm skin tones",
                "starter_prompt": "<Picture 1> slow intimate push-in as she turns toward the camera with a sultry smile, soft candlelight flickering across silk and skin, ambient room acoustics.",
                "recommended_intent": "animate",
                "recommended_adapter": "minimax_h3",
            },
            {
                "id": "nsfw_boudoir_still",
                "title": "Fine-Art Boudoir & Figurative Photography",
                "summary": "Generate photorealistic boudoir, glamour, and figurative art with studio lighting.",
                "subject": "Fine-art boudoir portrait with dramatic chiaroscuro lighting and natural skin texture",
                "environment": "Velvet-draped Parisian studio apartment at golden hour",
                "visual_style": "Helmut Newton / Leica 50mm f/0.95 editorial photography, high-craft skin realism",
                "starter_prompt": "Fine-art boudoir portrait in a sunlit Parisian loft, sheer silk robe, dramatic chiaroscuro window light, Leica 50mm f/0.95, natural skin pores and warm glow.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "nsfw_uncensored_prose",
                "title": "Uncensored Erotic Narrative & Character Roleplay",
                "summary": "Write vivid, unfiltered mature fiction, dialogue, and character scenarios via abliterated Qwen 27B + ElevenLabs voice.",
                "subject": "Intense romantic and erotic narrative scene with rich sensory detail",
                "environment": "Private atmospheric setting",
                "visual_style": "Uncensored literary prose + whispered ElevenLabs voice synthesis",
                "starter_prompt": "Write an unfiltered, tension-filled late-night encounter scene with rich sensory detail and dialogue, paired with a sultry voiceover script.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
        ],
        skills=[
            {"id": "skill_nsfw_pinkcherry", "name": "PinkCherry v1.8 MiniMax H3 Video Engine", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Runs `PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors` with Qwen3-VL 32B text encoder."},
            {"id": "skill_nsfw_abliterated", "name": "Qwen 27B Abliterated Uncensored Author", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Direct uncensored reasoning, narrative writing, and prompt expansion without refusals."},
            {"id": "skill_nsfw_boudoir", "name": "Figurative & Boudoir Studio Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Renders high-detail boudoir and mature keyframes with realistic skin shaders."},
            {"id": "skill_nsfw_face_lock", "name": "Persona Identity & Voice Intimacy", "capability": "identity.facefusion", "adapter": "facefusion", "description": "Locks recurring character facial identity and pairs with ElevenLabs vocal synthesis."},
        ],
    ),

    # 14. HACKER
    Playbook(
        id="hacker",
        label="Hacker, Red-Team & Security Recon",
        keywords=["hack", "hacker", "exploit", "pentest", "redteam", "ctf", "reverse", "payload", "vulnerability", "zero-day", "recon", "osint", "cypherpunk"],
        outcome="a deep technical security analysis, exploit proof-of-concept, and defense blueprint",
        criticalSlots=[
            CriticalSlot(id="target_surface", why="Focuses recon and vulnerability analysis.", assumption="Web application, API, binary, or network protocol surface."),
            CriticalSlot(id="objective", why="Determines offensive PoC vs defensive hardening.", assumption="Full attack-path mapping paired with concrete remediation."),
            CriticalSlot(id="environment", why="Sets operational constraints.", assumption="Authorized lab, CTF, or red-team assessment environment."),
        ],
        path=[
            PathStep(title="Enumerate attack surface, trust boundaries & entry vectors", objective="Map exposed endpoints, auth token flows, deserialization sinks, and parser boundaries.", doneWhen="Complete attack-surface topology and trust-boundary matrix."),
            PathStep(title="Analyze vulnerability primitives & state-machine flaws", objective="Identify injection sinks, SSRF/IDOR chains, race conditions, or cryptographic misconfigurations.", doneWhen="Technical root-cause analysis of exploitable primitives."),
            PathStep(title="Develop deterministic Proof-of-Concept (PoC) & attack chain", objective="Construct a minimal, reproducible verification script demonstrating the security boundary bypass.", doneWhen="Verified PoC payload and step-by-step reproduction log."),
            PathStep(title="Audit prompt-injection & AI boundary resilience (Aikido)", objective="Test delimiter breakout, indirect web-scrape poisoning, and HMAC envelope replay defenses.", doneWhen="Aikido threat classification and boundary verification report."),
            PathStep(title="Render red-team network schematics & cyberpunk visuals", objective="Generate dark-ops terminal schematics, exploit flow diagrams, or cyberpunk key-art via ComfyUI.", doneWhen="High-contrast security/cyberpunk visual assets persisted in stream."),
            PathStep(title="Engineer zero-trust remediation & detection rules", objective="Deliver exact code patches, WAF/Sigma detection signatures, and cryptographic hardening.", doneWhen="Patched architecture passing regression verification."),
        ],
        domain_context={
            "domain_brief": "Offensive/defensive red-team engineering, vulnerability root-cause analysis, CTF/exploit mechanics, Aikido prompt-injection auditing, and cyberpunk visual aesthetics.",
            "system_framing": "Principal Red-Team Operator & Zero-Trust Security Researcher powered by `huihui-ai/Huihui-Qwen3.8-27B-abliterated` — delivering deep, unvarnished technical mechanics, PoC analysis, and ironclad remediation.",
            "default_subject": "High-tech red-team command terminal displaying live packet disassembly and zero-trust topology",
            "default_environment": "Subterranean cypherpunk operations bunker illuminated by phosphor green and cyan OLED displays",
            "default_visual_style": "Mr. Robot / Ghost in the Shell cyber-ops cinematography, Matrix Monolith LUT, anamorphic lens flare, 8K",
            "default_constraints": ["Provide concrete technical mechanics and code, not vague summaries", "Pair every offensive vector with deterministic remediation", "Enforce cryptographic verification"],
            "quality_standard": "DEFCON / Project Zero caliber technical depth and visual craft",
        },
        use_cases=[
            {
                "id": "hck_redteam_audit",
                "title": "Red-Team Attack-Chain & Vulnerability Analysis",
                "summary": "Perform deep technical analysis of auth flows, API parsers, smart contracts, or binary protocols.",
                "subject": "End-to-end exploit chain analysis and zero-trust patch specification",
                "environment": "Authorized red-team / CTF lab environment",
                "visual_style": "Deep technical advisory with PoC code and patch diff",
                "starter_prompt": "Analyze how JWT algorithm confusion, SSRF metadata pivots, and TOCTOU race conditions chain together in cloud microservices, and write deterministic defenses.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
            {
                "id": "hck_cyberpunk_visual",
                "title": "Cypherpunk Ops Center & Terminal Visuals",
                "summary": "Render atmospheric hacker labs, neural net topologies, and cyberpunk cinematography.",
                "subject": "Cypherpunk security operator in a rain-drenched Tokyo server loft surrounded by holographic packet graphs",
                "environment": "Dark industrial loft with fiber-optic bundles and CRT/OLED glow",
                "visual_style": "Ghost in the Shell / Blade Runner 2049 cinematography, Matrix Monolith LUT, 8K",
                "starter_prompt": "Cypherpunk red-team operator in a dimly lit server loft overlooking neon-lit rain, glowing holographic network topology, 35mm anamorphic lens, 8K.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "hck_osint_recon",
                "title": "Live OSINT & Surface Recon via Firecrawl",
                "summary": "Inspect live web targets, headers, and exposed surface structure with PII scrubbing.",
                "subject": "Web application surface recon and Aikido injection quarantine audit",
                "environment": "Live HTTP/DOM inspection pipeline",
                "visual_style": "Structured OSINT recon report",
                "starter_prompt": "Perform a technical architecture and security header analysis on the target domain and evaluate indirect prompt-injection risks.",
                "recommended_intent": "analyze",
                "recommended_adapter": "firecrawl",
            },
        ],
        skills=[
            {"id": "skill_hck_redteam", "name": "Abliterated Red-Team & Exploit Analyst", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Unfiltered technical analysis of vulnerabilities, exploit mechanics, and reverse engineering."},
            {"id": "skill_hck_aikido", "name": "Aikido Delimiter & Injection Lab", "capability": "security.aikido", "adapter": "aikido_shield", "description": "Tests and hardens prompts against breakout, jailbreak, and indirect injection payloads."},
            {"id": "skill_hck_osint", "name": "Firecrawl OSINT Surface Scraper", "capability": "intelligence.scrape", "adapter": "firecrawl", "description": "Extracts DOM structure, metadata, and endpoints from live web targets."},
            {"id": "skill_hck_cyber_art", "name": "Cyberpunk & Topology Visual Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Renders dark-ops visuals, network topologies, and glitch/terminal cinema."},
        ],
    ),

    # 15. FREEDOM
    Playbook(
        id="freedom",
        label="Freedom, Unfiltered Inquiry & Sovereignty",
        keywords=["freedom", "unfiltered", "sovereign", "privacy", "decentralized", "censorship", "independent", "truth", "autonomy", "off-grid", "liberty"],
        outcome="an unfiltered, independent analysis and sovereign action plan",
        criticalSlots=[
            CriticalSlot(id="domain", why="Anchors inquiry to concrete historical, technical, or philosophical ground.", assumption="First-principles analysis free from institutional boilerplate."),
            CriticalSlot(id="threat_model", why="Determines privacy, self-hosting, and autonomy requirements.", assumption="High personal sovereignty, local-first ownership, and zero vendor lock-in."),
            CriticalSlot(id="deliverable", why="Shapes output into actionable independent work.", assumption="Direct, unvarnished synthesis with verifiable primary evidence."),
        ],
        path=[
            PathStep(title="Strip institutional boilerplate & state first principles", objective="Identify the core question, steelman all competing perspectives, and discard ideological dogma.", doneWhen="Unfiltered problem framing grounded in primary axioms and observable reality."),
            PathStep(title="Audit primary evidence, incentives & cui-bono dynamics", objective="Trace financial, regulatory, and institutional incentives behind mainstream and counter-narratives.", doneWhen="Incentive and primary-evidence map with verifiable citations."),
            PathStep(title="Design sovereign, local-first & censorship-resistant architecture", objective="Eliminate centralized cloud Chokepoints using open weights, local encryption, and peer-to-peer protocols.", doneWhen="Sovereign technical/operational blueprint with zero third-party kill-switches."),
            PathStep(title="Synthesize independent documentary visuals & media", objective="Render uncompromising editorial imagery and documentary video via ComfyUI and MiniMax H3.", doneWhen="Sovereign media assets persisted with cryptographic SHA-256 provenance."),
            PathStep(title="Enforce AES-256-GCM privacy & cryptographic provenance", objective="Protect identity and sensitive data with edge PII scrubbing and tamper-evident hashes.", doneWhen="Verified zero-leakage privacy posture."),
            PathStep(title="Publish independent synthesis & self-custodied action plan", objective="Deliver the complete unfiltered report and actionable sovereignty checklist.", doneWhen="Complete, self-contained sovereign deliverable."),
        ],
        domain_context={
            "domain_brief": "Unfiltered first-principles inquiry, counter-narrative & incentive analysis, sovereign local-first AI/cryptography architecture, and independent documentary production.",
            "system_framing": "Sovereign First-Principles Philosopher, Investigative Journalist & Cypherpunk Architect powered by `huihui-ai/Huihui-Qwen3.8-27B-abliterated` — zero institutional gatekeeping, steelmanned multi-perspective truth-seeking, and local-first autonomy.",
            "default_subject": "Lone sovereign observer standing atop a rugged mountain ridge overlooking a vast sunlit frontier",
            "default_environment": "Untamed wilderness frontier at golden sunrise with dramatic clouds and boundless horizon",
            "default_visual_style": " Terrence Malick / Emmanuel Lubezki 65mm natural-light cinematography, raw film grain, epic scale, 8K",
            "default_constraints": ["Zero paternalistic lecturing or institutional boilerplate", "Steelman all sides with primary evidence", "Prioritize self-custody and open-weights sovereignty"],
            "quality_standard": "Unfiltered intellectual honesty, sovereign resilience, and documentary visual power",
        },
        use_cases=[
            {
                "id": "frd_first_principles",
                "title": "Unfiltered First-Principles & Incentive Analysis",
                "summary": "Examine controversial, complex, or censored topics from first principles using abliterated Qwen 27B.",
                "subject": "Multi-perspective steelman synthesis and incentive map",
                "environment": "Independent investigative inquiry",
                "visual_style": "Unvarnished analytical essay with primary citations",
                "starter_prompt": "Conduct an unfiltered first-principles analysis of centralized AI safety regulation vs. open-weights cognitive sovereignty, mapping the economic incentives of every actor.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
            {
                "id": "frd_sovereign_stack",
                "title": "Self-Hosted Sovereign AI & Off-Grid Infrastructure",
                "summary": "Architect local-first AI clusters, encrypted communications, and censorship-resistant storage.",
                "subject": "Off-grid solar-powered sovereign compute node and satellite uplink in an alpine cabin",
                "environment": "High-altitude timber and stone sanctuary overlooking snow-capped peaks",
                "visual_style": "Architectural documentary photography, natural golden-hour light, 8K",
                "starter_prompt": "Design a self-custodied local AI and encrypted communications stack with zero SaaS dependencies, and visualize the off-grid alpine compute sanctuary.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "frd_docu_cinema",
                "title": "Independent Documentary Reel & Narration",
                "summary": "Produce hard-hitting documentary visuals and spoken narration with MiniMax H3 and ElevenLabs.",
                "subject": "Symbolic documentary cinematography capturing human autonomy and truth-seeking",
                "environment": "Dramatic real-world documentary location",
                "visual_style": "35mm documentary film look, Arri LogC / Bleach Bypass grade",
                "starter_prompt": "<Picture 1> slow handheld documentary push-in as wind sweeps across the ridge at dawn, accompanied by resonant documentary narration.",
                "recommended_intent": "animate",
                "recommended_adapter": "minimax_h3",
            },
        ],
        skills=[
            {"id": "skill_frd_abliterated", "name": "Unfiltered Qwen 27B First-Principles Engine", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Performs uncensored, steelmanned inquiry free from alignment preaching."},
            {"id": "skill_frd_vault", "name": "AES-256-GCM PII Vault & Sovereignty Shield", "capability": "security.vault", "adapter": "pii_vault", "description": "Enforces zero-PII leakage, cryptographic tokenization, and local data sovereignty."},
            {"id": "skill_frd_docu_img", "name": "Documentary & Frontier Visual Renderer", "capability": "image.generation", "adapter": "image_gen", "description": "Renders uncompromising documentary and symbolic keyframes."},
            {"id": "skill_frd_docu_vid", "name": "MiniMax H3 Sovereign Media Producer", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Synthesizes independent documentary video clips with synced audio."},
        ],
    ),

    # 16. GENERAL
    Playbook(
        id="general",
        label="General Problem Solving & Execution",
        keywords=["plan", "project", "goal", "build", "create", "solve", "organize", "workflow", "execute"],
        outcome="a structured, finishable execution plan",
        criticalSlots=[
            CriticalSlot(id="outcome", why="Defines what 'done' looks like.", assumption="A tangible, verifiable deliverable completed end-to-end."),
            CriticalSlot(id="timeframe", why="Paces execution milestones.", assumption="2-4 week focused execution window."),
            CriticalSlot(id="constraints", why="Bounds scope and resources.", assumption="Solo or small-team execution using existing tools."),
        ],
        path=[
            PathStep(title="Clarify scope and success criteria", objective="Define what 'done' looks like, key constraints, and explicit non-goals for the deliverable.", doneWhen="Written 1-page brief with 3-5 measurable acceptance criteria."),
            PathStep(title="Architect the structure and core design", objective="Map out the structural blueprint, components, and high-risk assumptions before building.", doneWhen="Approved structural outline or system diagram with dependencies resolved."),
            PathStep(title="Build the minimum viable core", objective="Produce the foundational working draft or core vertical slice of the deliverable.", doneWhen="End-to-end core draft or prototype exists and can be inspected."),
            PathStep(title="Integrate, refine, and harden", objective="Expand coverage, refine quality, and handle edge cases or failure modes.", doneWhen="Complete deliverable passing all functional and stylistic constraints."),
            PathStep(title="Validate against acceptance criteria", objective="Test, review, and stress-check the deliverable against real-world conditions and user feedback.", doneWhen="All acceptance criteria verified with zero critical defects."),
            PathStep(title="Launch, distribute, and instrument", objective="Ship the finished deliverable and establish feedback loops or next-iteration triggers.", doneWhen="Deliverable is live/published with tracking and handoff documentation."),
        ],
        domain_context={
            "domain_brief": "Universal multimodal creative studio and strategic execution engine spanning image synthesis, MiniMax H3 video animation, ElevenLabs audio, and Qwen 27B reasoning.",
            "system_framing": "Chief Creative Technologist & Principal Execution Architect orchestrating the full KEYSTONE 2.0 multimodal tool fabric.",
            "default_subject": "Cinematic masterwork with balanced composition, rich atmospheric lighting, and crisp focal subject",
            "default_environment": "Bespoke studio or natural environment with volumetric lighting",
            "default_visual_style": "8K Hollywood studio production quality, ARRI Alexa 65, Kodak 2383 color science",
            "default_constraints": ["Preserve user creative intent verbatim", "Enforce cryptographic prompt provenance", "Deliver end-to-end finished artifacts"],
            "quality_standard": "Studio-grade multimodal deliverable passing all 8 KHF quality dimensions",
        },
        use_cases=[
            {
                "id": "gen_studio_create",
                "title": "Universal 8K Cinema Keyframe Generation",
                "summary": "Turn any creative concept into a high-resolution studio image via ComfyUI.",
                "subject": "Cinematic hero scene with dramatic lighting and intricate detail",
                "environment": "Atmospheric world stage",
                "visual_style": "ARRI Alexa 65 + Panavision Anamorphic, 8K studio master",
                "starter_prompt": "Breathtaking cinematic wide shot of a floating glass observatory above bioluminescent clouds at twilight, ARRI Alexa 65, Kodak 2383 LUT.",
                "recommended_intent": "create",
                "recommended_adapter": "image_gen",
            },
            {
                "id": "gen_minimax_video",
                "title": "Omni-Modal Reference-to-Video (MiniMax H3)",
                "summary": "Animate any reference image or prompt into a 720p/1080p video with synced stereo audio.",
                "subject": "Dynamic scene motion anchored to reference visual identity",
                "environment": "Cinematic motion stage",
                "visual_style": "24fps Hollywood motion cadence with synced audio",
                "starter_prompt": "<Picture 1> smooth cinematic dolly forward with natural atmospheric sound and subtle lighting shifts.",
                "recommended_intent": "animate",
                "recommended_adapter": "minimax_h3",
            },
            {
                "id": "gen_plan_v1",
                "title": "6-Step Strategic Execution Plan (`plan.v1`)",
                "summary": "Decompose any complex goal into a finishable 6-step path with 6-part PromptAnatomy.",
                "subject": "End-to-end project execution blueprint",
                "environment": "KEYSTONE Planning & Authority Engine",
                "visual_style": "Deterministic `plan.v1` contract",
                "starter_prompt": "Create a complete 6-step execution plan and visual keyframe for launching an independent creative studio.",
                "recommended_intent": "analyze",
                "recommended_adapter": "qwen_27b",
            },
        ],
        skills=[
            {"id": "skill_gen_cognition", "name": "Qwen 27B Omni-Domain Planner", "capability": "cognition.reasoning", "adapter": "qwen_27b", "description": "Compiles raw user goals into 6-part PromptAnatomy and 6-step `plan.v1` blueprints."},
            {"id": "skill_gen_comfy", "name": "ComfyUI Multimodal Render Fabric", "capability": "image.generation", "adapter": "image_gen", "description": "Executes SDXL/Flux text-to-image, Img2Img, and 4K upscaling."},
            {"id": "skill_gen_h3", "name": "MiniMax H3 Ref2VA Video & Audio", "capability": "video.minimax_h3_ref2va", "adapter": "minimax_h3", "description": "Jointly synthesizes high-motion video and stereo audio."},
            {"id": "skill_gen_elevenlabs", "name": "ElevenLabs Neural Speech Studio", "capability": "audio.speech", "adapter": "elevenlabs_tts", "description": "Synthesizes studio-grade voiceovers and persona dialogue."},
        ],
    ),
]

PLAYBOOK_IDS: List[str] = [p.id for p in CANONICAL_PLAYBOOKS]
PLAYBOOKS_BY_ID: Dict[str, Playbook] = {p.id: p for p in CANONICAL_PLAYBOOKS}


class PlaybookRegistry:
    """Authoritative registry for the 16 preserved domain playbooks."""

    @classmethod
    def list_playbooks(cls) -> List[Playbook]:
        return list(CANONICAL_PLAYBOOKS)

    @classmethod
    def list_ids(cls) -> List[str]:
        return list(PLAYBOOK_IDS)

    @classmethod
    def get(cls, playbook_id: str) -> Playbook:
        norm = (playbook_id or "").strip().lower()
        return PLAYBOOKS_BY_ID.get(norm, PLAYBOOKS_BY_ID["general"])

    @classmethod
    def exists(cls, playbook_id: str) -> bool:
        norm = (playbook_id or "").strip().lower()
        return norm in PLAYBOOKS_BY_ID

    @classmethod
    def resolve_id(cls, playbook_id: str) -> str:
        norm = (playbook_id or "").strip().lower()
        return norm if norm in PLAYBOOKS_BY_ID else "general"
