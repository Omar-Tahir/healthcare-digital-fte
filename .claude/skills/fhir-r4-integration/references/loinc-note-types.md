# LOINC Note Type Codes — Reference

## Document Types (DocumentReference.type.coding)

| LOINC Code | Note Type | Coding Relevance | Priority |
|-----------|-----------|-----------------|----------|
| 18842-5 | Discharge Summary | Primary coding document | P0 |
| 34117-2 | H&P Note | Admission documentation | P0 |
| 11506-3 | Progress Note | Daily clinical assessment | P1 |
| 11504-8 | Operative Note | Surgical procedure detail | P0 |
| 28570-0 | Procedure Note | Non-surgical procedures | P1 |
| 11488-4 | Consultation Note | Specialist assessment | P1 |
| 47039-3 | ED Note | Emergency department | P0 |
| 34133-9 | Summarization of Episode Note | Episode summary | P1 |
| 11492-6 | History and Physical | Alternative to 34117-2 | P0 |
| 57133-1 | Referral Note | Referral documentation | P2 |

## C-CDA Section LOINC Codes

| LOINC Code | Section Name | Content Type |
|-----------|-------------|-------------|
| 10164-2 | History of Present Illness | Narrative HPI |
| 51848-0 | Assessment | Physician assessment |
| 18776-5 | Plan of Treatment | Treatment plan |
| 8648-8 | Hospital Course | Discharge summary narrative |
| 29545-1 | Physical Examination | Physical exam findings |
| 10160-0 | Medications | Current medications |
| 11450-4 | Problems | Problem list |
| 30954-2 | Results | Lab results |
| 42349-1 | Reason for Referral | Why patient was referred |
| 46240-8 | History of Hospitalizations | Prior admissions |

## Processing Priority

For coding analysis, process documents in this order:
1. Discharge Summary (18842-5) — most complete
2. H&P (34117-2) — admission context
3. Operative Notes (11504-8) — procedure codes
4. Progress Notes (11506-3) — interval changes
5. Consultation Notes (11488-4) — specialist input

Always concatenate multiple relevant notes for a complete
picture, but weight the discharge summary most heavily.
