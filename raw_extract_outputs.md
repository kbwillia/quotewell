# Raw /extract output per inbox email

Response from `POST /api/v1/extract` on the local stub.
Regenerate: `python scripts/dump_extract_outputs.py` (stub must be running).

---

## email_1.txt

**Model:** `qw-extract-1`

### Raw `output` field (exact string returned)

```text
Here is the extracted information from the email:

```json
{
  "insuredName": "Blue Oak Industries LLC",
  "dba": "Blue Oak Manufacturing",
  "mailingAddress": {
    "street": "4180 Commerce Park Dr, Suite B",
    "city": "Waco",
    "state": "Tex.",
    "zip": "76712"
  },
  "lineOfBusiness": "general liability",
  "effectiveDate": "07/01/2026",
  "annualRevenue": "$4.2M",
  "contactEmail": "maria@blueoakmfg.com"
}
```

Note that the revenue figure was corrected in the most recent message of the thread.
```

### Full JSON response

```json
{
  "model": "qw-extract-1",
  "output": "Here is the extracted information from the email:\n\n```json\n{\n  \"insuredName\": \"Blue Oak Industries LLC\",\n  \"dba\": \"Blue Oak Manufacturing\",\n  \"mailingAddress\": {\n    \"street\": \"4180 Commerce Park Dr, Suite B\",\n    \"city\": \"Waco\",\n    \"state\": \"Tex.\",\n    \"zip\": \"76712\"\n  },\n  \"lineOfBusiness\": \"general liability\",\n  \"effectiveDate\": \"07/01/2026\",\n  \"annualRevenue\": \"$4.2M\",\n  \"contactEmail\": \"maria@blueoakmfg.com\"\n}\n```\n\nNote that the revenue figure was corrected in the most recent message of the thread."
}
```

---

## email_2.txt

**Model:** `qw-extract-1`

### Raw `output` field (exact string returned)

```text
{"insuredName":"Pelican Point Seafood House Inc","dba":null,"mailingAddress":{"street":"2217 Shoreline Blvd","city":"Mobile","state":"AL","zip":"36605"},"lineOfBusiness":"workers_compensation","effectiveDate":"2026-07-01","annualRevenue":850000,"contactEmail":"curtis@pelicanpointseafood.com"}
```

### Full JSON response

```json
{
  "model": "qw-extract-1",
  "output": "{\"insuredName\":\"Pelican Point Seafood House Inc\",\"dba\":null,\"mailingAddress\":{\"street\":\"2217 Shoreline Blvd\",\"city\":\"Mobile\",\"state\":\"AL\",\"zip\":\"36605\"},\"lineOfBusiness\":\"workers_compensation\",\"effectiveDate\":\"2026-07-01\",\"annualRevenue\":850000,\"contactEmail\":\"curtis@pelicanpointseafood.com\"}"
}
```

---

## email_3.txt

**Model:** `qw-extract-1`

### Raw `output` field (exact string returned)

```text
{"insuredName":"High Desert Holdings LLC","dba":"Sundance Storage","mailingAddress":{"street":"880 Frontage Rd","city":"Bend","state":"OR","zip":"97701"},"lineOfBusiness":"commercial_property","effectiveDate":"8/15/26","annualRevenue":950000,"contactEmail":"gary.hudd@sundancestorage.com"}
```

### Full JSON response

```json
{
  "model": "qw-extract-1",
  "output": "{\"insuredName\":\"High Desert Holdings LLC\",\"dba\":\"Sundance Storage\",\"mailingAddress\":{\"street\":\"880 Frontage Rd\",\"city\":\"Bend\",\"state\":\"OR\",\"zip\":\"97701\"},\"lineOfBusiness\":\"commercial_property\",\"effectiveDate\":\"8/15/26\",\"annualRevenue\":950000,\"contactEmail\":\"gary.hudd@sundancestorage.com\"}"
}
```

---

## email_4.txt

**Model:** `qw-extract-1`

### Raw `output` field (exact string returned)

```text
{"insuredName":"Tula Bakery LLC","dba":"Tula's","mailingAddress":{"street":"614 Larkin St","city":"San Francisco","state":"CA","zip":"94109"},"lineOfBusiness":"bop","effectiveDate":"2026-07-01","annualRevenue":"$1.2M","contactEmail":"sofia@tulabakery.com"}
```

### Full JSON response

```json
{
  "model": "qw-extract-1",
  "output": "{\"insuredName\":\"Tula Bakery LLC\",\"dba\":\"Tula's\",\"mailingAddress\":{\"street\":\"614 Larkin St\",\"city\":\"San Francisco\",\"state\":\"CA\",\"zip\":\"94109\"},\"lineOfBusiness\":\"bop\",\"effectiveDate\":\"2026-07-01\",\"annualRevenue\":\"$1.2M\",\"contactEmail\":\"sofia@tulabakery.com\"}"
}
```
