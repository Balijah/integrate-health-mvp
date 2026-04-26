# /financial_audit

Comprehensive cost analysis for Integrate Health MVP infrastructure.

## Context
Services in use: AWS EC2, ALB, RDS PostgreSQL, S3, SES, Bedrock (Claude), Deepgram Nova-2 Medical, CloudFront, GoDaddy.
Pilot client: Kare Health (single clinic).
Variable costs (Bedrock, Deepgram) are healthy COGS — they scale with revenue-generating visits.
Fixed costs (EC2, RDS, ALB) are overhead to minimize at current scale.

## Step 1: Gather Config
Read `backend/app/config.py`, `backend/app/services/transcription.py`, `backend/app/services/note_generation.py`, and `deploy.sh` to identify all external services and usage patterns.

## Step 2: Cost Analysis Per Service

**AWS Bedrock (Claude SOAP generation)**
- Identify model from `note_generation.py`
- Estimate input tokens: system prompt length + average transcript length
- Estimate output tokens: full SOAP JSON structure
- Calculate cost per visit at current Bedrock pricing
- Project monthly cost at 10 / 50 / 200 visits/day

**Deepgram (transcription)**
- Model: Nova-2 Medical (~$0.0043/minute pre-recorded)
- Estimate average functional medicine visit duration (20–45 min)
- Cost per visit
- Project monthly cost at 10 / 50 / 200 visits/day
- Flag: volume pricing available at scale?

**AWS EC2** — estimate based on visible instance usage patterns
**AWS RDS** — estimate based on config
**AWS ALB** — ~$16/month base + LCU costs
**AWS S3** — audio storage + tarball deploys + frontend static files
**CloudFront** — data transfer costs for frontend delivery
**AWS SES** — ~$0.10/1,000 emails (negligible at pilot scale)

## Step 3: Cost Table

| Service | 10 visits/day | 50 visits/day | 200 visits/day |
|---------|--------------|--------------|----------------|
| EC2 | $X/mo | $X/mo | $X/mo |
| RDS | $X/mo | $X/mo | $X/mo |
| ALB | $X/mo | $X/mo | $X/mo |
| S3 + CF | $X/mo | $X/mo | $X/mo |
| Bedrock | $X/mo | $X/mo | $X/mo |
| Deepgram | $X/mo | $X/mo | $X/mo |
| SES | $X/mo | $X/mo | $X/mo |
| **TOTAL** | **$X/mo** | **$X/mo** | **$X/mo** |
| **Per visit** | **$X.XX** | **$X.XX** | **$X.XX** |

## Step 4: Margin Analysis

At $99 / $149 / $199 per provider per month — what is gross margin at each scale tier?
How many providers needed to break even on infrastructure?

## Step 5: Optimization Opportunities (ranked by ROI)

**Immediate (zero risk):**
- Delete raw audio from S3 after transcript confirmed stored
- Confirm RDS Multi-AZ is OFF for pilot (not needed, saves ~$30-50/mo)
- CloudWatch log retention set (not infinite)

**Short-term:**
- EC2 + RDS Reserved Instances (1-year saves ~40%)
- Bedrock prompt optimization (shorter prompt = lower token cost)
- Deepgram enterprise/pre-pay pricing at volume

**Medium-term:**
- Audio compression before upload
- Cache repeated note generation for same transcript

## Step 6: Financial Risk Flags
- Is there a Deepgram spending cap?
- Is there an AWS budget alert configured?
- Is Bedrock token usage logged per visit (needed for accurate COGS)?
- Any zombie resources (unused EC2, unattached EBS, empty S3 buckets)?

## Output
```
## FINANCIAL AUDIT REPORT — [DATE]

### CURRENT ESTIMATED MONTHLY COSTS
[table]

### COST PER VISIT PROCESSED
[at each scale]

### MARGIN ANALYSIS
[table]

### TOP 3 COST DRIVERS
1. [service] — $X/mo — why

### OPTIMIZATION RECOMMENDATIONS
[ranked by ROI]

### FINANCIAL RISK FLAGS

### ASSUMPTIONS & DATA GAPS
```
