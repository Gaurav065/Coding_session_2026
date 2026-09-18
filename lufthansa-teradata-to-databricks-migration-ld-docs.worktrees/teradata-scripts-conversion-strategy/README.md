# Lufthansa Teradata to Databricks Migration - L&D Documentation

Repository containing learning and development (L&D) presentations, SOP deep-dives, developer guides, and architectural discovery documents for the **Lufthansa Teradata to Databricks Migration**.

---

## 📁 Repository Contents

All primary documentation decks and guides are located in [`Important documents and pdfs/`](./Important%20documents%20and%20pdfs/):

| Document / Presentation | Description |
|---|---|
| **`Session1_Program_Overview 2.pptx`** | High-level program overview and migration scope. |
| **`Session2_POD_Lead_Hour 1.pptx`** | Pod lead briefing and operating model. |
| **`01 - Pod-Lead Hour - RCA & Troubleshooting 4.pptx`** | Root Cause Analysis (RCA) procedures & troubleshooting guidelines. |
| **`02 - Brickify Deep-Dive - Conversion Engine 3.pptx`** | Technical deep-dive into the Brickify automated SQL/code conversion engine. |
| **`03 - DAB Deep-Dive - Targets, Variables & Env Promotion 3.pptx`** | Databricks Asset Bundles (DAB), target environments, variable substitution & promotion. |
| **`04 - The Conversion Rulebook - Defect Prevention 3.pptx`** | Rulebook and best practices to prevent conversion defects. |
| **`08 - Data Load Utility - SOP Deep-Dive 2.pptx`** | Standard Operating Procedure (SOP) for the Data Load Utility. |
| **`09 - DDL Deployment Utility - SOP Deep-Dive 1.pptx`** | SOP for the DDL Deployment Utility. |
| **`10 - Git & Azure DevOps Workflow 2.pptx`** | Git branching, pull request policies, and Azure DevOps CI/CD pipelines. |
| **`11 - Teradata Defect & Out-of-Scope Tracker 2.pptx`** | Tracking methodology for Teradata-specific syntax issues and out-of-scope items. |
| **`3_Workstation_Setup_Deck 1.pptx`** | Developer environment & workstation setup guide. |
| **`E2E_Stream_Job_Developer_Guide 4.html`** | Interactive developer guide for End-to-End Stream jobs. |
| **`Lufthansa_ADW_Discovery (1) 3.html`** | Lufthansa ADW (Analytics Data Warehouse) discovery & inventory reference. |

---

## 🔗 External Resources

* [**Reference Links & Google Drive Assets**](./reference_links.md): External file links and project shared drive resources.

---

## 🔄 Teradata script conversion

The reusable conversion workflow is documented in
[`TERADATA_TO_DATABRICKS_CONVERSION_PROMPT.md`](./TERADATA_TO_DATABRICKS_CONVERSION_PROMPT.md).
The corresponding repository skill is
[`teradata-to-databricks-conversion`](./.github/skills/teradata-to-databricks-conversion/SKILL.md).
It converts scripts in logical blocks, validates each checkpoint, compares final
outputs with the verification results in the hands-on archive, and records every
Teradata-to-Databricks semantic gap.

## 🔒 Confidentiality
This repository contains proprietary project assets and documentation. Access is restricted to authorized project team members.
