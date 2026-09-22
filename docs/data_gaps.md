# Data gaps and synthetic stand-ins

Every dataset or parameter that AquaOS cannot yet source from a verified primary document is listed here.
Code and YAML that use a stand-in label it `SYNTHETIC`.

## Environment finding (2026-09-22)

The cloud development environment's egress policy returns HTTP 403 for all candidate source hosts.
WebFetch is blocked as well. None of the values below could be verified against a primary source, so none has been
entered from memory. Each source must be fetched once from an environment that allows these hosts. After that, the
offline cache serves them.

| Source | Host(s) | Needed for | Status |
|---|---|---|---|
| Reclamation 24-Month Study | www.usbr.gov | Lake Mead projections, shortage tier scenarios | UNVERIFIED (blocked) |
| USGS Water Data APIs | api.waterdata.usgs.gov, waterservices.usgs.gov | streamflow, groundwater levels | UNVERIFIED (blocked) |
| ADWR well / groundwater data | new.azwater.gov | AMA budgets, well levels | UNVERIFIED (blocked) |
| CAP delivery and energy | www.cap-az.com | CAP allocation by tier, pumping energy | UNVERIFIED (blocked) |
| EIA API | api.eia.gov | AZ electricity price, generation mix, carbon intensity | UNVERIFIED (blocked) |
| SRP / APS tariff sheets | www.srpnet.com, www.aps.com | TOU windows, energy and demand charges | UNVERIFIED (blocked) |
| NOAA / PRISM climate | www.ncei.noaa.gov, prism.oregonstate.edu | temperature for demand models, heat-wave statistics | UNVERIFIED (blocked) |
| EPA SDWIS / ECHO | echo.epa.gov | system characteristics, compliance context | UNVERIFIED (blocked) |

## Synthetic stand-ins in use

_None yet. Phase 1 adds entries here: Valley City network, demand coefficients, synthetic temperature series,
CAP tier reduction table, groundwater budget, pump curves._
