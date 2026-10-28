# ResQ Zambia
### AI-Powered Emergency Triage and Dispatch for Low-Resource Urban Communities

ResQ Zambia is a web-based emergency triage and dispatch system designed to support emergency reporting and response coordination in low-resource urban communities. It combines text-based incident classification with a dispatcher dashboard and a USSD access channel to explore how emergency services can become more accessible to people using both smartphones and basic feature phones.

## The Problem

Reporting an emergency and getting the right response can be difficult when access to smartphones, internet connectivity, and centralised dispatch services is limited. Emergency reports also need to be categorised and prioritised quickly so they can be directed to the appropriate response team.

ResQ Zambia explores a technology-assisted approach to these challenges within the Zambian context.

## Key Features

- **AI-assisted incident triage:** Uses text classification to identify incident categories and estimate severity from written reports.
- **Emergency categorisation:** Supports Medical, Fire, and Crime incident types.
- **Severity assessment:** Classifies incidents into Critical, High, and Low severity levels.
- **Dispatch dashboard:** Provides a central interface for reviewing and managing emergency reports.
- **Role-based access:** Supports separate access roles for administrators, dispatchers, police, fire services, and medical responders.
- **USSD access:** Includes a feature-phone reporting channel designed around Africa's Talking integration.
- **Incident tracking:** Supports monitoring incident status through the response workflow.

## How It Works

1. An incident is submitted through a supported reporting channel.
2. The triage component processes the report text and predicts an incident category and severity.
3. The system applies classification rules and keyword-based overrides where configured.
4. The incident is made available for review and coordination through the dispatch interface.
5. Authorised users can manage incident status according to their assigned roles.

## Technology Stack

- **Backend:** Python, Flask
- **Database and migrations:** Flask-SQLAlchemy, Flask-Migrate
- **Authentication:** Flask-Login
- **Real-time communication:** Flask-SocketIO
- **Natural language processing:** TF-IDF text vectorisation and Linear Support Vector Classification (LinearSVC), with rule-based overrides
- **Feature-phone integration:** Africa's Talking USSD API
- **Development and version control:** Git and GitHub

## Machine Learning Approach

The triage component uses text features to classify incident descriptions. TF-IDF converts text into numerical features, while LinearSVC is used for classification. Additional rules help account for important keywords and locally relevant phrasing.

The system is designed as an emergency triage support tool, not as a replacement for professional emergency assessment or human dispatch decisions.

## Running Locally

### Prerequisites

- Python compatible with the packages listed in `requirements.txt`
- Git
- Environment variables configured for the application

### Installation

Clone the repository and enter the project directory:

```bash
git clone https://github.com/cinedroidv2/resq-zambia.git
cd ResQ
```

Create and activate a virtual environment, then install the dependencies:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a local `.env` file with the environment variables required by the application. Use placeholder values in documentation and keep real credentials out of version control.

Start the application:

```bash
python run.py
```

Open the local address printed by the application in your browser.

## Project Structure

- `app/` — Flask application, routes, models, services, templates, and communication channels
- `docs/` — Project documentation and supporting materials
- `migrations/` — Database migration files
- `train_model.py` — Model training script
- `evaluate_model.py` — Model evaluation script
- `corpus.json` — Text classification corpus
- `requirements.txt` — Python dependencies
- `run.py` — Application entry point

## Evaluation

Model evaluation scripts and classification results are included in the repository. These materials support inspection of the triage model's performance.

Evaluation results should be interpreted in the context of the available dataset. Performance on a development corpus does not, by itself, establish readiness for real-world emergency deployment.

## Current Status

ResQ Zambia is an academic software project and prototype exploring AI-assisted emergency triage and dispatch in Zambia. Further validation, security testing, deployment testing, and integration with real emergency response workflows would be required before operational use.

## Security and Privacy

- Never commit `.env` files, API keys, passwords, or production credentials.
- Use secure password hashing and role-based access controls.
- Do not publish real personal information or identifiable emergency reports.
- Treat model predictions as decision support rather than definitive emergency assessments.

## Author

Developed as a Bachelor of Computer Science final-year project at ZCAS University 2026.

Project: ResQ Zambia — AI-Powered Emergency Triage and Dispatch System by Francine Mwamba Chileshe
