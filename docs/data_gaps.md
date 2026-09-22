# Data gaps and synthetic stand-ins

Every dataset or parameter that AquaOS cannot yet source from a verified primary document is listed here.
Code and YAML that use a stand-in label it `SYNTHETIC`.

## Source status (updated 2026-09-22)

The session's network policy was widened on 2026-09-22. Status per source:

| Source | Host(s) | Needed for | Status |
|---|---|---|---|
| Reclamation 24-Month Study | www.usbr.gov | Lake Mead projections | **Fetched.** Latest published is the July 2026 Most Probable (the August/September 2026 PDFs return 404 as of 2026-09-22). Connector: `aquaos.data.connectors.usbr` |
| Reclamation 2027-2028 Operating Guidelines + ROD (2026-08-21) | www.usbr.gov | Shortage condition for 2027-2028 | **Fetched and used** in `params/colorado_river_shortage.yaml` |
| CAP Colorado River operations page | www.cap-az.com | CY2026 Tier 1 reduction | **Fetched and used** in `params/colorado_river_shortage.yaml` |
| A.R.S. 45-852.01 | www.azleg.gov | Long-term storage credit fraction | **Fetched and used** in `params/recharge_credits.yaml` |
| NOAA NCEI (GHCN-Daily, Global Hourly) | www.ncei.noaa.gov | Temperature | **Fetched and used** in `params/phoenix_climate.yaml`. Connector: `aquaos.data.connectors.noaa` |
| USGS Water Data APIs | waterservices.usgs.gov | Streamflow, groundwater levels | Reachable, not used yet (aquifer parameters are synthetic) |
| ADWR well / groundwater data | azwater.gov | AMA data, well levels | **Blocked by the site** (Cloudflare challenge, HTTP 403). Needs a manual download or an ADWR data-service endpoint |
| EIA API | api.eia.gov | AZ electricity price, carbon intensity (Phase 2) | Reachable. **Requires a free API key** (HTTP 403 without one) |
| SRP tariff sheets | www.srpnet.com | TOU tariffs (Phase 2) | **Blocked by the site** (HTTP 403 to automated clients). Needs a manual download |
| APS tariff sheets | www.aps.com | TOU tariffs (Phase 2) | Reachable, not fetched yet |
| PRISM | prism.oregonstate.edu | Gridded climate | Reachable, not used yet |
| EPA ECHO / SDWIS | echo.epa.gov | System context | Reachable, not used yet |

## Synthetic stand-ins in use

| Stand-in | Replaces | Label |
|---|---|---|
| Valley City network | A real utility `.inp` | SYNTHETIC |
| Demand coefficients (per-capita use, diurnal patterns, temperature response) | Utility billing/AMI and SCADA data | SYNTHETIC |
| City CAP subcontract and M&I share of shortage | CAP subcontract schedules and CAP shortage-sharing by priority pool | SYNTHETIC / ASSUMPTION |
| Groundwater allowance and aquifer parameters | ADWR AWS determination, ADWR/USGS well data, Phoenix AMA groundwater model | SYNTHETIC |
| Recharge credit balance | ADWR long-term storage account data | SYNTHETIC |
| Pump efficiencies and curves | Pump test data | SYNTHETIC |
| Hypothetical 1.0 maf Arizona reduction | No source; stress test beyond the 2027-2028 guidelines | ASSUMPTION |
