# Hackathon compliance

Verified against the official
[All Things Agentic Hackathon rules](https://allthingsagentichackathon.devpost.com/rules)
on 2026-08-10.

This document separates binding requirements from optional scoring bonuses and
from ByFeel's internal strategy. The rules, not the internal brief, control.

## Contest timing

- Submission period: August 3, 2026 at 09:00 PT through August 31, 2026 at
  17:00 PT.
- Judging: September 1, 2026 at 09:00 PT through October 1, 2026 at 23:45 PT.
- Winners are expected on or around October 8, 2026 at 10:00 PT.
- A Devpost account and Internet access are required.

## Mandatory application requirements

Every project must:

- be a next-generation autonomous agent that operates beyond a standard chat
  loop;
- use Gemini 3.5 or newer through the Gemini API or Vertex AI;
- use at least one Google agent framework: Google ADK, GenAI SDK, Antigravity
  SDK, or GenKit;
- use at least one Google Cloud infrastructure service, with examples including
  Cloud Run, Cloud SQL, Firestore, GKE, and Pub/Sub;
- enter exactly one of the three official categories;
- run consistently on its intended platform and match the submitted video and
  description;
- support English at minimum;
- be new work created during the submission period, while disclosing any
  incorporated pre-existing code or work;
- use third-party tools, data, media, and integrations only with the necessary
  permissions and licenses;
- be original entrant-owned work and respect intellectual-property, privacy,
  publicity, and other third-party rights.

ByFeel currently satisfies the technology direction through Gemini 3.5+,
planned Google ADK integration, and its existing Firestore/Cloud Storage test
infrastructure. Final eligibility still depends on the entrant confirming age,
residency, employment/conflict, ownership, and new-work conditions.

## Official categories

### Taskmaster

An action-oriented agent that completes a messy, multi-step workflow rather
than merely producing text.

### Collaborative Partner

An agent that leads, asks clarifying questions, guides step by step, captures
feedback, and adapts to the user's way of thinking.

### Fortified Enterprise Fleet

A scalable network of institutional agents with cataloging, long-running state,
enterprise infrastructure, governance, security, and production-data controls.

ByFeel should enter **Collaborative Partner**. Its teacher clarification,
feedback-backed procedure repair, and learner guidance directly match that
category. It should not claim the enterprise category or add agents merely to
look more complex.

## Submission deliverables

The final Devpost submission must include:

- the selected category;
- a hosted-project URL when available; hosting is highly encouraged;
- an English text description covering features, functionality, technologies,
  other data sources, findings, and learnings;
- a public or private GitHub, GitLab, or Bitbucket repository URL; a private
  repository must grant access to `testing@devpost.com` and
  `cloudhackathons@google.com`;
- step-by-step README spin-up instructions for local setup or cloud deployment;
- a clear architecture diagram;
- a publicly visible YouTube or Vimeo demonstration video, in English or with
  English subtitles, no longer than four minutes;
- a video overview of the problem and value proposition plus the application
  operating in practice;
- visual proof in the video that the backend runs on Google Cloud;
- a working project or test build available without charge or restriction
  through the judging period, with private testing credentials when applicable.

The video and submission must not include unlawful, discriminatory, offensive,
privacy-infringing, or third-party-rights-infringing material, or unauthorized
third-party advertising, logos, slogans, trademarks, sponsorship, or
endorsement.

## Deployment requirement and current boundary

The rules explicitly require the demonstration video to prove that the backend
is running on Google Cloud, giving examples such as a Cloud Run dashboard,
Vertex AI logs, or a `.run` URL.

The active ByFeel goal prohibits Cloud Run deployment and prohibits creation or
reconfiguration of cloud resources. Therefore:

- this goal can build and validate the complete local judge experience;
- existing Firestore and Cloud Storage test usage proves cloud infrastructure
  integration but does not, by itself, prove that the backend is cloud-hosted;
- documentation and the evidence view must not claim a cloud-hosted backend;
- final contest submission remains blocked on a later, separately approved
  Google Cloud backend deployment and video proof unless the user changes the
  current boundary.

No deployment mutation is authorized by this compliance finding.

## Judging

### Stage One — pass/fail viability

The submission must include all required materials, reasonably address its
category, and reasonably apply the mandatory technologies.

### Stage Two — weighted score

1. **Innovation & Operational Utility — 40%**
   - eliminate real-world friction;
   - demonstrate high-value autonomous behavior beyond simple chat;
   - under the Evolving Knowledge Engine lens, actively synthesize or mutate
     data and handle unusual, messy, or complex unstructured inputs.
2. **Architectural Discipline & Tech Stack — 30%**
   - justify engineering decisions;
   - decouple components, manage state, and tolerate failures;
   - under the Evolving Knowledge Engine lens, show disciplined data
     architecture and efficient context handling.
3. **Demo & Production Readiness — 30%**
   - make the friction, architecture, and execution undeniable within four
     minutes;
   - show an unedited live agent action through UI changes, logs, or database
     updates;
   - provide reproducible setup, a clean architecture diagram, and visible
     Google Cloud deployment proof.

The ByFeel blinded-probe boundary and append-only, human-approved procedure
mutation are especially relevant to the first two criteria. Gate A evidence
must remain honest because a seeded or rehearsed UI path is not proof of real
mechanism reliability.

### Stage Three — optional bonus contributions

- Public build content stating it was created for this hackathon: up to 0.2
  points.
- Social post with `#AllThingsAgenticHackathon`: up to 0.2 points.
- Additional successfully integrated Google AI models such as Gemma, Veo, or
  Lyria: 0.2 each, up to 0.6 points.

These are optional. They should not displace core ByFeel validation or add
unnecessary models.

## Eligibility restrictions

Entrants must be above the age of majority in their jurisdiction, or at least
20 in Taiwan. The rules exclude residents of Italy, Quebec, Crimea, Cuba, Iran,
Syria, North Korea, Sudan, Belarus, Russia, other OFAC-designated jurisdictions,
and persons or entities restricted by export controls or sanctions. Contest
entities, specified relatives/household members, government-agency employees,
and entrants whose participation creates an actual or apparent conflict are
also ineligible.

Teams must contain only eligible individuals, list all members on Devpost, and
appoint a representative. Employer/company entrants must have the necessary
knowledge and consent. Startup-prize eligibility separately requires an
incorporated organization and corporate email address.

The entrant, not the application, must verify these facts before submission.

## Official versus internal terminology

The official category names are Taskmaster, Collaborative Partner, and
Fortified Enterprise Fleet. The official judging text also uses Continuous
Action Engine, Evolving Knowledge Engine, and Multi-Agent Nexus as
criterion-specific lenses, but the rules do not formally declare a one-to-one
alias table.

The internal brief's mapping remains a reasonable strategy:

- Taskmaster → Continuous Action Engine;
- Collaborative Partner → Evolving Knowledge Engine;
- Fortified Enterprise Fleet → Multi-Agent Nexus.

It must still be described as an interpretation rather than an official mapping.

## ByFeel compliance actions

- Integrate Google ADK as meaningful orchestration, not branding.
- Retain Gemini 3.5+ model routing and record model use safely.
- Preserve existing Firestore/Storage integration without unauthorized cloud
  mutation.
- Add the architecture diagram and complete README spin-up instructions.
- Build a reliable unedited four-minute rehearsal path.
- Disclose the repository's pre-existing MVP work and identify what was built
  during the submission period.
- Audit every demonstration video, reference image, name, logo, and data source
  for ownership, consent, privacy, and third-party rights before submission.
- Plan a separately approved cloud-backend deployment before the final video.
