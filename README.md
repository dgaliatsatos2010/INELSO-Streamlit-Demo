# INELSO Streamlit Demo v0.1

Standalone Streamlit prototype for Service 21 and Service 26.

## What it includes

- Greek customer-facing UI
- Service 21 metrics, item facility, discrimination, Cronbach alpha
- Service 26 before/after progress, improvement, READY/human-review summary
- Technical details hidden in expanders
- Demo Mode with the current controlled demonstration results
- Upload CSV mode for independent analysis
- 0 official grade writes

## Local run

Create a virtual environment if desired, then:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Service 21 upload format

One row per completed attempt and one numeric/binary item-response column per question.
Binary 0/1 columns are automatically preferred when present.

## Service 26 upload format

Required columns:
- learner_id
- attempt (1 or 2)
- score

Optional columns:
- confidence
- status (READY / ESCALATE)

## Deployment note

The existing Moodle/PHP implementation remains unchanged. This Streamlit app is a parallel interactive analytics layer that can be deployed on Streamlit Community Cloud and linked back into Moodle/LTI.
