# ARCHITECTURE.md - Project ARCHITECTURE
The purpose of this document is to provide an overview of the architecture of the project, including its components, their interactions, and the overall design principles. It is structured as follows:
1. File Structure
2. Data Flow
3. Key Design Decisions
4. Extension Points
5. Conventions

## 1. File structure
The project is organized into the following directories and files:
```
.
├── AGENTS.md
├── ARCHITECTURE.md
├── HEARTBEAT.md
├── IDENTITY.md
├── memory
├── resources
│   ├── daily_papers.json
│   ├── digests
│   │   ├── digest_YYYY-MM-DD.json
│   │   └── digest_YYYY-MM-DD.md
│   ├── filtered_papers.json
│   ├── papers
│   │   ├── YYMM.XXXXXv1.txt
│   │   └── download_metadata.json
│   └── scored_papers_summary.json
├── scripts
│   ├── deliver_digest_markdown.py
│   ├── download_full_papers.py
│   ├── fetch_papers.py
│   ├── fetch_prefilter.sh
│   ├── make_digest_markdown.py
│   ├── prefilter_papers.py
│   └── process_deliver.sh
├── skills
│   ├── preference-updater
│   │   ├── scripts
│   │   │   └── update_preferences.py
│   │   └── SKILL.md
│   ├── preference-wizard
│   │   ├── scripts
│   │   │   └── save_preferences.py
│   │   └── SKILL.md
│   └── score-papers
│       ├── references
│       │   └── scoring_algorithm.md
│       └── SKILL.md
├── SOUL.md
├── SPEC.md
├── TOOLS.md
├── USER.md
└── user_preferences.json
```

